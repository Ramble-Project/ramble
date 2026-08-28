# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import shutil
import subprocess

import pytest

import ramble.filters
import ramble.pipeline
import ramble.workspace
from ramble.utility.builtin.spack.utility import Spack


def test_utility_base_validate_versions_regex_fails(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    spack = Spack("/tmp/dummy")
    spack.provided_executables = {
        "spack": [
            {"executable": "spack", "version_cmd": "echo bad", "version_regex": r"(\d+\.\d+\.\d+)"}
        ]
    }
    monkeypatch.setattr(shutil, "which", lambda cmd, **kwargs: "/path/to/spack")

    class MockResult:
        stdout = "bad\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: MockResult())
    assert spack.validate_versions(min_version="1.0.0") is False
    assert "Could not determine version" in spack.availability_error


def test_utility_base_validate_versions_less_than_min(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    spack = Spack("/tmp/dummy")
    spack.provided_executables = {
        "spack": [
            {
                "executable": "spack",
                "version_cmd": "echo 1.0.0",
                "version_regex": r"(\d+\.\d+\.\d+)",
            }
        ]
    }
    monkeypatch.setattr(shutil, "which", lambda cmd, **kwargs: "/path/to/spack")

    class MockResult:
        stdout = "1.0.0\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: MockResult())
    assert spack.validate_versions(min_version="1.5.0") is False
    assert "is less than required minimum" in spack.availability_error


def test_utility_base_validate_versions_greater_than_max(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    spack = Spack("/tmp/dummy")
    spack.provided_executables = {
        "spack": [
            {
                "executable": "spack",
                "version_cmd": "echo 2.0.0",
                "version_regex": r"(\d+\.\d+\.\d+)",
            }
        ]
    }
    monkeypatch.setattr(shutil, "which", lambda cmd, **kwargs: "/path/to/spack")

    class MockResult:
        stdout = "2.0.0\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: MockResult())
    assert spack.validate_versions(max_version="1.5.0") is False
    assert "is greater than required maximum" in spack.availability_error


def test_utility_base_validate_versions_shutil_fails(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    spack = Spack("/tmp/dummy")
    spack.provided_executables = {"spack": [{"executable": "spack"}]}
    monkeypatch.setattr(shutil, "which", lambda cmd, **kwargs: None)
    assert spack.validate_versions() is False
    assert "not found in PATH" in spack.availability_error


def test_utility_base_validate_versions_no_executables(
    mutable_config, mutable_mock_workspace_path
):
    spack = Spack("/tmp/dummy")
    spack.provided_executables = {}
    assert spack.validate_versions() is False
    assert "No provided executables defined" in spack.availability_error


def test_utility_base_validate_versions_run_fails(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    spack = Spack("/tmp/dummy")
    spack.provided_executables = {
        "spack": [{"executable": "spack", "version_cmd": "fail", "version_regex": ".*"}]
    }
    monkeypatch.setattr(shutil, "which", lambda cmd, **kwargs: "/path")

    def mock_run_fail(*args, **kwargs):
        raise Exception("Run failed")

    monkeypatch.setattr(subprocess, "run", mock_run_fail)
    assert spack.validate_versions(min_version="1.0") is False
    assert "Error checking version" in spack.availability_error


def test_utility_base_setup_runner_environment_system(mutable_config, mutable_mock_workspace_path):
    ws = ramble.workspace.create("test_sys")

    class MockAppInst:
        variables = {"utility::spack::path": "system"}

        def satisfy_when(self, when_key):
            return True

    app_inst = MockAppInst()
    spack = Spack("/tmp/dummy")
    env_mod = spack.setup_runner_environment(ws, app_inst)
    assert len(env_mod) == 0
    assert spack.get_experiment_activation_command(ws, app_inst) == ""


def test_utility_base_setup_runner_environment_missing_script(
    mutable_config, mutable_mock_workspace_path
):
    ws = ramble.workspace.create("test_miss")
    ws.dry_run = False

    class MockAppInst:
        variables = {"utility::spack::path": "/path/to/spack"}

        def satisfy_when(self, when_key):
            return True

    app_inst = MockAppInst()
    spack = Spack("/tmp/dummy")
    spack.env_sources = {"True": [{"script_path": "/missing/script.sh", "when": []}]}
    # This should log a warning but not fail
    spack.setup_runner_environment(ws, app_inst)


def test_utility_base_map_fetch_kwargs(mutable_config, mutable_mock_workspace_path):
    spack = Spack("/tmp/dummy")
    spack.fetch_mappings = {None: [{"utility_var": "git", "fetch_var": "url", "fallback_for": []}]}
    mapped = spack.map_fetch_kwargs({"git": "my_git_url"})
    assert mapped == {"url": "my_git_url"}


def test_application_base_bootstrap_utilities_is_available_true(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    ws = ramble.workspace.create("test_avail")
    os.makedirs(os.path.dirname(ws.config_file_path), exist_ok=True)
    with open(ws.config_file_path, "w", encoding="utf-8") as f:
        f.write("""ramble:
  config:
    bootstrap_utilities: True
  applications:
    hostname:
      workloads:
        serial:
          experiments:
            test_exp:
              variables:
                n_ranks: '1'
  utilities:
    spack:
      git: mygit
""")
    ws._re_read()
    filters = ramble.filters.Filters()
    with ws:
        setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)
        app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))
        app_inst.required_utilities = {
            frozenset([]): {"spack": {"git": "mygit", "allow_external": "True"}}
        }
        monkeypatch.setattr(
            shutil, "which", lambda cmd, **kwargs: "/path/to/spack" if cmd == "spack" else None
        )
        setup_pipeline.run()
    assert app_inst.variables.get("utility::spack::path") == "system"


def test_application_base_bootstrap_utilities_is_bootstrappable_false(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    ws = ramble.workspace.create("test_boot")
    os.makedirs(os.path.dirname(ws.config_file_path), exist_ok=True)
    with open(ws.config_file_path, "w", encoding="utf-8") as f:
        f.write("""ramble:
  config:
    bootstrap_utilities: True
  applications:
    hostname:
      workloads:
        serial:
          experiments:
            test_exp:
              variables:
                n_ranks: '1'
  utilities:
    spack:
      git: mygit
""")
    ws._re_read()
    filters = ramble.filters.Filters()
    with ws:
        setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)
        app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))
        app_inst.required_utilities = {frozenset([]): {"spack": {"git": "mygit"}}}
        SpackClass = type(ramble.repository.get("spack", ramble.repository.ObjectTypes.utilities))
        monkeypatch.setattr(SpackClass, "is_available", lambda *a, **k: False)
        # Mock bootstrappable to False
        monkeypatch.setattr(SpackClass, "bootstrappable", {"True": [{"is_bootstrappable": False}]})
        monkeypatch.setattr(
            SpackClass,
            "missing_error_messages",
            {"True": [{"message": "Custom Error"}]},
        )

        with pytest.raises(SystemExit):
            setup_pipeline.run()
        # Custom Error should have been logged


def test_application_base_bootstrap_utilities_allow_external_false(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    ws = ramble.workspace.create("test_allow_ext_false")
    os.makedirs(os.path.dirname(ws.config_file_path), exist_ok=True)
    with open(ws.config_file_path, "w", encoding="utf-8") as f:
        f.write("""ramble:
  config:
    bootstrap_utilities: True
  applications:
    hostname:
      workloads:
        serial:
          experiments:
            test_exp:
              variables:
                n_ranks: '1'
  utilities:
    spack:
      git: mygit
""")
    ws._re_read()
    filters = ramble.filters.Filters()
    with ws:
        setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)
        app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))
        app_inst.required_utilities = {
            frozenset([]): {"spack": {"git": "mygit", "allow_external": "False"}}
        }
        UtilityBase = ramble.repository.get_base_class("utility-base")

        def mock_is_available(*args, **kwargs):
            raise Exception("is_available should not be called when allow_external=False")

        monkeypatch.setattr(UtilityBase, "is_available", mock_is_available)

        ws.dry_run = False

        class MockStage:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def set_subdir(self, subdir):
                pass

            def fetch(self):
                pass

            def expand_archive(self):
                pass

        monkeypatch.setattr(ramble.stage, "InputStage", MockStage)
        monkeypatch.setattr(UtilityBase, "validate_versions", lambda *a, **k: True)

        setup_pipeline.run()
    assert hasattr(app_inst, "_bootstrapped_utility_paths")
    assert "spack" in app_inst._bootstrapped_utility_paths


