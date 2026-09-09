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
from ramble.error import RambleCommandError
from ramble.main import RambleCommand

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
    "mutable_mock_apps_repo",
    "workspace_deactivate",
)

config = RambleCommand("config")
workspace = RambleCommand("workspace")
ramble_on = RambleCommand("on")


def test_success_criteria_precedence(mock_applications, workspace_name):
    """
    Tests that YAML success_criteria takes precedence over
    object-defined criteria
    """
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "success-criteria-conflicts",
            "-e",
            "pass-experiment",
            "--wf",
            "success_str_wl",
            "-v",
            "processes_per_node=1",
            "-v",
            "n_threads=1",
            "-v",
            "n_nodes=1",
            "-s",
            "name=test_success,mode=string,match=SUCCESS",
            global_args=global_args,
        )

    workspace("setup", global_args=global_args)
    ramble_on(global_args=global_args)
    workspace("analyze", "-f", "text", "json", "yaml", global_args=global_args)

    for ext in ["txt", "json", "yaml"]:
        assert os.path.exists(os.path.join(ws.results_dir, f"results.latest.{ext}"))

    with open(os.path.join(ws.results_dir, "results.latest.txt"), encoding="utf-8") as f:
        data = f.read()
        assert "Success criteria summary:" in data
        assert "application::success-criteria-conflicts::_application_function = PASSED" in data
        assert "config::experiment::test_success = PASSED" in data


def test_success_criteria_mutex_versions(workspace_name):
    """
    Tests that same named success_criteria defined in mutually exclusive
    when clauses are handled appropriately.
    """
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "success-criteria-conflicts@1.0.0",
            "--wf",
            "version_wl",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

    workspace("setup", global_args=global_args)
    ramble_on(global_args=global_args)
    workspace("analyze", "-f", "text", "json", "yaml", global_args=global_args)

    for ext in ["txt", "json", "yaml"]:
        assert os.path.exists(os.path.join(ws.results_dir, f"results.latest.{ext}"))

    with open(os.path.join(ws.results_dir, "results.latest.txt"), encoding="utf-8") as f:
        data = f.read()
        assert "Success criteria summary:" in data
        assert "application::success-criteria-conflicts::_application_function = PASSED" in data
        assert "application::success-criteria-conflicts::test_version = PASSED" in data


def test_success_criteria_multiple_satisfies(workspace_name):
    """
    Tests that an object, Application in this case, defining the same named
    success_criteria in multiple satisfying when conditions, will error out.
    """
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name):
        workspace(
            "manage",
            "experiments",
            "success-criteria-conflicts",
            "--wf",
            "success_str_wl",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )
    config("add", "variants:force_pass:true", global_args=global_args)

    expected_err = (
        r"Success criteria '.*' in object '.*' is defined "
        r"multiple times under conflicting satisfied 'when' conditions"
    )

    with pytest.raises(RambleCommandError, match=expected_err):
        workspace("setup", global_args=global_args)


def test_success_criteria_inheritance(workspace_name):
    """
    Tests that same named success_criteria defined in multiple objects (using
    inheritance) is handled appropriately.
    """
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "success-criteria-conflicts",
            "--wf",
            "inheritance_wl",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

    workspace("setup", global_args=global_args)
    ramble_on(global_args=global_args)
    workspace("analyze", "-f", "text", "json", "yaml", global_args=global_args)

    for ext in ["txt", "json", "yaml"]:
        assert os.path.exists(os.path.join(ws.results_dir, f"results.latest.{ext}"))

    with open(os.path.join(ws.results_dir, "results.latest.txt"), encoding="utf-8") as f:
        data = f.read()
        assert "Success criteria summary:" in data
        assert "application::success-criteria-conflicts::_application_function = PASSED" in data
        assert "application::success-criteria-conflicts::test_inheritance = PASSED" in data
