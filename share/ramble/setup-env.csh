# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

#
# This file is part of Ramble and sets up the ramble environment for
# csh and tcsh. It adds ramble to your PATH and defines a shell alias
# so that workspace activation commands update the current shell.
# Source it like this:
#
#    source /path/to/ramble/share/ramble/setup-env.csh
#

# prevent infinite recursion when ramble shells out
if ($?_rmb_initializing) then
    exit 0
endif
setenv _rmb_initializing true

# If RAMBLE_ROOT is not set, we'll try to find it ourselves.
# csh/tcsh don't have a built-in way to do this, but both keep files
# they are sourcing open. We use /proc on linux and lsof on macs to
# find this script's full path in the current process's open files.
if (! $?RAMBLE_ROOT) then
    # figure out a command to list open files
    if (-d /proc/$$/fd) then
        set _rmb_lsof = "ls -l /proc/$$/fd"
    else
        which lsof > /dev/null
        if ($? == 0) then
            set _rmb_lsof = "lsof -p $$"
        endif
    endif

    # filter this script out of list of open files
    if ( $?_rmb_lsof ) then
        set _rmb_source_file = `$_rmb_lsof | sed -e 's/^[^/]*//' | grep "/setup-env.csh"`
    endif

    # This script is in $RAMBLE_ROOT/share/ramble; get the root with dirname
    if ($?_rmb_source_file) then
        set _rmb_share_ramble = `dirname "$_rmb_source_file"`
        set _rmb_share = `dirname "$_rmb_share_ramble"`
        setenv RAMBLE_ROOT `dirname "$_rmb_share"`
    endif

    if (! $?RAMBLE_ROOT) then
        echo "==> Error: setup-env.csh couldn't figure out where ramble lives."
        echo "    Set RAMBLE_ROOT to the root of your ramble installation and try again."
        exit 1
    endif
endif

# Command aliases point at separate source files
set _ramble_source_file = $RAMBLE_ROOT/share/ramble/setup-env.csh
set _ramble_share_dir = $RAMBLE_ROOT/share/ramble
alias ramble          'set _rmb_args = (\!*); source $_ramble_share_dir/csh/ramble.csh'
alias _ramble_pathadd 'set _pa_args = (\!*) && source $_ramble_share_dir/csh/pathadd.csh'

# Identify and lock the python interpreter
if ($?RAMBLE_PYTHON) then
    echo "The RAMBLE_PYTHON environment variable is set to $RAMBLE_PYTHON"
    echo "Will pin the python binary ramble uses to this value".
endif

if (! $?RAMBLE_PYTHON) then
    setenv RAMBLE_PYTHON ""
endif

if ($?_RAMBLE_PYTHON && "$RAMBLE_PYTHON" != "$_RAMBLE_PYTHON") then
    echo "WARNING: Ramble was previously pinned to use $_RAMBLE_PYTHON"
    echo "         If this is not what you want, set the correct python"
    echo "         in RAMBLE_PYTHON and re-source this file"
endif

foreach cmd ("$RAMBLE_PYTHON" python3 python)
    command -v "$cmd" >& /dev/null
    if ($status == 0) then
        setenv _RAMBLE_PYTHON `command -v "$cmd"`
        break
    endif
end

# Set variables needed by this script
_ramble_pathadd PATH "$RAMBLE_ROOT/bin"

# done: unset sentinel variable as we're no longer initializing
unsetenv _rmb_initializing
