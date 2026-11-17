# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import shlex
from typing import Any, Dict, List, Optional, Union

import ramble.error
import ramble.util.colors
from ramble.util.output_capture import OUTPUT_CAPTURE
from ramble.util.path import system_path_filter

import spack.util.executable


class PrefixedExecutable(spack.util.executable.Executable):
    """A version of spack.util.executable.Executable that allows command prefixes to be added"""

    @system_path_filter
    def add_default_prefix(self, prefix: Optional[str]):
        """Add a prefixed arg / cmd to the command"""
        if prefix is not None:
            for part in reversed(shlex.split(prefix)):
                self.exe.insert(0, part)

    def copy(self) -> "PrefixedExecutable":
        from copy import deepcopy

        new_exec = deepcopy(self)
        new_exec.returncode = None
        return new_exec


def which(*args: str, **kwargs: Any) -> Optional[PrefixedExecutable]:
    """Finds an executable in the path like command-line which.

    If given multiple executables, returns the first one that is found.
    If no executables are found, returns None.

    Parameters:
        *args (str): One or more executables to search for

    Keyword Arguments:
        path (list | str): The path to search. Defaults to ``PATH``
        required (bool): If set to True, raise an error if executable not found

    Returns:
        (PrefixedExecutable): The first executable that is found in the path
    """
    exe = spack.util.executable.which_string(*args, **kwargs)
    return PrefixedExecutable(exe) if exe else None


class CommandExecutable:
    """CommandExecutable class
    This class is used to represent internal executables in Ramble.

    These executables are portions of an experiment definition. They are
    generally used to group one or more commands together into an executable
    name.
    """

    def __init__(
        self,
        name: str,
        template: Union[str, List[str]],
        use_mpi: bool = False,
        mpi: bool = False,
        variables: Optional[Dict[str, Any]] = None,
        redirect: str = "{log_file}",
        output_capture: OUTPUT_CAPTURE = OUTPUT_CAPTURE.DEFAULT,
        run_in_background: bool = False,
        allow_extension: bool = False,
        when: Optional[List[str]] = None,
        **kwargs: Any,
    ):
        """Create a CommandExecutable instance

        Args:
        - template: Either a string, or a list of strings representing
                    independent commands within this executable
        - use_mpi: Boolean value for if MPI should be applied to each
                   portion of this executable's template
        - mpi: Same as use_mpi
        - variables (dict or None): dictionary of variable definitions
                                   to use for this executable only
        - redirect: File to redirect output of template into
        - output_capture: Operator to use when capturing output
        - run_in_background: If true, run the command in background
        """

        if variables is None:
            variables = {}
        if isinstance(template, str):
            self.template = [template]
        elif isinstance(template, list):
            self.template = template.copy()
        else:
            raise CommandExecutableError(
                "Command executable is given an " f"invalid template type of {type(template)}"
            )

        self.name = name
        self.mpi = use_mpi or mpi
        self.redirect = redirect
        self.output_capture = output_capture
        self.run_in_background = run_in_background
        self.variables = variables.copy()
        self.allow_extension = allow_extension
        self.when = when.copy() if when else []

    def copy(self) -> "CommandExecutable":
        """Replicate a CommandExecutable instance"""
        new_inst = type(self)(
            self.name,
            self.template,
            mpi=self.mpi,
            redirect=self.redirect,
            variables=self.variables,
            output_capture=self.output_capture,
            run_in_background=self.run_in_background,
            when=self.when,
        )
        return new_inst

    def __str__(self) -> str:
        """String representation of CommandExecutable instance"""

        color_name = ramble.util.colors.section_title(self.name)
        attrs = ["mpi", "variables", "redirect", "output_capture", "run_in_background", "when"]
        self_str = f"{color_name}:\n"
        self_str += f"    {ramble.util.colors.nested_1('template')}:\n"
        for temp in self.template:
            self_str += f"    - {temp}:\n"
        for attr in attrs:
            color_attr = ramble.util.colors.nested_1(attr)
            self_str += f"    {color_attr}: {getattr(self, attr)}\n"

        return self_str

    def __eq__(self, cmp) -> bool:
        attrs = [
            "name",
            "mpi",
            "redirect",
            "output_capture",
            "run_in_background",
            "variables",
            "allow_extension",
            "template",
            "when",
        ]

        if cmp is None:
            return False

        for attr in attrs:
            self_val = getattr(self, attr, None)
            cmp_val = getattr(cmp, attr, None)
            if self_val != cmp_val:
                return False
        return True


class CommandExecutableError(ramble.error.RambleError):
    """Class for errors when using command executable classes"""
