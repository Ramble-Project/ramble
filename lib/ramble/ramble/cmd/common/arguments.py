# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import argparse
import inspect
from typing import Callable, Dict

from ramble.util.logger import logger

from spack.util.pattern import Args

__all__ = [
    "add_common_arguments",
    "allows_unknown_args",
    "validate_unknown_args",
    "sanitize_arg_name",
    "setup_subcommands_from_prefix",
]

#: dictionary of argument-generating functions, keyed by name
_arguments: Dict[str, Callable[[], Args]] = {}


def arg(fn):
    """Decorator for a function that generates a common argument.

    This ensures that argument bunches are created lazily. Decorate
    argument-generating functions below with @arg so that
    ``add_common_arguments()`` can find them.

    """
    _arguments[fn.__name__] = fn
    return fn


def add_common_arguments(parser, list_of_arguments):
    """Extend a parser with extra arguments

    Args:
        parser: parser to be extended
        list_of_arguments: arguments to be added to the parser
    """
    for argument in list_of_arguments:
        if argument not in _arguments:
            message = 'Trying to add non existing argument "{0}" to a command'
            raise KeyError(message.format(argument))

        x = _arguments[argument]()
        parser.add_argument(*x.flags, **x.kwargs)


def allows_unknown_args(command):
    """Implements really simple argument injection for unknown arguments.

    Commands may add an optional argument called "unknown args" to
    indicate they can handle unknown args. This checks that the
    command allows `unknown_args` as an input argument.
    """
    params = inspect.signature(command).parameters
    return "unknown_args" in params


def validate_unknown_args(command, unknown_args):
    """Validate command allows unknown arguments when they are passed in"""
    if allows_unknown_args(command):
        return
    elif unknown_args:
        logger.die(f'unrecognized arguments: {" ".join(unknown_args)}')


@arg
def yes_to_all():
    return Args(
        "-y",
        "--yes-to-all",
        action="store_true",
        dest="yes_to_all",
        help='assume "yes" is the answer to every confirmation request',
    )


@arg
def tags():
    return Args("-t", "--tags", action="append", help="filter a package query by tags")


@arg
def application():
    return Args("application", help="application name")


@arg
def workspace():
    return Args("workspace", help="workspace name")


@arg
def specs():
    return Args("specs", nargs=argparse.REMAINDER, help="one or more workload specs")


@arg
def obj_type():
    from ramble.repository import OBJECT_NAMES, default_type

    return Args(
        "--type",
        default=f"{default_type.name}",
        help=f"type of objects. Defaults to '{default_type.name}'. "
        f"Allowed types are {', '.join(OBJECT_NAMES)}",
    )


@arg
def repo_type():
    from ramble.repository import OBJECT_NAMES, default_type

    return Args(
        "-t",
        "--type",
        default="any",
        help=f"type of repositories to manage. Defaults to '{default_type.name}'. "
        f"Allowed types are {', '.join(OBJECT_NAMES)}, or any",
    )


@arg
def phases():
    return Args(
        "--phases",
        dest="phases",
        nargs="+",
        default=["*"],
        help="select phases to execute when performing setup. " + "Phase names support globbing",
        required=False,
    )


@arg
def include_phase_dependencies():
    return Args(
        "--include-phase-dependencies",
        dest="include_phase_dependencies",
        action="store_true",
        help="if set, phase dependencies are automatically added to "
        "the list of executed phases",
        required=False,
    )


@arg
def profile_phases():
    return Args(
        "--profile-phase",
        nargs="+",
        action="append",
        default=None,
        dest="profile_phases",
        help="phases to be profiled by line_profiler",
        required=False,
    )


@arg
def profile_phase_output():
    return Args(
        "--profile-phase-output",
        default=None,
        dest="profile_phase_output",
        help="file path to save the phase line_profiler output",
        required=False,
    )


@arg
def where():
    return Args(
        "--where",
        dest="where",
        nargs="+",
        action="append",
        help="inclusive filter on experiments where the provided logical statement is True",
        required=False,
    )


@arg
def exclude_where():
    return Args(
        "--exclude-where",
        dest="exclude_where",
        nargs="+",
        action="append",
        help="exclusive filter experiments where the provided logical statement is True",
        required=False,
    )


@arg
def filter_tags():
    return Args(
        "--filter-tags",
        action="append",
        nargs="+",
        help="filter experiments to only those that include the provided tags",
        required=False,
    )


@arg
def no_checksum():
    return Args(
        "-n",
        "--no-checksum",
        action="store_true",
        default=False,
        help="do not use checksums to verify downloaded files (unsafe)",
    )


@arg
def filter_group():
    return Args(
        "--fg",
        "--filter-group",
        dest="filter_group",
        help="Filter experiments using a logical expression of filter groups",
        required=False,
    )


@arg
def exclude_filter_group():
    return Args(
        "--efg",
        "--exclude-filter-group",
        dest="exclude_filter_group",
        help="Exclude experiments matching a logical expression of filter groups",
        required=False,
    )


def sanitize_arg_name(base_name: str) -> str:
    """Format argument/command names by converting hyphens to underscores."""
    return base_name.replace("-", "_")


def setup_subcommands_from_prefix(
    subparser,
    dest: str,
    subcommands: list,
    prefix: str,
    globals_dict: dict,
    subcommand_functions: dict,
    inject_dry_run: bool = False,
):
    """Set up subparsers and map functions for a prefixed list of subcommands.

    Args:
        subparser: Parent ArgumentParser or subparser
        dest (str): Destination attribute name for selected subcommand
        subcommands (list): List of subcommand names or (name, *aliases) tuples
        prefix (str): Prefix used in function names (e.g. 'workspace', 'data', 'deployment')
        globals_dict (dict): The globals() dictionary of the calling module
        subcommand_functions (dict): Dictionary mapping command/alias name -> function
        inject_dry_run (bool): Whether to automatically add --dry-run to subparsers if not present
    """
    sp = subparser.add_subparsers(metavar="SUBCOMMAND", dest=dest)

    for cmd_entry in subcommands:
        if isinstance(cmd_entry, (list, tuple)):
            name, aliases = cmd_entry[0], list(cmd_entry[1:])
        else:
            name = cmd_entry
            aliases = []

        # add commands to subcommands dict
        function_name = sanitize_arg_name(f"{prefix}_{name}")
        function = globals_dict[function_name]
        for alias in [name] + aliases:
            subcommand_functions[alias] = function

        # make a subparser and run the command's setup function on it
        setup_parser_cmd_name = sanitize_arg_name(f"{prefix}_{name}_setup_parser")
        setup_parser_cmd = globals_dict[setup_parser_cmd_name]

        subsubparser = sp.add_parser(
            name,
            aliases=aliases,
            help=setup_parser_cmd.__doc__,
            description=setup_parser_cmd.__doc__,
        )
        setup_parser_cmd(subsubparser)

        if inject_dry_run and "--dry-run" not in subsubparser._option_string_actions:
            subsubparser.add_argument(
                "--dry-run",
                dest="dry_run",
                action="store_true",
                help=f"perform a dry run of the {name} command",
            )
