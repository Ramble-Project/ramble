# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
"""Perform tests of the util/web functions"""

import pytest

from ramble.util import web

from spack.util import url as url_util


def test_get_header():
    headers = {"Content-type": "text/plain"}

    assert web.get_header(headers, "Content-type") == "text/plain"

    # test fuzzy lookup
    assert web.get_header(headers, "contentType") == "text/plain"
    headers["contentType"] = "text/html"
    assert web.get_header(headers, "contentType") == "text/html"

    # test no match
    with pytest.raises(KeyError):
        web.get_header(headers, "ContentLength")


def test_gcs_url_exists(monkeypatch):

    def _get_client():
        return MockGcsClient()

    import spack.util.gcs

    monkeypatch.setattr(spack.util.gcs, "gcs_client", _get_client)
    test_url = "gs://abc/xyz.txt"
    with pytest.raises(MockGcsClientError, match="Mock error for bucket abc"):
        web.url_exists(test_url)


class MockGcsClient:
    def bucket(self, name):
        raise MockGcsClientError(f"Mock error for bucket {name}")


class MockGcsClientError(Exception):
    pass


def test_uses_ssl(monkeypatch):
    # Test https
    url = url_util.parse("https://example.com")
    assert web.uses_ssl(url)

    # Test http
    url = url_util.parse("http://example.com")
    assert not web.uses_ssl(url)

    # Test s3 without S3_ENDPOINT_URL
    url = url_util.parse("s3://my-bucket/key")
    assert web.uses_ssl(url)

    # Test s3 with http S3_ENDPOINT_URL
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://s3.local")
    url = url_util.parse("s3://my-bucket/key")
    assert not web.uses_ssl(url)

    # Test s3 with https S3_ENDPOINT_URL
    monkeypatch.setenv("S3_ENDPOINT_URL", "https://s3.local")
    url = url_util.parse("s3://my-bucket/key")
    assert web.uses_ssl(url)
    monkeypatch.delenv("S3_ENDPOINT_URL")

    # Test gs
    url = url_util.parse("gs://my-bucket/key")
    assert web.uses_ssl(url)

    # Test file
    url = url_util.parse("file:///path/to/file")
    assert not web.uses_ssl(url)


def test_url_exists_file(tmpdir):
    # Test existing file
    p = tmpdir.join("exists.txt")
    p.write("content")
    assert web.url_exists(f"file://{str(p)}")

    # Test non-existing file
    assert not web.url_exists(f"file://{str(p)}/nonexistent.txt")


def test_push_to_url_file(tmpdir):
    local_file = tmpdir.join("local.txt")
    local_file.write("some data")
    remote_dir = tmpdir.mkdir("remote")
    remote_file_path = remote_dir.join("remote.txt")

    # Test copy
    web.push_to_url(str(local_file), f"file://{str(remote_file_path)}", keep_original=True)
    assert local_file.exists()
    assert remote_file_path.exists()
    assert remote_file_path.read() == "some data"
    remote_file_path.remove()

    # Test move
    web.push_to_url(str(local_file), f"file://{str(remote_file_path)}", keep_original=False)
    assert not local_file.exists()
    assert remote_file_path.exists()
    assert remote_file_path.read() == "some data"


def test_remove_url_file(tmpdir):
    # Test remove file
    p = tmpdir.join("file.txt")
    p.write("content")
    web.remove_url(f"file://{str(p)}")
    assert not p.exists()

    # Test remove directory recursively
    d = tmpdir.mkdir("dir")
    f = d.join("file.txt")
    f.write("content")
    web.remove_url(f"file://{str(d)}", recursive=True)
    assert not d.exists()


