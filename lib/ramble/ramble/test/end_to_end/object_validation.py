# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.error
import ramble.workspace
from ramble.main import RambleCommand

pytestmark = pytest.mark.usefixtures(
    "mutable_config", "mutable_mock_workspace_path", "mock_applications"
)

workspace = RambleCommand("workspace")


def test_object_validation(workspace_name):
    global_args = ["-w", workspace_name]

    ws = ramble.workspace.create(workspace_name)
    workspace(
        "manage",
        "experiments",
        "validation",
        "-v",
        "n_nodes=3",
        "-v",
        "processes_per_node=1",
        "-v",
        "batch_submit={execute_experiment}",
        "--wf",
        "test_validation",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    ws._re_read()
    with pytest.raises(
        ramble.error.ObjectValidationError, match="should run with even number of processes"
    ):
        workspace("setup", global_args=global_args)

    # Correct configuration should pass
    workspace(
        "manage",
        "experiments",
        "validation",
        "-v",
        "n_nodes=2",
        "-v",
        "processes_per_node=1",
        "--wf",
        "test_validation",
        "--overwrite",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    ws._re_read()
    out = workspace("setup", global_args=global_args)
    assert "Warning: Validator 'validate_var_check'" not in out
    assert "Warning: Validator 'validate_undefined_var_check'" in out

    # Validator without fail_on_invalid should only issue a warning
    workspace(
        "manage",
        "experiments",
        "validation",
        "-v",
        "validate_var=invalid",
        "-v",
        "n_nodes=2",
        "-v",
        "processes_per_node=1",
        "--wf",
        "test_validation",
        "--overwrite",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    ws._re_read()

    out = workspace("setup", global_args=global_args)
    assert "Warning: Validator 'validate_var_check'" in out
    assert "The validate_var is recommended to start with 'valid', but got 'invalid'" in out


def test_variable_validation_workload(workspace_name):
    global_args = ["-w", workspace_name]

    ws = ramble.workspace.create(workspace_name)

    workspace(
        "manage",
        "experiments",
        "validation",
        "-v",
        "n_nodes=2",
        "-v",
        "processes_per_node=1",
        "-v",
        "batch_submit={execute_experiment}",
        "-v",
        "multi_choice_var=invalid",
        "--wf",
        "test_validation_workload_var",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    ws._re_read()
    with pytest.raises(
        ramble.error.ObjectValidationError,
        match=r"variable 'multi_choice_var' \('invalid'\) is not one of the allowed values",
    ):
        workspace("setup", global_args=global_args)

    workspace(
        "manage",
        "experiments",
        "validation",
        "-v",
        "n_nodes=2",
        "-v",
        "processes_per_node=1",
        "-v",
        "batch_submit={execute_experiment}",
        "-v",
        "multi_choice_var=choice2",
        "--wf",
        "test_validation_workload_var",
        "--overwrite",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    ws._re_read()
    # No error when a valid value is given
    workspace("setup", global_args=global_args)


def test_variable_validation_workload_defaults(workspace_name):
    global_args = ["-w", workspace_name]

    ws = ramble.workspace.create(workspace_name)
    workspace(
        "manage",
        "experiments",
        "validation",
        "-v",
        "n_nodes=2",
        "-v",
        "processes_per_node=1",
        "-v",
        "batch_submit={execute_experiment}",
        "-v",
        "multi_choice_var2=choice0",
        "--wf",
        "test_validation_workload_var_with_workload_defaults",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    ws._re_read()
    with pytest.raises(
        ramble.error.ObjectValidationError,
        match=r"variable 'multi_choice_var2' \('choice0'\) is not one of the allowed values",
    ):
        workspace("setup", global_args=global_args)


def test_variable_validation_workload_group(workspace_name):
    global_args = ["-w", workspace_name]

    ws = ramble.workspace.create(workspace_name)
    workspace(
        "manage",
        "experiments",
        "validation",
        "-v",
        "n_nodes=2",
        "-v",
        "processes_per_node=1",
        "-v",
        "batch_submit={execute_experiment}",
        "-v",
        "multi_choice_var3=choice0",
        "--wf",
        "test_validation_workload_var_with_workload_group",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    ws._re_read()
    with pytest.raises(
        ramble.error.ObjectValidationError,
        match=r"variable 'multi_choice_var3' \('choice0'\) is not one of the allowed values",
    ):
        workspace("setup", global_args=global_args)


def test_object_variable_validation(workspace_name, mutable_mock_pkg_mans_repo):
    global_args = ["-w", workspace_name]

    ws = ramble.workspace.create(workspace_name)
    workspace(
        "manage",
        "experiments",
        "validation",
        "-v",
        "n_nodes=2",
        "-v",
        "processes_per_node=1",
        "-v",
        "batch_submit={execute_experiment}",
        "-v",
        "obj_multi_choice_var=a",
        "--wf",
        "test_validation",
        "-V",
        "package_manager=info",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    ws._re_read()
    with pytest.raises(
        ramble.error.ObjectValidationError,
        match=r"variable 'obj_multi_choice_var' \('a'\) is not one of the allowed values",
    ):
        workspace("setup", global_args=global_args)
