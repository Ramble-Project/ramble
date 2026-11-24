# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
import os

import ramble.workspace
from ramble.util.colors import colorize

from spack.util.environment import EnvironmentModifications


def activate_header(ws, shell, prompt=None, filter_group=None, invalidate_workspace_cache=False):
    # Construct the commands to run
    cmds = ""
    if shell == "csh":
        # TODO: figure out how to make color work for csh
        cmds += f"setenv {ramble.workspace.RAMBLE_WORKSPACE_VAR} {ws.root};\n"
        if filter_group:
            cmds += f"setenv RAMBLE_ACTIVE_FILTER_GROUP {filter_group};\n"
        if prompt:
            cmds += "if (! $?RAMBLE_OLD_PROMPT ) "
            cmds += 'setenv RAMBLE_OLD_PROMPT "${prompt}";\n'
            cmds += 'set prompt="%s ${prompt}";\n' % prompt
    elif shell == "fish":
        if "color" in os.getenv("TERM", "") and prompt:
            prompt = colorize("@G{%s} " % prompt, color=True)

        cmds += f"set -gx {ramble.workspace.RAMBLE_WORKSPACE_VAR} {ws.root};\n"
        if filter_group:
            cmds += f"set -gx RAMBLE_ACTIVE_FILTER_GROUP {filter_group};\n"
        #
        # NOTE: We're not changing the fish_prompt function (which is fish's
        # solution to the PS1 variable) here. This is a bit fiddly, and easy to
        # screw up => spend time reasearching a solution. Feedback welcome.
        #
    elif shell == "bat":
        # TODO: Color
        cmds += f'set "{ramble.workspace.RAMBLE_WORKSPACE_VAR}={ws.root}"\n'
        if filter_group:
            cmds += f'set "RAMBLE_ACTIVE_FILTER_GROUP={filter_group}"\n'
        # TODO: prompt
    else:
        if "color" in os.getenv("TERM", "") and prompt:
            prompt = colorize("@G{%s}" % prompt, color=True)

        cmds += f"export {ramble.workspace.RAMBLE_WORKSPACE_VAR}={ws.root};\n"
        if filter_group:
            cmds += f"export RAMBLE_ACTIVE_FILTER_GROUP={filter_group};\n"
        if invalidate_workspace_cache:
            cmds += "unset RAMBLE_WORKSPACES;\n"
        if prompt:
            cmds += "if [ -z ${RAMBLE_OLD_PS1+x} ]; then\n"
            cmds += "    if [ -z ${PS1+x} ]; then\n"
            cmds += "        PS1='$$$$';\n"
            cmds += "    fi;\n"
            cmds += '    export RAMBLE_OLD_PS1="${PS1}";\n'
            cmds += "fi;\n"
            cmds += 'export PS1="%s ${PS1}";\n' % prompt

    return cmds


def deactivate_header(shell):
    cmds = ""
    if shell == "csh":
        cmds += f"unsetenv {ramble.workspace.RAMBLE_WORKSPACE_VAR};\n"
        cmds += "if ( $?RAMBLE_ACTIVE_FILTER_GROUP ) unsetenv RAMBLE_ACTIVE_FILTER_GROUP;\n"
        cmds += "if ( $?RAMBLE_OLD_PROMPT ) "
        cmds += '    eval \'set prompt="$RAMBLE_OLD_PROMPT" &&'
        cmds += "        unsetenv RAMBLE_OLD_PROMPT';\n"
    elif shell == "fish":
        cmds += f"set -e {ramble.workspace.RAMBLE_WORKSPACE_VAR};\n"
        cmds += "if set -q RAMBLE_ACTIVE_FILTER_GROUP; set -e RAMBLE_ACTIVE_FILTER_GROUP; end;\n"
        #
        # NOTE: Not changing fish_prompt (above) => no need to restore it here.
        #
    elif shell == "bat":
        # TODO: Color
        cmds += f'set "{ramble.workspace.RAMBLE_WORKSPACE_VAR}="\n'
        cmds += 'set "RAMBLE_ACTIVE_FILTER_GROUP="\n'
        # TODO: prompt
    else:
        cmds += "if [ ! -z ${%s+x} ]; then\n" % (ramble.workspace.RAMBLE_WORKSPACE_VAR)
        cmds += "unset {}; export {};\n".format(
            ramble.workspace.RAMBLE_WORKSPACE_VAR,
            ramble.workspace.RAMBLE_WORKSPACE_VAR,
        )
        cmds += "fi;\n"
        cmds += "if [ ! -z ${RAMBLE_ACTIVE_FILTER_GROUP+x} ]; then\n"
        cmds += "    unset RAMBLE_ACTIVE_FILTER_GROUP; export RAMBLE_ACTIVE_FILTER_GROUP;\n"
        cmds += "fi;\n"
        cmds += "if [ ! -z ${RAMBLE_OLD_PS1+x} ]; then\n"
        cmds += "    if [ \"$RAMBLE_OLD_PS1\" = '$$$$' ]; then\n"
        cmds += "        unset PS1; export PS1;\n"
        cmds += "    else\n"
        cmds += '        export PS1="$RAMBLE_OLD_PS1";\n'
        cmds += "    fi;\n"
        cmds += "    unset RAMBLE_OLD_PS1; export RAMBLE_OLD_PS1;\n"
        cmds += "fi;\n"

    return cmds


def activate(ws):
    """
    Activate a workspace and return environment modifications.

    To activate a workspace, we add its configuration scope to the
    existing Ramble configuration, and set it as the active workspace.

    Arguments:
        ws (ramble.workspace.Workspace): the workspace to activate

    Returns:
        spack.util.environment.EnvironmentModifications: Environment variable
        modifications to activate the workspace.
    """
    ramble.workspace.activate(ws)

    env_mods = EnvironmentModifications()

    #
    # NOTE in the fish-shell: Path variables are a special kind of variable
    # used to support colon-delimited path lists including PATH, CDPATH,
    # MANPATH, PYTHONPATH, etc. All variables that end in PATH (case-sensitive)
    # become PATH variables.
    #

    return env_mods


def deactivate():
    """
    Deactivate the currently active workspace and return environment modifications.

    Returns:
        spack.util.environment.EnvironmentModifications: Environment variable
        modifications to deactivate the workspace.
    """
    env_mods = EnvironmentModifications()
    active = ramble.workspace.active_workspace()

    if active is None:
        return env_mods

    ramble.workspace.deactivate()

    return env_mods
