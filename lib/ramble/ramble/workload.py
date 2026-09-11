# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from typing import Dict, FrozenSet, List, Optional

import ramble.util.colors as color
from ramble.definitions.variables import EnvironmentVariable, Variable
from ramble.util.format import when_order
from ramble.util.logger import logger


class Workload:
    """Class representing a single workload"""

    executables: List[str]
    inputs: List[str]
    tags: List[str]

    def __init__(
        self,
        name: str,
        executables: List[str],
        inputs: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        where: Optional[List[str]] = None,
        exclude_where: Optional[List[str]] = None,
        when: Optional[List[str]] = None,
    ):
        """Constructor for a workload

        Args:
            name (str): Name of this workload
            executables (list(str)): List of executable names for this workload
            inputs (list(str) | None): List of input names for this workload
            tags (list(str) | None): List of tags for this workload
        """
        if inputs is None:
            inputs = []
        if tags is None:
            tags = []
        if where is None:
            where = []
        if exclude_where is None:
            exclude_where = []
        if when is None:
            when = []

        self.name = name
        self.variables: Dict[FrozenSet[str], List[Variable]] = {}
        self.environment_variables: Dict[FrozenSet[str], List[EnvironmentVariable]] = {}
        self.when = when

        attr_names = ["executables", "inputs", "tags", "where", "exclude_where"]
        attr_vals = [executables, inputs, tags, where, exclude_where]

        for attr, vals in zip(attr_names, attr_vals):
            if isinstance(vals, list):
                setattr(self, attr, vals.copy())
            else:
                attr_val = []
                if vals:
                    attr_val.append(vals)
                setattr(self, attr, attr_val)

    def __str__(self):
        if not hasattr(self, "_str_indent"):
            self._str_indent = 0
        return self.as_str(n_indent=self._str_indent)

    def as_str(self, n_indent: int = 0, verbose: bool = False):
        """String representation of this workload

        Args:
            n_indent (int): Number of spaces to indent string with
            verbose (bool): Whether to include verbose information

        Returns:
            str: Representation of this workload
        """
        attrs = [
            ("Executables", "executables"),
            ("Inputs", "inputs"),
            ("Tags", "tags"),
            ("Where", "where"),
            ("Exclude Where", "exclude_where"),
            ("When", "when"),
        ]

        indentation = " " * n_indent

        out_str = color.section_title(f"{indentation}Workload: ")
        out_str += f"{self.name}\n"
        for attr in attrs:
            out_str += color.nested_1(f"{indentation}    {attr[0]}: ")
            attr_val = getattr(self, attr[1], [])
            # TODO: Remove this after adding 'when' to the loop in 'ramble info' that prints
            # workloads. Better to group workloads under 'when' than print 'when' for each workload
            if attr[0] == "When" and isinstance(attr_val, list):
                out_str += f"{' AND '.join(x for x in attr_val)}\n"
            else:
                out_str += f"{attr_val}\n"

        if self.variables:
            out_str += color.nested_1(f"{indentation}    Variables:\n")
            for when_set, var_list in self.variables.items():
                if when_set:
                    out_str += color.nested_2(f"{indentation}        When: ")
                    when_str = " AND ".join(x for x in sorted(when_set, key=when_order))
                    out_str += f"{when_str}\n"
                else:
                    out_str += color.nested_2(f"{indentation}        Unconditional\n")

                var_dict = {}
                for var in var_list:
                    var_dict[var.name] = var
                for var_name in sorted(var_dict.keys()):
                    out_str += var_dict[var_name].as_str(n_indent=(n_indent + 12), verbose=verbose)

        if self.environment_variables:
            out_str += color.nested_1(f"{indentation}    Environment Variables:\n")
            for when_set, env_var_list in self.environment_variables.items():
                if when_set:
                    out_str += color.nested_2(f"{indentation}        When: ")
                    when_str = " AND ".join(x for x in sorted(when_set, key=when_order))
                    out_str += f"{when_str}\n"
                else:
                    out_str += color.nested_2(f"{indentation}        Unconditional\n")

                env_var_dict = {}
                for env_var in env_var_list:
                    env_var_dict[env_var.name] = env_var
                for env_var_name in sorted(env_var_dict.keys()):
                    out_str += env_var_dict[env_var_name].as_str(
                        n_indent=(n_indent + 12), verbose=verbose
                    )

        return out_str

    def add_variable(self, variable: Variable):
        """Add a variable to this workload

        Args:
            variable (ramble.definitions.variables.Variable): New variable to add to this workload
        """
        when_key = frozenset(variable.when)
        if when_key not in self.variables:
            self.variables[when_key] = []
        self.variables[when_key].append(variable)

    def add_environment_variable(self, env_var: EnvironmentVariable):
        """Add an environment variable to this workload

        Args:
            env_var (ramble.definitions.variables.EnvironmentVariable): New environment variable to
                add to this workload
        """
        when_key = frozenset(env_var.when)
        if when_key not in self.environment_variables:
            self.environment_variables[when_key] = []
        self.environment_variables[when_key].append(env_var)

    def add_executable(self, executable: str):
        """Add an executable to this workload

        Args:
            executable (str): Name of executable to add to this workload
        """
        self.executables.append(executable)

    def is_valid(self):
        """Test if this workload is considered valid

        Returns:
            bool: ``True`` if workload is valid, ``False`` otherwise
        """
        if not self.executables:
            return False

        return True

    def find_executable(self, exec_name: str):
        """Find an executable in this workload

        Args:
            exec_name (str): Name of executable to find

        Returns:
            str | None: Name of executable if it exists, ``None`` if it is not found
        """
        for executable in self.executables:
            if executable == exec_name:
                return executable
        return None

    def find_input(self, input_name):
        """Find an input in this workload

        Args:
            input_name (str): Name of input to find

        Returns:
            str | None: Name of input if it exists, ``None`` if it is not found
        """
        for input in self.inputs:
            if input == input_name:
                return input
        return None

    def find_variable(self, name):
        """Find a variable in this workload

        Args:
            var_name (str): Name of variable to find

        Returns:
            ramble.definitions.variables.Variable | None: Variable instance if it exists,
            ``None`` if it is not found
        """
        named_vars: List[Variable] = []
        for var_list in self.variables.values():
            named_vars.extend(var for var in var_list if var.name == name)
        return named_vars


