# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
"""Define base classes for workflow manager definitions"""

import abc
from typing import Collection, Iterator

import ramble.definitions.families
import ramble.variants
from ramble.expander import ExpanderError
from ramble.language.language_base import DirectiveMeta
from ramble.language.workflow_manager_language import (
    workflow_manager_variable,
)
from ramble.util.naming import NS_SEPARATOR
from ramble.workspace import namespace

ObjectMixin = ramble.repository.get_base_class("object-mixin")


class WorkflowManagerBase(ObjectMixin, metaclass=DirectiveMeta):
    origin_type = "workflow_manager"
    _builtin_name = NS_SEPARATOR.join(
        ("workflow_manager_builtin", "{obj_name}", "{name}")
    )
    _language_types = ["workflow_manager", "shared"]
    _language_classes = _language_types
    pipelines = [
        "analyze",
        "setup",
        "execute",
    ]
    is_containerized = False

    workflow_manager_variable(
        "workflow_banner",
        default="",
        description="Banner to describe the workflow within execution templates",
    )

    workflow_manager_variable(
        "workflow_pragmas",
        default="",
        description="Pragmas to apply within execution templates for the workflow",
    )

    workflow_manager_variable(
        "workflow_hostfile_cmd",
        default="",
        description="Hostfile command to apply within execution templates for the workflow",
    )

    workflow_manager_variable(
        "hostfile",
        default="{experiment_run_dir}/hostfile",
        description="Default hostfile path",
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
            description="Name of workflow manager for an experiment",
        )

        for family in self.families:
            self.object_variants.multi_value_variant(
                self.families.family_type,
                value=family,
            )

        self.app_inst = None
        self.runner = None

    def set_application(self, app_inst):
        """Set a reference to the associated app_inst"""
        self.app_inst = app_inst
        self.clear_variant_cache()

        if (
            self.is_containerized
            and namespace.containerized not in app_inst.variants
        ):
            app_inst.object_variants.experiment_variant(
                namespace.containerized, True
            )
            app_inst.clear_variant_cache()

    @abc.abstractmethod
    def get_status(self, workspace):
        """Return status of a given job"""

    def conditional_expand(self, templates: Collection[str]) -> Iterator[str]:
        """Return a (potentially empty) iterator of expanded strings

        Args:
            templates: A collection (ordering not important) of templates to expand.
                If the template cannot be fully expanded, it's skipped.
        Returns:
            An iterator of expanded strings
        """
        expander = self.app_inst.expander
        for tpl in sorted(set(templates)):
            try:
                rendered = expander.expand_var(tpl, allow_passthrough=False)
                if rendered:
                    yield rendered
            except ExpanderError:
                # Skip a particular entry if any of the vars are not defined
                continue

    @property
    def template_render_vars(self):
        """Define variables to be used in template rendering"""
        return {}
