# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import sys

import pytest

import ramble.repository
from ramble.main import RambleCommand

edit = RambleCommand("edit")


@pytest.fixture
def mock_editor(monkeypatch):
    """Mock editor so we don't open a real one, using the _exec_func hook in ramble.util.editor."""
    monkeypatch.setenv("EDITOR", sys.executable)
    calls = []

    def mock_exec_func(exe, args):
        if args:
            calls.append(args[-1])

    def mocked_editor_wrapper(*args, **kwargs):
        kwargs["_exec_func"] = mock_exec_func
        from ramble.util.editor import editor as real_editor

        real_editor(*args, **kwargs)

    monkeypatch.setattr("ramble.cmd.edit.editor", mocked_editor_wrapper)

    return calls


def test_edit_command(mock_editor):
    """Test `ramble edit -t command <cmd>`"""
    edit("-t", "command", "edit")
    assert len(mock_editor) == 1
    assert "ramble/cmd/edit.py" in mock_editor[0]


def test_edit_test(mock_editor):
    """Test `ramble edit -t test <test>`"""
    edit("-t", "test", "cmd/edit")
    assert len(mock_editor) == 1
    assert "ramble/test/cmd/edit.py" in mock_editor[0]


def test_edit_module(mock_editor):
    """Test `ramble edit -t module <module>`"""
    edit("-t", "module", "config")
    assert len(mock_editor) == 1
    assert "ramble/config.py" in mock_editor[0]


def test_edit_docs(mock_editor):
    """Test `ramble edit -t docs <doc>`"""
    edit("-t", "docs", "index.rst")
    assert len(mock_editor) == 1
    assert "docs/index.rst" in mock_editor[0]


def test_edit_file_not_found():
    output = edit("-t", "command", "non-existent-cmd", fail_on_error=False)
    assert "No file for 'non_existent_cmd' was found" in output


def test_edit_application(mock_applications, mock_editor):
    edit("basic")
    assert len(mock_editor) == 1
    assert "repos/builtin.mock/applications/basic/application.py" in mock_editor[0]


def test_edit_modifier(mock_modifiers, mock_editor):
    edit("info", "-t", "modifiers")
    assert len(mock_editor) == 1
    assert "repos/builtin.mock/modifiers/info/modifier.py" in mock_editor[0]


def test_edit_deduction_modifier(mock_modifiers, mock_editor):
    """Test `ramble edit versions-mod` deduces it's a modifier"""
    edit("versions-mod")
    assert len(mock_editor) == 1
    assert "repos/builtin.mock/modifiers/versions-mod/modifier.py" in mock_editor[0]


def test_edit_singular_type(mock_modifiers, mock_editor):
    """Test `ramble edit -t modifier info` normalizes singular type"""
    edit("info", "-t", "modifier")
    assert len(mock_editor) == 1
    assert "repos/builtin.mock/modifiers/info/modifier.py" in mock_editor[0]


def test_edit_deduction_command(mock_editor):
    """Test `ramble edit edit` deduces it's a command"""
    edit("edit")
    assert len(mock_editor) == 1
    assert "ramble/cmd/edit.py" in mock_editor[0]


def test_edit_deduction_test(mock_editor):
    """Test `ramble edit application` deduces it's a test"""
    edit("application")
    assert len(mock_editor) == 1
    assert "ramble/test/application.py" in mock_editor[0]


def test_edit_singular_type_with_spaces_hyphens(mock_editor):
    """Test package manager singular forms normalization with spaces/hyphens"""
    edit("spack", "-t", "package-manager")
    assert len(mock_editor) == 1
    assert "package_managers/spack/package_manager.py" in mock_editor[0]

    edit("spack", "-t", "package_manager")
    assert len(mock_editor) == 2
    assert "package_managers/spack/package_manager.py" in mock_editor[1]


def test_edit_unknown_type():
    with pytest.raises(ramble.repository.UnknownObjectTypeError):
        edit("-t", "unknown_type", "spack")


