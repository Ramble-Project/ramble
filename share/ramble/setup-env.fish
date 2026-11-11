# Copyright 2013-2019 Lawrence Livermore National Security, LLC and other
# Spack Project Developers. See the top-level COPYRIGHT file for details.
#
# SPDX-License-Identifier: (Apache-2.0 OR MIT)


#################################################################################
#
# This file is part of Ramble and sets up the ramble environment for the friendly
# interactive shell (fish). This includes module support, and it also puts ramble
# in your path. The script also checks that at least module support exists, and
# provides suggestions if it doesn't. Source it like this:
#
#    source /path/to/ramble/share/ramble/setup-env.fish
#
#################################################################################
# This is a wrapper around the ramble command that forwards calls to 'ramble load'
# and 'ramble unload' to shell functions. This in turn allows them to be used to
# invoke environment modules functions.
#
# 'ramble load' is smarter than just 'load' because it converts its arguments into
# a unique ramble spec that is then passed to module commands. This allows the
# user to load packages without knowing all their installation details.
#
# e.g., rather than requiring a full spec for libelf, the user can type:
#
#     ramble load libelf
#
# This will first find the available libelf modules and load a matching one. If
# there are two versions of libelf, the user would need to be more specific,
# e.g.:
#
#     ramble load libelf@0.8.13
#
# This is very similar to how regular ramble commands work and it avoids the need
# to come up with a user-friendly naming scheme for ramble dotfiles.
#################################################################################

# prevent infinite recursion when ramble shells out (e.g., on cray for modules)
if test -n "$_rmb_initializing"
    exit 0
end
set -x _rmb_initializing true


#
# Test for STDERR-NOCARET feature: if this is off, fish will redirect stderr to
# a file named in the string after `^`
#


if status test-feature stderr-nocaret
else
    echo "WARNING: you have not enabled the 'stderr-nocaret' feature."
    echo "This means that you have to escape the caret (^) character when defining specs."
    echo "Consider enabling stderr-nocaret: https://fishshell.com/docs/current/index.html#featureflags"
end



#
# RAMBLE wrapper function, preprocessing arguments and flags.
#


function ramble -d "wrapper for the `ramble` command"


#
# DEFINE SUPPORT FUNCTIONS HERE
#


#
# ALLOCATE_rmb_SHARED, and DELETE_rmb_SHARED allocate (and delete) temporary
# global variables
#


function allocate_rmb_shared -d "allocate shared (global variables)"
    set -gx __rmb_remaining_args
    set -gx __rmb_subcommand_args
    set -gx __rmb_module_args
    set -gx __rmb_stat
    set -gx __rmb_stdout
    set -gx __rmb_stderr
end



function delete_rmb_shared -d "deallocate shared (global variables)"
    set -e __rmb_remaining_args
    set -e __rmb_subcommand_args
    set -e __rmb_module_args
    set -e __rmb_stat
    set -e __rmb_stdout
    set -e __rmb_stderr
end




#
# STREAM_ARGS and SHIFT_ARGS: helper functions manipulating the `argv` array:
#   -> STREAM_ARGS: echos the `argv` array element-by-element
#   -> SHIFT_ARGS:  echos the `argv` array element-by-element starting with the
#                   second element. If `argv` has only one element, echo the
#                   empty string `""`.
# NOTE: while `stream_args` is not strictly necessary, it adds a nice symmetry
#       to `shift_args`
#

function stream_args -d "echos args as a stream"
    # return the elements of `$argv` as an array
    #  -> since we want to be able to call it as part of `set x (shift_args
    #     $x)`, we return these one-at-a-time using echo... this means that the
    #     sub-command stream will correctly concatenate the output into an array
    for elt in $argv
        echo $elt
    end
end


function shift_args -d "simulates bash shift"
    #
    # Returns argv[2..-1] (as an array)
    #  -> if argv has only 1 element, then returns the empty string. This
    #     simulates the behavior of bash `shift`
    #

    if test -z "$argv[2]"
        # there are no more element, returning the empty string
        echo ""
    else
        # return the next elements `$argv[2..-1]` as an array
        #  -> since we want to be able to call it as part of `set x (shift_args
        #     $x)`, we return these one-at-a-time using echo... this means that
        #     the sub-command stream will correctly concatenate the output into
        #     an array
        for elt in $argv[2..-1]
            echo $elt
        end
    end

end




#
# CAPTURE_ALL: helper function used to capture stdout, stderr, and status
#   -> CAPTURE_ALL: there is a bug in fish, that prevents stderr re-capture
#                   from nested command substitution:
#                   https://github.com/fish-shell/fish-shell/issues/6459
#