def test_application_base_bootstrap_utilities_success(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    ws = ramble.workspace.create("test_succ")
    os.makedirs(os.path.dirname(ws.config_file_path), exist_ok=True)
    with open(ws.config_file_path, "w", encoding="utf-8") as f:
        f.write("""ramble:
  config:
    bootstrap_utilities: True
  applications:
    hostname:
      workloads:
        serial:
          experiments:
            test_exp:
              variables:
                n_ranks: '1'
  utilities:
    spack:
      git: mygit
""")
    ws._re_read()
    filters = ramble.filters.Filters()
    with ws:
        setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)
        app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))
        app_inst.required_utilities = {frozenset([]): {"spack": {"git": "mygit"}}}
        UtilityBase = ramble.repository.get_base_class("utility-base")
        monkeypatch.setattr(UtilityBase, "is_available", lambda *a, **k: False)
        # Force fetch
        ws.dry_run = False

        class MockStage:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

            def set_subdir(self, subdir):
                pass

            def fetch(self):
                pass

            def expand_archive(self):
                pass

        monkeypatch.setattr(ramble.stage, "InputStage", MockStage)
        monkeypatch.setattr(UtilityBase, "validate_versions", lambda *a, **k: True)

        setup_pipeline.run()
    assert hasattr(app_inst, "_bootstrapped_utility_paths")
    assert "spack" in app_inst._bootstrapped_utility_paths


