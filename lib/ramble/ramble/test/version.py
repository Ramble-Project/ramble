# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.variants
import ramble.workspace
from ramble.appkit import ExecutableApplication
from ramble.definitions.versions import ObjectVersion
from ramble.error import DirectiveError, ObjectValidationError
from ramble.main import RambleCommand

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
    "mutable_mock_apps_repo",
    "mock_modifiers",
    "mock_base_applications",
)

config = RambleCommand("config")
workspace = RambleCommand("workspace")


def test_only_one_preferred_version_allowed():
    app_inst = ExecutableApplication("/not/a/path")

    app_inst.preferred_version = ObjectVersion(version_number="1.0", preferred=True)

    with pytest.raises(DirectiveError, match="Only one version can be marked preferred."):
        app_inst.version("1.1", preferred=True)


@pytest.mark.parametrize(
    "version,expected_zlib",
    [
        ("2.0a1", {"zlib-greater"}),
        ("1.0", {"zlib-exact", "zlib-greater", "zlib-range"}),
        ("0.9", {"zlib-range", "zlib-less"}),
        ("0.8", {"zlib-less"}),
    ],
)
def test_application_version_variant_when(workspace_name, version, expected_zlib):
    global_args = ["-w", workspace_name]

    zlib_versions = {
        ("zlib-exact", "zlib@1.2.14"),
        ("zlib-greater", "zlib@1.2.13"),
        ("zlib-range", "zlib@1.2.12"),
        ("zlib-less", "zlib@1.2.11"),
    }

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            f"versions@{version}",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()

            for zlib_name, zlib_version in zlib_versions:
                if zlib_name in expected_zlib:
                    assert zlib_version in data
                else:
                    assert zlib_version not in data


def test_strict_versions_config(workspace_name, capsys):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "versions@0.1",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        with pytest.raises(ObjectValidationError):
            captured = workspace("concretize", global_args=global_args)
            assert "You must select from defined versions" in captured

        config("add", "config:enable_strict_versions:false", global_args=global_args)
        ws._re_read()

        workspace("concretize", global_args=global_args)

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "versions@0.1" in data


def test_strict_versions_directive(workspace_name):
    """Test that the strict_versions(False) directive works correctly."""
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "versions-strict-disabled@0.1",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "versions-strict-disabled@0.1" in data


