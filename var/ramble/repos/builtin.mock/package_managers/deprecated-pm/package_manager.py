# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from typing import List

from ramble.pkgmankit import *


class DeprecatedPm(PackageManagerBase):
    """Mock package manager to test declarative deprecations."""

    name = "deprecated-pm"

    deprecate(
        deprecated_in="0.7.0",
        removed_in="99.0.0",
        replacement="user-managed",
    )

    def get_package_list(self, workspace):
        del workspace
        return []

    def package_name_from_spec(self, spec: str) -> str:
        return spec

    def environment_load_commands(self) -> List[str]:
        return []

    def environment_unload_commands(self) -> List[str]:
        return []
