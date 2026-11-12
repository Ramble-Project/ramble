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


@pytest.mark.parametrize(
    "codes,expected_final,expected_status",
    [
        ([0, 0], "0", "SUCCESS"),
        ([0, 2], "2", "FAILED"),
    ],
)
def test_exit_code_foms(
    workspace_name, codes, expected_final, expected_status
):
    global_args = ["-w", workspace_name]
    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "hostname",
            "--wf",
            "local",
            "-e",
            "test_exp",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            global_args=global_args,
        )
        workspace(
            "manage",
            "modifiers",
            "--add",
            "-n",
            "exit-code",
            global_args=global_args,
        )
        workspace("setup", "--dry-run", global_args=global_args)

        run_dir = os.path.join(
            ws.experiment_dir, "hostname", "local", "test_exp"
        )
        with open(
            os.path.join(run_dir, "test_exp.out"), "w", encoding="utf-8"
        ) as f:
            f.write("test-host.local\n")

        exit_log_path = os.path.join(run_dir, "exit_codes.out")
        log_content = "".join(
            f"Exit code for exec_{i}: {c}\n" for i, c in enumerate(codes)
        )
        with open(exit_log_path, "w", encoding="utf-8") as f:
            f.write(log_content)

        workspace("analyze", "-f", "json", global_args=global_args)

        result_file = os.path.join(ws.results_dir, "results.latest.json")
        with open(result_file, encoding="utf-8") as f:
            data = json.load(f)

        exp = data["experiments"][0]
        assert exp["RAMBLE_STATUS"] == expected_status

        null_foms = {}
        for ctx in exp["CONTEXTS"]:
            if ctx["name"] == "null":
                for fom in ctx["foms"]:
                    null_foms[fom["name"]] = str(fom["value"])

        assert null_foms["Final exit code"] == expected_final
