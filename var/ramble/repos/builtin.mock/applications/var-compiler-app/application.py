# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.appkit import *


class VarCompilerApp(ExecutableApplication):
    """Test application to verify concretize variable expansion in specs"""

    name = "var-compiler-app"

    executable("echo", "echo", use_mpi=False)
    workload("test_wl", executable="echo")

    workload_variable(
        "my_compiler_spec",
        default="gcc@12.2.0",
        description="Compiler spec variable",
        workloads=["test_wl"],
    )

    define_compiler(
        "var-compiler",
        pkg_spec="{my_compiler_spec}",
        compiler_spec="{my_compiler_spec}",
    )

    software_spec(
        "var-pkg",
        pkg_spec="zlib@1.2.13",
        compiler="var-compiler",
    )
