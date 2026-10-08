# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.filters
import ramble.pipeline
import ramble.repository
import ramble.workspace
from ramble.main import RambleCommand

ApplicationBase = ramble.repository.get_obj_class(
    "application-base", object_type=ramble.repository.ObjectTypes.base_classes
)

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


def test_workspace_setup_creates_inventory(
    mutable_config, mutable_mock_workspace_path, mock_applications, workspace_name
):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    partition: 'part1'
    processes_per_node: '16'
    n_threads: '1'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            simple_test:
              variables:
                n_nodes: 1
              env_vars:
                set:
                  MY_VAR: 'TEST'
  software:
    packages: {}
    environments: {}
"""
    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        config_path = os.path.join(ws.config_dir, ramble.workspace.CONFIG_FILE_NAME)

        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(test_config)
        ws._re_read()
        workspace("setup", "--dry-run", global_args=["-w", workspace_name])

        assert os.path.exists(
            os.path.join(ws.root, ramble.workspace.Workspace.inventory_file_name)
        )
        assert os.path.exists(os.path.join(ws.root, ramble.workspace.Workspace.hash_file_name))
        assert os.path.exists(
            os.path.join(
                ws.experiment_dir,
                "basic",
                "test_wl",
                "simple_test",
                ApplicationBase._inventory_file_name,
            )
        )


def test_deterministic_workspace_hash(workspace_name):
    global_args = ["-w", workspace_name]
    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "hostname",
            "--wf",
            "local",
            "--wm",
            "slurm",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )
        ws._re_read()
        workspace("setup", "--dry-run", global_args=global_args)
        hash_file = os.path.join(ws.root, ramble.workspace.Workspace.hash_file_name)
        with open(hash_file, encoding="utf-8") as f:
            hash = f.read().strip()
        workspace("setup", "--dry-run", global_args=global_args)
        with open(hash_file, encoding="utf-8") as f:
            new_hash = f.read().strip()

        assert hash == new_hash


def test_construct_experiment_hashes_preserves_changes(workspace_name):
    global_args = ["-w", workspace_name]
    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "hostname",
            "--wf",
            "local",
            "-e",
            "exp{n_ranks}",
            "-v",
            "n_ranks=[1,2]",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )
        workspace("setup", "--dry-run", global_args=global_args)

        # Remove only the first experiment's inventory so its hash is recomputed
        # while the second experiment's inventory remains unchanged.
        exp1_inventory = os.path.join(
            ws.experiment_dir,
            "hostname",
            "local",
            "exp1",
            ApplicationBase._inventory_file_name,
        )
        os.remove(exp1_inventory)

        pipe = ramble.pipeline.Pipeline(ws, ramble.filters.Filters())
        assert pipe._construct_experiment_hashes() is True
