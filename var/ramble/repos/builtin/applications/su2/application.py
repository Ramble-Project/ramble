# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.appkit import *


class Su2(ExecutableApplication):
    """Define SU2 (Stanford University Unstructured) application.

    See https://su2code.github.io/ for more details.
    """

    name = "su2"

    tags("cfd", "multiphysics", "aerospace")

    maintainers("linsword13")

    version("8.2.0", "Version 8.2.0 of SU2", preferred=True)

    with when("package_manager_family=spack"):
        define_compiler("gcc12", pkg_spec="gcc@12.2.0")
        # See https://github.com/spack/spack/pull/50601 for building with intel mpi.
        software_spec("impi2021p13", pkg_spec="intel-oneapi-mpi@2021.13.1")
        software_spec(
            "su2-{application::su2::version}",
            pkg_spec="su2@{application::su2::version} +mpi +openmp",
            compiler="gcc12",
        )
        required_package("su2")

    input_file(
        "inv_channel_in",
        url="https://raw.githubusercontent.com/su2code/Tutorials/refs/tags/v8.2.0/compressible_flow/Inviscid_Bump/inv_channel.cfg",
        sha256="de01ac92d184e312fecad1aca72eba61808c70503ed3197daddadb0e22892205",
        description="input deck used in https://su2code.github.io/tutorials/Inviscid_Bump",
        expand=False,
    )
    input_file(
        "inv_mesh_in",
        url="https://raw.githubusercontent.com/su2code/Tutorials/refs/tags/v8.2.0/compressible_flow/Inviscid_Bump/mesh_channel_256x128.su2",
        sha256="1a7eac64244f1e4206eae3eb2af48a41d614ace59b357026c5f9dd0f56b1271f",
        description="input deck used in https://su2code.github.io/tutorials/Inviscid_Bump",
        expand=False,
    )

    stage_files(src="{input_path}/*", dst=".")

    executable(
        "execute",
        template=["{su2_executable} {input_config}"],
        use_mpi=True,
    )

    workload(
        "inv_channel",
        executables=["stage-files", "execute"],
        inputs=["inv_channel_in", "inv_mesh_in"],
    )

    workload_group("all_workloads", workloads=["inv_channel"])

    workload_variable(
        "input_path",
        default="{workload_input_dir}",  # only works where inputs do not need expanding
        description="Path to the input for experiments",
        workload="inv_channel",
    )

    workload_variable(
        "input_config",
        default="inv_channel.cfg",
        description="Name of the input configuration file",
        workload="inv_channel",
    )

    workload_variable(
        "su2_executable",
        default="SU2_CFD",
        description="Path to the SU2 executable",
        workload_group="all_workloads",
    )

    # This is only used if using the SU2 parallel wrapper like parallel_computation.py
    environment_variable(
        "SU2_MPI_COMMAND",
        value="{mpi_command} -n %i %s",
        description="custom mpi command used by the wrapper",
        workload_group="all_workloads",
    )

    # The two env vars won't be needed after
    # https://github.com/spack/spack/pull/50495 is merged.
    environment_variable(
        "SU2_RUN",
        value="{su2_path}/bin",
        description="SU2 bin path",
        workload_group="all_workloads",
    )

    environment_variable(
        "SU2_HOME",
        value="{su2_path}",
        description="SU2 package prefix",
        workload_group="all_workloads",
    )

    success_criteria("completion", mode="string", match=".*?Exit Success")

    figure_of_merit(
        "Version",
        fom_regex=r".*?Release\s+(?P<version>[0-9\.]+)",
        group_name="version",
        units="",
        fom_type=FomType.CATEGORY,
    )

    figure_of_merit(
        "Average seconds per iteration",
        fom_regex=r".*?Avg. s/iter:\s+(?P<avg_sec_per_iter>[0-9\.]+)",
        group_name="avg_sec_per_iter",
        units="s",
        fom_type=FomType.TIME,
    )
