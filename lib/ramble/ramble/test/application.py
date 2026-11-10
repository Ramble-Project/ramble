# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
"""Perform tests of the Application class"""

import unittest
from typing import FrozenSet
from unittest.mock import Mock

import pytest

import ramble.definitions.variables
import ramble.paths
import ramble.repository
import ramble.workload
import ramble.workspace
from ramble.keywords import Keywords

pytestmark = pytest.mark.usefixtures(
    "mutable_config", "mutable_mock_workspace_path", "mutable_mock_apps_repo"
)

_FS: FrozenSet[str] = frozenset()


def basic_exp_dict():
    """To set expander consistently with test_wl2 of builtin.mock/applications/basic"""
    return {
        "application_name": "bar",
        "inputs": {"test_wl": "input", "test_wl2": "input"},
        "workload_name": "test_wl2",
        "experiment_name": "baz",
        "application_input_dir": "/workspace/inputs/bar",
        "workload_input_dir": "/workspace/inputs/bar/test_wl2",
        "application_run_dir": "/workspace/experiments/bar",
        "workload_run_dir": "/workspace/experiments/bar/test_wl2",
        "experiment_run_dir": "/workspace/experiments/bar/test_wl2/baz",
        "env_name": "spack_bar.test_wl2",
        "n_ranks": "4",
        "processes_per_node": "2",
        "n_nodes": "2",
        "var1": "{var2}",
        "var2": "{var3}",
        "var3": "3",
        "mpi_command": "mpirun -n {n_ranks}",
        "batch_command": "sbatch -p {partition} {execute_experiment}",
    }


@pytest.mark.parametrize(
    "app", ["basic", "basic-inherited", "input-test", "interleved-env-vars", "register-builtin"]
)
def test_app_features(mutable_mock_apps_repo, app):
    app_inst = mutable_mock_apps_repo.get(app)

    assert hasattr(app_inst, "workloads")
    assert hasattr(app_inst, "workload_groups")
    assert hasattr(app_inst, "executables")
    assert hasattr(app_inst, "figures_of_merit")
    assert hasattr(app_inst, "inputs")
    assert hasattr(app_inst, "compilers")
    assert hasattr(app_inst, "software_specs")
    assert hasattr(app_inst, "required_packages")
    assert hasattr(app_inst, "builtins")


def test_basic_app(mutable_mock_apps_repo):
    basic_inst = mutable_mock_apps_repo.get("basic")
    exp_dict = basic_exp_dict()
    basic_inst.set_variables_and_variants(exp_dict, {}, None, None)
    basic_inst.define_variable("application_name", "basic")

    assert "test_wl" in basic_inst.workloads[_FS]
    assert len(basic_inst.workloads[_FS]["test_wl"].executables) == 1
    foo_exec = basic_inst.workloads[_FS]["test_wl"].find_executable("foo")
    assert foo_exec is not None
    foo_exec = basic_inst.executables[_FS][foo_exec]
    assert foo_exec.template == ["bar"]
    assert not foo_exec.mpi

    assert len(basic_inst.workloads[_FS]["test_wl"].inputs) == 1
    example_input = basic_inst.workloads[_FS]["test_wl"].find_input("input")
    assert example_input is not None

    assert len(basic_inst.workloads[_FS]["test_wl"].variables[_FS]) == 7
    possible_vars = basic_inst.workloads[_FS]["test_wl"].find_variable("my_var")
    assert len(possible_vars) == 1
    assert possible_vars[0].default == "1.0"
    assert possible_vars[0].description == "Example var"

    assert "test_wl2" in basic_inst.workloads[_FS]
    assert len(basic_inst.workloads[_FS]["test_wl2"].executables) == 1
    bar_exec = basic_inst.workloads[_FS]["test_wl2"].find_executable("bar")
    assert bar_exec is not None
    bar_exec = basic_inst.executables[_FS][bar_exec]
    assert bar_exec.template == ["baz"]
    assert bar_exec.mpi

    assert len(basic_inst.workloads[_FS]["test_wl2"].inputs) == 1
    example_input = basic_inst.workloads[_FS]["test_wl2"].find_input("input")
    assert example_input is not None

    basic_inst.define_variable("workload_name", "test_wl")
    exec_graph = basic_inst.get_executable_graph("test_wl")
    assert exec_graph.get_node("foo") is not None
    assert exec_graph.get_node("builtin::env_vars") is not None

    basic_inst.define_variable("workload_name", "test_wl2")
    exec_graph = basic_inst.get_executable_graph("test_wl2")
    assert exec_graph.get_node("bar") is not None
    assert exec_graph.get_node("builtin::env_vars") is not None

    assert "test_fom" in basic_inst.figures_of_merit[_FS][_FS]
    fom_conf = basic_inst.figures_of_merit[_FS][_FS]["test_fom"]
    assert fom_conf["log_file"] == "{log_file}"
    assert fom_conf["regex"] == r"(?P<test>[0-9]+\.[0-9]+).*seconds.*"
    assert fom_conf["group_name"] == "test"
    assert fom_conf["units"] == "s"

    assert "input" in basic_inst.inputs[_FS]
    assert basic_inst.inputs[_FS]["input"]["url"] == "file:///tmp/test_file.log"
    assert basic_inst.inputs[_FS]["input"]["description"] == "Not a file"


