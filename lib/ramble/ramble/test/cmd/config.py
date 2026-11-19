# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import copy
import functools
import os

import pytest

import llnl.util.filesystem as fs

import ramble.config
import ramble.main
import ramble.workspace

import spack.util.spack_yaml as syaml

config = ramble.main.RambleCommand("config")
workspace = ramble.main.RambleCommand("workspace")


def _create_config(scope=None, data=None, section="repos"):
    if data is None:
        data = {}
    scope = scope or ramble.config.default_modify_scope()
    cfg_file = ramble.config.config.get_config_filename(scope, section)
    with open(cfg_file, "w", encoding="utf-8") as f:
        syaml.dump(data, stream=f)
    return cfg_file


@pytest.fixture()
def config_yaml_v015(mutable_config):
    """Create a config.yaml in the old format"""
    old_data = {
        "config": {
            "install_tree": "/fake/path",
            "install_path_scheme": "{name}-{version}",
        }
    }
    return functools.partial(_create_config, data=old_data, section="config")


def test_get_config_scope(mock_low_high_config):
    assert config("get", "repos").strip() == "repos: {}"


def test_get_config_scope_merged(mock_low_high_config):
    low_path = mock_low_high_config.scopes["low"].path
    high_path = mock_low_high_config.scopes["high"].path

    fs.mkdirp(low_path)
    fs.mkdirp(high_path)

    with open(os.path.join(low_path, "repos.yaml"), "w", encoding="utf-8") as f:
        f.write("""\
repos:
- repo3
""")

    with open(os.path.join(high_path, "repos.yaml"), "w", encoding="utf-8") as f:
        f.write("""\
repos:
- repo1
- repo2
""")

    assert config("get", "repos").strip() == """repos:
- repo1
- repo2
- repo3"""


def test_merged_variables_section(mock_low_high_config):
    low_path = mock_low_high_config.scopes["low"].path
    high_path = mock_low_high_config.scopes["high"].path

    fs.mkdirp(low_path)
    fs.mkdirp(high_path)

    with open(os.path.join(low_path, "variables.yaml"), "w", encoding="utf-8") as f:
        f.write("""\
variables:
  foo: 'bar'
""")

    with open(os.path.join(high_path, "variables.yaml"), "w", encoding="utf-8") as f:
        f.write("""\
variables:
  bar: 'baz'
""")

    assert config("get", "variables").strip() == """variables:
  bar: baz
  foo: bar"""


def test_merged_env_vars_section(mock_low_high_config):
    low_path = mock_low_high_config.scopes["low"].path
    high_path = mock_low_high_config.scopes["high"].path

    fs.mkdirp(low_path)
    fs.mkdirp(high_path)

    with open(os.path.join(low_path, "env_vars.yaml"), "w", encoding="utf-8") as f:
        f.write("""\
env_vars:
  set:
    FOO: bar
""")

    with open(os.path.join(high_path, "env_vars.yaml"), "w", encoding="utf-8") as f:
        f.write("""\
env_vars:
  append:
    vars:
      FOO: baz
""")

    assert config("get", "env_vars").strip() == """env_vars:
  append:
    vars:
      FOO: baz
  set:
    FOO: bar"""


@pytest.mark.parametrize("section_key", ["software"])
def test_merged_software_section(mock_low_high_config, section_key):
    low_path = mock_low_high_config.scopes["low"].path
    high_path = mock_low_high_config.scopes["high"].path

    fs.mkdirp(low_path)
    fs.mkdirp(high_path)

    with open(os.path.join(low_path, f"{section_key}.yaml"), "w", encoding="utf-8") as f:
        f.write(f"""\
{section_key}:
  packages:
    gcc:
      pkg_spec: gcc@4.8.5
""")

    with open(os.path.join(high_path, f"{section_key}.yaml"), "w", encoding="utf-8") as f:
        f.write(f"""\
{section_key}:
  packages:
    zlib:
      pkg_spec: zlib
      compiler: gcc
""")

    assert config("get", section_key).strip() == f"""{section_key}:
  packages:
    zlib:
      pkg_spec: zlib
      compiler: gcc
    gcc:
      pkg_spec: gcc@4.8.5"""


