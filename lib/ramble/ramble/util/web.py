# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import concurrent.futures
import errno
import os
import os.path
import re
import shutil
import ssl
import sys
from typing import Any, Dict, List
from urllib.error import URLError
from urllib.request import Request, urlopen

from llnl.util.filesystem import mkdirp, rename

import ramble
import ramble.config
import ramble.error
from ramble.util.logger import logger

import spack.util.gcs as gcs_util
import spack.util.s3 as s3_util
import spack.util.url as url_util
from spack.error import SpackError
from spack.util.path import convert_to_posix_path

#: User-Agent used in Request objects
RAMBLE_USER_AGENT = f"Ramblebot/{ramble.ramble_version}"


def uses_ssl(parsed_url):
    if parsed_url.scheme == "https":
        return True

    if parsed_url.scheme == "s3":
        endpoint_url = os.environ.get("S3_ENDPOINT_URL")
        if not endpoint_url:
            return True

        if url_util.parse(endpoint_url, scheme="https").scheme == "https":
            return True

    elif parsed_url.scheme == "gs":
        logger.debug("(uses_ssl) GCS Blob is https")
        return True

    return False


def read_from_url(url, accept_content_type=None):
    url = url_util.parse(url)

    verify_ssl = ramble.config.get("config:verify_ssl")

    # Timeout in seconds for web requests
    timeout = ramble.config.get("config:connect_timeout", 10)

    # Don't even bother with a context unless the URL scheme is one that uses
    # SSL certs.
    if uses_ssl(url):
        if verify_ssl:
            context = ssl.create_default_context()  # novm
        else:
            context = ssl._create_unverified_context()
    else:
        context = None

    url_scheme = url.scheme
    url = url_util.format(url)
    if sys.platform == "win32" and url_scheme == "file":
        url = convert_to_posix_path(url)
    req = Request(url, headers={"User-Agent": RAMBLE_USER_AGENT})

    content_type = None
    is_web_url = url_scheme in ("http", "https")
    try:
        if accept_content_type and is_web_url:
            # Make a HEAD request first to check the content type.  This lets
            # us ignore tarballs and gigantic files.
            # It would be nice to do this with the HTTP Accept header to avoid
            # one round-trip.  However, most servers seem to ignore the header
            # if you ask for a tarball with Accept: text/html.
            req.method = "HEAD"
            resp = _urlopen(req, timeout=timeout, context=context)

            content_type = get_header(resp.headers, "Content-type")

        # Do the real GET request when we know it's just HTML.
        req.method = "GET"
        response = _urlopen(req, timeout=timeout, context=context)
    except (URLError, SpackError) as err:
        raise RambleWebError("Download failed") from err

    if accept_content_type and not is_web_url:
        content_type = get_header(response.headers, "Content-type")

    reject_content_type = accept_content_type and (
        content_type is None or not content_type.startswith(accept_content_type)
    )

    if reject_content_type:
        logger.debug(
            "ignoring page {}{}{}".format(
                url, " with content type " if content_type is not None else "", content_type or ""
            )
        )

        return None, None, None

    return response.geturl(), response.headers, response


def check_push_scheme(url):
    """Validate that a URL scheme is supported for push operations.

    Args:
        url (str or urllib.parse.ParseResult): URL to check

    Returns:
        urllib.parse.ParseResult: Parsed URL object

    Raises:
        NotImplementedError: If the URL scheme is not supported for push operations
    """
    remote_url = url_util.parse(url)
    if url_util.local_file_path(remote_url) is not None:
        return remote_url

    if remote_url.scheme in ("s3", "gs"):
        return remote_url

    raise NotImplementedError(f"Unrecognized URL scheme: {remote_url.scheme}")


