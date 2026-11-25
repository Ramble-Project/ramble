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

from ramble.error import ObjectValidationError
from ramble.experiment_set import RambleVariableDefinitionError
from ramble.main import RambleCommand
from ramble.workspace import WORKSPACE_EXECUTION_SCRIPT

workspace = RambleCommand("workspace")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)


def _exec_script_path(ws, app, workload, experiment):
    return os.path.join(
        ws.experiment_dir,
        app,
        workload,
        experiment,
        WORKSPACE_EXECUTION_SCRIPT,
    )


def _read_execute_experiment(ws, app, workload, experiment):
    with open(
        _exec_script_path(ws, app, workload, experiment), encoding="utf-8"
    ) as f:
        return f.read()


def test_tpu_node_local_standard_mode(make_workspace_from_config):
    """Test tpu-node-local required variable validation and env var exports."""
    ws, ws_name = make_workspace_from_config()
    global_args = ["-w", ws_name]

    workspace(
        "manage",
        "experiments",
        "hostname",
        "--wf",
        "local",
        "-e",
        "test_node_local",
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
        "tpu-node-local",
        global_args=global_args,
    )

    # Without a TPU platform or explicit variable, setup rejects missing
    # required variable node_local_libtpu_init_args.
    with pytest.raises(RambleVariableDefinitionError):
        workspace("setup", "--dry-run", global_args=global_args)

    workspace(
        "manage",
        "experiments",
        "hostname",
        "--wf",
        "local",
        "-e",
        "test_node_local",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "node_local_libtpu_init_args=--custom_flag=true",
        "--overwrite",
        global_args=global_args,
    )
    workspace("setup", "--dry-run", global_args=global_args)

    local_content = _read_execute_experiment(
        ws, "hostname", "local", "test_node_local"
    )
    for node_local_var in (
        "TPU_HOST_BOUNDS",
        "TPU_SKIP_MDS_QUERY",
        "TPU_WORKER_ID",
        "TPU_WORKER_HOSTNAMES",
    ):
        assert f"export {node_local_var}=" in local_content
    assert (
        'export LIBTPU_INIT_ARGS="${LIBTPU_INIT_ARGS} --custom_flag=true"'
        in local_content
    )
    for distributed_var in (
        "JAX_COORDINATOR_ADDRESS",
        "JAX_COORDINATOR_PORT",
        "JAX_NUM_PROCESSES",
        "JAX_PROCESS_ID",
    ):
        assert distributed_var not in local_content


def test_tpu_node_local_container_env_forwarding(make_workspace_from_config):
    """Test ContainerBase forwards tpu-node-local env vars."""
    ws, ws_name = make_workspace_from_config()
    global_args = ["-w", ws_name]

    workspace(
        "manage",
        "experiments",
        "hostname",
        "--wf",
        "parallel",
        "-e",
        "test_container",
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
        "-v",
        "node_local_libtpu_init_args=--custom_flag=true",
        global_args=global_args,
    )
    workspace(
        "manage",
        "modifiers",
        "--add",
        "-n",
        "tpu-node-local",
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

    content = _read_execute_experiment(
        ws, "hostname", "parallel", "test_container"
    )
    match = re.search(r"--container-env\s+(\S+)", content)
    assert match is not None, f"Missing --container-env in:\n{content}"

    forwarded = set(match.group(1).split(","))
    expected = {
        "TPU_HOST_BOUNDS",
        "TPU_SKIP_MDS_QUERY",
        "TPU_WORKER_ID",
        "TPU_WORKER_HOSTNAMES",
        "LIBTPU_INIT_ARGS",
    }
    excluded = {
        "JAX_COORDINATOR_ADDRESS",
        "JAX_COORDINATOR_PORT",
        "JAX_NUM_PROCESSES",
        "JAX_PROCESS_ID",
    }
    assert expected.issubset(forwarded)
    assert excluded.isdisjoint(forwarded)


def test_tpu_node_local_conflicts_with_jax_distributed(
    make_workspace_from_config,
):
    """Test tpu-node-local conflicts with active jax-distributed modifier."""
    ws, ws_name = make_workspace_from_config()
    global_args = ["-w", ws_name]

    workspace(
        "manage",
        "experiments",
        "hostname",
        "--wf",
        "local",
        "-e",
        "test_conflict",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "node_local_libtpu_init_args=--custom_flag=true",
        global_args=global_args,
    )
    workspace(
        "manage",
        "modifiers",
        "--add",
        "-n",
        "jax-distributed",
        global_args=global_args,
    )
    workspace(
        "manage",
        "modifiers",
        "--add",
        "-n",
        "tpu-node-local",
        global_args=global_args,
    )

    with pytest.raises(
        ObjectValidationError,
        match="tpu-node-local cannot be used with jax-distributed",
    ):
        workspace("setup", "--dry-run", global_args=global_args)

    workspace(
        "manage",
        "modifiers",
        "--remove",
        "-i",
        "0",
        global_args=global_args,
    )
    workspace(
        "manage",
        "modifiers",
        "--add",
        "-n",
        "jax-distributed",
        "-m",
        "disabled",
        global_args=global_args,
    )
    workspace("setup", "--dry-run", global_args=global_args)
    content = _read_execute_experiment(
        ws, "hostname", "local", "test_conflict"
    )
    assert "export TPU_HOST_BOUNDS=" in content
    assert "JAX_COORDINATOR_ADDRESS" not in content
