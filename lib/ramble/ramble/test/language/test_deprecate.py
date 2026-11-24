# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import warnings
from unittest.mock import patch

import deprecation
import pytest

import ramble
import ramble.language.shared_language
import ramble.repository
import ramble.util.deprecations
from ramble.error import DirectiveError
from ramble.language.language_base import DirectiveMeta
from ramble.main import RambleCommand

workspace = RambleCommand("workspace")
info = RambleCommand("info")
list_cmd = RambleCommand("list")


def test_deprecate_directive_parsing():
    class MockApp(metaclass=DirectiveMeta):
        name = "mock-app"
        origin_type = "application"
        __module__ = "ramble.app"

        ramble.language.shared_language.deprecate(
            deprecated_in="0.7.0",
            removed_in="0.8.0",
            replacement="new-app@2.0",
            msg="Please migrate configs.",
        )

        with ramble.language.shared_language.when("@:1.0"):
            ramble.language.shared_language.deprecate(
                deprecated_in="0.7.0",
                removed_in="0.8.0",
                replacement="mock-app@2.0",
            )

        with ramble.language.shared_language.when("workload_name=legacy"):
            ramble.language.shared_language.deprecate(
                deprecated_in="0.7.0",
                when="+extra_flag",
            )

    obj = MockApp()
    assert hasattr(obj, "deprecations")

    unconditional = obj.deprecations[frozenset()]
    assert len(unconditional) == 1
    assert unconditional[0] == {
        "deprecated_in": "0.7.0",
        "removed_in": "0.8.0",
        "replacement": "new-app@2.0",
        "message": "Please migrate configs.",
        "when": [],
    }

    version_when = frozenset(["application_version@:1.0"])
    assert version_when in obj.deprecations
    assert obj.deprecations[version_when][0]["replacement"] == "mock-app@2.0"
    assert obj.deprecations[version_when][0]["when"] == ["application_version@:1.0"]

    combined_when = frozenset(["workload_name=legacy", "+extra_flag"])
    assert combined_when in obj.deprecations
    assert obj.deprecations[combined_when][0]["removed_in"] is None


def test_deprecate_directive_inheritance():
    class ParentApp(metaclass=DirectiveMeta):
        name = "parent-app"
        origin_type = "application"
        __module__ = "ramble.app"

        ramble.language.shared_language.deprecate(
            deprecated_in="0.7.0",
            removed_in="0.8.0",
            replacement="new-parent",
        )

    class ChildApp(ParentApp):
        name = "child-app"
        __module__ = "ramble.app"

    assert len(ChildApp.deprecations[frozenset()]) == 1
    assert ChildApp.deprecations[frozenset()][0]["replacement"] == "new-parent"


@pytest.mark.parametrize(
    "kwargs,err_match",
    [
        ({"removed_in": "0.8.0"}, "cannot specify 'removed_in' without also specifying"),
        ({"deprecated_in": "not-a-version"}, "invalid 'deprecated_in' version"),
        ({"deprecated_in": "0.7.0", "removed_in": "bad-ver"}, "invalid 'removed_in' version"),
        ({"deprecated_in": 7}, "requires 'deprecated_in' to be a version string"),
        (
            {"deprecated_in": "0.7.0", "removed_in": 8},
            "requires 'removed_in' to be a version string",
        ),
        (
            {"deprecated_in": "0.8.0", "removed_in": "0.7.0"},
            "earlier than 'deprecated_in'",
        ),
        ({"deprecated_in": "0.7.0", "replacement": 123}, "requires 'replacement' to be a string"),
        ({"deprecated_in": "0.7.0", "msg": 123}, "requires 'msg' to be a string"),
    ],
)
def test_deprecate_directive_validation_errors(kwargs, err_match):
    class InvalidApp(metaclass=DirectiveMeta):
        name = "invalid-app"
        origin_type = "application"
        __module__ = "ramble.app"

        ramble.language.shared_language.deprecate(**kwargs)

    with pytest.raises(DirectiveError, match=err_match):
        _ = InvalidApp.deprecations


def test_deprecate_version_condition_and_silence(
    make_workspace_from_config, mutable_mock_apps_repo
):
    # Preferred version (2.0) and current_wl should trigger NO deprecation warnings
    clean_config = """
ramble:
  variables:
    mpi_command: ''
    batch_submit: '{execute_experiment}'
    n_ranks: '1'
    n_nodes: '1'
    processes_per_node: '1'
  applications:
    object-deprecations:
      workloads:
        current_wl:
          experiments:
            test_exp: {}
"""
    _, ws_name = make_workspace_from_config(clean_config)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out = workspace("info", global_args=["-w", ws_name])

    assert "deprecated" not in out.lower()
    dep_warnings = [w for w in caught if issubclass(w.category, deprecation.DeprecatedWarning)]
    assert not dep_warnings


