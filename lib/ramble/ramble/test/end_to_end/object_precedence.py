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

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)

workspace = RambleCommand("workspace")


@pytest.mark.parametrize(
    "test_args,disabled_value,enabled_value",
    [
        (
            ["-V", "workflow_manager=when-workflow-manager"],
            "object_precedence_var from application",
            "object_precedence_var from workflow_manager",
        ),
    ],
)
def test_object_precedence_variables(
    workspace_name,
    test_args,
    disabled_value,
    enabled_value,
    mutable_mock_apps_repo,
    mutable_mock_mods_repo,
    mutable_mock_pkg_mans_repo,
    mutable_mock_wms_repo,
):
    global_args = ["-w", workspace_name]

    ws = ramble.workspace.create(workspace_name)
    workspace(
        "manage",
        "experiments",
        "basic",
        "-v",
        "n_nodes=3",
        "-v",
        "processes_per_node=1",
        "-v",
        "batch_submit={execute_experiment}",
        "--wf",
        "test_wl",
        "-V",
        "package_manager=info",
        "--default-variable-value",
        "1",
        *test_args,
        global_args=global_args,
    )

    with open(os.path.join(ws.config_dir, "test.tpl"), "w+", encoding="utf-8") as f:
        f.write("{object_precedence_var}")

    variants_file = os.path.join(ws.config_dir, "variants.yaml")
    test_file = os.path.join(ws.experiment_dir, "basic", "test_wl", "generated", "test")

    workspace("setup", "--dry-run", global_args=global_args)

    with open(test_file, encoding="utf-8") as f:
        assert disabled_value in f.read()

    with open(variants_file, "w+", encoding="utf-8") as f:
        f.write("""variants:
  set_precedence_var: True""")

    workspace("setup", "--dry-run", global_args=global_args)

    with open(test_file, encoding="utf-8") as f:
        assert enabled_value in f.read()


def test_object_precedence_ordering(
    workspace_name, mock_applications, mock_platforms, mock_systems
):
    ws = ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]
    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl2",
        "-v",
        "n_ranks={processes_per_node}*{n_nodes}",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node={max_cores_per_node}",
        "-V",
        "system=spack-slurm-sys",
        global_args=global_args,
    )

    ws._re_read()
    ws.dry_run = True

    workspace("setup", "--dry-run", global_args=["-D", ws.root])

    exec_file = os.path.join(
        ws.experiment_dir, "basic", "test_wl2", "generated", "execute_experiment"
    )
    assert os.path.isfile(exec_file)
    with open(exec_file, encoding="utf-8") as f:
        data = f.read()
        # Verify mpi_command from workflow manager is not set
        assert "srun" not in data
        # Verify mpi_command from system is set, since that
        # is higher precedence than workflow managers.
        assert "mpirun" in data
        assert "-t sys-variant1-foo" in data
