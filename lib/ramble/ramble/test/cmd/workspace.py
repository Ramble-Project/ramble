# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import glob
import os
import re

import pytest

import llnl.util.filesystem as fs

import ramble.config
import ramble.filters
import ramble.pipeline
import ramble.workspace
from ramble.error import RambleCommandError
from ramble.main import RambleCommand, main
from ramble.namespace import namespace
from ramble.test.dry_run_helpers import search_files_for_string

import spack.util.spack_yaml as syaml

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
    "mutable_mock_apps_repo",
    "workspace_deactivate",
)

config = RambleCommand("config")
workspace = RambleCommand("workspace")
on = RambleCommand("on")


def add_basic(ws):
    ramble.config.add(
        "applications:basic:workloads:test_wl:experiments:" + "{}",
        scope=ws.ws_file_config_scope_name(),
    )
    ramble.config.add(
        "applications:basic:workloads:test_wl2:experiments:" + "{}",
        scope=ws.ws_file_config_scope_name(),
    )
    ws.write()
    ws._re_read()


def remove_basic(ws):
    ramble.config.set("applications", syaml.syaml_dict(), scope=ws.ws_file_config_scope_name())

    ws.write()
    ws._re_read()


def check_basic(ws):
    found_basic = False
    found_test_wl = False
    found_test_wl2 = False

    for workloads, application_context in ws.all_applications():
        if application_context.context_name == "basic":
            found_basic = True
        for _, workload_context in ws.all_workloads(workloads):
            if workload_context.context_name == "test_wl":
                found_test_wl = True
            elif workload_context.context_name == "test_wl2":
                found_test_wl2 = True

    assert found_basic
    assert found_test_wl
    assert found_test_wl2


def check_no_basic(ws):
    found_basic = False
    found_test_wl = False
    found_test_wl2 = False

    for workloads, application_context in ws.all_applications():
        if application_context.context_name == "basic":
            found_basic = True
        for _, workload_context in ws.all_workloads(workloads):
            if workload_context.context_name == "test_wl":
                found_test_wl = True
            elif workload_context.context_name == "test_wl2":
                found_test_wl2 = True

    assert not found_basic
    assert not found_test_wl
    assert not found_test_wl2


def check_info_basic(output):
    assert "basic" in output
    assert "test_wl" in output
    assert "test_wl2" in output

    assert "Application" in output
    assert "Workload" in output
    assert "Experiment" in output
    assert "Software Stack" in output


def check_results(ws):
    fn = ws.dump_results(output_formats=["text", "json", "yaml"])
    assert os.path.exists(os.path.join(ws.results_dir, fn + ".txt"))
    assert os.path.exists(os.path.join(ws.results_dir, fn + ".json"))
    assert os.path.exists(os.path.join(ws.results_dir, fn + ".yaml"))


def test_workspace_create_links(mutable_mock_workspace_path, tmpdir):
    import pathlib

    expected_links = ["software", "inputs"]
    with tmpdir.as_cwd():
        workspace("create", "-d", "foo")
        workspace(
            "create", "-d", "bar", "--inputs-dir", "foo/inputs", "--software-dir", "foo/software"
        )

        for expected_link in expected_links:
            assert os.path.exists(os.path.join("bar", expected_link))
            assert os.path.islink(os.path.join("bar", expected_link))
            resolved_path = pathlib.PosixPath(os.path.join("bar", expected_link)).resolve()
            assert str(resolved_path) == os.path.abspath(os.path.join("foo", expected_link))


def test_workspace_activate_fails(mutable_mock_workspace_path):
    workspace("create", "foo")
    out = workspace("activate", "foo")
    assert "To set up shell support" in out


def test_workspace_activate_prompt(workspace_name, monkeypatch):
    monkeypatch.delenv("TERM", raising=False)
    ramble.workspace.deactivate()
    ws = ramble.workspace.create(workspace_name)
    ws.write()

    # Assert no prompt modification
    output = workspace("activate", workspace_name, "--sh")
    assert "PS1" not in output

    # Assert prompt mod with --prompt
    output = workspace("activate", workspace_name, "--sh", "--prompt")
    assert "export RAMBLE_OLD_PS1=" in output
    assert "export PS1=" in output
    assert f"[{workspace_name}]" in output
    assert "${PS1}" in output

    # Assert prompt mod with config value
    with ramble.config.override("config:enable_workspace_prompt", True):
        output = workspace("activate", workspace_name, "--sh")
        assert "export RAMBLE_OLD_PS1=" in output
        assert "export PS1=" in output
        assert f"[{workspace_name}]" in output
        assert "${PS1}" in output


def test_workspace_activate_by_name(workspace_name):
    ws = ramble.workspace.create(workspace_name)
    ws.write()

    output = workspace("activate", workspace_name, "--sh")
    assert f"export RAMBLE_WORKSPACE={ws.root}" in output


def test_workspace_activate_by_dir(tmpdir):
    with tmpdir.as_cwd():
        workspace("create", "-d", "foo")
        output = workspace("activate", "--dir", "foo", "--sh")
        ws_path = os.path.abspath("foo")
        assert f"export RAMBLE_WORKSPACE={ws_path}" in output


def test_workspace_activate_temp():
    """Test `ramble workspace activate --temp`."""
    # Test without prompt decoration
    output = workspace("activate", "--temp", "--sh")

    match = re.search(r"export RAMBLE_WORKSPACE=([^;]+)", output)
    workspace_path = match.group(1)

    assert os.path.isdir(workspace_path)
    assert ramble.workspace.is_workspace_dir(workspace_path)


def test_workspace_activate_non_existent():
    output = workspace("activate", "non-existent-ws", "--sh", fail_on_error=False)
    assert "No such workspace: 'non-existent-ws'" in output


def test_workspace_activate_no_args():
    output = workspace("activate", fail_on_error=False)
    assert "ramble workspace activate requires a workspace name, directory, or --temp" in output


def test_workspace_deactivate(workspace_name, working_env):
    """Test `ramble workspace deactivate`."""
    ws = ramble.workspace.create(workspace_name)
    ws.write()

    # Test deactivation of a workspace
    ramble.workspace.activate(ws)
    output = workspace("deactivate", "--sh")
    assert "unset RAMBLE_WORKSPACE;" in output
    ramble.workspace.deactivate()

    # Test deactivation restores prompt
    ramble.workspace.activate(ws)
    os.environ["RAMBLE_OLD_PS1"] = "old_prompt"
    output = workspace("deactivate", "--sh")
    assert 'PS1="$RAMBLE_OLD_PS1";' in output
    assert "unset RAMBLE_OLD_PS1;" in output
    del os.environ["RAMBLE_OLD_PS1"]
    ramble.workspace.deactivate()

    # Test deactivation fails when no workspace is active
    if ramble.workspace.RAMBLE_WORKSPACE_VAR in os.environ:
        del os.environ[ramble.workspace.RAMBLE_WORKSPACE_VAR]
    output = workspace("deactivate", "--sh", fail_on_error=False)
    assert "No workspace is currently active." in output

    # Test deactivation fails without shell args
    output = workspace("deactivate", fail_on_error=False)
    assert "To set up shell support" in output

    # Test deactivation fails with ambiguous flags
    ramble.workspace.activate(ws)
    output = workspace(
        "deactivate", "--sh", global_args=["-w", workspace_name], fail_on_error=False
    )
    assert "is ambiguous" in output


def test_workspace_list(mutable_mock_workspace_path):
    workspace("create", "foo")
    workspace("create", "bar")
    workspace("create", "baz")

    out = workspace("list")

    assert "foo" in out
    assert "bar" in out
    assert "baz" in out

    # make sure `ramble workspace list` skips invalid things in
    # var/ramble/workspaces
    mutable_mock_workspace_path.join(".DS_Store").ensure(file=True)
    out = workspace("list")

    assert "foo" in out
    assert "bar" in out
    assert "baz" in out
    assert ".DS_Store" not in out


def test_workspace_list_empty(mutable_mock_workspace_path):
    out = workspace("list")
    assert workspace.returncode == 0
    assert "No workspaces found." in out

    out = workspace("list", "--merged")
    assert workspace.returncode == 0
    assert "No workspaces found." in out


def test_workspace_info(workspace_name):
    global_args = ["-w", workspace_name]
    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    workspace(
        "manage",
        "experiments",
        "basic",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=2",
        global_args=global_args,
    )
    workspace(
        "manage",
        "experiments",
        "zlib",
        "-V",
        "package_manager=spack",
        "--wf",
        "ensure_installed",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=2",
        global_args=global_args,
    )
    workspace("concretize", global_args=global_args)
    ws1._re_read()

    output = workspace("info", "--software", global_args=global_args)

    check_info_basic(output)


def test_workspace_info_namespaced_application(workspace_name, mutable_mock_apps_repo):
    global_args = ["-w", workspace_name]
    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config("add", "config:enable_strict_versions:false", global_args=global_args)

    workspace(
        "manage",
        "experiments",
        "builtin.mock.app.basic",
        "--wf",
        "test_wl",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=2",
        global_args=global_args,
    )
    workspace(
        "manage",
        "experiments",
        "basic@1.0",
        "--wf",
        "test_wl",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=1",
        global_args=global_args,
    )
    workspace(
        "manage",
        "experiments",
        "builtin.mock.basic",
        "--wf",
        "test_wl",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=3",
        global_args=global_args,
    )
    workspace(
        "manage",
        "experiments",
        "app.basic",
        "--wf",
        "test_wl",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=4",
        global_args=global_args,
    )
    ws1._re_read()

    output = workspace("info", global_args=global_args)

    assert "Application: builtin.mock.app.basic" in output
    assert "Application: basic" in output
    assert "Application: builtin.mock.basic" in output
    assert "Application: app.basic" in output
    assert "builtin.mock.app.basic.test_wl.test_experiment" in output
    assert "basic@1.0.test_wl.test_experiment" in output
    assert "builtin.mock.basic.test_wl.test_experiment" in output
    assert "app.basic.test_wl.test_experiment" in output


