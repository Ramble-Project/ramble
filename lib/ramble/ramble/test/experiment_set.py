# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.context
import ramble.experiment_set
import ramble.workspace
from ramble.error import ChainCycleDetectedError, InvalidChainError
from ramble.main import RambleCommand

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
    "mutable_mock_apps_repo",
)

workspace = RambleCommand("workspace")


def test_single_experiment_in_set():
    workspace("create", "test")

    assert "test" in workspace("list")

    with ramble.workspace.read("test") as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {
            "exp_var1": "1",
            "exp_var2": "2",
            "n_nodes": "2",
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4" in exp_set.experiments


def test_vector_experiment_in_set():
    workspace("create", "test")

    assert "test" in workspace("list")

    with ramble.workspace.read("test") as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "4"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series1_8" in exp_set.experiments


def test_vector_length_mismatch_errors(workspace_name, capsys):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"processes_per_node": ["2", "4", "6"]}
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}_{processes_per_node}"
        experiment_context.variables = {"n_nodes": ["2", "4"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        with pytest.raises(SystemExit):
            exp_set.set_experiment_context(experiment_context)

        captured = capsys.readouterr().err

        assert "Length mismatch in vector variables in experiment series1_{n_ranks}" in captured
        assert "Variable processes_per_node has length 3" in captured
        assert "Variable n_nodes has length 2" in captured


def test_nonunique_vector_errors(workspace_name, capsys):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{processes_per_node}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "4"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)

        with pytest.raises(SystemExit):
            exp_set.set_experiment_context(experiment_context)

        captured = capsys.readouterr().err
        assert "is not unique." in captured


def test_collision_across_different_blocks(workspace_name, capsys):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"

        experiment_context1 = ramble.context.Context()
        experiment_context1.context_name = "collision_{my_var1}"
        experiment_context1.variables = {"my_var1": "foo", "my_var2": "bar"}

        experiment_context2 = ramble.context.Context()
        experiment_context2.context_name = "collision_{my_var2}"
        experiment_context2.variables = {
            "my_var1": "baz",
            "my_var2": "foo",
            "unique_to_right": "yes",
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)

        # Ingest the first experiment
        exp_set.set_experiment_context(experiment_context1)

        # Ingest the second experiment, which should trigger collision
        with pytest.raises(SystemExit):
            exp_set.set_experiment_context(experiment_context2)

        captured = capsys.readouterr().err
        assert "is not unique." in captured
        assert (
            "Collision Origin: Across different YAML "
            "experiment blocks: 'collision_{my_var1}' vs 'collision_{my_var2}'" in captured
        )

        assert "Variables unique to newly defined experiment:" in captured
        assert "unique_to_right" in captured


def test_collision_static_definition(workspace_name, capsys):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"

        experiment_context1 = ramble.context.Context()
        experiment_context1.context_name = "static_collision"

        experiment_context2 = ramble.context.Context()
        experiment_context2.context_name = "static_collision"

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)

        # Ingest the first experiment
        exp_set.set_experiment_context(experiment_context1)

        # Ingest the second experiment, which should trigger collision
        with pytest.raises(SystemExit):
            exp_set.set_experiment_context(experiment_context2)

        captured = capsys.readouterr().err
        assert "is not unique." in captured
        assert (
            "Collision Origin: Static definition (No Matrix/Vector expansion active)" in captured
        )
        assert (
            "Multiple distinct experiment blocks in your YAML are using the same literal name."
            in captured
        )


def test_collision_matrix_and_zip(workspace_name, capsys):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"

        experiment_context = ramble.context.Context()
        # Name template does not use the matrix/zip variables, so they will collide
        experiment_context.context_name = "collision_matrix"
        experiment_context.variables = {
            "var_a": ["1", "2"],
            "var_b": ["a", "b"],
            "var_c": ["x", "y"],
        }
        experiment_context.zips = {"my_zip": ["var_b", "var_c"]}
        experiment_context.matrices = [["var_a", "my_zip"]]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)

        with pytest.raises(SystemExit):
            exp_set.set_experiment_context(experiment_context)

        captured = capsys.readouterr().err
        assert "is not unique." in captured
        assert "var_b" in captured
        assert "var_c" in captured


def test_zipped_vector_experiments(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
            "processes_per_node": ["2", "4"],
        }
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}_{processes_per_node}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "4"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4_2" in exp_set.experiments
        assert "basic.test_wl.series1_16_4" in exp_set.experiments


def test_matrix_experiments(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "3"]}
        experiment_context.matrices = [["n_nodes"]]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series1_6" in exp_set.experiments


def test_matrix_multiplication_experiments(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
            "processes_per_node": ["1", "4", "6"],
        }
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "4"]}
        experiment_context.matrices = [["n_nodes", "processes_per_node"]]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_2" in exp_set.experiments
        assert "basic.test_wl.series1_8" in exp_set.experiments
        assert "basic.test_wl.series1_12" in exp_set.experiments
        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series1_16" in exp_set.experiments
        assert "basic.test_wl.series1_24" in exp_set.experiments


def test_matrix_vector_experiments(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
            "processes_per_node": ["2", "4"],
        }
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "3"]}
        experiment_context.matrices = [["n_nodes"]]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series1_8" in exp_set.experiments
        assert "basic.test_wl.series1_6" in exp_set.experiments
        assert "basic.test_wl.series1_12" in exp_set.experiments


def test_multi_matrix_experiments(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
            "processes_per_node": ["2", "4"],
        }
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}_{processes_per_node}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "3"]}
        experiment_context.matrices = [["n_nodes"], ["processes_per_node"]]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4_2" in exp_set.experiments
        assert "basic.test_wl.series1_12_4" in exp_set.experiments


