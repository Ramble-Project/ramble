# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


from ramble.appkit import *


class NvidiaDcgm(ExecutableApplication):
    """NVIDIA Data Center GPU Manager (DCGM).

    DCGM is a suite of tools for managing and monitoring NVIDIA GPUs
    in cluster environments.
    https://docs.nvidia.com/datacenter/dcgm/latest/user-guide/dcgm-diagnostics.html


    # Example Ramble configuration for the DCGM application
    ramble:
      env_vars:
        set:
          OMP_NUM_THREADS: '{n_threads}'

      variants:
        package_manager: user-managed
        workflow_manager: user-managed

      variables:
        n_ranks: 1
        processes_per_node: 1
        mpi_command: '' # DCGM commands don't need MPI
        batch_submit: '{execute_experiment}' # Simple direct execution

      applications:
        nvidia-dcgm:
          workloads:
            diag:
              experiments:
                dcgm_r{diag_level}: # Parameterize dcgmi diag level
                  variables:
                    diag_level: [1,2,3]

      # No specific software packages needed if dcgmi is in the PATH
      software:
        packages: {}
        environments: {}
    """

    name = "nvidia-dcgm"
    maintainers("samskillman")
    tags("gpu-utility", "diagnostics", "nvidia-tool")

    executable(
        "diag",
        "dcgmi diag -r {diag_level}",
        use_mpi=False,
        output_capture=OUTPUT_CAPTURE.ALL,
    )

    workload(
        "diag",
        executable="diag",
    )

    workload_variable(
        "diag_level",
        default=1,
        workloads=["diag"],
        description="Level for dcgmi diagnostics",
        expandable=False,
    )

    # FOMs from 'diag' executable
    # Example Output:
    # Successfully ran diagnostic for group.
    # +---------------------------+------------------------------------------------+
    # | Diagnostic                | Result                                         |
    # +===========================+================================================+
    # |-----  Metadata  ----------+------------------------------------------------|
    # | DCGM Version              | 3.3.9                                          |
    # | Driver Version Detected   | 570.133.20                                     |
    # | GPU Device IDs Detected   | 2335,2335,2335,2335,2335,2335,2335,2335        |
    # |-----  Deployment  --------+------------------------------------------------|
    # | Denylist                  | Pass                                           |
    # | NVML Library              | Pass                                           |
    # | CUDA Main Library         | Pass                                           |
    # | Permissions and OS Blocks | Pass                                           |
    # | Persistence Mode          | Pass                                           |
    # | Environment Variables     | Pass                                           |
    # | Page Retirement/Row Remap | Pass                                           |
    # | Graphics Processes        | Pass                                           |
    # | Inforom                   | Pass                                           |
    # +-----  Integration  -------+------------------------------------------------+
    # | PCIe                      | Pass - All                                     |
    # +-----  Hardware  ----------+------------------------------------------------+
    # | GPU Memory                | Pass - All                                     |
    # | Diagnostic                | Pass - All                                     |
    # +-----  Stress  ------------+------------------------------------------------+
    # | Targeted Stress           | Pass - All                                     |
    # | Targeted Power            | Pass - All                                     |
    # | Memory Bandwidth          | Pass - All                                     |
    # | EUD Test                  | Skip - All                                     |
    # +---------------------------+------------------------------------------------+

    figure_of_merit(
        "diag: {diag_test}",
        executable="diag",
        fom_regex=r"^\|\s*(?P<diag_test>[\w\s\/]+?)\s*\|\s*(?P<result>Pass|Fail)\b.*",
        group_name="result",
        units="",
        fom_type=FomType.CATEGORY,
    )

    # Success Criteria
    success_criteria(
        "{fom_name}",
        mode="fom_comparison",
        fom_name="diag:*",
        formula="{value} == 'Pass'",
    )
