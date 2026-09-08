# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.cmd.software_definitions
from ramble.error import RambleCommandError
from ramble.main import RambleCommand

pytestmark = pytest.mark.usefixtures("config")

software_defs = RambleCommand("software-definitions")


def test_software_definitions_runs():
    software_defs()


def test_software_definitions_summary():
    expected_strs = ["Software Summary", "Software Packages", "Compiler Definitions", "Spec:"]

    out = software_defs("--summary")
    for expected_str in expected_strs:
        assert expected_str in out

    out = software_defs("-s")
    for expected_str in expected_strs:
        assert expected_str in out


def test_software_definitions_conflicts_runs():
    software_defs("-c")


def test_software_definitions_error_on_conflicts():
    expected_strs = [
        "Software Definition Conflicts:",
        "Package:",
        "Defined as:",
        "In objects:",
        "Conflicts with objects:",
    ]

    try:
        software_defs("-e")
    except RambleCommandError:
        if software_defs.returncode not in (None, 0):
            out = software_defs("-c")
            for expected_str in expected_strs:
                assert expected_str in out


def test_software_definitions_conflicts_output(mock_applications, mock_base_applications):
    out = software_defs("-c")
    assert "Software Definition Conflicts:" in out
    assert "Package: zlib" in out
    assert "Defined as:" in out
    assert "pkg_spec = zlib@1.2.11" in out
    assert "In objects:" in out
    assert "ramble.app.builtin.mock.conflict-test" in out
    assert "Conflicts with objects:" in out
    assert "ramble.app.builtin.mock.multi-package-manager-specs" in out


def test_software_definitions_unused_compilers_output(mock_applications, mock_base_applications):
    out = software_defs("-c")
    assert "Unused Compilers:" in out
    assert "Compiler my_unused_compiler is not used in packages:" in out
    assert "ramble.app.builtin.mock.unused-compiler-test" in out


def test_software_definitions_error_on_conflicts_overflow(monkeypatch):
    monkeypatch.setattr(ramble.cmd.software_definitions, "count_conflicts", lambda: 256)
    out = software_defs("-e", fail_on_error=False)
    assert software_defs.returncode == 1
    assert "256 conflicts detected." in out


def test_software_definitions_error_on_conflicts_zero(monkeypatch):
    monkeypatch.setattr(ramble.cmd.software_definitions, "count_conflicts", lambda: 0)
    out = software_defs("-e", fail_on_error=False)
    assert software_defs.returncode == 0
    assert "0 conflicts detected." in out


def test_software_definitions_error_on_conflicts_single(monkeypatch):
    monkeypatch.setattr(ramble.cmd.software_definitions, "count_conflicts", lambda: 1)
    out = software_defs("-e", fail_on_error=False)
    assert software_defs.returncode == 1
    assert "1 conflict detected." in out