@pytest.mark.parametrize(
    "app_name,wl_name",
    [
        ("basic", "test_wl2"),
        ("zlib", "ensure_installed"),
    ],
)
def test_application_copy_is_deep(app_name, wl_name, mutable_mock_apps_repo):
    src_inst = mutable_mock_apps_repo.get(app_name)

    defined_variables = {
        "n_nodes": "1",
        "n_ranks": "{processes_per_node}*{n_nodes}",
        "processes_per_node": "1",
        "test_var1": "test_val1",
        "test_var2": "test_val2",
        "workload_name": wl_name,
    }

    defined_env_vars = [
        {
            "set": {"SET_ENV_VAR": "TEST"},
            "unset": ["UNSET_ENV_VAR"],
            "append": [{"var-separator": ",", "vars": {"APPEND_VAR": "APPEND_TEST"}}],
            "prepend": [{"var-separator": ",", "vars": {"PREPEND_VAR": "PREPEND_TEST"}}],
        }
    ]

    defined_internals = {
        "custom_executables": {
            "test_exec": {"template": ["test_exec"], "use_mpi": False, "redirect": "{log_file}"}
        }
    }

    src_inst.set_variables_and_variants(defined_variables, {}, None, None)
    src_inst.set_env_variable_sets(defined_env_vars)
    src_inst.set_internals(defined_internals)

    clone_inst = src_inst.clone()

    # Test variables
    for var, val in src_inst.variables.items():
        assert var in clone_inst.variables
        assert clone_inst.variables[var] == val

    # Test env-vars
    def _compare_env_var_groups(src_group, clone_group):
        for var_set in src_group:
            assert var_set in clone_group
            # Test set sets
            if var_set == "set":
                for var, val in src_group[var_set].items():
                    assert var in clone_group[var_set]
                    assert clone_group[var_set][var] == val
            elif var_set == "append" or var_set == "prepend":
                for idx, set_group in enumerate(src_group[var_set]):
                    if "var-separator" in set_group:
                        assert "var-separator" in clone_group[var_set][idx]
                        assert (
                            clone_group[var_set][idx]["var-separator"]
                            == set_group["var-separator"]
                        )
                    if "vars" in set_group:
                        assert "vars" in clone_group[var_set][idx]
                        for var, val in set_group["vars"].items():
                            assert var in clone_group[var_set][idx]["vars"]
                            assert clone_group[var_set][idx]["vars"][var] == val
            elif var_set == "unset":
                for var in src_group[var_set]:
                    assert var in clone_group[var_set]

    for src_group, clone_group in zip(src_inst._env_variable_sets, clone_inst._env_variable_sets):
        _compare_env_var_groups(src_group, clone_group)

    # Test internals:
    for internal, conf in src_inst.internals.items():
        assert internal in clone_inst.internals
        if internal == "custom_executables":
            for exec_name, exec_conf in conf.items():
                assert exec_name in clone_inst.internals[internal]
                for option, value in exec_conf.items():
                    assert option in clone_inst.internals[internal][exec_name]
                    assert clone_inst.internals[internal][exec_name][option] == value