def test_workspace_info_prints_all_levels(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      variables:
        application_level: '1'
      workloads:
        test_wl:
          variables:
            workload_level: '1'
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
    zlib:
      variants:
        package_manager: spack
      workloads:
        ensure_installed:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
  software:
    packages:
      zlib:
        pkg_spec: 'zlib'
    environments:
      zlib:
        packages:
        - zlib
"""

    config_file = """
config:
  variables:
    conf_level: 1
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    ramble_config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)
    config_scope_path = os.path.join(ws1.config_dir, "config.yaml")

    with open(ramble_config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    with open(config_scope_path, "w+", encoding="utf-8") as f:
        f.write(config_file)

    ws1._re_read()

    output = workspace("info", "--expansions", global_args=["-w", workspace_name])
    assert "Variables from Config:" in output
    assert "Variables from Workspace:" in output
    assert "Variables from Application:" in output
    assert "Variables from Workload:" in output
    assert "Variables from Experiment:" in output


def test_workspace_info_with_experiment_chain(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment:
              template: true
              variables:
                n_nodes: '2'
                processes_per_node: '5'
                n_ranks: '10'
        test_wl2:
          experiments:
            test_experiment:
              chained_experiments:
              - name: basic.test_wl.test_experiment
                order: 'after_root'
                command: '{execute_experiment}'
              variables:
                n_nodes: '2'
                processes_per_node: '5'
                n_ranks: '10'

  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    output = workspace("info", "-vv", global_args=["-w", workspace_name])

    assert "Experiment Chain:" in output
    assert "- basic.test_wl2.test_experiment.chain.0.basic.test_wl.test_experiment" in output


def test_workspace_info_with_where_filter(workspace_name):
    global_args = ["-w", workspace_name]
    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=2",
        global_args=global_args,
    )
    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl2",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=2",
        global_args=global_args,
    )
    workspace(
        "manage",
        "experiments",
        "zlib",
        "-V",
        "package_manager=spack",
        "--wf",
        "ensure_installed",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=2",
        global_args=global_args,
    )
    workspace("concretize", global_args=global_args)
    ws1._re_read()

    output = workspace(
        "info",
        "--software",
        "--where",
        '"{experiment_index}" == "1"',
        global_args=global_args,
    )

    assert "basic.test_wl.test_experiment" in output
    assert "basic.test_wl2.test_experiment" not in output
    assert "zlib.ensure_installed.test_experiment" not in output


def test_workspace_info_phases(workspace_name):
    global_args = ["-w", workspace_name]
    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    workspace(
        "manage",
        "experiments",
        "basic",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=2",
        global_args=global_args,
    )
    workspace(
        "manage",
        "experiments",
        "zlib",
        "--wf",
        "ensure_installed",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=2",
        global_args=global_args,
    )
    ws1._re_read()

    output = workspace("info", "--phases", global_args=global_args)

    assert "basic" in output
    assert "test_wl" in output
    assert "test_wl2" in output
    assert "Application" in output
    assert "Workload" in output
    assert "Experiment" in output

    assert "Phases for analyze pipeline:" in output
    assert "analyze_experiments" in output


