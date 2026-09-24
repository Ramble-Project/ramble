# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import subprocess
import sys

import pytest

import ramble.util.cleaner as cleaner
import ramble.util.file_editor as file_editor


def test_cleaner_and_editor_script_getters():
    cleaner_content = cleaner.get_cleaner_script()
    assert "Ramble Directory Cleaner" in cleaner_content
    assert cleaner.get_cleaner_exec_path() == "{workspace_shared}/utilities/_ramble_cleaner.py"

    editor_content = file_editor.get_file_editor_script()
    assert "Ramble File Editor" in editor_content
    assert (
        file_editor.get_file_editor_exec_path()
        == "{workspace_shared}/utilities/_ramble_file_editor.py"
    )


@pytest.fixture
def cleaner_script_path(tmpdir):
    script_path = tmpdir.join("test_cleaner.py")
    script_path.write(cleaner.get_cleaner_script())
    return str(script_path)


@pytest.fixture
def run_cleaner(cleaner_script_path):
    def _run(*args):
        return subprocess.run(
            [sys.executable, cleaner_script_path] + list(args),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )

    return _run


def test_cleaner_script_execution_non_recursive(tmpdir, run_cleaner):
    # Setup test files
    dir_path = tmpdir.mkdir("test_clean_dir")
    file_keep = dir_path.join("keep.txt")
    file_keep.write("keep me")
    file_remove = dir_path.join("remove.tmp")
    file_remove.write("delete me")

    res = run_cleaner(
        "--directory",
        str(dir_path),
        "--regex",
        r".*\.tmp$",
    )

    assert res.returncode == 0
    assert file_keep.exists()
    assert not file_remove.exists()


def test_cleaner_script_execution_recursive(tmpdir, run_cleaner):
    # Setup test nested structure
    dir_path = tmpdir.mkdir("test_recursive_dir")
    subdir = dir_path.mkdir("sub")
    file_sub_keep = subdir.join("keep.txt")
    file_sub_keep.write("keep me")
    file_sub_del = subdir.join("delete.log")
    file_sub_del.write("delete me")

    res = run_cleaner(
        "--directory",
        str(dir_path),
        "--regex",
        r".*\.log$",
        "--recurse",
    )

    assert res.returncode == 0
    assert file_sub_keep.exists()
    assert not file_sub_del.exists()


def test_cleaner_script_invalid_regex(tmpdir, run_cleaner):
    dir_path = tmpdir.mkdir("test_invalid_dir")
    res = run_cleaner(
        "--directory",
        str(dir_path),
        "--regex",
        r"[invalid",
    )
    assert res.returncode == 1
    assert "Invalid regex pattern" in res.stderr
