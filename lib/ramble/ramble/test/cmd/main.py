# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import signal

import pytest

import ramble.main

pytestmark = pytest.mark.usefixtures("mutable_config", "workspace_deactivate")


def test_unknown_global_argument_is_rejected(capsys):
    ret = ramble.main.main(argv=["--madeuparg", "workspace", "list"])

    captured = capsys.readouterr()
    assert ret == 1
    assert "unrecognized arguments: --madeuparg" in captured.err


def test_command_argument_before_command_is_rejected(capsys):
    ret = ramble.main.main(argv=["--dry-run", "workspace", "list"])

    captured = capsys.readouterr()
    assert ret == 1
    assert "unrecognized arguments: --dry-run" in captured.err


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_global_version(flag, capsys):
    ret = ramble.main.main(argv=[flag])
    captured = capsys.readouterr()
    assert ret == 0
    assert str(ramble.ramble_version) in captured.out


@pytest.mark.parametrize("flag", ["-h", "--help"])
def test_global_help(flag, capsys):
    ret = ramble.main.main(argv=[flag])
    captured = capsys.readouterr()
    assert ret == 0
    assert "A flexible benchmark experiment manager" in captured.out


@pytest.mark.parametrize("flag", ["-H", "--all-help"])
def test_global_all_help(flag, capsys):
    ret = ramble.main.main(argv=[flag])
    captured = capsys.readouterr()
    assert ret == 0
    assert "Complete list of ramble commands:" in captured.out


def test_global_config_var(capsys):
    ret = ramble.main.main(argv=["-c", "config:debug:true", "help"])
    captured = capsys.readouterr()
    assert ret == 0
    assert "A flexible benchmark experiment manager" in captured.out


def test_global_config_scope(tmpdir, capsys):
    ret = ramble.main.main(argv=["-C", str(tmpdir), "help"])
    captured = capsys.readouterr()
    assert ret == 0
    assert "A flexible benchmark experiment manager" in captured.out


def test_keyboard_interrupt_exit_code(monkeypatch, capsys):
    def mock_invoke(*args, **kwargs):
        raise KeyboardInterrupt()

    monkeypatch.setattr(ramble.main, "_invoke_command", mock_invoke)
    ret = ramble.main.main(argv=["workspace", "list"])
    captured = capsys.readouterr()
    assert ret == ramble.main.POSIX_SIGNAL_EXIT_OFFSET + signal.SIGINT.value
    assert "Keyboard interrupt." in captured.err
