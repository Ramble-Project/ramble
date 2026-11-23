# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import sys

from ramble.util.colors import colorize

description = "get help on ramble and its commands"
section = "help"
level = "short"

#
# These are longer guides on particular aspects of Ramble. Currently there
# is only one on spec syntax.
#
spec_guide = """\
spec expression syntax:

  [namespace.][type.]name[@version]

  name                              any object from 'ramble list'
  namespace                         repository namespace (e.g., builtin)
  type                              object type or abbreviation
                                    (e.g., app, mod, pkg_man, wm, sys, plat, utility)
  @version                          optional version suffix (e.g., gromacs@2024)

  examples:
      @B{hostname}                      the hostname application
      @B{builtin.hostname}              hostname from the builtin repository
      @B{builtin.app.hostname}          hostname application from builtin
      @B{mod.perf}                      the perf modifier
      @B{builtin.wm.slurm}              the slurm workflow manager from builtin
"""


guides = {
    "spec": spec_guide,
}


def setup_parser(subparser):
    help_cmd_group = subparser.add_mutually_exclusive_group()
    help_cmd_group.add_argument(
        "help_command", nargs="?", default=None, help="command to get help on"
    )

    help_all_group = subparser.add_mutually_exclusive_group()
    help_all_group.add_argument(
        "-a",
        "--all",
        action="store_const",
        const="long",
        default="short",
        help="list all available commands and options",
    )

    help_spec_group = subparser.add_mutually_exclusive_group()
    help_spec_group.add_argument(
        "--spec",
        action="store_const",
        dest="guide",
        const="spec",
        default=None,
        help="help on the object specification syntax",
    )


def help(parser, args):
    if args.guide:
        print(colorize(guides[args.guide]))
        return 0

    if args.help_command:
        parser.add_command(args.help_command)
        parser.parse_args([args.help_command, "-h"])
    else:
        sys.stdout.write(parser.format_help(level=args.all))
        return 0