@pytest.mark.parametrize(
    "app", ["basic", "basic-inherited", "input-test", "interleved-env-vars", "register-builtin"]
)
def test_required_builtins(mutable_mock_apps_repo, app):
    app_inst = mutable_mock_apps_repo.get(app)
    exp_dict = basic_exp_dict()
    app_inst.set_variables_and_variants(exp_dict, {}, None, None)
    app_inst.define_variable("application_name", app)

    required_builtins = []
    for builtin, conf in app_inst.builtins[_FS].items():
        if conf[app_inst._builtin_required_key]:
            required_builtins.append(builtin)

    for workload in app_inst.workloads[_FS]:
        app_inst.define_variable("workload_name", workload)
        exec_graph = app_inst.get_executable_graph(workload)
        for builtin in required_builtins:
            assert exec_graph.get_node(builtin) is not None


def test_register_builtin_app(mutable_mock_apps_repo):
    app_inst = mutable_mock_apps_repo.get("register-builtin")
    exp_dict = basic_exp_dict()
    app_inst.set_variables_and_variants(exp_dict, {}, None, None)
    app_inst.define_variable("application_name", "register-builtin")

    required_builtins = []
    excluded_builtins = []
    for builtin, conf in app_inst.builtins[_FS].items():
        if conf[app_inst._builtin_required_key]:
            required_builtins.append(builtin)
        else:
            excluded_builtins.append(builtin)

    for workload in app_inst.workloads[_FS]:
        exec_graph = app_inst.get_executable_graph(workload)
        app_inst.define_variable("workload_name", workload)

        for builtin in required_builtins:
            assert exec_graph.get_node(builtin) is not None
        for builtin in excluded_builtins:
            assert exec_graph.get_node(builtin) is None

        # Test for dependency injection
        found_prerequisite = False
        for node in exec_graph.walk():
            if node.key == "builtin::test_builtin":
                break
            if node.key == "builtin::test_builtin_pre":
                found_prerequisite = True
        assert found_prerequisite


@pytest.mark.parametrize(
    "app", ["basic", "basic-inherited", "input-test", "interleved-env-vars", "register-builtin"]
)
def test_short_print(mutable_mock_apps_repo, app):
    app_inst = mutable_mock_apps_repo.get(app)
    app_inst._verbosity = "short"

    str_val = str(app_inst)

    assert str_val == app


def test_get_executable_graph_initial(mutable_mock_apps_repo):
    """_get_executable_graph, test1, workload executables"""

    executable_application_instance = mutable_mock_apps_repo.get("basic")

    expansion_vars = basic_exp_dict()

    # Set up the instance to test just the initial part of the function
    executable_application_instance.expander = ramble.expander.Expander(expansion_vars, None)
    test_wl = ramble.workload.Workload("test_wl", executables=["foo"], inputs=["input"])
    test_wl2 = ramble.workload.Workload("test_wl2", executables=["bar"], inputs=["input"])
    executable_application_instance.workloads[_FS] = {"test_wl": test_wl, "test_wl2": test_wl2}
    executable_application_instance.internals = {}

    executable_graph = executable_application_instance.get_executable_graph("test_wl2")
    bar_node = executable_graph.get_node("bar")

    assert bar_node is not None


def test_get_executable_graph_yaml_defined(mutable_mock_apps_repo):
    """_get_executable_graph, test2, yaml-defined order"""

    executable_application_instance = mutable_mock_apps_repo.get("basic")

    expansion_vars = basic_exp_dict()

    # Set up the instance to pass the initial part of the function
    executable_application_instance.expander = ramble.expander.Expander(expansion_vars, None)
    test_wl = ramble.workload.Workload("test_wl", executables=["foo"], inputs=["input"])
    test_wl2 = ramble.workload.Workload("test_wl2", executables=["bar"], inputs=["input"])
    executable_application_instance.workloads[_FS] = {"test_wl": test_wl, "test_wl2": test_wl2}

    # Insert namespace.executables into the instance's internals to pass the
    # second part of the function
    defined_internals = {
        "custom_executables": {
            "test_exec": {"template": ["test_exec"], "use_mpi": False, "redirect": "{log_file}"}
        },
        "executables": ["bar", "test_exec"],
    }
    executable_application_instance.set_internals(defined_internals)

    executable_graph = executable_application_instance.get_executable_graph("test_wl")

    test_node = executable_graph.get_node("test_exec")

    assert test_node is not None


