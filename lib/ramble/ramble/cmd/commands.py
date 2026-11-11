# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import argparse
import copy
import os
import re
import sys
from typing import Callable, Dict

import llnl.util.filesystem as fs
from llnl.util.argparsewriter import ArgparseCompletionWriter, ArgparseRstWriter, ArgparseWriter
from llnl.util.tty.colify import colify

import ramble.cmd
import ramble.config
import ramble.main
import ramble.paths
from ramble.main import section_descriptions
from ramble.util.logger import logger

_CMD_HEADER_RE = re.compile(r"\.\. _cmd-(ramble-.*):")

description = "list available ramble commands"
section = "developer"
level = "long"


#: list of command formatters
formatters: Dict[str, Callable] = {}


#: standard arguments for updating completion scripts
#: we iterate through these when called with --update-completion
update_completion_args = {
    # Default one included in source control
    # Disable aliases to avoid custom configs leaking into it
    "bash_no_aliases": {
        "aliases": False,
        "format": "bash",
        "header": os.path.join(ramble.paths.share_path, "bash", "ramble-completion.in"),
        "update": os.path.join(ramble.paths.share_path, "ramble-completion.bash"),
    },
    # Generate a version that supports aliases (including ones defined in `config:aliases`)
    # This one is not included in source control as it is user-specific
    "base_with_aliases": {
        "aliases": True,
        "format": "bash",
        "header": os.path.join(ramble.paths.share_path, "bash", "ramble-completion.in"),
        "update": os.path.join(ramble.paths.share_path, "custom-ramble-completion.bash"),
    },
}


def formatter(func):
    """Decorator used to register formatters"""
    formatters[func.__name__] = func
    return func


def setup_parser(subparser):
    subparser.add_argument(
        "--update-completion",
        action="store_true",
        default=False,
        help="regenerate ramble's tab completion scripts",
    )

    subparser.add_argument(
        "-a", "--aliases", action="store_true", default=False, help="include command aliases"
    )
    subparser.add_argument(
        "--format",
        default="names",
        choices=formatters,
        help="format to be used to print the output (default: names)",
    )
    subparser.add_argument(
        "--header",
        metavar="FILE",
        default=None,
        action="store",
        help="prepend contents of FILE to the output (useful for rst format)",
    )
    subparser.add_argument(
        "--update",
        metavar="FILE",
        default=None,
        action="store",
        help="write output to the specified file, if any command is newer",
    )
    subparser.add_argument(
        "rst_files",
        nargs=argparse.REMAINDER,
        help="list of rst files to search for `_cmd-ramble-<cmd>` cross-refs",
    )


class RambleArgparseRstWriter(ArgparseRstWriter):
    """RST writer tailored for ramble documentation."""

    def __init__(
        self,
        prog,
        out=None,
        aliases=False,
        documented_commands=None,
        rst_levels=None,
    ):
        if documented_commands is None:
            documented_commands = []
        if rst_levels is None:
            rst_levels = ["-", "-", "^", "~", ":", "`"]
        out = sys.stdout if out is None else out
        super().__init__(prog, out, aliases, rst_levels)
        self.documented = documented_commands

    def usage(self, *args):
        string = super().usage(*args)

        cmd = self.parser.prog.replace(" ", "-")
        if cmd in self.documented:
            string += f"\n:ref:`More documentation <cmd-{cmd}>`\n"

        return string


class SubcommandWriter(ArgparseWriter):
    def format(self, cmd):
        return "    " * self.level + cmd.prog + "\n"


_positional_to_subroutine = {
    "application": "_all_applications",
    "spec": "_all_applications",
    "filter": "_all_applications",
    "section": "_config_sections",
    "workspace": "_workspaces",
    "keys": "_keys",
    "help_command": "_subcommands",
    "namespace": "_repos",
    "pytest": "_unit_tests",
    "target": "_location_targets",
}


class BashCompletionWriter(ArgparseCompletionWriter):
    """Write argparse output as bash programmable tab completion."""

    def body(self, positionals, optionals, subcommands):
        if positionals:
            return f"""
    if $list_options
    then
        {self.optionals(optionals)}
    else
        {self.positionals(positionals)}
    fi
"""
        elif subcommands:
            return f"""
    if $list_options
    then
        {self.optionals(optionals)}
    else
        {self.subcommands(subcommands)}
    fi
"""
        else:
            return f"""
    {self.optionals(optionals)}
"""

    def positionals(self, positionals):
        # If match found, return function name
        for positional in positionals:
            for key, value in _positional_to_subroutine.items():
                if positional.startswith(key):
                    return value

        # If no matches found, return empty list
        return 'RAMBLE_COMPREPLY=""'

    def optionals(self, optionals):
        return f"RAMBLE_COMPREPLY=\"{' '.join(optionals)}\""

    def subcommands(self, subcommands):
        return f"RAMBLE_COMPREPLY=\"{' '.join(subcommands)}\""


