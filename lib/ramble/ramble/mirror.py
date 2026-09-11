# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


"""
This file contains code for creating ramble mirror directories.  A
mirror is an organized hierarchy containing specially named archive
files.  This enabled ramble to know where to find files in a mirror if
the main server for a particular input is down.  Or, if the computer
where ramble is run is not connected to the internet, it allows ramble
to download inputs directly from a mirror (e.g., on an intranet).
"""

import collections
import operator
import os.path

import ruamel.yaml.error as yaml_error

from llnl.util.compat import Mapping

import ramble.config
import ramble.error
import ramble.fetch_strategy as fs
from ramble.util import json_util
from ramble.util.logger import logger

import spack.url
import spack.util.spack_yaml
from spack.util.spack_yaml import syaml_dict


def _is_string(url):
    return isinstance(url, str)


def _display_mirror_entry(size, name, url, type_=None):
    if type_:
        type_ = "".join((" (", type_, ")"))
    else:
        type_ = ""

    print("%-*s%s%s" % (size + 4, name, url, type_))


class Mirror:
    """Represents a named location for storing input tarballs.

    Mirrors have a fetch_url that indicate where and how artifacts are fetched
    from them, and a push_url that indicate where and how artifacts are pushed
    to them.  These two URLs are usually the same.
    """

    def __init__(self, fetch_url, push_url=None, name=None):
        self._fetch_url = fetch_url
        self._push_url = push_url
        self._name = name

    def __eq__(self, other):
        return self._fetch_url == other._fetch_url and self._push_url == other._push_url

    def to_json(self, stream=None):
        return json_util.dump(self.to_dict(), stream)

    def to_yaml(self, stream=None):
        return spack.util.spack_yaml.dump(self.to_dict(), stream)

    @staticmethod
    def from_yaml(stream, name=None):
        try:
            data = spack.util.spack_yaml.load(stream)
            return Mirror.from_dict(data, name)
        except yaml_error.MarkedYAMLError as e:
            raise spack.util.spack_yaml.SpackYAMLError("error parsing YAML mirror:", str(e)) from e

    @staticmethod
    def from_json(stream, name=None):
        try:
            d = json_util.load(stream)
            return Mirror.from_dict(d, name)
        except Exception as e:
            raise MirrorError(f"error parsing JSON mirror: {e}") from e

    def to_dict(self):
        return syaml_dict(
            [("fetch", self._fetch_url), ("push", self._push_url or self._fetch_url)]
        )

    @staticmethod
    def from_dict(d, name=None):
        if isinstance(d, str):
            return Mirror(d, name=name)
        else:
            return Mirror(d["fetch"], d["push"], name=name)

    def display(self, max_len=0):
        if self._push_url is None:
            _display_mirror_entry(max_len, self._name, self.fetch_url)
        else:
            _display_mirror_entry(max_len, self._name, self.fetch_url, "fetch")
            _display_mirror_entry(max_len, self._name, self.push_url, "push")

    def __str__(self):
        name = self._name
        if name is None:
            name = ""
        else:
            name = f' "{name}"'

        if self._push_url is None:
            return f"[Mirror{name} ({self._fetch_url})]"

        return f"[Mirror{name} (fetch: {self._fetch_url}, push: {self._push_url})]"

    def __repr__(self):
        return "".join(
            (
                "Mirror(",
                ", ".join(
                    f"{k}={repr(v)}"
                    for k, v in (
                        ("fetch_url", self._fetch_url),
                        ("push_url", self._push_url),
                        ("name", self._name),
                    )
                    if k == "fetch_url" or v
                ),
                ")",
            )
        )

    @property
    def name(self):
        return self._name or "<unnamed>"

    @property
    def fetch_url(self):
        return self._fetch_url if _is_string(self._fetch_url) else self._fetch_url["url"]

    @fetch_url.setter
    def fetch_url(self, url):
        self._fetch_url["url"] = url
        self._normalize()

    @property
    def push_url(self):
        if self._push_url is None:
            return self._fetch_url if _is_string(self._fetch_url) else self._fetch_url["url"]
        return self._push_url if _is_string(self._push_url) else self._push_url["url"]

    @push_url.setter
    def push_url(self, url):
        self._push_url["url"] = url
        self._normalize()

    def _normalize(self):
        if self._push_url is not None and self._push_url == self._fetch_url:
            self._push_url = None


class MirrorCollection(Mapping):
    """A mapping of mirror names to mirrors."""

    def __init__(self, mirrors=None, scope=None):
        self._mirrors = collections.OrderedDict(
            (name, Mirror.from_dict(mirror, name))
            for name, mirror in (
                mirrors.items()
                if mirrors is not None
                else ramble.config.get("mirrors", scope=scope).items()
            )
        )

    def __eq__(self, other):
        return self._mirrors == other._mirrors

    def to_json(self, stream=None):
        return json_util.dump(self.to_dict(True), stream)

    def to_yaml(self, stream=None):
        return spack.util.spack_yaml.dump(self.to_dict(True), stream)

    def to_dict(self, recursive=False):
        return syaml_dict(
            sorted(
                ((k, (v.to_dict() if recursive else v)) for (k, v) in self._mirrors.items()),
                key=operator.itemgetter(0),
            )
        )

    @staticmethod
    def from_dict(d):
        return MirrorCollection(d)

    def __getitem__(self, item):
        return self._mirrors[item]

    def display(self):
        max_len = max(len(mirror.name) for mirror in self._mirrors.values())
        for mirror in self._mirrors.values():
            mirror.display(max_len)

    def lookup(self, name_or_url):
        """Looks up and returns a Mirror.

        If this MirrorCollection contains a named Mirror under the name
        [name_or_url], then that mirror is returned.  Otherwise, [name_or_url]
        is assumed to be a mirror URL, and an anonymous mirror with the given
        URL is returned.
        """
        result = self.get(name_or_url)

        if result is None:
            result = Mirror(fetch_url=name_or_url)

        return result

    def __iter__(self):
        return iter(self._mirrors)

    def __len__(self):
        return len(self._mirrors)


