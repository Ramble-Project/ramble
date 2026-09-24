# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.appkit import *


class Graph500(ExecutableApplication):
    """The Graph500 benchmark is a data-intensive graph algorithms benchmark
    designed for high-performance computing, memory subsystem analysis, and
    large-scale graph traversal evaluation.

    It stresses memory bandwidth, latency, and irregular all-to-all communication
    patterns using Kronecker/R-MAT power-law graph generation and Breadth-First
    Search (BFS).

    https://graph500.org
    https://github.com/graph500/graph500
    """

    name = "graph500"

    maintainers("juntangc")

    tags(
        "graph",
        "benchmark",
        "mpi-benchmark",
        "micro-benchmark",
        "eda-proxy",
    )

    version("3.0.0", "Version 3.0.0 of Graph500", preferred=True)

    with when("package_manager_family=spack"):
        define_compiler("gcc14", pkg_spec="gcc@14.2.0")

        software_spec(
            "intel-mpi",
            pkg_spec="intel-oneapi-mpi@2021.17.2",
        )

        software_spec(
            "graph500",
            pkg_spec="graph500@{application::graph500::version} +procs_not_power_of_two",
            compiler="gcc14",
        )

        required_package("graph500")

    executable(
        "execute-bfs",
        "graph500_reference_bfs {scale} {edge_factor} {additional_args}",
        use_mpi=True,
    )

    executable(
        "execute-bfs-sssp",
        "graph500_reference_bfs_sssp {scale} {edge_factor} {additional_args}",
        use_mpi=True,
    )

    workload("bfs", executable="execute-bfs")
    workload("bfs_sssp", executable="execute-bfs-sssp")

    # Common pre-defined scale workloads (2^N vertices)
    scales = [16, 18, 20, 21, 22, 24, 26, 28, 30]
    for s in scales:
        workload(f"scale_{s}", executable="execute-bfs")

    workload_group(
        "all_workloads",
        workloads=["bfs", "bfs_sssp"] + [f"scale_{s}" for s in scales],
    )

    workload_variable(
        "scale",
        default="21",
        description="Scale of the graph (2^scale vertices; e.g. 21 = 2M vertices)",
        workloads=["bfs", "bfs_sssp"],
    )

    # Set default scale for each scale-specific workload
    for s in scales:
        workload_variable(
            "scale",
            default=str(s),
            description=f"Scale {s} graph (2^{s} vertices)",
            workloads=[f"scale_{s}"],
        )

    workload_variable(
        "edge_factor",
        default="16",
        description="Half the average degree of a vertex (default 16)",
        workload_group="all_workloads",
    )

    workload_variable(
        "additional_args",
        default="",
        description="Additional arguments for graph500 execution",
        workload_group="all_workloads",
    )

    # =========================================================================
    # Figures of Merit (FOMs)
    # =========================================================================
    fom_regex_float = r"[0-9]+(?:\.[0-9]+)?(?:[eE][\+\-]?[0-9]+)?"

    # Primary Benchmark Metric: Harmonic Mean TEPS
    figure_of_merit(
        "Harmonic Mean TEPS",
        fom_regex=r"bfs\s+harmonic_mean_TEPS:\s+(?P<fom>"
        + fom_regex_float
        + r")",
        group_name="fom",
        units="TEPS",
    )

    figure_of_merit(
        "Harmonic Stddev TEPS",
        fom_regex=r"bfs\s+harmonic_stddev_TEPS:\s+(?P<fom>"
        + fom_regex_float
        + r")",
        group_name="fom",
        units="TEPS",
    )

    figure_of_merit(
        "Min TEPS",
        fom_regex=r"bfs\s+min_TEPS:\s+(?P<fom>" + fom_regex_float + r")",
        group_name="fom",
        units="TEPS",
    )

    figure_of_merit(
        "First Quartile TEPS",
        fom_regex=r"bfs\s+firstquartile_TEPS:\s+(?P<fom>"
        + fom_regex_float
        + r")",
        group_name="fom",
        units="TEPS",
    )

    figure_of_merit(
        "Median TEPS",
        fom_regex=r"bfs\s+median_TEPS:\s+(?P<fom>" + fom_regex_float + r")",
        group_name="fom",
        units="TEPS",
    )

    figure_of_merit(
        "Third Quartile TEPS",
        fom_regex=r"bfs\s+thirdquartile_TEPS:\s+(?P<fom>"
        + fom_regex_float
        + r")",
        group_name="fom",
        units="TEPS",
    )

    figure_of_merit(
        "Max TEPS",
        fom_regex=r"bfs\s+max_TEPS:\s+(?P<fom>" + fom_regex_float + r")",
        group_name="fom",
        units="TEPS",
    )

    # Timing Figures of Merit
    figure_of_merit(
        "Graph Generation Time",
        fom_regex=r"graph_generation:\s+(?P<fom>" + fom_regex_float + r")",
        group_name="fom",
        units="s",
    )

    figure_of_merit(
        "Construction Time",
        fom_regex=r"construction_time:\s+(?P<fom>" + fom_regex_float + r")",
        group_name="fom",
        units="s",
    )

    figure_of_merit(
        "Min BFS Time",
        fom_regex=r"bfs\s+min_time:\s+(?P<fom>" + fom_regex_float + r")",
        group_name="fom",
        units="s",
    )

    figure_of_merit(
        "Median BFS Time",
        fom_regex=r"bfs\s+median_time:\s+(?P<fom>" + fom_regex_float + r")",
        group_name="fom",
        units="s",
    )

    figure_of_merit(
        "Mean BFS Time",
        fom_regex=r"bfs\s+mean_time:\s+(?P<fom>" + fom_regex_float + r")",
        group_name="fom",
        units="s",
    )

    figure_of_merit(
        "Max BFS Time",
        fom_regex=r"bfs\s+max_time:\s+(?P<fom>" + fom_regex_float + r")",
        group_name="fom",
        units="s",
    )

    figure_of_merit(
        "Mean Validate Time",
        fom_regex=r"bfs\s+mean_validate:\s+(?P<fom>" + fom_regex_float + r")",
        group_name="fom",
        units="s",
    )

    # Configuration Metadata FOMs
    figure_of_merit(
        "Graph Scale",
        fom_regex=r"SCALE:\s+(?P<scale>[0-9]+)",
        group_name="scale",
        units="",
    )

    figure_of_merit(
        "Edge Factor",
        fom_regex=r"edgefactor:\s+(?P<ef>[0-9]+)",
        group_name="ef",
        units="",
    )

    figure_of_merit(
        "MPI Processes",
        fom_regex=r"num_mpi_processes:\s+(?P<nprocs>[0-9]+)",
        group_name="nprocs",
        units="",
    )

    success_criteria(
        "passed",
        mode="string",
        match=r"bfs\s+harmonic_mean_TEPS:\s+" + fom_regex_float,
    )
