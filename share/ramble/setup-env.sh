#!/bin/bash -e
# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


########################################################################
#
# This file is part of Ramble and sets up the ramble environment for bash,
# zsh, and dash (sh).  This includes environment modules and lmod support,
# and it also puts ramble in your path. The script also checks that at least
# module support exists, and provides suggestions if it doesn't. Source
# it like this:
#
#    . /path/to/ramble/share/ramble/setup-env.sh
#
########################################################################
# This is a wrapper around the ramble command that forwards calls to
# 'ramble load' and 'ramble unload' to shell functions.  This in turn
# allows them to be used to invoke environment modules functions.
#
# 'ramble load' is smarter than just 'load' because it converts its
# arguments into a unique Ramble spec that is then passed to module
# commands.  This allows the user to use packages without knowing all
# their installation details.
#
# e.g., rather than requiring a full spec for libelf, the user can type:
#
#     ramble load libelf
#
# This will first find the available libelf module file and use a
# matching one.  If there are two versions of libelf, the user would
# need to be more specific, e.g.:
#
#     ramble load libelf@0.8.13
#
# This is very similar to how regular ramble commands work and it
# avoids the need to come up with a user-friendly naming scheme for
# ramble module files.
########################################################################

# prevent infinite recursion when ramble shells out (e.g., on cray for modules)
if [ -n "${_rmb_initializing:-}" ]; then
    exit 0
fi
export _rmb_initializing=true


_ramble_shell_wrapper() {
    # Store LD_LIBRARY_PATH variables from ramble shell function
    # This is necessary because MacOS System Integrity Protection clears
    # variables that affect dyld on process start.
    for var in LD_LIBRARY_PATH DYLD_LIBRARY_PATH DYLD_FALLBACK_LIBRARY_PATH; do
        eval "if [ -n \"\${${var}-}\" ]; then export RAMBLE_$var=\${${var}}; fi"
    done

    # Zsh does not do word splitting by default, this enables it for this
    # function only
    if [ -n "${ZSH_VERSION:-}" ]; then
        emulate -L sh
    fi

    # accumulate flags meant for the main ramble command
    # the loop condition is unreadable, but it means:
    #     while $1 is set (while there are arguments)
    #       and $1 starts with '-' (and the arguments are flags)
    _rmb_flags=""
    while [ ! -z ${1+x} ] && [ "${1#-}" != "${1}" ]; do
        _rmb_flags="$_rmb_flags $1"
        shift
    done

    # h and V flags don't require further output parsing.
    if [ -n "$_rmb_flags" ] && \
       [ "${_rmb_flags#*h}" != "${_rmb_flags}" ] || \
       [ "${_rmb_flags#*V}" != "${_rmb_flags}" ];
    then
        command ramble $_rmb_flags "$@"
        return
    fi

    # set the subcommand if there is one (if $1 is set)
    _rmb_subcommand=""
    if [ ! -z ${1+x} ]; then
        _rmb_subcommand="$1"
        shift
    fi

    # Filter out use and unuse.  For any other commands, just run the
    # command.
    case $_rmb_subcommand in
        "workspace")
            _rmb_arg=""
            if [ -n "$1" ]; then
                _rmb_arg="$1"
                shift
            fi

            if [ "$_rmb_arg" = "-h" ] || [ "$_rmb_arg" = "--help" ]; then
                command ramble workspace -h
            else
                case $_rmb_arg in
                    activate)
                        # Get --sh, --csh, or -h/--help arguments.
                        # Space needed here because regexes start with a space
                        # and `-h` may be the only argument.
                        _a=" $@"
                        # Space needed here to differentiate between `-h`
                        # argument and workspaces with "-h" in the name.
                        # Also see: https://www.gnu.org/software/bash/manual/html_node/Shell-Parameter-Expansion.html#Shell-Parameter-Expansion
                        if [ -z ${1+x} ] || \
                           [ "${_a#* --sh}" != "$_a" ] || \
                           [ "${_a#* --csh}" != "$_a" ] || \
                           [ "${_a#* -h}" != "$_a" ] || \
                           [ "${_a#* --help}" != "$_a" ];
                        then
                            # No args or args contain --sh, --csh, or -h/--help: just execute.
                            command ramble workspace activate "$@"
                        else
                            # Actual call to activate: source the output.
                            _activate_cmd=$(command ramble $_rmb_flags workspace activate --sh "$@")
                            _rs=$?
                            eval "$_activate_cmd" || return $?
                            return $_rs
                        fi
                        ;;
                    deactivate)
                        # Get --sh, --csh, or -h/--help arguments.
                        # Space needed here because regexes start with a space
                        # and `-h` may be the only argument.
                        _a=" $@"
                        # Space needed here to differentiate between `--sh`
                        # argument and environments with "--sh" in the name.
                        # Also see: https://www.gnu.org/software/bash/manual/html_node/Shell-Parameter-Expansion.html#Shell-Parameter-Expansion
                        if [ "${_a#* --sh}" != "$_a" ] || \
                           [ "${_a#* --csh}" != "$_a" ];
                        then
                            # Args contain --sh or --csh: just execute.
                            command ramble workspace deactivate "$@"
                        elif [ -n "$*" ]; then
                            # Any other arguments are an error or -h/--help: just run help.
                            command ramble workspace deactivate -h
                        else
                            # No args: source the output of the command.
                            _deactivate_cmd=$(command ramble $_rmb_flags workspace deactivate --sh)
                            _rs=$?
                            eval "$_deactivate_cmd" || return $?
                            return $_rs
                        fi
                        ;;
                    create)
                        _a=" $@ "
                        # Do not invalidate cache for help flags
                        if [[ "$_a" =~ " -h " ]] || [[ "$_a" =~ " --help " ]]; then
                            command ramble $_rmb_flags workspace create "$@"
                        elif [[ "$_a" =~ " -a " ]] || [[ "$_a" =~ " --activate " ]]; then
                            # With -a, the command writes only the activation command
                            # into stdout (`ramble workspace activate <ws>`.)
                            # And the eval routes that command back to the wrapper to
                            # inject shell args, etc.
                            _create_activate_cmd="$(command ramble $_rmb_flags workspace create "$@")"
                            _rs=$?
                            if [ $_rs -eq 0 ]; then
                                unset RAMBLE_WORKSPACES
                                eval "$_create_activate_cmd" || return $?
                                _workspace="$(echo $_create_activate_cmd | awk '{print $NF}')"
                                echo "==> Created and activated workspace in $_workspace"
                            fi
                            return $_rs
                        else
                            command ramble $_rmb_flags workspace create "$@"
                            _rs=$?
                            if [ $_rs -eq 0 ]; then
                                unset RAMBLE_WORKSPACES
                            fi
                            return $_rs
                        fi
                        ;;
                    *)
                        _a=" $@ "
                        if [[ ( "$_rmb_arg" = "rm" || "$_rmb_arg" = "remove" ) ]] && \
                           [[ ! "$_a" =~ " -h " ]] && [[ ! "$_a" =~ " --help " ]];
                        then
                            command ramble $_rmb_flags workspace $_rmb_arg "$@"
                            if [ $? -eq 0 ]; then
                                unset RAMBLE_WORKSPACES
                            fi
                        else
                            command ramble $_rmb_flags workspace $_rmb_arg "$@"
                        fi
                        ;;
                esac
            fi
            return
            ;;

        *)
            command ramble $_rmb_flags $_rmb_subcommand "$@"
            ;;
    esac
}


