# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


from ramble.appkit import *
from ramble.expander import Expander


class Hpcg(ExecutableApplication):
    """The High Performance Conjugate Gradients (HPCG) Benchmark project is an
    effort to create a new metric for ranking HPC systems. HPCG is intended as
    a complement to the High Performance LINPACK (HPL) benchmark, currently
    used to rank the TOP500 computing systems. The computational and data
    access patterns of HPL are still representative of some important scalable
    applications, but not all. HPCG is designed to exercise computational and
    data access patterns that more closely match a different and broad set of
    important applications, and to give incentive to computer system designers
    to invest in capabilities that will have impact on the collective
    performance of these applications."""

    name = "hpcg"

    maintainers("douglasjacobsen")

    tags("hpc-benchmark", "conjugate-gradient")

    executable("execute", "xhpcg", use_mpi=True)

    executable("move-log", "mv HPCG-Benchmark*.txt {out_file}", use_mpi=False)

    workload_group("all_workloads")

    workload_group("calculator")

    workload_variable(
        "matrix_size",
        default="104 104 104",
        description="Dimensions of the matrix to use",
        workload_group="all_workloads",
    )

    workload_variable(
        "memory_per_rank",
        default="4.0",
        description="Target total physical memory (RSS) per MPI rank (in GB), including MPI and runtime overhead",
        workload_group="calculator",
    )

    workload_variable(
        "bytes_per_grid_point",
        default="768",
        description="Estimated bytes per grid point for memory calculation",
        workload_group="calculator",
    )

    workload_variable(
        "static_memory_overhead",
        default="0.6",
        description="Estimated static memory overhead per MPI rank (in GB), subtracted from memory_per_rank to size grids",
        workload_group="calculator",
    )

    workload_variable(
        "size_multiple",
        default="8",
        description="Dimension size must be a multiple of this value",
        workload_group="calculator",
    )

    workload_variable(
        "iterations",
        default="60",
        description="Number of iterations to perform",
        workload_group="all_workloads",
    )

    workload_variable(
        "out_file",
        default="{experiment_run_dir}/hpcg_result.out",
        description="Output file for results",
        workload_group="all_workloads",
    )

    out_file = Expander.expansion_str("out_file")

    figure_of_merit(
        "Status",
        log_file=out_file,
        fom_regex=r"Final Summary::HPCG result is (?P<status>[a-zA-Z]+) with a GFLOP/s rating of=(?P<gflops>[0-9\.]+)",
        group_name="status",
        units="",
    )

    figure_of_merit(
        "GFlops",
        log_file=out_file,
        fom_regex=r"Final Summary::HPCG result is (?P<status>[a-zA-Z]+) with a GFLOP/s rating of=(?P<gflops>[0-9\.]+)",
        group_name="gflops",
        units="GFLOP/s",
        fom_type=FomType.THROUGHPUT,
    )

    figure_of_merit(
        "Time",
        log_file=out_file,
        fom_regex=r"Final Summary::Results are.*? execution time.*?is=(?P<exec_time>[0-9\.]*)",
        group_name="exec_time",
        units="s",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "ComputeDotProductMsg",
        log_file=out_file,
        fom_regex=r"Final Summary::Reference version of ComputeDotProduct used.*?=(?P<msg>.*)",
        group_name="msg",
        units="",
    )

    figure_of_merit(
        "ComputeSPMVMsg",
        log_file=out_file,
        fom_regex=r"Final Summary::Reference version of ComputeSPMV used.*?=(?P<msg>.*)",
        group_name="msg",
        units="",
    )

    figure_of_merit(
        "ComputeMGMsg",
        log_file=out_file,
        fom_regex=r"Final Summary::Reference version of ComputeMG used.*?=(?P<msg>.*)",
        group_name="msg",
        units="",
    )

    figure_of_merit(
        "ComputeWAXPBYMsg",
        log_file=out_file,
        fom_regex=r"Final Summary::Reference version of ComputeWAXPBY used.*?=(?P<msg>.*)",
        group_name="msg",
        units="",
    )

    figure_of_merit(
        "HPCG 2.4 Rating",
        log_file=out_file,
        fom_regex=r"Final Summary::HPCG 2\.4 rating.*?=(?P<rating>[0-9\.]+)",
        group_name="rating",
        units="",
        fom_type=FomType.THROUGHPUT,
    )

    figure_of_merit(
        "Memory Used for Data",
        log_file=out_file,
        fom_regex=r"Memory Use Information::Total memory used for data \(Gbytes\)=(?P<memory_gb>[0-9\.]+)",
        group_name="memory_gb",
        units="Gbytes",
    )

    register_template(
        name="hpcg_dat",
        src_path="hpcg.dat.tpl",
        dest_path="hpcg.dat",
        define_var=False,
    )

    register_phase(
        "calculate_values", pipeline="setup", run_before=["make_experiments"]
    )

    register_phase(
        "calculate_values", pipeline="analyze", run_before=["analyze_experiments"]
    )

    def _calculate_values(self, workspace, app_inst):
        expander = self.expander
        if "calculator" in expander.workload_name:
            try:
                memory_per_rank = float(
                    expander.expand_var_name("memory_per_rank")
                )
                bytes_per_grid_point = float(
                    expander.expand_var_name("bytes_per_grid_point")
                )
                size_multiple = int(expander.expand_var_name("size_multiple"))
                static_memory_overhead = float(
                    expander.expand_var_name("static_memory_overhead")
                )
            except ValueError as e:
                logger.die(
                    f"Failed to parse calculator workload variables: {e}"
                )

            if memory_per_rank < 0:
                logger.die("memory_per_rank must be non-negative")
            if static_memory_overhead < 0:
                logger.die("static_memory_overhead must be non-negative")
            if bytes_per_grid_point <= 0:
                logger.die("bytes_per_grid_point must be positive")
            if size_multiple <= 0:
                logger.die("size_multiple must be positive")

            # Available memory for matrix allocation (subtracting fixed overhead)
            available_memory = memory_per_rank - static_memory_overhead
            if available_memory < 0.1:
                available_memory = 0.1

            # Calculate local grid size per rank
            memory_bytes = available_memory * (1024**3)
            num_grid_points = memory_bytes / bytes_per_grid_point

            # Each dimension is the cube root of num_grid_points
            dim_size = num_grid_points ** (1.0 / 3.0)

            # Round to the nearest multiple of size_multiple
            ndim = int(round(dim_size / size_multiple)) * size_multiple

            # Ensure it is at least size_multiple
            if ndim < size_multiple:
                ndim = size_multiple

            matrix_size_str = f"{ndim} {ndim} {ndim}"
            self.define_variable("matrix_size", matrix_size_str)
