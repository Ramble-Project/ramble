# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import re

from ramble.appkit import *

from spack.util.executable import Executable, ProcessError


class Wrf(ExecutableApplication):
    """Define Wrf application"""

    name = "wrf"

    maintainers("douglasjacobsen")

    tags("weather", "nwp", "climate-modeling")

    version("4.2", description="Version 4.2 of WRF", preferred=True)
    version("3.9.1.1", description="Version 3.9.1.1 of WRF")

    with when("package_manager_family=spack"):
        define_compiler("gcc14", pkg_spec="gcc@14.2.0")

        software_spec(
            "intel-mpi",
            pkg_spec="intel-oneapi-mpi@2021.17.2",
        )

        with when("application_version@4.0:"):
            software_spec(
                "wrfv4-{application::wrf::version}",
                pkg_spec="wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real nesting=basic ~pnetcdf",
                compiler="gcc14",
            )

            required_package("wrf")

        with when("application_version@:3.9.1.1"):
            define_compiler("gcc8", pkg_spec="gcc@8.2.0")

            software_spec(
                "wrfv3-{application::wrf::version}",
                pkg_spec="wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real nesting=basic ~pnetcdf",
                compiler="gcc8",
            )

            required_package("wrf")

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

    with when("application_version@4.0:"):
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
            "all_workloads",
            workloads=["CONUS_2p5km", "CONUS_12km", "Maria_1km"],
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

        success_criteria(
            "Complete",
            mode="string",
            match=r".*?wrf: SUCCESS COMPLETE WRF",
            file="{experiment_run_dir}/rsl.out.base",
        )

    archive_pattern("{experiment_run_dir}/rsl_logs.tgz")
    archive_pattern("{experiment_run_dir}/rsl.out.base")
    archive_pattern("{experiment_run_dir}/rsl.error.base")

    with when("application_version@:3.9.1.1"):
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

        executable(
            "setup",
            template=[
                "rm -f rsl.* wrfout* namelist*",
            ],
            use_mpi=False,
            output_capture=OUTPUT_CAPTURE.ALL,
        )

        workload(
            "CONUS_2p5km",
            executables=[
                "stage-files",
                "stage-namelist",
                "setup",
                "execute",
                "copy-logs",
            ],
            input="CONUS_2p5km",
        )

        workload(
            "CONUS_12km",
            executables=[
                "stage-files",
                "stage-namelist",
                "setup",
                "execute",
                "copy-logs",
            ],
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

        success_criteria(
            "Complete",
            mode="string",
            match=r".*?wrf: SUCCESS COMPLETE WRF",
            file="{experiment_run_dir}/rsl.out.0000",
        )

    archive_pattern("{experiment_run_dir}/rsl.out.*")
    archive_pattern("{experiment_run_dir}/rsl.error.*")

    figure_of_merit(
        "Average Timestep Time",
        formula="{Cumulative Timestep Time} / {Number of timesteps}",
        units="s",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "Cumulative Timestep Time",
        fom_map_key="sum_time",
        units="s",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "Minimum Timestep Time",
        fom_map_key="min_time",
        units="s",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "Maximum Timestep Time",
        fom_map_key="max_time",
        units="s",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "Number of timesteps",
        fom_map_key="count",
        units="",
        fom_type=FomType.MEASURE,
    )

    figure_of_merit(
        "Avg. Max Ratio Time",
        formula="{Average Timestep Time} / {Maximum Timestep Time}",
        units="",
        fom_type=FomType.MEASURE,
    )

    def _prepare_analysis(self, workspace, app_inst=None):
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

            self.add_inmem_fom_value("sum_time", sum_time)
            self.add_inmem_fom_value("count", count)
            if count > 0:
                self.add_inmem_fom_value("min_time", min_time)
                self.add_inmem_fom_value("max_time", max_time)
