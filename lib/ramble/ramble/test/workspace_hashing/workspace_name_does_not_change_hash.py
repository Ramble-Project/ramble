# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.util.ramble_yaml as ryaml
import ramble.workspace
from ramble.main import RambleCommand
from ramble.namespace import namespace

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


def test_workspace_name_does_not_change_hash(
    mutable_config, mutable_mock_workspace_path, mock_applications
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
    workspace1_name = "test_workspace1"
    workspace2_name = "test_workspace2"
    with ramble.workspace.create(workspace1_name) as ws1:
        ws1.write()

        config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(test_config)
        ws1._re_read()
        workspace("setup", "--dry-run", global_args=["-w", workspace1_name])

        with ramble.workspace.create(workspace2_name) as ws2:
            ws2.write()

            config_path = os.path.join(ws2.config_dir, ramble.workspace.CONFIG_FILE_NAME)

            with open(config_path, "w+", encoding="utf-8") as f:
                f.write(test_config)
            ws2._re_read()
            workspace("setup", "--dry-run", global_args=["-w", workspace2_name])

            metadata_path = os.path.join(ws1.root, ramble.workspace.METADATA_FILE_NAME)
            with open(metadata_path, encoding="utf-8") as f:
                data = ryaml.load(f)
                ws1_hash = data[namespace.metadata]["workspace_digest"]

            metadata_path = os.path.join(ws2.root, ramble.workspace.METADATA_FILE_NAME)
            with open(metadata_path, encoding="utf-8") as f:
                data = ryaml.load(f)
                ws2_hash = data[namespace.metadata]["workspace_digest"]

            assert ws1_hash == ws2_hash
