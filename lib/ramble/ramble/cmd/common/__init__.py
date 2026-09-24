# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import ramble.paths
import ramble.util.colors as color
from ramble.cmd.common.arguments import (
    sanitize_arg_name,
    setup_subcommands_from_prefix,
)
from ramble.util.logger import logger

__all__ = [
    "shell_init_instructions",
    "sanitize_arg_name",
    "setup_subcommands_from_prefix",
]


def shell_init_instructions(cmd, equivalent):
    """Print out instructions for users to initialize shell support.

    Arguments:
        cmd (str): the command the user tried to run that requires
            shell support in order to work
        equivalent (str): a command they can run instead, without
            enabling shell support
    """

    shell_specific = "{sh_arg}" in equivalent

    msg = [
        f"`{cmd}` requires ramble's shell support.",
        "",
        "To set up shell support, run the command below for your shell.",
        "",
        color.colorize("@*c{For bash/zsh/sh:}"),
        f"  . {ramble.paths.share_path}/setup-env.sh",
        "",
        color.colorize("@*c{For csh/tcsh:}"),
        f"  source {ramble.paths.share_path}/setup-env.csh",
        "",
        "Or, if you do not want to use shell support, run "
        + ("one of these" if shell_specific else "this")
        + " instead:",
        "",
    ]

    if shell_specific:
        msg += [
            equivalent.format(sh_arg="--sh  ") + "  # bash/zsh/sh",
            equivalent.format(sh_arg="--csh ") + "  # csh/tcsh",
        ]
    else:
        msg += ["  " + equivalent]

    msg += [""]
    logger.error(*msg)
