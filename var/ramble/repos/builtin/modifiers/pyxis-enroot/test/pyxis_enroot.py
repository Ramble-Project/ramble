# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.repository
from ramble.main import RambleCommand

workspace = RambleCommand("workspace")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)


def test_pyxis_enroot_forwards_slurm_env_vars(make_workspace_from_config):
    """Test pyxis-enroot includes Slurm task variables and container_path."""
    pyxis_cls = ramble.repository.paths[
        ramble.repository.ObjectTypes.modifiers
    ].get_obj_class("pyxis-enroot")
    for slurm_var in (
        "SLURM_JOB_ID",
        "SLURM_JOB_NODELIST",
        "SLURM_STEP_NODELIST",
        "SLURM_NNODES",
        "SLURM_NTASKS",
        "SLURM_PROCID",
        "SLURM_NODEID",
        "SLURM_LOCALID",
    ):
        assert slurm_var in pyxis_cls._SLURM_CONTAINER_ENV_VARS

    test_config = """
ramble:
  variants:
    workflow_manager: slurm-pyxis
  variables:
    processes_per_node: 1
    n_nodes: 1
    container_uri: docker://alpine:latest
    container_name: alpine
  modifiers:
  - name: pyxis-enroot
  applications:
    hostname:
      workloads:
        parallel:
          experiments:
            test_pyxis: {}
"""
    ws, _ = make_workspace_from_config(test_config)
    workspace("setup", "--dry-run", global_args=["-D", ws.root])

    exec_path = os.path.join(
        ws.experiment_dir,
        "hostname",
        "parallel",
        "test_pyxis",
        "execute_experiment",
    )
    with open(exec_path, encoding="utf-8") as f:
        content = f.read()
        assert "--container-image" in content
        assert "alpine.sqsh" in content
        assert "SLURM_JOB_NODELIST" in content
        assert "SLURM_PROCID" in content
