# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import argparse
import os
import shutil

import pytest

import ramble.config
from ramble.namespace import namespace
from ramble.workspace import TEMPLATE_EXTENSION, workspace

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures(
    "config",
    "mutable_mock_workspace_path",
    "mutable_mock_apps_repo",
    "workspace_deactivate",
)


def test_re_read(tmpdir):
    with tmpdir.as_cwd():
        test_workspace = workspace.Workspace(os.getcwd(), True)
        test_workspace.clear()
        test_workspace._re_read()


def test_read_file_content(tmpdir):
    with tmpdir.as_cwd():
        test_workspace = workspace.Workspace(os.getcwd(), True)
        fname = "test.tpl"
        with open(fname, "w+", encoding="utf-8") as f:
            f.write("test content read")
        assert test_workspace.read_file_content(fname) == "test content read"
        with open(fname, "w", encoding="utf-8") as f:
            f.write("test content read modified")
        # The read is cached and does not reflect the latest content
        assert test_workspace.read_file_content(fname) == "test content read"


def test_all_config_files():
    ws_name = "test-ws-config-files"
    ws_root = workspace.root(ws_name)
    try:
        ws = workspace.create(ws_name)
        ws.write()

        config_dir = os.path.join(ws_root, workspace.WORKSPACE_CONFIG_PATH)

        # Create another yaml file
        extra_yaml_path = os.path.join(config_dir, "extra.yaml")
        with open(extra_yaml_path, "w", encoding="utf-8") as f:
            f.write("key: value")

        # Create a non-yaml file
        not_yaml_path = os.path.join(config_dir, "not.txt")
        with open(not_yaml_path, "w", encoding="utf-8") as f:
            f.write("hello")

        config_files = workspace.all_config_files(ws_root)

        ramble_yaml_path = os.path.join(config_dir, workspace.CONFIG_FILE_NAME)

        assert len(config_files) == 2
        assert ramble_yaml_path in config_files
        assert extra_yaml_path in config_files

    finally:
        if os.path.exists(ws_root):
            shutil.rmtree(ws_root)


def test_template_path():
    ws_name = "test-ws-template-path"
    ws_root = workspace.root(ws_name)

    template_name = "my-template"

    path = workspace.template_path(ws_root, template_name)

    expected_path = os.path.join(
        ws_root,
        workspace.WORKSPACE_CONFIG_PATH,
        template_name + TEMPLATE_EXTENSION,
    )

    assert path == expected_path


def test_get_workspace():
    ws_name = "test-ws-get-ws"
    ws_root = workspace.root(ws_name)
    ws = None

    try:
        # Setup a workspace
        ws = workspace.create(ws_name)
        ws.write()

        # Scenario 1: by name
        args = argparse.Namespace(workspace=ws_name)
        ret_ws = workspace.get_workspace(args, "test-cmd")
        assert ret_ws.name == ws_name

        # Scenario 2: by path
        args = argparse.Namespace(workspace=ws_root)
        ret_ws = workspace.get_workspace(args, "test-cmd")
        assert ret_ws.root == ws_root

        # Scenario 3: active workspace
        workspace.activate(ws)
        args = argparse.Namespace()  # no workspace attribute
        ret_ws = workspace.get_workspace(args, "test-cmd")
        assert ret_ws.name == ws_name

        # Scenario 4: no workspace, required=True
        # Deactivate first to test this case
        workspace.deactivate()
        with pytest.raises(SystemExit):
            workspace.get_workspace(args, "test-cmd", required=True)
        # Reactivate for cleanup
        workspace.activate(ws)

        # Scenario 5: invalid workspace in args
        args = argparse.Namespace(workspace="non-existent-ws")
        with pytest.raises(workspace.RambleWorkspaceError):
            workspace.get_workspace(args, "test-cmd")

    finally:
        if ws:
            workspace.deactivate()
        if os.path.exists(ws_root):
            shutil.rmtree(ws_root)