def test_full_experiments_from_dict(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_dict = {
            "variables": {
                "n_ranks": "{processes_per_node}*{n_nodes}",
                "mpi_command": "",
                "batch_submit": "",
            }
        }

        wl_dict = {"variables": {"partition": ["p1", "p2"], "processes_per_node": ["2", "4"]}}

        exp_dict = {
            "variables": {"n_nodes": ["2", "3"], "ids": ["1", "2", "3", "4"]},
            "zips": {"part_conf": ["partition", "processes_per_node"]},
            "matrices": [{"mat_name": ["part_conf", "n_nodes"]}],
            "matrix": ["ids"],
        }

        appContext = ramble.context.create_context_from_dict("basic", app_dict)
        wlContext = ramble.context.create_context_from_dict("test_wl", wl_dict)
        expContext = ramble.context.create_context_from_dict(
            "test_{n_ranks}_{processes_per_node}_{ids}", exp_dict
        )

        exp_set.set_application_context(appContext)
        exp_set.set_workload_context(wlContext)
        exp_set.set_experiment_context(expContext)

        assert "basic.test_wl.test_4_2_1" in exp_set.experiments
        assert "basic.test_wl.test_6_2_2" in exp_set.experiments
        assert "basic.test_wl.test_8_4_3" in exp_set.experiments
        assert "basic.test_wl.test_12_4_4" in exp_set.experiments

        assert exp_set._context[exp_set._contexts.workspace].context_name is not None


def test_matrix_undefined_var_errors(workspace_name, capsys):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
            "processes_per_node": ["2", "4"],
        }

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}_{processes_per_node}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "3"]}
        experiment_context.matrices = [["n_nodes"], ["foo"]]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)

        with pytest.raises(SystemExit):
            exp_set.set_experiment_context(experiment_context)

        captured = capsys.readouterr().err
        assert "variable or zip foo has not been defined yet." in captured


def test_experiment_names_match(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
            "processes_per_node": ["2", "4"],
        }
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}_{processes_per_node}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "3"]}
        experiment_context.matrices = [["n_nodes"], ["processes_per_node"]]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4_2" in exp_set.experiments
        assert "basic.test_wl.series1_12_4" in exp_set.experiments

        for exp, app, _ in exp_set.all_experiments():
            assert exp == app.expander.expand_var("{experiment_namespace}")