@deprecation.fail_if_not_removed
def test_deprecate_version_and_workload_matrix_dedup(
    make_workspace_from_config, mutable_mock_apps_repo
):
    # Version 1.0 + legacy_wl across a 3-point matrix should emit exactly 2 warnings
    # (one per unique triggered deprecation), NOT 6.
    config_str = """
ramble:
  variables:
    mpi_command: ''
    batch_submit: '{execute_experiment}'
    n_ranks: '1'
    processes_per_node: '1'
  applications:
    object-deprecations@1.0:
      workloads:
        legacy_wl:
          experiments:
            test_exp_{n_nodes}:
              variables:
                n_nodes: ['1', '2', '3']
              matrix:
              - n_nodes
"""
    _, ws_name = make_workspace_from_config(config_str)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        out1 = workspace("info", global_args=["-w", ws_name])

    version_msg = (
        "The 'object-deprecations' application (when application_version@:1.0) "
        "is deprecated as of v0.7.0 and will be removed in v99.0.0. "
        "Please use 'object-deprecations@2.0' instead."
    )
    workload_msg = (
        "The 'object-deprecations' application (when workload_name=legacy_wl) "
        "is deprecated as of v0.7.0 and will be removed in v99.0.0. "
        "Please use 'current_wl' instead. Migrate legacy_wl to current_wl."
    )
    assert out1.count(version_msg) == 1
    assert out1.count(workload_msg) == 1

    dep_warnings = [w for w in caught if w.category is deprecation.DeprecatedWarning]
    assert len(dep_warnings) == 2

    # A second CLI command should emit the warnings once again (no stale cross-command state)
    out2 = workspace("info", global_args=["-w", ws_name])
    assert out2.count(version_msg) == 1
    assert out2.count(workload_msg) == 1


@deprecation.fail_if_not_removed
def test_deprecate_variant_future_and_versionless(
    make_workspace_from_config, mutable_mock_apps_repo
):
    config_str = """
ramble:
  variables:
    mpi_command: ''
    batch_submit: '{execute_experiment}'
    n_ranks: '1'
    n_nodes: '1'
    processes_per_node: '1'
  variants:
    legacy_mode: True
    future_dep: True
    no_version_dep: True
    bad_when: True
  applications:
    object-deprecations:
      workloads:
        current_wl:
          experiments:
            test_exp: {}
"""
    _, ws_name = make_workspace_from_config(config_str)
    out = workspace("info", global_args=["-w", ws_name])

    assert (
        out.count(
            "The 'object-deprecations' application (when +legacy_mode) "
            "is deprecated as of v0.7.0 and will be removed in v99.0.0. "
            "Use the default mode instead."
        )
        == 1
    )
    assert (
        out.count(
            "The 'object-deprecations' application (when +no_version_dep) "
            "is deprecated. Please use 'unversioned-replacement' instead."
        )
        == 1
    )
    # Future deprecation (99.0.0) should NOT warn at current ramble_version
    assert "future-replacement" not in out


@deprecation.fail_if_not_removed
def test_deprecate_across_all_object_types(
    make_workspace_from_config,
    mutable_mock_apps_repo,
    mutable_mock_mods_repo,
    mutable_mock_pkg_mans_repo,
    mutable_mock_wms_repo,
):
    config_str = """
ramble:
  variables:
    mpi_command: ''
    batch_submit: '{execute_experiment}'
    n_ranks: '1'
    processes_per_node: '1'
  variants:
    package_manager: deprecated-pm
    workflow_manager: deprecated-wm
  modifiers:
  - name: deprecated-mod@1.0
    mode: legacy
  applications:
    object-deprecations:
      workloads:
        current_wl:
          experiments:
            test_exp_{n_nodes}:
              variables:
                n_nodes: ['1', '2']
              matrix:
              - n_nodes
"""
    _, ws_name = make_workspace_from_config(config_str)
    out = workspace("info", global_args=["-w", ws_name])

    assert (
        out.count(
            "The 'deprecated-mod' modifier (when deprecated-mod_mode=legacy) "
            "is deprecated as of v0.7.0 and will be removed in v99.0.0. "
            "Please use 'deprecated-mod_mode=standard' instead."
        )
        == 1
    )
    assert (
        out.count(
            "The 'deprecated-mod' modifier (when modifier_version@:1.0) "
            "is deprecated as of v0.7.0 and will be removed in v99.0.0. "
            "Please use 'deprecated-mod@2.0' instead."
        )
        == 1
    )
    assert (
        out.count(
            "The 'deprecated-pm' package manager is deprecated as of v0.7.0 "
            "and will be removed in v99.0.0. Please use 'user-managed' instead."
        )
        == 1
    )
    assert (
        out.count(
            "The 'deprecated-wm' workflow manager is deprecated as of v0.7.0 "
            "and will be removed in v99.0.0. Please use 'slurm' instead."
        )
        == 1
    )


