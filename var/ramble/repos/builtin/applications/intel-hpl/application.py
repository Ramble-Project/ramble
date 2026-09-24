# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

from ramble.appkit import *
from ramble.base_app.builtin.hpl import Hpl as HplBase
from ramble.base_app.builtin.intel_mkl_benchmarks import (
    IntelMklBenchmarks as IntelMklBenchmarksBase,
)


class IntelHpl(HplBase, IntelMklBenchmarksBase):
    """Define HPL application using Intel MKL optimized binary from intel-oneapi-mkl package"""

    name = "intel-hpl"

    maintainers("rfbgo")

    tags("intel-optimized")

    with when("package_manager_family=spack"):
        define_compiler("gcc14", pkg_spec="gcc@14.2.0")

        software_spec(
            "imkl_{application::intel-hpl::version}",
            pkg_spec="intel-oneapi-mkl@{application::intel-hpl::version} threads=openmp",
            compiler="gcc14",
        )
        software_spec(
            "impi2021p17",
            pkg_spec="intel-oneapi-mpi@2021.17.2",
        )

        required_package("intel-oneapi-mkl")

    #  We call the runme_intel64_prv script instead of the underlying xhpl_intel64_dynamic
    #  since it sets up derived env var HPL_HOST_NODE for numa placement control.
    #  We copy in the xhpl_intel64_dynamic binary to the running dir
    #  because runme_intel64_prv invokes it using "./"
    stage_files(
        name="stage-binary",
        src=os.path.join("{hpl_bench_dir}", "xhpl_intel64_dynamic"),
        dst=os.path.join("{experiment_run_dir}", "."),
        method="cp",
    )

    stage_files(
        name="stage-runme",
        src=os.path.join("{hpl_bench_dir}", "runme_intel64_prv.txt"),
        dst=os.path.join("{experiment_run_dir}", "runme_intel64_prv"),
        method="install",
    )

    executable(
        "execute",
        "{hpl_run_script}",
        use_mpi=True,
    )

    # At 2025.0.1, the runme_intel64_prv script was changed to .txt format
    # (runme_intel64_dynamic was changed to .txt at 2025.1.0)
    with when("application_version@:2025.0.0"):
        workload("standard", executables=["stage-binary", "execute"])
        workload("calculator", executables=["stage-binary", "execute"])

        workload_variable(
            "hpl_run_script",
            default=os.path.join("{hpl_bench_dir}", "runme_intel64_prv"),
            description="Path to the HPL run script.",
            workloads=["*"],
        )

    with when("application_version@2025.0.1:"):
        workload(
            "standard", executables=["stage-binary", "stage-runme", "execute"]
        )
        workload(
            "calculator",
            executables=["stage-binary", "stage-runme", "execute"],
        )

        workload_variable(
            "hpl_run_script",
            default=os.path.join("{experiment_run_dir}", "runme_intel64_prv"),
            description="Path to the HPL run script.",
            workloads=["*"],
        )

    workload_group("standard", workloads=["standard"], mode="append")
    workload_group("calculator", workloads=["calculator"], mode="append")

    workload_variable(
        "hpl_bench_dir",
        default=os.path.join("{mkl_benchmark_path}", "mp_linpack"),
        description="Path to Intel HPL benchmarks directory",
        workloads=["*"],
    )

    environment_variable(
        "MPI_PROC_NUM",
        value="{n_ranks}",
        description="Number of total ranks",
        workloads=["*"],
    )

    environment_variable(
        "MPI_PER_NODE",
        value="{processes_per_node}",
        description="Number of ranks per node",
        workloads=["*"],
    )

    environment_variable(
        "NUMA_PER_MPI",
        value="{numa_per_mpi}",
        description="Number of NUMA nodes per rank",
        workloads=["*"],
    )

    environment_variable(
        "HPL_EXE",
        value="xhpl_intel64_dynamic",
        description="HPL executable name",
        workloads=["*"],
    )

    workload_variable(
        "numa_per_mpi",
        description="numa per mpi process",
        default="1",
        workloads=["*"],
    )
