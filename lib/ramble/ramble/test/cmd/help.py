# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

from ramble.main import RambleCommand

help_cmd = RambleCommand("help")


def test_help_default():
    """Test that `ramble help` gives short help."""
    help_cmd = RambleCommand("help")
    output = help_cmd()
    assert "A flexible benchmark experiment manager" in output


def test_help_all():
    """Test that `ramble help --all` and `-a` list all available commands."""
    help_cmd = RambleCommand("help")
    out_all = help_cmd("--all")
    assert "Complete list of ramble commands:" in out_all
    assert "workspace" in out_all

    help_cmd2 = RambleCommand("help")
    out_short = help_cmd2("-a")
    assert "Complete list of ramble commands:" in out_short
    assert "workspace" in out_short


def test_help_spec():
    """Test that `ramble help --spec` prints the spec guide."""
    help_cmd = RambleCommand("help")
    output = help_cmd("--spec")
    assert "spec expression syntax:" in output
    assert "[namespace.][type.]name[@version]" in output
    assert "builtin.app.hostname" in output


@pytest.mark.parametrize("subcmd", ["config", "info", "list", "workspace", "help"])
def test_help_command(subcmd):
    """Test that `ramble help <cmd>` prints help for the given command."""
    help_cmd = RambleCommand("help")
    output = help_cmd(subcmd)
    assert f"usage: ramble {subcmd}" in output or "usage: ramble" in output
