# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
"""Define base classes for platform definitions"""

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


class PlatformBase(ObjectMixin, metaclass=DirectiveMeta):
    name = None
    origin_type = "platform"
    _builtin_name = NS_SEPARATOR.join(
        ("platform_builtin", "{obj_name}", "{name}")
    )
    _language_types = ["platform", "shared"]
    _language_classes = _language_types

    variant(
        "accelerator",
        default=False,
        description="Whether platform has accelerator or not",
    )

    variant(
        "accelerator_type",
        default=None,
        values=[None],
        description="Type of accelerator on this platform",
    )

    variant(
        "validate_platform",
        default=True,
        description="Whether to validate the platform configuration",
    )

    with when("+validate_platform"):
        required_variable(
            "max_accelerators_per_node",
            description="Maximum number of accelerators per node for this platform",
        )

        required_variable(
            "max_sockets_per_node",
            description="Maximum number of sockets per node on this platform",
        )

        required_variable(
            "max_threads_per_core",
            description="Maximum number of threads per core for this platform",
        )

        required_variable(
            "max_cores_per_node",
            description="Maximum number of cores per node for this platform",
        )

        required_variable(
            "max_memory_per_node",
            description="Maximum amount of memory per node for this platform",
        )

        register_validator(
            "threads_per_node_platform_validation",
            predicate="{n_threads} * {processes_per_node} <= {max_cores_per_node}",
            message="Number of threads per node ({n_threads} * {processes_per_node}) "
            "exceeds max cores per node ({max_cores_per_node})",
        )

        register_validator(
            "accelerators_per_node_platform_validation",
            predicate="{accelerators_per_node} <= {max_accelerators_per_node}",
            message="Number of accelerators per node ({accelerators_per_node}) "
            "exceeds max accelerators on node ({max_accelerators_per_node})",
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
            description="Name of platform for an experiment",
        )

        for family in self.families:
            self.object_variants.multi_value_variant(
                self.families.family_type,
                value=family,
            )

        self.app_inst = None

    def set_application(self, app_inst):
        """Set the application instance for this platform"""
        self.app_inst = app_inst
        self.clear_variant_cache()
