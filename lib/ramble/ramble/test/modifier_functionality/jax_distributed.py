# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.repository
from ramble.util.executable import CommandExecutable


@pytest.fixture
def jax_dist_mod_cls():
    return ramble.repository.paths[ramble.repository.ObjectTypes.modifiers].get_obj_class(
        "jax-distributed"
    )


def test_jax_distributed_modifier_definition(jax_dist_mod_cls):
    """Test jax-distributed modifier variables and basic properties."""
    inst = jax_dist_mod_cls("/mock/path")
    assert inst.name == "jax-distributed"
    assert "tpu" in inst.tags
    assert "jax" in inst.tags

    # Check env var modifications are registered
    env_vars = [name for when_set in inst.env_var_modifications.values() for name in when_set]
    assert "JAX_COORDINATOR_ADDRESS" in env_vars
    assert "JAX_COORDINATOR_PORT" in env_vars
    assert "SLURM_PROCID" in env_vars
    assert "SLURM_NTASKS" in env_vars
    assert "SLURM_NODEID" in env_vars


def test_jax_coordinator_setup(jax_dist_mod_cls):
    """Test jax_coordinator_setup injects coordinator discovery script."""
    inst = jax_dist_mod_cls("/mock/path")
    exec_cmd = CommandExecutable(
        "test_exec",
        template=["python3 test.py"],
        mpi=True,
    )
    pre_cmds, post_cmds = inst.jax_coordinator_setup("test_exec", exec_cmd)
    assert len(pre_cmds) == 1
    assert "scontrol show hostnames" in pre_cmds[0].template[0]
    assert "JAX_COORDINATOR_ADDRESS" in pre_cmds[0].template[0]
    assert "JAX_COORDINATOR_PORT" in pre_cmds[0].template[0]
