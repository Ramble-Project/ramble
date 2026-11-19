# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


from ramble.appkit import *


class Cesm(ExecutableApplication):
    """Community Earth System Model Application"""

    name = "cesm"

    software_spec(
        "cesm",
        pkg_spec="cesm@2.1.5",
        when=["package_manager_family=spack"],
    )
    required_package("cesm", when=["package_manager_family=spack"])

    executable(
        "execute_case",
        template=[
            "export PATH={cesm_root}/.bin:$PATH",
            "rm -rf {case_dir} {experiment_run_dir}/scratch",
            "{cesm_root}/cime/scripts/create_clone --clone {cesm_root}/case_FC2000climo_f09 --case {case_dir}",
            "cd {case_dir}",
            "./xmlchange CIME_OUTPUT_ROOT={experiment_run_dir}/scratch",
            "python3 -c \"import re; p='env_mach_specific.xml'; c=open(p).read(); open(p,'w').write(re.sub(r'<executable>.*?</executable>', '<executable>{mpi_command}</executable>', c))\"",
            "./xmlchange NTASKS={n_ranks},NTHRDS={n_threads},ROOTPE=0",
            "./xmlchange MAX_TASKS_PER_NODE=192,MAX_MPITASKS_PER_NODE={processes_per_node}",
            "./xmlchange STOP_OPTION={stop_option},STOP_N={stop_n}",
            "./case.setup --reset",
            "./case.setup",
            'grep -q "use_gw_front" user_nl_cam || echo "use_gw_front = .false." >> user_nl_cam',
            "./check_input_data --download",
            "./xmlchange -file env_build.xml -id SMP_BUILD -val 0",
            "./case.build --skip-provenance-check",
            "python3 ./.case.run",
            "cat {case_dir}/timing/cesm_timing.* >> {experiment_run_dir}/{experiment_name}.out",
            "./case.st_archive",
            "cat $(ls -1t {experiment_run_dir}/scratch/archive/{experiment_name}/logs/cesm.log.* | head -n 1) >> {experiment_run_dir}/{experiment_name}.out",
            "find {experiment_run_dir}/scratch -name '*.nc' -type f -delete",
        ],
        use_mpi=False,
    )

    workload(
        "FC2000climo_f09",
        executables=["execute_case"],
    )
    workload_variable(
        "cesm_root",
        description="Path to installed CESM root directory",
        default="{cesm_path}",
        workload="FC2000climo_f09",
    )
    workload_variable(
        "case_dir",
        description="Path where CIME case directory will be generated",
        default="{experiment_run_dir}/case",
        workload="FC2000climo_f09",
    )
    workload_variable(
        "stop_option",
        description="Run length unit (nmonths, ndays, nyears)",
        default="nmonths",
        workload="FC2000climo_f09",
    )
    workload_variable(
        "stop_n",
        description="Run length count",
        default="1",
        workload="FC2000climo_f09",
    )
    workload_variable(
        "n_threads",
        description="Number of OpenMP threads per MPI task (NTHRDS)",
        default="1",
        workload="FC2000climo_f09",
    )
    workload_variable(
        "processes_per_node",
        description="Maximum MPI tasks per node for machine profile",
        default="192",
        workload="FC2000climo_f09",
    )
    workload_variable(
        "hydra_host_file",
        description="Path to Intel MPI Hydra hostfile (HYDRA_HOST_FILE)",
        default="{hostfile}",
        environment_variable_name="HYDRA_HOST_FILE",
        workload="FC2000climo_f09",
    )

    figure_of_merit(
        "SYPD",
        fom_regex=r"\s*Model Throughput:\s+(?P<sypd>[0-9\.]+)\s+simulated_years/day",
        group_name="sypd",
        units="SYPD",
    )
    figure_of_merit(
        "pe-hrs/SY",
        fom_regex=r"\s*Model Cost:\s+(?P<pe_hrs>[0-9\.]+)\s+pe-hrs/simulated_year",
        group_name="pe_hrs",
        units="pe-hrs/SY",
    )
    figure_of_merit(
        "run_time",
        fom_regex=r"\s*Run Time\s+:\s+(?P<run_time>[0-9\.]+)\s+seconds",
        group_name="run_time",
        units="s",
    )
    figure_of_merit(
        "init_time",
        fom_regex=r"\s*Init Time\s+:\s+(?P<init_time>[0-9\.]+)\s+seconds",
        group_name="init_time",
        units="s",
    )

    success_criteria(
        "no_numerical_errors",
        mode="string",
        anti_match=r"(?i)\b(nan|inf|cpl\s+abort|dycore\s+abort)\b",
    )