def test_spack_utility_is_available_version_checking(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    ws = ramble.workspace.create("test_spack_ver")

    spack = Spack("/tmp/dummy")
    monkeypatch.setattr(
        shutil, "which", lambda cmd, **kwargs: "/path/to/spack" if cmd == "spack" else None
    )

    class MockResult:
        stdout = "0.22.0\n"
        stderr = ""
        returncode = 0

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: MockResult())
    assert spack.is_available(ws, min_version="0.20.0", max_version="0.25.0") is True
    assert spack.is_available(ws, min_version="0.23.0") is False
    assert spack.is_available(ws, max_version="0.21.0") is False


def test_application_base_bootstrap_utilities_allow_external_false_bool(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    ws = ramble.workspace.create("test_allow_ext_false_bool")
    import os

    os.makedirs(os.path.dirname(ws.config_file_path), exist_ok=True)
    with open(ws.config_file_path, "w", encoding="utf-8") as f:
        f.write("""ramble:
  config:
    bootstrap_utilities: True
  applications:
    hostname:
      workloads:
        serial:
          experiments:
            test_exp:
              variables:
                n_ranks: '1'
  utilities:
    spack:
      git: mygit
""")
    ws._re_read()
    filters = ramble.filters.Filters()
    with ws:
        setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)
        app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))
        app_inst.required_utilities = {
            frozenset([]): {"spack": {"git": "mygit", "allow_external": False}}
        }
        UtilityBase = ramble.repository.get_base_class("utility-base")

        def mock_is_available(*args, **kwargs):
            raise Exception("is_available should not be called when allow_external=False")

        monkeypatch.setattr(UtilityBase, "is_available", mock_is_available)

        ws.dry_run = False
        app_inst._bootstrap_utilities(ws)


def test_application_base_bootstrap_utilities_empty_conf_and_none_variables(
    mutable_config, mutable_mock_workspace_path, monkeypatch, mock_applications, mock_utilities
):
    import ramble.workspace

    ws = ramble.workspace.create("test_app_bootstrap")

    # Just need a mocked application instance
    app_inst = ramble.repository.get("basic")
    app_inst.variables = None  # Explicitly set to None to test the getattr fallback
    app_inst.utilities = {}  # No utilities, just bypasses

    app_inst._bootstrap_utilities(ws)