def _determine_extension(fetcher):
    if isinstance(fetcher, fs.URLFetchStrategy):
        if fetcher.expand_archive:
            # If we fetch with a URLFetchStrategy, use URL's archive type
            ext = spack.url.determine_url_file_extension(fetcher.url)

            if ext:
                # Remove any leading dots
                ext = ext.lstrip(".")
            else:
                # TODO: Clean up this message...
                # TODO: Add extension to input files...
                msg = """\
Unable to parse extension from {0}.

If this URL is for a tarball but does not include the file extension
in the name, you can explicitly declare it with the following syntax:

    input_file('1.2.3', 'hash', extension='tar.gz')

If this URL is for a download like a .jar or .whl that does not need
to be expanded, or an uncompressed installation script, you can tell
Ramble not to expand it with the following syntax:

    input_file('1.2.3', 'hash', expand=False)
"""
                raise MirrorError(msg.format(fetcher.url))
        else:
            # If the archive shouldn't be expanded, don't check extension.
            ext = None
    else:
        # Otherwise we'll make a .tar.gz ourselves
        ext = "tar.gz"

    return ext


class MirrorReference:
    """A ``MirrorReference`` stores the relative paths where you can store a
    resource in a mirror directory.

    The appropriate storage location is given by ``storage_path``. The
    ``cosmetic_path`` property provides a reference that a human could generate
    themselves based on reading the details of the input.

    A user can iterate over a ``MirrorReference`` object to get all the
    possible names that might be used to refer to the resource in a mirror;
    this includes names generated by previous naming schemes that are no-longer
    reported by ``storage_path`` or ``cosmetic_path``.
    """

    def __init__(self, cosmetic_path, global_path=None):
        self.global_path = global_path
        self.cosmetic_path = cosmetic_path

    @property
    def storage_path(self):
        if self.global_path:
            return self.global_path
        else:
            return self.cosmetic_path

    def __iter__(self):
        if self.global_path:
            yield self.global_path
        yield self.cosmetic_path


def mirror_archive_paths(fetcher, per_input_ref):
    """Returns a ``MirrorReference`` object which keeps track of the relative
    storage path of the resource associated with the specified ``fetcher``."""
    ext = None or _determine_extension(fetcher)

    if ext:
        per_input_ref += f".{ext}"

    global_ref = fetcher.mirror_id()
    if global_ref:
        global_ref = os.path.join("_input-cache", global_ref)
    if global_ref and ext:
        global_ref += f".{ext}"

    return MirrorReference(per_input_ref, global_ref)


def add(name, url, scope):
    """Add a named mirror in the given scope"""
    mirrors = ramble.config.get("mirrors", scope=scope)
    if not mirrors:
        mirrors = syaml_dict()

    if name in mirrors:
        logger.die(f"Mirror with name {name} already exists.")

    items = [(n, u) for n, u in mirrors.items()]
    mirror_data = url
    items.insert(0, (name, mirror_data))
    mirrors = syaml_dict(items)
    ramble.config.set("mirrors", mirrors, scope=scope)


def remove(name, scope):
    """Remove the named mirror in the given scope"""
    mirrors = ramble.config.get("mirrors", scope=scope)
    if not mirrors:
        mirrors = syaml_dict()

    if name not in mirrors:
        logger.die(f"No mirror with name {name}")

    old_value = mirrors.pop(name)
    ramble.config.set("mirrors", mirrors, scope=scope)

    debug_msg_url = "url %s"
    debug_msg = ["Removed mirror %s with"]
    values = [name]

    try:
        fetch_value = old_value["fetch"]
        push_value = old_value["push"]

        debug_msg.extend(("fetch", debug_msg_url, "and push", debug_msg_url))
        values.extend((fetch_value, push_value))
    except TypeError:
        debug_msg.append(debug_msg_url)
        values.append(old_value)

    logger.debug(" ".join(debug_msg) % tuple(values))
    logger.msg(f"Removed mirror {name}.")


class MirrorStats:
    def __init__(self):
        self.present = {}
        self.new = {}
        self.errors = set()

        self.current_spec = None
        self.added_resources = set()
        self.existing_resources = set()

    def _tally_current_spec(self):
        if self.current_spec:
            if self.added_resources:
                self.new[self.current_spec] = len(self.added_resources)
            if self.existing_resources:
                self.present[self.current_spec] = len(self.existing_resources)
            self.added_resources = set()
            self.existing_resources = set()
        self.current_spec = None

    def stats(self):
        self._tally_current_spec()
        return list(self.present), list(self.new), list(self.errors)

    def already_existed(self, resource):
        self.present[resource] = True

    def added(self, resource):
        self.new[resource] = True

    def error(self, resource):
        self.errors.add(self.current_spec)


class MirrorError(ramble.error.RambleError):
    """Superclass of all mirror-creation related errors."""

    def __init__(self, msg, long_msg=None):
        super().__init__(msg, long_msg)