########################################################################
# Prepends directories to path, if they exist.
#      pathadd /path/to/dir            # add to PATH
# or   pathadd OTHERPATH /path/to/dir  # add to OTHERPATH
########################################################################
_ramble_pathadd() {
    # If no variable name is supplied, just append to PATH
    # otherwise append to that variable.
    _pa_varname=PATH
    _pa_new_path="$1"
    if [ -n "$2" ]; then
        _pa_varname="$1"
        _pa_new_path="$2"
    fi

    # Do the actual prepending here.
    eval "_pa_oldvalue=\${${_pa_varname}:-}"

    _pa_canonical=":$_pa_oldvalue:"
    if [ -d "$_pa_new_path" ] && \
       [ "${_pa_canonical#${_pa_new_path}:}" = "${_pa_canonical}" ];
    then
        if [ -n "$_pa_oldvalue" ]; then
            eval "export $_pa_varname=\"$_pa_new_path:$_pa_oldvalue\""
        else
            export $_pa_varname="$_pa_new_path"
        fi
    fi
}


# Determine which shell is being used
_ramble_determine_shell() {
    if [ -f "/proc/$$/exe" ]; then
        # If procfs is present this seems a more reliable
        # way to detect the current shell
        _rmb_exe=$(readlink /proc/$$/exe)
        # Shell may contain number, like zsh5 instead of zsh
        basename ${_rmb_exe} | tr -d '0123456789'
    elif [ -n "${BASH:-}" ]; then
        echo bash
    elif [ -n "${ZSH_NAME:-}" ]; then
        echo zsh
    else
        PS_FORMAT= ps -p $$ | tail -n 1 | awk '{print $4}' | sed 's/^-//' | xargs basename
    fi
}
_rmb_shell=$(_ramble_determine_shell)


#
# Figure out where this file is.
#
if [ "$_rmb_shell" = bash ]; then
    _rmb_source_file="${BASH_SOURCE[0]:-}"
elif [ "$_rmb_shell" = zsh ]; then
    _rmb_source_file="${(%):-%N}"