def test_cross_experiment_variable_references(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment1_context = ramble.context.Context()
        experiment1_context.context_name = "series1_{n_ranks}"
        experiment1_context.variables = {
            "exp_var1": "1",
            "exp_var2": "2",
            "n_nodes": "2",
            "test_var": "success",
        }
        experiment1_context.internals = {
            "custom_executables": {
                "echo_test": {"template": 'echo "{test_var}"'},
            },
            "executable_injection": [{"name": "echo_test", "order": "after"}],
        }

        experiment2_context = ramble.context.Context()
        experiment2_context.context_name = "series2_{n_ranks}"
        experiment2_context.variables = {
            "exp_var1": "1",
            "exp_var2": "2",
            "n_nodes": "2",
            "test_var": "test_var in basic.test_wl.series1_4",
        }

        experiment2_context.internals = {
            "custom_executables": {
                "echo_test": {"template": 'echo "{test_var}"'},
            },
            "executable_injection": [{"name": "echo_test", "order": "after"}],
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment1_context)
        exp_set.set_experiment_context(experiment2_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series2_4" in exp_set.experiments

        exp2_app = exp_set.experiments["basic.test_wl.series2_4"]
        assert exp2_app.expander.expand_var("{test_var}") == "success"


def test_cross_experiment_missing_experiment_errors(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment1_context = ramble.context.Context()
        experiment1_context.context_name = "series1_{n_ranks}"
        experiment1_context.variables = {
            "exp_var1": "1",
            "exp_var2": "2",
            "n_nodes": "2",
            "test_var": "processes_per_node in basic.test_wl.does_not_exist",
        }

        experiment1_context.internals = {
            "custom_executables": {
                "echo_test": {"template": 'echo "{test_var}"'},
            },
            "executable_injection": [{"name": "echo_test", "order": "after"}],
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)

        expected = (
            "basic.test_wl.does_not_exist does not exist in: "
            f'"{experiment1_context.variables["test_var"]}"'
        )
        with pytest.raises(ramble.expander.RambleSyntaxError, match=expected):
            exp_set.set_experiment_context(experiment1_context)


def test_n_ranks_correct_defaults(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl2"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "3"]}
        experiment_context.matrices = [["n_nodes"]]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl2.series1_4" in exp_set.experiments
        assert "basic.test_wl2.series1_6" in exp_set.experiments


def test_n_nodes_correct_defaults(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": ["4", "6"],
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl2"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}_{n_nodes}"
        experiment_context.variables = {
            "exp_var1": "1",
            "exp_var2": "2",
        }
        experiment_context.matrices = [["n_ranks"]]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl2.series1_4_2" in exp_set.experiments
        assert "basic.test_wl2.series1_6_3" in exp_set.experiments


def test_processes_per_node_correct_defaults(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)
        # Remove workspace vars, which default to a `processes_per_node = -1` definition.
        exp_set._context[exp_set._contexts.workspace].variables = {}

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": ["4", "6"],
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl2"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}_{processes_per_node}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "3"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl2.series1_4_2" in exp_set.experiments
        assert "basic.test_wl2.series1_6_2" in exp_set.experiments


@pytest.mark.parametrize("var", ["env_path"])
def test_reserved_keywords_error_in_application(workspace_name, var):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": ["4", "6"],
            var: "should_fail",
            "mpi_command": "",
            "batch_submit": "",
        }

        with pytest.raises(ramble.experiment_set.RambleVariableDefinitionError) as e:
            exp_set.set_application_context(application_context)
        captured = str(e.value)
        assert "In application basic" in captured
        assert f"{var}" in captured
        assert "is reserved by ramble" in captured


@pytest.mark.parametrize("var", ["env_path"])
def test_reserved_keywords_error_in_workload(workspace_name, var):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": ["4", "6"],
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", var: "should_fail"}

        exp_set.set_application_context(application_context)
        with pytest.raises(ramble.experiment_set.RambleVariableDefinitionError) as e:
            exp_set.set_workload_context(workload_context)
        captured = str(e.value)
        assert "In workload basic.test_wl" in captured
        assert f"{var}" in captured
        assert "is reserved by ramble" in captured


@pytest.mark.parametrize("var", ["env_path"])
def test_reserved_keywords_error_in_experiment(workspace_name, var):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)
        # Remove workspace vars, which default to a `processes_per_node = -1` definition.
        exp_set._context[exp_set._contexts.base].variables = {}

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": ["4", "6"],
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}_{processes_per_node}"
        experiment_context.variables = {
            "exp_var1": "1",
            "exp_var2": "2",
            "n_nodes": ["2", "3"],
            var: "should_fail",
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        with pytest.raises(ramble.experiment_set.RambleVariableDefinitionError) as e:
            exp_set.set_experiment_context(experiment_context)
        captured = str(e.value)
        assert "In experiment basic.test_wl" in captured
        assert f"{var}" in captured
        assert "is reserved by ramble" in captured


def test_missing_required_keyword_errors(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl2"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }
        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1"
        experiment_context.variables = {
            "exp_var1": "1",
            "exp_var2": "2",
            "batch_submit": "",
            "mpi_command": "",
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)

        match_str = r"Invalid number of required variables defined"
        with pytest.raises(ramble.error.ObjectValidationError, match=match_str):
            exp_set.set_experiment_context(experiment_context)


def test_chained_experiments_populate_new_experiments(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }

        experiment1_context = ramble.context.Context()
        experiment1_context.context_name = "test1"
        experiment1_context.variables = {"n_ranks": "2"}

        experiment2_context = ramble.context.Context()
        experiment2_context.context_name = "series2_{n_ranks}"
        experiment2_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_ranks": ["4", "6"]}
        experiment2_context.chained_experiments = [
            {
                "name": "basic.test_wl.test1",
                "order": "before_root",
                "command": "{execute_experiment}",
                "variables": {},
            },
            {
                "name": "basic.test_wl.test1",
                "order": "after_root",
                "command": "{execute_experiment}",
                "variables": {},
            },
        ]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment1_context)
        exp_set.set_experiment_context(experiment2_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series2_4" in exp_set.experiments
        assert "basic.test_wl.series2_4.chain.0.basic.test_wl.test1" in exp_set.chained_experiments
        assert "basic.test_wl.series2_4.chain.1.basic.test_wl.test1" in exp_set.chained_experiments
        assert "basic.test_wl.series2_6" in exp_set.experiments
        assert "basic.test_wl.series2_6.chain.0.basic.test_wl.test1" in exp_set.chained_experiments
        assert "basic.test_wl.series2_6.chain.1.basic.test_wl.test1" in exp_set.chained_experiments
        assert "basic.test_wl.test1" in exp_set.experiments

        assert exp_set.get_var_from_experiment("basic.test_wl.series2_4", "{n_ranks}") == "4"
        assert (
            exp_set.get_var_from_experiment(
                "basic.test_wl.series2_4.chain.0.basic.test_wl.test1", "{n_ranks}"
            )
            == "2"
        )
        assert exp_set.get_var_from_experiment("non_existent.exp.name", "{n_ranks}") is None


def test_chained_experiment_has_correct_directory(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }

        experiment1_context = ramble.context.Context()
        experiment1_context.context_name = "test1"
        experiment1_context.variables = {"n_ranks": "2"}

        experiment2_context = ramble.context.Context()
        experiment2_context.context_name = "series2_{n_ranks}"
        experiment2_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_ranks": "4"}
        experiment2_context.chained_experiments = [
            {
                "name": "basic.test_wl.test1",
                "order": "before_root",
                "command": "{execute_experiment}",
                "variables": {},
            },
        ]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment1_context)
        exp_set.set_experiment_context(experiment2_context)
        exp_set.build_experiment_chains()

        parent_name = "basic.test_wl.series2_4"
        chained_name = "basic.test_wl.series2_4.chain.0.basic.test_wl.test1"
        chained_dir = "chain.0.basic.test_wl.test1"
        assert parent_name in exp_set.experiments
        assert chained_name in exp_set.chained_experiments

        parent_inst = exp_set.get_experiment(parent_name)
        chained_inst = exp_set.get_experiment(chained_name)

        parent_run_dir = parent_inst.expander.expand_var("{experiment_run_dir}")
        expected_dir = os.path.join(parent_run_dir, "chained_experiments", chained_dir)
        assert chained_inst.variables["experiment_run_dir"] == expected_dir


def test_chained_cycle_errors(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }

        experiment1_context = ramble.context.Context()
        experiment1_context.context_name = "test1"
        experiment1_context.variables = {"n_ranks": "2"}

        experiment2_context = ramble.context.Context()
        experiment2_context.context_name = "series2_{n_ranks}"
        experiment2_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_ranks": "4"}
        experiment2_context.chained_experiments = [
            {
                "name": "basic.test_wl.series2_4",
                "order": "before_root",
                "command": "{execute_experiment}",
                "variables": {},
            },
        ]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment1_context)
        exp_set.set_experiment_context(experiment2_context)
        with pytest.raises(ChainCycleDetectedError, match="Cycle detected in experiment chain"):
            exp_set.build_experiment_chains()


def test_chained_invalid_order_errors(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }

        experiment1_context = ramble.context.Context()
        experiment1_context.context_name = "test1"
        experiment1_context.variables = {"n_ranks": "2"}

        experiment2_context = ramble.context.Context()
        experiment2_context.context_name = "series2_{n_ranks}"
        experiment2_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_ranks": "4"}
        experiment2_context.chained_experiments = [
            {
                "name": "basic.test_wl.test1",
                "order": "foo",
                "command": "{execute_experiment}",
                "variables": {},
            },
        ]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment1_context)
        exp_set.set_experiment_context(experiment2_context)
        with pytest.raises(InvalidChainError, match="Invalid experiment chain defined:"):
            exp_set.build_experiment_chains()


def test_modifiers_set_correctly(workspace_name, mock_modifiers):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "1",
            "modeless_required_var": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        application_context.modifiers = [
            {"name": "test-mod", "mode": "app-scope", "on_executable": ["builtin::env_vars"]}
        ]

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }
        workload_context.modifiers = [
            {"name": "test-mod", "mode": "wl-scope", "on_executable": ["builtin::env_vars"]}
        ]

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "test1"
        experiment_context.variables = {"n_ranks": "2"}
        experiment_context.modifiers = [
            {"name": "test-mod", "mode": "exp-scope", "on_executable": ["builtin::env_vars"]}
        ]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)

        assert "basic.test_wl.test1" in exp_set.experiments
        app_inst = exp_set.experiments["basic.test_wl.test1"]
        assert app_inst.modifiers is not None

        expected_modifier_modes = {"app-scope", "wl-scope", "exp-scope"}
        for mod_def in app_inst.modifiers:
            assert mod_def["mode"] in expected_modifier_modes
            expected_modifier_modes.remove(mod_def["mode"])
        assert not expected_modifier_modes


