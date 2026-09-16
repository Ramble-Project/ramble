# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
"""Define base classes for modifier definitions"""

import fnmatch
import re

import ramble.repository
import ramble.variants
from ramble.error import (
    ConflictingModifiersError,
    InvalidModeError,
    ModifierError,
)
from ramble.language.language_base import DirectiveMeta
from ramble.language.modifier_language import (
    mode,
    modifier_conflict,
)
from ramble.util.conflicts import MODIFIER_CONFLICT
from ramble.util.logger import logger
from ramble.util.naming import NS_SEPARATOR

ObjectMixin = ramble.repository.get_base_class("object-mixin")


class ModifierBase(ObjectMixin, metaclass=DirectiveMeta):
    name = "modifier-base"
    origin_type = "modifier"
    _builtin_name = NS_SEPARATOR.join(
        ("modifier_builtin", "{obj_name}", "{name}")
    )
    _mod_prefix_builtin = f"modifier_builtin{NS_SEPARATOR}"
    _language_types = ["modifier", "shared"]
    _language_classes = _language_types
    pipelines = [
        "analyze",
        "archive",
        "mirror",
        "setup",
        "pushtocache",
        "execute",
        "logs",
    ]

    modifier_class = "ModifierBase"

    disabled = False

    modifier_conflict(MODIFIER_CONFLICT["name_executables"])
    mode("disabled", description="Mode to disable all modifier functionality")

    def __init__(self, file_path):
        super().__init__()

        self.object_variants = ramble.variants.VariantSet()
        for var_args in self.class_variants.values():
            self.object_variants.default_variant(**var_args)

        self._file_path = file_path
        self._on_executables = ["*"]
        self.expander = None
        self._usage_mode = None
        self.app_inst = None
        self._executable_modification_applied = set()

        self._mod_regex = re.compile(
            self._mod_prefix_builtin + f"{self.name}{NS_SEPARATOR}"
        )

    def copy(self):
        """Deep copy a modifier instance"""
        new_copy = super().copy()
        new_copy._on_executables = self._on_executables.copy()
        new_copy._usage_mode = self._usage_mode

        return new_copy

    def satisfy_when(self, when_key):
        return self.expander.satisfies(when_key, self.experiment_variants())

    def set_usage_mode(self, mode):
        """Set the usage mode for this modifier.

        If not set, or given an empty string the modifier tries to auto-detect a mode.

        If it cannot auto detect the usage mode, an error is raised.
        """
        if mode:
            self._usage_mode = mode
        elif getattr(self, "default_usage_mode", None) is not None:
            self._usage_mode = self.default_usage_mode
            if len(logger.log_stack) >= 1:
                logger.msg(
                    f"    Using default usage mode {self._usage_mode} on modifier {self.name}"
                )
        else:
            non_disabled_modes = set(self.modes)
            non_disabled_modes.remove("disabled")
            if len(non_disabled_modes) != 1:
                raise InvalidModeError(
                    "Cannot auto determine usage "
                    f"mode for modifier {self.name}"
                )

            self._usage_mode = non_disabled_modes.pop()
            if len(logger.log_stack) >= 1:
                logger.msg(
                    f"    Using default usage mode {self._usage_mode} on modifier {self.name}"
                )

        if self._usage_mode == "disabled":
            self.disabled = True

    def set_modifier_variants(self):
        """Set the variants for this modifier.

        Requires usage mode to be set first."""
        self.object_variants.multi_value_variant(
            "modifier",
            value=self.name,
        )

        self.object_variants.multi_value_variant(
            f"{self.name}_mode",
            value=self._usage_mode,
        )

    def set_on_executables(self, on_executables):
        """Set the executables this modifier applies to.

        If given an empty list or a value of None, the default of: '*' is usage.
        """
        if on_executables:
            if not isinstance(on_executables, list):
                raise ModifierError(
                    f"Modifier {self.name} given an unsupported on_executables "
                    f"type of {type(on_executables)}"
                )

            self._on_executables = list(on_executables)
        else:
            self._on_executables = ["*"]

    def inherit_from_application(self, app):
        self.app_inst = app
        self.expander = app.expander.copy()

        for name, value in app.variants.items():
            expanded_value = self.expander.expand_var(value, typed=True)
            self.object_variants.experiment_variant(name, expanded_value)

        modded_vars = self.modded_variables(app)
        self.expander._variables.update(modded_vars)

    @property
    def conflict_value(self):
        """
        Evaluate when sets to determine the most restrictive conflict that is currently satisfied.
        """
        value = None
        for when_set, conflict_value in self.modifier_conflicts.items():
            if self.expander.satisfies(when_set, self.object_variants):
                if value is None:
                    value = conflict_value
                else:
                    if conflict_value.value < value.value:
                        value = conflict_value
        return value

    def check_conflicts(self, existing_modifiers):
        """Evaluate conflicts with other existing modifiers.


        Iterate over (input) existing modifiers, and evaluate if they conflict based on
        this modifier's conflict setting.

        Args:
            existing_modifiers: Existing modifiers in a list
        """
        conflict_value = self.conflict_value

        if conflict_value is None:
            return

        self_idx = len(existing_modifiers)

        for mod_idx, mod_inst in enumerate(existing_modifiers):
            if mod_inst is self:
                self_idx = mod_idx
                continue

            # Don't check conflicts if they are different modifiers
            if mod_inst.name != self.name:
                continue

            if conflict_value == MODIFIER_CONFLICT.name_only:
                comp_str = mod_inst.config_str(index=mod_idx, indent=4)
                self_str = self.config_str(index=self_idx, indent=4)
                raise ConflictingModifiersError(
                    f"Two modifier definitions conflict by having the same name.\n"
                    f"Modifier 1:\n"
                    f"{comp_str}"
                    f"Modifier 2:\n"
                    f"{self_str}"
                )

            elif conflict_value == MODIFIER_CONFLICT.name_mode:
                if (
                    mod_inst.name == self.name
                    and mod_inst._usage_mode == self._usage_mode
                ):
                    comp_str = mod_inst.config_str(
                        index=mod_idx, include_mode=True, indent=4
                    )
                    self_str = self.config_str(
                        index=self_idx, include_mode=True, indent=4
                    )
                    raise ConflictingModifiersError(
                        "Two modifier definitions conflict by having the same "
                        "name and mode.\n"
                        f"Modifier 1:\n"
                        f"{comp_str}"
                        f"Modifier 2:\n"
                        f"{self_str}"
                    )

            elif conflict_value == MODIFIER_CONFLICT.name_executables:
                if mod_inst.name == self.name:
                    compare_set = set(mod_inst._on_executables)
                    self_set = set(self._on_executables)
                    intersect = self_set.intersection(compare_set)
                    if intersect:
                        comp_str = mod_inst.config_str(
                            index=mod_idx, include_executables=True, indent=4
                        )
                        self_str = self.config_str(
                            index=self_idx, include_executables=True, indent=4
                        )
                        raise ConflictingModifiersError(
                            "Two modifier definitions conflict by having the same "
                            "name and overlapping on_executable.\n"
                            f"Modifier 1:\n"
                            f"{comp_str}"
                            f"Modifier 2:\n"
                            f"{self_str}"
                        )

            elif conflict_value == MODIFIER_CONFLICT.name_mode_executables:
                if (
                    mod_inst.name == self.name
                    and mod_inst._usage_mode == self._usage_mode
                ):
                    compare_set = set(mod_inst._on_executables)
                    self_set = set(self._on_executables)
                    intersect = self_set.intersection(compare_set)
                    if intersect:
                        comp_str = mod_inst.config_str(
                            index=mod_idx,
                            include_mode=True,
                            include_executables=True,
                            indent=4,
                        )
                        self_str = self.config_str(
                            index=self_idx,
                            include_mode=True,
                            include_executables=True,
                            indent=4,
                        )
                        raise ConflictingModifiersError(
                            "Two modifier definitions conflict by having the same "
                            "name, mode, and overlapping on_executable.\n"
                            f"Modifier 1:\n"
                            f"{comp_str}"
                            f"Modifier 2:\n"
                            f"{self_str}"
                        )

            if self.selected_version != mod_inst.selected_version:
                comp_str = mod_inst.config_str(
                    index=mod_idx, include_version=True, indent=4
                )
                self_str = self.config_str(
                    index=self_idx, include_version=True, indent=4
                )
                raise ConflictingModifiersError(
                    "Two modifier definitions conflict by having the same name "
                    "and different version numbers.\n"
                    f"Modifier 1:\n"
                    f"{comp_str}"
                    f"Modifier 2:\n"
                    f"{self_str}"
                )

    def config_str(
        self,
        index=None,
        include_mode=False,
        include_executables=False,
        include_version=False,
        indent=0,
    ):
        """Construct a string representation of this modifier's configuration

        Args:
            index (int): Index of this modifier to include if provided
            include_mode (bool): Whether to include the mode of the modifier in the configuration or not
            include_executables (bool): Whether to include the on_executables attribute or not
            include_version (bool): Whether to include the version attribute or not
            indent (int): Number of spaces to prefix the config with

        Returns:
            (str) String representation of the modifier's configuration
        """
        indentation = " " * indent
        out_str = f"{indentation}Name: {self.name}\n"
        if include_version:
            out_str += f"{indentation}Version: {str(self.selected_version)}\n"
        if index is not None:
            out_str += f"{indentation}Index: {index}\n"
        if include_mode:
            out_str += f"{indentation}Mode: {self._usage_mode}\n"
        if include_executables and self._on_executables:
            out_str += f"{indentation}On Executables\n"
            for exec in self._on_executables:
                out_str += f"{indentation}- {exec}\n"
        return out_str

    def define_variable(self, var_name, var_value):
        """Define a variable within this modifier's expander instance"""
        self.expander._variables[var_name] = var_value

    def modify_experiment(self, app):
        """Stubbed method to allow modification of experiment variables before
        an experiment is completely defined.

        This can be used to define things like n_ranks and have it influence
        the name of the resulting experiment.
        """

    def modded_variables(self, app, extra_vars=None):
        mods = {}

        if extra_vars is None:
            extra_vars = {}

        for when_set, var_mod_dict in self.variable_modifications.items():
            if self.expander.satisfies(
                when_set, self.experiment_variants(allow_caching=False)
            ):
                for var, var_mods in var_mod_dict.items():
                    for var_mod in var_mods:
                        if var_mod.method in ["append", "prepend"]:
                            if var in mods:
                                prev_val = mods[var]
                            elif var in extra_vars:
                                prev_val = extra_vars[var]
                            elif var in app.variables:
                                prev_val = app.variables[var]
                            else:
                                prev_val = ""

                            if prev_val:
                                sep = var_mod.separator
                            else:
                                sep = ""

                            if var_mod.method == "append":
                                mods[var] = (
                                    f"{prev_val}{sep}{var_mod.modification}"
                                )
                            else:  # method == prepend
                                mods[var] = (
                                    f"{var_mod.modification}{sep}{prev_val}"
                                )
                        else:  # method == set
                            mods[var] = var_mod.modification

        return mods

    def applies_to_executable(self, executable):
        """Check if this modifier applies to a given executable name."""
        if any(
            fnmatch.fnmatch(executable, pattern)
            for pattern in self._on_executables
        ):
            return True

        return bool(self._mod_regex.match(executable))

    def executable_modifier_applied(self, exec_mod):
        """Check if an executable modifier has been applies alerady


        Returns:
            (bool): True if the executable modifier has been applied. False otherwise
        """
        if exec_mod in self._executable_modification_applied:
            return True
        return False

    def executable_modifier_usage_filter(filter_name: str):
        """Decorator for registering a usage filter for executable modifiers"""

        def _decorator(decorated_function):
            if not hasattr(decorated_function, "_ramble_attributes"):
                decorated_function._ramble_attributes = {}
            decorated_function._ramble_attributes["filter_name"] = filter_name
            return decorated_function

        return _decorator

    @executable_modifier_usage_filter("once")
    def filter_once(self, exec_mod, executable) -> bool:
        """Usage filter for only allowing an executable modifier to be applied
        once in an experiment"""
        return not self.executable_modifier_applied(exec_mod)

    @executable_modifier_usage_filter("first_mpi")
    def filter_first_mpi(self, exec_mod, executable) -> bool:
        """Usage filter for only applying executable modifier to the first MPI
        executable in an experiment"""
        return executable.mpi and not self.executable_modifier_applied(
            exec_mod
        )

    @executable_modifier_usage_filter("all_mpi")
    def filter_all_mpi(self, exec_mod, executable) -> bool:
        """Usage filter for applying an executalbe modifier to only MPI
        executables in an experiment"""
        return executable.mpi

    def get_executable_modifier_filter(self, filter_name):
        """Get the filter function for a usage filter (by name)

        Args:
            filter_name (str): Name of usage filter to extract for filtering executable modifier

        Returns:
            Reference to function, if found. None otherwise"""

        if filter_name is None or filter_name == "None":
            return None

        filter_names = set()
        for attr in dir(self):
            method = getattr(self, attr)

            if callable(method):
                method_attributes = getattr(method, "_ramble_attributes", {})
                test_filter_name = None
                if "filter_name" in method_attributes:
                    test_filter_name = method_attributes["filter_name"]
                filter_names.add(test_filter_name)
                if filter_name == test_filter_name:
                    return method

        logger.die(
            f"When extracting a usage_filter for an executable_modifier "
            f"on modifier {self.name} "
            f"the filter {filter_name} does not exist. Registered filters are: \n"
            f"{filter_names}"
        )

    def executable_modification_applies(
        self, exec_mod, filter_name, executable
    ):
        """Determine if an executable modifier applies to an executable or not

        Args:
            exec_mod (str): Name of executable modifier
            filter_name (str): Name of usage filter to apply
            executable: CommandExecutable object to check if exec_mod applies to

        """
        apply = True

        filter_func = self.get_executable_modifier_filter(filter_name)

        if filter_func is not None:
            apply = filter_func(exec_mod, executable)

        return apply

    def apply_executable_modifiers(
        self, executable_name, executable, app_inst=None
    ):
        """Apply all executable modifiers to an executable

        Args:
            executable_name (str): Name of executable
            executable: CommandExecutable object
            app_inst: Instance of application object

        Returns
            (list, list): List of CommandExecutable objects that occur before
                          and after (respectively) to the input executable.
        """
        pre_execs = []
        post_execs = []
        for when_set, exec_mods in self.executable_modifiers.items():
            if self.expander.satisfies(when_set, self.experiment_variants()):
                for exec_mod, mod_conf in exec_mods.items():
                    if self.executable_modification_applies(
                        exec_mod, mod_conf["usage_filter"], executable
                    ):
                        self._executable_modification_applied.add(exec_mod)
                        mod_func = getattr(self, exec_mod)

                        pre_exec, post_exec = mod_func(
                            executable_name, executable, app_inst=app_inst
                        )

                        pre_execs.extend(pre_exec)
                        post_execs.extend(post_exec)

        return pre_execs, post_execs

    def all_env_var_modifications(self):
        for when_set, env_var_mods in self.env_var_modifications.items():
            if not self.expander.satisfies(
                when_set, self.experiment_variants()
            ):
                continue

            yield from env_var_mods.values()

    def all_package_manager_requirements(self):
        for when_set in self.package_manager_requirements:
            if not self.expander.satisfies(
                when_set, self.experiment_variants()
            ):
                continue

            yield from self.package_manager_requirements[when_set]

    def no_expand_vars(self):
        """Iterator over non-expandable variables in current mode

        Yields:
            (str): Variable name
        """

        for when_key, var_list in self.object_variables.items():
            if not self.expander.satisfies(
                when_key, self.experiment_variants()
            ):
                continue

            for var in var_list:
                if not var.expandable:
                    yield var.name

    def artifact_inventory(self, workspace, app_inst=None):
        """Return an inventory of modifier artifacts

        Artifact inventories are up to the individual modifier to define the
        format of.

        This will then show up in an experiment inventory.

        Returns:
            (Any) Artifact inventory for this modifier
        """

        return

    def _prepare_analysis(self, workspace):
        """Hook to perform analysis that a modifier defines.

        This function allows modifier definitions to inject their own
        processing to output files, before FOMs are extracted.
        """