else
    # Try to read the /proc filesystem (works on linux without lsof)
    # In dash, the sourced file is the last one opened (and it's kept open)
    _rmb_source_file_fd="$(\ls /proc/$$/fd 2>/dev/null | sort -n | tail -1)"
    if ! _rmb_source_file="$(readlink /proc/$$/fd/$_rmb_source_file_fd)"; then
        # Last resort: try lsof. This works in dash on macos -- same reason.
        # macos has lsof installed by default; some linux containers don't.
        _rmb_lsof_output="$(lsof -p $$ -Fn0 | tail -1)"
        _rmb_source_file="${_rmb_lsof_output#*n}"
    fi

    # If we can't find this script's path after all that, bail out with
    # plain old $0, which WILL NOT work if this is sourced indirectly.
    if [ ! -f "$_rmb_source_file" ]; then
        _rmb_source_file="$0"
    fi
fi

#
# Find root directory and add bin to path.
#
# We send cd output to /dev/null to avoid because a lot of users set up
# their shell so that cd prints things out to the tty.
_rmb_share_dir="$(cd "$(dirname $_rmb_source_file)" > /dev/null && pwd)"
_rmb_prefix="$(cd "$(dirname $(dirname $_rmb_share_dir))" > /dev/null && pwd)"
if [ -x "$_rmb_prefix/bin/ramble" ]; then
    export RAMBLE_ROOT="${_rmb_prefix}"
else
    # If the shell couldn't find the sourced script, fall back to
    # whatever the user set RAMBLE_ROOT to.
    if [ -n "$RAMBLE_ROOT" ]; then
        _rmb_prefix="$RAMBLE_ROOT"
        _rmb_share_dir="$_rmb_prefix/share/ramble"
    fi

    # If RAMBLE_ROOT didn't work, fail.  We should need this rarely, as
    # the tricks above for finding the sourced file are pretty robust.
    if [ ! -x "$_rmb_prefix/bin/ramble" ]; then
        echo "==> Error: RAMBLE_ROOT must point to ramble's prefix when using $_rmb_shell"
        echo "Run this with the correct prefix before sourcing setup-env.sh:"
        echo "    export RAMBLE_ROOT=</path/to/ramble>"
        return 1
    fi
fi
_ramble_pathadd PATH "${_rmb_prefix%/}/bin"

#
# Check whether a function of the given name is defined
#
_ramble_fn_exists() {
	LANG= type $1 2>&1 | grep -q 'function'
}

need_module="no"
if ! _ramble_fn_exists use && ! _ramble_fn_exists module; then
	need_module="yes"
fi;

# Define the ramble shell function with some informative no-ops, so when users
# run `which ramble`, they see the path to ramble and where the function is from.
eval "ramble() {
    : this is a shell function from: $_rmb_share_dir/setup-env.sh
    : the real ramble script is here: $_rmb_prefix/bin/ramble
    _ramble_shell_wrapper \"\$@\"
    return \$?
}"

# Export ramble function so it is available in subshells (only works with bash)
if [ "$_rmb_shell" = bash ]; then
    export -f ramble
    export -f _ramble_shell_wrapper
fi

# Identify and lock the python interpreter
if [ -n "${RAMBLE_PYTHON:-}" ]; then
  echo "The RAMBLE_PYTHON environment variable is set to $RAMBLE_PYTHON"
  echo "Will pin the python binary ramble uses to this value".
  if [ -n "${_RAMBLE_PYTHON:-}" ]; then
    if [ "$RAMBLE_PYTHON" != "$_RAMBLE_PYTHON" ]; then
      echo "WARNING: Ramble was previously pinned to use $_RAMBLE_PYTHON"
      echo "         If this is not what you want, set the correct python"
      echo "         in RAMBLE_PYTHON and re-source this file"
    fi
  fi
fi

for cmd in "${RAMBLE_PYTHON:-}" python3 python; do
    if command -v > /dev/null "$cmd"; then
        export _RAMBLE_PYTHON="$(command -v "$cmd")"
        break
    fi
done

# Add programmable tab completion for Bash
#
# The completion script is written for Bash, but it bootstraps zsh's
# bash-completion compatibility layer (bashcompinit) when sourced from zsh.
if test "$_rmb_shell" = bash || test -n "${ZSH_VERSION:-}"; then
    source $_rmb_share_dir/ramble-completion.bash
    # The custom version includes support for command aliases, it is
    # generated via `ramble commands --update-completion`.
    if [ -f "$_rmb_share_dir/custom-ramble-completion.bash" ]; then
        if [ ! "$_rmb_share_dir/ramble-completion.bash" -nt "$_rmb_share_dir/custom-ramble-completion.bash" ]; then
            source $_rmb_share_dir/custom-ramble-completion.bash
        fi
    fi
fi

# done: unset sentinel variable as we're no longer initializing
unset _rmb_initializing
export _rmb_initializing
