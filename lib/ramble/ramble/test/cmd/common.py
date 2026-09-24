# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import argparse

import ramble.cmd.common


def test_sanitize_arg_name():
    assert ramble.cmd.common.sanitize_arg_name("foo-bar") == "foo_bar"
    assert ramble.cmd.common.sanitize_arg_name("simple") == "simple"
    assert ramble.cmd.common.sanitize_arg_name("a-b-c_d") == "a_b_c_d"


def test_setup_subcommands_from_prefix():
    def mock_cmd_foo_setup_parser(subparser):
        """Foo command docstring"""
        subparser.add_argument("--test-opt", action="store_true")

    def mock_cmd_foo(args):
        return "foo executed"

    def mock_cmd_bar_baz_setup_parser(subparser):
        """Bar Baz command docstring"""
        subparser.add_argument("--bar-opt", type=str)

    def mock_cmd_bar_baz(args):
        return "bar-baz executed"

    mock_globals = {
        "mock_cmd_foo_setup_parser": mock_cmd_foo_setup_parser,
        "mock_cmd_foo": mock_cmd_foo,
        "mock_cmd_bar_baz_setup_parser": mock_cmd_bar_baz_setup_parser,
        "mock_cmd_bar_baz": mock_cmd_bar_baz,
    }
    subcommand_functions = {}
    subcommands = [
        "foo",
        ("bar-baz", "bb", "barbaz"),
    ]

    parser = argparse.ArgumentParser()
    ramble.cmd.common.setup_subcommands_from_prefix(
        subparser=parser,
        dest="subcommand",
        subcommands=subcommands,
        prefix="mock_cmd",
        globals_dict=mock_globals,
        subcommand_functions=subcommand_functions,
        inject_dry_run=True,
    )

    assert "foo" in subcommand_functions
    assert "bar-baz" in subcommand_functions
    assert "bb" in subcommand_functions
    assert "barbaz" in subcommand_functions
    assert subcommand_functions["bb"] == mock_cmd_bar_baz

    args = parser.parse_args(["foo", "--test-opt", "--dry-run"])
    assert args.subcommand == "foo"
    assert args.test_opt is True
    assert args.dry_run is True

    args_alias = parser.parse_args(["bb", "--bar-opt", "hello"])
    assert args_alias.subcommand == "bb"
    assert args_alias.bar_opt == "hello"


def test_shell_init_instructions(caplog):
    ramble.cmd.common.shell_init_instructions(
        "workspace activate", "ramble workspace activate {sh_arg}"
    )
