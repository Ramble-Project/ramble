# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
import copy
import functools
import os
from html import escape
from typing import List, Optional

import ramble.config
from ramble.definitions.versions import ObjectVersion
from ramble.error import ObjectValidationError
from ramble.repository import ObjectTypes
from ramble.util import format
from ramble.util.logger import logger


class ObjectMixin:
    """A mixin class for Ramble objects"""

    _name = None

    #: Lists of strings which contains GitHub usernames of attributes.
    #: Do not include @ here in order not to unnecessarily ping the users.
    maintainers: List[str] = []
    tags: List[str] = []

    _verbosity = "short"

    def __init__(self):
        if not hasattr(self, "selected_version"):
            self.selected_version = None

    def __str__(self):
        return self.name

    @property
    def name(self):
        if not self._name:
            # When yielding base classes in _objects, we might encounter
            # ObjectMixin itself. ObjectMixin does not have an explicit name,
            # but we want to avoid a warning that it's missing a name, as it's
            # a known base class.
            if type(self) is ObjectMixin:
                self._name = "object-mixin"
            else:
                base_type = getattr(self, "origin_type", "base_class")
                logger.warn(
                    f"{base_type} {self.__class__.__name__} is missing explicit name."
                )
                self._name = os.path.basename(os.path.dirname(self._file_path))
        return self._name

    @property
    def scoped_name(self):
        return f"{self.origin_type}::{self.name}"

    @property
    def preferred_version(self) -> Optional[ObjectVersion]:
        _ = getattr(self, "known_versions", None)
        return getattr(self, "_preferred_version", None)

    @preferred_version.setter
    def preferred_version(self, value: Optional[ObjectVersion]):
        self._preferred_version = value

    def _copy_evaluated_directives(self, target):
        """Copy all evaluated directive dictionaries from self to target."""
        from ramble.language.language_base import _UNSET

        directive_dicts = getattr(self, "_directive_dict_names", set())
        for dict_name in directive_dicts:
            private_name = f"_{dict_name}"
            if (
                private_name in self.__dict__
                and self.__dict__[private_name] is not _UNSET
            ):
                target.__dict__[private_name] = copy.deepcopy(
                    self.__dict__[private_name]
                )
            elif dict_name in self.__dict__:
                target.__dict__[dict_name] = copy.deepcopy(
                    self.__dict__[dict_name]
                )

    def copy(self):
        """Generic copy method for Ramble objects."""
        new_copy = type(self)(self._file_path)
        if hasattr(self, "_verbosity"):
            new_copy._verbosity = self._verbosity
        self._copy_evaluated_directives(new_copy)
        return new_copy

    def all_pipeline_phases(self, pipeline):
        """Iterator over all phases within a specified pipeline

        Iterate over all phases (and their graph nodes) within a pipeline.

        Args:
            pipeline (str): Name of pipeline to extract phases for

        Yields:
            phase_name (str): Name of phase
            phase_note (ramble.util.graph.GraphNode): Object representing a
                node in the phase graph
        """
        if pipeline in self.phase_definitions:
            yield from self.phase_definitions[pipeline].items()

    def _get_app_inst(self):
        # This helper gets the app_inst for different object types
        if hasattr(self, "app_inst"):
            return self.app_inst
        return self

    def _get_object_type(self):
        if self.origin_type == "application":
            return ObjectTypes.applications
        elif self.origin_type == "package_manager":
            return ObjectTypes.package_managers
        elif self.origin_type == "workflow_manager":
            return ObjectTypes.workflow_managers
        elif self.origin_type == "modifier":
            return ObjectTypes.modifiers
        elif self.origin_type == "system":
            return ObjectTypes.systems
        elif self.origin_type == "platform":
            return ObjectTypes.platforms
        return None

    def satisfy_when(self, when_key, variant_set=None):
        app_inst = self._get_app_inst()
        experiment_variants = self.experiment_variants()
        return app_inst.expander.satisfies(when_key, experiment_variants)

    def validate_version(self):
        """Checks if the current version is registered in the application definition. Can be
        disabled using config:enable_strict_versions:false.
        """

        global_strict = ramble.config.get("config:enable_strict_versions")
        obj_strict = True
        if hasattr(self, "enable_strict_versions"):
            obj_strict = self.enable_strict_versions

        if not global_strict or not obj_strict:
            return

        current_ver = self.object_variants.version(
            f"{self.origin_type}_version"
        )

        if current_ver:
            for known_version in self.known_versions.values():
                if current_ver.version == known_version.version:
                    return
            raise ObjectValidationError(
                f"The current version {current_ver.version} is not defined in the "
                f"{self.origin_type}.py. You must select from defined versions. Set "
                "config:enable_strict_versions:false to disable strict version checking."
            )

    def set_version(
        self,
        version_number: Optional[str] = "",
        version: Optional[ObjectVersion] = None,
        description: str = "",
    ):
        """Set the version of this object.

        args:
            version_number: Optional. Version number to be converted to ObjectVersion
            version (ramble.definitions.versions.ObjectVersion): Version to set
            description: Description of this version
        """
        if version:
            self.selected_version = version
        else:
            self.selected_version = ObjectVersion(
                version_number=version_number,
                description=description,
                origin_type=self.origin_type,
                version_to_pep440=self.version_to_pep440,
                pep440_to_version=self.pep440_to_version,
            )

        self.object_variants.version_variant(
            f"{self.origin_type}_version", self.selected_version
        )
        self.clear_variant_cache()

    def set_required_variables(self, app_inst=None):
        """Stub that allows objects to update required variables"""

    @staticmethod
    def version_to_pep440(version_str):
        """Converts object version number to PEP 440 compliant version number.
        This enables Ramble to use python.packaging for version comparison logic.
        See https://peps.python.org/pep-0440/ for valid formats.
        """
        return version_str

    @staticmethod
    def pep440_to_version(version_str):
        """Converts PEP 440 compliant version number to object version number"""
        return version_str

    def clear_variant_cache(self):
        """Clear the cached variant set for this object."""
        if hasattr(self, "_variant_cache"):
            self._variant_cache.clear()
        app_inst = self._get_app_inst()
        if app_inst is not self and hasattr(app_inst, "clear_variant_cache"):
            app_inst.clear_variant_cache()

    def experiment_variants(
        self, include_modifier=None, allow_caching=True, app_inst=None
    ):
        """Construct a VariantSet for this experiment.

        Apply some merging logic to VariantSet combination, in order to
        provide scoped variant definitions.

        Args:
            include_modifier (ModifierBase): A single modifier to merge in to resulting set

        Returns:
            VariantSet: Merged variants for the experiment.
        """

        if allow_caching:
            if not hasattr(self, "_variant_cache"):
                self._variant_cache = {}

            cache_key = f"{self.origin_type}::{self.name}"
            if include_modifier is not None:
                cache_key += f"-{include_modifier.origin_type}::{include_modifier.name}::{include_modifier._usage_mode}"

            if cache_key in self._variant_cache:
                return self._variant_cache[cache_key]

        if app_inst is None:
            app_inst = self._get_app_inst()

        self_type = self._get_object_type()
        new_set = self.object_variants.copy()

        exclude_types = [self_type]

        if include_modifier is not None:
            exclude_types.append(ObjectTypes.modifiers)
            new_set.merge_variants(include_modifier.object_variants)

        for _, obj in app_inst.objects(exclude_types=exclude_types):
            new_set.merge_variants(obj.object_variants)

        if allow_caching:
            self._variant_cache[cache_key] = new_set

        return new_set

    @property
    def required_variables(self):
        """Get all the required variables based on the mode and when conditions."""
        if not self.required_vars:
            return {}

        return {
            var_name: {k: var_props[k] for k in var_props.keys() - {"when"}}
            for var_name, var_props in self.required_vars.items()
            if any(self.satisfy_when(w) for w in var_props["when"])
        }

    @property
    def selected_variables(self):
        """Extract all variables which would be included based
        on the current variants.

        Returns:
            (dict) Keys are variable names, values are variable instances
        """
        return {
            var.name: var
            for when_key, var_list in self.object_variables.items()
            if self.satisfy_when(when_key)
            for var in var_list
        }

    @property
    def selected_environment_variables(self):
        """Extract all environment variables which would be included based
        on the current variants.

        Returns:
            (dict) Keys are environment variable names, values are environment
            variable instances
        """
        return {
            env_var.name: env_var
            for when_key, env_var_list in self.object_environment_variables.items()
            if self.satisfy_when(when_key)
            for env_var in env_var_list
        }

    def add_inmem_fom_value(self, fom_map_key, value):
        """Add an in-memory FOM value"""
        app_inst = self._get_app_inst()
        app_inst.add_inmem_fom_value(fom_map_key, value)

    def _github_url(self, obj_def):
        """Link to an object file on github."""
        base_url = "https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin"
        return f'{base_url}/{obj_def["dir_name"]}/{self.name}/{obj_def["file_name"]}'

    def to_html_docs(self, out, obj_def):
        """Writes HTML documentation for this object."""
        out.write('<dl class="docutils">\n')

        out.write(f'<dt>Ramble {obj_def["dir_name"]}:</dt>\n')
        out.write('<dd><ul class="first last simple">\n')
        out.write(
            "<li>"
            '<a class="reference external" '
            f'href="{self._github_url(obj_def)}">'
            f'{self.name}/{obj_def["file_name"]}</a>'
            "</li>\n"
        )
        out.write("</ul></dd>\n")

        out.write("<dt>Description:</dt>\n")
        out.write("<dd>\n")
        out.write(escape(format.format_doc(self.__doc__, indent=2), True))
        out.write("\n")
        out.write("</dd>\n")

        self._format_docs_details(out)

        out.write("</dl>\n")

    def _format_docs_details(self, _out):
        """Hook for objects to add extra documentation."""

    @staticmethod
    def workspace_cache(method):
        """
        A decorator that caches the result of a ramble object's instance method into the workspace.
        """

        @functools.wraps(method)
        def wrapper(obj, *args, **kwargs):
            # Precondition: the method should be called with a `workspace=` argument.
            ws = kwargs["workspace"]
            key = (
                obj.origin_type,
                obj.name,
                method.__name__,
                args,
                frozenset(kwargs.items()),
            )
            if key not in ws.object_command_cache:
                ws.object_command_cache[key] = method(obj, *args, **kwargs)
            return ws.object_command_cache[key]

        return wrapper
