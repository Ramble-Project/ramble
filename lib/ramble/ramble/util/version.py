# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import functools
import os
import re
from typing import Any, Optional

from packaging.version import InvalidVersion
from packaging.version import Version as PackagingVersion

import ramble
import ramble.paths


@functools.total_ordering
class Version:
    """Wrapper around packaging.version.Version supporting rich comparisons with strings."""

    raw: str
    _version: PackagingVersion

    def __init__(self, version: str):
        if not isinstance(version, str):
            raise ValueError(f"Invalid version: '{version}'")

        raw = version.strip()
        try:
            self._version = PackagingVersion(raw)
        except InvalidVersion as err:
            raise ValueError(f"Invalid version: '{version}'") from err
        self.raw = raw

    @classmethod
    def _coerce(cls, other: Any) -> Optional["Version"]:
        if isinstance(other, cls):
            return other
        try:
            return cls(other)
        except ValueError:
            return None

    def __eq__(self, other: object) -> bool:
        coerced = self._coerce(other)
        if coerced is None:
            return NotImplemented
        return self._version == coerced._version

    def __lt__(self, other: object) -> bool:
        coerced = self._coerce(other)
        if coerced is None:
            return NotImplemented
        return self._version < coerced._version

    def __str__(self) -> str:
        return self.raw


def get_version() -> str:
    """Get a descriptive version of this instance of Ramble.

    Outputs '<PEP440 version> (<git commit sha>)'.

    The commit sha is only added when available.
    """
    version = ramble.ramble_version
    git_hash = get_git_hash(path=ramble.paths.prefix)

    if git_hash:
        version += f" ({git_hash})"

    return version


def get_git_hash(path: str = ramble.paths.prefix) -> Optional[str]:
    """Get get hash from a path

    Outputs '<git commit sha>'.
    """
    import spack.util.git

    git_path = os.path.join(path, ".git")
    if os.path.exists(git_path):
        git = spack.util.git.git()
        if not git:
            return None
        rev = git(
            "-C",
            path,
            "rev-parse",
            "HEAD",
            output=str,
            error=os.devnull,
            fail_on_error=False,
        )
        if git.returncode != 0:
            return None
        match = re.match(r"[a-f\d]{7,}$", rev)
        if match:
            return match.group(0)

    return None
