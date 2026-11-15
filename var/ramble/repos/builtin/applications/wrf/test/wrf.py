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


def test_wrf_foms(workspace_name):
    """Test that wrf computes in-memory and derived FOMs without stats.out"""
    global_args = ["-w", workspace_name]
    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "wrf",
            "--wf",
            "CONUS_12km",
            "-e",
            "test_exp",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-v",
            "mpi_command=mpirun -n {n_ranks}",
            "-v",
            "batch_submit={execute_experiment}",
            global_args=global_args,
        )
        workspace("setup", "--dry-run", global_args=global_args)

        run_dir = os.path.join(
            ws.experiment_dir, "wrf", "CONUS_12km", "test_exp"
        )
        out_file = os.path.join(run_dir, "rsl.out.base")
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(
                "Timing for main: time 2019-11-27_00:01:12 on domain 1: 1.5 elapsed seconds\n"
                "Timing for main: time 2019-11-27_00:02:24 on domain 1: 2.5 elapsed seconds\n"
                "d01 2019-11-27_00:02:24 wrf: SUCCESS COMPLETE WRF\n"
            )

        workspace("analyze", "-f", "json", global_args=global_args)

        assert not os.path.exists(os.path.join(run_dir, "stats.out"))

        result_file = os.path.join(ws.results_dir, "results.latest.json")
        with open(result_file, encoding="utf-8") as f:
            results = json.load(f)

        exp_res = results["experiments"][0]
        assert exp_res["RAMBLE_STATUS"] == "SUCCESS"
        contexts_by_name = {ctx["name"]: ctx for ctx in exp_res["CONTEXTS"]}
        null_foms = {f["name"]: f for f in contexts_by_name["null"]["foms"]}

        assert int(null_foms["Number of timesteps"]["value"]) == 2
        assert float(
            null_foms["Cumulative Timestep Time"]["value"]
        ) == pytest.approx(4.0)
        assert float(
            null_foms["Minimum Timestep Time"]["value"]
        ) == pytest.approx(1.5)
        assert float(
            null_foms["Maximum Timestep Time"]["value"]
        ) == pytest.approx(2.5)
        assert float(
            null_foms["Average Timestep Time"]["value"]
        ) == pytest.approx(2.0)
        assert float(
            null_foms["Avg. Max Ratio Time"]["value"]
        ) == pytest.approx(0.8)
