# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import os
import re
from typing import List, Optional

from llnl.util.lang import attr_setdefault

import ramble.error
import ramble.paths
import ramble.workspace
from ramble.error import RambleCommandError
from ramble.util.logger import logger

import spack.extensions

# cmd has a submodule called "list" so preserve the python list module
python_list = list

# Patterns to ignore in the commands directory when looking for commands.
ignore_files = r"^\.|^__init__.py$|^#"

SETUP_PARSER = "setup_parser"
DESCRIPTION = "description"


def python_name(cmd_name):
    """Convert ``-`` to ``_`` in command name, to make a valid identifier."""
    return cmd_name.replace("-", "_")


def cmd_name(python_name):
    """Convert module name (with ``_``) to command name (with ``-``)."""
    return python_name.replace("_", "-")


def require_cmd_name(cname):
    """Require that the provided name is a valid command name (per
    cmd_name()). Useful for checking parameters for function
    prerequisites.
    """
    if cmd_name(cname) != cname:
        raise CommandNameError(cname)


#: global, cached list of all commands -- access through all_commands()
_all_commands: Optional[List[str]] = None


def all_commands():
    """Get a sorted list of all ramble commands.

    This will list the lib/ramble/ramble/cmd directory and find the
    commands there to construct the list.  It does not actually import
    the python files -- just gets the names.
    """
    global _all_commands
    if _all_commands is None:
        _all_commands = []
        command_paths = [ramble.paths.command_path]  # Built-in commands
        for path in command_paths:
            for file in os.listdir(path):
                if file.endswith(".py") and not re.search(ignore_files, file):
                    cmd = re.sub(r".py$", "", file)
                    _all_commands.append(cmd_name(cmd))

        _all_commands.sort()

    return _all_commands


def get_module(cmd_name):
    """Imports the module for a particular command name and returns it.

    Args:
        cmd_name (str): name of the command for which to get a module
            (contains ``-``, not ``_``).
    """
    require_cmd_name(cmd_name)
    pname = python_name(cmd_name)

    logger.debug(f"Getting module for command {cmd_name}")

    try:
        # Try to import the command from the built-in directory
        module_name = f"{__name__}.{pname}"
        module = __import__(module_name, fromlist=[pname, SETUP_PARSER, DESCRIPTION], level=0)
        logger.debug(f"Imported {pname} from built-in commands")
    except ImportError as e:
        if getattr(e, "name", None) != module_name:
            raise
        try:
            module = spack.extensions.get_module(cmd_name)
        except (AttributeError, spack.extensions.CommandNotFoundError):
            raise RambleCommandError(f"Command {cmd_name} does not exist.") from None

    attr_setdefault(module, SETUP_PARSER, lambda *args: None)  # null-op
    attr_setdefault(module, DESCRIPTION, "")

    if not hasattr(module, pname):
        logger.die(
            f"Command module {module.__name__} ({module.__file__}) must define function '{pname}'."
        )

    return module


def get_command(cmd_name):
    """Imports the command function associated with cmd_name.

    The function's name is derived from cmd_name using python_name().

    Args:
        cmd_name (str): name of the command (contains ``-``, not ``_``).
    """
    require_cmd_name(cmd_name)
    pname = python_name(cmd_name)
    return getattr(get_module(cmd_name), pname)


class CommandNameError(ramble.error.RambleError):
    """Exception class thrown for impermissible command names"""

    def __init__(self, name):
        self.name = name
        super().__init__(f"{name} is not a permissible Ramble command name.")


def require_active_workspace(cmd_name, dry_run: bool = False):
    """Used by commands to get the active workspace

    If a workspace is not found, print an error message that says the calling
    command *needs* an active workspace.

    Arguments:
        cmd_name (str): name of calling command
        dry_run (bool): whether this is a dry run

    Returns:
        (ramble.workspace.Workspace): the active workspace
    """
    ws = ramble.workspace.active_workspace()

    if ws:
        if dry_run:
            ws.dry_run = True
        return ws
    else:
        logger.die(
            f"`ramble {cmd_name}` requires a workspace",
            "activate a workspace first:",
            "    ramble workspace activate WRKSPC",
            "or use:",
            f"    ramble -w WRKSPC {cmd_name} ...",
        )


def find_workspace(args):
    """Find active workspace from args or environment variable.

    Check for a workspace in this order:
        1. via ``ramble -w WRKSPC`` or ``ramble -D DIR`` (arguments)
        2. via a path in the ramble.workspace.RAMBLE_WORKSPACE_VAR environment variable.

    If a workspace is found, read it in.  If not, return None.

    Arguments:
        args (argparse.Namespace): argparse namespace with command arguments

    Returns:
        (ramble.workspace.Workspace): a found workspace, or ``None``
    """

    # treat workspace as a name
    ws = args.workspace
    if ws:
        if ramble.workspace.exists(ws):
            return ramble.workspace.read(ws)

    else:
        # if workspace was specified, see if it is a directory otherwise, look
        # at workspace_dir (workspace and workspace_dir are mutually exclusive)
        ws = args.workspace_dir

        # if no argument, look for the environment variable
        if not ws:
            ws = os.environ.get(ramble.workspace.RAMBLE_WORKSPACE_VAR)

            # nothing was set; there's no active environment
            if not ws:
                return None
            elif not ramble.workspace.is_workspace_dir(ws):
                env_var = ramble.workspace.RAMBLE_WORKSPACE_VAR
                raise ramble.workspace.RambleActiveWorkspaceError(
                    f"The environment variable {env_var} refers to an invalid ramble workspace."
                )

    # if we get here, ws isn't the name of a ramble workspace; it has
    # to be a path to a workspace, or there is something wrong.
    if ramble.workspace.is_workspace_dir(ws):
        return ramble.workspace.Workspace(ws)

    raise ramble.workspace.RambleWorkspaceError(f"No workspace in {ws}")


def find_workspace_path(args):
    """Find path to active workspace from args or environment variable.

    Check for a workspace in this order:
        1. via ``ramble -w WRKSPC`` or ``ramble -D DIR`` (arguments)
        2. via a path in the ramble.workspace.RAMBLE_WORKSPACE_VAR environment variable.

    If a workspace is found, return it's path.  If not, return None.

    Arguments:
        args (argparse.Namespace): argparse namespace with command arguments

    Returns:
        (str): Path to workspace root, or None
    """

    # treat workspace as a name
    ws = args.workspace
    if ws:
        if ramble.workspace.exists(ws):
            return ramble.workspace.root(ws)

    else:
        # if workspace was specified, see if it is a directory otherwise, look
        # at workspace_dir (workspace and workspace_dir are mutually exclusive)
        ws = args.workspace_dir

        # if no argument, look for the environment variable
        if not ws:
            ws = os.environ.get(ramble.workspace.RAMBLE_WORKSPACE_VAR)

            # nothing was set; there's no active environment
            if not ws:
                return None

    # if we get here, ws isn't the name of a ramble workspace; it has
    # to be a path to a workspace, or there is something wrong.
    if ramble.workspace.is_workspace_dir(ws):
        return ws

    raise ramble.workspace.RambleWorkspaceError(f"no workspace in {ws}")
