# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import copy
from typing import Dict, List, Optional

import ramble.util.colors as color


class SoftwareSpec:

    def __init__(
        self,
        name: str,
        pkg_spec: str,
        prefix: str = "",
        compiler: Optional[str] = None,
        compiler_spec: Optional[str] = None,
        inject_if_missing: bool = False,
        when: Optional[List[str]] = None,
    ):
        self.name = name
        self.pkg_spec = pkg_spec
        self.prefix = prefix
        self.compiler = compiler
        self.compiler_spec = compiler_spec
        self.inject_if_missing = inject_if_missing
        self.when = when.copy() if when else []

    def to_dict(self, apply_prefix: bool = False):
        prefix_base = self.prefix if apply_prefix else ""
        prefix_str = f"{prefix_base}_" if prefix_base else ""

        attrs = ["pkg_spec", "compiler", "compiler_spec"]

        output = {}
        for attr in attrs:
            val = getattr(self, attr, None)
            if val is not None:
                output[f"{prefix_str}{attr}"] = val
        return output

    def as_str(self, n_indent: int = 0, verbose: bool = False):
        base_indent = " " * n_indent
        indentation = " " * (n_indent + 4)
        self_dict = self.to_dict()
        color_name = color.section_title(self.name)
        output = f"{base_indent}{color_name}:\n"
        for key, val in self_dict.items():
            output += f"{indentation}{color.nested_1(key)}: {val}\n"
        if self.when:
            color_when = color.nested_1("when")
            output += f"{indentation}{color_when}: {self.when}\n"
        return output

    def __str__(self):
        self_dict = self.to_dict()
        self_dict["prefix"] = self.prefix
        return str(self_dict)

    def copy(self):
        return copy.deepcopy(self)

    def conflict_spec(self, test, skip_conflicting_when: bool = True):
        if skip_conflicting_when:
            new_when = set(getattr(self, "when", set()))
            test_when = set(getattr(test, "when", set()))

            if new_when != test_when:
                return False

        if self.prefix != test.prefix:
            return False

        for attr in ["pkg_spec", "compiler", "compiler_spec"]:
            new_val = getattr(self, attr, None)
            test_val = getattr(test, attr, None)
            if new_val != test_val:
                return True

        return False

    def conflict_dict(self, test_dict: Dict):
        self_dict = self.to_dict()
        for key, val in self_dict.items():
            if key in test_dict and val != test_dict[key]:
                return True
        return False
