# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import re

import deprecation

import ramble
from ramble.appkit import *
from ramble.expander import Expander

from spack.util.executable import Executable, ProcessError


class Wrfv4(ExecutableApplication):
    """Define Wrf version 4 application.

    .. deprecated:: 0.7.0
       Use the ``wrf`` application (e.g., ``wrf@4.2``) instead.
    """

    name = "wrfv4"

    @deprecation.deprecated(
        deprecated_in="0.7.0",
        removed_in="0.8.0",
        current_version=str(ramble.ramble_version),
        details="The 'wrfv4' application is deprecated. Use the 'wrf' application (e.g., 'wrf@4.2') instead.",
    )
    def __init__(self, file_path):
        super().__init__(file_path)

    def set_variables_and_variants(
        self, variables, variants, workspace, experiment_set
    ):
        target = experiment_set or workspace or type(self)
        warned_attr = f"_{self.name}_deprecation_warned"
        if not getattr(target, warned_attr, False):
            setattr(target, warned_attr, True)
            logger.warn(
                "The 'wrfv4' application is deprecated and will be removed in v0.8.0. "
                "Please use the 'wrf' application (e.g., 'wrf@4.2') instead."
            )
        super().set_variables_and_variants(
            variables, variants, workspace, experiment_set
        )

    maintainers("douglasjacobsen")

    tags("weather", "nwp", "climate-modeling")

    with when("package_manager_family=spack"):
        define_compiler("gcc14", pkg_spec="gcc@14.2.0")

        software_spec(
            "intel-mpi",
            pkg_spec="intel-oneapi-mpi@2021.17.2",
        )

        software_spec(
            "wrfv4",
            pkg_spec="wrf@4.2 build_type=dm+sm compile_type=em_real nesting=basic ~chem ~pnetcdf",
            compiler="gcc14",
        )

        required_package("wrf")

    variant(
        "wrf_tiles",
        default=False,
        values=[True, False],
        description="Whether to define tiles for WRF or not",
    )

    variant(
        "wrf_explicit_x",
        default=False,
        values=[True, False],
        description="Whether to set explicit nproc_x in the namelist or not",
    )

    variant(
        "wrf_explicit_y",
        default=False,
        values=[True, False],
        description="Whether to set explicit nproc_y in the namelist or not",
    )

    variant(
        "wrf_clean_after_run",
        default=False,
        values=[True, False],
        description="Whether to clean execution artifacts after completion or not",
    )

    input_file(
        "CONUS_2p5km",
        url="https://www2.mmm.ucar.edu/wrf/users/benchmark/v422/v42_bench_conus2.5km.tar.gz",
        sha256="dcae9965d1873c1c1e34e21ad653179783302b9a13528ac10fab092b998578f6",
        description="2.5 km resolution mesh of the continental United States.",
    )

    input_file(
        "CONUS_12km",
        url="https://www2.mmm.ucar.edu/wrf/users/benchmark/v422/v42_bench_conus12km.tar.gz",
        sha256="6a0e87e3401efddc50539e71e5437fd7a5af9228b64cd4837e739737c3706fc3",
        description="12 km resolution mesh of the continental United States.",
    )

    input_file(
        "Maria_1km",
        url="https://www2.mmm.ucar.edu/wrf/users/benchmark/v44/v4.4_bench_maria1km.tar.gz",
        sha256="8a64d45fe53b13a810af8137fab3188c6aad6dc0948e4aa1a84c62bf3afaa102",
        description="1 km Maria workload input",
    )

    stage_files(
        stages=[
            ("{wrf_path}/run/*", "{experiment_run_dir}/."),
            ("{input_path}/*", "{experiment_run_dir}/."),
        ]
    )

    stage_files(
        name="stage-namelist",
        src="{input_path}/namelist.*",
        dst="{experiment_run_dir}/.",
        method="cp",
    )

    executable(
        "cleanup",
        template=[
            "rm -f rsl.* wrfout*",
        ],
        use_mpi=False,
        output_capture=OUTPUT_CAPTURE.ALL,
    )

    edit_file(
        "fix_12km_start_hour",
        file_path="namelist.input",
        match=r" start_hour.*",
        replace=" start_hour                          = 23,",
    )

    edit_file(
        "fix_12km_restart",
        file_path="namelist.input",
        match=r" restart .*",
        replace=" restart                             = .true.,",
    )

    edit_file(
        "define_nproc_x",
        file_path="namelist.input",
        match=r"(e_sn.*=.*)",
        replace=r"\g<1>\n nproc_x                            = {nproc_x},",
        when="+wrf_explicit_x",
    )

    edit_file(
        "define_nproc_y",
        file_path="namelist.input",
        match=r"(e_sn.*=.*)",
        replace=r"\g<1>\n nproc_y                            = {nproc_y},",
        when="+wrf_explicit_y",
    )

    executable("execute", "wrf.exe", use_mpi=True)

    executable(
        "copy-logs",
        template=[
            'RSL_LOG=`ls -1 {experiment_run_dir} | grep "rsl\\.out\\.[0]\\+" | sort -n | head -n 1`',
            "cp $RSL_LOG {experiment_run_dir}/rsl.out.base",
            'RSL_LOG=`ls -1 {experiment_run_dir} | grep "rsl\\.error\\.[0]\\+" | sort -n | head -n 1`',
            "cp $RSL_LOG {experiment_run_dir}/rsl.error.base",
            "tar czf rsl_logs.tgz rsl.out.* rsl.error.*",
            "rm -f rsl.out.* rsl.error.*",
            "tar xzf rsl_logs.tgz rsl.out.base rsl.error.base",
        ],
        redirect="",
        output_capture="",
    )

    executable(
        "post-exec-clean",
        template=[
            "rm -f {experiment_run_dir}/*.dat ",
            "rm -f {experiment_run_dir}/wrfout*",
            "rm -f {experiment_run_dir}/wrfrst*",
            "rm -f {experiment_run_dir}/wrfinput*",
        ],
        when=["+wrf_clean_after_run"],
    )

    workload(
        "CONUS_2p5km",
        executables=[
            "stage-files",
            "stage-namelist",
            "cleanup",
            "define_nproc_y",
            "define_nproc_x",
            "execute",
            "copy-logs",
            "post-exec-clean",
        ],
        input="CONUS_2p5km",
    )

    workload(
        "CONUS_12km",
        executables=[
            "stage-files",
            "stage-namelist",
            "cleanup",
            "define_nproc_y",
            "define_nproc_x",
            "fix_12km_start_hour",
            "fix_12km_restart",
            "execute",
            "copy-logs",
            "post-exec-clean",
        ],
        input="CONUS_12km",
    )

    workload(
        "Maria_1km",
        executables=[
            "stage-files",
            "stage-namelist",
            "cleanup",
            "define_nproc_y",
            "define_nproc_x",
            "execute",
            "copy-logs",
            "post-exec-clean",
        ],
        input="Maria_1km",
    )

    workload_group(
        "all_workloads", workloads=["CONUS_2p5km", "CONUS_12km", "Maria_1km"]
    )

    with when("+wrf_tiles"):
        workload_variable(
            "num_tiles",
            environment_variable_name="WRF_NUM_TILES",
            default="1",
            description="Number of tiles to use in WRF domain",
            workload_group="all_workloads",
        )

    workload_variable(
        "nproc_x",
        default="{n_ranks}",
        description="Number of process in the x dimension",
        workload_group="all_workloads",
        when=["+wrf_explicit_x"],
    )

    workload_variable(
        "nproc_y",
        default="{n_ranks}",
        description="Number of process in the y dimension",
        workload_group="all_workloads",
        when=["+wrf_explicit_y", "~wrf_explicit_x"],
    )

    workload_variable(
        "nproc_y",
        default="1",
        description="Number of process in the y dimension",
        workload_group="all_workloads",
        when=["+wrf_explicit_y", "+wrf_explicit_x"],
    )

    workload_variable(
        "input_path",
        description="Path for workload inputs.",
        workload_defaults={
            "CONUS_12km": "{CONUS_12km}",
            "CONUS_2p5km": "{CONUS_2p5km}",
            "Maria_1km": "{Maria_1km}",
        },
    )

    log_str = os.path.join(
        Expander.expansion_str("experiment_run_dir"), "stats.out"
    )

    figure_of_merit(
        "Average Timestep Time",
        log_file=log_str,
        fom_regex=r"Average time:\s+(?P<avg_time>[0-9]+\.[0-9]*)",
        group_name="avg_time",
        units="s",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "Cumulative Timestep Time",
        log_file=log_str,
        fom_regex=r"Cumulative time:\s+(?P<total_time>[0-9]+\.[0-9]*)",
        group_name="total_time",
        units="s",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "Minimum Timestep Time",
        log_file=log_str,
        fom_regex=r"Min time:\s+(?P<min_time>[0-9]+\.[0-9]*)",
        group_name="min_time",
        units="s",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "Maximum Timestep Time",
        log_file=log_str,
        fom_regex=r"Max time:\s+(?P<max_time>[0-9]+\.[0-9]*)",
        group_name="max_time",
        units="s",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "Number of timesteps",
        log_file=log_str,
        fom_regex=r"Number of times:\s+(?P<count>[0-9]+)",
        group_name="count",
        units="",
        fom_type=FomType.MEASURE,
    )

    figure_of_merit(
        "Avg. Max Ratio Time",
        log_file=log_str,
        fom_regex=r"Avg time / Max time:\s+(?P<avg_max_ratio>[0-9]+\.[0-9]*)",
        group_name="avg_max_ratio",
        units="",
        fom_type=FomType.MEASURE,
    )

    success_criteria(
        "Complete",
        mode="string",
        match=r".*?wrf: SUCCESS COMPLETE WRF",
        file="{experiment_run_dir}/rsl.out.base",
    )

    archive_pattern("{experiment_run_dir}/rsl_logs.tgz")
    archive_pattern("{experiment_run_dir}/rsl.out.base")
    archive_pattern("{experiment_run_dir}/rsl.error.base")

    def _analyze_experiments(self, workspace, app_inst=None):
        experiment_dir = self.expander.expand_var_name("experiment_run_dir")

        tar_file = os.path.join(experiment_dir, "rsl_logs.tgz")
        out_file = os.path.join(experiment_dir, "rsl.out.base")

        if os.path.isfile(tar_file) and not os.path.isfile(out_file):
            tar = Executable("tar")
            args = ["xzf", tar_file, "-C", experiment_dir, out_file]
            try:
                tar(*args)
            except ProcessError:
                pass

        if os.path.isfile(out_file):
            timing_regex = re.compile(
                r"Timing for main.*:\s+(?P<main_time>[0-9]+\.[0-9]*).*"
            )
            avg_time = 0.0
            min_time = float("inf")
            max_time = float("-inf")
            sum_time = 0.0
            count = 0
            with open(out_file, encoding="utf-8") as f:
                for line in f:
                    m = timing_regex.match(line)
                    if m:
                        time = float(m.group("main_time"))
                        count += 1
                        sum_time += time
                        min_time = min(min_time, time)
                        max_time = max(max_time, time)

            avg_time = sum_time / max(count, 1)

            stats_path = os.path.join(
                self.expander.expand_var_name("experiment_run_dir"),
                "stats.out",
            )
            with open(stats_path, "w+", encoding="utf-8") as f:
                f.write("Average time: %s s\n" % (avg_time))
                f.write("Cumulative time: %s s\n" % (sum_time))
                f.write("Min time: %s s\n" % (min_time))
                f.write("Max time: %s s\n" % (max_time))
                f.write(
                    "Avg time / Max time: %s s\n"
                    % (avg_time / max(max_time, float(1.0)))
                )
                f.write("Number of times: %s\n" % (count))

        super()._analyze_experiments(workspace)