def push_to_url(local_file_path, remote_path, keep_original=True, extra_args=None):
    if sys.platform == "win32":
        if remote_path[1] == ":":
            remote_path = "file://" + remote_path
    remote_url = check_push_scheme(remote_path)
    remote_file_path = url_util.local_file_path(remote_url)
    logger.debug(f"Trying to backup file to: {remote_file_path}")
    if remote_file_path is not None:
        mkdirp(os.path.dirname(remote_file_path))
        if keep_original:
            shutil.copy(local_file_path, remote_file_path)
        else:
            try:
                rename(local_file_path, remote_file_path)
            except OSError as e:
                if e.errno == errno.EXDEV:
                    # NOTE(opadron): The above move failed because it crosses
                    # filesystem boundaries.  Copy the file (plus original
                    # metadata), and then delete the original.  This operation
                    # needs to be done in separate steps.
                    shutil.copy2(local_file_path, remote_file_path)
                    os.remove(local_file_path)
                else:
                    raise

    elif remote_url.scheme == "s3":
        if extra_args is None:
            extra_args = {}

        remote_path = remote_url.path
        while remote_path.startswith("/"):
            remote_path = remote_path[1:]

        s3 = s3_util.create_s3_session(
            remote_url, connection=s3_util.get_mirror_connection(remote_url)
        )
        s3.upload_file(local_file_path, remote_url.netloc, remote_path, ExtraArgs=extra_args)

        if not keep_original:
            os.remove(local_file_path)

    elif remote_url.scheme == "gs":
        gcs = gcs_util.GCSBlob(remote_url)
        gcs.upload_to_blob(local_file_path)
        if not keep_original:
            os.remove(local_file_path)

    else:
        raise NotImplementedError(f"Unrecognized URL scheme: {remote_url.scheme}")


def push_dir_to_url(local_dir_path, remote_dir_path, max_workers=None):
    """Upload an entire directory tree recursively to a remote URL in parallel."""
    remote_url = check_push_scheme(remote_dir_path)

    if max_workers is None:
        max_workers = ramble.config.get("config:upload_threads")

    if remote_url.scheme == "gs":
        from google.cloud.storage import transfer_manager

        gcs_bucket = gcs_util.GCSBucket(remote_url)
        if not gcs_bucket.exists():
            gcs_bucket.create()

        rel_files = []
        for root, _, files in os.walk(local_dir_path):
            for file in files:
                src_file = os.path.join(root, file)
                rel_path = os.path.relpath(src_file, local_dir_path)
                rel_files.append(rel_path)

        if not rel_files:
            return

        prefix = remote_url.path.lstrip("/")
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        transfer_manager.upload_many_from_filenames(
            gcs_bucket.bucket,
            rel_files,
            source_directory=local_dir_path,
            blob_name_prefix=prefix,
            worker_type="thread",
            max_workers=max_workers,
            raise_exception=True,
        )
        return

    files_to_upload = []
    for root, _, files in os.walk(local_dir_path):
        for file in files:
            src_file = os.path.join(root, file)
            rel_path = os.path.relpath(src_file, local_dir_path)
            dest_file = os.path.join(remote_dir_path, rel_path).replace("\\", "/")
            files_to_upload.append((src_file, dest_file))

    if not files_to_upload:
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(push_to_url, src, dest, keep_original=True)
            for src, dest in files_to_upload
        ]
        for future in concurrent.futures.as_completed(futures):
            future.result()


def url_exists(url):
    url = url_util.parse(url)
    local_path = url_util.local_file_path(url)
    if local_path:
        return os.path.exists(local_path)

    if url.scheme == "s3":
        # Check for URL specific connection information
        s3 = s3_util.create_s3_session(url, connection=s3_util.get_mirror_connection(url))

        try:
            s3.get_object(Bucket=url.netloc, Key=url.path.lstrip("/"))
            return True
        except s3.ClientError as err:
            if err.response["Error"]["Code"] == "NoSuchKey":
                return False
            raise err

    elif url.scheme == "gs":
        gcs = gcs_util.GCSBlob(url)
        return gcs.exists()

    # otherwise, just try to "read" from the URL, and assume that *any*
    # non-throwing response contains the resource represented by the URL
    try:
        read_from_url(url)
        return True
    except (RambleWebError, URLError):
        return False