def test_edit_with_repo(mock_applications, mock_editor):
    import ramble.repository

    repo_path = ramble.repository.paths[ramble.repository.ObjectTypes.applications].repos[0].root
    edit("basic", "--repo", repo_path)
    assert len(mock_editor) == 1
    assert "repos/builtin.mock/applications/basic/application.py" in mock_editor[0]


def test_edit_with_namespace(mock_applications, mock_editor):
    edit("basic", "--namespace", "builtin.mock")
    assert len(mock_editor) == 1
    assert "repos/builtin.mock/applications/basic/application.py" in mock_editor[0]


def test_edit_deduction_docs(mock_editor):
    edit("index.rst")
    assert len(mock_editor) == 1
    assert "docs/index.rst" in mock_editor[0]


def test_edit_deduction_fails_correctly():
    output = edit("non-existent-object-name", fail_on_error=False)
    assert "No application for 'non-existent-object-name' was found" in output


def test_normalize_type_name():
    from ramble.cmd.edit import normalize_type_name

    assert normalize_type_name(None) is None
    assert normalize_type_name("") is None
    assert normalize_type_name("app") == "applications"
    assert normalize_type_name("application") == "applications"
    assert normalize_type_name("applications") == "applications"
    assert normalize_type_name("mod") == "modifiers"
    assert normalize_type_name("modifier") == "modifiers"
    assert normalize_type_name("modifiers") == "modifiers"
    assert normalize_type_name("pkg_man") == "package_managers"
    assert normalize_type_name("package-manager") == "package_managers"
    assert normalize_type_name("package_manager") == "package_managers"
    assert normalize_type_name("package manager") == "package_managers"
    assert normalize_type_name("test") == "test"
    assert normalize_type_name("tests") == "test"
    assert normalize_type_name("command") == "command"
    assert normalize_type_name("commands") == "command"
    assert normalize_type_name("doc") == "docs"
    assert normalize_type_name("docs") == "docs"
    assert normalize_type_name("module") == "module"
    assert normalize_type_name("modules") == "module"
    assert normalize_type_name("TEST") == "test"
    assert normalize_type_name("Command") == "command"
    assert normalize_type_name("APP") == "applications"
    with pytest.raises(ramble.repository.UnknownObjectTypeError):
        normalize_type_name("unknown_type")


def test_edit_abbreviated_type(mock_modifiers, mock_editor):
    """Test `ramble edit -t mod info` normalizes abbreviated type"""
    edit("info", "-t", "mod")
    assert len(mock_editor) == 1
    assert "repos/builtin.mock/modifiers/info/modifier.py" in mock_editor[0]


def test_edit_object_is_directory(mock_applications, monkeypatch):

    import ramble.repository

    monkeypatch.setattr(
        ramble.repository.Repo, "filename_for_object_name", lambda self, name: self.root
    )
    output = edit("basic", fail_on_error=False)
    assert "is not a file!" in output


def test_edit_object_insufficient_permissions(mock_applications, monkeypatch):
    import os

    real_access = os.access

    def mock_access(path, mode, real_access=real_access, **kwargs):
        if "application.py" in str(path):
            return False
        return real_access(path, mode, **kwargs)

    monkeypatch.setattr(os, "access", mock_access)
    output = edit("basic", fail_on_error=False)
    assert "Insufficient permissions" in output


def test_edit_no_editor_found(mock_applications, monkeypatch):
    def mock_fail_editor(*args, **kwargs):
        raise TypeError("No editor")

    monkeypatch.setattr("ramble.cmd.edit.editor", mock_fail_editor)
    output = edit("basic", fail_on_error=False)
    assert "No valid editor was found" in output


def test_edit_multiple_files_found(monkeypatch):
    import glob
    import os

    monkeypatch.setattr(glob, "glob", lambda pattern: ["file1.py", "file2.py"])
    monkeypatch.setattr(os.path, "isfile", lambda path: path in ["file1.py", "file2.py"])
    output = edit("-t", "command", "non-existent", fail_on_error=False)
    assert "Multiple files exist" in output


