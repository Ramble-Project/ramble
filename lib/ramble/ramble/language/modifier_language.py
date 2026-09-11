# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import functools
from typing import Optional

import ramble.definitions.requirements
import ramble.language.language_helpers
import ramble.language.shared_language
from ramble.definitions.variables import EnvironmentVariableModifications, VariableModification
from ramble.error import DirectiveError

ModifierMeta = ramble.language.shared_language.SharedMeta
modifier_directive = functools.partial(ModifierMeta.directive, language_type="modifier")


@modifier_directive("modes")
def mode(name, description, **kwargs):
    """Define a new mode for this modifier.

    Modes allow a modifier to bundle a set of modifications together.

    NOTE: A mode 'disabled' is defined by default for all modifiers.

    Args:
        name (str): Name of the mode to define
        description (str): Description of the new mode
    """

    def _execute_mode(mod):
        if name in mod.modes:
            raise DirectiveError(
                f"mode directive given an already defined mode for modifier "
                f"{mod.name}. Provided mode is {name}."
            )
        mod.modes[name] = {"description": description}

    return _execute_mode


@modifier_directive(dicts="default_usage_mode", init_value=None)
def default_mode(name, **kwargs):
    """Define a default mode for this modifier.

    The default mode will be used if modifier mode is not specified in an experiment.

    Args:
        name (str): Name of mode to be used as default
    """

    def _execute_default_mode(mod):
        if name not in mod.modes:
            raise DirectiveError(
                f"default_mode directive given an invalid mode for modifier "
                f"{mod.name}. Valid modes are {str(list(mod.modes.keys()))}"
            )

        if name == "disabled":
            raise DirectiveError(
                f"default_mode directive given an invalid mode for modifier "
                f"{mod.name}. The disabled mode cannot be set as the default mode"
            )
        mod.default_usage_mode = name

    return _execute_default_mode


@modifier_directive("variable_modifications")
def variable_modification(
    name, modification, method="set", mode=None, modes=None, separator=" ", when=None, **kwargs
):
    """Define a new variable modification for a mode in this modifier.

    A variable modification will apply a change to a defined variable within an experiment.

    Args:
        name (str): The variable to modify
        modification (str): The value to modify 'name' with
        method (str): How the modification should be applied
        mode (str): Single mode to group this modification into
        modes (str): List of modes to group this modification into
        separator (str): Optional separator to use when modifying with 'append' or
                         'prepend' methods.
        when (list | None): List of when conditions this modification should apply in

    Supported values are 'append', 'prepend', and 'set':
        'append' will add the modification to the end of 'name'
        'prepend' will add the modification to the beginning of 'name'
        'set' (Default) will overwrite 'name' with the modification
    """

    def _execute_variable_modification(mod):
        supported_methods = ["append", "prepend", "set"]
        if method not in supported_methods:
            raise DirectiveError(
                "variable_modification directive given an invalid method.\n"
                f"  Valid methods are {str(supported_methods)}"
            )

        when_lists = ramble.language.language_helpers.merge_conditions(
            mod, "variable_modification", "mode", "modes", mode=mode, modes=modes, when=when
        )

        for when_list in when_lists:
            when_set = frozenset(when_list)

            if when_set not in mod.variable_modifications:
                mod.variable_modifications[when_set] = {}

            if name not in mod.variable_modifications[when_set]:
                mod.variable_modifications[when_set][name] = []

            mod.variable_modifications[when_set][name].append(
                VariableModification(
                    name=name,
                    modification=modification,
                    method=method,
                    separator=separator,
                    when=when_list,
                )
            )

    return _execute_variable_modification


