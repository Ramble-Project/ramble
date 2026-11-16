# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

from ramble.appkit import *
from ramble.expander import Expander

# General Guidance:
# - Use compact placement policy
# - Check the compute nodes in a single rack using the network topology API


class IntelMpiBenchmarks(ExecutableApplication):
    """Intel MPI Benchmark application.

    https://www.intel.com/content/www/us/en/developer/articles/technical/intel-mpi-benchmarks.html
    https://github.com/intel/mpi-benchmarks
    https://www.intel.com/content/www/us/en/develop/documentation/imb-user-guide/top.html
    """

    name = "intel-mpi-benchmarks"

    maintainers("rfbgo")

    tags("mpi-benchmark", "micro-benchmark", "communication-benchmark")

    version("2019.6", "Version 2019.6 of Intel MPI Benchmarks", preferred=True)

    with when("package_manager_family=spack"):
        define_compiler("gcc14", pkg_spec="gcc@14.2.0")

        software_spec(
            "intel-mpi",
            pkg_spec="intel-oneapi-mpi@2021.17.2",
        )

        software_spec(
            "intel-mpi-benchmarks-{application::intel-mpi-benchmarks::version}",
            pkg_spec="intel-mpi-benchmarks@{application::intel-mpi-benchmarks::version}",
            compiler="gcc14",
        )

        required_package("intel-mpi-benchmarks")

    executable(
        "pingpong",
        "{install_path}/IMB-MPI1 {pingpong_type} -msglog {msglog_min}:{msglog_max} "
        "-iter {num_iterations} {additional_args}",
        use_mpi=True,
    )

    executable(
        "multi-pingpong",
        "{install_path}/IMB-MPI1 Pingpong -msglog {msglog_min}:{msglog_max} "
        "-iter {num_iterations} -multi {multi_val} -map {map_args} {additional_args}",
        use_mpi=True,
    )

    executable(
        "transfer",
        "{install_path}/IMB-MPI1 {transfer_type} -msglog {msglog_min}:{msglog_max} "
        "-iter {num_iterations} {additional_args}",
        use_mpi=True,
    )

    workload("pingpong", executable="pingpong")
    workload("multi-pingpong", executable="multi-pingpong")
    workload("collective", executable="collective")
    # TODO: should merge pingpong into this workload. For now keeping
    # the pingpong workload to avoid invalidating existing benchmark
    # configs.
    workload("transfer", executable="transfer")

    workload_group(
        "mpi1",
        workloads=["pingpong", "multi-pingpong", "collective", "transfer"],
    )

    workload_variable(
        "num_cores",
        default="{{{n_ranks}/2}:0.0f}",
        description="Number of cores",
        workloads=["multi-pingpong"],
    )

    workload_variable(
        "multi_val",
        default="0",
        description="Value to pass to the multi arg",
        workloads=["multi-pingpong"],
    )

    workload_variable(
        "map_args",
        default="{num_cores}x2",
        description="Args to map by",
        workloads=["multi-pingpong"],
    )

    executable(
        "collective",
        "{install_path}/IMB-MPI1 {collective_type} -msglog {msglog_min}:{msglog_max} "
        "-iter {num_iterations} -npmin {min_collective_ranks} {additional_args}",
        use_mpi=True,
    )

    # Multiple spack packages (specifically intel-oneapi-mpi) provide the
    # binary we need. It's fairly common to want to decouple the version of MPI
    # from the version of the benchmark, so this variable gives a user an
    # explicit way to control that, as well as more strongly implies the binary
    # from intel-mpi-benchmarks by default
    workload_variable(
        "install_path",
        default="{intel-mpi-benchmarks_path}/bin",
        description="User configurable dir to executables",
        workloads=["*"],
    )

    workload_variable(
        "pingpong_type",
        default="Pingpong",
        values=[
            "Pingpong",
            "Unirandom",
            "Multi-Pingpong",
            "Birandom",
            "Corandom",
        ],
        description="Pingpong Algorithm to Use",
        workloads=["pingpong"],
    )

    workload_variable(
        "transfer_type",
        default="Exchange",
        values=[
            "Exchange",
            "Sendrecv",
            "Uniband",
            "Biband",
        ],
        description="(Non-collective) Transfer pattern to benchmark",
        workloads=["transfer"],
    )

    workload_variable(
        "collective_type",
        # FIXME: should default just be denoted by the
        # first value in the values list?
        default="Allgather",
        values=[
            "Allgather",
            "Allgatherv",
            "Alltoall",
            "Alltoallv",
            "Bcast",
            "Scatter",
            "Scatterv",
            "Gather",
            "Gatherv",
            "Reduce",
            "Reduce_scatter",
            "Allreduce",
            "Barrier",
        ],
        description="Collective type to test",
        workloads=["collective"],
    )

    workload_variable(
        "min_collective_ranks",
        default="{n_ranks}",
        description="Minimum number of ranks to use in a collective operation",
        workloads=["collective"],
    )

    workload_variable(
        "num_iterations",
        default="1000",
        description="Number of iterations to test over",
        workload_group="mpi1",
    )

    workload_variable(
        "msglog_min",
        default="1",
        description="Min Message Size (power of 2)",
        workload_group="mpi1",
    )

    workload_variable(
        "msglog_max",
        default="30",
        description="Max Message Size (power of 2)",
        workload_group="mpi1",
    )

    workload_variable(
        "additional_args",
        default="",
        description="Additional cmd-line arguments",
        workload_group="mpi1",
    )

    # Matches tables like:
    #  bytes #repetitions  t_min[usec]  t_max[usec]  t_avg[usec]
    latency_regex = (
        r"^\s+(?P<bytes>\d+)\s+(?P<repetitions>\d+)\s+"
        + r"(?P<t_min>\d+\.\d+)\s+(?P<t_max>\d+\.\d+)\s+(?P<t_avg>\d+\.\d+)$"
    )

    log_str = os.path.join(
        Expander.expansion_str("experiment_run_dir"),
        Expander.expansion_str("experiment_name") + ".out",
    )

    figure_of_merit(
        "Latency min",
        log_file=log_str,
        fom_regex=latency_regex,
        group_name="t_min",
        units="usec",
        contexts=["latency-bytes"],
    )

    figure_of_merit(
        "Latency avg",
        log_file=log_str,
        fom_regex=latency_regex,
        group_name="t_avg",
        units="usec",
        contexts=["latency-bytes"],
    )

    figure_of_merit(
        "Latency max",
        log_file=log_str,
        fom_regex=latency_regex,
        group_name="t_max",
        units="usec",
        contexts=["latency-bytes"],
    )

    # Matches tables like:
    #  bytes #repetitions      t[usec]   Mbytes/sec
    bw_regex = r"^\s+(?P<bytes>\d+)\s+(?P<repetitions>\d+)\s+(?P<t_avg>\d+\.\d+)\s+(?P<bw>\d+\.\d+)$"
    figure_of_merit(
        "Bandwidth",
        log_file=log_str,
        fom_regex=bw_regex,
        group_name="bw",
        units="Mbytes/sec",
        contexts=["bw-bytes"],
    )

    figure_of_merit(
        "Time avg",
        log_file=log_str,
        fom_regex=bw_regex,
        group_name="t_avg",
        units="usec",
        contexts=["bw-bytes"],
    )

    # Combiend tables like:
    #  bytes #repetitions  t_min[usec]  t_max[usec]  t_avg[usec]   Mbytes/sec
    #   (happens in sendrecv and exchange)
    combined_regex = (
        r"^\s+(?P<bytes>\d+)\s+(?P<repetitions>\d+)\s+"
        + r"(?P<t_min>\d+\.\d+)\s+(?P<t_max>\d+\.\d+)\s+"
        + r"(?P<t_avg>\d+\.\d+)\s+(?P<bw>\d+\.\d+)$"
    )
    figure_of_merit(
        "Combo",
        log_file=log_str,
        fom_regex=combined_regex,
        group_name="bw",
        units="Mbytes/sec",
        contexts=["combo-bytes"],
    )

    figure_of_merit_context(
        "latency-bytes",
        regex=latency_regex,
        output_format="Bytes: {bytes} (Latency)",
    )

    figure_of_merit_context(
        "bw-bytes", regex=bw_regex, output_format="Bytes: {bytes} (BW)"
    )

    figure_of_merit_context(
        "combo-bytes",
        regex=combined_regex,
        output_format="Bytes: {bytes} (Combo)",
    )

    success_criteria(
        "run_to_completion",
        mode="string",
        match=r".*?All processes entering MPI_Finalize",
    )