def test_get_executable_graph_custom_executables(mutable_mock_apps_repo):
    """_get_executable_graph, test3, custom executables"""

    executable_application_instance = mutable_mock_apps_repo.get("basic")

    expansion_vars = basic_exp_dict()

    # Set up the instance to pass the initial part of the function
    executable_application_instance.expander = ramble.expander.Expander(expansion_vars, None)
    test_wl = ramble.workload.Workload("test_wl", executables=["foo"], inputs=["input"])
    test_wl2 = ramble.workload.Workload("test_wl2", executables=["bar"], inputs=["input"])
    executable_application_instance.workloads[_FS] = {"test_wl": test_wl, "test_wl2": test_wl2}

    # Insert namespace.executables into the instance's internals to pass the
    # second part of the function
    defined_internals = {
        "custom_executables": {
            "test_exec2": {
                "template": ["test_exec2"],
                "use_mpi": False,
                "redirect": "{log_file}",
            }
        },
        "executables": ["test_exec2", "bar"],
    }
    executable_application_instance.set_internals(defined_internals)

    executable_graph = executable_application_instance.get_executable_graph("test_wl2")
    test_node = executable_graph.get_node("test_exec2")

    assert test_node is not None


def test_set_input_path(mutable_mock_apps_repo):
    """_set_input_path"""

    executable_application_instance = mutable_mock_apps_repo.get("basic")

    expansion_vars = basic_exp_dict()

    # Set up the instance to pass the initial part of the function
    executable_application_instance.expander = ramble.expander.Expander(expansion_vars, None)

    executable_application_instance.internals = {}

    executable_application_instance.variables = {}

    executable_application_instance._set_input_path()

    default_answer = "/workspace/inputs/bar/test_wl2/test_file.log"

    assert executable_application_instance.variables["input"] == default_answer


def test_set_input_path_multi_input(mutable_mock_apps_repo):
    """Tests set_input_path with multiple inputs in a given workload"""

    executable_application_instance = mutable_mock_apps_repo.get("input-test")

    expansion_vars = basic_exp_dict()
    del expansion_vars["inputs"]
    expansion_vars["application_name"] = "input-test"
    expansion_vars["workload_name"] = "test"

    # Set up the instance to pass the initial part of the function
    executable_application_instance.expander = ramble.expander.Expander(expansion_vars, None)

    executable_application_instance.internals = {}

    executable_application_instance.variables = {}

    executable_application_instance._set_input_path()

    input1_path = "/workspace/inputs/bar/test_wl2/input1"
    input2_path = "/workspace/inputs/bar/test_wl2/input2"
    input3_path = "/workspace/inputs/bar/test_wl2/input3.txt"

    assert executable_application_instance.variables["test-input1"] == input1_path
    assert executable_application_instance.variables["test-input2"] == input2_path
    assert executable_application_instance.variables["test-input3"] == input3_path


def test_set_variables_and_variants(mutable_mock_apps_repo):
    """Test that set_variables defines workload variables"""

    executable_application_instance = mutable_mock_apps_repo.get("basic")

    expansion_vars = basic_exp_dict()
    del expansion_vars["n_ranks"]

    experiment_variants = {
        "workflow_manager": "slurm",
        "foo": "bar",
    }

    # Set up the instance to pass the initial part of the function

    test_wl = ramble.workload.Workload("test_wl", executables=["foo"], inputs=["input"])
    test_wl2 = ramble.workload.Workload("test_wl2", executables=["bar"], inputs=["input"])
    test_wl2.add_variable(ramble.definitions.variables.Variable("n_ranks", default="1"))
    executable_application_instance.workloads[_FS] = {"test_wl": test_wl, "test_wl2": test_wl2}

    executable_application_instance.internals = {}

    executable_application_instance.inputs[_FS] = {"input": {"target_dir": "."}}

    executable_application_instance.set_variables_and_variants(
        expansion_vars, experiment_variants, None, None
    )

    assert executable_application_instance.variables["n_ranks"] == "1"

    variant_set = executable_application_instance.experiment_variants().as_set()
    assert "workflow_manager=slurm" in variant_set
    assert "package_manager=spack" not in variant_set