function capture_all
    begin;
        begin;
            eval $argv[1]
            set $argv[2] $status  # read sets the `status` flag => capture here
        end 2>| read -z __err
    end 1>| read -z __out

    # output arrays
    set $argv[3] (echo $__out | string split \n)
    set $argv[4] (echo $__err | string split \n)

    return 0
end




#
# GET_rmb_FLAGS, and GET_MOD_ARGS: support functions for extracting arguments and
# flags. Note bash's `shift` operation is simulated by the `__rmb_remaining_args`
# array which is roughly equivalent to `$@` in bash.
#

function get_rmb_flags -d "return leading flags"
    #
    # Accumulate initial flags for main ramble command. NOTE: Sets the external
    # array: `__rmb_remaining_args` containing all unprocessed arguments.
    #

    set -l i 1
    set -l n (count $argv)

    while test $i -le $n
        set -l elt $argv[$i]

        if echo "x$elt" | string match -r -q "^x-"
            echo $elt
            switch "x$elt"
                case "x-w" "x--workspace" "x-D" "x--workspace-dir" "x-c" "x--config" "x-C" "x--config-scope" "x--color" "x--sorted-profile" "x--lines" "x--profile-restrictions"
                    set i (math $i+1)
                    if test $i -le $n
                        echo $argv[$i]
                    end
            end
        else
            set __rmb_remaining_args (stream_args $argv[$i..-1])
            return
        end

        set i (math $i+1)
    end

    set -e __rmb_remaining_args
end



#
# CHECK_RMB_FLAGS, CONTAINS_HELP_FLAGS, CHECK_WORKSPACE_ACTIVATE_FLAGS, and
# CHECK_WORKSPACE_DEACTIVATE_FLAGS: support functions for checking arguments and flags.
#

function check_rmb_flags -d "check ramble flags for h/V flags"
    set -l skip_next 0
    for f in $argv
        if test $skip_next -eq 1
            set skip_next 0
            continue
        end
        switch "x$f"
            case "x-h" "x--help" "x-H" "x--all-help" "x-V" "x--version" "x-h*" "x-H*" "x-V*"
                return 0
            case "x-w" "x--workspace" "x-D" "x--workspace-dir" "x-c" "x--config" "x-C" "x--config-scope" "x--color" "x--sorted-profile" "x--lines" "x--profile-restrictions"
                set skip_next 1
            case "x--*" "x-*[wDcC]*"
            case "x-*h*" "x-*H*" "x-*V*"
                return 0
        end
    end
    return 1
end



function match_flag -d "checks all combinations of flags occurring inside of a string"

    # Remove leading and trailing spaces -- but we need to insert a "guard" (x)
    # so that eg. `string trim -h` doesn't trigger the help string for `string trim`
    set -l _a (string sub -s 2 (string trim "x$argv[1]"))
    set -l _b (string sub -s 2 (string trim "x$argv[2]"))

    if test -z "$_a" || test -z "$_b"
        return 0
    end

    # surrounded by spaced
    if echo "$_a" | string match -r -q " +$_b +"
        return 0
    end

    # beginning of string + trailing space
    if echo "$_a" | string match -r -q "^$_b +"
        return 0
    end

    # end of string + leadingg space
    if echo "$_a" | string match -r -q " +$_b\$"
        return 0
    end

    # entire string
    if echo "$_a" | string match -r -q "^$_b\$"
        return 0
    end

    return 1

end



function check_workspace_activate_flags -d "check ramble workspace subcommand flags for -h, --sh, --csh, or --fish"
    #
    # Check if inputs contain -h/--help, --sh, --csh, or --fish
    #

    # combine argument array into single string (space separated), to be passed
    # to regular expression matching (`string match -r`)
    set -l _a "$argv"

    # skip if called with blank input. Notes: [1] (cf. EOF)
    if test -n "$_a"

        # looks for a single `-h`
        if match_flag $_a "-h"
            return 0
        end

        # looks for a single `--help`
        if match_flag $_a "--help"
            return 0
        end

        # looks for a single `--sh`
        if match_flag $_a "--sh"
            return 0
        end

        # looks for a single `--csh`
        if match_flag $_a "--csh"
            return 0
        end

        # looks for a single `--fish`
        if match_flag $_a "--fish"
            return 0
        end

    end

    return 1
end