def _debug_print_delete_results(result):
    if "Deleted" in result:
        for d in result["Deleted"]:
            logger.debug(f'Deleted {d["Key"]}')
    if "Errors" in result:
        for e in result["Errors"]:
            logger.debug(f'Failed to delete {e["Key"]} ({e["Message"]})')


def remove_url(url, recursive=False):
    url = url_util.parse(url)

    local_path = url_util.local_file_path(url)
    if local_path:
        if recursive:
            shutil.rmtree(local_path)
        else:
            os.remove(local_path)
        return

    if url.scheme == "s3":
        # Try to find a mirror for potential connection information
        s3 = s3_util.create_s3_session(url, connection=s3_util.get_mirror_connection(url))
        bucket = url.netloc
        if recursive:
            # Because list_objects_v2 can only return up to 1000 items
            # at a time, we have to paginate to make sure we get it all
            prefix = url.path.strip("/")
            paginator = s3.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

            delete_request: Dict[str, List[Dict[str, Any]]] = {"Objects": []}
            for item in pages.search("Contents"):
                if not item:
                    continue

                delete_request["Objects"].append({"Key": item["Key"]})

                # Make sure we do not try to hit S3 with a list of more
                # than 1000 items
                if len(delete_request["Objects"]) >= 1000:
                    r = s3.delete_objects(Bucket=bucket, Delete=delete_request)
                    _debug_print_delete_results(r)
                    delete_request = {"Objects": []}

            # Delete any items that remain
            if len(delete_request["Objects"]):
                r = s3.delete_objects(Bucket=bucket, Delete=delete_request)
                _debug_print_delete_results(r)
        else:
            s3.delete_object(Bucket=bucket, Key=url.path.lstrip("/"))
        return

    elif url.scheme == "gs":
        if recursive:
            bucket = gcs_util.GCSBucket(url)
            bucket.destroy(recursive=recursive)
        else:
            blob = gcs_util.GCSBlob(url)
            blob.delete_blob()
        return

    # Don't even try for other URL schemes.


def _urlopen(req, *args, **kwargs):
    """Wrapper for compatibility with old versions of Python."""
    url = req
    try:
        url = url.get_full_url()
    except AttributeError:
        pass

    opener = urlopen
    if url_util.parse(url).scheme == "s3":
        import spack.s3_handler

        opener = spack.s3_handler.open  # type: ignore[assignment]
    elif url_util.parse(url).scheme == "gs":
        import spack.gcs_handler

        opener = spack.gcs_handler.gcs_open  # type: ignore[assignment]

    try:
        return opener(req, *args, **kwargs)
    except TypeError as err:
        # If the above fails because of 'context', call without 'context'.
        if "context" in kwargs and "context" in str(err):
            del kwargs["context"]
        return opener(req, *args, **kwargs)


def get_header(headers, header_name):
    """Looks up a dict of headers for the given header value.

    Looks up a dict of headers, [headers], for a header value given by
    [header_name].  Returns headers[header_name] if header_name is in headers.
    Otherwise, the first fuzzy match is returned, if any.

    This fuzzy matching is performed by discarding word separators and
    capitalization, so that for example, "Content-length", "content_length",
    "conTENtLength", etc., all match.  In the case of multiple fuzzy-matches,
    the returned value is the "first" such match given the underlying mapping's
    ordering, or unspecified if no such ordering is defined.

    If header_name is not in headers, and no such fuzzy match exists, then a
    KeyError is raised.
    """

    def unfuzz(header):
        return re.sub(r"[ _-]", "", header).lower()

    try:
        return headers[header_name]
    except KeyError:
        unfuzzed_header_name = unfuzz(header_name)
        for header, value in headers.items():
            if unfuzz(header) == unfuzzed_header_name:
                return value
        raise


class RambleWebError(ramble.error.RambleError):
    """Superclass for Ramble web spidering errors."""
