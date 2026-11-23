# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import re

import pytest

from ramble.main import RambleCommand
from ramble.workspace import WORKSPACE_EXECUTION_SCRIPT

workspace = RambleCommand("workspace")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)


def test_pyxis_enroot_forwards_slurm_env_vars(make_workspace_from_config):
    """Test pyxis-enroot forwards Slurm task variables and sets container_path."""
    ws, ws_name = make_workspace_from_config()
    global_args = ["-w", ws_name]

    workspace(
        "manage",
        "experiments",
        "hostname",
        "--wf",
        "parallel",
        "-e",
        "test_pyxis",
        "-V",
        "workflow_manager=slurm-pyxis",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "container_uri=docker://alpine:latest",
        "-v",
        "container_name=alpine",
        global_args=global_args,
    )
    workspace(
        "manage",
        "modifiers",
        "--add",
        "-n",
        "pyxis-enroot",
        global_args=global_args,
    )
    workspace("setup", "--dry-run", global_args=global_args)

    exec_path = os.path.join(
        ws.experiment_dir,
        "hostname",
        "parallel",
        "test_pyxis",
        WORKSPACE_EXECUTION_SCRIPT,
    )
    with open(exec_path, encoding="utf-8") as f:
        content = f.read()

    assert "--container-image" in content
    assert "alpine.sqsh" in content

    match = re.search(r"--container-env\s+(\S+)", content)
    assert match is not None, f"Missing --container-env in:\n{content}"
    forwarded = set(match.group(1).split(","))
    expected_slurm_vars = {
        "SLURM_JOB_ID",
        "SLURM_JOB_NODELIST",
        "SLURM_STEP_NODELIST",
        "SLURM_NNODES",
        "SLURM_NTASKS",
        "SLURM_PROCID",
        "SLURM_NODEID",
        "SLURM_LOCALID",
    }
    assert expected_slurm_vars.issubset(forwarded)