def test_merged_success_criteria_section(mock_low_high_config):
    low_path = mock_low_high_config.scopes["low"].path
    high_path = mock_low_high_config.scopes["high"].path

    fs.mkdirp(low_path)
    fs.mkdirp(high_path)

    with open(os.path.join(low_path, "success_criteria.yaml"), "w", encoding="utf-8") as f:
        f.write("""\
success_criteria:
  - name: done
    mode: string
    match: "DONE"
    file: "{log_file}"
""")

    with open(os.path.join(high_path, "success_criteria.yaml"), "w", encoding="utf-8") as f:
        f.write("""\
success_criteria:
  - name: complete
    mode: string
    match: "COMPLETE"
    file: "{log_file}"
""")

    assert config("get", "success_criteria").strip() == """success_criteria:
- name: complete
  mode: string
  match: COMPLETE
  file: '{log_file}'
- name: done
  mode: string
  match: DONE
  file: '{log_file}'"""


def test_merged_applications_section(mock_low_high_config):
    low_path = mock_low_high_config.scopes["low"].path
    high_path = mock_low_high_config.scopes["high"].path

    fs.mkdirp(low_path)
    fs.mkdirp(high_path)

    with open(os.path.join(low_path, "applications.yaml"), "w", encoding="utf-8") as f:
        f.write("""\
applications:
  foo:
    workloads:
      bar:
        experiments:
          test:
            variables:
              my_var: value
""")

    with open(os.path.join(high_path, "applications.yaml"), "w", encoding="utf-8") as f:
        f.write("""\
applications:
  foo:
    workloads:
      bar:
        experiments:
          test2:
            variables:
              my_var: value
      baz:
        experiments:
          test:
            variables:
              my_var: value
  hostname:
    workloads:
      serial:
        experiments:
          single:
            variables:
              n_ranks: 1
""")

    assert config("get", "applications").strip() == """applications:
  foo:
    workloads:
      bar:
        experiments:
          test2:
            variables:
              my_var: value
          test:
            variables:
              my_var: value
      baz:
        experiments:
          test:
            variables:
              my_var: value
  hostname:
    workloads:
      serial:
        experiments:
          single:
            variables:
              n_ranks: 1"""


def test_config_edit():
    """Ensure `ramble config edit` edits the right paths."""

    dms = ramble.config.default_modify_scope("config")
    dms_path = ramble.config.config.scopes[dms].path
    user_path = ramble.config.config.scopes["user"].path

    comp_path = os.path.join(dms_path, "config.yaml")
    repos_path = os.path.join(user_path, "repos.yaml")

    assert config("edit", "--print-file", "config").strip() == comp_path
    assert config("edit", "--print-file", "repos").strip() == repos_path


def test_config_get_gets_ramble_yaml(mutable_mock_workspace_path, mutable_mock_apps_repo):
    ws = ramble.workspace.create("test")

    config("get", fail_on_error=False)
    assert config.returncode == 1

    with ws:
        config("get", fail_on_error=False)
        assert config.returncode == 1

        ws.write()

        config_output = config("get")

        expected_keys = [
            "applications",
            "variables",
            "env_vars",
            "software",
            "processes_per_node",
        ]

        for key in expected_keys:
            assert key in config_output


def test_config_edit_edits_ramble_yaml(mutable_mock_workspace_path):
    ws = ramble.workspace.create("test")
    ws.write()
    with ws:
        assert config("edit", "--print-file").strip() == ramble.workspace.config_file(ws.root)


def test_config_edit_fails_correctly_with_no_workspace(mutable_mock_workspace_path):
    output = config("edit", "--print-file", fail_on_error=False)
    assert "requires a section argument or an active workspace" in output


def test_config_get_fails_correctly_with_no_workspace(mutable_mock_workspace_path):
    output = config("get", fail_on_error=False)
    assert "requires a section argument or an active workspace" in output


def test_config_list():
    output = config("list")
    assert "config" in output
    assert "repos" in output


def test_config_add(mutable_empty_config):
    config("add", "config:dirty:true")
    output = config("get", "config")

    assert output == """config:
  dirty: true
"""


def test_config_add_list(mutable_empty_config):
    config("add", "config:template_dirs:test1")
    config("add", "config:template_dirs:[test2]")
    config("add", "config:template_dirs:test3")
    output = config("get", "config")

    assert output == """config:
  template_dirs:
  - test3
  - test2
  - test1
"""