@modifier_directive("executable_modifiers")
def executable_modifier(name, usage_filter=None, when=None, **kwargs):
    """Register an executable modifier

    Executable modifiers can modify various aspects of non-builtin application
    executable definitions.

    These behave similarly to builtins, in that a python method defines the
    actual modifications

    For example:

    .. code-block:: python

      executable_modifier('write_exec_name')

      def write_exec_name(self, executable_name, executable, app_inst=None):
        prepend_execs = []
        append_execs = [ExecutableCommand(
            template='echo "{executable_name}"',
            mpi=False,
            redirect='{log_file}',
            output_capture=OUTPUT_CAPTURE.DEFAULT
        )]

        return prepend_execs, append_execs

    Would append the `echo "{executable_name}"` to every non-builtin executable
    in an experiment.

    Executable modifiers are allowed to modify the input executable in place.
    Executable modifiers must return two lists of executables.

    Args:
        name (str): Name of executable modifier to use. Should be the name of a
                    class method.
        usage_filter (str): Filters the application of this executable modifier.
                            Modifiers can register filters to select how to apply this.
                            Valid default options include: None, "once", "first_mpi", "all_mpi"
        when (list | None): List of when conditions this executable modifier should apply in

    Each executable modifier needs to return:

     * **prepend_execs (list(CommandExecutable)):** List of executables to inject
       before the base executable
     * **append_execs (list(CommandExecutable)):** List of executables to inject
       after the base executable
    """

    def _executable_modifier(mod):
        when_list = ramble.language.language_helpers.build_when_list(
            when, mod, name, "executable_modifier"
        )
        when_set = frozenset(when_list)

        if when_set not in mod.executable_modifiers:
            mod.executable_modifiers[when_set] = {}

        mod.executable_modifiers[when_set][name] = {
            "usage_filter": usage_filter,
            "when": when_list,
        }

    return _executable_modifier


@modifier_directive("env_var_modifications")
def env_var_modification(
    name,
    modification=None,
    method="set",
    mode=None,
    modes=None,
    when=None,
    **kwargs,
):
    """Define an environment variable modifier

    Environment variable modifications modify the values of environment
    variables within the application instance.

    Args:
        name (str): The name of the environment variable that will be modified
        modification (str): The value of the modification
        method (str): The method of the modification.
        mode (str | None): Name of mode this env_var_modification should apply in
        modes (list(str) | None): List of mode names this env_var_modification should apply in
        when (list | None): List of when conditions this env_var_modification should apply in

    Supported values for method are:

        - set: Defines the variable to equal the modification value
        - unset: Removes any definition of the variable from the environment
        - prepend: Prepends the modification to the beginning of the variable.
          Always uses the separator ':'
        - append: Appends the modification value to the end of the value. Allows a
          keyword argument of 'separator' to define the delimiter between values.
    """

    def _env_var_modification(mod):
        supported_methods = ["set", "unset", "append", "prepend"]
        if method not in supported_methods:
            raise DirectiveError(
                "env_var_modification directive given an invalid method of "
                f"{method}. Supported methods are {str(supported_methods)}"
            )

        if method != "unset" and not modification:
            raise DirectiveError(
                f"env_var_modification directive with method {method} "
                "requires a value for the modification argument."
            )

        when_lists = ramble.language.language_helpers.merge_conditions(
            mod, "env_var_modification", "mode", "modes", mode=mode, modes=modes, when=when
        )

        for when_list in when_lists:
            when_set = frozenset(when_list)

            if when_set not in mod.env_var_modifications:
                mod.env_var_modifications[when_set] = {}

            if name not in mod.env_var_modifications[when_set]:
                mod.env_var_modifications[when_set][name] = EnvironmentVariableModifications(
                    name=name,
                    modification=modification,
                    method=method,
                    when=when_list,
                    **kwargs,
                )
            else:
                mod.env_var_modifications[when_set][name].add_modification(
                    modification=modification, method=method, when=when_list, **kwargs
                )

    return _env_var_modification


@modifier_directive("object_variables", init_value={})
def modifier_variable(
    name: str,
    default,
    description: str,
    values: Optional[list] = None,
    mode: Optional[str] = None,
    modes: Optional[list] = None,
    expandable: bool = True,
    track_used: bool = False,
    when=None,
    **kwargs,
):
    """Define a variable for this modifier

    Args:
        name (str): Name of variable to define
        default: Default value of variable definition
        description (str): Description of variable's purpose
        values (list): Optional list of suggested values for this variable
        mode (str): Single mode this variable is used in, if no mode/modes are
                    specified, will apply to all modes.
        modes (list): List of modes this variable is used in, if no mode/modes are
                      specified, will apply to all modes.
        expandable (bool): True if the variable should be expanded, False if not.
        track_used (bool): True if the variable should be tracked as used,
                           False if not. Can help with allowing lists without vectorizing
                           experiments.
        when (list | None): List of when conditions to apply to directive
    """

    def _define_modifier_variable(mod):
        when_lists = ramble.language.language_helpers.merge_conditions(
            mod, "modifier_variable", "mode", "modes", mode=mode, modes=modes, when=when
        )

        for when_list in when_lists:
            ramble.language.shared_language.variable(
                name,
                default,
                description=description,
                values=values,
                expandable=expandable,
                track_used=track_used,
                when=when_list,
                error_context="modifier_variable",
                **kwargs,
            )(mod)

    return _define_modifier_variable