def test_define_commands(mutable_mock_apps_repo):
    """test _define_commands"""

    executable_application_instance = mutable_mock_apps_repo.get("basic")

    expansion_vars = basic_exp_dict()

    test_wl = ramble.workload.Workload("test_wl", executables=["foo"], inputs=["input"])
    test_wl2 = ramble.workload.Workload("test_wl2", executables=["bar"], inputs=["input"])
    test_wl2.add_variable(ramble.definitions.variables.Variable("n_ranks", default="1"))
    executable_application_instance.workloads[_FS] = {"test_wl": test_wl, "test_wl2": test_wl2}

    executable_application_instance.internals = {}

    executable_application_instance.inputs[_FS] = {"input": {"target_dir": "."}}
    executable_application_instance.set_variables_and_variants(expansion_vars, {}, None, None)

    exec_graph = executable_application_instance.get_executable_graph("test_wl2")

    executable_application_instance.set_formatted_executables(
        {"command": {"join_separator": "\n"}}
    )

    executable_application_instance.chain_prepend = []
    executable_application_instance._define_commands(exec_graph)
    executable_application_instance._define_formatted_executables()
    assert "mpirun" in executable_application_instance.variables["command"]


def test_define_variables_for_template_path(mutable_mock_apps_repo, workspace_name):
    """_set_default_variables_for_template_path"""
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment:
              template: true
              variables:
                n_nodes: '2'
        test_wl2:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'

  software:
    packages: {}
    environments: {}
