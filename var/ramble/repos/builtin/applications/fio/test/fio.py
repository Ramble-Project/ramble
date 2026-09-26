# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import json
import os

import pytest

import ramble.workspace
from ramble.main import RambleCommand

workspace = RambleCommand("workspace")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)


def test_fio_inmem_foms_analysis(workspace_name):
    """Test that fio extracts job and I/O mode FOMs in-memory without writing metrics.out"""
    global_args = ["-w", workspace_name]
    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "fio",
            "--wf",
            "standard",
            "-e",
            "test_exp",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-v",
            "batch_submit={execute_experiment}",
            global_args=global_args,
        )
        workspace("setup", global_args=global_args)

        run_dir = os.path.join(
            ws.experiment_dir, "fio", "standard", "test_exp"
        )
        fio_out = os.path.join(run_dir, "fio.out")

        sample_json = {
            "fio version": "fio-3.37",
            "jobs": [
                {
                    "jobname": "test_exp",
                    "job_runtime": 1000,
                    "usr_cpu": 1.5,
                    "sys_cpu": 2.5,
                    "ctx": 42,
                    "majf": 0,
                    "minf": 10,
                    "read": {
                        "io_bytes": 4096,
                        "io_kbytes": 4,
                        "bw_bytes": 4096,
                        "bw": 4,
                        "iops": 100.5,
                        "runtime": 1000,
                        "total_ios": 100,
                        "short_ios": 0,
                        "drop_ios": 0,
                        "slat_ns": {
                            "min": 10,
                            "max": 50,
                            "mean": 20.5,
                            "stddev": 5.1,
                            "N": 100,
                        },
                        "clat_us": {
                            "min": 1,
                            "max": 10,
                            "mean": 3.2,
                            "stddev": 0.8,
                            "N": 100,
                        },
                        "lat_ms": {
                            "min": 2,
                            "max": 12,
                            "mean": 4.0,
                            "stddev": 1.0,
                            "N": 100,
                        },
                        "bw_min": 3,
                        "bw_max": 5,
                        "bw_agg": 100.0,
                        "bw_mean": 4.0,
                        "bw_dev": 0.5,
                        "bw_samples": 10,
                        "iops_min": 90,
                        "iops_max": 110,
                        "iops_mean": 100.5,
                        "iops_stddev": 4.2,
                        "iops_samples": 10,
                    },
                }
            ],
        }

        with open(fio_out, "w", encoding="utf-8") as f:
            json.dump(sample_json, f)

        workspace("analyze", "-f", "json", global_args=global_args)

        result_file = os.path.join(ws.results_dir, "results.latest.json")
        with open(result_file, encoding="utf-8") as f:
            results = json.load(f)

        exp_res = results["experiments"][0]
        contexts_by_name = {ctx["name"]: ctx for ctx in exp_res["CONTEXTS"]}
        assert list(contexts_by_name.keys()) == ["null"]

        null_foms = {f["name"]: f for f in contexts_by_name["null"]["foms"]}
        assert null_foms["Job Name"]["value"] == "test_exp"
        assert null_foms["FIO Version"]["value"] == "fio-3.37"
        assert null_foms["Job Runtime"]["value"] == "1000"
        assert null_foms["Job Runtime"]["units"] == "msec"

        assert null_foms["read Total I/O (Bytes)"]["value"] == "4096"
        assert null_foms["read Total I/O (Bytes)"]["units"] == "B"
        assert null_foms["read Submission Latency (Min)"]["value"] == "10"
        assert null_foms["read Submission Latency (Min)"]["units"] == "ns"
        assert null_foms["read Completion Latency (Mean)"]["value"] == "3200.0"
        assert null_foms["read Completion Latency (Mean)"]["units"] == "ns"
        assert null_foms["read Total Latency (Max)"]["value"] == "12000000"
        assert null_foms["read Total Latency (Max)"]["units"] == "ns"
        assert null_foms["read Submission Latency (N)"]["value"] == "100"
        assert null_foms["read Submission Latency (N)"]["units"] == ""
