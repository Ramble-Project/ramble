# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import copy

import ramble.error
import ramble.util.colors as color
import ramble.util.matrices
from ramble.namespace import namespace

import spack.util.spack_yaml as syaml


class ContextError(ramble.error.RambleError):
    """Exception raised for errors in context parsing and handling."""


class Context:
    """Class to represent a context

    This class contains variable definitions to store any individual context
    (such as application, workload, or experiment) and logic to merge in
    additional contexts by order of precedence."""

    output_mapping = {
        "variables": namespace.variables,
        "variants": namespace.variants,
        "env_variables": namespace.env_var,
        "internals": namespace.internals,
        "chained_experiments": namespace.chained_experiments,
        "modifiers": namespace.modifiers,
        "template": namespace.template,  # TODO: Make sure this is good
        "exclude": namespace.exclude,
        "zips": namespace.zips,
        "tables": namespace.tables,
        "tags": namespace.tags,
        "matrices": namespace.matrices,
        "n_repeats": namespace.n_repeats,
        "formatted_executables": namespace.formatted_executables,
        "success_criteria": namespace.success,
    }

    def __init__(self):
        """Constructor for a Context

        Create a Context object, which holds context attributes.
        """
        self.env_variables = []
        self.variables = syaml.syaml_dict()
        self.variants = syaml.syaml_dict()
        self.version = None
        self.internals = {}
        self.templates = None
        self.formatted_executables = {}
        self.chained_experiments = []
        self.modifiers = []
        self.context_name = None
        self.success_criteria = []
        self.exclude = {}
        self.zips = {}
        self.matrices = []
        self.tags = []
        self.tables = []
        self.is_template = False
        self.n_repeats = 0

    @property
    def escaped_name(self):
        return color.escape_str(self.context_name)

    def merge_context(self, in_context):
        """Merges another Context into this Context."""

        internal_sections = [
            namespace.custom_executables,
            namespace.executables,
            namespace.executable_injection,
            namespace.custom_inputs,
            namespace.custom_workloads,
        ]

        if in_context.variables:
            self.variables.update(in_context.variables)
        if in_context.variants:
            self.variants.update(in_context.variants)
        if in_context.version:
            self.version = in_context.version
        if in_context.env_variables:
            self.env_variables.append(in_context.env_variables)
        if in_context.internals:
            for internal_section in internal_sections:
                if internal_section in in_context.internals:
                    if isinstance(in_context.internals[internal_section], dict):
                        if internal_section not in self.internals:
                            self.internals[internal_section] = {}
                        section_dict = in_context.internals[internal_section]
                        for key, val in section_dict.items():
                            if (
                                key in self.internals[internal_section]
                                and isinstance(self.internals[internal_section][key], dict)
                                and isinstance(val, dict)
                            ):
                                self.internals[internal_section][key].update(copy.deepcopy(val))
                            else:
                                self.internals[internal_section][key] = (
                                    copy.deepcopy(val) if isinstance(val, (dict, list)) else val
                                )
                    elif isinstance(in_context.internals[internal_section], list):
                        if internal_section not in self.internals:
                            self.internals[internal_section] = []
                        self.internals[internal_section].extend(
                            in_context.internals[internal_section]
                        )
                    else:
                        self.internals[internal_section] = in_context.internals[internal_section]
        if in_context.chained_experiments:
            for chained_exp in in_context.chained_experiments:
                self.chained_experiments.append(chained_exp.copy())
        if in_context.modifiers:
            for modifier in in_context.modifiers:
                self.modifiers.append(modifier.copy())
        if in_context.templates is not None:
            self.is_template = in_context.templates
        if in_context.exclude:
            self.exclude = in_context.exclude
        if in_context.zips:
            self.zips.update(in_context.zips)
        if in_context.matrices:
            self.matrices = in_context.matrices
        if in_context.tags:
            self.tags.extend(in_context.tags)
        if in_context.n_repeats != 0:
            try:
                self.n_repeats = int(in_context.n_repeats)
            except (ValueError, TypeError) as e:
                raise ContextError(
                    f"Cannot cast n_repeats value '{in_context.n_repeats}' to an integer: {e}"
                ) from e
        if in_context.formatted_executables:
            self.formatted_executables.update(in_context.formatted_executables)
        if in_context.success_criteria:
            self.success_criteria.extend(in_context.success_criteria)
        if in_context.tables:
            self.tables.extend(in_context.tables)

    def to_workspace_config(self, application_spec, workload_name):
        experiment_config = {}

        for attr_name, namespace_name in self.output_mapping.items():
            attr_val = getattr(self, attr_name, None)
            if attr_val:
                experiment_config[namespace_name] = attr_val

        workspace_config = {
            "ramble": {
                "applications": {
                    application_spec: {
                        "workloads": {
                            workload_name: {"experiments": {self.context_name: experiment_config}}
                        }
                    }
                }
            }
        }

        return workspace_config


def create_context_from_dict(context_name, in_dict):
    """Creates a new Context object from an input dictionary

    Dictionaries should follow the below format:

    .. code-block:: python

        in_dict = {
            'env_vars': [],
            'variables': {},
            'variants': {},
            'internals': {},
            'template': '',
            'chained_experiments': [],
            'modifiers': [],
            'context_name': '',
            'exclude': {},
            'zips': {},
            'matrices': {} or [],
            'tags': [],
            'n_repeats': ''
        }

    Args:
        context_name (str): The name of the context (e.g., application name)
        in_dict (dict): A dictionary representing the variable definitions

    Returns:
        Context(object)
    """

    new_context = Context()

    new_context.context_name = context_name

    if namespace.env_var in in_dict:
        new_context.env_variables = in_dict[namespace.env_var]

    if namespace.variables in in_dict:
        new_context.variables = in_dict[namespace.variables]

    if namespace.variants in in_dict:
        new_context.variants = in_dict[namespace.variants]

    if namespace.version in in_dict:
        new_context.version = in_dict[namespace.version]

    if namespace.internals in in_dict:
        new_context.internals = in_dict[namespace.internals]

    if namespace.template in in_dict:
        new_context.templates = in_dict[namespace.template]

    if namespace.chained_experiments in in_dict:
        new_context.chained_experiments = in_dict[namespace.chained_experiments]

    if namespace.modifiers in in_dict:
        new_context.modifiers = in_dict[namespace.modifiers]

    if namespace.exclude in in_dict:
        new_context.exclude = in_dict[namespace.exclude]

    if namespace.zips in in_dict:
        new_context.zips = in_dict[namespace.zips]

    if namespace.tables in in_dict:
        new_context.tables = in_dict[namespace.tables].copy()

    if namespace.tags in in_dict:
        new_context.tags = in_dict[namespace.tags].copy()

    new_context.matrices = ramble.util.matrices.extract_matrices(
        "experiment creation", context_name, in_dict
    )

    if namespace.n_repeats in in_dict:
        try:
            new_context.n_repeats = int(in_dict[namespace.n_repeats])
        except (ValueError, TypeError) as e:
            raise ContextError(
                f"Cannot cast n_repeats value '{in_dict[namespace.n_repeats]}' to an integer: {e}"
            ) from e

    if namespace.formatted_executables in in_dict:
        new_context.formatted_executables = in_dict[namespace.formatted_executables].copy()

    if namespace.success in in_dict:
        new_context.success_criteria = in_dict[namespace.success].copy()

    return new_context
