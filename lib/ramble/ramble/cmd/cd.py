# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import ramble.cmd.common
import ramble.cmd.location

description = "cd to ramble directories, workspaces, or experiments in the shell"
section = "workspaces"
level = "short"

_CD_WRAPPER_ENV = "_RAMBLE_CD_WRAPPER"


def setup_parser(subparser):
    """Set up argument parser for ``ramble cd`` (identical to ``ramble location``)."""
    ramble.cmd.location.setup_parser(subparser)


def cd(parser, args):
    if not os.environ.get(_CD_WRAPPER_ENV):
        ramble.cmd.common.shell_init_instructions(
            "ramble cd",
            "    cd `ramble location --first --existing ...`",
        )
        return 1

    return ramble.cmd.location.run_location(
        args,
        limit_one=True,
        existing=True,
        warn_implicit_first=not bool(args.limit_one or args.first_failed),
    )