"""
    import os.path

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    executable_application_instance = mutable_mock_apps_repo.get("basic")

    expansion_vars = basic_exp_dict()

    test_wl = ramble.workload.Workload("test_wl", executables=["foo"], inputs=["input"])
    test_wl2 = ramble.workload.Workload("test_wl2", executables=["bar"], inputs=["input"])
    test_wl2.add_variable(ramble.definitions.variables.Variable("n_ranks", default="1"))
    executable_application_instance.workloads[_FS] = {"test_wl": test_wl, "test_wl2": test_wl2}

    executable_application_instance.internals = {}

    executable_application_instance.inputs[_FS] = {"input": {"target_dir": "."}}
    executable_application_instance.set_variables_and_variants(expansion_vars, {}, None, None)

    exec_graph = executable_application_instance.get_executable_graph("test_wl2")

    executable_application_instance.chain_prepend = []
    executable_application_instance._define_commands(exec_graph)
    executable_application_instance._define_formatted_executables()

    test_answer = "/workspace/experiments/bar/test_wl2/baz/execute_experiment"
    executable_application_instance.workspace = ws1
    executable_application_instance.define_variables_for_template_path()
    assert executable_application_instance.variables["execute_experiment"] == test_answer

    # Also test
    executable_application_instance.variables.clear()
    executable_application_instance._template_paths_defined = False
    executable_application_instance.set_variables_and_variants(expansion_vars, {}, ws1, None)
    executable_application_instance._define_commands(exec_graph)
    executable_application_instance._define_formatted_executables()
    executable_application_instance.define_variables_for_template_path()
    assert executable_application_instance.variables["execute_experiment"] == test_answer


def test_class_attributes(mutable_mock_apps_repo):
    basic_inst = mutable_mock_apps_repo.get("basic")
    basic_inst.variables = {
        "n_nodes": "1",
        "n_ranks": "{processes_per_node}*{n_nodes}",
        "processes_per_node": "1",
        "workload_name": "test_wl",
    }
    basic_clone = basic_inst.clone()

    instances = [basic_inst, basic_clone]
    for inst in instances:
        assert hasattr(inst, "workloads")
        assert "test_wl" in inst.workloads[_FS]

    basic_clone.workload("added_workload", executables=["foo"])

    assert "added_workload" in basic_clone.workloads[_FS]
    assert "added_workload" not in basic_inst.workloads[_FS]


def test_workload_groups(mutable_mock_apps_repo):
    workload_group_inst = mutable_mock_apps_repo.get("workload-groups")

    assert "test_wl" in workload_group_inst.workloads[_FS]

    assert "empty" in workload_group_inst.workload_groups
    assert "test_wlg" in workload_group_inst.workload_groups

    possible_vars = workload_group_inst.workloads[_FS]["test_wl"].find_variable("test_var")
    assert len(possible_vars) >= 1
    found = False
    for var in possible_vars:
        if var.default == "2.0" and var.description == "Test workload vars and groups":
            found = True
    assert found

    possible_vars = workload_group_inst.workloads[_FS]["test_wl"].find_variable("test_var_mixed")
    assert len(possible_vars) >= 1
    found = False
    for var in possible_vars:
        if var.default == "3.0" and var.description == "Test vars for workload and groups":
            found = True
    assert found


def test_workload_groups_inherited(mutable_mock_apps_repo):
    wlgi_inst = mutable_mock_apps_repo.get("workload-groups-inherited")

    assert "test_wl" in wlgi_inst.workloads[_FS]
    assert "test_wl3" in wlgi_inst.workloads[_FS]

    # check we inherit groups we don't touch
    assert "empty" in wlgi_inst.workload_groups
    assert "test_wlg" in wlgi_inst.workload_groups

    assert "test_wl" in wlgi_inst.workload_groups["test_wlg"].name

    # Ensure a new workload can obtain the parent level vars via groups
    possible_vars = wlgi_inst.workloads[_FS]["test_wl3"].find_variable("test_var")
    assert len(possible_vars) >= 1
    found = False
    for var in possible_vars:
        if var.default == "2.0" and var.description == "Test workload vars and groups":
            found = True
    assert found

    for wl in ["test_wl", "test_wl3"]:
        possible_vars = wlgi_inst.workloads[_FS][wl].find_variable("test_var_mixed")
        assert len(possible_vars) >= 1
        found = False
        for var in possible_vars:
            if var.default == "3.0":
                found = True
        assert found


def test_undefined_executable_dies(mutable_mock_apps_repo, capsys):
    """Test that an undefined executable causes a fatal error."""
    executable_application_instance = mutable_mock_apps_repo.get("basic")
    expansion_vars = basic_exp_dict()
    executable_application_instance.expander = ramble.expander.Expander(expansion_vars, None)
    # Create a workload with an executable that is not defined
    undefined_exec_wl = ramble.workload.Workload(
        "wl_with_undefined_exec", executables=["undefined_exec"]
    )
    executable_application_instance.workloads[_FS]["wl_with_undefined_exec"] = undefined_exec_wl

    with pytest.raises(SystemExit):
        executable_application_instance.get_executable_graph("wl_with_undefined_exec")
    captured = capsys.readouterr()
    assert "Executable undefined_exec is not defined." in captured.err


def test_application_methods_with_default_workspace(mutable_mock_apps_repo, workspace_name):
    """Verify ApplicationBase methods fallback to self.workspace when workspace=None"""
    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    executable_application_instance = mutable_mock_apps_repo.get("basic")
    expansion_vars = basic_exp_dict()

    test_wl2 = ramble.workload.Workload("test_wl2", executables=["foo"], inputs=["input"])
    executable_application_instance.workloads[_FS] = {"test_wl2": test_wl2}
    executable_application_instance.internals = {}
    executable_application_instance.inputs[_FS] = {"input": {"target_dir": "."}}
    executable_application_instance.chain_prepend = []
    from ramble.success_criteria import ScopedCriteriaList

    executable_application_instance.success_list = ScopedCriteriaList()

    # Call set_variables_and_variants passing ws1
    executable_application_instance.set_variables_and_variants(expansion_vars, {}, ws1, None)

    # Test define_missing_variables
    executable_application_instance.define_missing_variables()

    # Test set_modifiers
    executable_application_instance.set_modifiers(None)

    # Test get_pipeline_phases
    phases = executable_application_instance.get_pipeline_phases("analyze")
    assert isinstance(list(phases), list)

    # Test build_used_variables
    used_vars = executable_application_instance.build_used_variables()
    assert isinstance(used_vars, set)

    # Test print_phase_times
    executable_application_instance.print_phase_times("analyze")

    # Test create_experiment_chain
    executable_application_instance.create_experiment_chain()

    # Test build_modifier_instances
    executable_application_instance.build_modifier_instances()

    # Test object_inventory
    inventory = executable_application_instance.object_inventory()
    assert isinstance(inventory, list)

    # Test define_variables_for_template_path
    executable_application_instance.define_variables_for_template_path()


class TestApplicationBase(unittest.TestCase):
    def test_non_reserved_variables(self):
        obj_type = ramble.repository.ObjectTypes.base_classes
        repo = ramble.repository.Repo(ramble.paths.builtin_path, obj_type)

        with ramble.repository.use_repositories(repo, object_type=obj_type):
            ApplicationBase = ramble.repository.get_base_class("application-base")

            # Instantiate the class, bypassing the __init__ method
            app_base = ApplicationBase.__new__(ApplicationBase)

            # Set the required attributes
            app_base.keywords = Keywords()
            app_base.variables = {
                "regular_variable": "value1",
                # A reserved variable
                "workspace_name": "value2",
                # A variable that matches a reserved pattern
                "application::name::version": "value3",
                # A variable that matches a reserved pattern
                "modifier_version": "value4",
            }
            app_base.package_manager = None
            app_base.workflow_manager = None

            # This is needed by _get_object_templates
            app_base._modifier_instances = []
            app_base.expander = Mock()
            app_base.expander.satisfies.return_value = True
            app_base.templates = {}

            # Mock the workspace
            mock_workspace = Mock()
            mock_workspace.all_templates.return_value = []
            app_base.workspace = mock_workspace

            # Call the method to be tested
            non_reserved = app_base.non_reserved_variables()

            # Assert the result
            self.assertIn("regular_variable", non_reserved)
            self.assertNotIn("workspace_name", non_reserved)
            self.assertNotIn("application::name::version", non_reserved)
            self.assertNotIn("modifier_version", non_reserved)
            self.assertEqual(len(non_reserved), 1)


@pytest.mark.parametrize(
    "n_nodes,mpi_cmd,expect_warning",
    [
        ("2", "", True),
        ("1", "", False),
        ("2", "mpirun -n {n_ranks}", False),
    ],
)
def test_multi_node_mpi_command_warning(
    make_workspace_from_config, mutable_mock_apps_repo, n_nodes, mpi_cmd, expect_warning
):
    workspace = ramble.main.RambleCommand("workspace")

    test_config = f"""