@modifier_directive("package_manager_requirements")
def package_manager_requirement(
    command: str,
    validation_type: str,
    mode: Optional[str] = None,
    modes: Optional[list] = None,
    regex=None,
    package_manager: str = "*",
    when=None,
    **kwargs,
):
    """Define a requirement when this modifier is used in an experiment with a
    package manager.

    This allows modifiers to inject additional requirements on packages
    managers. These can be used to ensure package manager commands return
    specific values.

    Args:
        command (str): Package manager command to execute, when evaluating the requirement
        validation_type (str): Type of validation to perform on output of command.
                         Valid types are: 'empty', 'not_empty', 'contains_regex',
                         'does_not_contain_regex'
        mode (str): Usage mode this requirement should apply to
        modes (list(str)): List of usage modes this requirement should apply to
        regex (str): Regular expression to use when validation_type is either 'contains_regex'
               or 'does_no_contain_regex'
        package_manager (str): Name of the package manager this requirement applies to
        when (list | None): List of when conditions this requirement should apply to
    """

    def _new_package_manager_requirement(mod):

        regex_validations = ["contains_regex", "does_not_contain_regex"]
        validation_types = ["empty", "not_empty"] + regex_validations

        if validation_type not in validation_types:
            raise DirectiveError(
                f"package_manager_requirement directive given an invalid "
                f"validation_type of {validation_type}\n"
                f"Valid values are {validation_types}"
            )

        if validation_type in regex_validations and not regex:
            raise DirectiveError(
                f"package_manager_requirement validation type is "
                f"{validation_type} but no regex is given"
            )

        when_lists = ramble.language.language_helpers.merge_conditions(
            mod, "package_manager_requirement", "mode", "modes", mode=mode, modes=modes, when=when
        )

        for when_list in when_lists:
            when_set = frozenset(when_list)

            if when_set not in mod.package_manager_requirements:
                mod.package_manager_requirements[when_set] = []

            mod.package_manager_requirements[when_set].append(
                ramble.definitions.requirements.PackageManagerRequirement(
                    command=command,
                    validation_type=validation_type,
                    regex=regex,
                    package_manager=package_manager,
                    when=when_list,
                )
            )

    return _new_package_manager_requirement


@modifier_directive("modifier_conflicts")
def modifier_conflict(
    conflict_type,
    when=None,
    **kwargs,
):
    """Define a conflict with other modifiers on the same experiment.

    Allowed values are defined in the MODIFIER_CONFLICT class in conflicts.py

    Args:
        conflict_type: Either a string or integer based on the options in
                       ramble.util.conflicts.MODIFIER_CONFLICT
    """

    def _define_modifier_conflict(mod):
        from ramble.util.conflicts import MODIFIER_CONFLICT

        conflict_value = None
        usage_error = False
        if conflict_type is not None:
            if isinstance(conflict_type, str):
                if conflict_type not in MODIFIER_CONFLICT._member_names_:
                    usage_error = True
                else:
                    conflict_value = MODIFIER_CONFLICT[conflict_type]
            elif isinstance(conflict_type, int):
                try:
                    conflict_value = MODIFIER_CONFLICT(conflict_type)
                except ValueError:
                    usage_error = True
            elif isinstance(conflict_type, MODIFIER_CONFLICT):
                conflict_value = conflict_type
            else:
                usage_error = True

        if usage_error:
            raise DirectiveError(
                f"modifier_conflict directive on modifier {mod.name} was given "
                f"an invalid value for the conflict_type argument."
                "This argument needs to be an integer or string based on the "
                "MODIFIER_CONFLICT enum.\n"
                f"The provided value was {conflict_type}"
            )

        when_list = ramble.language.language_helpers.build_when_list(
            when, mod, mod.name, "modifier_conflict"
        )
        when_set = frozenset(when_list)

        if conflict_value is None and when_set in mod.modifier_conflicts:
            del mod.modifier_conflicts[when_set]
        else:
            mod.modifier_conflicts[when_set] = conflict_value

    return _define_modifier_conflict
