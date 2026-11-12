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

import ramble.config
import ramble.paths
import ramble.pipeline
import ramble.workspace
from ramble.main import RambleCommand, RambleCommandError
from ramble.util import json_util

deployment = RambleCommand("deployment")
workspace = RambleCommand("workspace")

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="does not run on windows")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)


def check_deployment_files(root, app_name, pm_name="spack-lightweight", util_name="spack"):
    configs_dir = os.path.join(root, "configs")
    tpl = os.path.join(configs_dir, "execute_experiment.tpl")
    yaml = os.path.join(configs_dir, "ramble.yaml")

    ramble_object_dir = os.path.join(root, "object_repos", "ramble", "builtin")
    app = os.path.join(ramble_object_dir, "applications", app_name, "application.py")

    dir_list = [root, configs_dir, ramble_object_dir]
    file_list = [tpl, yaml, app]

    if pm_name:
        pm = os.path.join(ramble_object_dir, "package_managers", pm_name, "package_manager.py")
        file_list.append(pm)
        if pm_name.startswith("spack"):
            spack_object_dir = os.path.join(root, "object_repos", "spack", "obj_repo")
            pkg = os.path.join(spack_object_dir, "packages", app_name, "package.py")
            dir_list.append(spack_object_dir)
            file_list.append(pkg)

    if util_name:
        util = os.path.join(ramble_object_dir, "utilities", util_name, "utility.py")
        file_list.append(util)

    for d in dir_list:
        assert os.path.isdir(d)

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

        ramble.config.add(
            f"repos:[{ramble.paths.mock_builtin_path}]",
            scope=ws.ws_file_config_scope_name(),
        )

        repos_yaml_path = os.path.join(ws.config_dir, "repos.yaml")
        with open(repos_yaml_path, "w", encoding="utf-8") as f:
            f.write(f"repos:\n  - {ramble.paths.mock_builtin_path}\n")

        ws._re_read()

        deployment(
            "push",
            global_args=["-w", workspace_name],
        )

        deployment_dir = os.path.join(ws.root, "deployments")
        this_deployment_dir = os.path.join(deployment_dir, workspace_name)

        check_deployment_files(this_deployment_dir, app_name)

        assert not os.path.exists(os.path.join(this_deployment_dir, "configs", "repos.yaml"))

        deployed_yaml = os.path.join(this_deployment_dir, "configs", "ramble.yaml")
        with open(deployed_yaml, encoding="utf-8") as f:
            deployed_content = f.read()
            assert "repos:" not in deployed_content

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


@pytest.mark.parametrize(
    "malicious_entry_kind",
    [
        "relative_parent",
        "relative_nested_parent",
        "relative_bounce_back",
        "absolute_outside",
        "absolute_inside",
        "symlink_escape",
    ],
)
def test_deployment_pull_rejects_path_traversal(tmpdir, workspace_name, malicious_entry_kind):
    outside_dir = tmpdir.mkdir("outside")
    victim_file = outside_dir.join("victim.txt")
    victim_file.write("original content")

    deploy_dir = tmpdir.mkdir("malicious_deployment")
    push_cls = ramble.pipeline.PushDeploymentPipeline

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        if malicious_entry_kind == "relative_parent":
            entry = "../victim.txt"
            target_check_path = os.path.normpath(os.path.join(ws.root, entry))
            with open(target_check_path, "w", encoding="utf-8") as f:
                f.write("original content")
        elif malicious_entry_kind == "relative_nested_parent":
            entry = "configs/../../victim.txt"
            target_check_path = os.path.normpath(os.path.join(ws.root, entry))
            with open(target_check_path, "w", encoding="utf-8") as f:
                f.write("original content")
        elif malicious_entry_kind == "relative_bounce_back":
            entry = f"../{os.path.basename(ws.root)}/configs/ramble.yaml"
            target_check_path = str(victim_file)
        elif malicious_entry_kind == "absolute_outside":
            entry = str(victim_file)
            target_check_path = str(victim_file)
        elif malicious_entry_kind == "absolute_inside":
            entry = os.path.join(ws.root, "configs", "ramble.yaml")
            target_check_path = str(victim_file)
        elif malicious_entry_kind == "symlink_escape":
            os.symlink(str(outside_dir), os.path.join(ws.root, "escaped_link"))
            entry = "escaped_link/victim.txt"
            target_check_path = str(victim_file)

        index_path = os.path.join(str(deploy_dir), push_cls.index_filename)
        with open(index_path, "w", encoding="utf-8") as f:
            f.write(json_util.dumps({push_cls.index_namespace: [entry]}))

        with pytest.raises(
            RambleCommandError,
            match="resolves outside of the workspace root",
        ):
            deployment(
                "pull",
                "-p",
                str(deploy_dir),
                global_args=["-w", workspace_name],
            )

        assert os.path.isfile(target_check_path)
        with open(target_check_path, encoding="utf-8") as f:
            assert f.read() == "original content"