ramble:
  variables:
    mpi_command: '{mpi_cmd}'
    batch_submit: '{{execute_experiment}}'
    processes_per_node: 1
    n_nodes: {n_nodes}
  applications:
    basic:
      workloads:
        test_wl2:
          experiments:
            test_exp: {{}}
"""
    ws, _ = make_workspace_from_config(test_config)
    out = workspace("setup", "--dry-run", global_args=["-D", ws.root])

    expected_msg = (
        "Command bar requires a non-empty `mpi_command` variable in a multi-node experiment"
    )
    warning_present = expected_msg in out
    assert warning_present == expect_warning


def test_custom_workloads(mutable_mock_apps_repo):
    app_inst = mutable_mock_apps_repo.get("basic")
    expansion_vars = basic_exp_dict()
    app_inst.expander = ramble.expander.Expander(expansion_vars, None)

    existing_wl = ramble.workload.Workload(
        "test_wl", executables=["foo"], inputs=["input"], tags=["orig_tag"]
    )
    app_inst.workloads[_FS] = {"test_wl": existing_wl}

    app_inst.set_internals(
        {
            "custom_workloads": {
                "test_wl": {
                    "executables": "bar",
                    "inputs": None,
                },
                "new_wl": {
                    "executables": ["foo", "bar"],
                    "tags": ["tag1", 2],
                },
            }
        }
    )

    wl1 = app_inst.workloads[_FS]["test_wl"]
    assert wl1.executables == ["bar"]
    assert wl1.inputs == []
    assert wl1.tags == ["orig_tag"]

    wl2 = app_inst.workloads[_FS]["new_wl"]
    assert wl2.executables == ["foo", "bar"]
    assert wl2.inputs == []
    assert wl2.tags == ["tag1", "2"]

    app_inst.experiment_tags = ["tag1", "2"]
    assert app_inst.has_tags(["tag1"])