def test_config_add_override(mutable_empty_config):
    config("--scope", "site", "add", "config:template_dirs:test1")
    config("add", "config:template_dirs:[test2]")
    output = config("get", "config")

    assert output == """config:
  template_dirs:
  - test2
  - test1
"""


def test_config_add_override_short_scope(mutable_empty_config):
    config("-s", "site", "add", "config:template_dirs:test1")
    config("add", "config:template_dirs:[test2]")
    output = config("get", "config")

    assert output == """config:
  template_dirs:
  - test2
  - test1
"""

    config("add", "config::template_dirs:[test2]")
    output = config("get", "config")

    assert output == """config:
  template_dirs:
  - test2
"""


def test_config_add_override_leaf(mutable_empty_config):
    config("--scope", "site", "add", "config:template_dirs:test1")
    config("add", "config:template_dirs:[test2]")
    output = config("get", "config")

    assert output == """config:
  template_dirs:
  - test2
  - test1
"""

    config("add", "config:template_dirs::[test2]")
    output = config("get", "config")

    assert output == """config:
  'template_dirs:':
  - test2
"""


def test_config_add_update_dict(mutable_empty_config):
    config("add", "config:test_conf:version:[1.0.0]")
    output = config("get", "config")

    expected = "config:\n  test_conf:\n    version: [1.0.0]\n"
    assert output == expected


def test_config_with_c_argument(mutable_empty_config):

    # I don't know how to add a ramble argument to a Ramble Command, so we test this way
    config_file = "config:install_root:root:/path/to/config.yaml"
    parser = ramble.main.make_argument_parser()
    args = parser.parse_args(["-c", config_file])
    assert config_file in args.config_vars

    # Add the path to the config
    config("add", args.config_vars[0], scope="command_line")
    output = config("get", "config")
    assert "config:\n  install_root:\n    root: /path/to/config.yaml" in output


def test_config_add_ordered_dict(mutable_empty_config):
    config("add", "config:first:/path/to/first")
    config("add", "config:second:/path/to/second")
    output = config("get", "config")

    assert output == """config:
  first: /path/to/first
  second: /path/to/second
"""


def test_config_add_from_file(mutable_empty_config, tmpdir):
    contents = """config:
  dirty: true
"""

    file = str(tmpdir.join("my_conf.yaml"))
    with open(file, "w", encoding="utf-8") as f:
        f.write(contents)
    config("add", "-f", file)
    output = config("get", "config")

    assert output == """config:
  dirty: true
"""


def test_config_add_from_file_multiple(mutable_empty_config, tmpdir):
    contents = """config:
  dirty: true
  template_dirs: [test1]
"""

    file = str(tmpdir.join("my_conf.yaml"))
    with open(file, "w", encoding="utf-8") as f:
        f.write(contents)
    config("add", "-f", file)
    output = config("get", "config")

    assert output == """config:
  dirty: true
  template_dirs: [test1]
"""


def test_config_add_override_from_file(mutable_empty_config, tmpdir):
    config("--scope", "site", "add", "config:template_dirs:test1")
    contents = """config::
  template_dirs: [test2]
"""

    file = str(tmpdir.join("my_conf.yaml"))
    with open(file, "w", encoding="utf-8") as f:
        f.write(contents)
    config("add", "-f", file)
    output = config("get", "config")

    assert output == """config:
  template_dirs: [test2]
"""


def test_config_add_override_leaf_from_file(mutable_empty_config, tmpdir):
    config("--scope", "site", "add", "config:template_dirs:test1")
    contents = """config:
  template_dirs:: [test2]
"""

    file = str(tmpdir.join("my_conf.yaml"))
    with open(file, "w", encoding="utf-8") as f:
        f.write(contents)
    config("add", "-f", file)
    output = config("get", "config")

    assert output == """config:
  'template_dirs:': [test2]
"""


def test_config_add_invalid_file_fails(tmpdir):
    # contents to add to file
    # invalid because version requires a list
    contents = """config:
  test_stage: [~/stage]
"""

    # create temp file and add it to config
    file = str(tmpdir.join("my_conf.yaml"))
    with open(file, "w", encoding="utf-8") as f:
        f.write(contents)

    with pytest.raises(ramble.config.ConfigFormatError):
        config("add", "-f", file)


