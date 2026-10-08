# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.workspace
from ramble.main import RambleCommand
from ramble.success_criteria import SuccessCriteriaScope

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")
ramble_on = RambleCommand("on")


def test_disconnected_success(mock_applications, workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: '{execute_experiment}'
    processes_per_node: '1'
    n_threads: '1'
  applications:
    basic:
      workloads:
        working_wl:
          experiments:
            pass-experiment:
              variables:
                n_nodes: 1
              success_criteria:
              - name: always-pass
                mode: string
                match: '.*seconds.*'
            fail-experiment:
              variables:
                n_nodes: 1
              success_criteria:
              - name: always-fail
                mode: string
                match: 'Blarg'
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

        workspace("setup", global_args=["-w", workspace_name])
        ramble_on(global_args=["-w", workspace_name])
        workspace(
            "analyze", "--where", "{experiment_index} == 1", global_args=["-w", workspace_name]
        )

        with open(os.path.join(ws.results_dir, "results.latest.txt"), encoding="utf-8") as f:
            data = f.read()
            assert "Status = SUCCESS" in data

        workspace(
            "analyze", "--where", "{experiment_index} == 2", global_args=["-w", workspace_name]
        )

        with open(os.path.join(ws.results_dir, "results.latest.txt"), encoding="utf-8") as f:
            data = f.read()
            assert "Status = FAILED" in data


def test_experiment_success_list_populated_at_init(
    mock_applications, mock_modifiers, workspace_name
):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: '{execute_experiment}'
    processes_per_node: '1'
    n_threads: '1'
    target_pattern: 'libz.so'
  applications:
    zlib:
      workloads:
        ensure_installed:
          experiments:
            test_exp:
              variables:
                n_nodes: 1
              modifiers:
              - name: success-criteria
                mode: test
              success_criteria:
              - name: exp_criteria_with_var
                mode: string
                match: '{target_pattern}'
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

        exp_set = ws.build_experiment_set()
        for _, app, _ in exp_set.all_experiments():
            obj_names = [
                c.name for c in app.success_list.criteria[SuccessCriteriaScope.OBJECT_DEFINITIONS]
            ]
            assert "zlib_installed" in obj_names
            assert "status" in obj_names
            assert "_application_function" in obj_names

            crit = app.success_list.find_criteria("exp_criteria_with_var")
            assert crit is not None
            assert crit.match.pattern == "libz.so"
