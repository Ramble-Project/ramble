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

import ramble.workspace
from ramble.main import RambleCommand

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

config = RambleCommand("config")
workspace = RambleCommand("workspace")


def test_concretize_does_not_set_required(
    mutable_config, mutable_mock_workspace_path, workspace_name
):
    """
    Verify that concretizing an application with required set to True
    does not insert a required statement into software dict.
    """

    test_config = """
ramble:
  variants:
    package_manager: spack
  variables:
    mpi_command: 'mpirun'
    batch_submit: '{execute_experiment}'
    partition: ['part1', 'part2']
    processes_per_node: ['16', '36']
    n_ranks: '{processes_per_node}*{n_nodes}'
    n_threads: '1'
  applications:
    wrfv4:
      variables:
        env_name: 'wrfv4'
      workloads:
        CONUS_12km:
          experiments:
            scaling_{n_nodes}_{partition}_{env_name}:
              success_criteria:
              - name: 'timing'
                mode: 'string'
                match: '.*Timing for main.*'
                file: '{experiment_run_dir}/rsl.out.base'
              env_vars:
                set:
                  OMP_NUM_THREADS: '{n_threads}'
                  TEST_VAR: '1'
                append:
                - var-separator: ', '
                  vars:
                    TEST_VAR: 'add_var'
                - paths:
                    TEST_VAR: 'new_path'
                prepend:
                - paths:
                    TEST_VAR: 'pre_path'
                unset:
                - TEST_VAR
              variables:
                n_nodes: ['1', '2', '4', '8', '16']
              matrix:
              - n_nodes
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

        ws.concretize()

        ws._re_read()

        req_test = True
        with open(config_path, encoding="utf-8") as f:
            for line in f:
                if re.match(r"^[^#]*required", line):
                    req_test = False
                    break
            assert req_test


def test_concretize_allows_invalid_experiment(
    mutable_config, mutable_mock_workspace_path, workspace_name
):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:

        workspace(
            "manage",
            "experiments",
            "gromacs",
            "--wf",
            "water_bare",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        # Remove variables, to create an invalid experiment
        config(
            "rm",
            "applications:gromacs:workloads:water_bare:experiments:generated:n_ranks",
            global_args=global_args,
        )
        config(
            "rm",
            "applications:gromacs:workloads:water_bare:experiments:generated:n_nodes",
            global_args=global_args,
        )

        ws._re_read()

        workspace("concretize")

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()

            assert "gromacs" in data