@deprecation.fail_if_not_removed
def test_deprecate_dedup_across_multiple_build_experiment_sets_in_command(
    make_workspace_from_config, mutable_mock_apps_repo
):
    config_str = """
ramble:
  variables:
    mpi_command: ''
    batch_submit: '{execute_experiment}'
    n_ranks: '1'
    n_nodes: '1'
    processes_per_node: '1'
  variants:
    legacy_mode: True
  applications:
    object-deprecations:
      workloads:
        current_wl:
          experiments:
            test_exp: {}
"""
    ws, _ = make_workspace_from_config(config_str, activate=True)

    with patch("ramble.util.logger.logger.warn") as mock_warn:
        with ramble.util.deprecations.deprecation_warning_context():
            ws.build_experiment_set()
            ws.build_experiment_set()

    deprecation_calls = [call for call in mock_warn.call_args_list if "is deprecated" in str(call)]
    assert len(deprecation_calls) == 1


def test_deprecate_fail_if_not_removed_on_expired_version(
    make_workspace_from_config, mutable_mock_apps_repo
):
    config_str = """
ramble:
  variables:
    mpi_command: ''
    batch_submit: '{execute_experiment}'
    n_ranks: '1'
    n_nodes: '1'
    processes_per_node: '1'
  variants:
    expired_dep: True
  applications:
    object-deprecations:
      workloads:
        current_wl:
          experiments:
            test_exp: {}
"""
    _, ws_name = make_workspace_from_config(config_str)

    @deprecation.fail_if_not_removed
    def _run_expired():
        workspace("info", global_args=["-w", ws_name])

    with pytest.raises(AssertionError, match="uses a function that should be removed"):
        _run_expired()


def test_deprecate_fail_if_not_removed_on_version_bump(make_workspace_from_config, monkeypatch):
    config_str = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '1'
    n_ranks: '1'
    n_nodes: '1'
    n_threads: '1'
    wrf_path: '/not/a/real/path'
  applications:
    wrfv3:
      workloads:
        CONUS_12km:
          experiments:
            test_exp: {}
"""
    _, ws_name = make_workspace_from_config(config_str)

    @deprecation.fail_if_not_removed
    def _run_wrfv3():
        workspace("info", global_args=["-w", ws_name])

    # Passes at current version (0.7.0 < 0.8.0)
    _run_wrfv3()

    # Fails once ramble_version reaches removed_in (0.8.0)
    monkeypatch.setattr(ramble, "ramble_version", "0.8.0")
    with pytest.raises(AssertionError, match="wrfv3.*unsupported as of 0.8.0"):
        _run_wrfv3()


def test_deprecate_silent_in_list_and_info():
    with patch("ramble.util.logger.logger.warn") as mock_warn:
        list_out = list_cmd("wrf*")
        info_out = info("wrfv3")

    assert "wrfv3" in list_out
    assert "wrfv4" in list_out
    assert "deprecations:" in info_out
    assert "deprecated in 0.7.0, removed in 0.8.0 (replacement: wrf@3.9.1.1)" in info_out
    mock_warn.assert_not_called()


@deprecation.fail_if_not_removed
def test_all_builtin_deprecations_not_expired():
    """Verify no built-in Ramble object has a deprecation past its removed_in version."""
    for obj_type in ramble.repository.ObjectTypes:
        repo_path = ramble.repository.paths[obj_type]
        for obj_name in repo_path.all_object_names():
            obj_cls = repo_path.get_obj_class(obj_name)
            deprecations = getattr(obj_cls, "deprecations", None)
            if not deprecations:
                continue
            origin_type = getattr(obj_cls, "origin_type", obj_type.name)
            for dep_list in deprecations.values():
                for dep in dep_list:
                    ramble.util.deprecations.emit_deprecation_warning(
                        obj_name=obj_name,
                        obj_type=origin_type,
                        deprecation_entry=dep,
                        warn_user=False,
                    )