def test_config_remove_value(mutable_empty_config):
    config("add", "config:dirty:true")
    config("remove", "config:dirty:true")
    output = config("get", "config")

    assert output == """config: {}
"""


def test_config_remove_alias_rm(mutable_empty_config):
    config("add", "config:dirty:true")
    config("rm", "config:dirty:true")
    output = config("get", "config")

    assert output == """config: {}
"""


def test_config_remove_dict(mutable_empty_config):
    config("add", "config:dirty:true")
    config("rm", "config:dirty")
    output = config("get", "config")

    assert output == """config: {}
"""


def test_remove_from_list(mutable_empty_config):
    config("add", "config:template_dirs:test1")
    config("add", "config:template_dirs:[test2]")
    config("add", "config:template_dirs:test3")
    config("remove", "config:template_dirs:test2")
    output = config("get", "config")

    assert output == """config:
  template_dirs:
  - test3
  - test1
"""


def test_remove_list(mutable_empty_config):
    config("add", "config:template_dirs:test1")
    config("add", "config:template_dirs:[test2]")
    config("add", "config:template_dirs:test3")
    config("remove", "config:template_dirs:[test2]")
    output = config("get", "config")

    assert output == """config:
  template_dirs:
  - test3
  - test1
"""


def test_config_add_to_workspace(mutable_empty_config, mutable_mock_workspace_path):
    workspace("create", "test")
    with ramble.workspace.read("test"):
        config("add", "config:dirty:true")
        output = config("get")

    expected = """  config:
    dirty: true
"""
    assert expected in output


def test_config_add_to_workspace_preserve_comments(
    mutable_empty_config, mutable_mock_workspace_path, tmpdir
):
    workspace = ramble.workspace.Workspace(str(tmpdir))
    workspace.write()
    filepath = ramble.workspace.config_file(workspace.root)
    contents = """# comment
ramble:  # comment
  # comment
  applications:
    hostname: # comment
      workloads:
        basic:
          experiments:
            test: # Single node
              variables:
                n_ranks: '1'
                n_nodes: '1'
                processes_per_node: '1'
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(contents)

    with workspace:
        config("add", "config:dirty:true")
        output = config("get")

    expected = contents
    expected += """  config:
    dirty: true

"""
    assert output == expected

    # Verify copy.deepcopy preserves comments on nested CommentedMaps
    parsed = syaml.load_config(expected)
    copied = copy.deepcopy(parsed)
    assert syaml.dump_config(copied, default_flow_style=False) == expected


def test_config_add_to_workspace_preserve_multiline_str(
    mutable_empty_config, mutable_mock_workspace_path, tmpdir
):
    workspace = ramble.workspace.Workspace(str(tmpdir))
    workspace.write()
    filepath = ramble.workspace.config_file(workspace.root)
    contents = """# comment
ramble:  # comment
  # comment
  variables:
    test_multi_line: |
      my test
      string with
      multiple lines
  applications:
    hostname: # comment
      workloads:
        basic:
          experiments:
            test: # Single node
              variables:
                n_ranks: '1'
                n_nodes: '1'
                processes_per_node: '1'
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(contents)

    with workspace:
        config("add", "variables:foo:bar")
        output = config("get")

    expected = """    test_multi_line: |
      my test
      string with
      multiple lines"""

    assert expected in output


def test_config_remove_from_workspace(mutable_empty_config, mutable_mock_workspace_path):
    import io

    workspace("create", "test")

    with ramble.workspace.read("test"):
        config("add", "config:dirty:true")

    with ramble.workspace.read("test"):
        config("rm", "config:dirty")
        output = config("get")

    expected = ramble.workspace.Workspace._default_config_yaml()
    expected += """  config: {}
"""
    for line in io.StringIO(expected):
        assert line in output


# TODO: (dwj) Enable test when we can test properly
# def test_config_update_config(config_yaml_v015):
#     config_yaml_v015()
#     config('update', '-y', 'config')
#
#     # Check the entries have been transformed
#     data = ramble.config.get('config')
#     check_config_updated(data)


def test_config_update_not_needed(mutable_config):
    data_before = ramble.config.get("repos")
    config("update", "-y", "repos")
    data_after = ramble.config.get("repos")
    assert data_before == data_after


