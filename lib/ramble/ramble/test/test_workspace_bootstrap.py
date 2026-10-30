# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.config
import ramble.filters
import ramble.pipeline
import ramble.workspace
from ramble.main import RambleCommand


def test_workspace_bootstrap_utilities(make_workspace_from_config, monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda x, **kwargs: None)

    test_config = """
ramble:
  utilities:
    spack:
      git: https://github.com/my/ext_dep.git
      commit: v2.0
"""
    ws, ws_name = make_workspace_from_config(test_config, activate=True)
    workspace = RambleCommand("workspace")
    workspace(
        "manage",
        "experiments",
        "hostname",
        "--wf",
        "serial",
        "-v",
        "n_ranks=1",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        global_args=["-w", ws_name],
    )
    ws._re_read()

    # In order to test bootstrap, we need an object with required_utilities
    filters = ramble.filters.Filters()

    with ws:
        setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)

        # Retrieve the app instance to mock the external dependency definition
        app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))

        # Manually attach required_utilities to the instance
        app_inst.required_utilities = {
            frozenset([]): {
                "spack": {
                    "git": "https://github.com/spack/spack.git",
                    "commit": "v1.0",
                }
            }
        }

        ws.dry_run = True
        with ramble.config.override("config:bootstrap_utilities", True):
            setup_pipeline.run()

    assert hasattr(app_inst, "_bootstrapped_utility_paths")
    assert "spack" in app_inst._bootstrapped_utility_paths
    # Verify the external dependency directory is correct
    ext_dep_dir = app_inst._bootstrapped_utility_paths["spack"]
    assert ext_dep_dir.endswith(os.path.join("bootstrapped_utilities", "spack", "v2.0", "source"))
    assert "utility::spack::activation_command" in app_inst.variables
    assert "source" in app_inst.variables["utility::spack::activation_command"]


def test_workspace_bootstrap_utilities_from_modifier(
    mutable_config,
    mutable_mock_workspace_path,
    mock_applications,
    mock_modifiers,
    workspace_name,
):
    workspace = RambleCommand("workspace")
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name):
        workspace(
            "manage",
            "experiments",
            "basic",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            global_args=global_args,
        )
        workspace(
            "manage",
            "modifiers",
            "--add",
            "--name",
            "requires-utility-mod",
            "--scope",
            "workspace",
            global_args=global_args,
        )

        ws = ramble.workspace.active_workspace()
        filters = ramble.filters.Filters()
        setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)
        ws.dry_run = True
        with ramble.config.override("config:bootstrap_utilities", True):
            setup_pipeline.run()

        app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))
        assert "spack" in app_inst.utilities
        assert app_inst.utilities["spack"]["git"] == "https://github.com/spack/spack.git"
        assert app_inst.utilities["spack"]["commit"] == "v1.5"
        assert app_inst.utilities["spack"]["allow_external"] is False
        assert len(app_inst._utility_instances) == 1
        assert app_inst._utility_instances[0].name == "spack"
        assert app_inst._utility_instances[0].utility_config == app_inst.utilities["spack"]
        # Calling build_utility_instances again should return early from cached instances
        cached_instances = list(app_inst._utility_instances)
        app_inst.build_utility_instances()
        assert app_inst._utility_instances == cached_instances
        assert hasattr(app_inst, "_bootstrapped_utility_paths")
        assert "spack" in app_inst._bootstrapped_utility_paths
        ext_dep_dir = app_inst._bootstrapped_utility_paths["spack"]
        assert ext_dep_dir.endswith(
            os.path.join("bootstrapped_utilities", "spack", "v1.5", "source")
        )


def test_missing_utility_from_workspace_config_error(
    make_workspace_from_config, mock_applications
):
    test_config = """
ramble:
  utilities:
    non_existent_utility:
      git: https://github.com/my/ext_dep.git
"""
    _, ws_name = make_workspace_from_config(test_config, activate=True)
    workspace = RambleCommand("workspace")
    out = workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-v",
        "n_ranks=1",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        global_args=["-w", ws_name],
        fail_on_error=False,
    )

    assert workspace.returncode != 0
    assert "The following utilities were required, but do not exist." in out
    assert "  - non_existent_utility" in out
    assert "To view the available utilities, use `ramble list --type utilities`" in out


def test_missing_required_utility_from_object_error(
    make_workspace_from_config, mock_applications, capsys
):
    ws, ws_name = make_workspace_from_config(activate=True)
    workspace = RambleCommand("workspace")
    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-v",
        "n_ranks=1",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        global_args=["-w", ws_name],
    )
    ws._re_read()

    filters = ramble.filters.Filters()
    setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)
    app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))

    app_inst.required_utilities = {
        frozenset([]): {
            "missing_util_b": {},
            "missing_util_a": {},
        }
    }
    app_inst._utility_instances = []

    with pytest.raises(SystemExit):
        app_inst.build_utility_instances()

    captured = capsys.readouterr()
    assert "The following utilities were required, but do not exist." in captured.err
    assert "  - missing_util_a\n  - missing_util_b" in captured.err
    assert "To view the available utilities, use `ramble list --type utilities`" in captured.err


def test_bootstrap_utilities_edge_cases(
    make_workspace_from_config, mock_applications, monkeypatch
):
    test_config = """
ramble:
  utilities:
    spack:
      git: https://github.com/my/ext_dep.git
      when: ["some_cond"]
"""
    ws, ws_name = make_workspace_from_config(test_config, activate=True)
    workspace = RambleCommand("workspace")
    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-v",
        "n_ranks=1",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "spack_version=expanded_commit",
        global_args=["-w", ws_name],
    )
    ws._re_read()

    filters = ramble.filters.Filters()
    setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)
    app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))

    app_inst.required_utilities = {
        frozenset([]): {
            "missing_repo_util": {},
            "spack": {"git": "https://github.com/spack/spack.git"},
        }
    }

    # Test inner config:bootstrap_utilities disabled check and missing utility warn/continue
    config_calls = {"count": 0}
    orig_get = ramble.config.get

    def mock_config_get(key, default=None, **kwargs):
        if key == "config:bootstrap_utilities":
            config_calls["count"] += 1
            return config_calls["count"] == 1
        return orig_get(key, default=default, **kwargs)

    monkeypatch.setattr(ramble.config, "get", mock_config_get)

    app_inst._bootstrap_utilities(ws)
    assert app_inst._bootstrapped_utility_paths["spack"] == "system"
    assert app_inst.variables["utility::spack::commit"] == "expanded_commit"
    assert "utility::spack::when" not in app_inst.variables
