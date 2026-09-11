# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import fnmatch
import functools
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Union

from packaging.specifiers import SpecifierSet
from packaging.version import InvalidVersion, Version

from ramble.error import DirectiveError


def check_definition(
    single_type, multiple_type, single_arg_name, multiple_arg_name, directive_name
):
    """
    Sanity check definitions before merging or require

    Args:
        single_type: Single string for type name
        multiple_type: List of strings for type names, may contain wildcards
        multiple_pattern_match: List of strings to match against patterns in multiple_type
        single_arg_name: String name of the single_type argument in the directive
        multiple_arg_name: String name of the multiple_type argument in the directive
        directive_name: Name of the directive requiring a type
    """
    if single_type and not isinstance(single_type, str):
        raise DirectiveError(
            f"Directive {directive_name} was given an invalid type "
            f"for the {single_arg_name} argument. "
            f"Type was {type(single_type)}"
        )

    if multiple_type and not isinstance(multiple_type, list):
        raise DirectiveError(
            f"Directive {directive_name} was given an invalid type "
            f"for the {multiple_arg_name} argument. "
            f"Type was {type(multiple_type)}"
        )


def merge_definitions(
    single_type,
    multiple_type,
    multiple_pattern_match,
    single_arg_name,
    multiple_arg_name,
    directive_name,
):
    """Merge definitions of a type

    This method will merge two optional definitions of single_type and
    multiple_type.

    Args:
        single_type: Single string for type name
        multiple_type: List of strings for type names, may contain wildcards
        multiple_pattern_match: List of strings to match against patterns in multiple_type
        single_arg_name: String name of the single_type argument in the directive
        multiple_arg_name: String name of the multiple_type argument in the directive
        directive_name: Name of the directive requiring a type

    Returns:
        list[str]: List of all type names (Merged if both ``single_type`` and ``multiple_type``
        definitions are valid)
    """

    check_definition(
        single_type, multiple_type, single_arg_name, multiple_arg_name, directive_name
    )

    merged_types = []

    if single_type:
        merged_types.append(single_type)

    if multiple_type:
        merged_types.extend(multiple_type)

    merged_types_expanded = expand_patterns(merged_types, multiple_pattern_match)

    return merged_types_expanded


def require_definition(
    single_type,
    multiple_type,
    multiple_pattern_match,
    single_arg_name,
    multiple_arg_name,
    directive_name,
):
    """Require at least one definition for a type in a directive

    This method will validate that single_type / multiple_type are properly defined.

    It will raise an error if at least one type is not defined, or if
    either are the incorrect type.

    Args:
        single_type: Single string for type name
        multiple_type: List of strings for type names, may contain wildcards
        multiple_pattern_match: List of strings to match against patterns in multiple_type
        single_arg_name: String name of the single_type argument in the directive
        multiple_arg_name: String name of the multiple_type argument in the directive
        directive_name: Name of the directive requiring a type

    Returns:
        list[str]: List of all type names (Merged if both single_type and multiple_type
        definitions are valid)
    """

    if not (single_type or multiple_type):
        raise DirectiveError(
            f"Directive {directive_name} requires at least one of "
            f"{single_arg_name} or {multiple_arg_name} to be defined."
        )

    return merge_definitions(
        single_type,
        multiple_type,
        multiple_pattern_match,
        single_arg_name,
        multiple_arg_name,
        directive_name,
    )


def merge_conditions(
    obj,
    directive_name: str,
    single_arg_name: Optional[str] = None,
    multiple_arg_name: Optional[str] = None,
    **kwargs,
) -> List[List[str]]:
    """Merge conditions for a type in a directive, and converts all conditions to
    when conditions

    If single/multiple values are provided, this method will validate that they are
    properly defined, and will merge them into a list of when conditions for each mode.

    Args:
        obj: Object instance
        directive_name: Name of the calling directive
        single_arg_name: Name of the singular kwarg being required
        multiple_arg_name: Name of the plural kwarg being required

    Kwargs:
        when (list | None): List of when conditions to apply to directive
        mode (str | None): Modifier mode to be applied as a when condition
        modes (list(str) | None): List of modifier modes to be applied as when conditions

    Returns:
        list[list[str]]:List of lists of strings, where each inner list is a list of when
        conditions for a mode.
    """
    single_arg_val = kwargs.get(single_arg_name) if single_arg_name else None
    multiple_arg_val = kwargs.get(multiple_arg_name) if multiple_arg_name else None

    base_when_list = build_when_list(kwargs.get("when"), obj, obj.name, directive_name)

    # Create a list of when conditions for each mode (or one modeless list if no mode)
    variant_when_lists = []

    # If args are modifier modes, convert to when conditions
    if single_arg_name == "mode" or multiple_arg_name == "modes":
        all_modes = merge_definitions(
            single_arg_val,
            multiple_arg_val,
            obj.modes,
            "mode",
            "modes",
            directive_name,
        )

        if not all_modes:
            all_modes = [None]

        for mode_name in all_modes:
            if mode_name:
                mode_variant = f"{obj.name}_mode={mode_name}"
                variant_when_list = base_when_list + [mode_variant]
            else:
                variant_when_list = base_when_list

            variant_when_lists.append(variant_when_list)
    else:
        variant_when_lists.append(base_when_list)

    return variant_when_lists