class WorkloadGroup:
    """Class representing a single workload group"""

    name: str
    workloads: Dict[FrozenSet[str], List[str]]

    def __init__(self, name: str, workloads: List[str], when_list: List[str]):
        """Constructor for a workload group. A workload group can have different lists of workloads
        for different 'when' conditions.

        Args:
            name: Name of this workload group
            workloads: List of workloads
            when_list: List of when conditions for this list of workloads
        """
        self.name = name
        self.workloads = {frozenset(when_list): workloads}

    def __str__(self):
        if not hasattr(self, "_str_indent"):
            self._str_indent = 0
        return self.as_str(n_indent=self._str_indent)

    def as_str(self, n_indent: int = 0, verbose: bool = False):
        """String representation of this workload group

        Args:
            n_indent (int): Number of spaces to indent string with
            verbose (bool): Whether to include verbose information

        Returns:
            str: Representation of this workload

        """
        indentation = " " * n_indent
        out_str = color.section_title(f"{indentation}{self.name}\n")
        for when_set, workload_list in self.workloads.items():
            if when_set:
                out_str += color.nested_1(f"{indentation}    When: ")
                when_str = " AND ".join(x for x in sorted(when_set, key=when_order))
                out_str += f"{when_str}\n"
            else:
                out_str += color.nested_1(f"{indentation}    Unconditional\n")

            for workload in workload_list:
                out_str += color.nested_2(f"{indentation}        {workload}\n")

        return out_str

    def add_workloads(self, workloads: List[str], when_list: List[str], mode: str):
        """Add workloads to this workload group using a different set of 'when'
        condition

        Args:
            workloads: List of workloads
            when_list: List of 'when' conditions for this list of workloads
            mode: Append or overwrite workloads in this set of 'when' conditions
        """
        when_set = frozenset(when_list)

        if mode == "append":
            self.workloads.setdefault(when_set, []).extend(workloads)
        else:
            if when_set in self.workloads and self.workloads[when_set] != workloads:
                logger.debug(
                    f"Workload group {self.name} has been defined twice with the same "
                    "`when` conditions. Overwriting by default. Use mode `append` to extend "
                    "workload group instead."
                )
            self.workloads[when_set] = workloads
