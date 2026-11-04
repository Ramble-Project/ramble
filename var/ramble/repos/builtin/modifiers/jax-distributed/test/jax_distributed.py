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
from ramble.util.executable import CommandExecutable

workspace = RambleCommand("workspace")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)


@pytest.fixture
def jax_dist_mod_cls():
    return ramble.repository.paths[
        ramble.repository.ObjectTypes.modifiers
    ].get_obj_class("jax-distributed")


def test_jax_distributed_modifier_definition(jax_dist_mod_cls):
    """Test jax-distributed modifier variables and basic properties."""
    inst = jax_dist_mod_cls("/mock/path")
    assert inst.name == "jax-distributed"
    assert "tpu" in inst.tags
    assert "jax" in inst.tags
    assert "slurm" not in inst.tags
    assert "distributed" not in inst.tags

    mod_vars = {
        var.name
        for var_list in inst.object_variables.values()
        for var in var_list
    }
    assert "jax_coordinator_port" in mod_vars
    assert "jax_coordinator_address" in mod_vars
    assert "node_local_libtpu_init_args" in mod_vars
    assert "jax_export_node_rank" not in mod_vars

    env_vars = [
        name
        for when_set in inst.env_var_modifications.values()
        for name in when_set
    ]
    assert "JAX_COORDINATOR_ADDRESS" in env_vars
    assert "JAX_COORDINATOR_PORT" in env_vars
    assert "JAX_NUM_PROCESSES" in env_vars
    assert "JAX_PROCESS_ID" in env_vars
    assert "TPU_HOST_BOUNDS" in env_vars
    assert "TPU_SKIP_MDS_QUERY" in env_vars
    assert "TPU_WORKER_ID" in env_vars
    assert "TPU_WORKER_HOSTNAMES" in env_vars
    assert "LIBTPU_INIT_ARGS" in env_vars
    assert "SLURM_PROCID" not in env_vars
    assert "SLURM_NTASKS" not in env_vars
    assert "SLURM_NODEID" not in env_vars


def test_jax_coordinator_setup(jax_dist_mod_cls):
    """Test jax_coordinator_setup injects multi-WLM discovery script."""
    inst = jax_dist_mod_cls("/mock/path")
    exec_cmd = CommandExecutable(
        "test_exec",
        template=["python3 test.py"],
        mpi=True,
    )
    pre_cmds, post_cmds = inst.jax_coordinator_setup("test_exec", exec_cmd)
    assert len(pre_cmds) == 1
    assert len(post_cmds) == 0
    script = pre_cmds[0].template[0]
    assert "MEGASCALE_COORDINATOR_ADDRESS" in script
    assert "TPU_WORKER_HOSTNAMES" in script
    assert "scontrol show hostnames" in script
    assert "BATCH_HOSTS_FILE" in script
    assert "/etc/mpi/hostfile" in script
    assert "PBS_NODEFILE" in script
    assert "LSB_HOSTS" in script
    assert "JAX_COORDINATOR_ADDRESS" in script
    assert "JAX_COORDINATOR_PORT" in script
    assert exec_cmd.template == ["python3 test.py"]

    # In node-local mode, coordinator bootstrap script is skipped
    inst.set_usage_mode("node-local")
    pre_cmds_local, _ = inst.jax_coordinator_setup("test_exec", exec_cmd)
    assert len(pre_cmds_local) == 0


def test_jax_distributed_dry_run_modes(make_workspace_from_config):
    """Test jax-distributed modifier in standard and node-local modes."""
    test_config = """
ramble:
  variables:
    processes_per_node: 1
    n_nodes: 1
    mpi_command: ''
    batch_submit: '{execute_experiment}'
  applications:
    hostname:
      workloads:
        local:
          experiments:
            test_standard:
              modifiers:
              - name: jax-distributed
                mode: standard
            test_node_local:
              modifiers:
              - name: jax-distributed
                mode: node-local
"""
    ws, _ = make_workspace_from_config(test_config)
    workspace("setup", "--dry-run", global_args=["-D", ws.root])

    std_exec = os.path.join(
        ws.experiment_dir,
        "hostname",
        "local",
        "test_standard",
        "execute_experiment",
    )
    with open(std_exec, encoding="utf-8") as f:
        std_content = f.read()
        assert (
            'export JAX_COORDINATOR_PORT="${JAX_COORDINATOR_PORT:-8471}";'
            in std_content
        )
        assert (
            "export JAX_COORDINATOR_PORT=${JAX_COORDINATOR_PORT:-8471}"
            in std_content
        )
        assert "scontrol show hostnames" in std_content
        assert "TPU_HOST_BOUNDS" not in std_content

    local_exec = os.path.join(
        ws.experiment_dir,
        "hostname",
        "local",
        "test_node_local",
        "execute_experiment",
    )
    with open(local_exec, encoding="utf-8") as f:
        local_content = f.read()
        assert "export TPU_HOST_BOUNDS=1,1,1;" in local_content
        assert "export TPU_SKIP_MDS_QUERY=true;" in local_content
        assert "export TPU_WORKER_ID=0;" in local_content
        assert "export TPU_WORKER_HOSTNAMES=localhost;" in local_content
        assert "--xla_tpu_use_enhanced_launch_barrier=false" in local_content
        assert "scontrol show hostnames" not in local_content