def test_workspace_info_complete(workspace_name):
    global_args = ["-w", workspace_name]
    ws = ramble.workspace.create(workspace_name)
    ws.write()

    workspace(
        "manage",
        "experiments",
        "zlib",
        "-V",
        "package_manager=spack",
        "--wf",
        "ensure_installed",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    workspace("concretize", global_args=global_args)

    ws._re_read()

    output = workspace(
        "info",
        "-vv",
        "--phases",
        "--variants",
        "--all-software",
        global_args=["-w", workspace_name],
    )

    assert "All experiment tags" in output

    assert "zlib.ensure_installed.generated" in output
    for pipeline in [
        "analyze",
        "archive",
        "execute",
        "logs",
        "mirror",
        "pushdeployment",
        "pushtocache",
        "setup",
    ]:
        assert f"Phases for {pipeline}" in output

    assert "Variants:" in output
    assert "package_manager=spack" in output

    assert "Variables from Workspace" in output
    assert "Variables from Experiment" in output
    assert "n_ranks = 1 ==> 1" in output

    assert "Executables" in output
    assert "builtin::env_vars" in output
    assert "package_manager_builtin::spack::spack_source" in output
    assert "list_lib" in output

    assert "Software Stack" in output
    assert "Template package: zlib" in output
    assert "Template package: zlib" in output
    assert "Spec: zlib" in output
    assert "Template environment: zlib" in output
    assert "- zlib = zlib" in output


def test_workspace_dir(tmpdir):
    with tmpdir.as_cwd():
        workspace("create", "-d", ".")
        assert os.path.exists(tmpdir + "/configs/ramble.yaml")
        num_templates = 0
        for filename in os.listdir(tmpdir + "/configs"):
            if filename.endswith(".tpl"):
                num_templates += 1

        assert num_templates > 0


def test_workspace_from_template(tmpdir):
    with tmpdir.as_cwd():
        tpl_in = """
cd "{experiment_run_dir}"

cmake -DTEST=1 -h

{command}
        """
        tpl_path = os.path.join(tmpdir, "tmp_test.tpl")
        with open(tpl_path, "w+", encoding="utf-8") as f:
            f.write(tpl_in)

        assert os.path.exists(tpl_path)

        workspace("create", "-d", "-t", tpl_path, ".")

        assert os.path.exists(tmpdir + "/configs/tmp_test.tpl")
        assert os.path.exists(tmpdir + "/configs/ramble.yaml")
        num_templates = 0
        for filename in os.listdir(tmpdir + "/configs"):
            if filename.endswith(".tpl"):
                num_templates += 1

        assert num_templates > 0


def test_workspace_dirs(tmpdir, mutable_mock_workspace_path):
    with tmpdir.as_cwd():
        # Make a temp directory,
        # Set it up as the workspace_dirs path,
        # make a test workspace there, and
        # verify the workspace was created where
        # it would be expected
        wsdir1 = os.path.join(os.getcwd(), "ws1")
        os.makedirs(wsdir1)
        with ramble.config.override("config:workspace_dirs", wsdir1):
            workspace("create", "test1")
            out = workspace("list")
        assert "test1" in out

        # Now make a second temp directory,
        # follow same process to make another test
        # workspace, and verify that the first
        # test workspace is not found while the
        # second is
        wsdir2 = os.path.join(os.getcwd(), "ws2")
        os.makedirs(wsdir2)
        with ramble.config.override("config:workspace_dirs", wsdir2):
            workspace("create", "test2")
            out = workspace("list")
        assert "test2" in out
        assert "test1" not in out


def test_workspace_create_parent_dir(tmpdir, mutable_mock_workspace_path):
    with tmpdir.as_cwd():
        wsdir1 = os.path.join(os.getcwd(), "ws1")
        wsdir2 = os.path.join(os.getcwd(), "ws2")
        os.makedirs(wsdir1)
        os.makedirs(wsdir2)

        with ramble.config.override("config:workspace_dirs", [wsdir1, wsdir2]):
            # Create in default (wsdir1)
            workspace("create", "test_default")
            assert os.path.exists(os.path.join(wsdir1, "test_default"))

            # Create in wsdir2 using --parent-dir
            workspace("create", "--parent-dir", wsdir2, "test_specific")
            assert os.path.exists(os.path.join(wsdir2, "test_specific"))

            # Verify both are listed
            out = workspace("list")
            assert "test_default" in out
            assert "test_specific" in out

        # Test validation of parent-dir
        with ramble.config.override("config:workspace_dirs", [wsdir1]):
            with pytest.raises(
                ramble.workspace.RambleWorkspaceError,
                match="is not in configured workspace_dirs",
            ):
                ramble.workspace.create("test_fail", parent_dir=wsdir2)


def test_workspace_list_parent_dir(tmpdir, mutable_mock_workspace_path):
    with tmpdir.as_cwd():
        wsdir1 = os.path.join(os.getcwd(), "ws1")
        wsdir2 = os.path.join(os.getcwd(), "ws2")
        os.makedirs(wsdir1)
        os.makedirs(wsdir2)

        with ramble.config.override("config:workspace_dirs", [wsdir1, wsdir2]):
            workspace("create", "--parent-dir", wsdir1, "test1")
            workspace("create", "--parent-dir", wsdir2, "test2")

            # List all (default grouped by section)
            out = workspace("list")
            assert f"Workspaces from dir: {wsdir1}" in out
            assert f"Workspaces from dir: {wsdir2}" in out
            assert "test1" in out
            assert "test2" in out

            # List merged version
            out = workspace("list", "--merged")
            assert f"Workspaces from dir: {wsdir1}" not in out
            assert f"Workspaces from dir: {wsdir2}" not in out
            assert "test1" in out
            assert "test2" in out

            # List only ws1
            out = workspace("list", "--parent-dir", wsdir1)
            assert f"Workspaces from dir: {wsdir1}" in out
            assert "test1" in out
            assert "test2" not in out

            # List only ws2
            out = workspace("list", "--parent-dir", wsdir2)
            assert f"Workspaces from dir: {wsdir2}" in out
            assert "test1" not in out
            assert "test2" in out

        # Test validation of parent-dir in list
        with ramble.config.override("config:workspace_dirs", [wsdir1]):
            with pytest.raises(
                ramble.workspace.RambleWorkspaceError,
                match="is not in configured workspace_dirs",
            ):
                ramble.workspace.all_workspace_names(parent_dir=wsdir2)


def test_workspace_activate_parent_dir(tmpdir, mutable_mock_workspace_path):
    with tmpdir.as_cwd():
        wsdir1 = os.path.join(os.getcwd(), "ws1")
        wsdir2 = os.path.join(os.getcwd(), "ws2")
        os.makedirs(wsdir1)
        os.makedirs(wsdir2)

        with ramble.config.override("config:workspace_dirs", [wsdir1, wsdir2]):
            workspace("create", "--parent-dir", wsdir1, "test1")
            workspace("create", "--parent-dir", wsdir2, "test1")

            # Activate without parent-dir (should pick first one, wsdir1)
            out = workspace("activate", "test1", "--sh")
            assert wsdir1 in out

            # Activate with parent-dir wsdir1
            out = workspace("activate", "test1", "--parent-dir", wsdir1, "--sh")
            assert wsdir1 in out

            # Activate with parent-dir wsdir2
            out = workspace("activate", "test1", "--parent-dir", wsdir2, "--sh")
            assert wsdir2 in out

        # Test validation of parent-dir in activate (via exists)
        with ramble.config.override("config:workspace_dirs", [wsdir1]):
            with pytest.raises(
                ramble.workspace.RambleWorkspaceError,
                match="is not in configured workspace_dirs",
            ):
                ramble.workspace.exists("test1", parent_dir=wsdir2)


def test_remove_workspace():
    workspace("create", "foo")
    workspace("create", "bar")

    out = workspace("list")
    assert "foo" in out
    assert "bar" in out

    workspace("remove", "-y", "foo")
    out = workspace("list")
    assert "foo" not in out
    assert "bar" in out

    workspace("remove", "-y", "bar")
    out = workspace("list")
    assert "foo" not in out
    assert "bar" not in out


def test_concretize_command(workspace_name):
    global_args = ["-w", workspace_name]
    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    workspace(
        "manage",
        "experiments",
        "basic",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=2",
        global_args=global_args,
    )
    workspace(
        "manage",
        "experiments",
        "zlib",
        "-V",
        "package_manager=spack",
        "--wf",
        "ensure_installed",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=2",
        global_args=global_args,
    )

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    assert search_files_for_string([config_path], "packages: {}")
    assert not search_files_for_string([config_path], "pkg_spec: zlib")

    workspace("concretize", global_args=global_args)

    assert not search_files_for_string([config_path], "packages: {}")
    assert search_files_for_string([config_path], "pkg_spec: zlib")


def test_concretize_nothing():
    ws_name = "test"
    workspace("create", ws_name)
    assert ws_name in workspace("list")

    with ramble.workspace.read(ws_name) as ws:
        add_basic(ws)
        check_basic(ws)

        assert search_files_for_string([ws.config_file_path], "packages: {}")
        assert not search_files_for_string([ws.config_file_path], "pkg_spec:")

        ws.concretize()

        assert search_files_for_string([ws.config_file_path], "packages: {}")
        assert not search_files_for_string([ws.config_file_path], "pkg_spec:")


def test_concretize_concrete_config(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
        test_wl2:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
    zlib:
      variants:
        package_manager: spack
      workloads:
        ensure_installed:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
  software:
    packages:
      zlib:
        pkg_spec: 'zlib@1.3'
    environments:
      zlib:
        packages:
        - zlib
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    with pytest.raises(
        ramble.workspace.RambleWorkspaceError,
        match="Package zlib would be defined in multiple conflicting ways",
    ):
        workspace("concretize", global_args=["-w", workspace_name])


def test_force_concretize(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
        test_wl2:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
    zlib:
      variants:
        package_manager: spack
      workloads:
        ensure_installed:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
  software:
    packages:
      zlib-test:
        pkg_spec: 'zlib-test'
    environments:
      zlib-test:
        packages:
        - zlib-test
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    workspace("concretize", "-f", global_args=["-w", workspace_name])

    assert search_files_for_string([config_path], "zlib:")
    assert search_files_for_string([config_path], "zlib-test")

    workspace("concretize", "--simplify", global_args=["-w", workspace_name])

    assert search_files_for_string([config_path], "zlib:")
    assert not search_files_for_string([config_path], "zlib-test")


def test_setup_command():
    ws_name = "test"
    workspace("create", ws_name)

    with ramble.workspace.read("test") as ws:
        add_basic(ws)
        check_basic(ws)

        workspace("concretize")

        workspace("setup")
        assert os.path.exists(ws.root + "/all_experiments")


def test_setup_command_with_missing_log_dir():
    ws_name = "test"
    workspace("create", ws_name)

    with ramble.workspace.read("test") as ws:
        add_basic(ws)
        check_basic(ws)
        # Missing log directory shouldn't prevent workspace
        # setup, as long as the workspace is considered valid
        # by the `is_workspace_dir` check.
        os.rmdir(ws.log_dir)

        workspace("concretize")

        workspace("setup")
        assert os.path.exists(ws.root + "/all_experiments")


def test_setup_nothing():
    ws_name = "test"
    workspace("create", ws_name)
    assert ws_name in workspace("list")
    pipeline_type = ramble.pipeline.pipelines.setup
    pipeline_cls = ramble.pipeline.pipeline_class(pipeline_type)
    filters = ramble.filters.Filters()

    with ramble.workspace.read(ws_name) as ws:
        add_basic(ws)
        check_basic(ws)

        ws.concretize()

        setup_pipeline = pipeline_cls(ws, filters)
        setup_pipeline.run()
        assert os.path.exists(ws.root + "/all_experiments")


def test_anlyze_command():
    ws_name = "test"
    workspace("create", ws_name)

    with ramble.workspace.read("test") as ws:
        add_basic(ws)
        check_basic(ws)

        workspace("concretize")

        workspace("setup")
        assert os.path.exists(ws.root + "/all_experiments")

        workspace("analyze")
        check_results(ws)


def test_analyze_nothing():
    ws_name = "test"
    workspace("create", ws_name)
    assert ws_name in workspace("list")
    setup_type = ramble.pipeline.pipelines.setup
    setup_cls = ramble.pipeline.pipeline_class(setup_type)
    analyze_type = ramble.pipeline.pipelines.analyze
    analyze_cls = ramble.pipeline.pipeline_class(analyze_type)
    filters = ramble.filters.Filters()

    with ramble.workspace.read(ws_name) as ws:
        add_basic(ws)
        check_basic(ws)

        ws.concretize()

        setup_pipeline = setup_cls(ws, filters)
        setup_pipeline.run()
        assert os.path.exists(ws.root + "/all_experiments")

        analyze_pipeline = analyze_cls(ws, filters)
        analyze_pipeline.run()
        check_results(ws)


def test_workspace_flag_named():
    ws_name = "test_ws_flag"
    workspace("create", ws_name)
    assert ws_name in workspace("list")

    flag_args = ["-w", ws_name]

    with ramble.workspace.read(ws_name) as ws:
        add_basic(ws)
        check_basic(ws)

    workspace("concretize", global_args=flag_args)

    workspace("setup", global_args=flag_args)
    with ramble.workspace.read(ws_name) as ws:
        assert os.path.exists(ws.root + "/all_experiments")

    workspace("analyze", global_args=flag_args)
    with ramble.workspace.read(ws_name) as ws:
        check_results(ws)

    with ramble.workspace.read(ws_name) as ws:
        remove_basic(ws)
        check_no_basic(ws)


def test_workspace_flag_anon(tmpdir):
    ws_path = str(tmpdir.join("test_ws_dir_flag"))
    workspace("create", "-d", ws_path)
    assert ramble.workspace.is_workspace_dir(ws_path)

    flag_args = ["-D", ws_path]

    with ramble.workspace.Workspace(ws_path) as ws:
        add_basic(ws)
        check_basic(ws)

    workspace("concretize", global_args=flag_args)

    workspace("setup", global_args=flag_args)
    with ramble.workspace.Workspace(ws_path) as ws:
        assert os.path.exists(ws.root + "/all_experiments")

    workspace("analyze", global_args=flag_args)
    with ramble.workspace.Workspace(ws_path) as ws:
        check_results(ws)

    with ramble.workspace.Workspace(ws_path) as ws:
        remove_basic(ws)
        check_no_basic(ws)


def test_no_workspace_flag():
    ws_name = "test_no_ws_flag"
    workspace("create", ws_name)
    assert ws_name in workspace("list")

    flag_args = ["-W"]
    with ramble.workspace.read(ws_name) as ws:
        ramble.workspace.activate(ws)
        add_basic(ws)
        check_basic(ws)

        with pytest.raises(RambleCommandError):
            workspace("concretize", global_args=flag_args)
        ramble.workspace.activate(ws)
        workspace("concretize")

        with pytest.raises(RambleCommandError):
            workspace("setup", global_args=flag_args)
        ramble.workspace.activate(ws)
        workspace("setup")
        assert os.path.exists(ws.root + "/all_experiments")

        with pytest.raises(RambleCommandError):
            workspace("analyze", global_args=flag_args)
        ramble.workspace.activate(ws)
        workspace("analyze")
        check_results(ws)

        ramble.workspace.activate(ws)
        remove_basic(ws)
        check_no_basic(ws)


def test_edit_edits_correct_paths():
    ws = ramble.workspace.create("test")
    ws.write()

    config_file = ramble.workspace.config_file(ws.root)
    default_template_path = ws.template_path("execute_experiment")
    experiments_test_file = os.path.join(ws.experiment_dir, "test")

    ws_args = ["-w", "test"]
    assert (
        workspace("edit", "-f", "ramble.yaml", "--print-file", global_args=ws_args).strip()
        == config_file
    )
    assert (
        workspace(
            "edit", "-f", "{workspace_experiments}/test", "--print-file", global_args=ws_args
        ).strip()
        == experiments_test_file
    )
    assert workspace("edit", "-c", "--print-file", global_args=ws_args).strip() == config_file
    assert (
        workspace("edit", "-t", "--print-file", global_args=ws_args).strip()
        == default_template_path
    )


def test_edit_fails_without_workspace():
    output = workspace("edit", global_args=["-W"], fail_on_error=False)
    assert (
        "ramble workspace edit requires either a "
        + "command line workspace or an active workspace"
        in output
    )


def test_edit_override_gets_correct_path():
    ws1 = ramble.workspace.create("test1")
    ws2 = ramble.workspace.create("test2")

    ws1.write()
    ws2.write()

    config_path = ramble.workspace.config_file(ws2.root)

    with ws1:
        ws_args = ["-D", ws2.root]
        output = workspace("edit", "-c", "--print-file", global_args=ws_args).strip()
        assert output == config_path


def test_edit_with_faulty_config(workspace_name, capsys):
    """Tests that `ramble workspace edit` works with a faulty config."""
    bad_config = """
ramble # Missing colon!
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: 1
    n_nodes: 1
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment: {}
"""
    try:
        ws = ramble.workspace.create(workspace_name)
        ws.write()

        config_path = os.path.join(ws.config_dir, ramble.workspace.CONFIG_FILE_NAME)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(bad_config)

        argv = ["-w", workspace_name, "workspace", "edit", "-c", "-p"]
        # Use main instead of RambleCommand, as this tests the error handling
        # only in the former.
        main(argv)
        captured = capsys.readouterr()
        assert config_path in captured.out
    finally:
        main(["-w", workspace_name, "workspace", "remove", "-y"])


def test_dryrun_setup(workspace_name):
    global_args = ["-w", workspace_name]
    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=2",
        global_args=global_args,
    )

    workspace("setup", "--dry-run", global_args=global_args)

    out_files = glob.glob(os.path.join(ws1.log_dir, "**", "*.out"), recursive=True)

    assert search_files_for_string(out_files, "Would download file:///tmp/test_file.log")
    assert os.path.exists(
        os.path.join(
            ws1.root, "experiments", "basic", "test_wl", "test_experiment", "execute_experiment"
        )
    )


def test_matrix_vector_workspace_full(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: [2, 4]
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      variables:
        cells: [5, 10]
      workloads:
        test_wl:
          experiments:
            exp_series_{idx}_{n_nodes}_{cells}_{processes_per_node}:
              variables:
                n_nodes: [1, 2, 4]
                idx: [1, 2, 3, 4, 5, 6]
              matrices:
               - - cells
                 - n_nodes
               - - idx
  software:
    packages: {}
    environments: {}
"""

    # Should be ppn * ( cells * n_nodes, idx ) = 12
    expected_experiments = set()
    expected_experiments.add("exp_series_1_1_5_2")
    expected_experiments.add("exp_series_1_1_5_4")
    expected_experiments.add("exp_series_4_1_10_2")
    expected_experiments.add("exp_series_4_1_10_4")
    expected_experiments.add("exp_series_2_2_5_2")
    expected_experiments.add("exp_series_2_2_5_4")
    expected_experiments.add("exp_series_5_2_10_2")
    expected_experiments.add("exp_series_5_2_10_4")
    expected_experiments.add("exp_series_3_4_5_2")
    expected_experiments.add("exp_series_3_4_5_4")
    expected_experiments.add("exp_series_6_4_10_2")
    expected_experiments.add("exp_series_6_4_10_4")

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    workspace_flags = ["-w", workspace_name]

    output = workspace("info", global_args=workspace_flags)

    for exp in expected_experiments:
        assert exp in output

    workspace("setup", "--dry-run", global_args=workspace_flags)

    out_files = glob.glob(os.path.join(ws1.log_dir, "**", "*.out"), recursive=True)

    assert search_files_for_string(out_files, "Would download file:///tmp/test_file.log")

    exp_base = os.path.join(ws1.experiment_dir, "basic", "test_wl")
    for exp in expected_experiments:
        assert os.path.exists(os.path.join(exp_base, exp))


def test_invalid_vector_workspace(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: [2, 4]
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      variables:
        cells: [5, 10]
      workloads:
        test_wl:
          experiments:
            exp_series_{idx}_{n_nodes}_{cells}_{processes_per_node}:
              variables:
                n_nodes: [1, 2, 4]
                idx: [1, 2, 3, 4, 5, 6]
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    workspace_flags = ["-w", workspace_name]

    output = workspace("info", global_args=workspace_flags, fail_on_error=False)
    assert (
        "Length mismatch in vector variables in "
        + "experiment exp_series_{idx}_{n_nodes}_{cells}_{processes_per_node}"
        in output
    )

    output = workspace("setup", "--dry-run", global_args=workspace_flags, fail_on_error=False)

    assert (
        "Length mismatch in vector variables in "
        + "experiment exp_series_{idx}_{n_nodes}_{cells}_{processes_per_node}"
        in output
    )


def test_invalid_size_matrices_workspace(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            exp_series_{idx}_{n_nodes}_{cells}_{processes_per_node}:
              variables:
                n_nodes: [1, 2, 4]
                idx: [1, 2, 3, 4, 5, 6]
              matrices:
                - - n_nodes
                - - idx
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    workspace_flags = ["-w", workspace_name]

    output = workspace("info", global_args=workspace_flags, fail_on_error=False)
    assert "Matrices defined in experiment" in output
    assert "do not result in the same number of elements." in output

    output = workspace("setup", "--dry-run", global_args=workspace_flags, fail_on_error=False)

    assert "Matrices defined in experiment" in output
    assert "do not result in the same number of elements." in output


def test_undefined_var_matrices_workspace(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            exp_series_{foo}:
              matrices:
                - - foo
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    workspace_flags = ["-w", workspace_name]

    output = workspace("info", global_args=workspace_flags, fail_on_error=False)
    assert "variable or zip foo has not been defined yet" in output

    output = workspace("setup", "--dry-run", global_args=workspace_flags, fail_on_error=False)
    assert "variable or zip foo has not been defined yet" in output


def test_non_vector_var_matrices_workspace(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            exp_series_{foo}:
              variables:
                foo: '1'
              matrices:
                - - foo
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    workspace_flags = ["-w", workspace_name]

    output = workspace("info", global_args=workspace_flags, fail_on_error=False)
    assert "variable foo does not refer to a vector" in output

    output = workspace("setup", "--dry-run", global_args=workspace_flags, fail_on_error=False)
    assert "variable foo does not refer to a vector" in output


def test_multi_use_vector_var_matrices_workspace(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            exp_series_{foo}:
              variables:
                foo: [1, 2, 3, 4]
              matrices:
                - - foo
                - - foo
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    workspace_flags = ["-w", workspace_name]

    output = workspace("info", global_args=workspace_flags, fail_on_error=False)
    assert "Variable foo has been used in multiple matrices" in output

    output = workspace("setup", "--dry-run", global_args=workspace_flags, fail_on_error=False)
    assert "Variable foo has been used in multiple matrices" in output


def test_reconcretize_in_configs_dir(tmpdir, workspace_name):
    """
    Test multiple concretizations while the configs dir is the cwd do not fail.
    This catches a bug that existed when lock files were written incorrectly.
    """
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun'
    batch_submit: '{execute_experiment}'
    n_ranks: '1'
    n_nodes: '1'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            exp_series_{foo}:
              variables:
                foo: 1
  software:
    packages: {}
    environments: {}
"""

    def write_config(ws_path, config):
        with ramble.workspace.Workspace(ws_path) as ws:
            config_path = os.path.join(ws.config_dir, ramble.workspace.CONFIG_FILE_NAME)
            with open(config_path, "w+", encoding="utf-8") as f:
                f.write(config)
            ws._re_read()

    ws_path = str(tmpdir.join(workspace_name))
    workspace("create", "-d", ws_path)
    assert ramble.workspace.is_workspace_dir(ws_path)

    workspace_flags = ["-D", ws_path]

    config_path = os.path.join(ws_path, "configs")
    with fs.working_dir(config_path):
        write_config(ws_path, test_config)

        with ramble.workspace.Workspace(ws_path):
            software_dict = ramble.config.get(namespace.software)
            print(f"software_dict before = {software_dict}")

        workspace("concretize", global_args=workspace_flags)

        with ramble.workspace.Workspace(ws_path):
            software_dict = ramble.config.get(namespace.software)
            assert namespace.environments in software_dict

        write_config(ws_path, test_config)

        workspace("concretize", global_args=workspace_flags)
        with ramble.workspace.Workspace(ws_path):
            software_dict = ramble.config.get(namespace.software)
            assert namespace.environments in software_dict


def test_workspace_archive(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
  software:
    packages: {}
    environments: {}
"""

    test_licenses = """
licenses:
  basic:
    set:
      TEST_LIC: 'value'
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)
    lic_path = os.path.join(ws1.config_dir, "licenses.yaml")

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    with open(lic_path, "w+", encoding="utf-8") as f:
        f.write(test_licenses)

    # Create more templates, and test files to archive
    new_templates = []
    for i in range(5):
        new_template = os.path.join(ws1.config_dir, f"test_template.{i}")
        new_templates.append(new_template)
        f = open(new_template, "w+", encoding="utf-8")
        f.close()

        new_archive_file = os.path.join(ws1.root, f"test_pattern.{i}")
        with open(new_archive_file, "w+", encoding="utf-8") as f:
            f.write("Test archive file")

    ws1._re_read()

    workspace("setup", "--dry-run", global_args=["-w", workspace_name])
    experiment_dir = os.path.join(ws1.root, "experiments", "basic", "test_wl", "test_experiment")
    out_files = glob.glob(os.path.join(ws1.log_dir, "**", "*.out"), recursive=True)

    assert search_files_for_string(out_files, "Would download file:///tmp/test_file.log")
    assert os.path.exists(os.path.join(experiment_dir, "execute_experiment"))

    # Create files that match archive pattern
    new_files = []
    for i in range(5):
        new_name = f"archive_test.{i}"
        new_file = os.path.join(experiment_dir, new_name)

        new_files.append(new_file)
        f = open(new_file, "w+", encoding="utf-8")
        f.close()

    workspace("archive", "--archive-pattern", "test_pattern*", global_args=["-w", workspace_name])

    assert ws1.latest_archive
    assert os.path.exists(ws1.latest_archive_path)
    assert os.path.exists(os.path.join(ws1.archive_dir, "archive.latest"))

    for template in new_templates:
        archived_path = template.replace(ws1.root, ws1.latest_archive_path)
        assert os.path.exists(archived_path)

    for file in new_files:
        archived_path = file.replace(ws1.root, ws1.latest_archive_path)
        assert os.path.exists(archived_path)

    # Check for archive pattern files
    for i in range(5):
        archived_path = os.path.join(ws1.latest_archive_path, f"test_pattern.{i}")
        assert os.path.isfile(archived_path)
        with open(archived_path, encoding="utf-8") as f:
            assert "Test archive file" in f.read()

    assert not os.path.exists(
        os.path.join(
            ws1.latest_archive_path,
            "shared",
            "licenses",
            "basic",
            ramble.workspace.LICENSE_INC_NAME,
        )
    )


def test_workspace_archive_include_secrets(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
  software:
    packages: {}
    environments: {}
"""

    test_licenses = """
licenses:
  basic:
    set:
      TEST_LIC: 'value'
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)
    lic_path = os.path.join(ws1.config_dir, "licenses.yaml")

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    with open(lic_path, "w+", encoding="utf-8") as f:
        f.write(test_licenses)

    # Create more templates
    new_templates = []
    for i in range(5):
        new_template = os.path.join(ws1.config_dir, f"test_template.{i}")
        new_templates.append(new_template)
        f = open(new_template, "w+", encoding="utf-8")
        f.close()

    ws1._re_read()

    workspace("setup", "--dry-run", global_args=["-w", workspace_name])

    workspace("archive", "--include-secrets", global_args=["-w", workspace_name])

    assert os.path.exists(
        os.path.join(
            ws1.latest_archive_path,
            "shared",
            "licenses",
            "basic",
            ramble.workspace.LICENSE_INC_NAME,
        )
    )


def test_workspace_tar_archive(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    # Create more temlates
    new_templates = []
    for i in range(5):
        new_template = os.path.join(ws1.config_dir, f"test_template.{i}")
        new_templates.append(new_template)
        f = open(new_template, "w+", encoding="utf-8")
        f.close()

    ws1._re_read()

    workspace("setup", "--dry-run", global_args=["-w", workspace_name])
    experiment_dir = os.path.join(ws1.root, "experiments", "basic", "test_wl", "test_experiment")
    out_files = glob.glob(os.path.join(ws1.log_dir, "**", "*.out"), recursive=True)

    assert search_files_for_string(out_files, "Would download file:///tmp/test_file.log")
    assert os.path.exists(os.path.join(experiment_dir, "execute_experiment"))

    # Create files that match archive pattern
    new_files = []
    for i in range(5):
        new_name = f"archive_test.{i}"
        new_file = os.path.join(experiment_dir, new_name)

        new_files.append(new_file)
        f = open(new_file, "w+", encoding="utf-8")
        f.close()

    workspace("archive", "-t", global_args=["-w", workspace_name])

    assert ws1.latest_archive
    assert os.path.exists(ws1.latest_archive_path)

    for template in new_templates:
        archived_path = template.replace(ws1.root, ws1.latest_archive_path)
        assert os.path.exists(archived_path)

    for file in new_files:
        archived_path = file.replace(ws1.root, ws1.latest_archive_path)
        assert os.path.exists(archived_path)

    assert os.path.exists(ws1.latest_archive_path + ".tar.gz")
    assert os.path.exists(os.path.join(ws1.archive_dir, "archive.latest.tar.gz"))


def test_workspace_tar_upload_archive(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    # Create more templates
    new_templates = []
    for i in range(5):
        new_template = os.path.join(ws1.config_dir, f"test_template.{i}")
        new_templates.append(new_template)
        f = open(new_template, "w+", encoding="utf-8")
        f.close()

    ws1._re_read()

    workspace("setup", "--dry-run", global_args=["-w", workspace_name])
    experiment_dir = os.path.join(ws1.root, "experiments", "basic", "test_wl", "test_experiment")
    out_files = glob.glob(os.path.join(ws1.log_dir, "**", "*.out"), recursive=True)

    assert search_files_for_string(out_files, "Would download file:///tmp/test_file.log")
    assert os.path.exists(os.path.join(experiment_dir, "execute_experiment"))

    # Create files that match archive pattern
    new_files = []
    for i in range(5):
        new_name = f"archive_test.{i}"
        new_file = os.path.join(experiment_dir, new_name)

        new_files.append(new_file)
        f = open(new_file, "w+", encoding="utf-8")
        f.close()

    remote_archive_path = os.path.join(ws1.root, "archive_backup")
    fs.mkdirp(remote_archive_path)

    workspace(
        "archive", "-t", "-u", "file://" + remote_archive_path, global_args=["-w", workspace_name]
    )

    assert ws1.latest_archive
    assert os.path.exists(ws1.latest_archive_path)

    for template in new_templates:
        archived_path = template.replace(ws1.root, ws1.latest_archive_path)
        assert os.path.exists(archived_path)

    for file in new_files:
        archived_path = file.replace(ws1.root, ws1.latest_archive_path)
        assert os.path.exists(archived_path)

    assert os.path.exists(ws1.latest_archive_path + ".tar.gz")

    assert os.path.exists(os.path.join(remote_archive_path, ws1.latest_archive + ".tar.gz"))


def test_workspace_uncompressed_upload_archive(make_workspace_from_config):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: 5
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment:
              variables:
                n_nodes: 2
  software:
    packages: {}
    environments: {}
"""

    ws1, workspace_name = make_workspace_from_config(test_config)

    workspace("setup", "--dry-run", global_args=["-w", workspace_name])

    remote_archive_path = os.path.join(ws1.root, "uncompressed_archive_backup")
    fs.mkdirp(remote_archive_path)

    workspace("archive", "-u", "file://" + remote_archive_path, global_args=["-w", workspace_name])

    assert ws1.latest_archive
    assert os.path.exists(ws1.latest_archive_path)
    assert not os.path.exists(ws1.latest_archive_path + ".tar.gz")

    remote_latest_dir = os.path.join(remote_archive_path, ws1.latest_archive)
    assert os.path.exists(remote_latest_dir)
    assert os.path.exists(
        os.path.join(remote_latest_dir, "configs", ramble.workspace.CONFIG_FILE_NAME)
    )


def test_workspace_tar_upload_archive_config_url(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    # Create more templates
    new_templates = []
    for i in range(5):
        new_template = os.path.join(ws1.config_dir, f"test_template.{i}")
        new_templates.append(new_template)
        f = open(new_template, "w+", encoding="utf-8")
        f.close()

    ws1._re_read()

    workspace("setup", "--dry-run", global_args=["-w", workspace_name])
    experiment_dir = os.path.join(ws1.root, "experiments", "basic", "test_wl", "test_experiment")
    out_files = glob.glob(os.path.join(ws1.log_dir, "**", "*.out"), recursive=True)

    assert search_files_for_string(out_files, "Would download file:///tmp/test_file.log")
    assert os.path.exists(os.path.join(experiment_dir, "execute_experiment"))

    # Create files that match archive pattern
    new_files = []
    for i in range(5):
        new_name = f"archive_test.{i}"
        new_file = os.path.join(experiment_dir, new_name)

        new_files.append(new_file)
        f = open(new_file, "w+", encoding="utf-8")
        f.close()

    remote_archive_path = os.path.join(ws1.root, "archive_backup")
    fs.mkdirp(remote_archive_path)

    config("add", f"config:archive_url:{remote_archive_path}/", global_args=["-w", workspace_name])

    workspace("archive", "-t", global_args=["-w", workspace_name])

    assert ws1.latest_archive
    assert os.path.exists(ws1.latest_archive_path)

    for template in new_templates:
        archived_path = template.replace(ws1.root, ws1.latest_archive_path)
        assert os.path.exists(archived_path)

    for file in new_files:
        archived_path = file.replace(ws1.root, ws1.latest_archive_path)
        assert os.path.exists(archived_path)

    assert os.path.exists(ws1.latest_archive_path + ".tar.gz")

    assert os.path.exists(os.path.join(remote_archive_path, ws1.latest_archive + ".tar.gz"))


def test_workspace_archive_includes_exec_logs(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: ''
    batch_submit: '{execute_experiment}'
    processes_per_node: '1'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    fom-log-path:
      workloads:
        test:
          experiments:
            test_experiment:
              variables:
                n_nodes: '1'
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    workspace("setup", global_args=["-w", workspace_name])
    on(global_args=["-w", workspace_name])

    expected_files = [
        os.path.join(ws1.experiment_dir, "fom-log-path", "test", "test_experiment", "log.file"),
        os.path.join(
            ws1.experiment_dir, "fom-log-path", "test", "test_experiment", "other.log.file"
        ),
    ]

    for file in expected_files:
        assert os.path.isfile(file)

    workspace("archive", global_args=["-w", workspace_name])

    for file in expected_files:
        assert os.path.isfile(file.replace(ws1.root, ws1.latest_archive_path))


def test_dryrun_noexpvars_setup(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment: {}
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    workspace("setup", "--dry-run", global_args=["-w", workspace_name])

    out_files = glob.glob(os.path.join(ws1.log_dir, "**", "*.out"), recursive=True)

    assert search_files_for_string(out_files, "Would download file:///tmp/test_file.log")
    assert os.path.exists(
        os.path.join(
            ws1.root, "experiments", "basic", "test_wl", "test_experiment", "execute_experiment"
        )
    )


def test_workspace_include(workspace_name):

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_file = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)
    inc_file = os.path.join(ws1.config_dir, "test_include.yaml")

    test_include = """
config:
  variables:
    test_var: '1'
"""

    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
        test_wl2:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
  include:
     - '%s'
  software:
    packages: {}
    environments: {}
""" % inc_file

    with open(inc_file, "w+", encoding="utf-8") as f:
        f.write(test_include)

    with open(config_file, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    output = workspace("info", "--software", global_args=["-w", workspace_name])

    check_info_basic(output)


@pytest.mark.parametrize("tpl_name", ["env_path"])
def test_invalid_template_name_errors(tpl_name, capsys, workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test_experiment: {}
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)
    template_path = os.path.join(ws1.config_dir, f"{tpl_name}.tpl")

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    with open(template_path, "w+", encoding="utf-8") as f:
        f.write("{command}")

    err_str = (
        f"Template file {tpl_name}.tpl results in a template name of "
        f"{tpl_name} which is reserved by ramble"
    )
    with pytest.raises(ramble.workspace.RambleInvalidTemplateNameError, match=err_str):
        ws1._re_read()


def test_custom_executables_info(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}'
  applications:
    basic:
      internals:
        custom_executables:
          app_level_cmd:
            template:
            - 'app_level_cmd'
            use_mpi: false
            redirect: '{log_file}'
      workloads:
        test_wl:
          internals:
            custom_executables:
              wl_level_cmd:
                template:
                - 'wl_level_cmd'
                use_mpi: false
                redirect: '{log_file}'
          experiments:
            test_experiment:
              internals:
                custom_executables:
                  exp_level_cmd:
                    template:
                    - 'exp_level_cmd'
                    use_mpi: false
                    redirect: '{log_file}'
                    output_capture: '&>'
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    output = workspace("info", "-vv", global_args=["-w", workspace_name])

    assert "app_level_cmd" in output
    assert "wl_level_cmd" in output
    assert "exp_level_cmd" in output


def test_custom_executables_order_info(workspace_name):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}'
  applications:
    basic:
      internals:
        custom_executables:
          app_level_cmd:
            template:
            - 'app_level_cmd'
            use_mpi: false
            redirect: '{log_file}'
      workloads:
        test_wl:
          internals:
            custom_executables:
              wl_level_cmd:
                template:
                - 'wl_level_cmd'
                use_mpi: false
                redirect: '{log_file}'
          experiments:
            test_experiment:
              internals:
                custom_executables:
                  exp_level_cmd:
                    template:
                    - 'exp_level_cmd'
                    use_mpi: false
                    redirect: '{log_file}'
                executables:
                - exp_level_cmd
                - wl_level_cmd
                - app_level_cmd
  software:
    packages: {}
    environments: {}
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws1._re_read()

    output = workspace("info", "-vv", global_args=["-w", workspace_name])

    assert "['exp_level_cmd', 'wl_level_cmd', 'app_level_cmd']" in output


def test_workspace_simplify(workspace_name):
    test_ws_config = """
ramble:
  variants:
    package_manager: spack
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '5'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    zlib:
      workloads:
        ensure_installed:
          experiments:
            test_experiment:
              variables:
                n_nodes: '2'
    zlib-configs:
      workloads:
        ensure_installed:
          experiments:
            unused_exp_template:
              template: True
              variables:
                n_nodes: '1'
  software:
    packages:
      zlib:
        pkg_spec: zlib
      zlib-configs:
        pkg_spec: zlib-configs
      unused-pkg:
        pkg_spec: unused
    environments:
      zlib:
        packages:
        - zlib
      zlib-configs:
        packages:
        - zlib-configs
      unused-env:
        packages:
        - unused-pkg
"""
    test_app_config = """
applications:
  basic:
    workloads:
      test_wl:
        experiments:
          app_not_in_ws_config:
            variables:
              n_ranks: 1
"""
    test_software_config = """
software:
  packages:
    pkg_not_in_ws_config:
      pkg_spec: 'gcc@10.5.0'
      compiler_spec: gcc@10.5.0
"""

    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    ws_config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)
    app_config_path = os.path.join(ws1.config_dir, "applications.yaml")
    software_config_path = os.path.join(ws1.config_dir, "software.yaml")

    with open(ws_config_path, "w+", encoding="utf-8") as f:
        f.write(test_ws_config)
    with open(app_config_path, "w+", encoding="utf-8") as f:
        f.write(test_app_config)
    with open(software_config_path, "w+", encoding="utf-8") as f:
        f.write(test_software_config)

    ws1._re_read()

    assert search_files_for_string([ws_config_path], "pkg_spec: zlib")
    assert search_files_for_string([ws_config_path], "unused-pkg")
    assert search_files_for_string([ws_config_path], "unused-env")
    assert search_files_for_string([ws_config_path], "unused_exp_template")
    assert search_files_for_string([ws_config_path], "pkg_spec: zlib-configs")
    assert not search_files_for_string([ws_config_path], "app_not_in_ws_config")
    assert not search_files_for_string([ws_config_path], "pkg_not_in_ws_config")

    workspace("concretize", "--simplify", global_args=["-w", workspace_name])

    assert search_files_for_string([ws_config_path], "pkg_spec: zlib")  # keep used pkg
    assert not search_files_for_string([ws_config_path], "unused-pkg")  # remove unused pkg
    assert not search_files_for_string([ws_config_path], "unused-env")  # remove unused env
    # remove unused experiment template and associated pkgs/envs
    assert not search_files_for_string([ws_config_path], "unused_exp_template")
    assert not search_files_for_string([ws_config_path], "pkg_spec: zlib-configs")
    # ensure apps/pkgs/envs are not merged into workspace config from other config files
    assert not search_files_for_string([ws_config_path], "app_not_in_ws_config")
    assert not search_files_for_string([ws_config_path], "pkg_not_in_ws_config")


def write_variables_config_file(file_path, levels, value):
    with open(file_path, "w+", encoding="utf-8") as f:
        f.write("variables:\n")
        for i in range(levels):
            f.write(f"  scope{i}: {value}\n")


def test_workspace_config_precedence(workspace_name, tmpdir):
    ws = ramble.workspace.create(workspace_name)

    global_args = ["-w", workspace_name]

    # Highest precedence, experiment scope
    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-e",
        "unit-test",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "-v",
        "scope0=experiment",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )

    # 2nd highest precedence, included (in an included path)
    included_path = os.path.join(ws.root, "variables.yaml")
    with open(ws.config_file_path, "a", encoding="utf-8") as f:
        f.write("  include:\n")
        f.write(f"  - {included_path}\n")

    write_variables_config_file(included_path, 2, "include_path")

    # 3rd highest precedence, workspace overrides (in configs/variables.yaml)
    workspace_overrides = os.path.join(ws.config_dir, "variables.yaml")
    write_variables_config_file(workspace_overrides, 3, "workspace_overrides")

    # 4th highest precedence, workspace (in ramble.yaml)
    config("add", "variables:scope0:workspace", global_args=global_args)
    config("add", "variables:scope1:workspace", global_args=global_args)
    config("add", "variables:scope2:workspace", global_args=global_args)
    config("add", "variables:scope3:workspace", global_args=global_args)

    output = workspace("info", "-vv", global_args=global_args)

    assert "scope0 = experiment" in output
    assert "scope1 = include_path" in output
    assert "scope2 = workspace_override" in output
    assert "scope3 = workspace" in output


def test_workspace_info_software(workspace_name):
    ramble.workspace.create(workspace_name)

    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-e",
        "pip-test",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "-v",
        "env_name=pip-env",
        "-V",
        "package_manager=pip",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )

    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-e",
        "spack-test",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "-v",
        "env_name=spack-env",
        "-V",
        "package_manager=spack",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )

    workspace(
        "manage",
        "software",
        "--pkg",
        "pkg1",
        "--spec",
        "pip-pkg@1.2.3",
        global_args=global_args,
    )

    workspace(
        "manage",
        "software",
        "--pkg",
        "pkg2",
        "--spec",
        "spack-pkg@1.2.3",
        global_args=global_args,
    )

    workspace(
        "manage",
        "software",
        "--env",
        "pip-env",
        "--environment-packages",
        "pkg1",
        global_args=global_args,
    )

    workspace(
        "manage",
        "software",
        "--env",
        "spack-env",
        "--environment-packages",
        "pkg2",
        global_args=global_args,
    )

    output = workspace("info", "--software", global_args=global_args)
    assert "pip-pkg" in output
    assert "spack-pkg" in output

    output_all = workspace("info", "--all-software", global_args=global_args)
    assert "pip-pkg" in output_all
    assert "spack-pkg" in output_all
    assert "pip-test" in output
    assert "spack-test" in output

    output = workspace(
        "info",
        "--software",
        "--where",
        "'{experiment_name}' == 'spack-test'",
        global_args=global_args,
    )
    assert "pip-pkg" not in output
    assert "spack-pkg" in output
    assert "pip-test" not in output
    assert "spack-test" in output

    output = workspace(
        "info",
        "--all-software",
        "--where",
        "'{experiment_name}' == 'spack-test'",
        global_args=global_args,
    )
    assert "pip-pkg" in output
    assert "spack-pkg" in output
    assert "pip-test" not in output
    assert "spack-test" in output

    output = workspace(
        "info",
        "--software",
        "--where",
        "'{experiment_name}' == 'pip-test'",
        global_args=global_args,
    )
    assert "pip-pkg" in output
    assert "spack-pkg" not in output
    assert "pip-test" in output
    assert "spack-test" not in output

    output = workspace(
        "info",
        "--all-software",
        "--where",
        "'{experiment_name}' == 'pip-test'",
        global_args=global_args,
    )
    assert "pip-pkg" in output
    assert "spack-pkg" in output
    assert "pip-test" in output
    assert "spack-test" not in output


def test_workspace_no_empty_workloads(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        with pytest.raises(RambleCommandError):
            workspace(
                "manage",
                "experiments",
                "basic",
                "--wf",
                "nothing*",
                "-v",
                "n_nodes=1",
                "-v",
                "n_ranks=1",
                "--default-variable-value",
                "1",
                global_args=global_args,
            )

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "basic:" not in data


def test_no_inherit_active_workspace_variants(request):
    workspace1_name = re.sub("[^0-9a-zA-Z_-]", "_", request.node.name) + "_1"
    workspace2_name = re.sub("[^0-9a-zA-Z_-]", "_", request.node.name) + "_2"

    global_args = ["-w", workspace1_name]

    workspace("create", workspace1_name)
    config("add", "variants:package_manager:spack", global_args=global_args)
    config("add", "variants:workflow_manager:slurm", global_args=global_args)

    workspace("create", workspace2_name, global_args=global_args)

    with ramble.workspace.read(workspace2_name) as ws2:
        with open(ws2.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "spack" not in data
            assert "slurm" not in data


@pytest.mark.parametrize(
    "mod_scope,mod_conf",
    [
        ("workspace", {"name": "lscpu", "mode": "standard", "on_executable": ["*"]}),
        ("basic", {"name": "lscpu"}),
        ("basic:test_wl", {"name": "lscpu", "mode": "standard"}),
        ("basic:test_wl:generated", {"name": "lscpu", "on_executable": ["*"]}),
    ],
)
def test_manage_single_modifiers(workspace_name, mod_scope, mod_conf):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:

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
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        list_output = workspace("manage", "modifiers", "--list", global_args=global_args)

        assert "Workspace contains 0 modifiers" in list_output

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "modifiers" not in data
            assert mod_conf["name"] not in data

        add_args = ["-s", mod_scope, "-n", mod_conf["name"]]
        remove_args = ["-s", mod_scope, "-n", mod_conf["name"]]
        if "mode" in mod_conf:
            add_args.append("-m")
            add_args.append(mod_conf["mode"])
            remove_args.append("-m")
            remove_args.append(mod_conf["mode"])

        on_exec_str = None
        if "on_executable" in mod_conf:
            on_exec_str = "[" + ",".join(mod_conf["on_executable"]) + "]"
            add_args.append("-e")
            add_args.append(on_exec_str)

        workspace("manage", "modifiers", "--add", *add_args, global_args=global_args)

        list_output = workspace("manage", "modifiers", "--list", global_args=global_args)

        assert f"Modifier scope: {mod_scope}" in list_output
        assert f"Name: {mod_conf['name']}" in list_output
        if "mode" in mod_conf:
            assert f"Mode: {mod_conf['mode']}" in list_output

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "modifiers" in data
            assert f"- name: {mod_conf['name']}" in data
            if "mode" in mod_conf:
                assert f"mode: {mod_conf['mode']}" in data
            if on_exec_str is not None:
                assert "on_executable" in data

        workspace("manage", "modifiers", "--remove", *remove_args, global_args=global_args)

        list_output = workspace("manage", "modifiers", "--list", global_args=global_args)

        assert "Workspace contains 0 modifiers" in list_output

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "modifiers" not in data
            assert mod_conf["name"] not in data


def test_manage_modifier_index_remove(workspace_name):
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
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        output = workspace(
            "manage",
            "modifiers",
            "--add",
            "-s",
            "workspace",
            "-n",
            "lscpu",
            global_args=global_args,
        )

        assert "Added 1 modifier to workspace" in output

        output = workspace(
            "manage",
            "modifiers",
            "--remove",
            "-i",
            "0",
            global_args=global_args,
        )

        assert "Removed 1 modifier from workspace" in output


def test_manage_modifier_no_modifiers(workspace_name):
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
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        output = workspace(
            "manage",
            "modifiers",
            "--add",
            "-s",
            "workspace",
            "-n",
            "not-a-modifier",
            global_args=global_args,
        )

        assert "0 modifiers added" in output

        output = workspace(
            "manage",
            "modifiers",
            "--remove",
            "-s",
            "workspace",
            "-n",
            "not-a-modifier",
            global_args=global_args,
        )

        assert "0 modifiers removed" in output


def test_manage_modifier_remove_scope_globs(workspace_name):
    global_args = ["-w", workspace_name]
    mod_scope = "workspace"

    with ramble.workspace.create(workspace_name) as ws:

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
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        list_output = workspace("manage", "modifiers", "--list", global_args=global_args)

        assert "Workspace contains 0 modifiers" in list_output

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "modifiers" not in data
            assert "intel-aps" not in data
            assert "intel-vtune" not in data

        workspace(
            "manage",
            "modifiers",
            "--add",
            "-s",
            "workspace",
            "-n",
            "intel-aps",
            global_args=global_args,
        )
        workspace(
            "manage",
            "modifiers",
            "--add",
            "-s",
            "basic:test_wl",
            "-n",
            "intel-vtune",
            global_args=global_args,
        )
        workspace(
            "manage",
            "modifiers",
            "--add",
            "-s",
            "basic:test_wl:generated",
            "-n",
            "intel-vtune",
            global_args=global_args,
        )

        list_output = workspace("manage", "modifiers", "--list", global_args=global_args)

        assert "Workspace contains 3 modifiers" in list_output
        assert f"Modifier scope: {mod_scope}" in list_output
        assert "Name: intel-aps" in list_output
        assert "Name: intel-vtune" in list_output

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "modifiers" in data
            assert "- name: intel-aps" in data
            assert "- name: intel-vtune" in data

        workspace(
            "manage", "modifiers", "--remove", "-s", "*", "-n", "intel*", global_args=global_args
        )

        list_output = workspace("manage", "modifiers", "--list", global_args=global_args)

        assert "Workspace contains 0 modifiers" in list_output

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "modifiers" not in data
            assert "intel-aps" not in data
            assert "intel-tune" not in data


def test_manage_modifier_name_globs(workspace_name):
    global_args = ["-w", workspace_name]
    mod_scope = "workspace"

    with ramble.workspace.create(workspace_name) as ws:

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
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        list_output = workspace("manage", "modifiers", "--list", global_args=global_args)

        assert "Workspace contains 0 modifiers" in list_output

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "modifiers" not in data
            assert "intel" not in data

        add_args = ["-s", mod_scope, "-n", "intel*"]
        remove_args = ["-s", mod_scope, "-n", "intel*"]

        workspace("manage", "modifiers", "--add", *add_args, global_args=global_args)

        list_output = workspace("manage", "modifiers", "--list", global_args=global_args)

        assert "Workspace contains 2 modifiers" in list_output
        assert f"Modifier scope: {mod_scope}" in list_output
        assert "Name: intel" in list_output

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "modifiers" in data
            assert "- name: intel" in data

        workspace("manage", "modifiers", "--remove", *remove_args, global_args=global_args)

        list_output = workspace("manage", "modifiers", "--list", global_args=global_args)

        assert "Workspace contains 0 modifiers" in list_output

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "modifiers" not in data
            assert "intel" not in data


def test_manage_modifier_no_modifier_errors(workspace_name):
    global_args = ["-w", workspace_name]
    name_pattern = "no-matching-mod-name"

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
        err_str = f"Error: No modifiers found matching name pattern of {name_pattern}"
        output = workspace(
            "manage",
            "modifiers",
            "--add",
            "-s",
            "workspace",
            "-n",
            name_pattern,
            global_args=global_args,
        )
        assert err_str in output


@pytest.mark.parametrize(
    "action,scope,error_message",
    [
        ("--add", "blarg", "No scope matches requested scope of blarg"),
        ("--add", "foo:test_wl:generated", "No application matches requested scope foo"),
        ("--add", "basic:foo", "No workload matches requested scope foo in application basic"),
        (
            "--add",
            "basic:test_wl:foo",
            "No experiment matches requested scope foo in application basic and workload test_wl",
        ),
    ],
)
def test_manage_modifier_add_invalid_scope_errors(workspace_name, action, scope, error_message):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
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
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        with pytest.raises(ramble.error.RambleCommandError) as err:
            workspace(
                "manage", "modifiers", action, "-s", scope, "-n", "lscpu", global_args=global_args
            )
            assert error_message in err


@pytest.mark.parametrize(
    "action,scope,error_message",
    [
        ("--remove", "blarg", "No modifiers matched criteria"),
        ("--remove", "foo:test_wl:generated", "No modifiers matched criteria"),
        ("--remove", "basic:foo", "No modifiers matched criteria"),
        ("--remove", "basic:test_wl:foo", "No modifiers matched criteria"),
    ],
)
def test_manage_modifier_remove_invalid_scope_errors(workspace_name, action, scope, error_message):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
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
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        output = workspace(
            "manage", "modifiers", action, "-s", scope, "-n", "lscpu", global_args=global_args
        )
        assert error_message in output


def test_workspace_config_squash(workspace_name, capsys):
    test_vars_include = """variables:
  foo: bar
  n_ranks: 1
  test_var: test_value
  test_multiline_str: |-
    This is a multi-line
    String in YAML
"""

    test_software_include = """software:
  packages:
    gcc:
      pkg_spec: gcc@9.3.0 target=x86_64
  environments:
    gcc:
      packages:
      - gcc
"""

    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        with open(f"{os.path.join(ws.root, 'variables.yaml')}", "w+", encoding="utf-8") as f:
            f.write(test_vars_include)

        with open(f"{os.path.join(ws.root, 'software.yaml')}", "w+", encoding="utf-8") as f:
            f.write(test_software_include)

        ws.write()
        workspace(
            "manage",
            "experiments",
            "zlib",
            "--wf",
            "ensure_installed",
            "-e",
            "zlib-repeats",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace(
            "manage",
            "experiments",
            "zlib",
            "--wf",
            "ensure_installed",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        # Add repeats for one set of experiments.
        config(
            "add",
            "applications:zlib:workloads:ensure_installed:experiments:zlib-repeats:n_repeats:5",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        workspace(
            "manage",
            "includes",
            "--add",
            "$workspace_root/variables.yaml",
            global_args=global_args,
        )

        workspace(
            "manage", "includes", "--add", "$workspace_root/software.yaml", global_args=global_args
        )

        config_output = config("get", "variables", global_args=global_args)

        assert "foo: bar" in config_output

        ws.write()

        # Can't call with the front-end command, because included config scopes
        # are not processed correctly in tests.
        ws.squash_and_print_config(excluded_section=["*repos", "config"])

        config_output = capsys.readouterr().out

        assert "foo: bar" in config_output
        assert "test_var: test_value" in config_output
        assert "gcc" in config_output
        assert "pkg_spec: gcc@9.3.0" in config_output
        assert "test_multiline_str: |-" in config_output

        with open(ws.config_file_path, "w+", encoding="utf-8") as f:
            f.write(config_output)

        ws._re_read()

        workspace("config", "--simplify-software", global_args=global_args)

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "pkg_spec: gcc@9.3.0" not in data
            assert "gcc" not in data

        workspace("config", "--simplify-variables", global_args=global_args)

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "foo: bar" not in data
            assert "test_var: test_value" not in data


def test_workspace_config_simplify_includes(workspace_name, tmpdir, capsys):
    test_vars_include = """variables:
  foo: bar
  n_ranks: 1
  test_var: test_value
"""

    test_software_include = """software:
  packages:
    gcc:
      pkg_spec: gcc@9.3.0 target=x86_64
  environments:
    gcc:
      packages:
      - gcc
"""

    global_args = ["-w", workspace_name]

    include_root = str(tmpdir)

    with ramble.workspace.create(workspace_name) as ws:
        with open(f"{os.path.join(include_root, 'variables.yaml')}", "w+", encoding="utf-8") as f:
            f.write(test_vars_include)

        with open(f"{os.path.join(include_root, 'software.yaml')}", "w+", encoding="utf-8") as f:
            f.write(test_software_include)

        ws.write()
        workspace(
            "manage",
            "experiments",
            "zlib",
            "--wf",
            "ensure_installed",
            "-e",
            "zlib-repeats",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace(
            "manage",
            "experiments",
            "zlib",
            "--wf",
            "ensure_installed",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        # Add repeats for one set of experiments.
        config(
            "add",
            "applications:zlib:workloads:ensure_installed:experiments:zlib-repeats:n_repeats:5",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        workspace("manage", "includes", "--add", include_root, global_args=global_args)

        config_output = config("get", "variables", global_args=global_args)

        assert "foo: bar" in config_output

        ws.write()

        output = workspace("config", "--simplify-software", global_args=global_args)

        assert "No changes were made to software configuration sections" in output

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "pkg_spec: gcc@9.3.0" not in data
            assert "gcc" not in data

        output = workspace("config", "--simplify-variables", global_args=global_args)

        assert "No variables were changed" in output


def test_workspace_experiment_logs(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
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
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        output = workspace("experiment-logs", global_args=global_args)

        expected_output = os.sep.join(
            ["experiments", "basic", "test_wl", "generated", "generated.out"]
        )
        assert expected_output in output


def test_workspace_ls(workspace_name):
    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
        out = workspace("ls")
        assert workspace_name in out


def test_workspace_rm_alias(workspace_name):
    workspace("create", workspace_name)
    out = workspace("list")
    assert workspace_name in out

    workspace("rm", "-y", workspace_name)
    out = workspace("list")
    assert workspace_name not in out


def test_workspace_push_to_cache(workspace_name, tmpdir):
    global_args = ["-w", workspace_name]
    cache_dir = tmpdir.mkdir("buildcache")

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
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
            "--default-variable-value",
            "1",
            global_args=global_args,
        )
        workspace("concretize", global_args=global_args)
        workspace(
            "push-to-cache",
            "-d",
            str(cache_dir),
            "--dry-run",
            global_args=global_args,
        )


def test_workspace_bootstrap_command(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
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
            "--default-variable-value",
            "1",
            global_args=global_args,
        )
        workspace("concretize", global_args=global_args)
        workspace("bootstrap", global_args=global_args)


def test_workspace_manage_filter_groups_rm_alias(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
        workspace(
            "manage",
            "filter-groups",
            "add",
            "-n",
            "test-group",
            "--where",
            "{n_nodes} == 1",
            global_args=global_args,
        )
        out = workspace("manage", "filter-groups", "list", global_args=global_args)
        assert "test-group" in out

        workspace(
            "manage",
            "filter-groups",
            "rm",
            "-n",
            "test-group",
            global_args=global_args,
        )
        out = workspace("manage", "filter-groups", "list", global_args=global_args)
        assert "test-group" not in out


def test_manage_experiments_single_success_criterion(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
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
            "-s",
            "name=crit1,mode=string,match=SUCCESS",
            global_args=global_args,
        )

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "success_criteria:" in data
            assert "name: crit1" in data
            assert "mode: string" in data
            assert "match: SUCCESS" in data


def test_manage_experiments_multiple_success_criteria(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
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
            "-s",
            "name=c1,mode=string,match=PASS",
            "-s",
            "name=c2,mode=string,anti_match=FAIL",
            global_args=global_args,
        )

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "success_criteria:" in data
            assert "name: c1" in data
            assert "match: PASS" in data
            assert "name: c2" in data
            assert "anti_match: FAIL" in data


def test_manage_experiments_fom_success_criterion(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
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
            "-s",
            'name=fom_c,mode=fom_comparison,fom_name=my_fom,formula="{value} > 5"',
            global_args=global_args,
        )

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "success_criteria:" in data
            assert "name: fom_c" in data
            assert "mode: fom_comparison" in data
            assert "fom_name: my_fom" in data
            assert "formula:" in data


@pytest.mark.parametrize(
    "crit_str,err_msg",
    [
        ("mode=string,match=SUCCESS", "requires a 'name' attribute"),
        ("name=c1,match=SUCCESS", "requires a 'mode' attribute"),
        ("name=c1,mode=invalid_mode", "mode 'invalid_mode' is invalid"),
        ("name=c1,mode=string", "requires 'match' or 'anti_match'"),
        (
            "name=c1,mode=string,match=M,anti_match=A",
            "requires exactly one of 'match' or 'anti_match'",
        ),
        ("name=c1,mode=fom_comparison,fom_name=my_fom", "requires 'fom_name' and 'formula'"),
        ("name=c1,invalid_attribute", "Invalid success_criteria attribute definition"),
    ],
)
def test_manage_experiments_invalid_success_criteria(workspace_name, crit_str, err_msg):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name):
        with pytest.raises(RambleCommandError, match=err_msg):
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
                "-s",
                crit_str,
                global_args=global_args,
            )


def test_manage_experiments_duplicate_success_criteria(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name):
        with pytest.raises(RambleCommandError, match="Duplicate success criteria name 'c1'"):
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
                "-s",
                "name=c1,mode=string,match=PASS",
                "-s",
                "name=c1,mode=string,match=PASS2",
                global_args=global_args,
            )


def test_manage_experiments_success_criteria_special_characters(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
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
            "-s",
            (
                "name=c_val_quotes,mode=fom_comparison,fom_name=my_fom,"
                'formula="{value} > 5, {value} < 100"'
            ),
            "-s",
            (
                "name=c_single_quotes,mode=fom_comparison,fom_name=my_fom,"
                "formula='{value} > 5, {value} < 100'"
            ),
            "-s",
            (
                "name=c_attr_quotes,mode=fom_comparison,fom_name=my_fom,"
                '"formula={value} > 5, {value} < 100"'
            ),
            "-s",
            (
                "name=c_escaped,mode=fom_comparison,fom_name=my_fom,"
                'formula=\\"{value} > 5, {value} < 100\\"'
            ),
            "-s",
            'name=c_equals,mode=string,match="status=OK"',
            "-s",
            "name=c_nested,mode=string,match=\"status='OK, DONE'\"",
            global_args=global_args,
        )

        with open(ws.config_file_path, encoding="utf-8") as f:
            data = f.read()
            assert "success_criteria:" in data
            assert "name: c_val_quotes" in data
            assert "name: c_single_quotes" in data
            assert "name: c_attr_quotes" in data
            assert "name: c_escaped" in data
            assert "{value} > 5, {value} < 100" in data
            assert "name: c_equals" in data
            assert "status=OK" in data
            assert "name: c_nested" in data
            assert "status='OK, DONE'" in data
