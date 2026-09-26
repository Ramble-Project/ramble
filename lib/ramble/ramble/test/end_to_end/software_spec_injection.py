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
from ramble.software_environments import RambleSoftwareEnvironmentError

pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


def test_software_spec_injection_works(mock_modifiers, workspace_name, ensure_spack_runner):

    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        with open(os.path.join(ws.config_dir, "variants.yaml"), "w+", encoding="utf-8") as f:
            f.write(
                """variants:
  implicit_compiler: True"""
            )

        workspace(
            "manage",
            "experiments",
            "gromacs",
            "--wf",
            "water_bare",
            "-v",
            "n_nodes=1",
            "-v",
            "n_ranks=1",
            "-p",
            "spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        ws.write()

        info_output = workspace("info", "--software", global_args=global_args)

        assert "missing_mod_package" not in info_output
        assert "missing_package@1.1" not in info_output
        assert "mod_compiler" not in info_output

        workspace(
            "manage",
            "modifiers",
            "--add",
            "--name",
            "spack-mod",
            "--scope",
            "workspace",
            global_args=global_args,
        )

        info_output = workspace("info", "--software", global_args=global_args)

        assert "missing_mod_package" in info_output
        assert "missing_package@1.1" in info_output
        assert "mod_compiler" in info_output
        assert "injected by ramble" in info_output


def test_existing_software_spec_does_not_inject(
    mock_modifiers, workspace_name, ensure_spack_runner
):

    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        with open(os.path.join(ws.config_dir, "variants.yaml"), "w+", encoding="utf-8") as f:
            f.write(
                """variants:
  implicit_compiler: True"""
            )

        workspace(
            "manage",
            "experiments",
            "gromacs",
            "--wf",
            "water_bare",
            "-v",
            "n_nodes=1",
            "-v",
            "n_ranks=1",
            "-p",
            "spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        ws.write()

        info_output = workspace("info", "--software", global_args=global_args)

        assert "missing_mod_package" not in info_output
        assert "missing_package@1.1" not in info_output
        assert "mod_compiler" not in info_output

        workspace(
            "manage",
            "modifiers",
            "--add",
            "--name",
            "spack-mod",
            "--scope",
            "workspace",
            global_args=global_args,
        )

        workspace("concretize", "-f", "--include-injected-packages", global_args=global_args)
        info_output = workspace("info", "--software", global_args=global_args)

        assert "missing_mod_package" in info_output
        assert "missing_package@1.1" in info_output
        assert "mod_compiler" in info_output
        assert "injected by ramble" not in info_output


def test_software_spec_injection_missing_compiler_errors(
    mock_modifiers, workspace_name, ensure_spack_runner
):

    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        with open(os.path.join(ws.config_dir, "variants.yaml"), "w+", encoding="utf-8") as f:
            f.write(
                """variants:
  missing_compiler: True"""
            )

        workspace(
            "manage",
            "experiments",
            "gromacs",
            "--wf",
            "water_bare",
            "-v",
            "n_nodes=1",
            "-v",
            "n_ranks=1",
            "-p",
            "spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        ws.write()

        workspace(
            "manage",
            "modifiers",
            "--add",
            "--name",
            "spack-mod",
            "--scope",
            "workspace",
            global_args=global_args,
        )

        with pytest.raises(
            RambleCommandError,
            match=r"When injecting packages from modifier spack-mod"
            + r".*non_existent_compiler.*is not defined",
        ):
            workspace("info", "--software", global_args=global_args)


def test_software_spec_compiler_injection_works(
    mock_applications, mock_modifiers, workspace_name, ensure_spack_runner
):

    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        with open(os.path.join(ws.config_dir, "variants.yaml"), "w+", encoding="utf-8") as f:
            f.write(
                """variants:
  injected_compiler: True"""
            )

        workspace(
            "manage",
            "experiments",
            "zlib",
            "--wf",
            "ensure_installed",
            "-v",
            "n_nodes=1",
            "-v",
            "n_ranks=1",
            "-p",
            "spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        with pytest.raises(
            RambleSoftwareEnvironmentError,
            match=r"Compiler injected_compiler used, but "
            + r"not defined in environment zlib by package zlib",
        ):
            workspace("info", "--software", global_args=global_args)

        workspace(
            "manage",
            "modifiers",
            "--add",
            "--name",
            "spack-mod",
            "--scope",
            "workspace",
            global_args=global_args,
        )

        info_out = workspace("info", "--software", global_args=global_args)

        assert "injected_compiler" in info_out


def test_conflict_resolution_inject_if_missing(
    mock_modifiers, ensure_spack_runner, make_workspace_from_config
):
    test_config = """
ramble:
  variants:
    package_manager: spack
    implicit_compiler: True
  variables:
    mpi_command: 'mpirun -n {n_ranks}'
    batch_submit: 'batch_submit {execute_experiment}'
    partition: 'part1'
    processes_per_node: '16'
    n_threads: '1'
  applications:
    gromacs:
      workloads:
        water_bare:
          experiments:
            test_exp:
              variables:
                n_nodes: '1'
                n_ranks: '1'
              modifiers:
                - name: spack-mod
  software:
    environments:
      gromacs:
        packages:
          - my_custom_package
    packages:
      my_custom_package:
        pkg_spec: missing_package@2.0
"""
    ws, ws_name = make_workspace_from_config(test_config)
    global_args = ["-w", ws_name]

    # Concretize the workspace. If the conflict resolution is correct,
    # it should NOT concretize/inject `missing_mod_package` because
    # `my_custom_package` (which defines `missing_package`) is already defined.
    workspace("concretize", global_args=global_args)

    info_output = workspace("info", "--software", global_args=global_args)

    # `missing_mod_package` should NOT be in the environment.
    assert "missing_mod_package" not in info_output
    assert "missing_package@1.1" not in info_output

    # `my_custom_package` (which is `missing_package@2.0`) should be in the environment.
    assert "my_custom_package" in info_output
    assert "missing_package@2.0" in info_output