def test_versions_inherited_from_base_app(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        # Add a version inherited from base application
        workspace(
            "manage",
            "experiments",
            "versions@0.8",
            "--wf",
            "test_wl_base",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        # Add a version from application
        workspace(
            "manage",
            "experiments",
            "versions@1.0",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "versions@0.8" in data
            assert "versions@1.0" in data


def test_non_pep440_version_number(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "versions-nonstandard@1_01",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "versions-nonstandard@1_01" in data
            assert "zlib@1.2.14" in data

        output = workspace("info", "-v", global_args=global_args)

        assert "Rendered package: versions-nonstandard-1_01" in output
        assert "Spec: versions-nonstandard@1_01" in output
        assert "versions-nonstandard-1_01 = versions-nonstandard@1_01" in output
        assert "zlib-exact = zlib@1.2.14" in output


@pytest.mark.parametrize(
    "version,expected_zlib",
    [
        ("1_01", {"zlib-exact", "zlib-range", "zlib-less"}),
        ("1_02", {"zlib-greater", "zlib-range"}),
        ("2_0a1", {"zlib-greater"}),
        ("0.8", {"zlib-less"}),
    ],
)
def test_non_pep440_application_version_variant_when(workspace_name, version, expected_zlib):
    global_args = ["-w", workspace_name]

    zlib_versions = {
        ("zlib-exact", "zlib@1.2.14"),
        ("zlib-greater", "zlib@1.2.13"),
        ("zlib-range", "zlib@1.2.12"),
        ("zlib-less", "zlib@1.2.11"),
    }

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            f"versions-nonstandard@{version}",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()

            for zlib_name, zlib_version in zlib_versions:
                if zlib_name in expected_zlib:
                    assert zlib_version in data
                else:
                    assert zlib_version not in data


def test_version_variable_expansion_info(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "versions@{version}",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-v",
            "version=['1.0', '2.0a1']",
            "-v",
            "custom_var='val_{version}'",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        output = workspace("info", global_args=global_args)

        assert "versions@1.0.test_wl.generated" in output
        assert "versions@2.0a1.test_wl.generated" in output

        # Verify expansion in the ramble.yaml file
        with open(ws.config_file_path, encoding="utf-8") as f:
            config_content = f.read()
            assert "versions@{version}" in config_content
            assert "val_{version}" in config_content

        # Verify application_version logic works for expanded experiments
        # versions@1.0 should have zlib@1.2.14, versions@2.0a1 should not.
        output_v = workspace("info", "-vv", global_args=global_args)
        assert "versions@1.0.test_wl.generated" in output_v
        assert "versions@2.0a1.test_wl.generated" in output_v
        assert "custom_var = val_{version} ==> val_1.0" in output_v
        assert "custom_var = val_{version} ==> val_2.0a1" in output_v
        assert "zlib-exact = zlib@1.2.14" in output_v
        assert "zlib-greater = zlib@1.2.13" in output_v

        workspace("setup", "--dry-run", global_args=global_args)

        # Verify paths for both experiments
        exp1_path = os.path.join(ws.experiment_dir, "versions@1.0", "test_wl", "generated")
        exp2_path = os.path.join(ws.experiment_dir, "versions@2.0a1", "test_wl", "generated")
        assert os.path.exists(exp1_path)
        assert os.path.exists(exp2_path)


def test_repeat_modifier_versions_error(workspace_name, workspace_deactivate):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name):
        workspace(
            "manage",
            "experiments",
            "versions@0.9",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace(
            "manage",
            "modifiers",
            "--add",
            "--scope",
            "workspace",
            "--name",
            "versions-mod@1.0",
            "--on-executable",
            "foo",
            global_args=global_args,
        )

        workspace(
            "manage",
            "modifiers",
            "--add",
            "--scope",
            "workspace",
            "--name",
            "versions-mod@2.0",
            "--on-executable",
            "bar",
            global_args=global_args,
        )

        err_str = (
            "Two modifier definitions conflict by having the "
            "same name and different version numbers."
        )
        with pytest.raises(ramble.error.ConflictingModifiersError, match=err_str):
            workspace("info", global_args=global_args)


def test_multi_modifier_versions(workspace_name):
    global_args = ["-w", workspace_name, "--overwrite-inventories"]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "versions@0.9",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-v",
            "info-app-dep_path=/not/a/path",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace(
            "manage",
            "modifiers",
            "--add",
            "--scope",
            "workspace",
            "--name",
            "versions-mod@1.0",
            global_args=global_args,
        )

        workspace(
            "manage",
            "modifiers",
            "--add",
            "--scope",
            "workspace",
            "--name",
            "info@2.0",
            global_args=global_args,
        )

        exec_tpl = os.path.join(ws.config_dir, "execute_experiment.tpl")
        with open(exec_tpl, "a+", encoding="utf-8") as f:
            f.write("versions-mod version: {modifier::versions-mod::version}\n")
            f.write("info version: {modifier::info::version}\n")

        workspace("setup", "--dry-run", global_args=global_args)

        exec_script = os.path.join(
            ws.experiment_dir, "versions@0.9", "test_wl", "generated", "execute_experiment"
        )

        with open(exec_script, encoding="utf-8") as f:
            data = f.read()
            assert "versions-mod version: 1.0" in data
            assert "info version: 2.0" in data


def test_define_version_variables_errors(workspace_name, workspace_deactivate):
    global_args = ["-w", workspace_name, "--overwrite-inventories"]

    with ramble.workspace.create(workspace_name):
        err_str = (
            'Keyword "application::versions::version" has been defined, but is reserved by ramble'
        )

        with pytest.raises(ramble.experiment_set.RambleVariableDefinitionError, match=err_str):
            workspace(
                "manage",
                "experiments",
                "versions@0.9",
                "--wf",
                "test_wl",
                "-v",
                "n_ranks=1",
                "-v",
                "n_nodes=1",
                "-v",
                "processes_per_node=1",
                "-v",
                "application::versions::version=foo",
                "--default-variable-value",
                "1",
                global_args=global_args,
            )
