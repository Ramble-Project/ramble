# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import copy
from typing import Any, Dict, List

from llnl.util.tty.colify import colify

import ramble.config
import ramble.filters
import ramble.util.colors as color
import ramble.workspace
from ramble.error import RambleError
from ramble.util.logger import logger

description = "manage global or workspace-scoped filter groups"
section = "config"
level = "long"


def setup_parser(subparser):
    scopes_metavar = ramble.config.scopes_metavar

    subparser.add_argument(
        "--scope",
        choices=ramble.config.scopes_choices(include_workspace=True),
        metavar=scopes_metavar,
        default=None,
        help="configuration scope to modify/list (default: user for modify, all for list)",
    )

    actions = subparser.add_subparsers(metavar="ACTION", dest="action")

    add_parser = actions.add_parser("add", help="add a filter group")
    add_parser.add_argument("-n", "--name", required=True, help="name of filter group")
    add_parser.add_argument(
        "--where",
        action="append",
        help="inclusive filter expression. Can be specified multiple times.",
    )
    add_parser.add_argument(
        "--exclude-where",
        dest="exclude_where",
        action="append",
        help="exclusive filter expression. Can be specified multiple times.",
    )

    remove_parser = actions.add_parser("remove", aliases=["rm"], help="remove a filter group")
    remove_parser.add_argument("-n", "--name", required=True, help="name of filter group")

    list_parser = actions.add_parser("list", help="list defined filter groups")
    list_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show the filter group definition for each",
    )
    actions.add_parser("blame", help="show defined filter groups with sources")


def _resolve_scope(args, default_scope=None):
    scope = args.scope if args.scope is not None else default_scope
    if scope:
        try:
            scope = ramble.config.resolve_scope(scope)
        except ValueError as e:
            logger.die(str(e))
    return scope


def filter_groups(parser, args):
    action = args.action
    if not action:
        parser.print_help()
        return

    if action == "list":
        return filter_groups_list(args)
    elif action == "blame":
        return filter_groups_blame(args)
    else:
        scope = _resolve_scope(args, default_scope="user")
        if action == "add":
            return filter_groups_add(scope, args)
        elif action in ("remove", "rm"):
            return filter_groups_remove(scope, args)


def filter_groups_add(scope, args):
    name = args.name

    try:
        ramble.filters.validate_filter_group_name(name)
    except RambleError as e:
        logger.die(str(e))

    if not args.where and not args.exclude_where:
        logger.die("At least one of --where or --exclude-where must be specified.")

    group_def = {}
    if args.where:
        group_def["where"] = args.where
    if args.exclude_where:
        group_def["exclude_where"] = args.exclude_where

    existing = ramble.config.get(f"filter_groups:{name}", scope=scope)
    if existing is not None:
        logger.msg(f"Updating existing filter group '{name}' in scope '{scope}'.")
    else:
        logger.msg(f"Adding filter group '{name}' to scope '{scope}'.")

    ws = ramble.workspace.active_workspace()
    if ws and scope == ws.ws_file_config_scope_name():
        with ws.write_transaction():
            ramble.config.set(f"filter_groups:{name}", group_def, scope=scope)
    else:
        ramble.config.set(f"filter_groups:{name}", group_def, scope=scope)


def filter_groups_remove(scope, args):
    name = args.name

    existing = ramble.config.get(f"filter_groups:{name}", scope=scope)
    if existing is None:
        logger.die(f"Filter group '{name}' not found in scope '{scope}'.")

    logger.msg(f"Removing filter group '{name}' from scope '{scope}'.")

    groups = ramble.config.get("filter_groups", scope=scope)
    if groups:
        groups = copy.deepcopy(groups)
        groups.pop(name, None)

        ws = ramble.workspace.active_workspace()
        if ws and scope == ws.ws_file_config_scope_name():
            with ws.write_transaction():
                ramble.config.set("filter_groups", groups, scope=scope)
        else:
            ramble.config.set("filter_groups", groups, scope=scope)


def print_filter_groups(resolved_scope_name=None, original_scope_name=None, verbose=False):
    groups_to_print = []

    if original_scope_name is not None:
        groups = ramble.config.config.get_config("filter_groups", scope=resolved_scope_name)
        if groups:
            display_name = (
                "workspace"
                if resolved_scope_name.startswith("workspace:")
                else resolved_scope_name
            )
            for name, definition in groups.items():
                groups_to_print.append(
                    {"scope": display_name, "name": name, "definition": definition}
                )
        else:
            logger.warn(f"No filter groups defined in scope '{original_scope_name}'.")
            return 0
    else:
        for scope in ramble.config.config:
            try:
                groups = ramble.config.config.get_config("filter_groups", scope=scope.name)
                if groups:
                    display_name = (
                        "workspace" if scope.name.startswith("workspace:") else scope.name
                    )
                    for name, definition in groups.items():
                        groups_to_print.append(
                            {"scope": display_name, "name": name, "definition": definition}
                        )
            except Exception:
                pass

    if not groups_to_print:
        logger.warn("No filter groups defined.")
        return 0

    if verbose:
        current_scope = None
        first = True
        for item in groups_to_print:
            scope = item["scope"]
            name = item["name"]
            definition = item["definition"]
            if scope != current_scope:
                if not first:
                    color.cprint("")
                first = False
                color.cprint(f"{color.section_title('Scope:')} {scope}")
                current_scope = scope

            lines = [color.nested_1(f"    {name}:")]
            if "where" in definition:
                lines.append("        where:")
                lines.extend(f"        - {w}" for w in definition["where"])
            if "exclude_where" in definition:
                lines.append("        exclude_where:")
                lines.extend(f"        - {ew}" for ew in definition["exclude_where"])
            color.cprint("\n".join(lines))
    else:
        scope_groups: Dict[str, List[str]] = {}
        for item in groups_to_print:
            scope = item["scope"]
            name = item["name"]
            if scope not in scope_groups:
                scope_groups[scope] = []
            scope_groups[scope].append(name)

        out_stream = logger.active_stream()
        colify_opts: Dict[str, Any] = {"indent": 4, "padding": 2}
        if out_stream:
            colify_opts["output"] = out_stream

        first = True
        for scope, names in scope_groups.items():
            if not first:
                color.cprint("", stream=out_stream)
            first = False

            color.cprint(
                f"{color.section_title('Scope:')} {scope}",
                stream=out_stream,
            )
            colify(names, **colify_opts)

    return 0


def filter_groups_list(args):
    verbose = getattr(args, "verbose", False)
    resolved_scope_name = None
    if args.scope is not None:
        resolved_scope_name = _resolve_scope(args)

    return print_filter_groups(
        resolved_scope_name=resolved_scope_name,
        original_scope_name=args.scope,
        verbose=verbose,
    )


def filter_groups_blame(args):
    ramble.config.config.print_section("filter_groups", blame=True)