def expand_patterns(merged_types: list, multiple_pattern_match: Union[list, dict]):
    """Expand wildcard patterns within a list of names

    This method takes an input list containing wildcard patterns and expands the
    wildcard with values matching a list of names. Returns a list containing
    matching names and any inputs with zero matches.

    If multiple_pattern_match is a dict keyed on 'when', it checks the input
    against patterns in all 'when' conditions, without evaluating them, and
    returns a list containing names that match under any when condition, and
    any inputs with zero matches.

    Args:
        merged_types: List of strings for type names, may contain wildcards
        multiple_pattern_match: List of strings (optional: nested in when_set
            dict) to match against patterns in merged_types

    Returns:
        list[str]: List of expanded patterns matching the names list plus
        patterns not found in the names list.
    """
    expanded_patterns = OrderedDict()
    for input in merged_types:
        expanded = False
        if (
            multiple_pattern_match
            and isinstance(multiple_pattern_match, dict)
            and isinstance(next(iter(multiple_pattern_match)), frozenset)
        ):
            for pattern_list in multiple_pattern_match.values():
                matched_inputs = fnmatch.filter(pattern_list, input)
                if matched_inputs:
                    expanded = True
                    for match in matched_inputs:
                        expanded_patterns[match] = ""
        else:
            matched_inputs = fnmatch.filter(multiple_pattern_match, input)
            if matched_inputs:
                expanded = True
                for match in matched_inputs:
                    expanded_patterns[match] = ""

        if not expanded:
            expanded_patterns[input] = ""

    return list(expanded_patterns.keys())


def add_variable_validator(obj, var_name, var_values, when_list, wl_name=None):
    """Adds a validator to an object to ensure a variable's value is in a list of values."""
    validator_name = f"validate_values_for_{var_name}_obj_{obj.name}"

    str_values = [str(v) for v in var_values]
    predicate = f"'{{{var_name}}}' in {str_values!r}"
    message = (
        f"Value of variable '{var_name}' ('{{{var_name}}}') is not one of the allowed values: "
        f"{var_values}"
    )
    new_when_list = when_list.copy()
    if wl_name is not None:
        new_when_list.extend([f"workload_name={wl_name}"])
    when_set = frozenset(new_when_list)

    if when_set not in obj.validators:
        obj.validators[when_set] = {}

    obj.validators[when_set][validator_name] = {
        "predicate": predicate,
        "message": message,
        "fail_on_invalid": True,
    }


def build_when_list(
    when_arg: Optional[Union[str, List[str]]],
    obj: Any,
    directive_id: str,
    directive_name: str,
) -> List[str]:
    """Construct list of when conditions based on a directives input argument
    Also, validate that when is passed in with the right type.

    Args:
        when_arg (str | list(str)): Single or list of string conditions that were input into
                                    the calling directive.
        obj: A ramble object (i.e. application, modifier, etc..)
        directive_id (str): Directive identifier. The calling directive can
                            define what is used here, but it should be
                            something that can help users identify where errors
                            from this method originate from.
        directive_name (str): Name of the calling directive

    Returns:
        list[str]: List of strings for all of the when conditions.
    """
    when_list = []
    if when_arg is not None:
        if isinstance(when_arg, str):
            when_arg = [when_arg]
        elif not isinstance(when_arg, list):
            if obj == "DirectiveMeta":
                raise DirectiveError(
                    "DirectiveMeta is unable to process an invalid `when` argument from directive "
                    f"{directive_name} {directive_id}. The `when` argument must be input as a "
                    "string or list."
                )

            else:
                raise DirectiveError(
                    f"Object {obj.name} calls directive {directive_name} {directive_id} "
                    f"with an invalid `when` argument. The `when` argument must be input as a "
                    "string or list."
                )
        when_list.extend(when_arg)

        # Enable '@{version}' syntax in `when` clauses
        if hasattr(obj, "origin_type") and obj.origin_type:
            for i, w in enumerate(when_list):
                if w.startswith("@"):
                    when_list[i] = f"{obj.origin_type}_version{w}"

    return when_list


def _parse_version_spec(value):
    if not value:
        return SpecifierSet()

    # Fallback translation: replace underscores with dots for PEP 440 compatibility
    value = value.replace("_", ".")

    sep_index = value.find(":")
    if sep_index == -1:
        return SpecifierSet(f"=={value}", prereleases=True)
    elif sep_index == 0:
        return SpecifierSet(f"<={value.lstrip(':')}", prereleases=True)
    elif sep_index == len(value) - 1:
        return SpecifierSet(f">={value.rstrip(':')}", prereleases=True)
    else:
        start = value[:sep_index]
        end = value[sep_index + 1 :]
        return SpecifierSet(f">={start},<={end}", prereleases=True)


