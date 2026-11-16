# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import re
from enum import Enum

from ramble.appkit import *
from ramble.expander import Expander


class OsuMicroBenchmarks(ExecutableApplication):
    """Define an OSU micro benchmarks application"""

    name = "osu-micro-benchmarks"

    maintainers("rfbgo", "douglasjacobsen")

    tags(
        "mpi-benchmark",
        "micro-benchmark",
        "network-benchmark",
        "communication-benchmark",
    )

    with when("package_manager_family=spack"):
        define_compiler("gcc", pkg_spec="gcc")
        software_spec("openmpi", pkg_spec="openmpi")
        software_spec(
            "osu-micro-benchmarks",
            pkg_spec="osu-micro-benchmarks",
            compiler="gcc",
        )

        required_package("osu-micro-benchmarks")

    all_workloads = [
        "osu_bibw",
        "osu_bw",
        "osu_latency",
        "osu_latency_mp",
        "osu_latency_mt",
        "osu_mbw_mr",
        "osu_multi_lat",
        "osu_allgather",
        "osu_allreduce_persistent",
        "osu_alltoallw",
        "osu_bcast_persistent",
        "osu_iallgather",
        "osu_ialltoallw",
        "osu_ineighbor_allgather",
        "osu_ireduce",
        "osu_neighbor_allgatherv",
        "osu_reduce_persistent",
        "osu_scatterv",
        "osu_allgather_persistent",
        "osu_alltoall",
        "osu_alltoallw_persistent",
        "osu_gather",
        "osu_iallgatherv",
        "osu_ibarrier",
        "osu_ineighbor_allgatherv",
        "osu_ireduce_scatter",
        "osu_neighbor_alltoall",
        "osu_reduce_scatter",
        "osu_scatterv_persistent",
        "osu_allgatherv",
        "osu_alltoall_persistent",
        "osu_barrier",
        "osu_gather_persistent",
        "osu_iallreduce",
        "osu_ibcast",
        "osu_ineighbor_alltoall",
        "osu_iscatter",
        "osu_neighbor_alltoallv",
        "osu_reduce_scatter_persistent",
        "osu_allgatherv_persistent",
        "osu_alltoallv",
        "osu_barrier_persistent",
        "osu_gatherv",
        "osu_ialltoall",
        "osu_igather",
        "osu_ineighbor_alltoallv",
        "osu_iscatterv",
        "osu_neighbor_alltoallw",
        "osu_scatter",
        "osu_allreduce",
        "osu_alltoallv_persistent",
        "osu_bcast",
        "osu_gatherv_persistent",
        "osu_ialltoallv",
        "osu_igatherv",
        "osu_ineighbor_alltoallw",
        "osu_neighbor_allgather",
        "osu_reduce",
        "osu_scatter_persistent",
        "osu_acc_latency",
        "osu_cas_latency",
        "osu_fop_latency",
        "osu_get_acc_latency",
        "osu_get_bw",
        "osu_get_latency",
        "osu_put_bibw",
        "osu_put_bw",
        "osu_put_latency",
        "osu_hello",
        "osu_init",
    ]

    size_time_regex = r"(?P<msg_size>[0-9.]+)+\s+(?P<fom>[0-9.]+)"
    figure_of_merit_context(
        "msg_size",
        regex=size_time_regex,
        output_format="Message Size: {msg_size}",
    )

    log_str = Expander.expansion_str("log_file")
    for benchmark in all_workloads:
        executable(
            name=f"execute-{benchmark}",
            template=f"{benchmark} " + "{additional_args}",
            use_mpi=True,
        )
        workload(benchmark, executable=f"execute-{benchmark}")

    workload_variable(
        "additional_args",
        # By default capture tail stats
        default="-z",
        description="Additional arguments for benchmark",
        workloads=all_workloads,
    )

    two_rank_workloads = [
        "osu_bibw",
        "osu_bw",
        "osu_latency",
        "osu_acc_latency",
        "osu_cas_latency",
        "osu_fop_latency",
        "osu_get_acc_latency",
        "osu_get_bw",
        "osu_get_latency",
        "osu_put_bibw",
        "osu_put_bw",
        "osu_put_latency",
    ]

    for two_rank_workload in two_rank_workloads:
        with when(f"workload_name={two_rank_workload}"):
            register_validator(
                name="two-rank-workloads",
                predicate="{n_ranks} == 2",
                message="This workload requires 2 ranks.",
                fail_on_invalid=True,
            )

    data_type_regex = r"# Datatype: (?P<type>\S+)\."
    figure_of_merit(
        "OMB Datatype", fom_regex=data_type_regex, group_name="type", units=""
    )

    hello_regex = r"This is a test with (?P<nprocs>[0-9]+) processes"
    figure_of_merit(
        "osu_hello_nprocs",
        fom_regex=hello_regex,
        group_name="nprocs",
        units="",
    )

    init_regex = r"nprocs: (?P<nprocs>[0-9]+), min: (?P<min>[0-9\.]+) ms, max: (?P<max>[0-9\.]+) ms, avg: (?P<avg>[0-9\.]+) ms"
    figure_of_merit(
        "osu_init_nprocs", fom_regex=init_regex, group_name="nprocs", units=""
    )
    figure_of_merit(
        "osu_init_min", fom_regex=init_regex, group_name="min", units="ms"
    )
    figure_of_merit(
        "osu_init_max", fom_regex=init_regex, group_name="max", units="ms"
    )
    figure_of_merit(
        "osu_init_avg", fom_regex=init_regex, group_name="avg", units="ms"
    )

    fom_types = Enum(
        "fom_types",
        [
            "single_lat",
            "single_tail_lat",
            "avg_lat",
            "avg_tail_lat",
            "multi_lat",
            "multi_tail_lat",
            "single_bw",
            "single_tail_bw",
            "multi_bw",
            "multi_tail_bw",
            "single_avg_lat",
            "single_avg_tail_lat",
        ],
    )

    fom_regex_headers = {
        fom_types.single_lat: re.compile(r"#\s+Size\s+Latency \(us\)\s*$"),
        fom_types.single_tail_lat: re.compile(
            r"# Size\s+Latency \(us\)\s+P50 Tail Lat\(us\)\s+P90 Tail Lat\(us\)\s+P99 Tail Lat\(us\)$"
        ),
        fom_types.avg_lat: re.compile(r"#\s+Size\s+Avg Latency\(us\)\s*$"),
        fom_types.avg_tail_lat: re.compile(
            r"# Size\s+Avg Latency\(us\)\s+P50 Tail Lat\(us\)\s+P90 Tail Lat\(us\)\s+P99 Tail Lat\(us\)$"
        ),
        fom_types.multi_lat: re.compile(
            r"#\s+Size\s+Overall\(us\)\s+Compute\(us\)\s+Pure Comm\.\(us\)\s+Overlap\(%\)\s*$"
        ),
        fom_types.multi_tail_lat: re.compile(
            r"# Size\s+Overall\(us\)\s+Compute\(us\)\s+Pure Comm\.\(us\)\s+Overlap\(%\)  P50 Tail Lat\(us\)  P90 Tail Lat\(us\)  P99 Tail Lat\(us\)\s*$"
        ),
        fom_types.single_bw: re.compile(r"# Size\s+Bandwidth \(MB/s\)\s*$"),
        fom_types.single_tail_bw: re.compile(
            r"# Size\s+Bandwidth \(MB/s\) P50 Tail BW\(MB/s\) P90 Tail BW\(MB/s\) P99 Tail BW\(MB/s\)\s*$"
        ),
        fom_types.multi_bw: re.compile(r"# Size\s+MB/s\s+Messages/s\s*$"),
        fom_types.multi_tail_bw: re.compile(
            r"# Size\s+MB/s\s+Messages/s P50 Tail BW\(MB/s\) P90 Tail BW\(MB/s\) P99 Tail BW\(MB/s\)\s*$"
        ),
        fom_types.single_avg_lat: re.compile(r"# Avg Latency\(us\)\s*$"),
        fom_types.single_avg_tail_lat: re.compile(
            r"# Avg Latency\(us\)\s+P50 Tail Lat\(us\)\s+P90 Tail Lat\(us\)\s+P99 Tail Lat\(us\)\s*$"
        ),
    }

    group_mapping = {
        "avg_lat": {"name": "Latency", "units": "us"},
        "p50_lat": {"name": "P50 Tail Latency", "units": "us"},
        "p90_lat": {"name": "P90 Tail Latency", "units": "us"},
        "p99_lat": {"name": "P99 Tail Latency", "units": "us"},
        "avg_bw": {"name": "Bandwidth", "units": "MB/s"},
        "p50_bw": {"name": "P50 Tail Bandwidth", "units": "MB/s"},
        "p90_bw": {"name": "P90 Tail Bandwidth", "units": "MB/s"},
        "p99_bw": {"name": "P99 Tail Bandwidth", "units": "MB/s"},
        "overall_lat": {"name": "Overall", "units": "us"},
        "comp_lat": {"name": "Computation", "units": "us"},
        "comm_lat": {"name": "Communication", "units": "us"},
        "overlap": {"name": "Overlap", "units": "%"},
        "msg_rate": {"name": "Message Rate", "units": "Messages/s"},
    }

    def _add_foms(self, regex: str):
        """Add figures of merit based on group names from input regular expression

        Args:
            regex (str): An uncompiled regular expression to use for determining which groups
                         are going to be extracted.
        """
        if regex is None:
            return

        compiled = re.compile(regex)

        for grp_name in compiled.groupindex:
            if grp_name in self.group_mapping:
                self.figure_of_merit(
                    self.group_mapping[grp_name]["name"],
                    fom_regex=regex,
                    group_name=grp_name,
                    units=self.group_mapping[grp_name]["units"],
                    contexts=["msg_size"],
                )

    def _prepare_analysis(self, workspace, app_inst=None):
        test_ver_regex = r"# OSU.*Test (?P<ver>v[0-9\.]+)"
        self.figure_of_merit(
            "OMB Version", fom_regex=test_ver_regex, group_name="ver", units=""
        )

        fom_type = None
        log_file = self.expander.expand_var_name("log_file")
        if os.path.isfile(log_file):
            with open(log_file, encoding="utf-8") as f:
                for line in f:
                    for test_fom_type in self.fom_types:
                        if self.fom_regex_headers[test_fom_type].match(line):
                            fom_type = test_fom_type

                    if fom_type is not None:
                        break

        fom_regex = None
        if fom_type == self.fom_types.single_lat:
            fom_regex = r"\s*(?P<msg_size>[0-9]+)\s+(?P<avg_lat>[0-9\.]+)\s*$"
        elif fom_type == self.fom_types.single_tail_lat:
            fom_regex = r"\s*(?P<msg_size>[0-9]+)\s+(?P<avg_lat>[0-9\.]+)\s+(?P<p50_lat>[0-9\.]+)\s+(?P<p90_lat>[0-9\.]+)\s+(?P<p99_lat>[0-9\.]+)\s*$"
        elif fom_type == self.fom_types.avg_lat:
            fom_regex = r"\s*(?P<msg_size>[0-9]+)\s+(?P<avg_lat>[0-9\.]+)\s*$"
        elif fom_type == self.fom_types.avg_tail_lat:
            fom_regex = r"\s*(?P<msg_size>[0-9]+)\s+(?P<avg_lat>[0-9\.]+)\s+(?P<p50_lat>[0-9\.]+)\s+(?P<p90_lat>[0-9\.]+)\s+(?P<p99_lat>[0-9\.]+)\s*$"
        elif fom_type == self.fom_types.multi_lat:
            fom_regex = r"\s*(?P<msg_size>[0-9]+)\s+(?P<overall_lat>[0-9\.]+)\s+(?P<comp_lat>[0-9\.]+)\s+(?P<comm_lat>[0-9\.]+)\s+(?P<overlap>[0-9\.]+)\s*$"
        elif fom_type == self.fom_types.multi_tail_lat:
            fom_regex = r"\s*(?P<msg_size>[0-9]+)\s+(?P<overall_lat>[0-9\.]+)\s+(?P<comp_lat>[0-9\.]+)\s+(?P<comm_lat>[0-9\.]+)\s+(?P<overlap>[0-9\.]+)\s+(?P<p50_lat>[0-9\.]+)\s+(?P<p90_lat>[0-9\.]+)\s+(?P<p99_lat>[0-9\.]+)\s*$"
        elif fom_type == self.fom_types.single_bw:
            fom_regex = r"\s*(?P<msg_size>[0-9]+)\s+(?P<avg_bw>[0-9\.]+)\s*$"
        elif fom_type == self.fom_types.single_tail_bw:
            fom_regex = r"\s*(?P<msg_size>[0-9]+)\s+(?P<avg_bw>[0-9\.]+)\s+(?P<p50_bw>[0-9\.]+)\s+(?P<p90_bw>[0-9\.]+)\s+(?P<p99_bw>[0-9\.]+)\s*$"
        elif fom_type == self.fom_types.multi_bw:
            fom_regex = r"\s*(?P<msg_size>[0-9]+)\s+(?P<avg_bw>[0-9\.]+)\s+(?P<msg_rate>[0-9\.]+)\s*$"
        elif fom_type == self.fom_types.multi_tail_bw:
            fom_regex = r"\s*(?P<msg_size>[0-9]+)\s+(?P<avg_bw>[0-9\.]+)\s+(?P<msg_rate>[0-9\.]+)\s+(?P<p50_bw>[0-9\.]+)\s+(?P<p90_bw>[0-9\.]+)\s+(?P<p99_bw>[0-9\.]+)\s*$"
        elif fom_type == self.fom_types.single_avg_lat:
            fom_regex = r"\s*(?P<avg_lat>[0-9\.]+)\s*$"
        elif fom_type == self.fom_types.single_avg_tail_lat:
            fom_regex = r"\s*(?P<avg_lat>[0-9\.]+)\s+(?P<p50_lat>[0-9\.]+)\s+(?P<p90_lat>[0-9\.]+)\s+(?P<p99_lat>[0-9\.]+)\s*$"

        self._add_foms(fom_regex)
