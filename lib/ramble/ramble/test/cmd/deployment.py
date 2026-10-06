# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import sys

import pytest

import ramble.workspace
from ramble.main import RambleCommand

deployment = RambleCommand("deployment")
workspace = RambleCommand("workspace")

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="does not run on windows")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)


def check_deployment_files(root, app_name):
    configs_dir = os.path.join(root, "configs")
    tpl = os.path.join(configs_dir, "execute_experiment.tpl")
    yaml = os.path.join(configs_dir, "ramble.yaml")

    ramble_object_dir = os.path.join(root, "object_repos", "ramble", "builtin")
    spack_pm = os.path.join(
        ramble_object_dir, "package_managers", "spack-lightweight", "package_manager.py"
    )
    app = os.path.join(ramble_object_dir, "applications", app_name, "application.py")
    spack_object_dir = os.path.join(root, "object_repos", "spack", "obj_repo")
    pkg = os.path.join(spack_object_dir, "packages", app_name, "package.py")

    dir_list = [root, configs_dir, ramble_object_dir, spack_object_dir]
    for d in dir_list:
        assert os.path.isdir(d)

    file_list = [tpl, yaml, spack_pm, app, pkg]
    for f in file_list:
        assert os.path.isfile(f)


@pytest.mark.maybeslow
def test_local_deployment(mutable_config, mutable_mock_workspace_path, workspace_name):

    app_name = "namd"

    deployment_dir = ""
    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        config_path = ws.config_file_path

        workspace(
            "manage",
            "experiments",
            app_name,
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "--default-variable-value",
            "1",
            "-V",
            "package_manager=spack",
            global_args=["-w", workspace_name],
        )
        workspace("concretize", global_args=["-w", workspace_name])

        ws._re_read()

        deployment(
            "push",
            global_args=["-w", workspace_name],
        )

        deployment_dir = os.path.join(ws.root, "deployments")
        this_deployment_dir = os.path.join(deployment_dir, workspace_name)

        check_deployment_files(this_deployment_dir, app_name)

    workspace_name = "test_local_pull"
    with ramble.workspace.create(workspace_name) as ws:
        deployment(
            "pull",
            "-p",
            os.path.join(deployment_dir, "test_local_deployment"),
            global_args=["-w", workspace_name],
        )
        config_path = ws.config_file_path

        with open(config_path, encoding="utf-8") as f:
            content = f.read()
            # Check that the app has a package, and the package is in an environment
            assert f"pkg_spec: {app_name}" in content

        check_deployment_files(ws.root, app_name)


@pytest.mark.maybeslow
def test_tar_deployment(mutable_config, mutable_mock_workspace_path, workspace_name):
    app_name = "namd"

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        workspace(
            "manage",
            "experiments",
            app_name,
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "--default-variable-value",
            "1",
            "-V",
            "package_manager=spack",
            global_args=["-w", workspace_name],
        )
        workspace("concretize", global_args=["-w", workspace_name])

        ws._re_read()

        # Push with -t (tar option)
        deployment(
            "push",
            "-t",
            global_args=["-w", workspace_name],
        )

        deployment_dir = os.path.join(ws.root, "deployments")
        tar_path = os.path.join(deployment_dir, f"{workspace_name}.tar.gz")
        assert os.path.isfile(tar_path)
