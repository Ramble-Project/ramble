# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
"""Define base classes for system definitions"""

import ramble.definitions.families
import ramble.variants
from ramble.language.language_base import DirectiveMeta
from ramble.language.shared_language import (
    register_validator,
    required_variable,
    variant,
    when,
)
from ramble.util.naming import NS_SEPARATOR

ObjectMixin = ramble.repository.get_base_class("object-mixin")


class SystemBase(ObjectMixin, metaclass=DirectiveMeta):
    name = None
    origin_type = "system"
    _builtin_name = NS_SEPARATOR.join(
        ("system_builtin", "{obj_name}", "{name}")
    )
    _language_types = ["system", "shared"]
    _language_classes = _language_types

    system_default_platform = None
    system_default_workflow_manager = None
    system_default_package_manager = None
    system_available_platforms = []

    variant(
        "validate_system",
        default=True,
        description="Whether to validate the system configuration",
    )

    with when("+validate_system"):
        required_variable(
            "max_nodes",
            description="Maximum number of nodes available in this system for this platform",
        )

        register_validator(
            "n_nodes_system_validation",
            predicate="{n_nodes} <= {max_nodes}",
            message="Number of nodes requested ({n_nodes}) exceeds max nodes ({max_nodes})",
        )

        register_validator(
            "n_ranks_system_validation",
            predicate="{n_ranks} <= {max_cores_per_node} * {n_nodes}",
            message="Total number of ranks ({n_ranks}) exceeds max cores ({max_cores_per_node} * {n_nodes})",
        )

    def __init__(self, file_path):
        super().__init__()

        self.object_variants = ramble.variants.VariantSet()
        for var_args in self.class_variants.values():
            self.object_variants.default_variant(**var_args)

        if getattr(self, "families", None) is None:
            self.families = ramble.definitions.families.Families(
                self.origin_type, list(self.class_families.keys())
            )

        self._file_path = file_path

        self.object_variants.default_variant(
            self.origin_type,
            default=self.name,
            description="Name of system for an experiment",
        )

        for family in self.families:
            self.object_variants.multi_value_variant(
                self.families.family_type,
                value=family,
            )

        self.app_inst = None

    def set_application(self, app_inst):
        """Set the application instance for this system"""
        self.app_inst = app_inst
        self.clear_variant_cache()
