# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import functools
from collections.abc import Sequence
from enum import Enum
from typing import Any, Callable, Dict, Optional, Union

import ramble.error
import ramble.util.colors as color
from ramble.expander import Expander

from spack.util.spack_yaml import syaml_bool

reserved_variants = {
    "modifier",
    "package_manager",
    "package_manager_prefix",
    "system",
    "platform",
    "version",
    "workflow_manager",
    "workload_group",
    "is_repeat_child",
    "is_repeat_parent",
    "repeat_index",
}

standard_variants: Dict[str, Dict[str, Any]] = {
    "containerized": {
        "default": False,
        "values": (True, False),
        "description": "Whether this experiment is run inside a container",
    },
}

variant_types = Enum("variant_types", ["default", "experiment", "version"])


def invalidates_cache(func):
    """Decorator to invalidate the variant set cache if the method mutates the set.

    The decorated method should return True if a mutation occurred, and False otherwise.
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        mutated = func(self, *args, **kwargs)
        if mutated:
            self._invalidate_cache()
        return mutated

    return wrapper


class VariantSet:
    """A custom set for housing multiple types of variants, and encapsulating
    the logic of merging them together."""

    def __init__(self):
        self.default_variants = {}
        self.multi_value_variants = {}
        self.experiment_variants = {}
        self.version_variants = {}
        self._set_cache = None
        self._output_set_cache = None
        self._has_template_variants = False
        self._has_output_template_variants = False

    def _invalidate_cache(self):
        self._set_cache = None
        self._output_set_cache = None
        self._has_template_variants = False
        self._has_output_template_variants = False

    def __str__(self):
        if not hasattr(self, "_str_indent"):
            self._str_indent = 0
        return self.as_str(n_indent=self._str_indent)

    def as_str(self, n_indent: int = 0, verbose: bool = False):
        """String representation of this variant set

        Args:
            n_indent (int): Number of spaces to indent string with
            verbose: Print verbose

        Returns:
            str: Representation of this variant set
        """
        to_print = list(self.default_variants.values())

        for variant_set in self.multi_value_variants.values():
            to_print.extend(variant_set)

        to_print.extend(self.experiment_variants.values())
        to_print.extend(self.version_variants.values())

        if verbose:
            out_str = "\n".join(v.as_str(verbose=True) for v in to_print)
        else:
            out_str = "  ".join(v.as_str(verbose=False) for v in to_print)

        return out_str

    def copy(self):
        new_set = VariantSet()

        set_attrs = ["default_variants", "experiment_variants", "version_variants"]
        for set_attr in set_attrs:
            src_attr_set = getattr(self, set_attr)
            setattr(new_set, set_attr, src_attr_set.copy())

        for name, var_list in self.multi_value_variants.items():
            new_set.multi_value_variants[name] = var_list.copy()

        return new_set

    def merge_variants(self, in_set):
        self.merge_default_variants(in_set)
        self.merge_experiment_variants(in_set)
        self.merge_multi_value_variants(in_set)
        self.merge_version_variants(in_set)

    @invalidates_cache
    def merge_default_variants(self, in_set):
        """Merge another variant set's default variants into this variant set.

        Args:
            in_set: VariantSet to merge into self
        """

        mutated = False
        for name, variant in in_set.default_variants.items():
            if name not in self.default_variants:
                self.default_variants[name] = variant.copy()
                mutated = True
            elif name in standard_variants:
                std_default = standard_variants[name].get("default", False)
                if (
                    variant.default != std_default
                    and self.default_variants[name].default == std_default
                ):
                    self.default_variants[name] = variant.copy()
                    mutated = True
        return mutated

    @invalidates_cache
    def merge_experiment_variants(self, in_set):
        """Merge another variant set's experiment variants into this variant set.

        Args:
            in_set: VariantSet to merge into self
        """

        mutated = False
        for name, variant in in_set.experiment_variants.items():
            if name not in self.experiment_variants:
                self.experiment_variants[name] = variant.copy()
                mutated = True
        return mutated

    @invalidates_cache
    def merge_multi_value_variants(self, in_set):
        """Merge another variant set's multi value variants into this variant set.

        Args:
            in_set: VariantSet to merge into self
        """

        if not in_set.multi_value_variants:
            return False

        for name, variant_list in in_set.multi_value_variants.items():
            if name not in self.multi_value_variants:
                self.multi_value_variants[name] = set()
            for variant in variant_list:
                self.multi_value_variants[name].add(variant)
        return True

    @invalidates_cache
    def merge_version_variants(self, in_set):
        """Merge another variant set's version variants into this variant set.

        Args:
            in_set: VariantSet to merge into self
        """

        mutated = False
        for name, variant in in_set.version_variants.items():
            if name not in self.version_variants:
                self.version_variants[name] = variant.copy()
                mutated = True
        return mutated

    def default_variant(
        self,
        name: str,
        default: Optional[Any] = None,
        description: str = "",
        values: Optional[Union[Sequence, Callable[[Any], bool]]] = None,
    ):
        """Define a new default variant within this set.

        Default variants are variants defined by directives in an object. These
        are used to define the defaults, and provide documentation for users.

        Args:
            name: Name of variant
            default: Default value of the variant
            description: Description of the variant, and what it's used for
            values: Set of valid values for the variant
        """

        self._define_variant(
            name,
            variant_type=variant_types.default,
            default=default,
            description=description,
            values=values,
        )

    def experiment_variant(self, name: str, value: Any):
        """Define a new experiment variant within this set.

        Experiment variants are variants defined within a workspace's configuration file.
        These are expected to be user defined values that will override the defaults of the object.

        Experiment variants should always be defined after default variants (as
        defaults come from object directives, and experiment variants come from
        yaml). As a result, we only define experiment variants that have a
        corresponding default variant with the same name.

        Args:
            name: Name of variant
            value: The value the variant should take.
        """
        default_var = None
        if name in self.default_variants:
            default_var = self.default_variants[name]

        # If the default value is a boolean, convert the experiment value to a boolean
        if default_var and isinstance(default_var.default, (bool, syaml_bool)):
            if isinstance(value, str):
                value = value.lower() == "true"
        elif name in standard_variants and isinstance(
            standard_variants[name].get("default"), (bool, syaml_bool)
        ):
            if isinstance(value, str):
                value = value.lower() == "true"

        self._define_variant(
            name,
            variant_type=variant_types.experiment,
            default=value,
            description=None,
            values=None,
        )

    @invalidates_cache
    def multi_value_variant(self, name: str, value: Any):
        if name not in self.multi_value_variants:
            self.multi_value_variants[name] = set()

        self.multi_value_variants[name].add(Variant(name, default=value))
        return True

    def version_variant(self, name: str, value: Any):
        """Define a new version variant within this set.

        Version variants are variants defined within the software section of a workspace's
        configuration file.

        Args:
            name: Name of variant
            default: Default value of the variant
            description: Description of the variant, and what it's used for
            values: Set of valid values for the variant
        """

        self._define_variant(
            name,
            variant_type=variant_types.version,
            default=value,
            description=None,
            values=None,
        )

    @invalidates_cache
    def _define_variant(
        self,
        name: str,
        variant_type: variant_types,
        default: Optional[Any] = None,
        description: Optional[str] = "",
        values: Optional[Union[Sequence, Callable[[Any], bool]]] = None,
    ):
        """Define a variant within this set.

        This is an abstract method intended to construct a new default or
        experiment variant based on the calling signature.

        Args:
            name: Name of variant
            variant_type: Type of variant (as defined in the variant_types enum) of this variant
            default: Default value of the variant
            description: Description of the variant, and what it's used for
            values: Set of valid values for the variant
        """

        variant_dict = None
        if variant_type == variant_types.experiment:
            variant_dict = self.experiment_variants

        elif variant_type == variant_types.default:
            variant_dict = self.default_variants

        elif variant_type == variant_types.version:
            variant_dict = self.version_variants

        else:
            raise RambleVariantError(
                f"Cannot define variant {name} with unknown variant type of {variant_type}"
            )

        old_var = variant_dict.get(name)
        if (
            old_var is None
            or old_var.default != default
            or old_var.description != description
            or old_var.values != values
        ):
            variant_dict[name] = Variant(
                name=name, default=default, description=description, values=values
            )
            return True
        return False

    def value(self, name: str):
        """Extract the value of a variant by name

        Args:
            name: Name of variant to determine value for

        Returns:
            Any | None: Value of variant if found, otherwise None.
        """

        if name in self.experiment_variants:
            return self.experiment_variants[name].default

        if name in self.default_variants:
            return self.default_variants[name].default

        return None

    def version(self, name: str):
        """Extract the version of the named variant

        Args:
            name: Name of the variant to determine version of

        Returns:
            ramble.definitions.versions.ObjectVersion | None: ObjectVersion of the variant
            if found, otherwise None.
        """
        if name in self.version_variants:
            return self.version_variants[name].default

        return None

    def _expanded_set(self, expander: Optional[Expander] = None, for_output: bool = False) -> set:
        """Return an expanded version of the cached set in this variant set.

        Args:
            expander (ramble.expander.Expander): Expander to use for expanding this set
            for_output (bool): If True, returns expanded set for output formatting.

        Returns:
            set[str]: Set of exanded variant definitions
        """
        cache = self._output_set_cache if for_output else self._set_cache
        has_templates = (
            self._has_output_template_variants if for_output else self._has_template_variants
        )

        if expander is None or not has_templates:
            return cache

        expanded_set = set()
        for variant in cache:
            if "{" in variant:
                expanded_set.add(expander.expand_var(variant))
            else:
                expanded_set.add(variant)
        return expanded_set

    def as_set(self, expander: Optional[Expander] = None, for_output: bool = False) -> set:
        """Construct a set of definitions for this variant set

        The set of variant definitions will be used to determine if a when
        clause is valid or not, or formatted for output.

        Args:
            expander (ramble.expander.Expander): Expander to use when expanding
                                                 variant definitions
            for_output (bool): If True, only include primary variant definitions
                               (e.g., +name or ~name for boolean variants) for display/output.

        Returns:
            set[str]: A set consisting of strings with the variant definitions
        """
        cache = self._output_set_cache if for_output else self._set_cache
        if cache is not None:
            return self._expanded_set(expander, for_output=for_output)

        defined_variants = set()
        out_set = set()

        def _add_variant(var):
            if for_output:
                out_set.add(var.as_definition())
            else:
                out_set.update(var.as_definitions())

        for name, variant in self.experiment_variants.items():
            if (
                name in self.default_variants
                or name in reserved_variants
                or name in standard_variants
            ):
                values = None
                if (
                    name in self.default_variants
                    and name not in reserved_variants
                    and self.default_variants[name].values
                ):
                    values = self.default_variants[name].values
                elif name in standard_variants and standard_variants[name].get("values"):
                    values = standard_variants[name]["values"]

                if values:
                    val = variant.default
                    if expander and isinstance(val, str) and "{" in val:
                        try:
                            val = expander.expand_var(val)
                        except Exception:
                            pass
                    if isinstance(val, str) and "{" in val:
                        pass
                    else:
                        if callable(values):
                            is_valid = values(val)
                        elif isinstance(values, (list, tuple, set, Sequence)):
                            is_valid = str(val).lower() in [str(v).lower() for v in values]
                        else:
                            is_valid = True
                        if not is_valid:
                            raise RambleVariantError(
                                f"When defining variant {name} the value {val} is not valid.\n"
                                f"   Valid values include: {values}"
                            )

                _add_variant(variant)
                defined_variants.add(name)

        for name, variant in self.default_variants.items():
            if name not in defined_variants:
                _add_variant(variant)
                defined_variants.add(name)

        for variant_list in self.multi_value_variants.values():
            for variant in variant_list:
                _add_variant(variant)

        # Version variants are included as strings in the set for completeness, but should be
        # checked using the stored ObjectVersion class instead of a string comparison.
        for variant in self.version_variants.values():
            _add_variant(variant)

        if for_output:
            self._output_set_cache = out_set
        else:
            self._set_cache = out_set

        if any("{" in v for v in out_set):
            if for_output:
                self._has_output_template_variants = True
            else:
                self._has_template_variants = True

        return self._expanded_set(expander, for_output=for_output)


class Variant:
    """A custom set for housing multiple types of variants, and encapsulating
    the logic of merging them together."""

    def __init__(
        self,
        name: str,
        default: Optional[Any] = None,
        description: Optional[str] = "",
        values: Optional[Union[Sequence, Callable[[Any], bool]]] = None,
    ):
        self.name = name
        self.default = default
        self.description = description
        self.values = values
        self._definition = self.format_value(self.default)
        self._definitions = self._build_definitions()

    def _build_definitions(self) -> tuple:
        if isinstance(self.default, (bool, syaml_bool)):
            val_str = str(self.default)
            return (
                self._definition,
                f"{self.name}={val_str}",
                f"{self.name}={val_str.lower()}",
            )
        return (self._definition,)

    def copy(self):
        return Variant(
            name=self.name, default=self.default, description=self.description, values=self.values
        )

    def format_value(self, value: Any) -> str:
        """Format a value for this variant into Spack-like syntax"""
        if isinstance(self.default, (bool, syaml_bool)):
            prefix = "+" if value else "~"
            return f"{prefix}{self.name}"
        else:
            return f"{self.name}={value}"

    def as_definition(self) -> str:
        """Build a definition for this variant

        Format the variant as a string which can be used to test against when
        clauses.

        Returns:
            str: String definition for this variant
        """
        return self._definition

    def as_definitions(self) -> tuple:
        """Build a tuple of definitions for this variant

        Format the variant as all possible strings which can be used to test
        against when clauses.

        Returns:
            tuple[str]: String definitions for this variant
        """
        return self._definitions

    def as_str(self, n_indent: int = 0, verbose: bool = False):
        """String documentation of this variant

        Returns:
            str: String for information of this variant
        """
        indentation = " " * n_indent

        if verbose:
            out_str = color.section_title(f"{indentation}{self.name}:\n")
            attrs = [
                ("Description", "description"),
                ("Default", "default"),
                ("Values", "values"),
            ]
            for print_name, attr_name in attrs:
                if hasattr(self, attr_name):
                    value = getattr(self, attr_name, None)
                    if value is not None:
                        out_str += f"{indentation}    {color.nested_1(print_name)}: {value}\n"
        else:
            out_str = self.name

        return out_str

    def __str__(self):
        return self.as_str(n_indent=0)


def validate_variant(
    variant: str,
    values: Optional[Union[Sequence, Callable[[Any], bool]]] = None,
    default: Optional[Any] = None,
):
    """Check if a variant name and definition are valid or not.

    If the input variant name is not valid, this function will raise an
    exception. Otherwise this function will not perform any actions.

    Args:
        variant (str): Variant name to test
        values: Allowed values for the variant
        default: Default value of the variant
    """

    if variant in reserved_variants:
        raise RambleVariantError(
            f"Variant {variant} is invalid, as this name is reserved by ramble"
        )

    if variant in standard_variants:
        std_info = standard_variants[variant]
        std_values = std_info.get("values")
        if (
            std_values
            and values is not None
            and isinstance(std_values, (list, tuple, set, Sequence))
        ):
            if isinstance(values, (list, tuple, set, Sequence)):
                for val in values:
                    if val not in std_values:
                        raise RambleVariantError(
                            f"Variant {variant} is a standard variant and value {val} "
                            f"is not in standard values {std_values}"
                        )


class RambleVariantError(ramble.error.RambleError):
    """Class representing errors with variants"""