def test_push_dir_to_url_file(tmpdir):
    local_dir = tmpdir.mkdir("src_dir")
    f1 = local_dir.join("file1.txt")
    f1.write("data1")
    sub_dir = local_dir.mkdir("subdir")
    f2 = sub_dir.join("file2.txt")
    f2.write("data2")

    remote_dir = tmpdir.mkdir("dest_dir")
    dest_url = f"file://{str(remote_dir)}"

    web.push_dir_to_url(str(local_dir), dest_url)

    assert remote_dir.join("file1.txt").exists()
    assert remote_dir.join("file1.txt").read() == "data1"
    assert remote_dir.join("subdir").join("file2.txt").exists()
    assert remote_dir.join("subdir").join("file2.txt").read() == "data2"


def test_push_dir_to_url_gcs(monkeypatch, tmpdir):
    local_dir = tmpdir.mkdir("src_gcs_dir")
    f1 = local_dir.join("file1.txt")
    f1.write("data1")

    uploaded_args = {}

    class MockGCSBucket:
        def __init__(self, url):
            self.bucket = "mock_bucket_obj"

        def exists(self):
            return True

        def create(self):
            pass

    def mock_upload_many(bucket, filenames, source_directory, blob_name_prefix, **kwargs):
        uploaded_args["bucket"] = bucket
        uploaded_args["filenames"] = filenames
        uploaded_args["source_directory"] = source_directory
        uploaded_args["blob_name_prefix"] = blob_name_prefix
        uploaded_args.update(kwargs)

    import google.cloud.storage.transfer_manager as tm

    import spack.util.gcs as gcs_util

    monkeypatch.setattr(gcs_util, "GCSBucket", MockGCSBucket)
    monkeypatch.setattr(tm, "upload_many_from_filenames", mock_upload_many)

    web.push_dir_to_url(str(local_dir), "gs://mock-bucket/prefix/path")

    assert uploaded_args["bucket"] == "mock_bucket_obj"
    assert "file1.txt" in uploaded_args["filenames"]
    assert uploaded_args["source_directory"] == str(local_dir)
    assert uploaded_args["blob_name_prefix"] == "prefix/path/"


def test_check_push_scheme():
    url_file = web.check_push_scheme("file:///path/to/file")
    assert url_file.scheme == "file"

    url_s3 = web.check_push_scheme("s3://bucket/key")
    assert url_s3.scheme == "s3"

    url_gs = web.check_push_scheme("gs://bucket/key")
    assert url_gs.scheme == "gs"

    with pytest.raises(NotImplementedError, match="Unrecognized URL scheme: http"):
        web.check_push_scheme("http://example.com/file")

    with pytest.raises(NotImplementedError, match="Unrecognized URL scheme: ftp"):
        web.check_push_scheme("ftp://example.com/file")


def test_push_dir_to_url_unsupported_scheme(tmpdir):
    local_dir = tmpdir.mkdir("src_dir")
    f1 = local_dir.join("file1.txt")
    f1.write("content")

    with pytest.raises(NotImplementedError, match="Unrecognized URL scheme: http"):
        web.push_dir_to_url(str(local_dir), "http://example.com/remote_dir")


def test_read_from_url_and_url_exists_web_error(monkeypatch):
    def _mock_urlopen(*args, **kwargs):
        raise web.URLError("mock connection error")

    monkeypatch.setattr(web, "_urlopen", _mock_urlopen)

    with pytest.raises(web.RambleWebError, match="Download failed"):
        web.read_from_url("http://example.com/nonexistent")

    with pytest.raises(web.RambleWebError, match="Download failed"):
        web.read_from_url("http://example.com/nonexistent", accept_content_type="text/html")

    assert not web.url_exists("http://example.com/nonexistent")


def test_gcs_open_missing_blob_raises_ramble_web_error(monkeypatch):
    import spack.util.gcs

    class DummyGCSBlob:
        def __init__(self, url):
            self.blob_path = "missing/blob.tar.gz"

        def exists(self):
            return False

    monkeypatch.setattr(spack.util.gcs, "GCSBlob", DummyGCSBlob)

    with pytest.raises(web.RambleWebError, match="Download failed"):
        web.read_from_url("gs://my-bucket/missing/blob.tar.gz")

    assert not web.url_exists("gs://my-bucket/missing/blob.tar.gz")
