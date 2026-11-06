# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from typing import Callable, Dict

import ramble.cmd.common

description = "manage data and databases"
section = "data"
level = "short"

subcommands = [
    "create-db",
    "upgrade-db",
]


def data_create_db_setup_parser(subparser):
    """create the database"""


def data_create_db(args):
    """create the database"""
    import ramble.uploader

    uploader, uri = ramble.uploader.get_uploader_and_uri()
    uploader.create_tables(uri)


def data_upgrade_db_setup_parser(subparser):
    """upgrade the database schema"""
    subparser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        default=False,
        help="validate and report planned schema changes without modifying the database",
    )


def data_upgrade_db(args):
    """upgrade the database schema"""
    import ramble.uploader

    uploader, uri = ramble.uploader.get_uploader_and_uri()
    uploader.upgrade_tables(uri, dry_run=args.dry_run)


#: Dictionary mapping subcommand names and aliases to functions
subcommand_functions: Dict[str, Callable] = {}


def setup_parser(subparser):
    ramble.cmd.common.setup_subcommands_from_prefix(
        subparser=subparser,
        dest="data_command",
        subcommands=subcommands,
        prefix="data",
        globals_dict=globals(),
        subcommand_functions=subcommand_functions,
    )


def data(parser, args, unknown_args=None):
    """Look for a function called data_<name> and call it."""
    action = subcommand_functions[args.data_command]
    action(args)
