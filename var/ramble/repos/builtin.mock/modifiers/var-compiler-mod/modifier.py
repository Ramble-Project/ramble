# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.modkit import *


class VarCompilerMod(BasicModifier):
    """Mock modifier to test concretize variable expansion in compiler specs"""

    name = "var-compiler-mod"
    tags("test")

    mode("test_mode", description="A test mode")
    default_mode("test_mode")

    variable(
        "mod_compiler_spec",
        default="gcc@13.1.0",
        description="Compiler spec defined in modifier",
        modes=["test_mode"],
    )

    with when("package_manager_family=spack"):
        define_compiler(
            "mod-compiler",
            pkg_spec="{mod_compiler_spec}",
            compiler_spec="{mod_compiler_spec}",
        )
