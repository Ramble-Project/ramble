# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
import functools
import os
from html import escape
from typing import Any, Optional

import ramble.config
import ramble.definitions.families
import ramble.repository
import ramble.variants
from ramble.definitions.versions import ObjectVersion
from ramble.error import ObjectValidationError
from ramble.language.shared_language import SharedMeta
from ramble.repository import ObjectTypes
from ramble.util import format
from ramble.util.foms import NULL_CONTEXT
from ramble.util.logger import logger


class ObjectMixin(metaclass=SharedMeta):
    """A mixin class for Ramble objects"""

    origin_type: str
    _name = None
    _language_types = ["shared"]
    _verbosity = "short"

    def __init__(self, file_path: Optional[str] = None):
        if not hasattr(self, "selected_version"):
            self.selected_version: Optional[ObjectVersion] = None

        self._file_path = file_path
        self.app_inst = None

        self.object_variants = ramble.variants.VariantSet()
        if hasattr(self, "class_variants"):
            for var_args in self.class_variants.values():
                self.object_variants.default_variant(**var_args)

        if hasattr(self, "origin_type"):
            if getattr(self, "families", None) is None:
                self.families = ramble.definitions.families.Families(
                    self.origin_type, list(getattr(self, "class_families", ()))
                )

            if self.origin_type not in ("application", "modifier"):
                self.object_variants.default_variant(
                    self.origin_type,
                    default=self.name,
                    description=f"Name of {self.origin_type.replace('_', ' ')} for an experiment",
                )

            for family in self.families:
                self.object_variants.multi_value_variant(
                    self.families.family_type,
                    value=family,
                )

    def set_application(self, app_inst):
        """Set a reference to the associated app_inst"""
        self.app_inst = app_inst
        self.clear_variant_cache()

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
        for ver in getattr(self, "known_versions", {}).values():
            if getattr(ver, "preferred", False):
                return ver
        return None

    @preferred_version.setter
    def preferred_version(self, value: Optional[Any]):
        if not hasattr(self, "known_versions"):
            return
        from ramble.language.language_base import (
            ensure_instance_directive_copy,
        )

        ensure_instance_directive_copy(self, "known_versions")
        for ver in self.known_versions.values():
            if hasattr(ver, "preferred"):
                ver.preferred = False
        if value is not None:
            try:
                value.preferred = True
            except (AttributeError, TypeError):
                pass
            ver_key = (
                getattr(value, "version_number", None)
                or getattr(value, "version", None)
                or str(value)
            )
            self.known_versions[ver_key] = value

    def _copy_evaluated_directives(self, target):
        """Copy instance-modified directive dictionaries from self to target."""
        from ramble.language.language_base import _UNSET, _copy_directive_value

        directive_dicts = getattr(self, "_directive_dict_names", set())

        for dict_name in directive_dicts.intersection(self.__dict__):
            val = self.__dict__[dict_name]
            if val is _UNSET:
                continue
            if (
                dict_name in target.__dict__
                and target.__dict__[dict_name] == val
            ):
                continue
            target.__dict__[dict_name] = _copy_directive_value(val)

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
        if getattr(self, "origin_type", None) == "application":
            return self
        return getattr(self, "app_inst", None)

    @classmethod
    def _get_object_type(cls):
        origin_type = getattr(cls, "origin_type", None)
        if origin_type:
            try:
                return ramble.repository.simplify_object_type(origin_type)
            except ramble.repository.UnknownObjectTypeError:
                return None
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
            obj_type = self._get_object_type()
            obj_file = (
                ramble.repository.type_definitions[obj_type]["file_name"]
                if obj_type in ramble.repository.type_definitions
                else f"{self.origin_type}.py"
            )
            raise ObjectValidationError(
                f"The current version {current_ver.version} is not defined in the "
                f"{obj_file}. You must select from defined versions. Set "
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
                version_number=version_number or "",
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

        if app_inst is not None:
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

    def get_fom_value(self, fom_name, context=NULL_CONTEXT):
        """Get a resolved FOM value by name and optional context"""
        app_inst = self._get_app_inst()
        return app_inst.get_fom_value(fom_name, context=context)

    def get_fom_values(self, fom_name, context=NULL_CONTEXT):
        """Get a list of all resolved FOM values matching fom_name and context"""
        app_inst = self._get_app_inst()
        return app_inst.get_fom_values(fom_name, context=context)

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
            ws = kwargs.get("workspace") or getattr(obj, "workspace", None)
            cache = getattr(ws, "object_command_cache", None)
            if cache is None:
                return method(obj, *args, **kwargs)

            def _make_hashable(val):
                if isinstance(val, dict):
                    return frozenset(
                        (k, _make_hashable(v)) for k, v in val.items()
                    )
                return val

            key = (
                obj.origin_type,
                obj.name,
                method.__name__,
                tuple(_make_hashable(a) for a in args),
                frozenset((k, _make_hashable(v)) for k, v in kwargs.items()),
            )
            if key not in cache:
                cache[key] = method(obj, *args, **kwargs)
            return cache[key]

        return wrapper
