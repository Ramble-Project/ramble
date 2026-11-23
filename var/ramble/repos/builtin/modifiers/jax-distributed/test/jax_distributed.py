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


def test_jax_distributed_standard_mode(make_workspace_from_config):
    """Test jax-distributed standard (default) mode script generation and isolation."""
    ws, ws_name = make_workspace_from_config()
    global_args = ["-w", ws_name]

    # Default mode on 2-executable workload (verifies usage_filter="once").
    workspace(
        "manage",
        "experiments",
        "hostname",
        "--wf",
        "local_bg",
        "-e",
        "test_default",
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
        "jax-distributed",
        "-s",
        "hostname:local_bg:test_default",
        global_args=global_args,
    )

    # Explicit standard mode with coordinator address and port overrides.
    workspace(
        "manage",
        "experiments",
        "hostname",
        "--wf",
        "local",
        "-e",
        "test_overrides",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "jax_coordinator_address=10.0.0.1",
        "-v",
        "jax_coordinator_port=9999",
        global_args=global_args,
    )
    workspace(
        "manage",
        "modifiers",
        "--add",
        "-n",
        "jax-distributed",
        "-m",
        "standard",
        "-s",
        "hostname:local:test_overrides",
        global_args=global_args,
    )

    workspace("setup", "--dry-run", global_args=global_args)

    # Default mode exports preserve any caller-supplied values.
    default_content = _read_execute_experiment(
        ws, "hostname", "local_bg", "test_default"
    )
    assert (
        'export JAX_COORDINATOR_ADDRESS="${JAX_COORDINATOR_ADDRESS:-}"'
        in default_content
    )
    assert (
        'export JAX_COORDINATOR_PORT="${JAX_COORDINATOR_PORT:-8471}"'
        in default_content
    )
    assert (
        'export JAX_NUM_PROCESSES="${JAX_NUM_PROCESSES:-}"' in default_content
    )
    assert 'export JAX_PROCESS_ID="${JAX_PROCESS_ID:-}"' in default_content

    # Bootstrap injects once across the 2-executable local_bg workload.
    assert (
        default_content.count('if [ -z "${JAX_COORDINATOR_ADDRESS:-}" ]; then')
        == 1
    )

    # Verify coordinator discovery branches and expanded default port are present.
    for token in (
        "MEGASCALE_COORDINATOR_ADDRESS",
        "TPU_WORKER_HOSTNAMES",
        "SLURM_JOB_NODELIST",
        "BATCH_HOSTS_FILE",
        "/etc/mpi/hostfile",
        "PBS_NODEFILE",
        "LSB_HOSTS",
        "OMPI_MCA_orte_hnp_uri",
        "KUBERNETES_SERVICE_HOST",
        "export JAX_COORDINATOR_PORT=${JAX_COORDINATOR_PORT:-8471}",
    ):
        assert token in default_content

    # Mode isolation: node-local env vars must not be set in standard mode.
    for node_local_var in (
        "TPU_HOST_BOUNDS",
        "TPU_SKIP_MDS_QUERY",
        "TPU_WORKER_ID",
        "LIBTPU_INIT_ARGS",
    ):
        assert node_local_var not in default_content
    assert "export TPU_WORKER_HOSTNAMES=" not in default_content

    # Standard mode variable overrides expand into both exports and bootstrap.
    override_content = _read_execute_experiment(
        ws, "hostname", "local", "test_overrides"
    )
    assert (
        'export JAX_COORDINATOR_ADDRESS="${JAX_COORDINATOR_ADDRESS:-10.0.0.1}"'
        in override_content
    )
    assert (
        'export JAX_COORDINATOR_PORT="${JAX_COORDINATOR_PORT:-9999}"'
        in override_content
    )
    assert (
        "export JAX_COORDINATOR_PORT=${JAX_COORDINATOR_PORT:-9999}"
        in override_content
    )


def test_jax_distributed_node_local_mode(make_workspace_from_config):
    """Test jax-distributed node-local mode, required var, and isolation."""
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
        "jax-distributed",
        "-m",
        "node-local",
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
    for standard_var in (
        "JAX_COORDINATOR_ADDRESS",
        "JAX_COORDINATOR_PORT",
        "JAX_NUM_PROCESSES",
        "JAX_PROCESS_ID",
    ):
        assert standard_var not in local_content


@pytest.mark.parametrize(
    "mode,extra_vars,expected_vars,excluded_vars",
    [
        pytest.param(
            "standard",
            [],
            {
                "JAX_COORDINATOR_ADDRESS",
                "JAX_COORDINATOR_PORT",
                "JAX_NUM_PROCESSES",
                "JAX_PROCESS_ID",
            },
            {
                "TPU_HOST_BOUNDS",
                "TPU_SKIP_MDS_QUERY",
                "TPU_WORKER_ID",
                "TPU_WORKER_HOSTNAMES",
                "LIBTPU_INIT_ARGS",
            },
            id="standard",
        ),
        pytest.param(
            "node-local",
            ["-v", "node_local_libtpu_init_args=--custom_flag=true"],
            {
                "TPU_HOST_BOUNDS",
                "TPU_SKIP_MDS_QUERY",
                "TPU_WORKER_ID",
                "TPU_WORKER_HOSTNAMES",
                "LIBTPU_INIT_ARGS",
            },
            {
                "JAX_COORDINATOR_ADDRESS",
                "JAX_COORDINATOR_PORT",
                "JAX_NUM_PROCESSES",
                "JAX_PROCESS_ID",
            },
            id="node-local",
        ),
    ],
)
def test_jax_distributed_container_env_forwarding(
    make_workspace_from_config, mode, extra_vars, expected_vars, excluded_vars
):
    """Test ContainerBase forwards jax-distributed env vars for the active mode."""
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
        *extra_vars,
        global_args=global_args,
    )
    workspace(
        "manage",
        "modifiers",
        "--add",
        "-n",
        "jax-distributed",
        "-m",
        mode,
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
    assert expected_vars.issubset(forwarded)
    assert excluded_vars.isdisjoint(forwarded)