def test_explicit_zips_work(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "4"]}
        experiment_context.zips = {"test_zip": ["n_nodes"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series1_8" in exp_set.experiments


def test_explicit_zips_in_matrix(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}_{exp_var1}"
        experiment_context.variables = {
            "exp_var1": ["1", "a", "3"],
            "exp_var2": ["2", "b", "4"],
            "n_nodes": ["2", "4"],
        }
        experiment_context.matrices = [["test_zip"]]
        experiment_context.zips = {"test_zip": ["exp_var1", "exp_var2"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4_1" in exp_set.experiments
        assert "basic.test_wl.series1_4_a" in exp_set.experiments
        assert "basic.test_wl.series1_4_3" in exp_set.experiments
        assert "basic.test_wl.series1_8_1" in exp_set.experiments
        assert "basic.test_wl.series1_8_a" in exp_set.experiments
        assert "basic.test_wl.series1_8_3" in exp_set.experiments


def test_explicit_zips_unconsumed(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}_{exp_var1}"
        experiment_context.variables = {
            "exp_var1": ["1", "a", "3"],
            "exp_var2": ["2", "b", "4"],
            "n_nodes": ["2", "4"],
        }
        experiment_context.matrices = [["n_nodes"]]
        experiment_context.zips = {"test_zip": ["exp_var1", "exp_var2"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4_1" in exp_set.experiments
        assert "basic.test_wl.series1_4_a" in exp_set.experiments
        assert "basic.test_wl.series1_4_3" in exp_set.experiments
        assert "basic.test_wl.series1_8_1" in exp_set.experiments
        assert "basic.test_wl.series1_8_a" in exp_set.experiments
        assert "basic.test_wl.series1_8_3" in exp_set.experiments


def test_single_var_explicit_zip(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "4"]}
        experiment_context.zips = {
            "test_zip": ["n_nodes"],
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series1_8" in exp_set.experiments


def test_zip_multi_use_var_errors(workspace_name, capsys):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "4"]}
        experiment_context.zips = {
            "test_zip1": ["n_nodes"],
            "test_zip2": ["n_nodes"],
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        with pytest.raises(SystemExit):
            exp_set.set_experiment_context(experiment_context)
        captured = capsys.readouterr().err
        assert "An undefined variable n_nodes is defined in zip test_zip2" in captured


def test_zip_non_list_var_errors(workspace_name, capsys):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {"n_nodes": ["2", "4"], "exp_var1": ["1", "2"]}
        experiment_context.zips = {
            "test_zip": ["exp_var1", "processes_per_node"],
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        with pytest.raises(SystemExit):
            exp_set.set_experiment_context(experiment_context)
        captured = capsys.readouterr().err
        assert "Variable processes_per_node in zip test_zip does not refer to a vector" in captured


def test_zip_variable_lengths_errors(workspace_name, capsys):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {
            "exp_var1": "1",
            "processes_per_node": ["2"],
            "n_nodes": ["2", "4"],
        }
        experiment_context.zips = {
            "test_zip": ["n_nodes", "processes_per_node"],
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        with pytest.raises(SystemExit):
            exp_set.set_experiment_context(experiment_context)
        captured = capsys.readouterr().err
        assert "Variable processes_per_node in zip" in captured
        assert "has a length of 1" in captured
        assert "differs from the current max of 2" in captured


def test_vector_experiment_with_explicit_excludes(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "4"]}
        experiment_context.exclude = {"variables": {"n_nodes": ["4"]}}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series1_8" not in exp_set.experiments


def test_matrix_experiments_explicit_excludes(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {"exp_var1": "1", "exp_var2": "2", "n_nodes": ["2", "3"]}
        experiment_context.matrices = [["n_nodes"]]
        experiment_context.exclude = {
            "variables": {
                "n_nodes": ["3"],
            },
            "matrix": ["n_nodes"],
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series1_6" not in exp_set.experiments


def test_vector_experiment_with_where_excludes(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {
            "exp_var1": "1",
            "exp_var2": "2",
            "n_nodes": ["1", "2", "3", "4", "5"],
        }
        experiment_context.exclude = {"where": ["{n_nodes} > 2 and {n_nodes} < 5"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_2" in exp_set.experiments
        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series1_6" not in exp_set.experiments
        assert "basic.test_wl.series1_8" not in exp_set.experiments
        assert "basic.test_wl.series1_10" in exp_set.experiments


def test_vector_experiment_with_late_where_excludes(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {
            "exp_var1": "1",
            "exp_var2": "2",
            "n_nodes": ["1", "2", "3", "4", "5"],
        }
        experiment_context.exclude = {"where": ["{my_base_var} == 0.0"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert not exp_set.experiments
        assert "basic.test_wl.series1_2" not in exp_set.experiments
        assert "basic.test_wl.series1_4" not in exp_set.experiments
        assert "basic.test_wl.series1_6" not in exp_set.experiments
        assert "basic.test_wl.series1_8" not in exp_set.experiments
        assert "basic.test_wl.series1_10" not in exp_set.experiments


def test_vector_experiment_with_multi_where_excludes(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {
            "exp_var1": "1",
            "exp_var2": "2",
            "n_nodes": ["1", "2", "3", "4", "5"],
        }
        experiment_context.exclude = {"where": ["{n_nodes} < 2", "{n_nodes} > 4"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_2" not in exp_set.experiments
        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series1_6" in exp_set.experiments
        assert "basic.test_wl.series1_8" in exp_set.experiments
        assert "basic.test_wl.series1_10" not in exp_set.experiments


def test_unused_vector_no_error(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {
            "exp_var1": "1",
            "exp_var2": "2",
            "other_var": ["1", "2,", "3"],
            "n_nodes": ["1", "2", "3", "4", "5"],
        }
        experiment_context.exclude = {"where": ["{n_nodes} < 2", "{n_nodes} > 4"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_2" not in exp_set.experiments
        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series1_6" in exp_set.experiments
        assert "basic.test_wl.series1_8" in exp_set.experiments
        assert "basic.test_wl.series1_10" not in exp_set.experiments


def test_unused_zip_no_error(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "n_ranks": "{processes_per_node}*{n_nodes}",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {"wl_var1": "1", "wl_var2": "2", "processes_per_node": "2"}

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series1_{n_ranks}"
        experiment_context.variables = {
            "exp_var1": "1",
            "exp_var2": "2",
            "other_var_1": ["1", "2,", "3"],
            "other_var_2": ["1", "2,", "3"],
            "n_nodes": ["1", "2", "3", "4", "5"],
        }
        experiment_context.zips = {
            "test_zip": ["other_var_1", "other_var_2"],
        }
        experiment_context.exclude = {"where": ["{n_nodes} < 2", "{n_nodes} > 4"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series1_2" not in exp_set.experiments
        assert "basic.test_wl.series1_4" in exp_set.experiments
        assert "basic.test_wl.series1_6" in exp_set.experiments
        assert "basic.test_wl.series1_8" in exp_set.experiments
        assert "basic.test_wl.series1_10" not in exp_set.experiments


def test_unused_var_propagates_to_chain(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        expanded_app_context = ramble.context.Context()
        expanded_app_context.context_name = "expanded_foms"
        expanded_app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }

        expanded_wl_context = ramble.context.Context()
        expanded_wl_context.context_name = "test_wl"
        expanded_wl_context.variables = {}

        expanded_exp_context = ramble.context.Context()
        expanded_exp_context.context_name = "test"
        expanded_exp_context.variables = {"n_ranks": "1", "my_var": "2.0"}
        expanded_exp_context.is_template = True

        exp_set.set_application_context(expanded_app_context)
        exp_set.set_workload_context(expanded_wl_context)
        exp_set.set_experiment_context(expanded_exp_context)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "test1"
        experiment_context.variables = {"n_ranks": "2", "my_var": "5.0"}
        experiment_context.chained_experiments = [
            {
                "name": "expanded_foms.test_wl.test",
                "order": "after_root",
                "command": "{execute_experiment}",
                "inherit_variables": ["my_var"],
            },
        ]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.test1" in exp_set.experiments
        assert (
            "basic.test_wl.test1.chain.0.expanded_foms.test_wl.test" in exp_set.chained_experiments
        )

        app_inst = exp_set.get_experiment("basic.test_wl.test1.chain.0.expanded_foms.test_wl.test")

        assert app_inst.variables["my_var"] == "5.0"


def test_custom_executables_track_variables(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        expanded_app_context = ramble.context.Context()
        expanded_app_context.context_name = "expanded_foms"
        expanded_app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }

        expanded_wl_context = ramble.context.Context()
        expanded_wl_context.context_name = "test_wl"
        expanded_wl_context.variables = {}

        expanded_exp_context = ramble.context.Context()
        expanded_exp_context.context_name = "test"
        expanded_exp_context.variables = {"n_ranks": "1", "my_var": "2.0"}
        expanded_exp_context.is_template = True

        exp_set.set_application_context(expanded_app_context)
        exp_set.set_workload_context(expanded_wl_context)
        exp_set.set_experiment_context(expanded_exp_context)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "test1"
        experiment_context.variables = {"n_ranks": "2", "my_var": "5.0"}
        experiment_context.chained_experiments = [
            {
                "name": "expanded_foms.test_wl.test",
                "order": "after_root",
                "command": "{execute_experiment}",
                "inherit_variables": ["my_var"],
            },
        ]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.test1" in exp_set.experiments
        assert (
            "basic.test_wl.test1.chain.0.expanded_foms.test_wl.test" in exp_set.chained_experiments
        )

        app_inst = exp_set.get_experiment("basic.test_wl.test1.chain.0.expanded_foms.test_wl.test")

        assert app_inst.variables["my_var"] == "5.0"


def test_chained_experiments(workspace_name):
    """Test that chained experiments are rendered correctly."""
    ramble.workspace.create(workspace_name)
    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)
        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "test"
        experiment_context.variables = {"n_ranks": "1", "processes_per_node": "1"}
        rendered_instances = exp_set.render_experiment_set(
            "basic", "test_wl", experiment_context, chained=True
        )

        assert len(rendered_instances) == 1
        assert "test" in exp_set.chained_experiments
        assert "basic.test_wl.test" not in exp_set.experiments


def test_repeated_experiments(workspace_name):
    """Test that repeated experiments are rendered correctly."""
    ramble.workspace.create(workspace_name)
    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)
        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "test"
        experiment_context.variables = {"n_ranks": "1", "processes_per_node": "1"}
        experiment_context.n_repeats = 2
        experiment_context.is_repeat_base = True
        exp_set.set_experiment_context(experiment_context)

        assert "basic.test_wl.test" in exp_set.experiments
        assert "basic.test_wl.test.1" in exp_set.experiments
        assert "basic.test_wl.test.2" in exp_set.experiments
        assert "basic.test_wl.test.3" not in exp_set.experiments

        base_exp = exp_set.experiments["basic.test_wl.test"]
        repeat1_exp = exp_set.experiments["basic.test_wl.test.1"]

        assert base_exp.repeats.is_repeat_base
        assert base_exp.repeats.n_repeats == 2
        assert repeat1_exp.repeats.repeat_index == 1


def test_validation_in_render_repeat_experiments(workspace_name):
    """Test that validation is called in _render_repeat_experiments."""
    ramble.workspace.create(workspace_name)
    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)
        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl2"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "test"
        experiment_context.n_repeats = 1
        experiment_context.is_repeat_base = True

        match_str = r"Invalid number of required variables defined"
        with pytest.raises(ramble.error.ObjectValidationError, match=match_str):
            exp_set.set_experiment_context(experiment_context)


def test_modifiers_no_version_set_correctly(workspace_name, mock_modifiers):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        application_context.modifiers = [
            {
                "name": "test-mod-no-version",
                "mode": "app-scope",
                "on_executable": ["builtin::env_vars"],
            }
        ]

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }
        workload_context.modifiers = [
            {
                "name": "test-mod-no-version",
                "mode": "wl-scope",
                "on_executable": ["builtin::env_vars"],
            }
        ]

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "test1"
        experiment_context.variables = {"n_ranks": "2"}
        experiment_context.modifiers = [
            {
                "name": "test-mod-no-version",
                "mode": "exp-scope",
                "on_executable": ["builtin::env_vars"],
            }
        ]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)

        assert "basic.test_wl.test1" in exp_set.experiments
        app_inst = exp_set.experiments["basic.test_wl.test1"]
        assert app_inst.modifiers is not None

        expected_modifier_modes = {"app-scope", "wl-scope", "exp-scope"}
        for mod_def in app_inst.modifiers:
            assert mod_def["mode"] in expected_modifier_modes
            expected_modifier_modes.remove(mod_def["mode"])
        assert not expected_modifier_modes


def test_dynamic_range_in_experiment_variables(workspace_name):
    workspace("create", workspace_name)

    assert workspace_name in workspace("list")

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "2",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series_{n_nodes}"
        experiment_context.variables = {
            "max_nodes": "3",
            "n_nodes": "range(1, {max_nodes})",
            "n_ranks": "{n_nodes} * 2",
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series_1" in exp_set.experiments
        assert "basic.test_wl.series_2" in exp_set.experiments
        assert len(exp_set.experiments) == 2
        assert exp_set.get_var_from_experiment("basic.test_wl.series_1", "{n_ranks}") == "2"
        assert exp_set.get_var_from_experiment("basic.test_wl.series_2", "{n_ranks}") == "4"


def test_dynamic_range_in_workload_variables(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "2",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
            "max_nodes": "4",
            "n_nodes": "range(1, {max_nodes})",
        }

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series_{n_nodes}"
        experiment_context.variables = {
            "n_ranks": "{n_nodes} * {processes_per_node}",
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series_1" in exp_set.experiments
        assert "basic.test_wl.series_2" in exp_set.experiments
        assert "basic.test_wl.series_3" in exp_set.experiments
        assert len(exp_set.experiments) == 3
        assert exp_set.get_var_from_experiment("basic.test_wl.series_1", "{n_ranks}") == "2"
        assert exp_set.get_var_from_experiment("basic.test_wl.series_3", "{n_ranks}") == "6"


def test_dynamic_range_with_exclude_where(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "2",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series_{n_nodes}"
        experiment_context.variables = {
            "max_nodes": "5",
            "n_nodes": "range(1, {max_nodes})",
            "n_ranks": "{n_nodes} * 2",
        }
        experiment_context.exclude = {"where": ["'{n_nodes}' == '2'"]}

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series_1" in exp_set.experiments
        assert "basic.test_wl.series_2" not in exp_set.experiments
        assert "basic.test_wl.series_3" in exp_set.experiments
        assert "basic.test_wl.series_4" in exp_set.experiments
        assert len(exp_set.experiments) == 3


def test_dynamic_range_with_chained_experiments(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "2",
            "mpi_command": "",
            "batch_submit": "",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }

        experiment1_context = ramble.context.Context()
        experiment1_context.context_name = "test1"
        experiment1_context.variables = {"n_ranks": "2"}

        experiment2_context = ramble.context.Context()
        experiment2_context.context_name = "series_{n_nodes}"
        experiment2_context.variables = {
            "max_nodes": "3",
            "n_nodes": "range(1, {max_nodes})",
            "n_ranks": "{n_nodes} * 2",
        }
        experiment2_context.chained_experiments = [
            {
                "name": "basic.test_wl.test1",
                "order": "after_root",
                "command": "{execute_experiment}",
                "variables": {},
            },
        ]

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment1_context)
        exp_set.set_experiment_context(experiment2_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series_1" in exp_set.experiments
        assert "basic.test_wl.series_2" in exp_set.experiments
        assert "basic.test_wl.test1" in exp_set.experiments
        assert "basic.test_wl.series_1.chain.0.basic.test_wl.test1" in exp_set.chained_experiments
        assert "basic.test_wl.series_2.chain.0.basic.test_wl.test1" in exp_set.chained_experiments


def test_dynamic_range_workspace_yaml(make_workspace_from_config):
    test_config = """
ramble:
  variables:
    mpi_command: ''
    batch_submit: ''
    processes_per_node: '1'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            exp_{n_nodes}:
              variables:
                max_nodes: '3'
                n_nodes: 'range(1, {max_nodes})'
                n_ranks: '{n_nodes} * 2'
"""
    ws, ws_name = make_workspace_from_config(test_config, activate=True)
    exp_set = ws.build_experiment_set()
    assert "basic.test_wl.exp_1" in exp_set.experiments
    assert "basic.test_wl.exp_2" in exp_set.experiments
    assert len(exp_set.experiments) == 2


def test_dynamic_range_in_application_variables(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        application_context = ramble.context.Context()
        application_context.context_name = "basic"
        application_context.variables = {
            "app_var1": "1",
            "app_var2": "2",
            "processes_per_node": "2",
            "mpi_command": "",
            "batch_submit": "",
            "min_nodes": "1",
            "max_nodes": "6",
            "stride": "2",
            "n_nodes": "range({min_nodes}, {max_nodes}, {stride})",
        }

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        workload_context.variables = {
            "wl_var1": "1",
            "wl_var2": "2",
        }

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "series_{n_nodes}"
        experiment_context.variables = {
            "n_ranks": "{n_nodes} * {processes_per_node}",
        }

        exp_set.set_application_context(application_context)
        exp_set.set_workload_context(workload_context)
        exp_set.set_experiment_context(experiment_context)
        exp_set.build_experiment_chains()

        assert "basic.test_wl.series_1" in exp_set.experiments
        assert "basic.test_wl.series_3" in exp_set.experiments
        assert "basic.test_wl.series_5" in exp_set.experiments
        assert len(exp_set.experiments) == 3
        assert exp_set.get_var_from_experiment("basic.test_wl.series_1", "{n_ranks}") == "2"
        assert exp_set.get_var_from_experiment("basic.test_wl.series_5", "{n_ranks}") == "10"


def test_dynamic_range_dry_run(make_workspace_from_config):
    test_config = """
ramble:
  variables:
    mpi_command: ''
    batch_submit: '{execute_experiment}'
    processes_per_node: '1'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            exp_{n_nodes}:
              variables:
                max_nodes: '3'
                n_nodes: 'range(1, {max_nodes})'
                n_ranks: '{n_nodes} * 2'
"""
    ws, ws_name = make_workspace_from_config(test_config, activate=True)
    workspace("setup", "--dry-run", global_args=["-w", ws_name])

    exp1_script = os.path.join(
        ws.experiment_dir, "basic", "test_wl", "exp_1", "execute_experiment"
    )
    exp2_script = os.path.join(
        ws.experiment_dir, "basic", "test_wl", "exp_2", "execute_experiment"
    )
    assert os.path.exists(exp1_script)
    assert os.path.exists(exp2_script)


def test_chained_experiment_with_dynamic_range(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "test_{n_nodes}"
        experiment_context.variables = {
            "max_nodes": "3",
            "n_nodes": "range(1, {max_nodes})",
            "n_ranks": "1",
            "processes_per_node": "1",
        }
        rendered_instances = exp_set.render_experiment_set(
            "basic", "test_wl", experiment_context, chained=True
        )

        assert len(rendered_instances) == 2
        assert "test_1" in exp_set.chained_experiments
        assert "test_2" in exp_set.chained_experiments
        assert "basic.test_wl.test_1" not in exp_set.experiments
        assert "basic.test_wl.test_2" not in exp_set.experiments


def test_dynamic_range_with_repeats(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "test_{n_nodes}"
        experiment_context.n_repeats = 2
        experiment_context.variables = {
            "max_nodes": "3",
            "n_nodes": "range(1, {max_nodes})",
            "n_ranks": "1",
        }
        rendered = exp_set.set_experiment_context(experiment_context)
        assert len(rendered) == 6
        assert "basic.test_wl.test_1" in exp_set.experiments
        assert "basic.test_wl.test_1.1" in exp_set.experiments
        assert "basic.test_wl.test_1.2" in exp_set.experiments
        assert "basic.test_wl.test_2" in exp_set.experiments
        assert "basic.test_wl.test_2.1" in exp_set.experiments
        assert "basic.test_wl.test_2.2" in exp_set.experiments


def test_dynamic_range_with_whitespace(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "test_{n_nodes}"
        experiment_context.variables = {
            "max_nodes": "3",
            "n_nodes": "range ( 1 , {max_nodes} )",
            "n_ranks": "1",
        }
        rendered = exp_set.set_experiment_context(experiment_context)
        assert len(rendered) == 2
        assert "basic.test_wl.test_1" in exp_set.experiments
        assert "basic.test_wl.test_2" in exp_set.experiments


def test_dynamic_range_with_matrix(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "sweep_{nodes}_{cores}"
        experiment_context.variables = {
            "max_nodes": "3",
            "nodes": "range(1, {max_nodes})",
            "cores": [1, 2],
            "n_ranks": "1",
        }
        experiment_context.matrices = [["nodes", "cores"]]
        rendered = exp_set.set_experiment_context(experiment_context)
        assert len(rendered) == 4
        assert "basic.test_wl.sweep_1_1" in exp_set.experiments
        assert "basic.test_wl.sweep_1_2" in exp_set.experiments
        assert "basic.test_wl.sweep_2_1" in exp_set.experiments
        assert "basic.test_wl.sweep_2_2" in exp_set.experiments


def test_dynamic_range_with_two_ranges_in_matrix(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "sweep_{nodes}_{cores}"
        experiment_context.variables = {
            "max_nodes": "3",
            "max_cores": "4",
            "nodes": "range(1, {max_nodes})",
            "cores": "range(1, {max_cores})",
            "n_ranks": "1",
        }
        experiment_context.matrices = [["nodes", "cores"]]
        rendered = exp_set.set_experiment_context(experiment_context)
        assert len(rendered) == 6
        assert "basic.test_wl.sweep_1_1" in exp_set.experiments
        assert "basic.test_wl.sweep_1_2" in exp_set.experiments
        assert "basic.test_wl.sweep_1_3" in exp_set.experiments
        assert "basic.test_wl.sweep_2_1" in exp_set.experiments
        assert "basic.test_wl.sweep_2_2" in exp_set.experiments
        assert "basic.test_wl.sweep_2_3" in exp_set.experiments


def test_dynamic_range_with_zips(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "sweep_{nodes}_{cores}"
        experiment_context.variables = {
            "max_nodes": "3",
            "nodes": "range(1, {max_nodes})",
            "cores": "range(10, 10 + {max_nodes} - 1)",
            "n_ranks": "1",
        }
        experiment_context.zips = {"my_zip": ["nodes", "cores"]}
        rendered = exp_set.set_experiment_context(experiment_context)
        assert len(rendered) == 2
        assert "basic.test_wl.sweep_1_10" in exp_set.experiments
        assert "basic.test_wl.sweep_2_11" in exp_set.experiments


def test_dynamic_range_with_static_vector_implicit_zip(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "sweep_{nodes}_{cores}"
        experiment_context.variables = {
            "max_nodes": "3",
            "nodes": "range(1, {max_nodes})",
            "cores": [10, 20],
            "n_ranks": "1",
        }
        rendered = exp_set.set_experiment_context(experiment_context)
        assert len(rendered) == 2
        assert "basic.test_wl.sweep_1_10" in exp_set.experiments
        assert "basic.test_wl.sweep_2_20" in exp_set.experiments


def test_dynamic_custom_list_function(workspace_name, monkeypatch):
    def custom_seq(start, stop):
        return list(range(start, stop))

    monkeypatch.setitem(ramble.expander.supported_list_function_pointers, "custom_seq", custom_seq)

    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "sweep_{nodes}"
        experiment_context.variables = {
            "max_nodes": "4",
            "nodes": "custom_seq(1, {max_nodes})",
            "n_ranks": "1",
        }
        rendered = exp_set.set_experiment_context(experiment_context)
        assert len(rendered) == 3
        assert "basic.test_wl.sweep_1" in exp_set.experiments
        assert "basic.test_wl.sweep_2" in exp_set.experiments
        assert "basic.test_wl.sweep_3" in exp_set.experiments


def test_dynamic_pow2_range_in_experiment_set(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "sweep_{nodes}"
        experiment_context.variables = {
            "max_nodes": "16",
            "nodes": "pow2_range(1, {max_nodes})",
            "n_ranks": "1",
        }
        rendered = exp_set.set_experiment_context(experiment_context)
        assert len(rendered) == 5
        assert "basic.test_wl.sweep_1" in exp_set.experiments
        assert "basic.test_wl.sweep_2" in exp_set.experiments
        assert "basic.test_wl.sweep_4" in exp_set.experiments
        assert "basic.test_wl.sweep_8" in exp_set.experiments
        assert "basic.test_wl.sweep_16" in exp_set.experiments


def test_dynamic_range_dependent_on_vector(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "sweep_{max_nodes}_{nodes}"
        experiment_context.variables = {
            "max_nodes": [2, 4],
            "nodes": "range(1, {max_nodes} + 1)",
            "n_ranks": "1",
        }
        rendered = exp_set.set_experiment_context(experiment_context)
        assert len(rendered) == 6
        assert "basic.test_wl.sweep_2_1" in exp_set.experiments
        assert "basic.test_wl.sweep_2_2" in exp_set.experiments
        assert "basic.test_wl.sweep_4_1" in exp_set.experiments
        assert "basic.test_wl.sweep_4_2" in exp_set.experiments
        assert "basic.test_wl.sweep_4_3" in exp_set.experiments
        assert "basic.test_wl.sweep_4_4" in exp_set.experiments


def test_dynamic_range_dependent_on_vector_with_matrix(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "sweep_{max_nodes}_{nodes}"
        experiment_context.variables = {
            "max_nodes": [2, 4],
            "nodes": "range(1, {max_nodes} + 1)",
            "n_ranks": "1",
        }
        experiment_context.matrices = [["max_nodes", "nodes"]]
        rendered = exp_set.set_experiment_context(experiment_context)
        assert len(rendered) == 6
        assert "basic.test_wl.sweep_2_1" in exp_set.experiments
        assert "basic.test_wl.sweep_2_2" in exp_set.experiments
        assert "basic.test_wl.sweep_4_1" in exp_set.experiments
        assert "basic.test_wl.sweep_4_2" in exp_set.experiments
        assert "basic.test_wl.sweep_4_3" in exp_set.experiments
        assert "basic.test_wl.sweep_4_4" in exp_set.experiments


def test_dynamic_pow2_range_dependent_on_vector(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "sweep_{max_nodes}_{nodes}"
        experiment_context.variables = {
            "max_nodes": [4, 8],
            "nodes": "pow2_range(1, {max_nodes})",
            "n_ranks": "1",
        }
        rendered = exp_set.set_experiment_context(experiment_context)
        assert len(rendered) == 7
        assert "basic.test_wl.sweep_4_1" in exp_set.experiments
        assert "basic.test_wl.sweep_4_2" in exp_set.experiments
        assert "basic.test_wl.sweep_4_4" in exp_set.experiments
        assert "basic.test_wl.sweep_8_1" in exp_set.experiments
        assert "basic.test_wl.sweep_8_2" in exp_set.experiments
        assert "basic.test_wl.sweep_8_4" in exp_set.experiments
        assert "basic.test_wl.sweep_8_8" in exp_set.experiments


def test_chained_multi_level_dependent_ranges(workspace_name):
    workspace("create", workspace_name)

    with ramble.workspace.read(workspace_name) as ws:
        exp_set = ramble.experiment_set.ExperimentSet(ws)

        app_context = ramble.context.Context()
        app_context.context_name = "basic"
        app_context.variables = {
            "processes_per_node": "1",
            "mpi_command": "",
            "batch_submit": "",
        }
        exp_set.set_application_context(app_context)

        workload_context = ramble.context.Context()
        workload_context.context_name = "test_wl"
        exp_set.set_workload_context(workload_context)

        experiment_context = ramble.context.Context()
        experiment_context.context_name = "sweep_{foo}_{bar}_{baz}"
        experiment_context.variables = {
            "foo": [1, 2, 4],
            "bar": "range(1, {foo} + 1)",
            "baz": "range(1, {bar} + 1)",
            "n_ranks": "1",
        }
        rendered = exp_set.set_experiment_context(experiment_context)
        assert len(rendered) == 14
        assert "basic.test_wl.sweep_1_1_1" in exp_set.experiments
        assert "basic.test_wl.sweep_2_1_1" in exp_set.experiments
        assert "basic.test_wl.sweep_2_2_1" in exp_set.experiments
        assert "basic.test_wl.sweep_2_2_2" in exp_set.experiments
        assert "basic.test_wl.sweep_4_1_1" in exp_set.experiments
        assert "basic.test_wl.sweep_4_2_1" in exp_set.experiments
        assert "basic.test_wl.sweep_4_2_2" in exp_set.experiments
        assert "basic.test_wl.sweep_4_3_1" in exp_set.experiments
        assert "basic.test_wl.sweep_4_3_2" in exp_set.experiments
        assert "basic.test_wl.sweep_4_3_3" in exp_set.experiments
        assert "basic.test_wl.sweep_4_4_1" in exp_set.experiments
        assert "basic.test_wl.sweep_4_4_2" in exp_set.experiments
        assert "basic.test_wl.sweep_4_4_3" in exp_set.experiments
        assert "basic.test_wl.sweep_4_4_4" in exp_set.experiments


def test_dynamic_range_indirect_vector_dependency_with_mpi_matrix(make_workspace_from_config):
    test_config = """
ramble:
  variables:
    processes_per_node: 4
    mpi_command: 'mpirun -n {n_ranks}'
    batch_submit: '{execute_experiment}'
    vm_family: [h4d]
    mpi_provider: [tcp, rxm]
    Alltoall_info:
      max_algo: 4
    Alltoallv_info:
      max_algo: 2
  applications:
    basic:
      workloads:
        test_wl2:
          experiments:
            '{vm_family}-{mpi_provider}-{n_nodes}node-{collective_type}-{algo_setting}':
              variables:
                n_nodes: [16, 32]
                max_algo: '{collective_type}_info["max_algo"]'
                algo_setting: 'range(1, {max_algo})'
                n_ranks: '{processes_per_node}*{n_nodes}'
                collective_type: [Alltoall, Alltoallv]
              matrix:
              - n_nodes
              - algo_setting
              - collective_type
              - vm_family
              - mpi_provider
              exclude:
                where:
                - '{algo_setting} > {max_algo}'
"""
    ws, _ = make_workspace_from_config(test_config, activate=True)
    exp_set = ws.build_experiment_set()
    # Alltoall has range(1, 4) -> [1, 2, 3] (3 algos) * 2 n_nodes * 1 vm_family * 2 mpi = 12
    # Alltoallv has range(1, 2) -> [1] (1 algo) * 2 n_nodes * 1 vm_family * 2 mpi = 4
    # Total = 16 experiments
    assert len(exp_set.experiments) == 16
    assert "basic.test_wl2.h4d-tcp-16node-Alltoall-1" in exp_set.experiments
    assert "basic.test_wl2.h4d-rxm-32node-Alltoall-3" in exp_set.experiments
    assert "basic.test_wl2.h4d-tcp-16node-Alltoallv-1" in exp_set.experiments
    assert "basic.test_wl2.h4d-tcp-16node-Alltoallv-2" not in exp_set.experiments


def test_dynamic_range_on_n_nodes_mpi(make_workspace_from_config):
    test_config = """
ramble:
  variables:
    processes_per_node: 4
    mpi_command: 'mpirun -n {n_ranks}'
    batch_submit: '{execute_experiment}'
  applications:
    basic:
      workloads:
        test_wl2:
          experiments:
            node_sweep_{n_nodes}:
              variables:
                max_nodes: 4
                n_nodes: 'range(1, {max_nodes})'
"""
    ws, _ = make_workspace_from_config(test_config, activate=True)
    exp_set = ws.build_experiment_set()
    assert len(exp_set.experiments) == 3
    assert exp_set.experiments["basic.test_wl2.node_sweep_1"].variables["n_ranks"] == "4"
    assert exp_set.experiments["basic.test_wl2.node_sweep_2"].variables["n_ranks"] == "8"
    assert exp_set.experiments["basic.test_wl2.node_sweep_3"].variables["n_ranks"] == "12"
