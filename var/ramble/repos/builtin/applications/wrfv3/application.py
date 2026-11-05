# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import deprecation

import ramble
from ramble.appkit import *
from ramble.expander import Expander


class Wrfv3(ExecutableApplication):
    """Define Wrf version 3 application.

    .. deprecated:: 0.7.0
       Use the ``wrf`` application (e.g., ``wrf@3.9.1.1``) instead.
    """

    name = "wrfv3"

    @deprecation.deprecated(
        deprecated_in="0.7.0",
        removed_in="0.8.0",
        current_version=str(ramble.ramble_version),
        details="The 'wrfv3' application is deprecated. Use the 'wrf' application (e.g., 'wrf@3.9.1.1') instead.",
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
                "The 'wrfv3' application is deprecated and will be removed in v0.8.0. "
                "Please use the 'wrf' application (e.g., 'wrf@3.9.1.1') instead."
            )
        super().set_variables_and_variants(
            variables, variants, workspace, experiment_set
        )

    maintainers("douglasjacobsen")

    tags("weather", "nwp", "climate-modeling")

    with when("package_manager_family=spack"):
        define_compiler("gcc8", pkg_spec="gcc@8.2.0")

        software_spec(
            "intel-mpi",
            pkg_spec="intel-oneapi-mpi@2021.17.2",
        )

        software_spec(
            "wrfv3",
            pkg_spec="wrf@3.9.1.1 build_type=dm+sm compile_type=em_real nesting=basic ~pnetcdf",
            compiler="gcc8",
        )

        required_package("wrf")

    input_file(
        "CONUS_2p5km",
        url="https://www2.mmm.ucar.edu/wrf/bench/conus2.5km_v3911/bench_2.5km.tar.bz2",
        sha256="1919a0e0499057c1a570619d069817022bae95b17cf1a52bdaa174f8e8d11508",
        description="2.5 km resolution mesh of the continental United States.",
    )

    input_file(
        "CONUS_12km",
        url="https://www2.mmm.ucar.edu/wrf/bench/conus12km_v3911/bench_12km.tar.bz2",
        sha256="0c5ecfc85f2a982f0fa0191371401c1474cf562a7cf97192acd3c9b91ebcc48d",
        description="12 km resolution mesh of the continental United States.",
    )

    stage_files(
        stages=[
            ("{wrf_path}/run/*", "{experiment_run_dir}/."),
            ("{input_path}/*", "{experiment_run_dir}/."),
        ]
    )

    stage_files(
        name="stage-namelist",
        method="cp",
        src="{input_path}/namelist.*",
        dst="{experiment_run_dir}/.",
    )

    executable(
        "setup",
        template=[
            "rm -f rsl.* wrfout* namelist*",
        ],
        use_mpi=False,
        output_capture=OUTPUT_CAPTURE.ALL,
    )

    executable("execute", "wrf.exe", use_mpi=True)

    workload(
        "CONUS_2p5km",
        executables=["stage-files", "stage-namelist", "setup", "execute"],
        input="CONUS_2p5km",
    )

    workload(
        "CONUS_12km",
        executables=["stage-files", "stage-namelist", "setup", "execute"],
        input="CONUS_12km",
    )

    workload_variable(
        "input_path",
        description="Path for workload inputs.",
        workload_defaults={
            "CONUS_12km": "{CONUS_12km}",
            "CONUS_2p5km": "{CONUS_2p5km}",
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
        file="{experiment_run_dir}/rsl.out.0000",
    )

    archive_pattern("{experiment_run_dir}/rsl.out.*")
    archive_pattern("{experiment_run_dir}/rsl.error.*")

    def _analyze_experiments(self, workspace, app_inst=None):
        import glob
        import re

        # Generate stats file

        file_list = glob.glob(
            os.path.join(
                self.expander.expand_var_name("experiment_run_dir"),
                "rsl.out.*",
            )
        )

        if file_list:
            timing_regex = re.compile(
                r"Timing for main.*:\s+(?P<main_time>[0-9]+\.[0-9]*).*"
            )
            avg_time = 0.0
            min_time = float("inf")
            max_time = float("-inf")
            sum_time = 0.0
            count = 0
            for out_file in file_list:
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
