# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

# Store LD_LIBRARY_PATH variables from ramble shell function
# This is necessary because MacOS System Integrity Protection clears
# variables that affect dyld on process start.
if ( ${?LD_LIBRARY_PATH} ) then
    setenv RAMBLE_LD_LIBRARY_PATH $LD_LIBRARY_PATH
endif
if ( ${?DYLD_LIBRARY_PATH} ) then
    setenv RAMBLE_DYLD_LIBRARY_PATH $DYLD_LIBRARY_PATH
endif
if ( ${?DYLD_FALLBACK_LIBRARY_PATH} ) then
    setenv RAMBLE_DYLD_FALLBACK_LIBRARY_PATH $DYLD_FALLBACK_LIBRARY_PATH
endif

# accumulate initial flags for main ramble command
set _rmb_flags = ""
while ( $#_rmb_args > 0 )
    if ( "$_rmb_args[1]" !~ "-*" ) break
    set _rmb_flags = "$_rmb_flags $_rmb_args[1]"
    shift _rmb_args
end

# h and V flags don't require further output parsing.
if ( "$_rmb_flags" =~ *h* || "$_rmb_flags" =~ *V* ) then
    \ramble $_rmb_flags $_rmb_args:q
    set _rmb_rs = $status
    goto _rmb_end
endif

# Set up args -- extract the subcommand.
set _rmb_subcommand=""
if ($#_rmb_args > 0) then
    set _rmb_subcommand = ($_rmb_args[1])
endif

# Run subcommand
switch ($_rmb_subcommand)
case workspace:
    shift _rmb_args  # get rid of 'workspace'

    set _rmb_arg=""
    if ($#_rmb_args > 0) then
        set _rmb_arg = ($_rmb_args[1])
    endif

    if ( "$_rmb_arg" == "-h" || "$_rmb_arg" == "--help" ) then
        \ramble workspace -h
    else
        switch ($_rmb_arg)
            case activate:
                set _rmb_env_arg=""
                if ($#_rmb_args > 1) then
                    set _rmb_env_arg = ($_rmb_args[2])
                endif

                # Space needed here to differentiate between `-h`
                # argument and workspaces with "-h" in the name.
                if ( "$_rmb_env_arg" == "" || \
                     "$_rmb_args" =~ "* --sh*" || \
                     "$_rmb_args" =~ "* --csh*" || \
                     "$_rmb_args" =~ "* -h*" || \
                     "$_rmb_args" =~ "* --help*" ) then
                    # No args or args contain --sh, --csh, or -h/--help: just execute.
                    \ramble $_rmb_flags workspace $_rmb_args:q
                    set _rmb_rs = $status
                else
                    shift _rmb_args  # consume 'activate' or 'deactivate'
                    # Actual call to activate: source the output.
                    set _activate_cmd = `\ramble $_rmb_flags workspace activate --csh $_rmb_args:q`
                    set _rmb_rs = $status
                    eval "$_activate_cmd"
                endif
                breaksw
            case deactivate:
                set _rmb_env_arg=""
                if ($#_rmb_args > 1) then
                    set _rmb_env_arg = ($_rmb_args[2])
                endif

                # Space needed here to differentiate between `--sh`
                # argument and workspaces with "--sh" in the name.
                if ( "$_rmb_args" =~ "* --sh*" || \
                     "$_rmb_args" =~ "* --csh*" ) then
                    # Args contain --sh or --csh: just execute.
                    \ramble $_rmb_flags workspace $_rmb_args:q
                    set _rmb_rs = $status
                else if ( "$_rmb_env_arg" != "" ) then
                    # Any other arguments are an error or -h/--help: just run help.
                    \ramble $_rmb_flags workspace deactivate -h
                    set _rmb_rs = $status
                else
                    # No args: source the output of the command.
                    set _deactivate_cmd = `\ramble $_rmb_flags workspace deactivate --csh`
                    set _rmb_rs = $status
                    eval "$_deactivate_cmd"
                endif
                breaksw
            case create:
                if ( "$_rmb_args" =~ *" -a"* || \
                     "$_rmb_args" =~ *" --activate"* ) then
                    # Args contain activate flag
                    set _create_activate_cmd = `\ramble $_rmb_flags workspace $_rmb_args:q`
                    set _rmb_rs = $status
                    if ( $_rmb_rs == 0 ) then
                        eval "$_create_activate_cmd"
                        set _ws = `echo "$_create_activate_cmd" | awk '{print $NF}'`
                        echo "==> Created and activated workspace in $_ws"
                    endif
                else
                    \ramble $_rmb_flags workspace $_rmb_args:q
                    set _rmb_rs = $status
                endif
                breaksw
            default:
                \ramble $_rmb_flags workspace $_rmb_args:q
                set _rmb_rs = $status
                breaksw
        endsw
    endif
    breaksw

default:
    \ramble $_rmb_flags $_rmb_args:q
    set _rmb_rs = $status
    breaksw
endsw

_rmb_end:
unset _rmb_args _rmb_subcommand _rmb_flags
unset _rmb_arg _rmb_env_arg

# The `endif` may swallow the subshell's exit status, so doing the eval at the very end.
if ( $?_rmb_rs ) then
    set _rmb_rs_eval="unset _rmb_rs _rmb_rs_eval; (exit $_rmb_rs)"
else
    set _rmb_rs_eval="unset _rmb_rs_eval; (exit 0)"
endif
eval "$_rmb_rs_eval"
