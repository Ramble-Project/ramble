# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import collections
import os
import shutil
from typing import List

import llnl.util.filesystem as fs
from llnl.util import tty

import ramble.cmd.common.arguments
import ramble.config
import ramble.util.editor
import ramble.workspace
from ramble.util.logger import logger

import spack.util.spack_yaml as syaml

description = "get and set configuration options"
section = "config"
level = "long"

_add_parser = None


def setup_parser(subparser):
    scopes_metavar = ramble.config.scopes_metavar

    # User can only choose one
    subparser.add_argument(
        "-s",
        "--scope",
        choices=ramble.config.scopes_choices(include_workspace=True),
        metavar=scopes_metavar,
        help="configuration scope to read/modify (default: user if no workspace, "
        "workspace if active)",
    )

    sp = subparser.add_subparsers(metavar="SUBCOMMAND", dest="config_command")

    get_parser = sp.add_parser("get", help="print configuration values")
    get_parser.add_argument(
        "section",
        help="configuration section to print. " "options: %(choices)s",
        nargs="?",
        metavar="section",
        choices=ramble.config.section_schemas,
    )

    blame_parser = sp.add_parser(
        "blame", help="print configuration annotated with source file:line"
    )
    blame_parser.add_argument(
        "section",
        help="configuration section to print. " "options: %(choices)s",
        metavar="section",
        choices=ramble.config.section_schemas,
    )

    edit_parser = sp.add_parser(
        "edit",
        help="edit configuration file. " + "Defaults to ramble.yaml with an activated workspace",
    )
    edit_parser.add_argument(
        "section",
        help="configuration section to edit. " "options: %(choices)s",
        metavar="section",
        nargs="?",
        choices=ramble.config.section_schemas,
    )
    edit_parser.add_argument(
        "--print-file", action="store_true", help="print the file name that would be edited"
    )

    sp.add_parser("list", help="list configuration sections")

    add_parser = sp.add_parser("add", help="add configuration parameters")
    add_parser.add_argument(
        "path",
        nargs="?",
        help="colon-separated path to config that should be added," " e.g. 'config:default:true'",
    )
    add_parser.add_argument("-f", "--file", help="file from which to set all config values")

    remove_parser = sp.add_parser("remove", aliases=["rm"], help="remove configuration parameters")
    remove_parser.add_argument(
        "path",
        help="colon-separated path to config that should be removed,"
        " e.g. 'config:default:true'",
    )

    # Make the add parser available later
    global _add_parser
    _add_parser = add_parser

    update = sp.add_parser("update", help="update configuration files to the latest format")
    ramble.cmd.common.arguments.add_common_arguments(update, ["yes_to_all"])
    update.add_argument("section", help="section to update")

    revert = sp.add_parser(
        "revert", help="revert configuration files to their state before update"
    )
    ramble.cmd.common.arguments.add_common_arguments(revert, ["yes_to_all"])
    revert.add_argument("section", help="section to update")


def _get_scope_and_section(args):
    """Extract config scope and section from arguments."""
    logger.debug(f" Args = {str(args)}")
    scope = args.scope
    section = getattr(args, "section", None)
    path = getattr(args, "path", None)

    # special handling for commands that take value instead of section
    if path:
        section = path[: path.find(":")] if ":" in path else path

    if scope:
        try:
            scope = ramble.config.resolve_scope(scope)
        except ValueError as e:
            logger.die(str(e))
    else:
        ws = ramble.workspace.active_workspace()
        if ws:
            scope = ws.ws_file_config_scope_name()
        else:
            scope = "user"

    return scope, section


def config_get(args):
    """Dump merged YAML configuration for a specific section.

    With no arguments and an active workspace, print the contents of
    the workspace's config file (ramble.yaml).
    """
    scope, section = _get_scope_and_section(args)

    if section is not None:
        ramble.config.config.print_section(section)

    elif scope and scope.startswith("workspace:"):
        config_file = ramble.config.config.get_config_filename(scope, section)
        if os.path.exists(config_file):
            with open(config_file, encoding="utf-8") as f:
                print(f.read())
        else:
            logger.die(f"workspace has no {ramble.workspace.CONFIG_FILE_NAME} file")

    else:
        logger.die("`ramble config get` requires a section argument " "or an active workspace.")