def is_specifier_set_compatible(spec_set):
    if not spec_set:
        return True

    eq_versions = []
    lower_bounds = []
    upper_bounds = []
    for spec in spec_set:
        try:
            val = Version(spec.version)
        except InvalidVersion:
            return False
        if spec.operator == "==":
            eq_versions.append(val)
        elif spec.operator == ">=":
            lower_bounds.append((val, True))
        elif spec.operator == ">":
            lower_bounds.append((val, False))
        elif spec.operator == "<=":
            upper_bounds.append((val, True))
        elif spec.operator == "<":
            upper_bounds.append((val, False))

    if eq_versions:
        target = eq_versions[0]
        for eq_val in eq_versions[1:]:
            if eq_val != target:
                return False
        for lb, inclusive in lower_bounds:
            if inclusive:
                if not (target >= lb):
                    return False
            else:
                if not (target > lb):
                    return False
        for ub, inclusive in upper_bounds:
            if inclusive:
                if not (target <= ub):
                    return False
            else:
                if not (target < ub):
                    return False
        return True

    max_lb = None
    max_lb_inclusive = True
    for lb, inclusive in lower_bounds:
        if max_lb is None or lb > max_lb:
            max_lb = lb
            max_lb_inclusive = inclusive
        elif lb == max_lb:
            if not inclusive:
                max_lb_inclusive = False

    min_ub = None
    min_ub_inclusive = True
    for ub, inclusive in upper_bounds:
        if min_ub is None or ub < min_ub:
            min_ub = ub
            min_ub_inclusive = inclusive
        elif ub == min_ub:
            if not inclusive:
                min_ub_inclusive = False

    if max_lb is not None and min_ub is not None:
        if max_lb > min_ub:
            return False
        if max_lb == min_ub:
            return max_lb_inclusive and min_ub_inclusive

    return True


@functools.lru_cache(maxsize=4096)
def _parse_when(w_set):
    from ramble.util.format import when_order

    variants: Dict[str, str] = {}
    versions: Dict[str, Any] = {}
    for w_entry in sorted(w_set, key=when_order):
        for w in w_entry.split():
            if "=" in w:
                name, val = w.split("=", 1)
                if name in variants and variants[name] != val:
                    return (
                        None,
                        None,
                        f"variant '{name}' has conflicting values: '{variants[name]}' and '{val}'",
                    )
                variants[name] = val
            elif w.startswith(("+", "~")):
                name = w[1:]
                val = "True" if w.startswith("+") else "False"
                if name in variants and variants[name] != val:
                    return (
                        None,
                        None,
                        f"variant '{name}' has conflicting values: '{variants[name]}' and '{val}'",
                    )
                variants[name] = val
            elif "@" in w:
                name, ver = w.split("@", 1)
                try:
                    spec_set = _parse_version_spec(ver)
                except Exception as e:
                    return (
                        None,
                        None,
                        f"version '{name}' has invalid spec '{ver}': {e}",
                    )
                if name in versions:
                    combined = versions[name] & spec_set
                    if not is_specifier_set_compatible(combined):
                        msg = (
                            f"version '{name}' has conflicting values: "
                            f"'{versions[name]}' and '{ver}'"
                        )
                        return (None, None, msg)
                    versions[name] = combined
                else:
                    versions[name] = spec_set
    return variants, versions, None


def are_when_compatible(when_set1, when_set2):
    """Determine if two sets of when conditions are compatible

    Args:
        when_set1 (list): First set of when conditions
        when_set2 (list): Second set of when conditions

    Returns:
        bool: True if they are compatible, False otherwise
    """
    if not isinstance(when_set1, frozenset):
        when_set1 = frozenset(when_set1)

    if not isinstance(when_set2, frozenset):
        when_set2 = frozenset(when_set2)

    v1, ver1, _ = _parse_when(when_set1)
    v2, ver2, _ = _parse_when(when_set2)

    if v1 is None or v2 is None:
        return False

    for name in v1.keys() & v2.keys():
        if v1[name] != v2[name]:
            return False

    for name in ver1.keys() & ver2.keys():
        if not is_specifier_set_compatible(ver1[name] & ver2[name]):
            return False
    return True


def is_when_impossible(when_list):
    """Determine if a single list of when conditions is self-contradictory

    Args:
        when_list (list): list of when conditions

    Returns:
        tuple[bool, str | None]: True and a message if it is impossible, False and None otherwise
    """
    if when_list is None:
        return False, None

    if isinstance(when_list, str):
        when_list = [when_list]

    if not isinstance(when_list, frozenset):
        when_list = frozenset(when_list)

    _, _, conflict = _parse_when(when_list)
    if conflict:
        return True, conflict
    return False, None
