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

# accumulate initial flags for main ramble command while preserving original word list
set _rmb_orig_args = ( $_rmb_args:q )
set _rmb_flags = ""
set _rmb_short_circuit = 0
while ( $#_rmb_args > 0 )
    if ( "$_rmb_args[1]" !~ "-*" ) break
    set _rmb_cur_flag = "$_rmb_args[1]"
    set _rmb_flags = "$_rmb_flags $_rmb_cur_flag"
    if ( "$_rmb_cur_flag" == "-h" || "$_rmb_cur_flag" == "--help" || \
         "$_rmb_cur_flag" == "-H" || "$_rmb_cur_flag" == "--all-help" || \
         "$_rmb_cur_flag" == "-V" || "$_rmb_cur_flag" == "--version" || \
         "$_rmb_cur_flag" =~ -h* || "$_rmb_cur_flag" =~ -H* || "$_rmb_cur_flag" =~ -V* ) then
        set _rmb_short_circuit = 1
    else if ( "$_rmb_cur_flag" !~ --* && "$_rmb_cur_flag" !~ -*[wDcC]* && \
              ( "$_rmb_cur_flag" =~ *h* || "$_rmb_cur_flag" =~ *H* || "$_rmb_cur_flag" =~ *V* ) ) then
        set _rmb_short_circuit = 1
    endif
    shift _rmb_args
    if ( "$_rmb_cur_flag" == "-w" || "$_rmb_cur_flag" == "--workspace" || \
         "$_rmb_cur_flag" == "-D" || "$_rmb_cur_flag" == "--workspace-dir" || \
         "$_rmb_cur_flag" == "-c" || "$_rmb_cur_flag" == "--config" || \
         "$_rmb_cur_flag" == "-C" || "$_rmb_cur_flag" == "--config-scope" || \
         "$_rmb_cur_flag" == "--color" || "$_rmb_cur_flag" == "--sorted-profile" || \
         "$_rmb_cur_flag" == "--lines" || "$_rmb_cur_flag" == "--profile-restrictions" ) then
        if ( $#_rmb_args > 0 ) then
            set _rmb_flags = "$_rmb_flags $_rmb_args[1]"
            shift _rmb_args
        endif
    endif
    unset _rmb_cur_flag
end

# h, H, and V flags don't require further output parsing.
if ( $_rmb_short_circuit == 1 ) then
    \ramble $_rmb_orig_args:q
    set _rmb_rs = $status
    goto _rmb_end
endif

# Set up args -- we want a subcommand and a spec.
set _rmb_subcommand=""
set _rmb_spec=""
if ($#_rmb_args > 0) then
    set _rmb_subcommand = ($_rmb_args[1])
endif
if ($#_rmb_args > 1) then
    set _rmb_spec = ($_rmb_args[2-])
endif

# Run subcommand
switch ($_rmb_subcommand)
case workspace:
    shift _rmb_args  # get rid of 'env'

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
                # argument and environments with "-h" in the name.
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
                # argument and environments with "--sh" in the name.
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

case cd:
    shift _rmb_args  # get rid of 'cd'
    set _rmb_cd_help = 0
    foreach _rmb_cd_arg ( $_rmb_args:q )
        if ( "$_rmb_cd_arg" == "--" ) break
        if ( "$_rmb_cd_arg" == "-h" || "$_rmb_cd_arg" == "--help" || "$_rmb_cd_arg" =~ -h* ) then
            set _rmb_cd_help = 1
            break
        endif
        if ( "$_rmb_cd_arg" =~ -[esrmW]*h* && "$_rmb_cd_arg" !~ -*[wDi]*h* ) then
            set _rmb_cd_help = 1
            break
        endif
    end
    if ( $_rmb_cd_help == 1 ) then
        \ramble $_rmb_orig_args:q
        set _rmb_rs = $status
    else
        set noglob
        set _cd_dir = `env _RAMBLE_CD_WRAPPER=1 ramble $_rmb_orig_args:q`
        set _rmb_rs = $status
        unset noglob
        if ( $_rmb_rs == 0 && "$_cd_dir" != "" ) then
            cd "$_cd_dir"
            set _rmb_rs = $status
        endif
        unset _cd_dir
    endif
    unset _rmb_cd_help _rmb_cd_arg
    breaksw

default:
    \ramble $_rmb_orig_args:q
    set _rmb_rs = $status
    breaksw
endsw

_rmb_end:
unset _rmb_args _rmb_orig_args _rmb_short_circuit _rmb_full_spec _rmb_sh_cmd _rmb_spec _rmb_subcommand _rmb_flags
unset _rmb_arg _rmb_env_arg

# The `endif` may swallow the subshell's exit status, so doing the eval at the very end.
if ( $?_rmb_rs ) then
    set _rmb_rs_eval="unset _rmb_rs _rmb_rs_eval; (exit $_rmb_rs)"
else
    set _rmb_rs_eval="unset _rmb_rs_eval; (exit 0)"
endif
eval "$_rmb_rs_eval"
