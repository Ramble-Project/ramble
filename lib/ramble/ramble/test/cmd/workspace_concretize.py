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

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


def test_workspace_concretize_additive(workspace_name):
    ws = ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "experiments",
        "gromacs",
        "-V",
        "package_manager=spack",
        "--wf",
        "water_*",
        global_args=global_args,
    )
    workspace("concretize", "-q", global_args=global_args)

    with open(ws.config_file_path, encoding="utf-8") as f:
        content = f.read()
        assert "gromacs" in content
        assert "gcc14" in content
        assert "wrf" not in content
        assert "intel-oneapi-vtune" not in content

    workspace(
        "manage",
        "experiments",
        "wrf",
        "-V",
        "package_manager=spack",
        global_args=global_args,
    )
    workspace("concretize", "-q", global_args=global_args)

    with open(ws.config_file_path, encoding="utf-8") as f:
        content = f.read()
        assert "gromacs" in content
        assert "gcc14" in content
        assert "wrf" in content
        assert "intel-oneapi-vtune" not in content

    modifiers_path = os.path.join(ws.config_dir, "modifiers.yaml")

    with open(modifiers_path, "w+", encoding="utf-8") as f:
        f.write("""modifiers:
- name: intel-aps""")

    workspace("concretize", "-q", global_args=global_args)

    with open(ws.config_file_path, encoding="utf-8") as f:
        content = f.read()
        assert "gromacs" in content
        assert "gcc14" in content
        assert "wrf" in content
        assert "intel-oneapi-vtune" in content


def test_workspace_multispec_concretize(workspace_name):
    ws = ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "experiments",
        "gromacs",
        "-V",
        "package_manager=spack",
        "-e",
        "spack_test",
        "--wf",
        "water_*",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    workspace(
        "manage",
        "experiments",
        "gromacs@2024.1",
        "-V",
        "package_manager=eessi",
        "-e",
        "eessi_test",
        "--wf",
        "water_*",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    workspace("concretize", "-q", global_args=global_args)

    with open(ws.config_file_path, encoding="utf-8") as f:
        content = f.read()
        assert "gromacs" in content
        assert "spack_pkg_spec" in content
        assert "eessi_pkg_spec" in content


def test_workspace_concretize_populated_env_no_warning(workspace_name, capsys):
    ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "experiments",
        "gromacs",
        "-V",
        "package_manager=spack",
        "--wf",
        "water_bare",
        "-v",
        "n_nodes=2",
        global_args=global_args,
    )
    _ = capsys.readouterr()
    workspace("concretize", global_args=global_args)
    captured = capsys.readouterr()
    assert "was auto-constructed" not in captured.err


def test_workspace_concretize_expand_software_spec_variables(
    workspace_name, mock_applications, mock_modifiers
):
    ws = ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "experiments",
        "var-compiler-app",
        "-V",
        "package_manager=spack",
        global_args=global_args,
    )
    workspace(
        "manage",
        "modifiers",
        "--add",
        "--name",
        "var-compiler-mod",
        "--scope",
        "workspace",
        global_args=global_args,
    )
    workspace("concretize", global_args=global_args)

    with open(ws.config_file_path, encoding="utf-8") as f:
        content = f.read()
        assert "var-compiler" in content
        assert "gcc@12.2.0" in content
        assert "{my_compiler_spec}" not in content
        assert "var-pkg" in content
        assert "zlib@1.2.13" in content
        assert "mod-compiler" in content
        assert "gcc@13.1.0" in content
        assert "{mod_compiler_spec}" not in content
