# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from typing import Callable, Optional

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

import ramble.util.colors as color
from ramble.language.language_base import DirectiveError


class ObjectVersion:
    def default_conversion(self, version_str):
        return version_str

    def __init__(
        self,
        version_number: str = "",
        version: Optional[Version] = None,
        description: str = "",
        origin_type: str = "",
        preferred: bool = False,
        version_to_pep440: Optional[Callable[[str], str]] = None,
        pep440_to_version: Optional[Callable[[str], str]] = None,
    ):
        self.version_to_pep440 = (
            version_to_pep440 if version_to_pep440 is not None else self.default_conversion
        )
        self.pep440_to_version = (
            pep440_to_version if pep440_to_version is not None else self.default_conversion
        )

        if version:
            self.version = version
        elif version_number:
            pep440_version = self.version_to_pep440(version_number)
            try:
                self.version = Version(pep440_version)
            except InvalidVersion as err:
                raise DirectiveError(
                    f"Version number '{version_number}' (converted: {pep440_version}) must be "
                    "converted to a valid PEP 440 version specifier format to use Ramble's "
                    "versioning functionality. If this object uses version numbering that differs "
                    "from PEP 440, please define the `version_to_pep440()` method. See "
                    "https://peps.python.org/pep-0440/ for valid formats."
                ) from err
        else:
            raise DirectiveError(
                "An ObjectVersion requires either a Version object or a version number"
            )
        self.version_number = version_number
        self.description = description
        self.origin_type = origin_type
        self.preferred = preferred

    def copy(self):
        """Construct a copy of self and return it"""
        return ObjectVersion(
            version_number=self.version_num,
            version=Version(str(self.version)),
            description=self.description,
            origin_type=self.origin_type,
            preferred=self.preferred,
            version_to_pep440=self.version_to_pep440,
            pep440_to_version=self.pep440_to_version,
        )

    def __str__(self):
        return self.version_num

    def __eq__(self, other):
        return str(self) == str(other)

    def as_str(self, n_indent: int = 0, verbose: bool = False):
        """String representation of this version

        Args:
            n_indent (int): Number of spaces to indent string with
            verbose (bool): Whether to include verbose information about the version

        Returns:
            str: Representation of this version
        """
        indentation = " " * n_indent
        out_str = color.section_title(f"{indentation}{self.version}") + "\n"
        out_str += color.nested_1(f"{indentation}    Description: ") + f"{self.description}\n"
        out_str += color.nested_1(f"{indentation}    Preferred: ") + f"{self.preferred}\n"

        return out_str

    @property
    def version_num(self):
        """Returns the version number of this version"""
        if not self.version_number:
            self.version_number = self.pep440_to_version(str(self.version))

        return self.version_number

    def evaluate_conflicts(self, variant):
        """Error if this version conflicts with a variant that is used"""
        # TODO(dapomeroy): Implement logic to allow conflicts to be defined

    def satisfies(self, variant):
        """Determine if an experiment's variant satisfies this version

        Args:
            variant: A version variant containing the "@" sigil

        Returns:
            bool: ``True`` or ``False``, based if the experiment's variant satisfies
            the version
        """
        # Convert the variant syntax to a python packaging specifier set
        variant_name, value = variant.split("@")

        satisfied = False
        if value:
            sep_index = value.find(":")
            if sep_index == -1:
                spec_set = SpecifierSet(f"=={self.version_to_pep440(value)}", prereleases=True)
            elif sep_index == 0:
                spec_set = SpecifierSet(
                    f"<={self.version_to_pep440(value.lstrip(':'))}", prereleases=True
                )
            elif sep_index == len(value) - 1:
                spec_set = SpecifierSet(
                    f">={self.version_to_pep440(value.rstrip(':'))}", prereleases=True
                )
            else:
                start = value[:sep_index]
                end = value[sep_index + 1 :]
                spec_set = SpecifierSet(
                    (f">={self.version_to_pep440(start)}," f"<={self.version_to_pep440(end)}"),
                    prereleases=True,
                )

            satisfied = spec_set.contains(self.version)

        return satisfied