def test_application_base_is_available_typeerror_fallback(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    import ramble.workspace
    from ramble.app.builtin.gromacs.application import Gromacs

    workspace = ramble.workspace.create("test_fallback_workspace")
    workspace.dry_run = False
    app = Gromacs("/tmp/dummy")

    class MockExpander:
        def expand_var_name(self, name):
            return name

        def satisfies(self, when_key, variant_set):
            return True

        def expand_var(self, name):
            return name

    class MockAppInst:
        def __init__(self):
            self.variables = {"gromacs_version": "1.2"}
            self.expander = MockExpander()

    app_inst = MockAppInst()
    app._app_inst = app_inst
    app.expander = MockExpander()
    app._is_experiment = True

    class MockUtilityType:
        def __init__(self):
            # self.bootstrappable removed
            self.object_variables = {}

        def is_available(self, workspace, min_version=None, max_version=None):
            return True

    class MockUtilityInst:
        def get(self, *args, **kwargs):
            return MockUtilityType()

    app.required_utilities = {
        frozenset(): {
            "spack": {
                "require_utility": True,
                "utility_name": "spack",
                "allow_external": "True",
                "min_version": "1.0",
                "version": "1.0",
                "url": "http://foo",
            }
        }
    }
    import ramble.repository

    monkeypatch.setitem(
        ramble.repository.paths, ramble.repository.ObjectTypes.utilities, MockUtilityInst()
    )

    def mock_bootstrap(workspace, ext_dep_paths):
        pass

    app.bootstrap_utility = mock_bootstrap

    import ramble.config

    monkeypatch.setattr(ramble.config, "get", lambda *args, **kwargs: True)

    app._bootstrap_utilities(workspace)
    assert app._bootstrapped_utility_paths["spack"] == "system"


def test_application_base_validate_versions_typeerror_fallback(
    mutable_config, mutable_mock_workspace_path, monkeypatch
):
    import ramble.workspace
    from ramble.app.builtin.gromacs.application import Gromacs
    from ramble.util.logger import logger

    workspace = ramble.workspace.create("test_fallback_val_workspace")
    workspace.dry_run = False
    app = Gromacs("/tmp/dummy")

    class MockExpander:
        def expand_var_name(self, name):
            return name

        def satisfies(self, when_key, variant_set):
            return True

        def expand_var(self, name):
            return name

    class MockAppInst:
        def __init__(self):
            self.variables = {"gromacs_version": "1.2"}
            self.expander = MockExpander()

    app_inst = MockAppInst()
    app._app_inst = app_inst
    app.expander = MockExpander()
    app._is_experiment = True

    class MockUtilityType:
        def __init__(self):
            # self.bootstrappable removed
            self.object_variables = {}
            self.availability_error = "Mock error"

        def is_available(self, workspace, min_version=None, max_version=None, exact_version=None):
            return False

        def setup_runner_environment(self, workspace, app_inst):
            return None

        def validate_versions(
            self, min_version=None, max_version=None, env=None, origin_name=None, origin_type=None
        ):
            return False

    class MockUtilityInst:
        def get(self, *args, **kwargs):
            return MockUtilityType()

    app.required_utilities = {
        frozenset(): {
            "spack": {
                "require_utility": True,
                "utility_name": "spack",
                "allow_external": "True",
                "version": "1.0",
                "url": "http://foo",
            }
        }
    }
    import ramble.repository

    monkeypatch.setitem(
        ramble.repository.paths, ramble.repository.ObjectTypes.utilities, MockUtilityInst()
    )

    def mock_bootstrap(workspace, ext_dep_paths):
        pass

    app.bootstrap_utility = mock_bootstrap

    import ramble.config

    monkeypatch.setattr(ramble.config, "get", lambda *args, **kwargs: True)

    warn_called = []
    monkeypatch.setattr(logger, "warn", lambda msg: warn_called.append(msg))
    import ramble.stage

    monkeypatch.setattr(ramble.stage.InputStage, "fetch", lambda *args, **kwargs: None)
    monkeypatch.setattr(ramble.stage.InputStage, "expand_archive", lambda *args, **kwargs: None)

    app._bootstrap_utilities(workspace)
    assert any("proceeding due to explicit version request" in msg for msg in warn_called)