function check_workspace_deactivate_flags -d "check ramble workspace subcommand flags for --sh, --csh, or --fish"
    #
    # Check if inputs contain --sh, --csh, or --fish
    #

    # combine argument array into single string (space separated), to be passed
    # to regular expression matching (`string match -r`)
    set -l _a "$argv"

    # skip if called with blank input. Notes: [1] (cf. EOF)
    if test -n "$_a"

        # looks for a single `--sh`
        if match_flag $_a "--sh"
            return 0
        end

        # looks for a single `--csh`
        if match_flag $_a "--csh"
            return 0
        end

        # looks for a single `--fish`
        if match_flag $_a "--fish"
            return 0
        end

    end

    return 1
end


function check_workspace_create_with_activate_flags -d "check create for activate flags"
    set -l _a "$argv"

    if test -n "$_a"
        if match_flag $_a "-a"
            return 0
        end
        if match_flag $_a "--activate"
            return 0
        end
    end

    return 1
end


#
# RAMBLE RUNNER function, this does all the work!
#


function ramble_runner -d "Runner function for the `ramble` wrapper"


    #
    # Accumulate initial flags for main ramble command
    #

    set __rmb_remaining_args # remaining (unparsed) arguments
    set -l rmb_flags (get_rmb_flags $argv) # sets __rmb_remaining_args


    #
    # h and V flags don't require further output parsing.
    #

    if check_rmb_flags $rmb_flags
        command ramble $rmb_flags $__rmb_remaining_args
        return 0
    end


    #
    # Isolate subcommand and subcommand specs. Notes: [1] (cf. EOF)
    #

    set -l rmb_subcommand ""

    if test -n "$__rmb_remaining_args[1]"
        set rmb_subcommand $__rmb_remaining_args[1]
        set __rmb_remaining_args (shift_args $__rmb_remaining_args)  # simulates bash shift
    end

    set -l rmb_spec $__rmb_remaining_args


    #
    # Filter out workspace. For any other commands, just run
    # the ramble command as is.
    #

    switch $rmb_subcommand

        # CASE: ramble subcommand is `workspace`. Here we get the ramble runtime to
        # supply the appropriate shell commands for setting the workspace
        # variables. These commands are then run by fish (using the `capture_all`
        # function, instead of a command substitution).

        case "workspace"

            set -l rmb_arg ""

            # Extract the first subcommand argument.  Notes: [1] (cf. EOF)
            if test -n "$__rmb_remaining_args[1]"
                set rmb_arg $__rmb_remaining_args[1]
                set __rmb_remaining_args (shift_args $__rmb_remaining_args) # simulates bash shift
            end

            # Notes: [2] (cf. EOF)
            if test "x$rmb_arg" = "x-h"; or test "x$rmb_arg" = "x--help"
                # nothing more needs to be done for `-h` or `--help`
                command ramble workspace -h
            else
                switch $rmb_arg
                    case "activate"
                        set -l _a (stream_args $__rmb_remaining_args)

                        if check_workspace_activate_flags $_a
                            # no args or args contain -h/--help, --sh, or --csh: just execute
                            command ramble workspace activate $_a
                            return $status
                        else
                            # actual call to activate: source the output
                            set -l rmb_workspace_cmd "command ramble $rmb_flags workspace activate --fish $__rmb_remaining_args"
                            capture_all $rmb_workspace_cmd __rmb_stat __rmb_stdout __rmb_stderr
                            set -l rmb_eval_stat 0
                            eval $__rmb_stdout
                            set rmb_eval_stat $status
                            if test -n "$__rmb_stderr"
                                echo -s \n$__rmb_stderr 1>&2  # current fish bug: handle stderr manually
                            end
                            if test $__rmb_stat -eq 0
                                return $rmb_eval_stat
                            else
                                return $__rmb_stat
                            end
                        end

                    case "deactivate"
                        set -l _a (stream_args $__rmb_remaining_args)

                        if check_workspace_deactivate_flags $_a
                            # just  execute the command if --sh, --csh, or --fish are provided
                            command ramble workspace deactivate $_a
                            return $status

                        # Test of further (unparsed arguments). Any other
                        # arguments are an error or help, so just run help
                        # -> TODO: This should throw and error but leave as is
                        #    for compatibility with setup-env.sh
                        # -> Notes: [1] (cf. EOF).
                        else if test -n "$__rmb_remaining_args"
                            command ramble workspace deactivate -h
                            return $status
                        else
                            # no args: source the output of the command
                            set -l rmb_workspace_cmd "command ramble $rmb_flags workspace deactivate --fish"
                            capture_all $rmb_workspace_cmd __rmb_stat __rmb_stdout __rmb_stderr
                            set -l rmb_eval_stat 0
                            eval $__rmb_stdout
                            set rmb_eval_stat $status
                            if test -n "$__rmb_stderr"
                                echo -s \n$__rmb_stderr 1>&2  # current fish bug: handle stderr manually
                            end
                            if test $__rmb_stat -eq 0
                                return $rmb_eval_stat
                            else
                                return $__rmb_stat
                            end
                        end

                    case "create"
                        set -l _a (stream_args $__rmb_remaining_args)

                        if check_workspace_create_with_activate_flags $_a
                            set -l rmb_workspace_cmd "command ramble $rmb_flags workspace create $__rmb_remaining_args"
                            capture_all $rmb_workspace_cmd __rmb_stat __rmb_stdout __rmb_stderr
                            if test -n "$__rmb_stderr"
                                echo -s \n$__rmb_stderr 1>&2  # current fish bug: handle stderr manually
                            end
                            if test $__rmb_stat -eq 0
                                set -l activate_cmd $__rmb_stdout
                                set -l rmb_eval_stat 0
                                eval $activate_cmd
                                set rmb_eval_stat $status
                                if test $rmb_eval_stat -eq 0
                                    set -l ws (echo $activate_cmd | awk '{print $NF}')
                                    echo "==> Created and activated workspace in $ws"
                                end
                                return $rmb_eval_stat
                            end
                            return $__rmb_stat
                        else
                            command ramble workspace create $_a
                            return $status
                        end

                    case "*"
                        # if $__rmb_remaining_args is empty, then don't include it
                        # as argument (otherwise it will be confused as a blank
                        # string input!)
                        if test -n "$__rmb_remaining_args"
                            command ramble workspace $rmb_arg $__rmb_remaining_args
                        else
                            command ramble workspace $rmb_arg
                        end
                        return $status
                end
            end

        case "cd"
            if test -n "$__rmb_remaining_args"
                for _arg in $__rmb_remaining_args
                    switch "x$_arg"
                        case "x--"
                            break
                        case "x-h" "x--help" "x-h*"
                            command ramble $argv
                            return $status
                        case "x--*" "x-*[wDi]*h*"
                        case "x-[esrmW]*h*"
                            command ramble $argv
                            return $status
                    end
                end
            end
            set -l rmb_loc (env _RAMBLE_CD_WRAPPER=1 ramble $argv)
            set -l rmb_stat $status
            if test $rmb_stat -eq 0 -a -n "$rmb_loc"
                cd "$rmb_loc"
                return $status
            end
            return $rmb_stat

        # CASE: Catch-all

        case "*"
            command ramble $argv
            return $status

    end

    return 0
