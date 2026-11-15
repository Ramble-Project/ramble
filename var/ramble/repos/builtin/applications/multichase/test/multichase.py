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


def test_multichase_foms(workspace_name):
    """Test that multichase computes Array Size via a derived FOM formula"""
    global_args = ["-w", workspace_name]
    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "multichase",
            "--wf",
            "latency",
            "-e",
            "test_exp",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-v",
            "array_size=2m",
            global_args=global_args,
        )
        workspace("setup", "--dry-run", global_args=global_args)

        run_dir = os.path.join(
            ws.experiment_dir, "multichase", "latency", "test_exp"
        )
        with open(
            os.path.join(run_dir, "test_exp.out"), "w", encoding="utf-8"
        ) as f:
            f.write("72.5\n")

        workspace("analyze", "-f", "json", global_args=global_args)

        result_file = os.path.join(ws.results_dir, "results.latest.json")
        with open(result_file, encoding="utf-8") as f:
            results = json.load(f)

        exp_res = results["experiments"][0]
        assert exp_res["RAMBLE_STATUS"] == "SUCCESS"
        contexts_by_name = {ctx["name"]: ctx for ctx in exp_res["CONTEXTS"]}
        null_foms = {f["name"]: f for f in contexts_by_name["null"]["foms"]}
        assert float(
            null_foms["Multichase Best Latency"]["value"]
        ) == pytest.approx(72.5)
        assert int(null_foms["Array Size"]["value"]) == 2 * 1024 * 1024