# TODO: (dwj) Enable test when we can test properly
# def test_config_update_fail_on_permission_issue(
#         config_yaml_v015, monkeypatch
# ):
#     # The first time it will update and create the backup file
#     config_yaml_v015()
#     # Mock a global scope where we cannot write
#     monkeypatch.setattr(
#         ramble.cmd.config, '_can_update_config_file', lambda x, y: False
#     )
#     with pytest.raises(ramble.main.RambleCommandError):
#         config('update', '-y', 'ramble')


def test_config_revert(config_yaml_v015):
    cfg_file = config_yaml_v015()
    bkp_file = cfg_file + ".bkp"

    fs.copy(cfg_file, bkp_file)

    config("add", "config:dirty:true")
    md5cfg = fs.md5sum(cfg_file)

    # Check that the backup file exists, compute its md5 sum
    assert os.path.exists(bkp_file)
    md5bkp = fs.md5sum(bkp_file)

    config("revert", "-y", "config")

    # Check that the backup file does not exist anymore and
    # that the md5 sum of the configuration file is the same
    # as that of the old backup file
    assert not os.path.exists(bkp_file)
    assert md5bkp == fs.md5sum(cfg_file)
    assert md5bkp != md5cfg


# TODO: (dwj) Enable test when we can test properly
# def test_config_revert_raise_if_cant_write(config_yaml_v015, monkeypatch):
#     config_yaml_v015()
#     config('update', '-y', 'config')

#     # Mock a global scope where we cannot write
#     monkeypatch.setattr(
#         ramble.cmd.config, '_can_revert_update', lambda x, y, z: False
#     )
#     # The command raises with an helpful error if a configuration
#     # file is to be deleted and we don't have sufficient permissions
#     with pytest.raises(ramble.main.RambleCommandError):
#         config('revert', '-y', 'config')


# TODO: (dwj) Enable test when we can test properly
# def test_updating_config_implicitly_raises(config_yaml_v015):
#     # Trying to write implicitly to a scope with a configuration file
#     # in the old format raises an exception
#     config_yaml_v015()
#     with pytest.raises(RuntimeError):
#         config('add', 'config:build_stage:[/tmp/stage]')


# TODO: (dwj) Enable test when we can test properly
# def test_updating_multiple_scopes_at_once(config_yaml_v015):
#     # Create 2 config files in the old format
#     config_yaml_v015(scope='user')
#     config_yaml_v015(scope='site')
#
#     # Update both of them at once
#     config('update', '-y', 'config')
#
#     for scope in ('user', 'site'):
#         data = ramble.config.get('config', scope=scope)
#         check_config_updated(data)


def check_config_updated(data):
    assert isinstance(data["install_tree"], dict)
    assert data["install_tree"]["root"] == "/fake/path"
    assert data["install_tree"]["projections"] == {"all": "{name}-{version}"}


@pytest.fixture(scope="function")
def mock_editor(monkeypatch):
    def _editor(*args, **kwargs):
        return True

    monkeypatch.setattr("ramble.util.editor.editor", _editor)


def section_args(section_name):
    class TestArgs:
        scope = None
        section = section_name
        config_command = "edit"
        print_file = False

    return TestArgs()


def test_config_edit_file(mutable_config, config_section, mock_editor):
    import ramble.cmd.config

    args = section_args(config_section)

    assert ramble.cmd.config.config_edit(args)


def test_command_alias(mutable_config):
    import io
    from contextlib import redirect_stdout

    from ramble import main

    # Test alias 'l' -> 'list'
    config("add", "config:aliases:l:list")
    f = io.StringIO()
    with redirect_stdout(f):
        ret = main.main(argv=["l"])
    assert ret == 0
    output = f.getvalue()
    assert "gromacs" in output

    # Test that an alias cannot override a built-in command
    config("add", "config:aliases:list:info")
    # `list` should run `list`, not `info`
    f = io.StringIO()
    with redirect_stdout(f):
        ret = main.main(argv=["list"])
    output = f.getvalue()
    assert ret == 0
    assert "ramble info" not in output


def test_config_blame(mock_low_high_config):
    low_path = mock_low_high_config.scopes["low"].path
    fs.mkdirp(low_path)
    with open(os.path.join(low_path, "config.yaml"), "w", encoding="utf-8") as f:
        f.write("""\
config:
  verbose: true
""")

    output = config("blame", "config")
    assert "config:" in output
    assert "verbose: true" in output
    assert "config.yaml:" in output