def config_blame(args):
    """Print out line-by-line blame of merged YAML."""
    ramble.config.config.print_section(args.section, blame=True)


def config_edit(args):
    """Edit the configuration file for a specific scope and config section.

    With no arguments and an active workspace, edit the ramble.yaml for
    the active workspace.
    """
    ramble_ws = os.environ.get(ramble.workspace.RAMBLE_WORKSPACE_VAR)
    if ramble_ws and not args.scope:
        # Don't use the scope object for workspaces, as `config edit` can be called
        # for a malformed workspace. Use RAMBLE_WORKSPACE to find ramble.yaml.
        config_file = ramble.workspace.config_file(ramble_ws)
    else:
        # If we aren't editing a ramble.yaml file, get config path from scope.
        scope, section = _get_scope_and_section(args)
        if not section and (not scope or not scope.startswith("workspace:")):
            logger.die(
                "`ramble config edit` requires a section argument " "or an active workspace."
            )
        config_file = ramble.config.config.get_config_filename(scope, section)

    if args.print_file:
        print(config_file)
    else:
        if not os.path.isdir(os.path.dirname(config_file)):
            fs.mkdirp(os.path.dirname(config_file))

        try:
            return ramble.util.editor.editor(config_file)
        except TypeError:
            logger.die("No valid editor was found.")


def config_list(args):
    """List the possible configuration sections.

    Used primarily for shell tab completion scripts.
    """
    print(" ".join(list(ramble.config.section_schemas)))


def config_add(args):
    """Add the given configuration to the specified config scope

    This is a stateful operation that edits the config files."""
    if not (args.file or args.path):
        logger.error("No changes requested. Specify a file or value.")
        if _add_parser:
            _add_parser.print_help()
        exit(1)

    scope, _ = _get_scope_and_section(args)

    if args.file:
        ramble.config.add_from_file(args.file, scope=scope)

    if args.path:
        ramble.config.add(args.path, scope=scope)


def config_remove(args):
    """Remove the given configuration from the specified config scope

    This is a stateful operation that edits the config files."""
    scope, _ = _get_scope_and_section(args)

    path, _, value = args.path.rpartition(":")
    existing = ramble.config.get(path, scope=scope)

    if not isinstance(existing, (list, dict)):
        path, _, value = path.rpartition(":")
        existing = ramble.config.get(path, scope=scope)

    value = syaml.load(value)

    if isinstance(existing, list):
        values = value if isinstance(value, list) else [value]
        for v in values:
            existing.remove(v)
    elif isinstance(existing, dict):
        existing.pop(value, None)
    else:
        # This should be impossible to reach
        raise ramble.config.ConfigError("Config has nested non-dict values")

    ramble.config.set(path, existing, scope)


def _can_update_config_file(scope_dir, cfg_file):
    dir_ok = fs.can_write_to_dir(scope_dir)
    cfg_ok = fs.can_access(cfg_file)
    return dir_ok and cfg_ok