def test_edit_multiple_matches_warning(mock_applications, mock_modifiers, mock_editor):
    output = edit("info", fail_on_error=False)
    assert "Multiple matches found for 'info'" in output
    assert "Opening highest-precedence match:" in output
    assert "In order to open a different object, use the commands below:" in output
    assert (
        "Type: modifiers, Command: ramble edit --type modifiers --namespace builtin.mock info"
        in output
    )
    assert "Type: command, Command: ramble edit --type command info" in output


def test_edit_object_fallback_repo():
    output = edit("non-existent", "--repo", "/non-existent-path", fail_on_error=False)
    assert "No application for 'non-existent' was found" in output


def test_edit_object_fallback_namespace():
    output = edit("non-existent", "--namespace", "non-existent-namespace", fail_on_error=False)
    assert "No application for 'non-existent' was found" in output


def test_edit_object_fallback_custom_type_not_found(mock_modifiers):
    output = edit("non-existent-modifier", "-t", "modifiers", fail_on_error=False)
    assert "No modifiers for 'non-existent-modifier' was found" in output


def test_edit_no_name_default_editor(mock_editor):
    edit()
    assert len(mock_editor) == 1
    assert "var/ramble/repos/builtin" in mock_editor[0]


def test_edit_no_name_with_type_editor(mock_editor):
    edit("-t", "command")
    assert len(mock_editor) == 1
    assert "lib/ramble/ramble/cmd" in mock_editor[0]

    edit("-t", "applications")
    assert len(mock_editor) == 2
    assert "var/ramble/repos/builtin" in mock_editor[1]

    edit("-t", "application")
    assert len(mock_editor) == 3
    assert "var/ramble/repos/builtin" in mock_editor[2]


def test_edit_no_name_with_custom_type_repo_editor(mock_editor):
    edit("-t", "applications", "--repo", "/non-existent-path")
    assert len(mock_editor) == 1


def test_edit_no_name_with_custom_type_namespace_editor(mock_applications, mock_editor):
    edit("-t", "applications", "--namespace", "builtin.mock")
    assert len(mock_editor) == 1
    assert "repos/builtin.mock/applications" in mock_editor[0]


def test_edit_no_name_no_editor(monkeypatch):
    def mock_fail_editor(*args, **kwargs):
        raise TypeError("No editor")

    monkeypatch.setattr("ramble.cmd.edit.editor", mock_fail_editor)
    output = edit(fail_on_error=False)
    assert "No valid editor was found" in output


def test_edit_namespaced_spec_with_type(mock_modifiers, mock_editor):
    """Test `ramble edit <repo>.<type>.<name>` covers lines 36 and 41 in edit.py."""
    edit("builtin.mock.mod.info")
    assert len(mock_editor) == 1
    assert "repos/builtin.mock/modifiers/info/modifier.py" in mock_editor[0]


def test_edit_namespaced_spec_without_type(mock_applications, mock_editor):
    """Test `ramble edit <repo>.<name>` covers line 41 in edit.py."""
    edit("builtin.mock.basic")
    assert len(mock_editor) == 1
    assert "repos/builtin.mock/applications/basic/application.py" in mock_editor[0]


def test_edit_repo_path(mock_applications, mock_editor):
    """Test `ramble edit --repo <path> <name>` covers line 47 in edit.py."""
    import ramble.repository

    repo_dir = (
        ramble.repository.paths[ramble.repository.ObjectTypes.applications]
        .get_repo("builtin.mock")
        .root
    )
    edit("--repo", repo_dir, "basic")
    assert len(mock_editor) == 1
    assert "repos/builtin.mock/applications/basic/application.py" in mock_editor[0]


def test_edit_application_with_tpl_files(mock_applications, monkeypatch):
    """Test that ramble edit opens .tpl files alongside application.py"""
    recorded_calls = []

    def mock_editor(*args, **kwargs):
        recorded_calls.extend(args)

    monkeypatch.setattr("ramble.cmd.edit.editor", mock_editor)
    edit("template")

    assert len(recorded_calls) == 3
    assert recorded_calls[0].endswith("application.py")
    assert recorded_calls[1].endswith("bar.tpl")
    assert recorded_calls[2].endswith("script.sh.tpl")
