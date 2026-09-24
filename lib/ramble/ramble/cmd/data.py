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
]


def data_create_db_setup_parser(subparser):
    """create the database"""


def data_create_db(args):
    """create the database"""
    import ramble.config
    import ramble.uploader
    from ramble.config import ConfigError

    uri = ramble.config.get("config:upload:uri")
    if not uri:
        raise ConfigError("No upload URI (config:upload:uri) in config.")

    uploader_type_str = ramble.config.get("config:upload:type")

    if uploader_type_str is None:
        raise ConfigError("No upload type (config:upload:type) in config.")

    if not hasattr(ramble.uploader.uploader_types, uploader_type_str):
        raise ConfigError(f"Upload type {uploader_type_str} is not valid.")

    uploader_type = getattr(ramble.uploader.uploader_types, uploader_type_str)

    if uploader_type == ramble.uploader.uploader_types.BigQuery:
        uploader = ramble.uploader.BigQueryUploader()
    elif uploader_type == ramble.uploader.uploader_types.SQLite:
        uploader = ramble.uploader.SQLiteUploader()
    else:
        # Note: PrintOnlyUploader shouldn't really be used here since it doesn't create tables
        uploader = ramble.uploader.PrintOnlyUploader()

    if hasattr(uploader, "create_tables"):
        uploader.create_tables(uri)
    else:
        # Some uploaders might not have/need create_tables (like PrintOnly)
        pass


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