end




#
# RUN RAMBLE_RUNNER HERE
#


#
# Allocate temporary global variables used for return extra arguments from
# functions. NOTE: remember to call delete_rmb_shared whenever returning from
# this function.
#

allocate_rmb_shared


#
# Run ramble command using the ramble_runner.
#

ramble_runner $argv
# Capture state of ramble_runner (returned below)
set -l stat $status


#
# Delete temporary global variables allocated in `allocated_rmb_shared`.
#

delete_rmb_shared



return $stat

end



#################################################################################
# Prepends directories to path, if they exist.
#      pathadd /path/to/dir            # add to PATH
# or   pathadd OTHERPATH /path/to/dir  # add to OTHERPATH
#################################################################################
function ramble_pathadd -d "Add path to specified variable (defaults to PATH)"
    #
    # Adds (existing only) paths to specified (defaults to PATH)
    # variable. Does not warn attempting to add non-existing path. This is not a
    # bug because the MODULEPATH setup tries add all possible compatible systems
    # and therefore rmb_multi_pathadd relies on this function failing silently.
    #

    # If no variable name is supplied, just append to PATH otherwise append to
    # that variable.
    #  -> Notes: [1] (cf. EOF).
    if test -n "$argv[2]"
        set pa_varname $argv[1]
        set pa_new_path $argv[2]
    else
        true # this is a bit of a strange hack! Notes: [3] (cf EOF).
        set pa_varname PATH
        set pa_new_path $argv[1]
    end

    set pa_oldvalue $$pa_varname

    # skip path is not existing directory
    #  -> Notes: [1] (cf. EOF).
    if test -d "$pa_new_path"

        # combine argument array into single string (space separated), to be
        # passed to regular expression matching (`string match -r`)
        set -l _a "$pa_oldvalue"

        # skip path if it is already contained in the variable
        # note spaces in regular expression: we're matching to a space delimited
        # list of paths
        if not echo $_a | string match -q -r " *$pa_new_path *"
            if test -n "$pa_oldvalue"
                set $pa_varname $pa_new_path $pa_oldvalue
            else
                true # this is a bit of a strange hack! Notes: [3] (cf. EOF)
                set $pa_varname $pa_new_path
            end
        end
    end