def test_all_workspace_names_multiple_dirs(tmpdir, monkeypatch):
    dir1 = tmpdir.mkdir("dir1")
    dir2 = tmpdir.mkdir("dir2")

    orig_get = ramble.config.get

    def mock_get(path, default=None, scope=None):
        if path == "config:workspace_dirs":
            return [str(dir1), str(dir2)]
        return orig_get(path, default=default, scope=scope)

    monkeypatch.setattr(ramble.config, "get", mock_get)

    ws1_root = os.path.join(str(dir1), "ws1")
    ws2_root = os.path.join(str(dir2), "ws2")

    ws1 = workspace.Workspace(ws1_root, True)
    ws1.write()

    ws2 = workspace.Workspace(ws2_root, True)
    ws2.write()

    names = workspace.all_workspace_names()

    assert "ws1" in names
    assert "ws2" in names


def test_add_experiments_with_zips(make_workspace_from_config):
    ws, _ = make_workspace_from_config(activate=True)
    ws.add_experiments(
        application="basic",
        workload_name_variable=None,
        workload_filters=["test_wl"],
        include_default_variables=False,
        default_variable_value="",
        variable_filters=["*"],
        variable_definitions=["var1=['a', 'b']", "var2=['c', 'd']"],
        variant_definitions=[],
        experiment_name="test_exp",
        zips=["my_zip=[var1,var2]"],
    )
    ws._re_read()
    app_config = ramble.config.get(namespace.application)
    exp_config = app_config["basic"]["workloads"]["test_wl"]["experiments"]["test_exp"]
    assert "zips" in exp_config
    assert exp_config["zips"]["my_zip"] == ["var1", "var2"]


def test_all_applications_with_version_and_namespace(mutable_mock_workspace_path):
    ws_name = "test-ws-app-versions"
    ws_root = workspace.root(ws_name)
    ws = None

    if os.path.exists(ws_root):
        shutil.rmtree(ws_root)

    try:
        ws = workspace.create(ws_name)
        workspace.activate(ws)

        ramble.config.add(
            "applications:builtin.app.hostname@1.0:workloads:test_wl:experiments:{}",
            scope=ws.ws_file_config_scope_name(),
        )
        ramble.config.add(
            "applications:basic@2.0:workloads:test_wl:experiments:{}",
            scope=ws.ws_file_config_scope_name(),
        )
        ws.write()
        ws._re_read()

        apps = {}
        for contents, app_context in ws.all_applications():
            apps[app_context.context_name] = contents.get(ramble.namespace.namespace.version)

        assert "builtin.app.hostname" in apps
        assert apps["builtin.app.hostname"] == "1.0"
        assert "basic" in apps
        assert apps["basic"] == "2.0"
    finally:
        if ws:
            workspace.deactivate()
        if os.path.exists(ws_root):
            shutil.rmtree(ws_root)


def test_all_applications_application_configs(mutable_mock_workspace_path):
    ws_name = "test-ws-app-configs"
    ws_root = workspace.root(ws_name)
    ws = None

    if os.path.exists(ws_root):
        shutil.rmtree(ws_root)

    try:
        ws = workspace.create(ws_name)
        workspace.activate(ws)

        ws.application_configs = {
            "app_conf_1": {
                "filename": "app_conf_1.yaml",
                "path": "/fake/path/app_conf_1.yaml",
                "raw_yaml": None,
                "yaml": {
                    ramble.namespace.namespace.application: {
                        "builtin.app.wrfv3@3.9": {ramble.namespace.namespace.workload: {}},
                        "hostname@2.0": {ramble.namespace.namespace.workload: {}},
                        "basic": {ramble.namespace.namespace.workload: {}},
                    }
                },
            }
        }

        apps = {}
        for contents, app_context in ws.all_applications():
            apps[app_context.context_name] = contents.get(ramble.namespace.namespace.version)

        assert "builtin.app.wrfv3" in apps
        assert apps["builtin.app.wrfv3"] == "3.9"
        assert "hostname" in apps
        assert apps["hostname"] == "2.0"
        assert "basic" in apps
        assert apps["basic"] is None
    finally:
        if ws:
            workspace.deactivate()
        if os.path.exists(ws_root):
            shutil.rmtree(ws_root)
