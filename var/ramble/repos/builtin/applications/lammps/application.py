# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

from ramble.appkit import *


class Lammps(ExecutableApplication):
    """Define LAMMPS application"""

    name = "lammps"

    maintainers("douglasjacobsen")

    tags("molecular-dynamics", "hpc-benchmark")

    define_compiler("gcc14", pkg_spec="gcc@14.2.0")

    workload_group("all_workloads", workloads=[])
    workload_group("standard_workloads", workloads=[])
    workload_group("configured_workloads", workloads=[])
    workload_group("intel_workloads", workloads=[])

    workload_variable(
        "intel_test_path",
        default=os.path.join("{lammps-stage}", "src", "INTEL", "TEST"),
        description="Path for Intel Test files",
        workload_group="all_workloads",
    )

    workload_variable(
        "examples_path",
        default=os.path.join("{lammps-stage}", "examples"),
        description="Path for example files",
        workload_group="all_workloads",
    )

    workload_variable(
        "input_stage",
        default="stable_23Jun2022_update3",
        description="Stage name of LAMMPS input archive",
        workload_group="all_workloads",
    )

    workload_variable(
        "input_path",
        default=os.path.join("{intel_test_path}", "in.{workload_name}"),
        description="Path to input file for workload",
        workload_group="intel_workloads",
    )

    workload_variable(
        "input_path",
        default=os.path.join("{lammps-stage}", "bench", "in.{workload_name}"),
        description="Path for the workload input file.",
        workload_group="standard_workloads",
    )

    workload_variable(
        "lammps_flags",
        default="",
        description="Additional execution flags for lammps",
        workload_group="all_workloads",
    )

    version("20250722", "Version 20250722 of LAMMPS")
    version("20220623.4", "Version 20220623.4 of LAMMPS", preferred=True)

    with when("package_manager_family=spack"):
        software_spec(
            "intel-mpi",
            pkg_spec="intel-oneapi-mpi@2021.17.2",
        )

        software_spec(
            "lammps-{application::lammps::version}",
            pkg_spec="lammps@{application::lammps::version} +opt+manybody+molecule+kspace+rigid+openmp+openmp-package+asphere+dpd-basic+dpd-meso+dpd-react+dpd-smooth",
            compiler="gcc14",
        )

        required_package("lammps")

    input_file(
        "lammps-stage",
        url="https://github.com/lammps/lammps/archive/refs/tags/{input_stage}.tar.gz",
        target_dir="{application_input_dir}/lammps-input-stage",
        description="Stage of lammps source from release",
    )
    stage_files(
        name="stage-input",
        src="{input_path}",
        dst="{experiment_run_dir}/input.txt",
    )
    edit_file(
        "configure-reaxff-x",
        file_path="input.txt",
        match=r"x index .*",
        replace="x index {x}",
    )
    edit_file(
        "configure-reaxff-y",
        file_path="input.txt",
        match=r"y index .*",
        replace="y index {y}",
    )
    edit_file(
        "configure-reaxff-z",
        file_path="input.txt",
        match=r"z index .*",
        replace="z index {z}",
    )
    edit_file(
        "configure-reaxff-timesteps",
        file_path="input.txt",
        match=r"t index .*",
        replace="t index {timesteps}",
    )

    edit_file(
        "configure-size-scale-xx",
        file_path="input.txt",
        match=r"xx equal .*",
        replace="xx equal {xx}",
    )
    edit_file(
        "configure-size-scale-yy",
        file_path="input.txt",
        match=r"yy equal .*",
        replace="yy equal {yy}",
    )
    edit_file(
        "configure-size-scale-zz",
        file_path="input.txt",
        match=r"zz equal .*",
        replace="zz equal {zz}",
    )

    edit_file(
        "configure-run-timesteps",
        file_path="input.txt",
        match=r"run.*[0-9]+",
        replace="run\t\t{timesteps}",
    )

    edit_file(
        "configure-timestep-variables-main",
        file_path="input.txt",
        match=r"t index .*[0-9]+",
        replace="t index {main_timesteps}",
    )
    edit_file(
        "configure-timestep-variables-warmup",
        file_path="input.txt",
        match=r"w index .*[0-9]+",
        replace="w index {warmup_timesteps}",
    )
    edit_file(
        "configure-timestep-variables-multiplier",
        file_path="input.txt",
        match=r"m index .*[0-9]+",
        replace="m index {timestep_multiplier}",
    )

    exec_path = os.path.join("{lammps_path}", "bin", "lmp")

    executable(
        "execute",
        f"{exec_path}" + " -i input.txt {lammps_flags}",
        use_mpi=True,
    )

    edit_file(
        "set-data-path",
        file_path="input.txt",
        match=r"data\.",
        replace=os.path.join("{lammps-stage}", "bench", "data."),
    )

    edit_file(
        "set-eam-path",
        file_path="input.txt",
        match=r"Cu_u3\.eam",
        replace=os.path.join("{lammps-stage}", "bench", "Cu_u3.eam"),
    )

    edit_file(
        "change-root",
        file_path="input.txt",
        match=r"\$\{root\}",
        replace="{lammps-stage}" + os.path.sep,
    )

    stage_files(
        name="stage-cube",
        src=os.path.join("{intel_test_path}", "mW*.data"),
        dst="{experiment_run_dir}/.",
    )
    stage_files(
        name="stage-cube-sw",
        src=os.path.join("{intel_test_path}", "mW.sw"),
        dst="{experiment_run_dir}/.",
    )

    stage_files(
        name="stage-contents",
        src="{input_path}/*",
        dst="{experiment_run_dir}/.",
    )
    stage_files(
        name="stage-input-file",
        src="{input_file}",
        dst="input.txt",
    )

    workload(
        "lj",
        executables=[
            "stage-input",
            "configure-size-scale-xx",
            "configure-size-scale-yy",
            "configure-size-scale-zz",
            "configure-run-timesteps",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["lj"]):
        workload_group("all_workloads", mode="append")
        workload_group("standard_workloads", mode="append")
        workload_variable(
            "timesteps",
            default="100",
            description="Number of timesteps",
        )
        workload_variable(
            "xx",
            default="20*$x",
            description="xx value",
        )
        workload_variable(
            "yy",
            default="20*$y",
            description="yy value",
        )
        workload_variable(
            "zz",
            default="20*$z",
            description="zz value",
        )

    workload(
        "eam",
        executables=[
            "stage-input",
            "set-eam-path",
            "configure-size-scale-xx",
            "configure-size-scale-yy",
            "configure-size-scale-zz",
            "configure-run-timesteps",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["eam"]):
        workload_group("all_workloads", mode="append")
        workload_group("standard_workloads", mode="append")
        workload_variable(
            "timesteps",
            default="100",
            description="Number of timesteps",
        )
        workload_variable(
            "xx",
            default="20*$x",
            description="xx value",
        )
        workload_variable(
            "yy",
            default="20*$y",
            description="yy value",
        )
        workload_variable(
            "zz",
            default="20*$z",
            description="zz value",
        )

    workload(
        "chain",
        executables=[
            "stage-input",
            "set-data-path",
            "configure-run-timesteps",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["chain"]):
        workload_group("all_workloads", mode="append")
        workload_group("standard_workloads", mode="append")
        workload_variable(
            "timesteps",
            default="100",
            description="Number of timesteps",
        )

    workload(
        "chute",
        executables=[
            "stage-input",
            "set-data-path",
            "configure-run-timesteps",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["chute"]):
        workload_group("all_workloads", mode="append")
        workload_group("standard_workloads", mode="append")
        workload_variable(
            "timesteps",
            default="100",
            description="Number of timesteps",
        )

    workload(
        "rhodo",
        executables=["stage-input", "set-data-path", "execute"],
        input="lammps-stage",
    )
    with default_args(workloads=["rhodo"]):
        workload_group("all_workloads", mode="append")
        workload_group("standard_workloads", mode="append")
        workload_variable(
            "timesteps",
            default="100",
            description="Number of timesteps",
        )

    workload(
        "intel.airebo",
        executables=[
            "stage-input",
            "change-root",
            "configure-size-scale-xx",
            "configure-size-scale-yy",
            "configure-size-scale-zz",
            "configure-timestep-variables-main",
            "configure-timestep-variables-warmup",
            "configure-timestep-variables-multiplier",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["intel.airebo"]):
        workload_group("all_workloads", mode="append")
        workload_group("intel_workloads", mode="append")
        workload_variable(
            "warmup_timesteps",
            default="10",
            description="Number of warmup timesteps",
        )
        workload_variable(
            "main_timesteps",
            default="550",
            description="Number of main timesteps",
        )
        workload_variable(
            "timestep_multiplier",
            default="1",
            description="Multiplier for main timesteps",
        )
        workload_variable(
            "xx",
            default="17*$x",
            description="xx value",
        )
        workload_variable(
            "yy",
            default="16*$y",
            description="yy value",
        )
        workload_variable(
            "zz",
            default="2*$z",
            description="zz value",
        )

    workload(
        "intel.dpd",
        executables=[
            "stage-input",
            "change-root",
            "configure-size-scale-xx",
            "configure-size-scale-yy",
            "configure-size-scale-zz",
            "configure-timestep-variables-main",
            "configure-timestep-variables-warmup",
            "configure-timestep-variables-multiplier",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["intel.dpd"]):
        workload_group("all_workloads", mode="append")
        workload_group("intel_workloads", mode="append")
        workload_variable(
            "warmup_timesteps",
            default="10",
            description="Number of warmup timesteps",
        )
        workload_variable(
            "main_timesteps",
            default="4000",
            description="Number of main timesteps",
        )
        workload_variable(
            "timestep_multiplier",
            default="1",
            description="Multiplier for main timesteps",
        )
        workload_variable(
            "xx",
            default="20*$x",
            description="xx value",
        )
        workload_variable(
            "yy",
            default="20*$y",
            description="yy value",
        )
        workload_variable(
            "zz",
            default="20*$z",
            description="zz value",
        )

    workload(
        "intel.eam",
        executables=[
            "stage-input",
            "change-root",
            "configure-size-scale-xx",
            "configure-size-scale-yy",
            "configure-size-scale-zz",
            "configure-timestep-variables-main",
            "configure-timestep-variables-warmup",
            "configure-timestep-variables-multiplier",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["intel.eam"]):
        workload_group("all_workloads", mode="append")
        workload_group("intel_workloads", mode="append")
        workload_variable(
            "warmup_timesteps",
            default="10",
            description="Number of warmup timesteps",
        )
        workload_variable(
            "main_timesteps",
            default="3100",
            description="Number of main timesteps",
        )
        workload_variable(
            "timestep_multiplier",
            default="1",
            description="Multiplier for main timesteps",
        )
        workload_variable(
            "xx",
            default="20*$x",
            description="xx value",
        )
        workload_variable(
            "yy",
            default="20*$y",
            description="yy value",
        )
        workload_variable(
            "zz",
            default="20*$z",
            description="zz value",
        )

    workload(
        "intel.lc",
        executables=[
            "stage-input",
            "change-root",
            "configure-timestep-variables-main",
            "configure-timestep-variables-warmup",
            "configure-timestep-variables-multiplier",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["intel.lc"]):
        workload_group("all_workloads", mode="append")
        workload_group("intel_workloads", mode="append")
        workload_variable(
            "warmup_timesteps",
            default="10",
            description="Number of warmup timesteps",
        )
        workload_variable(
            "main_timesteps",
            default="8400",
            description="Number of main timesteps",
        )
        workload_variable(
            "timestep_multiplier",
            default="1",
            description="Multiplier for main timesteps",
        )

    workload(
        "intel.lj",
        executables=[
            "stage-input",
            "change-root",
            "configure-size-scale-xx",
            "configure-size-scale-yy",
            "configure-size-scale-zz",
            "configure-timestep-variables-main",
            "configure-timestep-variables-warmup",
            "configure-timestep-variables-multiplier",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["intel.lj"]):
        workload_group("all_workloads", mode="append")
        workload_group("intel_workloads", mode="append")
        workload_variable(
            "warmup_timesteps",
            default="10",
            description="Number of warmup timesteps",
        )
        workload_variable(
            "main_timesteps",
            default="7900",
            description="Number of main timesteps",
        )
        workload_variable(
            "timestep_multiplier",
            default="1",
            description="Multiplier for main timesteps",
        )
        workload_variable(
            "xx",
            default="20*$x",
            description="xx value",
        )
        workload_variable(
            "yy",
            default="20*$y",
            description="yy value",
        )
        workload_variable(
            "zz",
            default="20*$z",
            description="zz value",
        )

    workload(
        "intel.rhodo",
        executables=[
            "stage-input",
            "change-root",
            "configure-timestep-variables-main",
            "configure-timestep-variables-warmup",
            "configure-timestep-variables-multiplier",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["intel.rhodo"]):
        workload_group("all_workloads", mode="append")
        workload_group("intel_workloads", mode="append")
        workload_variable(
            "warmup_timesteps",
            default="10",
            description="Number of warmup timesteps",
        )
        workload_variable(
            "main_timesteps",
            default="520",
            description="Number of main timesteps",
        )
        workload_variable(
            "timestep_multiplier",
            default="1",
            description="Multiplier for main timesteps",
        )

    workload(
        "intel.sw",
        executables=[
            "stage-input",
            "change-root",
            "configure-size-scale-xx",
            "configure-size-scale-yy",
            "configure-size-scale-zz",
            "configure-timestep-variables-main",
            "configure-timestep-variables-warmup",
            "configure-timestep-variables-multiplier",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["intel.sw"]):
        workload_group("all_workloads", mode="append")
        workload_group("intel_workloads", mode="append")
        workload_variable(
            "warmup_timesteps",
            default="10",
            description="Number of warmup timesteps",
        )
        workload_variable(
            "main_timesteps",
            default="6200",
            description="Number of main timesteps",
        )
        workload_variable(
            "timestep_multiplier",
            default="1",
            description="Multiplier for main timesteps",
        )
        workload_variable(
            "xx",
            default="20*$x",
            description="xx value",
        )
        workload_variable(
            "yy",
            default="20*$y",
            description="yy value",
        )
        workload_variable(
            "zz",
            default="10*$z",
            description="zz value",
        )

    workload(
        "intel.tersoff",
        executables=[
            "stage-input",
            "change-root",
            "configure-size-scale-xx",
            "configure-size-scale-yy",
            "configure-size-scale-zz",
            "configure-timestep-variables-main",
            "configure-timestep-variables-warmup",
            "configure-timestep-variables-multiplier",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["intel.tersoff"]):
        workload_group("all_workloads", mode="append")
        workload_group("intel_workloads", mode="append")
        workload_variable(
            "warmup_timesteps",
            default="10",
            description="Number of warmup timesteps",
        )
        workload_variable(
            "main_timesteps",
            default="2420",
            description="Number of main timesteps",
        )
        workload_variable(
            "timestep_multiplier",
            default="1",
            description="Multiplier for main timesteps",
        )
        workload_variable(
            "xx",
            default="20*$x",
            description="xx value",
        )
        workload_variable(
            "yy",
            default="20*$y",
            description="yy value",
        )
        workload_variable(
            "zz",
            default="10*$z",
            description="zz value",
        )

    workload(
        "intel.water",
        executables=[
            "stage-input",
            "change-root",
            "configure-timestep-variables-main",
            "configure-timestep-variables-warmup",
            "configure-timestep-variables-multiplier",
            "execute",
        ],
        input="lammps-stage",
    )
    with default_args(workloads=["intel.water"]):
        workload_group("all_workloads", mode="append")
        workload_group("intel_workloads", mode="append")
        workload_variable(
            "warmup_timesteps",
            default="10",
            description="Number of warmup timesteps",
        )
        workload_variable(
            "main_timesteps",
            default="2600",
            description="Number of main timesteps",
        )
        workload_variable(
            "timestep_multiplier",
            default="1",
            description="Multiplier for main timesteps",
        )

    workload(
        "hns-reaxff",
        executables=[
            "stage-contents",
            "stage-input-file",
            "configure-reaxff-x",
            "configure-reaxff-y",
            "configure-reaxff-z",
            "configure-reaxff-timesteps",
            "execute",
        ],
        inputs=["lammps-stage"],
    )
    with default_args(workloads=["hns-reaxff"]):
        workload_group("all_workloads", mode="append")

        workload_variable(
            "input_path",
            default=os.path.join(
                "{examples_path}", "reaxff", "HNS", "in.{workload_name}"
            ),
            description="Path to input file for workload",
        )

        workload_variable(
            "input_file",
            default="in.reaxff.hns",
            description="hns-reaxff input file name",
        )

        workload_variable(
            "timesteps",
            default="100",
            description="Number of timesteps",
        )
        workload_variable(
            "x",
            default="2",
            description="x value",
        )
        workload_variable(
            "y",
            default="2",
            description="y value",
        )
        workload_variable(
            "z",
            default="2",
            description="z value",
        )

    success_criteria(
        "walltime",
        mode="string",
        match=r"\s*Total wall time",
        file="{log_file}",
    )

    figure_of_merit(
        "Total wall time",
        fom_regex=r"Total wall time.*\s+(?P<walltime>[0-9:]+)",
        group_name="walltime",
        units="",
        fom_type=FomType.TIME,
    )
    figure_of_merit(
        "Nanoseconds per day",
        fom_regex=r"Performance.*?\s+(?P<nspd>[0-9\.]+) (ns|tau)/day",
        group_name="nspd",
        units="ns/day",
        fom_type=FomType.THROUGHPUT,
    )
    figure_of_merit(
        "Hours per nanosecond",
        fom_regex=r"Performance.*?\s+(?P<hpns>[0-9\.]+) hours/ns",
        group_name="hpns",
        units="hours/ns",
        fom_type=FomType.TIME,
    )
    figure_of_merit(
        "Timesteps per second",
        fom_regex=r"Performance.*?\s+(?P<tsps>[0-9\.]+) timesteps/s",
        group_name="tsps",
        units="timesteps/s",
        fom_type=FomType.THROUGHPUT,
    )

    figure_of_merit(
        "Number of Atoms",
        fom_regex=r"Loop.*with (?P<atoms>[0-9]+) atoms",
        group_name="atoms",
        units="",
        fom_type=FomType.INFO,
    )

    for func_name in ["Pair", "Neigh", "Comm", "Output", "Modifier"]:
        func_time_regex = (
            func_name
            + r"\s+\|\s+(?P<min_time>\S+)\s+\|\s+(?P<avg_time>\S+)\s+\|\s+(?P<max_time>\S+)\s+\|\s+(?P<avg_var>\S+)\s+\|\s+(?P<total_pct>\S+)"
        )
        figure_of_merit(
            f"{func_name} min time",
            fom_regex=func_time_regex,
            group_name="min_time",
            units="s",
        )

        figure_of_merit(
            f"{func_name} avg time",
            fom_regex=func_time_regex,
            group_name="avg_time",
            units="s",
        )

        figure_of_merit(
            f"{func_name} max time",
            fom_regex=func_time_regex,
            group_name="max_time",
            units="s",
        )

        figure_of_merit(
            f"{func_name} avg. variance",
            fom_regex=func_time_regex,
            group_name="avg_var",
            units="",
        )

        figure_of_merit(
            f"{func_name} percent of runtime",
            fom_regex=func_time_regex,
            group_name="total_pct",
            units="%",
        )