end


function rmb_multi_pathadd -d "Helper for adding module-style paths by incorporating compatible systems into pathadd" --inherit-variable _rmb_compatible_sys_types
    #
    # Calls ramble_pathadd in path inputs, adding all compatible system types
    # (sourced from $_rmb_compatible_sys_types) to input paths.
    #

    for pth in $argv[2]
        for systype in $_rmb_compatible_sys_types
            ramble_pathadd $argv[1] "$pth/$systype"
        end
    end
end



#
# Figure out where this file is. Below code only needs to work in fish
#
set -l rmb_source_file (status -f)  # name of current file

#
# Identify and lock the python interpreter
#
if test -n "$RAMBLE_PYTHON"
  echo "The RAMBLE_PYTHON environment variable is set to $RAMBLE_PYTHON"
  echo "Will pin the python binary ramble uses to this value".

  if test -n "$_RAMBLE_PYTHON" -a  "$RAMBLE_PYTHON" !=  "$_RAMBLE_PYTHON"
    echo "WARNING: Ramble was previously pinned to use $_RAMBLE_PYTHON"
    echo "         If this is not what you want, set the correct python"
    echo "         in RAMBLE_PYTHON and re-source this file"
  end
end
for cmd in "$RAMBLE_PYTHON" python3 python
    set -l _rmb_python (command -v "$cmd")
    if test $status -eq 0
        set -x _RAMBLE_PYTHON $_rmb_python
        break
    end
end



#
# Find root directory and add bin to path.
#
set -l rmb_share_dir (realpath (dirname $rmb_source_file))
set -l rmb_prefix (realpath (dirname (dirname $rmb_share_dir)))
ramble_pathadd PATH "$rmb_prefix/bin"
set -xg RAMBLE_ROOT $rmb_prefix



#
# No need to determine which shell is being used (obviously it's fish)
#
set -xg RAMBLE_SHELL "fish"
set -xg _rmb_shell "fish"




#
# Check whether we need environment-variables (module) <= `use` is not available
#
set -l need_module "no"
if not functions -q use; and not functions -q module
    set need_module "yes"
end



#
# Make environment-modules available to shell
#
function rmb_apply_shell_vars -d "applies expressions of the type `a='b'` as `set a b`"

    # convert `a='b' to array variable `a b`
    set -l expr_token (string trim -c "'" (string split "=" $argv))

    # run set command to takes, converting lists of type `a:b:c` to array
    # variables `a b c` by splitting around the `:` character
    set -xg $expr_token[1] (string split ":" $expr_token[2])
end


if test "$need_module" = "yes"
    set -l rmb_shell_vars (command ramble sh,modules)

    for rmb_var_expr in $rmb_shell_vars
        rmb_apply_shell_vars $rmb_var_expr
    end

    # _rmb_module_prefix is set by ramble --print-sh-vars
    if test "$_rmb_module_prefix" != "not_installed"
        set -xg MODULE_PREFIX $_rmb_module_prefix
        ramble_pathadd PATH "$MODULE_PREFIX/bin"
    end

else

    set -l rmb_shell_vars (command ramble sh)

    for rmb_var_expr in $rmb_shell_vars
        rmb_apply_shell_vars $rmb_var_expr
    end

end

if test "$need_module" = "yes"
    function module -d "wrapper for the `module` command to point at ramble's modules instance" --inherit-variable MODULE_PREFIX
        eval $MODULE_PREFIX/bin/modulecmd $RAMBLE_SHELL $argv
    end
end



#
# set module system roots
#

# Search of MODULESPATHS by trying all possible compatible system types as
# module roots.
if test -z "$MODULEPATH"
    set -gx MODULEPATH
end
rmb_multi_pathadd MODULEPATH $_rmb_tcl_roots



#
# NOTES
#
# [1]: `test -n` requires exactly 1 argument. If `argv` is undefined, or if it
#      is an array, `test -n $argv` is unpredictable. Instead, encapsulate
#      `argv` in a string, and test the string.
#
# [2]: `test "$a" = "$b$` is dangerous if `a` and `b` contain flags at index 1,
#      as `test $a` can be interpreted as `test $a[1] $a[2..-1]`. Solution is to
#      prepend a non-flag character, eg: `test "x$a" = "x$b"`.
#
# [3]: When the test in the if statement fails, the `status` flag is set to 1.
#      `true` here manuallt resets the value of `status` to 0. Since `set`
#      passes `status` along, we thus avoid the function returning 1 by mistake.

# done: unset sentinel variable as we're no longer initializing
set -e _rmb_initializing