@formatter
def subcommands(args, out):
    parser = ramble.main.make_argument_parser(color=False)
    ramble.main.add_all_commands(parser)
    writer = SubcommandWriter(parser.prog, out, args.aliases)
    writer.write(parser)


def rst_index(out):
    out.write("\n")

    index = ramble.main.index_commands()
    sections = index["long"]

    dmax = max(len(section_descriptions.get(s, s)) for s in sections) + 2
    cmax = max(len(c) for c in sections.values()) + 60

    row = f"{'=' * dmax}  {'=' * cmax}\n"
    line = "%%-%ds  %%s\n" % dmax

    out.write(row)
    out.write(line % (" Category ", " Commands "))
    out.write(row)
    for section, commands in sorted(sections.items()):
        description = section_descriptions.get(section, section)

        for i, cmd in enumerate(sorted(commands)):
            description = description.capitalize() if i == 0 else ""
            ref = f":ref:`{cmd} <ramble-{cmd}>`"
            comma = "," if i != len(commands) - 1 else ""
            bar = "| " if i % 8 == 0 else "  "
            out.write(line % (description, bar + ref + comma))
    out.write(row)


@formatter
def rst(args, out):
    # create a parser with all commands
    parser = ramble.main.make_argument_parser(color=False)
    ramble.main.add_all_commands(parser)

    # extract cross-refs of the form `_cmd-ramble-<cmd>:` from rst files
    documented_commands = set()
    for filename in args.rst_files:
        with open(filename, encoding="utf-8") as f:
            for line in f:
                match = _CMD_HEADER_RE.match(line)
                if match:
                    documented_commands.add(match.group(1).strip())

    # print an index to each command
    rst_index(out)
    out.write("\n")

    # print sections for each command and subcommand
    writer = RambleArgparseRstWriter(parser.prog, out, args.aliases, documented_commands)
    writer.write(parser)


@formatter
def names(args, out):
    commands = copy.copy(ramble.cmd.all_commands())

    if args.aliases:
        aliases = ramble.config.get("config:aliases")
        if aliases:
            commands.extend(aliases.keys())

    colify(commands, output=out)


@formatter
def bash(args, out):
    parser = ramble.main.make_argument_parser(color=False)
    ramble.main.add_all_commands(parser)

    writer = BashCompletionWriter(parser.prog, out, args.aliases)
    writer.write(parser)


def prepend_header(args, out):
    if not args.header:
        return

    with open(args.header, encoding="utf-8") as header:
        out.write(header.read())


def _commands(parser, args):
    """This is the 'regular' command, which can be called multiple times.

    See ``commands()`` below for ``--update-completion`` handling.
    """
    formatter = formatters[args.format]

    # check header first so we don't open out files unnecessarily
    if args.header and not os.path.exists(args.header):
        logger.die(f"No such file: '{args.header}'")

    # if we're updating an existing file, only write output if a command
    # or the header is newer than the file.
    if args.update:
        logger.msg(f"Generating file: {args.update}")
        with open(args.update, "w+", encoding="utf-8") as f:
            prepend_header(args, f)
            formatter(args, f)

        if args.update_completion:
            fs.set_executable(args.update)

    else:
        prepend_header(args, sys.stdout)
        formatter(args, sys.stdout)


def update_completion(parser, args):
    """Iterate through the shells and update the standard completion files.

    This is a convenience method to avoid calling this command many
    times, and to simplify completion update for developers.

    """
    for shell_args in update_completion_args.values():
        for attr, value in shell_args.items():
            setattr(args, attr, value)
        _commands(parser, args)


def commands(parser, args):
    if args.update_completion:
        if args.format != "names" or any([args.aliases, args.update, args.header]):
            logger.die("--update-completion can only be specified alone.")

        # this runs the command multiple times with different arguments
        return update_completion(parser, args)

    else:
        # run commands normally
        return _commands(parser, args)
