# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from typing import List

from ramble.pkg_man.builtin.environment_modules import EnvironmentModules
from ramble.pkgmankit import *


class Eessi(EnvironmentModules):
    """Package manager definition for EESSI

    This package manager uses the European Environment for Scientific Software
    Installations to stream binaries from an EESSI mirror.

    https://www.eessi.io/


    To control the target architecture used, add EESSI_SOFTWARE_SUBDIR_OVERRIDE
    to the workspace's environment variable definitions.
    """

    name = "eessi"
    _spec_prefix = "eessi"

    package_manager_variable(
        "eessi_version",
        default="2023.06",
        description="Version of EESSI to use",
    )

    package_manager_family("eessi")

    register_builtin("eessi_init")

    def eessi_init(self):
        return [
            ". /cvmfs/software.eessi.io/versions/{eessi_version}/init/bash >> {log_file} 2>&1"
        ]

    register_builtin(
        "module_load",
        depends_on=["package_manager_builtin::eessi::eessi_init"],
    )

    def environment_load_commands(self) -> List[str]:
        return self.eessi_init() + self.module_load()