def config_update(args) -> None:
    # Read the configuration files
    ramble.config.config.get_config(args.section, scope=args.scope)
    updates: List[ramble.config.ConfigScope] = list(
        filter(
            lambda s: not isinstance(
                s, (ramble.config.InternalConfigScope, ramble.config.ImmutableConfigScope)
            ),
            ramble.config.config.format_updates[args.section],
        )
    )

    cannot_overwrite, skip_system_scope = [], False
    for scope in updates:
        cfg_file = ramble.config.config.get_config_filename(scope.name, args.section)
        scope_dir = scope.path
        can_be_updated = _can_update_config_file(scope_dir, cfg_file)
        if not can_be_updated:
            if scope.name == "system":
                skip_system_scope = True
                msg = (
                    'Not enough permissions to write to "system" scope. '
                    f"Skipping update at that location [cfg={cfg_file}]"
                )
                logger.warn(msg)
                continue
            cannot_overwrite.append((scope, cfg_file))

    if cannot_overwrite:
        msg = "Detected permission issues with the following scopes:\n\n"
        for scope, cfg_file in cannot_overwrite:
            msg += f"\t[scope={scope.name}, cfg={cfg_file}]\n"
        msg += (
            "\nEither ensure that you have sufficient permissions to "
            "modify these files or do not include these scopes in the "
            "update."
        )
        logger.die(msg)

    if skip_system_scope:
        updates = [x for x in updates if x.name != "system"]

    # Report if there are no updates to be done
    if not updates:
        logger.msg(f'No updates needed for "{args.section}" section.')
        return

    proceed = True
    if not args.yes_to_all:
        msg = (
            "The following configuration files are going to be updated to"
            " the latest schema format:\n\n"
        )
        for scope in updates:
            cfg_file = ramble.config.config.get_config_filename(scope.name, args.section)
            msg += f"\t[scope={scope.name}, file={cfg_file}]\n"
        msg += (
            "\nIf the configuration files are updated, versions of Ramble "
            "that are older than this version may not be able to read "
            "them. Ramble stores backups of the updated files which can "
            'be retrieved with "ramble config revert"'
        )
        logger.msg(msg)
        proceed = bool(tty.get_yes_or_no("Do you want to proceed?", default=False))

    if not proceed:
        logger.die("Operation aborted.")

    # Get a function to update the format
    update_fn = ramble.config.ensure_latest_format_fn(args.section)
    for scope in updates:
        cfg_file = ramble.config.config.get_config_filename(scope.name, args.section)
        with open(cfg_file, encoding="utf-8") as f:
            data = ramble.config.load_config(f) or {}
            data = data.pop(args.section, {})
        update_fn(data)

        # Make a backup copy and rewrite the file
        bkp_file = cfg_file + ".bkp"
        shutil.copy(cfg_file, bkp_file)
        ramble.config.config.update_config(args.section, data, scope=scope.name, force=True)
        logger.msg(f'File "{cfg_file}" updated [backup={bkp_file}]')


def _can_revert_update(scope_dir, cfg_file, bkp_file):
    dir_ok = fs.can_write_to_dir(scope_dir)
    cfg_ok = not os.path.exists(cfg_file) or fs.can_access(cfg_file)
    bkp_ok = fs.can_access(bkp_file)
    return dir_ok and cfg_ok and bkp_ok


def config_revert(args):
    scopes = [args.scope] if args.scope else [x.name for x in ramble.config.config.file_scopes]

    # Search for backup files in the configuration scopes
    Entry = collections.namedtuple("Entry", ["scope", "cfg", "bkp"])
    to_be_restored, cannot_overwrite = [], []
    for scope in scopes:
        cfg_file = ramble.config.config.get_config_filename(scope, args.section)
        bkp_file = cfg_file + ".bkp"

        # If the backup files doesn't exist move to the next scope
        if not os.path.exists(bkp_file):
            continue

        # If it exists and we don't have write access in this scope
        # keep track of it and report a comprehensive error later
        entry = Entry(scope, cfg_file, bkp_file)
        scope_dir = os.path.dirname(bkp_file)
        can_be_reverted = _can_revert_update(scope_dir, cfg_file, bkp_file)
        if not can_be_reverted:
            cannot_overwrite.append(entry)
            continue

        to_be_restored.append(entry)

    # Report errors if we can't revert a configuration
    if cannot_overwrite:
        msg = "Detected permission issues with the following scopes:\n\n"
        for e in cannot_overwrite:
            msg += "\t[scope={0.scope}, cfg={0.cfg}, bkp={0.bkp}]\n".format(e)
        msg += (
            "\nEither ensure to have the right permissions before retrying"
            " or be more specific on the scope to revert."
        )
        logger.die(msg)

    proceed = True
    if not args.yes_to_all:
        msg = "The following scopes will be restored from the corresponding" " backup files:\n"
        for entry in to_be_restored:
            msg += "\t[scope={0.scope}, bkp={0.bkp}]\n".format(entry)
        msg += "This operation cannot be undone."
        logger.msg(msg)
        proceed = bool(tty.get_yes_or_no("Do you want to proceed?", default=False))

    if not proceed:
        logger.die("Operation aborted.")

    for _, cfg_file, bkp_file in to_be_restored:
        shutil.copy(bkp_file, cfg_file)
        os.unlink(bkp_file)
        logger.msg(f'File "{cfg_file}" reverted to old state')


def config(parser, args):
    action = {
        "get": config_get,
        "blame": config_blame,
        "edit": config_edit,
        "list": config_list,
        "add": config_add,
        "rm": config_remove,
        "remove": config_remove,
        "update": config_update,
        "revert": config_revert,
    }
    action[args.config_command](args)
