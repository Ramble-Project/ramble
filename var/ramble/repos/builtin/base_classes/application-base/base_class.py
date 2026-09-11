# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
"""Define base classes for application definitions"""

import copy
import fnmatch
import importlib.util
import operator
import os
import re
import shlex
import shutil
import stat
import time
from html import escape
from typing import Dict, List

import llnl.util.filesystem as fs
from llnl.util.tty import color

import ramble.config
import ramble.expander
import ramble.fetch_strategy
import ramble.graphs
import ramble.keywords
import ramble.mirror
import ramble.repeats
import ramble.repository
import ramble.stage
import ramble.success_criteria
import ramble.util.class_attributes
import ramble.util.colors as rucolor
import ramble.util.env
import ramble.util.executable
import ramble.util.hashing
import ramble.util.lock as lk
import ramble.util.path
import ramble.util.stats
import ramble.variants
from ramble.definitions.variables import CommandVariable
from ramble.error import (
    ApplicationError,
    ChainCycleDetectedError,
    ExecutableNameError,
    FormattedExecutableError,
    InvalidChainError,
    ObjectValidationError,
)
from ramble.experiment_result import ExperimentResult, ExperimentStatus
from ramble.language.application_language import ApplicationMeta
from ramble.language.shared_language import (
    SharedMeta,
    archive_pattern,
    register_builtin,
    register_phase,
    variant,
)
from ramble.util import cleaner, conversions, json_util
from ramble.util.foms import FomType, SummaryFoms, get_literal_from_regex
from ramble.util.format import when_order
from ramble.util.logger import logger
from ramble.util.naming import NS_SEPARATOR
from ramble.util.output_capture import output_mapper
from ramble.util.shell_utils import source_str
from ramble.workspace import LICENSE_INC_NAME, TEMPLATE_EXTENSION, namespace

import spack.util.compression
import spack.util.environment
import spack.util.executable

ObjectMixin = ramble.repository.get_base_class("object-mixin")

_NULL_CONTEXT = "null"

_DEFAULT_CONTENT_PERM = (
    stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH
)


def _get_context_display_name(context):
    return (
        f"default ({_NULL_CONTEXT}) context"
        if context == _NULL_CONTEXT
        else f"{context} context"
    )


def _check_shell_support(app_inst):
    def _check_match(inst, shell_to_support):
        pat = getattr(inst, "shell_support_pattern", None)
        matched = pat is None or fnmatch.fnmatch(shell_to_support, pat)
        if not matched:
            logger.die(
                f"{inst.name} does not support {shell_to_support} shell"
                f", the supported shell pattern is '{pat}'"
            )

    shell = ramble.config.get("config:shell")
    _check_match(app_inst, shell)
    for mod_inst in app_inst._modifier_instances:
        _check_match(mod_inst, shell)
    _check_match(app_inst.package_manager, shell)


def _run_phase_hook(obj, workspace, pipeline, hook):
    """Helper to enable an object run phase hooks defined in application"""
    phase_defs = obj.phase_definitions
    if pipeline in phase_defs and hook in phase_defs[pipeline]:
        return

    hook_func_name = f"_{hook}"
    if hasattr(obj, hook_func_name):
        phase_func = _get_phase_func_wrapper(
            workspace, getattr(obj, hook_func_name), hook
        )
        phase_func(workspace)


def _get_phase_func_wrapper(workspace, phase_func, phase_name):
    if workspace.profile_config is None:
        return phase_func
    profiler, profile_phases = workspace.profile_config
    if phase_name not in profile_phases:
        return phase_func

    # In addition to the phase function, also instrument methods of all associated objects.
    import inspect

    obj = getattr(phase_func, "__self__", None)
    if obj:
        objects_to_register = [obj]
        if getattr(obj, "origin_type", None) == "application" and hasattr(
            obj, "objects"
        ):
            for _, assoc_obj in obj.objects(yield_all=False):
                if assoc_obj and assoc_obj not in objects_to_register:
                    objects_to_register.append(assoc_obj)

        for target_obj in objects_to_register:
            for _, member in inspect.getmembers(
                target_obj, predicate=inspect.ismethod
            ):
                func_to_profile = getattr(member, "__func__", member)
                if inspect.isfunction(func_to_profile):
                    profiler.add_function(func_to_profile)

    return profiler(phase_func)


class ApplicationBase(ObjectMixin, metaclass=ApplicationMeta):
    _mro_obj_type_cache = {}
    name = "application-base"
    origin_type = "application"
    _builtin_name = NS_SEPARATOR.join(("builtin", "{name}"))
    _builtin_required_key = "required"
    _inventory_file_name = "ramble_inventory.json"
    _status_file_name = "ramble_status.json"
    pipelines = [
        "analyze",
        "archive",
        "bootstrap",
        "mirror",
        "setup",
        "pushdeployment",
        "pushtocache",
        "execute",
        "logs",
    ]
    _language_classes = [ApplicationMeta, SharedMeta]

    variant(
        "inject_modifiers_from_directives",
        default=True,
        description="Whether to include automatically injected modifiers",
    )

    license_names: List[str] = []

    archive_pattern("{experiment_run_dir}/" + ExperimentResult.cache_file_name)

    mpi_definitions = {
        ramble.keywords.keywords.n_ranks: "int({processes_per_node}*{n_nodes})",
        ramble.keywords.keywords.processes_per_node: "int({n_ranks}/{n_nodes})",
        ramble.keywords.keywords.n_nodes: "int({n_ranks}/{processes_per_node})",
    }

    def __init__(self, file_path):
        super().__init__()

        ramble.util.class_attributes.convert_class_attributes(self)

        self.object_variants = ramble.variants.VariantSet()
        for var_args in self.class_variants.values():
            self.object_variants.default_variant(**var_args)

        self.keywords = ramble.keywords.keywords.copy()
        self.object_variants.default_variant(
            name=self.keywords.is_repeat_parent,
            default=False,
            description="Whether this is the parent of a set of repeats or not",
        )
        self.object_variants.default_variant(
            name=self.keywords.is_repeat_child,
            default=False,
            description="Whether this is a child in a set of repeats or not",
        )
        self.object_variants.default_variant(
            name=self.keywords.repeat_index,
            default=0,
            description="Index of this experiment, in repeat space",
        )
        self.object_variants.default_variant(
            name=namespace.containerized,
            default=False,
            description="Whether this experiment is run inside a container",
        )

        self._vars_are_expanded = False
        self.expander = None
        self._formatted_executables = {}
        self.variables = None
        self.variants = None
        self._active_workload = None
        self.no_expand_vars = None
        self.experiment_set = None
        self.workspace = None
        self.internals = {}
        self.is_template = False
        self.has_generated_experiments = False
        self.repeats = ramble.repeats.Repeats()
        self._command_list = []
        self._command_list_without_logs = []
        self._missing_command_variables = {}
        self.missing_mpi_variables = set()
        self.chained_experiments = None
        self.chain_order = []
        self.chain_prepend = []
        self.chain_append = []
        self.chain_commands = {}
        self._env_variable_sets = []
        self.modifiers = []
        self.experiment_tags = []
        self._modifier_instances = []
        self._input_fetchers = None
        self.result = None
        self._phase_times = {}
        self._pipeline_graphs = None
        self.package_manager = None
        self.custom_executables = {}
        self.success_list = None
        self._exp_lock = None
        self._input_lock = None
        self._software_lock = None
        # A dict storing fom values, currently it only stores inmem FOMs
        self._fom_map = {}
        self._template_paths_defined = False

        # Ensure we always have the application name, and this is never empty
        self._file_path = file_path

        self.license_names = self.license_names + [self.name]

        self.hash_inventory = {
            "attributes": [],
            "inputs": [],
            "software": [],
            "templates": [],
            "package_manager": [],
            "modifier_artifacts": [],
        }
        self.experiment_hash = None

        self.application_class = "ApplicationBase"

        self.license_path = ""
        self.license_file = ""

        self.workflow_manager = None
        self.system = None
        self.platform = None

        self.result = ExperimentResult(self)

    @property
    def experiment_lock(self):
        """Create a lock for the experiment directory, and return it"""
        lock_path = os.path.join(
            self.expander.expand_var("{experiment_run_dir}"),
            ".ramble-experiment",
        )
        return lk.Lock(lock_path)

    @property
    def modifier_instances(self):
        """Return the modifier instances for this application"""
        return self._modifier_instances

    def clone(self):
        """Deep clone an application instance"""
        new_clone = type(self)(self._file_path)
        self.has_generated_experiments = True

        if self.known_versions:
            new_clone.known_versions = self.known_versions.copy()
        clone_variables = {} if not self.variables else self.variables
        clone_variants = {} if not self.variants else self.variants
        new_clone.set_variables_and_variants(
            clone_variables,
            clone_variants,
            self.workspace,
            self.experiment_set,
        )
        if self._env_variable_sets:
            new_clone.set_env_variable_sets(self._env_variable_sets.copy())
        if self.internals:
            new_clone.set_internals(self.internals.copy())
        if self._formatted_executables:
            new_clone.set_formatted_executables(
                self._formatted_executables.copy()
            )

        new_clone.workloads = copy.deepcopy(self.workloads)
        new_clone.inputs = copy.deepcopy(self.inputs)
        new_clone.custom_executables = self.custom_executables.copy()
        new_clone.keywords = ramble.keywords.keywords.copy()
        new_clone.set_template(False)
        new_clone.repeats.set_repeats(False, 0)
        new_clone.set_chained_experiments(None)
        new_clone.set_required_variables()

        return new_clone

    @property
    def is_actionable(self):
        """Determine if an experiment should be actioned in pipelines

        Returns True if the experiment should be actioned in a pipeline, False
        if not.
        """

        if self.is_template:
            return False

        return True

    def _validate_workload(self, workload_name):
        """Checks if a workload name is valid and returns the workload that
        satisfies `when` conditions.
        """
        self._define_custom_workloads()
        workload = None
        workload_found = False
        for when_set, workloads in self.workloads.items():
            if workload_name in workloads:
                workload_found = True
                if not self.expander:
                    workload = workloads[workload_name]
                elif self.expander.satisfies(
                    when_set, self.experiment_variants()
                ):
                    if workload:
                        logger.die(
                            f"Workload {workload_name} is defined with "
                            "overlapping `when` conditions. Ensure that "
                            "conditions are mutually exclusive."
                        )
                    workload = workloads[workload_name]

        if not workload_found:
            raise ApplicationError(
                f"Workload {workload_name} is not defined "
                f"as a workload of application {self.name}."
            )
        if not workload:
            raise ramble.expander.WorkloadNotDefinedError(
                f"Workload {workload_name} is not defined "
                "for the active `when` conditions."
            )

        return workload

    def set_active_workload(self):
        """Retrieves the current workload name from the expander, evaluates
        `when` conditions, and sets the active workload to the one that matches
        conditions.
        """
        self._active_workload = self._validate_workload(
            self.expander.workload_name
        )

    def get_workload(self, workload_name=None):
        """Retrieves a workload that satisfies current `when` conditions. If
        workload_name is not provided, retrieves the active workload.
        """
        if not workload_name or (
            self.expander
            and self.expander.workload_name
            and self.expander.workload_name == workload_name
        ):
            if not self._active_workload:
                self.set_active_workload()
            return self._active_workload
        else:
            return self._validate_workload(workload_name)

    def get_workloads(self, workload_name=None):
        """Retrieves all workloads with workload_name, ignoring `when`
        conditions. If workload_name is not provided, retrieves all workloads
        with the same name as the active workload.

        Use this instead of get_workload() if calling before variants are set,
        e.g. in set_variables()
        """
        self._define_custom_workloads()
        if not workload_name:
            workload_name = self.expander.workload_name

        found_workload = False
        for workloads in self.workloads.values():
            if workload_name in workloads:
                found_workload = True
                yield workloads[workload_name]

        if not found_workload:
            raise ApplicationError(
                f"Workload {workload_name} is not defined "
                f"as a workload of application {self.name}."
            )

    def get_all_workloads(self):
        """Retrieves all workloads satisfying current `when` conditions."""
        self._define_custom_workloads()
        all_workloads_names = set()
        found = False
        for when_set, workloads in self.workloads.items():
            if self.expander.satisfies(when_set, self.experiment_variants()):
                for workload_name, workload in workloads.items():
                    if workload_name in all_workloads_names:
                        logger.die(
                            f"Workload {workload_name} is defined with "
                            "overlapping `when` conditions. Ensure that "
                            "conditions are mutually exclusive."
                        )
                    all_workloads_names.add(workload_name)
                    yield workload
                    found = True

        if not found:
            sorted_variants = sorted(
                self.experiment_variants().as_set(for_output=True),
                key=when_order,
            )
            logger.die(
                "No workloads satisfy the current `when` conditions: \n"
                f"  {sorted_variants}"
            )

    def _set_package_manager(self):
        pkgman = conversions.canonical_none(
            self.expander.expand_var(
                self.experiment_variants().value(namespace.package_manager)
            )
        )

        if pkgman is not None:
            pkgman_name, _, maybe_pkgman_ver = pkgman.partition("@")

            try:
                pkgman_type = ramble.repository.ObjectTypes.package_managers
                self.package_manager = ramble.repository.get(
                    pkgman_name, pkgman_type
                ).copy()
                self.package_manager.set_application(self)

                if maybe_pkgman_ver:
                    self.package_manager.set_version(
                        version_number=maybe_pkgman_ver,
                        description=f"{pkgman_name} {maybe_pkgman_ver}",
                    )
            except ramble.repository.UnknownObjectError:
                logger.die(
                    f"{pkgman_name} is not a valid package manager. "
                    "Valid package managers can be listed via:\n"
                    "\tramble list --type package_managers"
                )

        if self.package_manager is not None:
            for pkgname, config in self.required_packages.items():
                if self.expander.satisfies(
                    config["when"],
                    variant_set=self.experiment_variants(),
                ):
                    self.keywords.update_keys(
                        {
                            f"{pkgname}_path": {
                                "type": ramble.keywords.key_type.reserved,
                                "level": ramble.keywords.output_level.variable,
                            }
                        }
                    )

    def _set_system(self):
        sys_var = conversions.canonical_none(
            self.experiment_variants().value(namespace.system)
        )

        if sys_var is None:
            sys_var = "user-managed"

        if sys_var is not None:
            sys_name, _, maybe_sys_ver = sys_var.partition("@")

            try:
                sys_type = ramble.repository.ObjectTypes.systems
                self.system = ramble.repository.get(sys_name, sys_type).copy()
                self.system.set_application(self)
                if maybe_sys_ver:
                    self.system.set_version(
                        version_number=maybe_sys_ver,
                        description=f"{sys_name} {maybe_sys_ver}",
                    )
            except ramble.repository.UnknownObjectError:
                logger.die(
                    f"{sys_name} is not a valid system. "
                    "Valid systems can be listed via:\n"
                    "\tramble list --type systems"
                )

            added_defaults = False
            for var_name in [
                "platform",
                "package_manager",
                "workflow_manager",
            ]:
                if (
                    self.experiment_variants(allow_caching=False).value(
                        var_name
                    )
                    is None
                ):
                    default_value = getattr(
                        self.system, f"system_default_{var_name}", None
                    )
                    if default_value:
                        self.experiment_variants(
                            allow_caching=False
                        ).default_variant(
                            var_name,
                            default=default_value,
                            description=f"{var_name} selection variant",
                        )
                        added_defaults = True
            if added_defaults:
                self.clear_variant_cache()

    def _set_platform(self):
        plat_var = conversions.canonical_none(
            self.expander.expand_var(
                self.experiment_variants().value(namespace.platform)
            )
        )

        if plat_var is None:
            plat_var = self.system.system_default_platform

        if plat_var is None:
            plat_var = "user-managed"

        if plat_var is not None:
            plat_name, _, maybe_plat_ver = plat_var.partition("@")

            if self.system and self.system.system_available_platforms:
                if plat_name not in self.system.system_available_platforms:
                    logger.die(
                        f"Platform {plat_name} is not available in system {self.system.name}. "
                        f"Available platforms are: {', '.join(self.system.system_available_platforms)}"
                    )

            try:
                plat_type = ramble.repository.ObjectTypes.platforms
                self.platform = ramble.repository.get(
                    plat_name, plat_type
                ).copy()
                self.platform.set_application(self)
                if maybe_plat_ver:
                    self.platform.set_version(
                        version_number=maybe_plat_ver,
                        description=f"{plat_name} {maybe_plat_ver}",
                    )
            except ramble.repository.UnknownObjectError:
                logger.die(
                    f"{plat_name} is not a valid platform. "
                    "Valid platforms can be listed via:\n"
                    "\tramble list --type platforms"
                )

    def _apply_system_and_platform_variables(self):
        """Apply variables from system and platform objects"""

        if self.system:
            # Apply platform_variable_maps
            plat_name = conversions.canonical_none(
                self.experiment_variants().value(namespace.platform)
            )

            if plat_name:
                for (
                    var_name,
                    var_map,
                ) in self.system.platform_variable_maps.items():
                    if plat_name in var_map:
                        if var_name not in self.variables:
                            self.define_variable(var_name, var_map[plat_name])

            # Apply variable_defaults
            for when_key, var_defs in self.system.variable_defaults.items():
                if self.system.satisfy_when(when_key):
                    for var_name, var_val in var_defs.items():
                        if var_name not in self.variables:
                            self.define_variable(var_name, var_val)

    def _set_workflow_manager(self):
        workflow = conversions.canonical_none(
            self.expander.expand_var(
                self.experiment_variants().value(namespace.workflow_manager)
            )
        )

        workflow_name = ""
        # Map None to the default of user-managed
        if workflow is None:
            workflow = "user-managed"

        try:
            workflow_name, _, maybe_workflow_ver = workflow.partition("@")

            wfman_type = ramble.repository.ObjectTypes.workflow_managers
            self.workflow_manager = ramble.repository.get(
                workflow_name, wfman_type
            ).copy()
            self.workflow_manager.set_application(self)
            if maybe_workflow_ver:
                self.workflow_manager.set_version(
                    version_number=maybe_workflow_ver,
                    description=f"{workflow_name} {maybe_workflow_ver}",
                )
        except ramble.repository.UnknownObjectError:
            logger.die(
                f"{workflow_name} is not a valid workflow manager. "
                "Valid workflow managers can be listed via:\n"
                "\tramble list --type workflow_managers"
            )

    def set_success_list(self, success_criteria):
        self.success_list = ramble.success_criteria.ScopedCriteriaList()

        if success_criteria:
            for conf in success_criteria:
                self.success_list.add_criteria("experiment", **conf)

    def build_phase_order(self):
        if self._pipeline_graphs is not None:
            return

        self._pipeline_graphs = {}
        for pipeline in self.pipelines:
            if pipeline not in self.phase_definitions:
                self.phase_definitions[pipeline] = {}

            self._pipeline_graphs[pipeline] = ramble.graphs.PhaseGraph(
                self.phase_definitions[pipeline], self
            )

            for mod_inst in self._modifier_instances:
                # Define phase nodes
                for _, phase_node in mod_inst.all_pipeline_phases(pipeline):
                    self._pipeline_graphs[pipeline].add_node(
                        phase_node, obj_inst=mod_inst
                    )

                # Define phase edges
                for _, phase_node in mod_inst.all_pipeline_phases(pipeline):
                    self._pipeline_graphs[pipeline].define_edges(
                        phase_node, internal_order=True
                    )

            if self.package_manager:
                # Define phase nodes
                for _, phase_node in self.package_manager.all_pipeline_phases(
                    pipeline
                ):
                    self._pipeline_graphs[pipeline].add_node(
                        phase_node, obj_inst=self.package_manager
                    )

                # Define phase edges
                for _, phase_node in self.package_manager.all_pipeline_phases(
                    pipeline
                ):
                    self._pipeline_graphs[pipeline].define_edges(
                        phase_node, internal_order=True
                    )

    def set_env_variable_sets(self, env_variable_sets):
        """Set internal reference to application environment variable sets"""

        self._env_variable_sets = env_variable_sets.copy()

    def set_variables_and_variants(
        self, variables, variants, workspace, experiment_set
    ):
        """Set internal reference to variables and variants

        Also, create an application specific expander class.

        Args:
            variables (dict): Dictionary of variable definitions for this
                             experiment.
            variants (dict): Dictionary of variant controls for this
                             experiment.
            workspace: Reference to workspace object
            experiment_set: Reference to experiment set, for expanding
                            referenced variables.
        """

        self.variables = variables.copy()
        self.variants = variants.copy()
        self.experiment_set = experiment_set
        self.workspace = workspace
        self.expander = ramble.expander.Expander(
            self.variables, self.experiment_set
        )

        # Set application version or use preferred version if none specified
        _, _, maybe_version = self.expander.application_spec.partition("@")

        if maybe_version:
            super().set_version(
                version_number=maybe_version,
                description=self.expander.application_spec,
            )
        elif hasattr(self, "preferred_version"):
            super().set_version(
                version=self.preferred_version,
                description=self.expander.application_spec,
            )

        # Define variants from repeats
        added_variants = False
        for keyword in [
            self.keywords.is_repeat_parent,
            self.keywords.is_repeat_child,
            self.keywords.repeat_index,
        ]:
            if keyword in variables:
                self.object_variants.experiment_variant(
                    keyword,
                    self.expander.expand_var(variables[keyword], typed=True),
                )
                added_variants = True

        # Define experiment variants
        if variants:
            for name, value in variants.items():
                expanded_value = self.expander.expand_var(value, typed=True)
                self.object_variants.experiment_variant(name, expanded_value)
                added_variants = True

        if added_variants:
            self.clear_variant_cache()

        # Set up remaining variants
        self._set_system()

        # Apply defaults from system and platform
        if self.system:
            added_defaults = False
            if (
                self.system.default_platform
                and namespace.platform not in self.variants
            ):
                self.object_variants.experiment_variant(
                    namespace.platform, self.system.system_default_platform
                )
                added_defaults = True

            if (
                self.system.default_package_manager
                and namespace.package_manager not in self.variants
            ):
                self.object_variants.experiment_variant(
                    namespace.package_manager,
                    self.system.system_default_package_manager,
                )
                added_defaults = True

            if (
                self.system.default_workflow_manager
                and namespace.workflow_manager not in self.variants
            ):
                self.object_variants.experiment_variant(
                    namespace.workflow_manager,
                    self.system.system_default_workflow_manager,
                )
                added_defaults = True

            if added_defaults:
                self.clear_variant_cache()

        self._set_platform()
        self._set_package_manager()
        self._set_workflow_manager()

        self._apply_system_and_platform_variables()

        for _, obj in self.objects():
            self.keywords.update_keys(obj.required_variables)

        base_chain = self.__class__.__mro__
        for cls in base_chain:
            if hasattr(cls, "name") and cls.name is not None:
                self.object_variants.multi_value_variant(
                    "application_name",
                    value=self.expander.application_name,
                )

        # Define workload_name variant as early as possible
        self.object_variants.default_variant(
            "workload_name",
            default=self.expander.workload_name,
            description="Name of experiment workload",
        )

        if hasattr(self, "workload_groups") and self.workload_groups:
            for group_name, group_inst in self.workload_groups.items():
                for (
                    wl_group_when_set,
                    workload_group_list,
                ) in group_inst.workloads.items():
                    if (not wl_group_when_set) or self.expander.satisfies(
                        wl_group_when_set, self.experiment_variants()
                    ):
                        if self.expander.workload_name in workload_group_list:
                            self.object_variants.multi_value_variant(
                                self.keywords.workload_group,
                                value=group_name,
                            )

        self.clear_variant_cache()

        self.no_expand_vars = set()
        workloads = self.get_workloads()

        for workload in workloads:
            for var_when_set, var_list in workload.variables.items():
                if self.expander.satisfies(
                    var_when_set, self.experiment_variants()
                ):
                    for var in var_list:
                        if not var.expandable:
                            self.no_expand_vars.add(var.name)

        self.define_missing_variables()

        self.expander.set_no_expand_vars(self.no_expand_vars)
        if experiment_set and experiment_set._workspace:
            self.expander.replacement_paths = (
                experiment_set._workspace.workspace_paths()
            )

        self._define_custom_executables()

    def non_reserved_variables(
        self, remove_keys: set = None
    ) -> Dict[str, str]:
        """Replicate this instances variables, and remove any reserved variables from the dict.
        Additionally, remove any variables in the remove_keys set.

        Args:
            remove_keys (set): Set of keys to remove from variable definitions

        Returns:
            (dict): A dictionary of variable, value pairs from this experiment.
        """
        workspace = self.workspace
        if remove_keys is None:
            remove_keys = {"env_name", "workspace_tables"}
        cleaned_variables = self.variables.copy()

        for var in list(cleaned_variables):
            if self.keywords.is_reserved(var):
                cleaned_variables.pop(var)

        for key in remove_keys:
            cleaned_variables.pop(key, None)

        for template_name, _ in workspace.all_templates():
            cleaned_variables.pop(template_name, None)

        for _, tpl_configs in self._object_templates():
            for tpl_config in tpl_configs:
                cleaned_variables.pop(tpl_config["var_name"], None)

        return cleaned_variables

    def register_missing_command_variable(self, var):
        """Register a missing command variable, so we can report it later in
        the correct log file.

        Args:
            var: Instance of a CommandVariable
        """
        self._missing_command_variables[var.name] = var

    def define_missing_variables(self):
        """Iterate over missing variable definitions, and add them until there
        are no more to add."""
        workspace = self.workspace

        # Track which precedence level defined each variable.
        # -1: YAML (highest)
        # 0-N: Objects in self.objects() order
        # N+1: Application (lowest)
        original_variables = self.variables.copy()
        var_precedence = dict.fromkeys(original_variables, -1)

        # Map objects to their precedence order
        obj_precedence = {}
        for i, (_, obj) in enumerate(self.objects()):
            obj_precedence[obj] = i

        default_value_precedence = len(obj_precedence)

        # Process the application variables that are missing
        for var, val in self.selected_variables.items():
            if var not in self.variables:
                self.define_variable(var, val.default)
                var_precedence[var] = default_value_precedence

        # Define object version and variant variables
        # Also, extract a merged set of when_keys from objects that are not
        # applications.
        # Also, define object version variables
        object_when_map = {"object_variables": {}, "command_variables": {}}
        for obj_type, obj in self.objects():
            prec = obj_precedence[obj]
            # TODO: Remove the {origin_type}_version variable when we can
            self.define_variable(
                f"{obj.origin_type}_version", str(obj.selected_version)
            )
            var_precedence[f"{obj.origin_type}_version"] = prec
            self.define_variable(
                f"{obj.origin_type}::{obj.name}::version",
                str(obj.selected_version),
            )
            var_precedence[f"{obj.origin_type}::{obj.name}::version"] = prec

            # Define variant variables for Spack-like syntax expansion
            for (
                name,
                var_val,
            ) in obj.object_variants.experiment_variants.items():
                self.define_variable(
                    f"{obj.origin_type}::variant::{name}",
                    var_val.as_definition(),
                )
                var_precedence[f"{obj.origin_type}::variant::{name}"] = prec

            for name, _var_val in obj.object_variants.default_variants.items():
                if name not in obj.object_variants.experiment_variants:
                    self.define_variable(
                        f"{obj.origin_type}::variant::{name}",
                        _var_val.as_definition(),
                    )
                    var_precedence[f"{obj.origin_type}::variant::{name}"] = (
                        prec
                    )

            if obj_type != ramble.repository.ObjectTypes.applications:
                # variable_sets = [obj.object_variables, obj.command_variables]
                for variable_set_attr, when_map in object_when_map.items():
                    when_map[obj] = []
                    variable_set = getattr(obj, variable_set_attr, {})
                    for when_key, var_list in variable_set.items():
                        keep = False
                        for var in var_list:
                            if var.name not in original_variables:
                                keep = True

                        if keep:
                            when_map[obj].append(when_key)

                    if not when_map[obj]:
                        when_map.pop(obj, None)

        # Process any missing variables from other objects
        # Handle object_variables before handling command_variables
        for variable_set_attr, when_map in object_when_map.items():
            while True:
                to_define = {}
                changed_definitions = False

                for obj, when_keys in when_map.items():
                    to_remove = set()
                    obj_prec = obj_precedence[obj]
                    for when_idx, when_key in enumerate(reversed(when_keys)):
                        if obj.satisfy_when(when_key):
                            to_remove.add(when_key)
                            variable_dict = getattr(obj, variable_set_attr, {})
                            if when_key in variable_dict:
                                for var in reversed(variable_dict[when_key]):
                                    if var.name not in original_variables:
                                        # Use a tuple for precedence: (obj_prec, when_idx)
                                        # Lower tuple means higher precedence.
                                        current_prec = (obj_prec, when_idx)
                                        best_prec = var_precedence.get(
                                            var.name, (999, 999)
                                        )

                                        # Convert existing scalar precedence to tuple if necessary
                                        if not isinstance(best_prec, tuple):
                                            best_prec = (best_prec, 999)

                                        if (
                                            var.name not in to_define
                                            and current_prec < best_prec
                                        ):
                                            if isinstance(
                                                var, CommandVariable
                                            ):
                                                to_define[var.name] = (
                                                    var.extract_value(
                                                        workspace, self
                                                    )
                                                )
                                            else:
                                                to_define[var.name] = (
                                                    var.default
                                                )

                                            var_precedence[var.name] = (
                                                current_prec
                                            )
                                            changed_definitions = True

                    # Remove any satisfied when_keys, as we won't need to check
                    # them (since their variables have already been defined).
                    for when_key in to_remove:
                        when_keys.remove(when_key)

                if not changed_definitions:
                    break

                for var, val in to_define.items():
                    self.define_variable(var, val)

    def set_internals(self, internals):
        """Set internal reference to application internals"""

        self.internals = internals
        self._define_custom_inputs()
        self._define_custom_workloads()
        if self.expander:
            self._define_custom_executables()

    def set_template(self, is_template):
        """Set if this instance is a template or not"""
        self.is_template = is_template

    def set_chained_experiments(self, chained_experiments):
        """Set chained experiments for this instance"""
        self.chained_experiments = None
        if chained_experiments:
            self.chained_experiments = chained_experiments.copy()

    def set_modifiers(self, modifiers):
        """Set modifiers for this instance"""
        if modifiers:
            self.modifiers = modifiers.copy()
        self.build_modifier_instances()

    def set_tags(self, tags):
        """Set experiment tags for this instance"""

        self.experiment_tags = self.tags.copy()

        self.experiment_tags.extend(self.get_workload().tags)

        if tags:
            self.experiment_tags.extend(tags)

    def set_formatted_executables(self, formatted_executables):
        """Set formatted executables for this instance"""
        self._formatted_executables = formatted_executables.copy()

    def has_tags(self, tags):
        """Check if this instance has provided tags.

        Args:
            tags (list): List of strings, where each string is an individual tag
        Returns:
            (bool): True if all tags are in this instance, False otherwise
        """

        if tags and self.experiment_tags:
            tag_set = set(tags)
            exp_tag_set = set(self.experiment_tags)

            for tag in tag_set:
                if tag not in exp_tag_set:
                    return False
            return True

        return False

    def experiment_log_file(self, logs_dir):
        """Returns an experiment log file path for the given logs directory"""
        return (
            os.path.join(logs_dir, self.expander.experiment_namespace) + ".out"
        )

    def get_pipeline_phases(self, pipeline, phase_filters=None):
        if phase_filters is None:
            phase_filters = ["*"]

        self.build_modifier_instances()
        self.build_phase_order()

        if pipeline not in self.pipelines:
            logger.die(
                f"Requested pipeline {pipeline} is not valid.\n",
                f"\tAvailable pipelinese are {self.pipelines}",
            )

        if pipeline not in self._pipeline_graphs:
            return

        ordered_phases = list(self._pipeline_graphs[pipeline].walk())

        selected_phases = set()
        last_match_idx = -1

        for i, phase in enumerate(ordered_phases):
            if self.expander.satisfies(
                phase.when, variant_set=self.experiment_variants()
            ) and any(fnmatch.fnmatch(phase.key, pf) for pf in phase_filters):
                selected_phases.add(phase)
                last_match_idx = i

        final_phases = selected_phases
        include_phase_deps = ramble.config.get(
            "config:include_phase_dependencies"
        )
        if include_phase_deps and last_match_idx > -1:
            dependencies = ordered_phases[:last_match_idx]
            final_phases.update(dependencies)

        for phase in ordered_phases:
            if phase in final_phases:
                yield phase.key

    def print_vars(self, header="", vars_to_print=None, indent=""):
        print_vars = vars_to_print
        if not print_vars:
            print_vars = self.variables

        color.cprint(f"{indent}{header}:")
        for var, val in print_vars.items():
            expansion_var = self.expander.expansion_str(var)
            expanded = self.expander.expand_var(expansion_var)
            color.cprint(f"{indent}  {var} = {val} ==> {expanded}")

    def build_used_variables(self):
        """Build a set of all used variables

        By expanding all necessary portions of this experiment (required /
        reserved keywords, templates, commands, etc...), determine which
        variables are used throughout the experiment definition.

        Variables can have list definitions. These are iterated over to ensure
        variables referenced by any of them are tracked properly.

        Returns:
            (set): All variable names used by this experiment.
        """
        workspace = self.workspace
        self.build_modifier_instances()
        self.define_variables_for_template_path()

        backup_variables = self.variables.copy()

        self._define_commands(success_list=self.success_list)
        self._define_formatted_executables()

        ########################
        # Define extra variables
        ########################
        self.define_missing_variables()

        ##########################################
        # Expand used variables to track all usage
        ##########################################

        # Add all known keywords
        for key in self.keywords.keys:
            self.expander.expand_var_name(key)

        if self.chained_experiments:
            for chained_exp in self.chained_experiments:
                if namespace.inherit_variables in chained_exp:
                    for var in chained_exp[namespace.inherit_variables]:
                        self.expander._used_variables.add(var)
                        self.expander.expand_var_name(var)

        # Add variables from success criteria
        criteria_list = self.success_list
        for criteria, _ in criteria_list.all_criteria():
            if criteria.mode == "fom_comparison":
                self.expander.expand_var(criteria.fom_formula)
                self.expander.expand_var(criteria.fom_name)
                self.expander.expand_var(criteria.fom_context)
            elif criteria.mode == "application_function":
                self.evaluate_success()

        if self.package_manager is not None:
            self.package_manager.build_used_variables()

        for template_name, template_conf in workspace.all_templates():
            self.expander._used_variables.add(template_name)
            self.expander.expand_var(template_conf["contents"])

        ############################
        # Reset variable definitions
        ############################
        to_remove = set()
        for var in self.variables:
            if var not in backup_variables:
                to_remove.add(var)

        for var in to_remove:
            del self.variables[var]

        for var, val in backup_variables.items():
            self.variables[var] = val

        self._command_list = []

        return self.expander._used_variables

    def print_internals(self, indent=""):
        if not self.internals:
            return

        if namespace.custom_executables in self.internals:
            header = rucolor.nested_4("Custom Executables")
            color.cprint(f"{indent}{header}:")

            for name in self.internals[namespace.custom_executables]:
                color.cprint(f"{indent}  {name}")

        if namespace.executables in self.internals:
            header = rucolor.nested_4("Executable Order")
            color.cprint(
                f"{indent}{header}: {str(self.internals[namespace.executables])}"
            )

        if namespace.executable_injection in self.internals:
            header = rucolor.nested_4("Executable Injection")
            color.cprint(
                f"{indent}{header}: {str(self.internals[namespace.executable_injection])}"
            )

        if namespace.custom_inputs in self.internals:
            header = rucolor.nested_4("Custom Inputs")
            color.cprint(f"{indent}{header}:")

            for name in self.internals[namespace.custom_inputs]:
                color.cprint(f"{indent}  {name}")

        if namespace.custom_workloads in self.internals:
            header = rucolor.nested_4("Custom Workloads")
            color.cprint(f"{indent}{header}:")

            for name in self.internals[namespace.custom_workloads]:
                color.cprint(f"{indent}  {name}")

    def print_chain_order(self, indent=""):
        if not self.chain_order:
            return

        header = rucolor.nested_4("Experiment Chain")
        color.cprint(f"{indent}{header}:")
        for exp in self.chain_order:
            color.cprint(f"{indent}- {exp}")

    # Phase execution helpers
    def run_phase(self, pipeline, phase):
        """Run a phase, by getting its function pointer"""
        workspace = self.workspace
        if self.is_template:
            logger.debug(f"{self.name} is a template. Skipping phases")
            return
        if self.repeats.is_repeat_base:
            logger.debug(f"{self.name} is a repeat base. Skipping phases")
            return

        phase_node = self._pipeline_graphs[pipeline].get_node(phase)

        if phase_node is None:
            logger.die(f"Phase {phase} is not defined in pipeline {pipeline}")

        logger.msg(f"  Executing phase {phase}")
        start_time = time.time()

        for _, obj in self.objects(
            exclude_types=[ramble.repository.ObjectTypes.applications]
        ):
            _run_phase_hook(obj, workspace, pipeline, phase)
        phase_func = _get_phase_func_wrapper(
            workspace, phase_node.attribute, phase
        )
        phase_func(workspace, app_inst=self)
        self._phase_times[phase] = time.time() - start_time

    def print_phase_times(self, pipeline, phase_filters=None):
        """Print phase execution times by pipeline phase order

        Args:
            pipeline (str): Name of pipeline to print timing information for
            phase_filters (list(str) | None): Filters to limit phases to print
        """
        logger.msg("Phase timing statistics:")
        if phase_filters is None:
            phase_filters = ["*"]
        for phase in self.get_pipeline_phases(
            pipeline, phase_filters=phase_filters
        ):
            # Set default time to 0.0 s, to prevent KeyError from skipped phases
            if phase not in self._phase_times:
                self._phase_times[phase] = 0.0
            logger.msg(
                f"  {phase} time: {round(self._phase_times[phase], 5)} (s)"
            )

    def create_experiment_chain(self):
        """Create the necessary chained experiments for this instance

        This method determines which experiments need to be chained, grabs the
        base instance from the experiment set, creates a copy of it (with a
        unique name), injects the copy back into the experiment set,
        and builds an internal mapping from unique name to the chaining definition.
        """
        if not self.chained_experiments or self.is_template:
            return

        # Build initial stack. Uses a reversal of the current instance's
        # chained experiments
        parent_namespace = self.expander.experiment_namespace
        classes_in_stack = {self}
        chain_idx = 0
        chain_stack = []
        for exp in reversed(self.chained_experiments):
            for exp_name in self.experiment_set.search_primary_experiments(
                exp["name"]
            ):
                child_inst = self.experiment_set.get_experiment(exp_name)

                if child_inst in classes_in_stack:
                    raise ChainCycleDetectedError(
                        "Cycle detected in experiment chain:\n"
                        + f"    Primary experiment {parent_namespace}\n"
                        + f"    Chained expeirment name: {exp_name}\n"
                        + f"    Chain definition: {str(exp)}"
                    )
                chain_stack.append((exp_name, exp.copy()))

        parent_run_dir = self.expander.expand_var(
            self.expander.expansion_str(self.keywords.experiment_run_dir)
        )

        # Continue until the stack is empty
        while len(chain_stack) > 0:
            cur_exp_name = chain_stack[-1][0]
            cur_exp_def = chain_stack[-1][1]

            # Perform basic validation on the chained experiment definition
            if "name" not in cur_exp_def:
                raise InvalidChainError(
                    "Invalid experiment chain defined:\n"
                    + f"    Primary experiment {parent_namespace}\n"
                    + f"    Chain definition: {str(exp)}\n"
                    + '    "name" keyword must be defined'
                )

            if "order" in cur_exp_def:
                possible_orders = [
                    "after_chain",
                    "after_root",
                    "before_chain",
                    "before_root",
                ]
                if cur_exp_def["order"] not in possible_orders:
                    raise InvalidChainError(
                        "Invalid experiment chain defined:\n"
                        + f"    Primary experiment {parent_namespace}\n"
                        + f"    Chain definition: {str(exp)}\n"
                        + '    Optional keyword "order" must '
                        + f"be one of {str(possible_orders)}\n"
                    )

            if "command" not in cur_exp_def:
                raise InvalidChainError(
                    "Invalid experiment chain defined:\n"
                    + f"    Primary experiment {parent_namespace}\n"
                    + f"    Chain definition: {str(exp)}\n"
                    + '    "command" keyword must be defined'
                )

            if "variables" in cur_exp_def:
                if not isinstance(cur_exp_def["variables"], dict):
                    raise InvalidChainError(
                        "Invalid experiment chain defined:\n"
                        + f"    Primary experiment {parent_namespace}\n"
                        + f"    Chain definition: {str(exp)}\n"
                        + '    Optional keyword "variables" '
                        + "must be a dictionary"
                    )

            base_inst = self.experiment_set.get_experiment(cur_exp_name)
            if base_inst in classes_in_stack:
                chain_stack.pop()
                classes_in_stack.remove(base_inst)

                order = "after_root"
                if "order" in cur_exp_def:
                    order = cur_exp_def["order"]

                chained_name = f"chain.{chain_idx}.{cur_exp_name}"
                new_name = f"{parent_namespace}.{chained_name}"

                new_run_dir = os.path.join(
                    parent_run_dir, namespace.chained_experiments, chained_name
                )

                if order == "before_chain":
                    self.chain_prepend.insert(0, new_name)
                elif order == "before_root":
                    self.chain_prepend.append(new_name)
                elif order == "after_root":
                    self.chain_append.insert(0, new_name)
                elif order == "after_chain":
                    self.chain_append.append(new_name)
                self.chain_commands[new_name] = cur_exp_def[namespace.command]

                # Skip editing the new instance if the base_inst doesn't work
                # This happens if the originating command is `workspace info`
                # The printing experiment set doesn't have access to all
                # of the experiment, so the base_inst command above
                # doesn't get an application instance.
                if base_inst:
                    new_inst = base_inst.clone()

                    if namespace.variables in cur_exp_def:
                        for var, val in cur_exp_def[
                            namespace.variables
                        ].items():
                            new_inst.variables[var] = val

                    new_inst.expander._experiment_namespace = new_name
                    new_inst.variables[self.keywords.experiment_run_dir] = (
                        new_run_dir
                    )
                    new_inst.variables[self.keywords.experiment_name] = (
                        new_name
                    )
                    new_inst.variables[self.keywords.experiment_index] = (
                        self.expander.expand_var_name(
                            self.keywords.experiment_index
                        )
                    )
                    new_inst.repeats = self.repeats
                    new_inst.read_status()

                    # Extract inherited variables
                    if namespace.inherit_variables in cur_exp_def:
                        for inherit_var in cur_exp_def[
                            namespace.inherit_variables
                        ]:
                            new_inst.variables[inherit_var] = self.variables[
                                inherit_var
                            ]

                    # Expand the chained experiment vars, so we can build the execution command
                    new_inst.define_variables_for_template_path()
                    chain_cmd = new_inst.expander.expand_var(
                        cur_exp_def[namespace.command]
                    )
                    self.chain_commands[new_name] = chain_cmd
                    cur_exp_def[namespace.command] = chain_cmd
                    self.experiment_set.add_chained_experiment(
                        new_name, new_inst
                    )

                chain_idx += 1
            else:
                # Avoid cycles, from children
                if base_inst in classes_in_stack:
                    chain_stack.pop()
                else:
                    if base_inst.chained_experiments:
                        for exp in reversed(base_inst.chained_experiments):
                            for (
                                exp_name
                            ) in self.experiment_set.search_primary_experiments(
                                exp["name"]
                            ):
                                child_inst = (
                                    self.experiment_set.get_experiment(
                                        exp_name
                                    )
                                )
                                if child_inst in classes_in_stack:
                                    raise ChainCycleDetectedError(
                                        "Cycle detected in "
                                        + "experiment chain:\n"
                                        + "    Primary experiment "
                                        + f"{parent_namespace}\n"
                                        + "    Chained expeirment name: "
                                        + f"{cur_exp_name}\n"
                                        + "    Chain definition: "
                                        + f"{str(cur_exp_def)}"
                                    )

                                chain_stack.append((exp_name, exp))
                    classes_in_stack.add(base_inst)

        # Create the final chain order
        for exp in self.chain_prepend:
            self.chain_order.append(exp)
        self.chain_order.append(self.expander.experiment_namespace)
        for exp in self.chain_append:
            self.chain_order.append(exp)

        # Inject the chain order into the children experiments
        for exp in self.chain_prepend:
            exp_inst = self.experiment_set.get_experiment(exp)
            if exp_inst:
                exp_inst.chain_order = self.chain_order.copy()

        for exp in self.chain_append:
            exp_inst = self.experiment_set.get_experiment(exp)
            if exp_inst:
                exp_inst.chain_order = self.chain_order.copy()

    def define_variable(self, var_name, var_value):
        self.variables[var_name] = var_value
        self.expander._variables[var_name] = var_value
        for mod_inst in self._modifier_instances:
            mod_inst.define_variable(var_name, var_value)

    def build_modifier_instances(self):
        """Built a map of modifier names to modifier instances needed for this
        application instance
        """
        if not self.modifiers:
            self.modifiers = []

        self._modifier_instances = []
        checked_objects = set()

        mod_type = ramble.repository.ObjectTypes.modifiers
        mod_idx = 0

        _existing_mod_base_names = {
            m["name"].partition("@")[0] for m in self.modifiers
        }

        while True:
            # Get the latest variants once per iteration to handle modifiers adding variants
            exp_variants = self.experiment_variants(allow_caching=False)

            # Check global toggle once per iteration
            try:
                var_val = exp_variants.value(
                    "inject_modifiers_from_directives"
                )
                include_mods_global = (
                    (var_val.lower() == "true")
                    if isinstance(var_val, str)
                    else bool(var_val)
                )
            except KeyError:
                include_mods_global = True

            # Gather object_modifiers from all available objects
            for _, obj in self.objects():
                if id(obj) in checked_objects:
                    continue
                checked_objects.add(id(obj))

                if (
                    include_mods_global
                    and hasattr(obj, "object_modifiers")
                    and obj.object_modifiers
                ):
                    for when_key, mod_def_list in obj.object_modifiers.items():
                        if self.expander.satisfies(
                            when_key, variant_set=exp_variants
                        ):
                            for mod_def in mod_def_list:
                                mod_name = mod_def["name"]
                                base_mod_name = mod_name.partition("@")[0]
                                # Add if not already explicitly in self.modifiers
                                if (
                                    base_mod_name
                                    not in _existing_mod_base_names
                                ):
                                    mod_dict = {"name": mod_name}
                                    mod_dict.update(
                                        {
                                            k: v
                                            for k, v in mod_def.items()
                                            if k not in ["name", "when"]
                                        }
                                    )
                                    self.modifiers.append(mod_dict)
                                    _existing_mod_base_names.add(base_mod_name)

            if mod_idx >= len(self.modifiers):
                break

            mod = self.modifiers[mod_idx]
            mod_idx += 1

            mod_name, _, maybe_mod_ver = mod["name"].partition("@")
            mod_inst = ramble.repository.get(mod_name, mod_type).copy()

            if "on_executable" in mod:
                mod_inst.set_on_executables(mod["on_executable"])
            else:
                mod_inst.set_on_executables(None)

            if "mode" in mod:
                mode_name = self.expander.expand_var(mod["mode"])
                mod_inst.set_usage_mode(mode_name)
            else:
                mod_inst.set_usage_mode(None)

            if maybe_mod_ver:
                mod_inst.set_version(
                    version_number=maybe_mod_ver,
                    description=f"{mod_name} {maybe_mod_ver}",
                )

            if not mod_inst.disabled:
                mod_inst.inherit_from_application(self)
                mod_inst.modify_experiment(self)
                mod_inst.set_modifier_variants()
            else:
                base_class_type = ramble.repository.ObjectTypes.base_classes
                DisabledModifier = ramble.repository.get_obj_class(
                    "disabled-modifier", object_type=base_class_type
                )
                mod_inst = DisabledModifier(mod_inst)

            mod_inst.check_conflicts(self._modifier_instances)
            self._modifier_instances.append(mod_inst)

            # Add this modifiers required variables for validation
            self.keywords.update_keys(mod_inst.required_variables)

        for mod_inst in self._modifier_instances:
            # Ensure no expand vars are set correctly for modifiers
            for var in mod_inst.no_expand_vars():
                self.expander.add_no_expand_var(var)
                mod_inst.expander.add_no_expand_var(var)

        # Define any missing modifier variables
        self.define_missing_variables()
        if self.modifiers:
            self.clear_variant_cache()

    @property
    def inventory_file(self):
        experiment_run_dir = self.expander.experiment_run_dir
        return os.path.join(experiment_run_dir, self._inventory_file_name)

    def object_hashes(self, yield_all=True):
        for obj_type, obj in self.objects(yield_all=yield_all):
            yield obj_type, obj, ramble.util.hashing.hash_file(obj._file_path)

    def object_inventory(self):
        workspace = self.workspace
        object_definitions = []
        added_objects = {}
        for obj_type, obj, obj_hash in self.object_hashes():
            if obj_type not in added_objects:
                added_objects[obj_type] = set()

            if obj.name not in added_objects[obj_type]:
                obj_inventory = {
                    "name": obj.name,
                    "object_type": obj_type.name,
                    "type": obj_type.name,
                    "digest": obj_hash,
                }

                if not getattr(obj, "_is_base_class", False) and hasattr(
                    obj, "get_version"
                ):
                    version = obj.get_version(workspace=workspace)
                    obj_inventory["version"] = version
                    obj_inventory["external_version"] = version

                object_definitions.append(obj_inventory)
                added_objects[obj_type].add(obj.name)
        return object_definitions

    def validate_experiment(
        self, warn_validation=True, die_on_validate_error=True
    ):

        mpi_required = self.is_mpi_required(self.expander.workload_name)

        mpi_vars_defined = self.defined_mpi_vars()

        if mpi_required and len(mpi_vars_defined) < 2:
            mpi_keys = (
                "Two or more of the following are required to be defined.\n"
            )
            for var in self.mpi_definitions:
                mpi_keys += f"  - {var}\n"

            defined_keys = (
                f"Experiment {self.expander.experiment_namespace} only has:\n"
            )
            for var in mpi_vars_defined:
                defined_keys += f"  - {var}\n"

            if die_on_validate_error:
                raise ramble.error.ObjectValidationError(
                    "Invalid number of required variables defined.\n"
                    + mpi_keys
                    + defined_keys
                )

        # Validate the new modifiers variables exist
        # (note: the base ramble variables are checked earlier too)
        self.keywords.check_required_keys(
            self.variables,
            warn_validation=warn_validation,
            die_on_validate_error=die_on_validate_error,
        )
        self._check_object_validators(
            warn_validation=warn_validation,
            die_on_validate_error=die_on_validate_error,
        )
        self._check_object_conflicts(
            warn_validation=warn_validation,
            die_on_validate_error=die_on_validate_error,
        )

    def _check_object_validators(
        self, warn_validation=True, die_on_validate_error=True
    ):
        expander = self.expander
        for _, obj in self.objects():
            for when_set, validator_defs in obj.validators.items():
                if not self.expander.satisfies(
                    when_set, variant_set=self.experiment_variants()
                ):
                    continue

                for name, validator in validator_defs.items():
                    try:
                        valid = expander.evaluate_predicate(
                            validator["predicate"]
                        )
                    except ramble.expander.ExpanderError:
                        valid = False
                    if not valid:
                        msg = expander.expand_var(validator["message"])
                        err_msg = (
                            f"Validator '{name}' (defined in '{obj.name}') "
                            f"fails with message: '{msg}'"
                        )
                        if (
                            die_on_validate_error
                            and validator["fail_on_invalid"]
                        ):
                            raise ObjectValidationError(err_msg)
                        elif warn_validation:
                            logger.warn(err_msg)

    def _check_object_conflicts(
        self, warn_validation=True, die_on_validate_error=True
    ):
        expander = self.expander
        for _, obj in self.objects():
            if not hasattr(obj, "conflicts") or not obj.conflicts:
                continue

            for when_set, conflict_list in obj.conflicts.items():
                experiment_variants = obj.experiment_variants()
                try:
                    when_active = expander.satisfies(
                        when_set, variant_set=experiment_variants
                    )
                except ramble.expander.ExpanderError:
                    when_active = False

                if not when_active:
                    continue

                for conflict in conflict_list:
                    conflict_spec = conflict["conflict_spec"]
                    msg = conflict["message"]

                    try:
                        conflict_active = expander.satisfies(
                            conflict_spec, variant_set=experiment_variants
                        )
                    except ramble.expander.ExpanderError:
                        conflict_active = False

                    if not conflict_active:
                        continue

                    # If BOTH are satisfied, it is a conflict!
                    if msg:
                        err_msg = (
                            f"Conflict detected in '{obj.name}': "
                            f"{expander.expand_var(msg)}"
                        )
                    else:
                        when_str = (
                            f" when {', '.join(when_set)}" if when_set else ""
                        )
                        err_msg = (
                            f"Conflict detected in '{obj.name}': "
                            f"'{conflict_spec}' is active{when_str}"
                        )

                    if die_on_validate_error:
                        raise ObjectValidationError(err_msg)
                    elif warn_validation:
                        logger.warn(err_msg)

    def _generate_cleanup_cmd(self, key):
        commands = []
        all_cleanups = {}
        for when_set, named_cleanups in self.cleanups.items():
            if self.expander.satisfies(when_set, self.object_variants):
                all_cleanups.update(named_cleanups)

        for name, cleanup_props in all_cleanups.items():
            if not cleanup_props.get(key):
                continue

            if cleanup_props["directory"]:
                dir = self.expander.expand_var(cleanup_props["directory"])
            else:
                dir = self.expander.experiment_run_dir
            regex = self.expander.expand_var(cleanup_props["regex"])
            cleaner_script = cleaner.get_cleaner_exec_path()
            recurse_flag = " --recurse" if cleanup_props["recurse"] else ""
            cleaner_cmd = (
                f'python3 "{cleaner_script}" '
                f"--directory {shlex.quote(dir)} "
                f"--regex {shlex.quote(regex)}"
                f"{recurse_flag}"
            )

            commands.append(f"# {key}-cleanup: {name}")
            commands.append(cleaner_cmd)

        return commands

    register_builtin("pre_cleanup", required=True, injection_method="prepend")

    def pre_cleanup(self):
        return self._generate_cleanup_cmd("pre")

    register_builtin("post_cleanup", required=True, injection_method="append")

    def post_cleanup(self):
        return self._generate_cleanup_cmd("post")

    def _get_filtered_and_full_executables(self):
        """Returns a dict of executables that satisfy `when` conditions, and a dict of all the executables"""
        filtered_executables = {}
        all_executables = self.executables.copy()
        full_executables = set().union(*all_executables.values())

        when_satisfied = {
            when_set
            for when_set in all_executables
            if self.expander.satisfies(
                when_set, variant_set=self.experiment_variants()
            )
        }

        for when_set in when_satisfied:
            executables = all_executables[when_set]
            for executable in executables:
                if executable in filtered_executables:
                    logger.die(
                        f"Executable {executable} is defined for overlapping `when` "
                        "conditions. Ensure conditions are mutually exclusive."
                    )
            filtered_executables.update(executables)

        return filtered_executables, full_executables

    def _define_custom_inputs(self):
        """Define custom inputs from internals"""
        if namespace.custom_inputs in self.internals:
            self.inputs = copy.deepcopy(self.inputs)
            empty_when = frozenset()
            if empty_when not in self.inputs:
                self.inputs[empty_when] = {}

            for name, conf in self.internals[namespace.custom_inputs].items():
                existing_input = None
                for when_set in list(self.inputs.keys()):
                    if name in self.inputs[when_set]:
                        existing_input = self.inputs[when_set][name]
                        del self.inputs[when_set][name]

                if existing_input:
                    new_input = existing_input.copy()
                    new_input["url"] = conf["url"]
                    if "sha256" in conf:
                        new_input["sha256"] = conf["sha256"]
                    if "target_dir" in conf:
                        new_input["target_dir"] = conf["target_dir"]
                    if "expand" in conf:
                        new_input["expand"] = conf["expand"]
                    if "extension" in conf:
                        ext = conf["extension"]
                        new_input["extension"] = (
                            ext.lstrip(".") if ext else ext
                        )
                    if "description" in conf:
                        new_input["description"] = conf["description"]
                    new_input["when"] = []
                    self.inputs[empty_when][name] = new_input
                else:
                    ext = conf.get("extension", None)
                    if ext:
                        ext = ext.lstrip(".")
                    new_input = {
                        "url": conf["url"],
                        "sha256": conf.get("sha256", None),
                        "target_dir": conf.get(
                            "target_dir", "{workload_input_dir}"
                        ),
                        "expand": conf.get("expand", True),
                        "extension": ext,
                        "description": conf.get("description", ""),
                        "when": [],
                    }
                    self.inputs[empty_when][name] = new_input

            self._input_fetchers = None

    def _define_custom_workloads(self):
        """Define custom workloads from internals"""
        if namespace.custom_workloads in self.internals:
            self.workloads = copy.deepcopy(self.workloads)
            empty_when = frozenset()
            if empty_when not in self.workloads:
                self.workloads[empty_when] = {}

            for name, conf in self.internals[
                namespace.custom_workloads
            ].items():
                existing_wl = None
                for when_set in list(self.workloads.keys()):
                    if name in self.workloads[when_set]:
                        existing_wl = self.workloads[when_set][name]
                        del self.workloads[when_set][name]

                if namespace.executables in conf:
                    executables = conf[namespace.executables]
                    if isinstance(executables, (str, int, float)):
                        executables = [str(executables)]
                    elif executables is None:
                        executables = []
                    else:
                        executables = [str(x) for x in executables]
                elif existing_wl:
                    executables = existing_wl.executables.copy()
                else:
                    executables = []

                if namespace.inputs in conf:
                    inputs = conf[namespace.inputs]
                    if isinstance(inputs, (str, int, float)):
                        inputs = [str(inputs)]
                    elif inputs is None:
                        inputs = []
                    else:
                        inputs = [str(x) for x in inputs]
                elif existing_wl:
                    inputs = existing_wl.inputs.copy()
                else:
                    inputs = []

                if namespace.tags in conf:
                    tags = conf[namespace.tags]
                    if isinstance(tags, (str, int, float)):
                        tags = [str(tags)]
                    elif tags is None:
                        tags = []
                    else:
                        tags = [str(x) for x in tags]
                elif existing_wl:
                    tags = existing_wl.tags.copy()
                else:
                    tags = []

                custom_wl = ramble.workload.Workload(
                    name=name,
                    executables=executables,
                    inputs=inputs,
                    tags=tags,
                )

                if existing_wl:
                    custom_wl.variables = copy.deepcopy(existing_wl.variables)
                    custom_wl.environment_variables = copy.deepcopy(
                        existing_wl.environment_variables
                    )
                    if existing_wl.where:
                        custom_wl.where = existing_wl.where.copy()
                    if existing_wl.exclude_where:
                        custom_wl.exclude_where = (
                            existing_wl.exclude_where.copy()
                        )

                self.workloads[empty_when][name] = custom_wl

    def _define_custom_executables(self):
        # Define custom executables
        if namespace.custom_executables in self.internals:
            for name, conf in self.internals[
                namespace.custom_executables
            ].items():
                custom_exec = ramble.util.executable.CommandExecutable(
                    name=name, **conf
                )
                existing_exec = self.custom_executables.get(name, None)

                if custom_exec == existing_exec:
                    continue

                filtered_executabls, _ = (
                    self._get_filtered_and_full_executables()
                )

                if (
                    name in filtered_executabls
                    or name in self.custom_executables
                ) and not conf.get("force", False):
                    experiment_namespace = self.expander.expand_var_name(
                        "experiment_namespace"
                    )
                    raise ExecutableNameError(
                        f"In experiment {experiment_namespace} "
                        f'a custom executable "{name}" is defined.\n'
                        f'However, an executable "{name}" is already '
                        "defined"
                    )

                self.custom_executables[name] = custom_exec

    def get_executable_graph(self, workload_name):
        """Construct and return an executable graph

        Builds an executable graph for a given workload.

        Returns:
            ExecutableGraph: Graph of executables for workload
        """
        self._define_custom_executables()
        # Use yaml defined executable order, if defined
        if namespace.executables in self.internals:
            exec_order = self.internals[namespace.executables]
        else:
            exec_order = self.get_workload(workload_name).executables

        builtin_objects = []
        all_builtins = []
        for _, obj in self.objects():
            for when_set, builtins in obj.builtins.items():
                if self.expander.satisfies(
                    when_set, variant_set=self.experiment_variants()
                ):
                    builtin_objects.append(obj)
                    all_builtins.append(builtins)

        filtered_executables, full_executables = (
            self._get_filtered_and_full_executables()
        )
        filtered_executables.update(self.custom_executables)

        filtered_exec_order = []
        for executable in exec_order:
            if executable in filtered_executables or any(
                executable in b for b in all_builtins
            ):
                filtered_exec_order.append(executable)
            else:
                if executable not in full_executables:
                    logger.die(f"Executable {executable} is not defined.")
                logger.debug(
                    f"Skipping executable {executable}. `When` conditions not satisfied."
                )

        executable_graph = ramble.graphs.ExecutableGraph(
            filtered_exec_order,
            filtered_executables,
            builtin_objects,
            all_builtins,
            self,
        )

        # Perform executable injection
        if namespace.executable_injection in self.internals:
            for exec_injection in self.internals[
                namespace.executable_injection
            ]:
                exec_name = exec_injection["name"]
                order = "before"
                if "order" in exec_injection:
                    order = exec_injection["order"]
                relative_to = None
                if "relative_to" in exec_injection:
                    relative_to = exec_injection["relative_to"]
                executable_graph.inject_executable(
                    exec_name, order, relative_to
                )

        return executable_graph

    def _set_input_path(self):
        """Define input file path variables

        Define variables for each input file, of the format:
            '{input_file_name}' = <path_to_input>
        """
        if not self.expander or not self.expander.workload_name:
            return

        self._inputs_and_fetchers(self.expander.workload_name)

        for input_file, input_conf in self._input_fetchers.items():
            input_vars = {}
            if input_conf["expand"]:
                input_vars[self.keywords.input_name] = input_conf["input_name"]
            else:
                input_vars[self.keywords.input_name] = input_file

            input_path = os.path.join(
                self.expander.expand_var(
                    os.path.join(input_conf["target_dir"], input_file),
                    extra_vars=input_vars,
                ),
            )
            self.variables[input_conf["input_name"]] = input_path

    @property
    def selected_variables(self):
        """Extract all variables which would be included based
        on the current variants. This overrides the one defined in
        the base mixin.

        Returns:
            (dict) Keys are variable names, values are variable instances
        """

        wl_vars = {}

        workloads = self.get_workloads()
        for workload in workloads:
            for var_when_set, var_list in workload.variables.items():
                if self.expander.satisfies(
                    var_when_set, self.experiment_variants()
                ):
                    for var in var_list:
                        wl_vars[var.name] = var

        for when_key, var_list in self.object_variables.items():
            if self.expander.satisfies(when_key, self.experiment_variants()):
                for var in var_list:
                    wl_vars[var.name] = var

        return wl_vars

    @property
    def selected_environment_variables(self):
        """Extract all environment variables which would be included based
        on the current variants. This overrides the one defined in
        the base mixin.

        Returns:
            (dict) Keys are environment variable names, values are environment
            variable instances
        """

        selected_env_vars = {}

        workloads = self.get_workloads()
        for workload in workloads:
            for (
                when_set,
                env_var_list,
            ) in workload.environment_variables.items():
                if self.expander.satisfies(
                    when_set, self.experiment_variants()
                ):
                    for env_var in env_var_list:
                        selected_env_vars[env_var.name] = env_var

        for (
            when_set,
            env_var_list,
        ) in self.object_environment_variables.items():
            if self.expander.satisfies(when_set, self.experiment_variants()):
                for env_var in env_var_list:
                    selected_env_vars[env_var.name] = env_var

        return selected_env_vars

    @property
    def environment_variable_sets(self):
        """Get environment variable sets for all objects.

        Returns:
            (list) List of environment variable sets from all objects
        """

        flattened_env_vars = {
            "set": {},
            "append": [],
            "prepend": [],
            "unset": set(),
        }

        for _, obj in self.objects():
            for env_var in obj.selected_environment_variables.values():
                action = env_var.method

                if action == "set":
                    flattened_env_vars[action][env_var.name] = env_var.value
                elif action == "unset":
                    flattened_env_vars[action].add(env_var.name)
                else:
                    sub_dict = {}
                    if action == "append":
                        sub_dict["var-separator"] = env_var.separator
                        sub_dict["vars"] = {env_var.name: env_var.value}
                    else:
                        sub_dict["paths"] = {env_var.name: env_var.value}
                    flattened_env_vars[action].append(sub_dict)

        # YAML defined env_vars override object defined env_vars
        for env_var_set in self._env_variable_sets:
            for action, conf in env_var_set.items():
                if action == "set":
                    flattened_env_vars[action].update(conf)
                elif action == "unset":
                    flattened_env_vars[action] = flattened_env_vars[
                        action
                    ].union(set(conf))
                else:
                    flattened_env_vars[action].extend(conf)

        flattened_env_vars["unset"] = list(flattened_env_vars["unset"])
        return [flattened_env_vars]

    def _define_commands(self, exec_graph=None, success_list=None):
        """Populate the internal list of commands based on executables

        Populates self._command_list with a list of the executable commands that
        should be executed by this experiment.
        """
        if self._command_list:
            return

        exec_graph = getattr(self, "_executable_graph", exec_graph)
        if exec_graph is None:
            self._executable_graph = self.get_executable_graph(
                self.expander.workload_name
            )
            exec_graph = self._executable_graph

        # Do not replace escaped braces here, to allow them to
        # be replace properly when templates are written.
        with self.expander.preserve_escaped_braces():
            self._command_list = []
            self._command_list_without_logs = []

            success_list = self.success_list
            if not success_list:
                success_list = ramble.success_criteria.ScopedCriteriaList()

            # Inject all prepended chained experiments
            for chained_exp in self.chain_prepend:
                self._command_list.append(self.chain_commands[chained_exp])
                self._command_list_without_logs.append(
                    self.chain_commands[chained_exp]
                )

            # ensure all log files are purged and set up
            logs = []

            for exec_node in exec_graph.walk():
                if isinstance(
                    exec_node.attribute,
                    ramble.util.executable.CommandExecutable,
                ):
                    exec_cmd = exec_node.attribute
                    if exec_cmd.redirect:
                        expanded_log = self.expander.expand_var(
                            exec_cmd.redirect
                        )
                        logs.append(expanded_log)

            analysis_logs, _, _ = self.analysis_dicts(success_list)
            logs = sorted(set(logs) | analysis_logs.keys())

            if logs:
                quoted_logs = " ".join(f'"{log}"' for log in logs)
                self._command_list.append(f"rm -f {quoted_logs}")
                self._command_list.append(f"touch {quoted_logs}")

            for exec_node in exec_graph.walk():
                exec_vars = {"executable_name": exec_node.key}

                if isinstance(
                    exec_node.attribute,
                    ramble.util.executable.CommandExecutable,
                ):
                    exec_vars.update(exec_node.attribute.variables)

                for mod in self._modifier_instances:
                    if mod.applies_to_executable(exec_node.key):
                        exec_vars.update(mod.modded_variables(self, exec_vars))

                if isinstance(
                    exec_node.attribute,
                    ramble.util.executable.CommandExecutable,
                ):
                    # Process directive defined executables
                    base_command = exec_node.attribute.copy()
                    pre_commands = []
                    post_commands = []

                    for mod in self._modifier_instances:
                        if mod.applies_to_executable(exec_node.key):
                            pre_cmd, post_cmd = mod.apply_executable_modifiers(
                                exec_node.key, base_command, app_inst=self
                            )
                            pre_commands.extend(pre_cmd)
                            post_commands.extend(post_cmd)

                    command_configs = pre_commands.copy()
                    command_configs.append(base_command)
                    command_configs.extend(post_commands)

                    for cmd_conf in command_configs:
                        mpi_cmd = ""
                        if cmd_conf.mpi:
                            raw_mpi_cmd = self.expander.expand_var(
                                "{mpi_command}",
                                exec_vars,
                            ).strip()
                            n_nodes = self.expander.expand_var_name(
                                self.keywords.n_nodes
                            )
                            n_nodes = (
                                1
                                if n_nodes in ("{n_nodes}", None, "")
                                else int(n_nodes)
                            )
                            if not raw_mpi_cmd and n_nodes > 1:
                                logger.warn(
                                    f"Command {cmd_conf.name} requires a non-empty `mpi_command` "
                                    "variable in a multi-node experiment"
                                )
                            mpi_cmd = " " + raw_mpi_cmd + " "

                        redirect = ""
                        if cmd_conf.redirect:
                            out_log = self.expander.expand_var(
                                cmd_conf.redirect,
                                exec_vars,
                            )
                            output_operator = cmd_conf.output_capture

                            redirect_mapper = output_mapper()
                            redirect = redirect_mapper.generate_out_string(
                                out_log, output_operator
                            )

                        if cmd_conf.run_in_background:
                            bg_cmd = " &"
                        else:
                            bg_cmd = ""

                        for part in cmd_conf.template:
                            command_part = f"{mpi_cmd}{part}"
                            suffix_part = f"{redirect}{bg_cmd}"

                            expanded_cmd = self.expander.expand_var(
                                command_part,
                                exec_vars,
                            ).lstrip()
                            suffix_cmd = self.expander.expand_var(
                                suffix_part,
                                exec_vars,
                            ).lstrip()

                            self._command_list.append(
                                (expanded_cmd + " " + suffix_cmd).rstrip()
                            )
                            self._command_list_without_logs.append(
                                expanded_cmd
                            )

                else:  # All Builtins
                    func = exec_node.attribute
                    func_cmds = func()
                    if isinstance(func_cmds, str):
                        func_cmds = [func_cmds]
                    for cmd in func_cmds:
                        expanded = self.expander.expand_var(cmd, exec_vars)
                        self._command_list.append(expanded)
                        self._command_list_without_logs.append(expanded)

            # Inject all appended chained experiments
            for chained_exp in self.chain_append:
                expanded = self.expander.expand_var(
                    self.chain_commands[chained_exp]
                )
                self._command_list.append(expanded)
                self._command_list_without_logs.append(expanded)

    def _define_formatted_executables(self):
        """Define variables representing the formatted executables

        Process the formatted_executables definitions, and construct their
        variable definitions.

        Each formatted executable definition is injected as its own variable
        based on the formatting requested.
        """

        self.variables[self.keywords.unformatted_command] = "\n".join(
            self._command_list
        )
        self.variables[self.keywords.unformatted_command_without_logs] = (
            "\n".join(self._command_list_without_logs)
        )
        formatted_exec_groups = [{frozenset(): self._formatted_executables}]

        objs_to_extract = [self, self.workflow_manager, self.package_manager]

        formatted_exec_groups.extend(
            obj.formatted_executables
            for obj in objs_to_extract + self._modifier_instances
            if obj and hasattr(obj, "formatted_executables")
        )

        all_execs = {}

        for formatted_exec_group in formatted_exec_groups:
            for when_set, formatted_exec_defs in formatted_exec_group.items():
                if not self.expander.satisfies(
                    when_set, variant_set=self.experiment_variants()
                ):
                    continue

                for var_name, formatted_conf in formatted_exec_defs.items():
                    if var_name in self.variables:
                        raise FormattedExecutableError(
                            f"Formatted executable {var_name} defined, but variable "
                            "definition already exists."
                        )

                    if var_name in all_execs:
                        raise FormattedExecutableError(
                            f"Formatted executable {var_name} already defined."
                        )

                    all_execs[var_name] = formatted_conf

        # Set formatted executable dependencies and order
        formatted_exec_graph = ramble.graphs.FormattedExecutableGraph(
            all_execs, obj_inst=self
        )
        for node in formatted_exec_graph.walk():
            formatted_conf = node.attribute

            # Create the formatted command for the executable
            n_indentation = 0
            if namespace.indentation in formatted_conf:
                n_indentation = int(formatted_conf[namespace.indentation])

            prefix = ""
            if namespace.prefix in formatted_conf:
                prefix = formatted_conf[namespace.prefix]

            join_separator = "\n"
            if namespace.join_separator in formatted_conf:
                join_separator = formatted_conf[
                    namespace.join_separator
                ].replace(r"\n", "\n")

            indentation = " " * n_indentation

            commands_to_format = self._command_list
            if namespace.commands in formatted_conf:
                commands_to_format = formatted_conf[namespace.commands].copy()

            formatted_lines = []
            for command in commands_to_format:
                # Do not replace escaped braces here, to allow them to
                # be replace properly when templates are written.
                expanded = self.expander.expand_var(
                    command, replace_escaped_braces=False
                )

                formatted_lines.extend(
                    indentation + prefix + out_line
                    for out_line in expanded.split("\n")
                )

            self.variables[node.key] = join_separator.join(formatted_lines)

    def define_variables_for_template_path(self):
        """Define variables for all workspace and object template paths"""
        if self._template_paths_defined:
            return

        self._set_input_path()

        workspace = self.workspace
        if workspace:
            for template_name, _ in workspace.all_templates():
                expand_path = os.path.join(
                    self.expander.expand_var("{experiment_run_dir}"),
                    template_name,
                )
                self.variables[template_name] = expand_path

        var_attr = {
            "type": ramble.keywords.key_type.reserved,
            "level": ramble.keywords.output_level.variable,
        }
        for obj, tpl_configs in self._object_templates():
            for tpl_config in tpl_configs:
                var_name = tpl_config["var_name"]
                if var_name is not None:
                    if var_name in self.variables:
                        old_var = f"_old_{var_name}"
                        self.variables[old_var] = self.variables[var_name]
                        self.keywords.update_keys({old_var: var_attr})
                    self.variables[var_name] = tpl_config["dest_path"]
                    self.keywords.update_keys({var_name: var_attr})
            if hasattr(obj, "template_render_vars"):
                render_vars = obj.template_render_vars
                self.variables.update(render_vars)
                for name in render_vars:
                    self.keywords.update_keys({name: var_attr})

        self._template_paths_defined = True

    def _inputs_and_fetchers(self, workload=None):
        """Extract all inputs for a given workload

        Take a workload name and extract all inputs for the workload.
        If the workload is set to None, extract all inputs for all workloads.
        """
        self._define_custom_inputs()

        if self._input_fetchers is not None:
            return

        self._input_fetchers = {}

        # Batch 'when' evaluation to avoid repeat expander calls
        when_satisfied = {
            when_set
            for when_set in self.inputs
            if self.expander.satisfies(
                when_set, variant_set=self.experiment_variants()
            )
        }

        inputs = {}
        workloads = (
            [self.get_workload(workload)]
            if workload
            else self.get_all_workloads()
        )
        for wl in workloads:
            for input_file in wl.inputs:
                inputs_found = 0
                active_inputs = 0
                input_conf = {}
                for when_set, app_inputs in self.inputs.items():
                    if input_file in app_inputs:
                        inputs_found += 1
                        if when_set in when_satisfied:
                            active_inputs += 1
                            input_conf = app_inputs[input_file].copy()

                if not inputs_found:
                    logger.die(
                        f"Workload {wl.name} references a non-existent input file "
                        f"{input_file}.\n"
                        f"Make sure this input file is defined before using it in a workload."
                    )
                if active_inputs == 0:
                    logger.debug(
                        f"Skipping input {input_file}. `When` conditions not satisfied."
                    )
                    continue
                elif active_inputs > 1:
                    logger.die(
                        f"Input files {input_file} are defined with overlapping 'when' "
                        f"conditions. Make sure that conditions are mutually exclusive."
                    )

                # Expand input value as it may be a var
                if "url" not in input_conf:
                    continue

                expanded_url = self.expander.expand_var(input_conf["url"])
                input_conf["url"] = expanded_url

                fetcher = ramble.fetch_strategy.URLFetchStrategy(**input_conf)

                file_name = os.path.basename(input_conf["url"])
                if not fetcher.extension:
                    fetcher.extension = spack.util.compression.extension(
                        file_name
                    )

                file_name = file_name.replace(f".{fetcher.extension}", "")

                namespace = f"{self.name}.{wl.name}"

                inputs[file_name] = {
                    "fetcher": fetcher,
                    "namespace": namespace,
                    "target_dir": input_conf["target_dir"],
                    "extension": fetcher.extension,
                    "input_name": input_file,
                    "expand": input_conf["expand"],
                }
        self._input_fetchers = inputs

    register_phase("mirror_inputs", pipeline="mirror")

    def _mirror_inputs(self, workspace, app_inst=None):
        """Mirror application inputs

        Perform mirroring of inputs within this application class.
        """
        mirror_lock = lk.Lock(
            os.path.join(workspace.input_mirror_path, ".ramble-mirror")
        )
        self._inputs_and_fetchers(self.expander.workload_name)

        with lk.WriteTransaction(mirror_lock):
            for input_file, input_conf in self._input_fetchers.items():
                mirror_paths = ramble.mirror.mirror_archive_paths(
                    input_conf["fetcher"], os.path.join(self.name, input_file)
                )
                fetch_dir = os.path.join(
                    workspace.input_mirror_path, self.name
                )
                fs.mkdirp(fetch_dir)
                stage = ramble.stage.InputStage(
                    input_conf["fetcher"],
                    name=input_conf["namespace"],
                    path=fetch_dir,
                    mirror_paths=mirror_paths,
                    lock=False,
                )

                stage.cache_mirror(
                    workspace.input_mirror_cache, workspace.input_mirror_stats
                )

    register_phase("bootstrap_utilities", pipeline="bootstrap")
    register_phase(
        "bootstrap_utilities",
        pipeline="setup",
        run_before=["get_inputs"],
    )

    def _bootstrap_utilities(self, workspace, app_inst=None):
        """Bootstrap external dependencies for this experiment"""
        if not ramble.config.get("config:bootstrap_utilities", True):
            logger.debug(
                "Bootstrapping external dependencies is disabled by config."
            )
            return

        ext_dep_paths = {}
        ext_dep_instances = {}
        ext_dep_versions = {}
        objects_to_check = [self]
        if hasattr(self, "package_manager") and self.package_manager:
            objects_to_check.append(self.package_manager)
        if hasattr(self, "system") and self.system:
            objects_to_check.append(self.system)
        if hasattr(self, "platform") and self.platform:
            objects_to_check.append(self.platform)
        if hasattr(self, "workflow_manager") and self.workflow_manager:
            objects_to_check.append(self.workflow_manager)
        if hasattr(self, "_modifiers") and self._modifiers:
            objects_to_check.extend(self._modifiers)

        ws_ext_deps = (
            workspace._get_workspace_dict()
            .get("ramble", {})
            .get("utilities", {})
        )

        for obj in objects_to_check:
            if not hasattr(obj, "required_utilities"):
                continue

            for (
                when_key,
                ext_deps,
            ) in obj.required_utilities.items():
                if obj.satisfy_when(when_key):
                    for ext_dep_name, ext_dep_conf in ext_deps.items():
                        try:
                            # Instantiate the external dependency
                            ext_dep_inst = ramble.repository.paths[
                                ramble.repository.ObjectTypes.utilities
                            ].get(ext_dep_name)
                            ext_dep_instances[ext_dep_name] = ext_dep_inst
                        except Exception as e:
                            logger.warn(
                                f"Failed to find external dependency {ext_dep_name}: {e}"
                            )
                            continue

                        # Variables merging logic: object -> workspace
                        fetch_kwargs = {}

                        for (
                            when_cond,
                            vars_list,
                        ) in ext_dep_inst.object_variables.items():
                            if obj.satisfy_when(when_cond):
                                for var_info in vars_list:
                                    var_name = var_info.name
                                    if hasattr(self, "expander"):
                                        expanded_val = (
                                            self.expander.expand_var(
                                                f"{{{var_name}}}"
                                            )
                                        )
                                        if expanded_val != f"{{{var_name}}}":
                                            fetch_kwargs[var_name] = (
                                                expanded_val
                                            )
                                            continue

                                    fetch_kwargs[var_name] = var_info.default

                        if ext_dep_name in ws_ext_deps:
                            fetch_kwargs.update(ws_ext_deps[ext_dep_name])
                        else:
                            fetch_kwargs.update(ext_dep_conf)

                        if hasattr(ext_dep_inst, "map_fetch_kwargs"):
                            fetch_kwargs = ext_dep_inst.map_fetch_kwargs(
                                fetch_kwargs
                            )

                        if "when" in fetch_kwargs:
                            del fetch_kwargs["when"]

                        min_version = fetch_kwargs.pop("min_version", None)
                        max_version = fetch_kwargs.pop("max_version", None)

                        origin_name = obj.name
                        origin_type = getattr(obj, "origin_type", "object")

                        ext_dep_versions[ext_dep_name] = {
                            "min_version": min_version,
                            "max_version": max_version,
                            "origin_name": origin_name,
                            "origin_type": origin_type,
                        }

                        for k, v in fetch_kwargs.items():
                            if isinstance(v, str):
                                fetch_kwargs[k] = self.expander.expand_var(v)

                        version_str = (
                            fetch_kwargs.get("commit")
                            or fetch_kwargs.get("version")
                            or fetch_kwargs.get("tag")
                            or fetch_kwargs.get("branch")
                            or fetch_kwargs.get("revision")
                            or "latest"
                        )
                        ext_dep_dir = os.path.join(
                            workspace.shared_dir,
                            "bootstrapped_utilities",
                            ext_dep_name,
                            version_str,
                        )
                        ext_dep_paths[ext_dep_name] = os.path.join(
                            ext_dep_dir, "source"
                        )

                        sorted_kwargs_str = str(sorted(fetch_kwargs.items()))
                        cache_tuple = (
                            f"utility-bootstrap-{ext_dep_name}",
                            sorted_kwargs_str,
                        )

                        if not hasattr(obj, "variables"):
                            obj.variables = {}
                        obj.variables[f"utility::{ext_dep_name}::path"] = (
                            ext_dep_paths[ext_dep_name]
                        )

                        if not ramble.config.get(
                            "config:bootstrap_utilities",
                            True,
                        ):
                            logger.debug(
                                f"External dependency bootstrapping is disabled globally. Using system {ext_dep_name}."
                            )
                            ext_dep_paths[ext_dep_name] = "system"
                            continue

                        allow_external = fetch_kwargs.pop(
                            "allow_external", True
                        )

                        if isinstance(allow_external, str):
                            allow_external = allow_external.lower() == "true"
                        else:
                            allow_external = bool(allow_external)

                        if allow_external:
                            if hasattr(
                                ext_dep_inst, "is_available"
                            ) and ext_dep_inst.is_available(
                                workspace,
                                min_version=min_version,
                                max_version=max_version,
                            ):
                                logger.debug(
                                    f"External dependency {ext_dep_name} is already available in the environment, skipping fetch."
                                )
                                ext_dep_paths[ext_dep_name] = "system"
                                continue
                            logger.msg(
                                f"External dependency {ext_dep_name} is not available in the environment. Bootstrapping a new version."
                            )
                        else:
                            logger.msg(
                                f"External dependency {ext_dep_name} is not allowed to be provided externally. Bootstrapping a new version."
                            )

                        is_bootstrappable = True
                        if hasattr(ext_dep_inst, "bootstrappable"):
                            for (
                                when_cond,
                                b_list,
                            ) in ext_dep_inst.bootstrappable.items():
                                if obj.satisfy_when(when_cond):
                                    for b_info in b_list:
                                        is_bootstrappable = b_info[
                                            "is_bootstrappable"
                                        ]

                        if not is_bootstrappable:
                            error_message = f"External dependency '{ext_dep_name}' is not available on the system and is marked as non-bootstrappable."
                            custom_message = None
                            if hasattr(ext_dep_inst, "missing_error_messages"):
                                for (
                                    when_cond,
                                    m_list,
                                ) in (
                                    ext_dep_inst.missing_error_messages.items()
                                ):
                                    if obj.satisfy_when(when_cond):
                                        for m_info in m_list:
                                            custom_message = m_info["message"]

                            if custom_message:
                                error_message = custom_message
                            elif (
                                hasattr(ext_dep_inst, "availability_error")
                                and ext_dep_inst.availability_error
                            ):
                                error_message += f"\nReason: {ext_dep_inst.availability_error}"
                            logger.die(error_message)

                        if not workspace.check_cache(cache_tuple):
                            if not workspace.dry_run:
                                try:
                                    if hasattr(ext_dep_inst, "install"):
                                        ext_dep_inst.install(workspace)

                                    fetcher_kwargs = {
                                        k: v
                                        for k, v in fetch_kwargs.items()
                                        if k
                                        in [
                                            "git",
                                            "url",
                                            "commit",
                                            "tag",
                                            "branch",
                                            "revision",
                                            "version",
                                            "checksum",
                                            "sha256",
                                            "svn",
                                            "hg",
                                        ]
                                    }
                                    fetcher = (
                                        ramble.fetch_strategy.from_kwargs(
                                            **fetcher_kwargs
                                        )
                                    )
                                    stage = ramble.stage.InputStage(
                                        fetcher,
                                        name=ext_dep_name,
                                        path=ext_dep_dir,
                                    )
                                    with stage:
                                        stage.set_subdir("source")
                                        stage.fetch()
                                        stage.expand_archive()

                                    if hasattr(
                                        ext_dep_inst, "modify_bootstrap"
                                    ):
                                        ext_dep_inst.modify_bootstrap(
                                            workspace,
                                            obj,
                                        )
                                except Exception as e:
                                    logger.die(
                                        f"Failed to bootstrap external dependency {ext_dep_name}: {e}"
                                    )

                            workspace.add_to_cache(cache_tuple)

        self._bootstrapped_utility_paths = ext_dep_paths

        for obj in objects_to_check:
            exp_env_mod = spack.util.environment.EnvironmentModifications()
            source_scripts_commands = []

            if hasattr(obj, "scripts_to_source"):
                for script_info in obj.scripts_to_source:
                    when_cond = script_info.get("when", [])
                    if obj.satisfy_when(when_cond):
                        script_path = script_info["path"]
                        source_scripts_commands.append(f"source {script_path}")
                        exp_env_mod.extend(
                            spack.util.environment.EnvironmentModifications.from_sourcing_file(
                                script_path
                            )
                        )

            if not hasattr(obj, "variables"):
                obj.variables = {}
            if source_scripts_commands:
                obj.variables["source_scripts_command"] = "\n".join(
                    source_scripts_commands
                )
            else:
                obj.variables["source_scripts_command"] = ""

            for ext_dep_name, ext_dep_path in ext_dep_paths.items():
                ext_dep_inst = ext_dep_instances[ext_dep_name]

                obj.variables[f"utility::{ext_dep_name}::path"] = ext_dep_path

                if hasattr(ext_dep_inst, "get_experiment_activation_command"):
                    act_cmd = ext_dep_inst.get_experiment_activation_command(
                        workspace, obj
                    )
                    obj.variables[
                        f"utility::{ext_dep_name}::activation_command"
                    ] = act_cmd

                if hasattr(ext_dep_inst, "setup_runner_environment"):
                    env_mod = ext_dep_inst.setup_runner_environment(
                        workspace, obj
                    )
                    if env_mod:
                        exp_env_mod.extend(env_mod)

            exp_env = os.environ.copy()
            exp_env_mod.apply_modifications(exp_env)
            obj.experiment_runner_env = exp_env

            for ext_dep_name, ext_dep_inst in ext_dep_instances.items():
                if hasattr(ext_dep_inst, "validate_versions"):
                    versions = ext_dep_versions.get(ext_dep_name, {})
                    min_v = versions.get("min_version")
                    max_v = versions.get("max_version")
                    origin_name = versions.get("origin_name")
                    origin_type = versions.get("origin_type")

                    if not workspace.dry_run:
                        if not ext_dep_inst.validate_versions(
                            min_version=min_v,
                            max_version=max_v,
                            env=exp_env,
                            origin_name=origin_name,
                            origin_type=origin_type,
                        ):
                            logger.die(
                                f"Version validation failed for {ext_dep_name} after bootstrap:\n{ext_dep_inst.availability_error}"
                            )

            if hasattr(obj, "bootstrap_utility"):
                obj.bootstrap_utility(workspace, ext_dep_paths)

    register_phase("get_inputs", pipeline="setup")

    def _get_inputs(self, workspace, app_inst=None):
        """Download application inputs

        Download application inputs into the proper directory within the workspace.
        """
        workload_namespace = self.expander.workload_namespace

        self._inputs_and_fetchers(self.expander.workload_name)

        for input_file, input_conf in self._input_fetchers.items():
            if not workspace.dry_run:
                input_vars = {
                    self.keywords.input_name: input_conf["input_name"]
                }
                input_namespace = workload_namespace + "." + input_file
                input_path = self.expander.expand_var(
                    os.path.join(input_conf["target_dir"], input_file),
                    extra_vars=input_vars,
                )
                input_tuple = (f"input-file-{input_file}", input_path)

                # Skip inputs that have already been cached
                if workspace.check_cache(input_tuple):
                    continue

                mirror_paths = ramble.mirror.mirror_archive_paths(
                    input_conf["fetcher"], os.path.join(self.name, input_file)
                )

                input_dir = os.path.dirname(input_path)
                input_base = os.path.basename(input_path)

                input_lock = lk.Lock(os.path.join(input_dir, ".ramble-input"))

                with lk.WriteTransaction(input_lock):
                    with ramble.stage.InputStage(
                        input_conf["fetcher"],
                        name=input_namespace,
                        path=input_dir,
                        mirror_paths=mirror_paths,
                    ) as stage:
                        stage.set_subdir(input_base)
                        try:
                            stage.fetch()
                            if input_conf["fetcher"].digest:
                                stage.check()
                            stage.cache_local()

                            if input_conf["expand"]:
                                try:
                                    stage.expand_archive()
                                except spack.util.executable.ProcessError:
                                    pass
                        except ramble.fetch_strategy.FetchError as e:
                            logger.all_msg(
                                f"Failed fetching input {input_file} in application {self.name}"
                            )
                            logger.all_msg(
                                f"Input url was: {input_conf['fetcher'].url}"
                            )
                            logger.die(str(e))

                workspace.add_to_cache(input_tuple)
            else:
                logger.msg(
                    f'DRY-RUN: Would download {input_conf["fetcher"].url}'
                )

    def _prepare_license_path(self, workspace):
        self.license_path = os.path.join(
            workspace.shared_license_dir, self.name
        )
        self.license_file = os.path.join(self.license_path, LICENSE_INC_NAME)

        fs.mkdirp(self.license_path)

    register_phase("license_includes", pipeline="setup")

    def _license_includes(self, workspace, app_inst=None):
        logger.debug("Writing License Includes")
        self._prepare_license_path(workspace)

        action_funcs = ramble.util.env.action_funcs
        config_scopes = ramble.config.scopes()
        shell = ramble.config.get("config:shell")
        var_set = set()
        for scope in config_scopes:
            license_conf = ramble.config.config.get_config(
                "licenses", scope=scope
            )
            if license_conf:
                # If we have multiple matches, the last entry should win (latest in hierarchy)
                app_licenses = {}
                for lic in self.license_names:
                    if lic in license_conf:
                        app_licenses = license_conf[lic]

                for action, conf in app_licenses.items():
                    env_cmds, var_set = action_funcs[action](
                        conf, self.expander, var_set, shell=shell
                    )

                    lock = lk.Lock(
                        os.path.join(self.license_path, ".ramble-license")
                    )
                    with lk.WriteTransaction(lock):
                        with open(
                            self.license_file, "w+", encoding="utf-8"
                        ) as f:
                            for cmd in env_cmds:
                                if cmd:
                                    f.write(
                                        self.expander.expand_var(cmd) + "\n"
                                    )

    register_phase(
        "make_experiments", pipeline="setup", run_after=["get_inputs"]
    )

    def _make_experiments(self, workspace, app_inst=None):
        """Create experiment directories

        Create the experiment this application encapsulates. This includes
        creating the experiment run directory, rendering the necessary
        templates, and injecting the experiment into the workspace all
        experiments file.
        """

        _check_shell_support(self)

        exp_lock = self.experiment_lock

        # Report missing command variables
        if self._missing_command_variables:
            logger.msg("Missing Command Variable Summary:")
            dry_run_str = " (dry-run)" if workspace.dry_run else ""
            for name, var in self._missing_command_variables.items():
                command = self.expander.expand_var(var.command)
                logger.msg(
                    f"- {name} = {self.variables[name]}{dry_run_str} from '{command}'"
                )

        self._set_input_path()
        self._define_commands(success_list=self.success_list)
        self._define_formatted_executables()

        with lk.WriteTransaction(exp_lock):
            experiment_run_dir = self.expander.experiment_run_dir
            fs.mkdirp(experiment_run_dir)

            exec_vars = {}

            for mod in self._modifier_instances:
                exec_vars.update(mod.modded_variables(self, exec_vars))

            for template_name, _ in workspace.all_templates():
                expand_path = os.path.join(experiment_run_dir, template_name)
                logger.msg(
                    f"Writing template {template_name} to {expand_path}"
                )
                fs.mkdirp(os.path.dirname(expand_path))

                rendered_content = self._get_rendered_template_content(
                    template_name, exec_vars, rendering_stack=[]
                )

                with open(expand_path, "w+", encoding="utf-8") as f:
                    f.write(rendered_content)
                os.chmod(expand_path, _DEFAULT_CONTENT_PERM)

            self._render_object_templates(exec_vars)

            experiment_script = workspace.experiments_script
            experiment_script.write(
                self.expander.expand_var("{batch_submit}\n")
            )

        self.set_status(status=ExperimentStatus.SETUP)

    def _clean_hash_variables(self, variables):
        """Cleanup variables to hash before computing the hash

        Perform some general cleanup operations on variables
        before hashing, to help give useful hashes.
        """
        workspace = self.workspace

        remove_variables = [
            "workspace_name",
            "experiment_hash",
            "experiment_status",
            "RAMBLE_STATUS",
        ]

        remove_prefixes = set()
        for _, obj in self.objects():
            remove_variables.append(f"{obj.origin_type}_version")
            remove_variables.append(f"{obj.origin_type}::{obj.name}::version")
            remove_prefixes.add(f"{obj.origin_type}::variant::")

        # Remove some variables that don't affect the experiment, and change
        # frequently (or are actually output variables)
        for var in remove_variables:
            if var in variables:
                del variables[var]

        # Remove variant variables (but not the variant definitions themselves)
        if remove_prefixes:
            prefixes = tuple(remove_prefixes)
            for var in list(variables.keys()):
                if var.startswith(prefixes):
                    del variables[var]

        # Remove the workspace path from variable definitions before hashing
        for var in variables:
            if isinstance(variables[var], str):
                variables[var] = variables[var].replace(
                    workspace.root, "$workspace_root"
                )

    def variant_inventory(self):
        """Construct a list of all variants from any object in the experiment,
        for the experiment's inventory.

        Returns:
            (list[str]): List of variant definitions from all objects
        """

        variant_definitions = set()

        for _, obj in self.objects():
            variant_definitions = variant_definitions.union(
                obj.experiment_variants(app_inst=self).as_set(for_output=True)
            )

        return sorted(variant_definitions, key=when_order)

    def _purge_inventory(self):
        self.hash_inventory = {
            "object_configuration": [],
            "attributes": [],
            "inputs": [],
            "software": [],
            "templates": [],
        }
        self.experiment_hash = None

    def populate_inventory(
        self,
        workspace,
        force_compute: bool = False,
    ) -> bool:
        """Populate this experiment's hash inventory

        If an inventory file exists, read it first.
        If it does not exist, compute it using the internal information.

        If force_compute is set to true, always compute and never read.

        Args:
            force_compute: Boolean that allows forces the inventory to be computed instead of read
                           Used in pipelines that should create the inventory, instead of
                           consuming it.
        """

        if self.repeats.is_repeat_base:
            return False

        if self.expander is None:
            return False

        changed = False
        self._purge_inventory()

        experiment_run_dir = self.expander.experiment_run_dir
        inventory_file = os.path.join(
            experiment_run_dir, self._inventory_file_name
        )

        force = force_compute or ramble.config.get(
            "config:overwrite_inventories", default=False
        )

        existing_hash = None
        if os.path.exists(inventory_file) and not force:
            with open(inventory_file, encoding="utf-8") as f:
                existing_inventory = json_util.load(f)
            existing_hash = ramble.util.hashing.hash_json(existing_inventory)

        # Clean up variables before hashing
        vars_to_hash = self.variables.copy()
        self._clean_hash_variables(vars_to_hash)

        # Build inventory of attributes
        attributes_to_hash = [
            ("variables", vars_to_hash),
            ("modifiers", self.modifiers),
            ("variants", self.variant_inventory()),
            ("chained_experiments", self.chained_experiments),
            ("internals", self.internals),
            ("env_vars", self._env_variable_sets),
        ]

        added_objects = {}
        for obj_type, obj in self.objects(yield_all=True):
            if obj_type not in added_objects:
                added_objects[obj_type] = set()

            if obj.name not in added_objects[obj_type]:
                added_objects[obj_type].add(obj.name)
                object_inventory = {
                    "name": obj.name,
                    "object_type": obj_type.name,
                    "type": obj_type.name,
                    "digest": ramble.util.hashing.hash_file(obj._file_path),
                }

                is_base_class = getattr(obj, "_is_base_class", False)

                version_func = getattr(obj, "get_version", None)
                if (
                    not is_base_class
                    and version_func is not None
                    and callable(version_func)
                ):
                    version = obj.get_version(workspace=workspace)
                    object_inventory["version"] = version
                    object_inventory["external_version"] = version

                if not is_base_class and obj is not self:
                    populate_func = getattr(obj, "populate_inventory", None)
                    if populate_func is not None and callable(populate_func):
                        obj.populate_inventory(workspace, force)

                artifact_func = getattr(obj, "artifact_inventory", None)
                if (
                    not is_base_class
                    and artifact_func is not None
                    and callable(artifact_func)
                ):
                    inventory = obj.artifact_inventory(workspace, self)
                    if inventory:
                        if hasattr(obj, "_usage_mode"):
                            object_inventory["mode"] = obj._usage_mode
                        object_inventory["artifacts"] = inventory

                self.hash_inventory["object_configuration"].append(
                    object_inventory
                )

        for attr, attr_dict in attributes_to_hash:
            self.hash_inventory["attributes"].append(
                {
                    "name": attr,
                    "digest": ramble.util.hashing.hash_json(attr_dict),
                }
            )

        # Build inventory of workspace templates
        for template_name, template_conf in workspace.all_templates():
            self.hash_inventory["templates"].append(
                {
                    "name": template_name,
                    "digest": template_conf["digest"],
                }
            )

        # Build inventory of inputs
        self._inputs_and_fetchers(self.expander.workload_name)

        for input_conf in self._input_fetchers.values():
            if input_conf["fetcher"].digest:
                self.hash_inventory["inputs"].append(
                    {
                        "name": input_conf["input_name"],
                        "digest": input_conf["fetcher"].digest,
                    }
                )
            else:
                self.hash_inventory["inputs"].append(
                    {
                        "name": input_conf["input_name"],
                        "digest": ramble.util.hashing.hash_string(
                            input_conf["fetcher"].url
                        ),
                    }
                )

        self.experiment_hash = ramble.util.hashing.hash_json(
            self.hash_inventory
        )

        # Compare inventory hashes, to validate experiment hasn't changed
        if existing_hash is not None and self.experiment_hash != existing_hash:
            logger.die(
                f"Mismatch on experiment hash for experiment {self.expander.experiment_namespace}.\n"
                f"  Hash from experiment directory: {existing_hash}\n"
                f"  Hash computed current config: {self.experiment_hash}\n"
                "Hashes change as a result of changes to the workspace YAML configuration file, or "
                "any object in an experiment's hierarchy.\n"
                "Hashes are compared to ensure experiments that are set up match the expected "
                "contents from these sources.\n"
                "Hashes can be overwritten if you are sure this is safe, and what you want. "
                "To overwrite the experiment hash, use the global --overwrite-inventories option."
            )

        self.variables[self.keywords.experiment_hash] = self.experiment_hash

        # Write out experiment inventory, if hash is different
        if existing_hash != self.experiment_hash:
            changed = True

        writable = True
        if self.repeats.is_repeat_base:
            writable = False

        if changed and writable:
            with lk.WriteTransaction(self.experiment_lock):
                with open(inventory_file, "w+", encoding="utf-8") as f:
                    json_util.dump(self.hash_inventory, f)

        return changed

    register_phase("archive_experiments", pipeline="archive")

    def _archive_experiments(self, workspace, app_inst=None):
        """Archive an experiment directory

        Perform the archiving action on an experiment.
        This includes capturing:
        - Rendered templates within the experiment directory
        - All files that contain a figure of merit or success criteria
        - Any files that match an archive pattern
        """
        import glob

        experiment_run_dir = self.expander.experiment_run_dir
        ws_archive_dir = workspace.latest_archive_path

        archive_experiment_dir = experiment_run_dir.replace(
            workspace.root, ws_archive_dir
        )

        fs.mkdirp(archive_experiment_dir)

        archive_lock = lk.Lock(
            os.path.join(archive_experiment_dir, ".ramble-exp-archive")
        )

        with lk.WriteTransaction(archive_lock):
            # Copy all log files from executables
            exec_logs = set()
            workload = self.get_workload()
            filtered_executables, _ = self._get_filtered_and_full_executables()
            for exec_name in workload.executables:
                if exec_name in filtered_executables:
                    exec_obj = filtered_executables[exec_name]
                    exec_log = self.expander.expand_var(exec_obj.redirect)
                    exec_logs.add(exec_log)

            for exec_log in exec_logs:
                file = exec_log
                if not os.path.isabs(file):
                    file = os.path.join(experiment_run_dir, exec_log)

                if os.path.isfile(file):
                    dest_dir = os.path.dirname(
                        file.replace(workspace.root, ws_archive_dir)
                    )
                    fs.mkdirp(dest_dir)
                    shutil.copy(file, dest_dir)

            # Copy all of the templates to the archive directory
            for template_name, _ in workspace.all_templates():
                src = os.path.join(experiment_run_dir, template_name)
                if os.path.exists(src):
                    shutil.copy(src, archive_experiment_dir)

            # Copy all rendered templates generated by `register_template`
            for _, tpl_configs in self._object_templates():
                for tpl_config in tpl_configs:
                    src_path = tpl_config["dest_path"]
                    if os.path.exists(src_path):
                        shutil.copy(src_path, archive_experiment_dir)

            # Copy all figure of merit files
            criteria_list = self.success_list
            analysis_files, _, _ = self.analysis_dicts(criteria_list)
            for file in analysis_files:
                if os.path.exists(file):
                    shutil.copy(file, archive_experiment_dir)

            # Copy all archive patterns
            archive_patterns = set()
            for _, obj_inst in self.objects():
                for when_set, patterns in getattr(
                    obj_inst, "archive_patterns", {}
                ).items():
                    if self.expander.satisfies(
                        reqs=when_set, variant_set=self.experiment_variants()
                    ):
                        for pattern in patterns.values():
                            archive_patterns.add(pattern)

            for pattern in archive_patterns:
                exp_pattern = self.expander.expand_var(pattern)
                if not os.path.isabs(exp_pattern):
                    exp_pattern = os.path.join(experiment_run_dir, exp_pattern)
                for file in glob.glob(exp_pattern):
                    dest_dir = os.path.dirname(
                        file.replace(workspace.root, ws_archive_dir)
                    )
                    fs.mkdirp(dest_dir)
                    shutil.copy(file, dest_dir)

            for file_name in [
                self._inventory_file_name,
                self._status_file_name,
            ]:
                file = os.path.join(experiment_run_dir, file_name)
                if os.path.exists(file):
                    shutil.copy(file, archive_experiment_dir)

    register_phase("prepare_analysis", pipeline="analyze")

    def _prepare_analysis(self, workspace, app_inst=None):
        """Prepapre experiment for analysis extraction

        This function performs any actions that are necessary before the
        figures of merit, and success criteria can be properly extracted.

        This function can be overridden at the application level to perform
        application specific processing of the output.
        """

    def extract_inmem_foms(
        self, inmem_fom_defs, fom_values, context_metadata=None
    ):
        """Extract in-memory FOMs"""
        for context, foms in inmem_fom_defs.items():
            context_key = context
            if context_metadata is not None:
                if isinstance(context, str):
                    context_key = (context, context, frozenset())
                    if context_key not in context_metadata:
                        context_metadata[context_key] = {
                            "name": context,
                            "def_name": context,
                            "vars": {},
                        }

            if context_key not in fom_values:
                fom_values[context_key] = {}
            foms = inmem_fom_defs[context]["foms"]
            for fom in foms:
                fom_conf = inmem_fom_defs[context]["foms"][fom]
                # Currently inmem FOM does not have semantics for expanded vars,
                # so use the already expanded name and unit
                fom_name = fom_conf["fom_name_expanded"]
                # TODO: this can be extended to support derived FOMs,
                # since the `fom_values` contains resolved file-based FOMs
                fom_map_key = fom_conf["fom_map_key"]
                if fom_map_key not in self._fom_map:
                    continue
                fom_value = self._fom_map.get(fom_map_key)
                if fom_value is None:
                    continue
                expanded_fom_value = self.expander.expand_var(fom_value)
                fom_values[context_key][fom_name] = {
                    "value": expanded_fom_value,
                    "units": fom_conf["units_expanded"],
                    "origin": fom_conf["origin"],
                    "origin_type": fom_conf["origin_type"],
                    "fom_type": fom_conf["fom_type"],
                }

    register_phase(
        "analyze_experiments",
        pipeline="analyze",
        run_after=["prepare_analysis"],
    )

    def _analyze_experiments(self, workspace, app_inst=None):
        """Perform experiment analysis.

        This method will build up the fom_values dictionary. Its structure is:

        fom_values[context][fom]

        A fom can show up in any number of explicit contexts (including zero).
        If the number of explicit contexts is zero, the fom is associated with
        the default '(null)' context.

        Success is determined at analysis time as well. This happens by checking if:
         - At least one FOM is extracted
         AND
         - Any defined success criteria pass

        Success criteria are defined within the application.py, but can also be
        injected in a workspace config.
        """
        import ramble.analysis

        strategy_name = getattr(self, "analysis_strategy", None) or "backwards"
        strategy = ramble.analysis.get_strategy(strategy_name, self)
        strategy(workspace)

    register_phase(
        "append_results_to_workspace",
        pipeline="analyze",
        run_after=["analyze_experiments"],
    )

    def _append_results_to_workspace(self, workspace, app_inst=None):
        """Phase for injected experiment results into workspace results

        This allows an experiment to register its results into the workspace,
        so when the workspace dumps results they are included.
        """

        if hasattr(self, "result") and self.result is not None:
            workspace.append_result(self.result.to_dict())

    def calculate_statistics(self, workspace):
        """Calculate statistics for results of repeated experiments

        When repeated experiments are used, this method aggregates the results of
        each experiment's repeats and calculates statistics for each numeric FOM.

        If a FOM is non-numeric, no calculations are performed.

        Statistics are injected into the results file under the base experiment
        namespace.
        """

        def is_numeric_fom(fom):
            """Returns true if a fom value is numeric, and of an applicable type"""

            value = fom["value"]
            try:
                value = float(value)
                if (
                    fom["fom_type"]["name"] is FomType.CATEGORY.name
                    or fom["fom_type"]["name"] is FomType.INFO.name
                ):
                    return False
                return True
            except (ValueError, TypeError):
                return False

        if not self.repeats.is_repeat_base:
            return

        repeat_experiments = {}
        repeat_foms = {}
        first_repeat_exp = ""

        # repeat_experiments dict = {repeat_experiment_namespace: {dict}}
        # repeat_foms dict = {context: {(fom_name, units, origin, origin_type): [list of values]}}
        # origin_type is generated as 'summary::stat_name'

        base_exp_name = self.expander.experiment_name
        base_exp_namespace = self.expander.experiment_namespace

        # Create a list of all repeats by inserting repeat index
        for n in range(1, self.repeats.n_repeats + 1):
            if (
                base_exp_name in self.experiment_set.chained_experiments
                and base_exp_name not in self.experiment_set.experiments
            ):
                insert_idx = base_exp_name.find(".chain")
                repeat_exp_namespace = (
                    base_exp_name[:insert_idx]
                    + f".{n}"
                    + base_exp_name[insert_idx:]
                )
            else:
                base_exp_namespace = self.expander.experiment_namespace
                repeat_exp_namespace = f"{base_exp_namespace}.{n}"
            repeat_experiments[repeat_exp_namespace] = {}
            repeat_experiments[repeat_exp_namespace][
                "base_exp"
            ] = base_exp_namespace
            if n == 1:
                first_repeat_exp = repeat_exp_namespace

        # If repeat_success_strict is true, one failed experiment will fail the whole set
        # If repeat_success_strict is false, any passing experiment will pass the whole set
        status, exp_status_list = self.calculate_repeat_status(
            workspace, return_status_list=True
        )
        self.set_status(status=status)
        self.result.finalize(workspace)

        logger.debug(
            f"Calculating statistics for {self.repeats.n_repeats} repeats of {base_exp_name}"
        )

        results = []

        # Iterate through repeat experiment instances, extract foms, and aggregate them
        for exp in repeat_experiments:
            if exp in self.experiment_set.experiments:
                exp_inst = self.experiment_set.experiments[exp]
            elif exp in self.experiment_set.chained_experiments:
                exp_inst = self.experiment_set.chained_experiments[exp]
            else:
                continue

            # When strict success is off for repeats (loose success), skip failed exps
            if exp_inst.result.status == ExperimentStatus.FAILED:
                continue

            if not exp_inst.result.contexts:
                exp_inst.result.read_cache(workspace, exp_inst)

            if exp_inst.result.contexts:
                for context in exp_inst.result.contexts:
                    context_name = context["name"]

                    if context_name not in repeat_foms:
                        repeat_foms[context_name] = {}

                    for fom in context["foms"]:
                        fom_key = (
                            fom["name"],
                            fom["units"],
                            fom["origin"],
                            fom["origin_type"],
                        )

                        # Stats will not be calculated for non-numeric foms so they're skipped
                        if fom_key not in repeat_foms[context_name]:
                            repeat_foms[context_name][fom_key] = {
                                "fom_type": fom["fom_type"],
                                "fom_values": [],
                            }
                            if is_numeric_fom(fom):
                                repeat_foms[context_name][fom_key][
                                    "fom_is_numeric"
                                ] = True
                            else:
                                repeat_foms[context_name][fom_key][
                                    "fom_is_numeric"
                                ] = False
                            fom_contents = (
                                False,
                                fom["value"],
                                fom["fom_type"],
                            )
                        if repeat_foms[context_name][fom_key][
                            "fom_is_numeric"
                        ]:
                            repeat_foms[context_name][fom_key][
                                "fom_values"
                            ].append(float(fom["value"]))
                        else:
                            repeat_foms[context_name][fom_key][
                                "fom_values"
                            ].append(fom["value"])

        # Iterate through the aggregated foms, calculate stats, and insert into results
        for context, fom_dict in repeat_foms.items():
            if not fom_dict:
                continue

            context_map = {
                "name": context,
                "foms": [],
                "display_name": _get_context_display_name(context),
            }

            summary_foms = []
            if context == _NULL_CONTEXT:
                # Use the app name as the origin of the FOM
                summary_origin = self.name
                n_total_dict = {
                    "value": str(self.repeats.n_repeats),
                    "units": "repeats",
                    "origin": summary_origin,
                    "origin_type": f"summary::{SummaryFoms.N_TOTAL.value}",
                    "name": SummaryFoms.SUMMARY.value,
                    "fom_type": FomType.MEASURE.to_dict(),
                }
                summary_foms.append(n_total_dict)

                n_success = exp_status_list.count(ExperimentStatus.SUCCESS)

                n_success_dict = {
                    "value": str(n_success),
                    "units": "repeats",
                    "origin": summary_origin,
                    "origin_type": f"summary::{SummaryFoms.N_SUCCESS.value}",
                    "name": SummaryFoms.SUMMARY.value,
                    "fom_type": FomType.MEASURE.to_dict(),
                }
                summary_foms.append(n_success_dict)

            for fom_key, fom_contents in fom_dict.items():
                fom_name, fom_units, fom_origin, fom_origin_type = fom_key

                fom_type = fom_contents["fom_type"]
                fom_values = fom_contents["fom_values"]

                if fom_contents["fom_is_numeric"]:

                    calcs = (
                        statistic.report(fom_values, fom_units)
                        for statistic in ramble.util.stats.all_stats
                    )

                    for calc in calcs:
                        if calc[0] == ramble.util.stats.NA:
                            continue
                        fom_calc_dict = {
                            "value": str(calc[0]),
                            "units": calc[1],
                            "origin": fom_origin,
                            "origin_type": calc[2],
                            "name": fom_name,
                            "fom_type": fom_type,
                        }

                        context_map["foms"].append(fom_calc_dict)
                else:
                    # Only elevate non-numeric FOMs when they have the same value for all repeats
                    if len(set(fom_values)) == 1:

                        fom_str_dict = {
                            "value": fom_values[0],
                            "units": fom_units,
                            "origin": fom_origin,
                            "origin_type": fom_origin_type,
                            "name": fom_name,
                            "fom_type": fom_type,
                        }

                        context_map["foms"].append(fom_str_dict)
                    else:
                        continue

            # Display the FOMs in alphabetic order, even if the corresponding log entries
            # may be in different ordering.
            context_map["foms"].sort(key=operator.itemgetter("name"))
            if context == _NULL_CONTEXT:
                context_map["foms"] = summary_foms + context_map["foms"]
            results.append(context_map)

        if results:
            self.result.contexts = results

        workspace.insert_result(self.result.to_dict(), first_repeat_exp)

    def _new_file_dict(self):
        """Create a dictionary to represent a new log file"""
        return {"success_criteria": [], "contexts": {}}

    def analysis_dicts(self, criteria_list):
        """Extract files that need to be analyzed.

        Process figures_of_merit, and return the manipulated dictionaries
        to allow them to be extracted.

        Additionally, ensure the success criteria list is complete.

        Returns:
            files (dict): All files that need to be processed
            file_fom_defs (dict): Definitions of all file-backed FOMs to be extracted
            inmem_fom_defs (dict): Definitions of all in-memory FOMs to be extracted
        """

        files = {}
        file_fom_defs = {}
        inmem_fom_defs = {}

        # Add the object defined criteria
        criteria_list.flush_scope("object_definitions")

        resolved_criteria = {
            crit.name for crit, _ in criteria_list.all_criteria()
        }

        for _, obj_inst in self.objects():
            if obj_inst.success_criteria:
                obj_satisfied_criteria = {}
                for (
                    when_set,
                    criteria_dict,
                ) in obj_inst.success_criteria.items():
                    if not self.expander.satisfies(
                        when_set,
                        variant_set=obj_inst.experiment_variants(),
                    ):
                        continue

                    for name, conf in criteria_dict.items():
                        if name in obj_satisfied_criteria:
                            existing_when_set = obj_satisfied_criteria[name][0]
                            logger.die(
                                f"Success criteria '{name}' in object '{obj_inst.name}' is defined multiple times "
                                f"under conflicting satisfied 'when' conditions:\n"
                                f"  1) {sorted(existing_when_set)}\n"
                                f"  2) {sorted(when_set)}"
                            )
                        obj_satisfied_criteria[name] = (when_set, conf)

                for criteria, (_, conf) in obj_satisfied_criteria.items():
                    if criteria in resolved_criteria:
                        continue

                    resolved_criteria.add(criteria)
                    if conf["mode"] == "string":
                        match = (
                            self.expander.expand_var(conf["match"])
                            if conf["match"] is not None
                            else None
                        )
                        anti_match = (
                            self.expander.expand_var(conf["anti_match"])
                            if conf["anti_match"] is not None
                            else None
                        )
                        criteria_list.add_criteria(
                            "object_definitions",
                            criteria,
                            mode=conf["mode"],
                            match=match,
                            file=conf["file"],
                            anti_match=anti_match,
                            owning_object=obj_inst,
                        )
                    elif conf["mode"] == "fom_comparison":
                        criteria_list.add_criteria(
                            "object_definitions",
                            criteria,
                            conf["mode"],
                            fom_name=conf["fom_name"],
                            fom_context=conf["fom_context"],
                            formula=conf["formula"],
                            owning_object=obj_inst,
                        )

        if "_application_function" not in resolved_criteria:
            criteria_list.add_criteria(
                scope="object_definitions",
                name="_application_function",
                mode="application_function",
                owning_object=self,
            )

        # Extract file paths for all criteria
        for criteria, _ in criteria_list.all_criteria():
            log_path = self.expander.expand_var(criteria.file)

            # Ensure log path is absolute. If not, prepend the experiment run directory
            if (
                not os.path.isabs(log_path)
                and self.expander.experiment_run_dir not in log_path
            ):
                log_path = os.path.join(
                    self.expander.experiment_run_dir, log_path
                )

            if log_path not in files and os.path.exists(log_path):
                files[log_path] = self._new_file_dict()

            if log_path in files:
                files[log_path]["success_criteria"].append(criteria.name)

        # Could push this into the language features in the future
        fom_sources = [self]
        fom_sources.extend(self._modifier_instances)
        if self.workflow_manager is not None:
            fom_sources.append(self.workflow_manager)

        all_contexts = {}
        for source in fom_sources:
            for (
                when_fs,
                source_context_defs,
            ) in source.figure_of_merit_contexts.items():
                if self.expander.satisfies(
                    when_fs, variant_set=self.experiment_variants()
                ):
                    all_contexts.update(source_context_defs)
            extra_vars = (
                source.modded_variables(self)
                if source.origin_type == "modifier"
                else None
            )
            # figures_of_merit[frozenset(when_list)][frozenset(context_list)][fom_name]
            for when_fs, source_contexts in source.figures_of_merit.items():
                if not self.expander.satisfies(
                    when_fs, variant_set=self.experiment_variants()
                ):
                    continue

                for context_fs, source_foms in source_contexts.items():
                    if (
                        not context_fs
                    ):  # FOMs with no defined context are set to the null context
                        context_fs = frozenset([_NULL_CONTEXT])
                        all_contexts[_NULL_CONTEXT] = {}
                    for context in context_fs:
                        if context not in all_contexts:
                            fom_list = str(list(source_foms.keys()))
                            logger.die(
                                f"Figure(s) of merit {fom_list} registered to context "
                                f"'{context}', which is not found. Check FOM and FOM context "
                                "definitions and 'when' conditions."
                            )

                        def _preset_context_dict(dest_def_dict, context):
                            # Copy context definition for contexts used by a FOM
                            if context not in dest_def_dict:
                                dest_def_dict[context] = {
                                    "definition": {},
                                    "foms": {},
                                }
                                if context != _NULL_CONTEXT:
                                    regex_str = self.expander.expand_var(
                                        all_contexts[context]["regex"]
                                    )
                                    dest_def_dict[context]["definition"] = {
                                        "regex": re.compile(regex_str),
                                        "pre_filter": get_literal_from_regex(
                                            regex_str
                                        ),
                                        "format": all_contexts[context][
                                            "output_format"
                                        ],
                                    }

                        for fom, source_def in source_foms.items():
                            is_inmem = source_def["fom_map_key"] is not None
                            dest_def_dict = (
                                inmem_fom_defs if is_inmem else file_fom_defs
                            )
                            _preset_context_dict(dest_def_dict, context)
                            if fom in dest_def_dict[context]["foms"]:
                                logger.warn(
                                    f"FOM {fom} already defined in context {context} by "
                                    f"{dest_def_dict[context]['foms'][fom]['origin']}. "
                                    f"Overwriting with new definition from {source.name}"
                                )
                            else:
                                dest_def_dict[context]["foms"][fom] = {}

                            def _expand_var(var, extra_vars=extra_vars):
                                return self.expander.expand_var(
                                    var, extra_vars=extra_vars
                                )

                            def _try_expand_var_or_none(var: str, expander):
                                try:
                                    return expander.expand_var(
                                        var, allow_passthrough=False
                                    )
                                except ramble.expander.RambleSyntaxError:
                                    return None

                            expanded_regex = (
                                ""
                                if is_inmem
                                else _expand_var(source_def["regex"])
                            )
                            fom_def = {
                                "origin": source.name,
                                "origin_type": source.origin_type,
                                "contexts": set(source_def["contexts"]),
                                "group": (
                                    ""
                                    if is_inmem
                                    else _expand_var(source_def["group_name"])
                                ),
                                "units": _expand_var(source_def["units"]),
                                "regex": (
                                    ""
                                    if is_inmem
                                    else re.compile(expanded_regex)
                                ),
                                "pre_filter": (
                                    ""
                                    if is_inmem
                                    else get_literal_from_regex(expanded_regex)
                                ),
                                "fom_type": source_def["fom_type"].to_dict(),
                                "fom_map_key": source_def["fom_map_key"],
                                # If expansion works (i.e., it doesn't rely on the matched fom
                                # groups), then cache it here to avoid repeated expansion later.
                                "units_expanded": _try_expand_var_or_none(
                                    source_def["units"], self.expander
                                ),
                                "fom_name_expanded": _try_expand_var_or_none(
                                    fom, self.expander
                                ),
                            }

                            dest_def_dict[context]["foms"][fom] = fom_def

                            if is_inmem:
                                continue
                            log_path = _expand_var(source_def["log_file"])
                            # Ensure log path is absolute. If not, prepend the experiment run dir
                            if (
                                not os.path.isabs(log_path)
                                and self.expander.experiment_run_dir
                                not in log_path
                            ):
                                log_path = os.path.join(
                                    self.expander.experiment_run_dir, log_path
                                )

                            if log_path not in files:
                                files[log_path] = self._new_file_dict()

                            if context not in files[log_path]["contexts"]:
                                files[log_path]["contexts"][context] = []
                            files[log_path]["contexts"][context].append(fom)

                            logger.debug(f"Log = {log_path}")
                            logger.debug(f"Conf = {fom_def}")

        return files, file_fom_defs, inmem_fom_defs

    def add_inmem_fom_value(self, fom_map_key, value):
        """Add value to an in-memory FOM"""
        self._fom_map[fom_map_key] = value

    def get_repeat_child_namespaces(self):
        """Return a list of namespaces for all repeat children of this experiment"""
        if not self.repeats.is_repeat_base or not self.experiment_set:
            return []

        base_exp_name = self.expander.experiment_name
        is_chained = (
            base_exp_name in self.experiment_set.chained_experiments
            and base_exp_name not in self.experiment_set.experiments
        )

        if is_chained and ".chain" in base_exp_name:
            idx = base_exp_name.index(".chain")
            prefix, suffix = base_exp_name[:idx], base_exp_name[idx:]
            return [
                f"{prefix}.{n}{suffix}"
                for n in range(1, self.repeats.n_repeats + 1)
            ]

        base = (
            base_exp_name if is_chained else self.expander.experiment_namespace
        )
        return [f"{base}.{n}" for n in range(1, self.repeats.n_repeats + 1)]

    def get_repeat_children(self):
        """Return a list of ApplicationBase instances for all repeat children"""
        if not self.experiment_set:
            return []
        children = []
        for exp in self.get_repeat_child_namespaces():
            child = self.experiment_set.get_experiment(exp)
            if child is not None:
                children.append(child)
        return children

    def calculate_repeat_status(
        self, workspace=None, return_status_list=False
    ):
        """Calculate the status of a repeat base experiment from its children"""
        if not self.repeats.is_repeat_base:
            status = self.get_status()
            return (status, [status]) if return_status_list else status

        children = self.get_repeat_children()
        if not children:
            return (
                (ExperimentStatus.UNKNOWN, [])
                if return_status_list
                else ExperimentStatus.UNKNOWN
            )

        exp_status_list = [c.get_status() for c in children]

        if not exp_status_list or all(
            s == ExperimentStatus.UNKNOWN for s in exp_status_list
        ):
            status = ExperimentStatus.UNKNOWN
            return (status, exp_status_list) if return_status_list else status

        ws = workspace or self.workspace
        strict = getattr(ws, "repeat_success_strict", None)
        if strict is None:
            strict = ramble.config.get(
                "config:repeat_success_strict", default=True
            )

        failed_statuses = {
            ExperimentStatus.FAILED,
            ExperimentStatus.CANCELLED,
            ExperimentStatus.TIMEOUT,
        }
        has_failed = any(s in failed_statuses for s in exp_status_list)
        all_failed = all(s in failed_statuses for s in exp_status_list)
        has_success = any(
            s == ExperimentStatus.SUCCESS for s in exp_status_list
        )
        all_success = all(
            s == ExperimentStatus.SUCCESS for s in exp_status_list
        )

        if strict:
            if has_failed:
                status = ExperimentStatus.FAILED
            elif all_success:
                status = ExperimentStatus.SUCCESS
            else:
                status = ExperimentStatus.UNKNOWN
        else:
            if has_success:
                status = ExperimentStatus.SUCCESS
            elif all_failed:
                status = ExperimentStatus.FAILED
            else:
                status = ExperimentStatus.UNKNOWN

        return (status, exp_status_list) if return_status_list else status

    def read_status(self):
        """Read status from an experiment's status file, if possible.

        Set this experiment's status based on the status file in the experiment
        run directory, if it exists. If it doesn't exist, set its status to
        ExperimentStatus.UNKNOWN (or calculate from children if repeat base).
        """
        if self.repeats.is_repeat_base:
            self.set_status(self.calculate_repeat_status())
            return

        status_path = os.path.join(
            self.expander.expand_var_name(self.keywords.experiment_run_dir),
            self._status_file_name,
        )

        if os.path.isfile(status_path):
            exp_lock = self.experiment_lock
            with lk.ReadTransaction(exp_lock):
                with open(status_path, encoding="utf-8") as f:
                    status_data = json_util.load(f)
                    self.set_status(
                        ExperimentStatus(
                            status_data[self.keywords.experiment_status]
                        )
                    )
        else:
            self.set_status(ExperimentStatus.UNKNOWN)

    def set_status(self, status=ExperimentStatus.UNKNOWN):
        """Set the status of this experiment"""
        self.variables[self.keywords.experiment_status] = status
        self.set_ramble_status(status)

    def get_status(self):
        """Get the status of this experiment"""
        if (
            self.repeats.is_repeat_base
            or self.keywords.experiment_status not in self.variables
        ):
            self.read_status()

        return self.variables[self.keywords.experiment_status]

    def get_ramble_status(self):
        """Get the RAMBLE_STATUS of this experiment (boolifyied status)"""
        return self.variables[self.keywords.RAMBLE_STATUS]

    def set_ramble_status(self, status):
        """Set the RAMBLE_STATUS (boolifyied status) of this experiment"""

        self.variables[self.keywords.RAMBLE_STATUS] = status
        if status != ExperimentStatus.SUCCESS:
            self.variables[self.keywords.RAMBLE_STATUS] = (
                ExperimentStatus.FAILED
            )

    register_phase(
        "write_status", pipeline="analyze", run_after=["analyze_experiments"]
    )
    register_phase(
        "write_status", pipeline="setup", run_after=["make_experiments"]
    )

    def _write_status(self, workspace, app_inst=None):
        """Phase to write an experiment's ramble_status.json file"""

        status_data = {}
        status_data[self.keywords.experiment_status] = (
            self.expander.expand_var_name(self.keywords.experiment_status)
        )

        exp_dir = self.expander.expand_var_name(
            self.keywords.experiment_run_dir
        )

        status_path = os.path.join(exp_dir, self._status_file_name)

        if os.path.exists(exp_dir):
            exp_lock = self.experiment_lock
            with lk.ReadTransaction(exp_lock):
                with open(status_path, "w+", encoding="utf-8") as f:
                    json_util.dump(status_data, f)

    register_phase(
        "write_results_cache",
        pipeline="analyze",
        run_after=["write_status", "append_results_to_workspace"],
    )

    def _write_results_cache(self, workspace, app_inst=None):
        if hasattr(self, "result") and self.result is not None:
            with lk.WriteTransaction(self.experiment_lock):
                self.result.write_cache(self)

    register_phase("deploy_artifacts", pipeline="pushdeployment")

    def _deploy_artifacts(self, workspace, app_inst=None):
        """Copy all relevant ramble objects to the deployment directory.

        All the ramble objects are grouped under a "ramble" directory, and
        further organized based on the object's original repo namespace.

        Package manager (like Spack) may also create its own repos.

        An example:

        object_repos/
        ├── ramble
        │   ├── builtin
        │   │   ├── modifiers
        │   │   │   ├── gcp-metadata
        │   │   │   │   └── modifier.py
        │   │   ├── package_managers
        │   │   │   ├── spack
        │   │   │   │   └── package_manager.py
        │   │   │   └── spack-lightweight
        │   │   │       └── package_manager.py
        │   │   ├── repo.yaml
        │   └── googleaux
        │       ├── applications
        │       │   ├── base-app
        │       │   │   └── application.py
        │       │   └── derived-app
        │       │       └── application.py
        │       └── repo.yaml
        └── spack
            └── obj_repo
                ├── packages
                │   └── my-package
                │       └── package.py
                └── repo.yaml
        """

        def _copy_files(obj_inst, obj_type, root_path):
            flist = ramble.repository.list_object_files(obj_inst, obj_type)
            for type_dir_name, obj_path, repo_namespace in flist:
                obj_src_dir_path = os.path.dirname(obj_path)
                obj_dir_name = os.path.basename(obj_src_dir_path)
                repo_root = os.path.join(root_path, "ramble", repo_namespace)
                obj_dest_dir = os.path.join(
                    repo_root, type_dir_name, obj_dir_name
                )
                shutil.rmtree(obj_dest_dir, ignore_errors=True)
                shutil.copytree(
                    obj_src_dir_path,
                    obj_dest_dir,
                    ignore=shutil.ignore_patterns("*.pyc", "__pycache__"),
                )
                config_path = os.path.join(
                    repo_root, ramble.repository.unified_config
                )
                if not os.path.exists(config_path):
                    with open(config_path, "w+", encoding="utf-8") as f:
                        f.write("repo:\n")
                        f.write(f"  namespace: {repo_namespace}\n")

        repo_path = workspace.deployment_repos_dir

        repo_lock = lk.Lock(os.path.join(repo_path, ".ramble-obj-repos.lock"))

        with lk.WriteTransaction(repo_lock):
            for obj_type, obj in self.objects():
                _copy_files(obj, obj_type, repo_path)

    register_builtin("env_vars", required=True)

    def env_vars(self):
        command = []
        # ensure license variables are set / modified
        # Process one scope at a time, to ensure
        # highest-precedence scopes are processed last
        config_scopes = ramble.config.scopes()
        shell = ramble.config.get("config:shell")

        action_funcs = ramble.util.env.action_funcs

        license_set = set()
        for scope in config_scopes:
            license_conf = ramble.config.config.get_config(
                "licenses", scope=scope
            )
            if license_conf:
                if self.name in license_conf:
                    app_licenses = license_conf[self.name]
                    if app_licenses:
                        # Append logic to source file which contains the exports
                        shell = ramble.config.get("config:shell")
                        license_set.add(
                            f"{source_str(shell)} {{license_input_dir}}/{LICENSE_INC_NAME}"
                        )

        command.extend(license_set)

        # Process environment variable actions
        for env_var_set in self.environment_variable_sets:
            for action, conf in env_var_set.items():
                env_cmds, _ = action_funcs[action](
                    conf, self.expander, set(), shell=shell
                )

                command.extend(cmd for cmd in env_cmds if cmd)

        for mod_inst in self._modifier_instances:
            for env_var_mod in mod_inst.all_env_var_modifications():
                for method in env_var_mod.all_methods:
                    if getattr(env_var_mod, method):
                        conf = {env_var_mod.name: env_var_mod.set}
                        env_cmds, _ = action_funcs[method](
                            getattr(env_var_mod, method),
                            self.expander,
                            set(),
                            shell=shell,
                        )
                        command.extend(cmd for cmd in env_cmds if cmd)

        return command

    def evaluate_success(self):
        """Hook for applications to evaluate custom success criteria

        Expected to perform analysis and return either true or false.
        """

        return True

    def _object_templates(self):
        """Return templates defined from different objects associated with the app_inst"""
        if hasattr(self, "_cached_object_templates"):
            return self._cached_object_templates

        workspace = self.workspace
        run_dir = self.expander.experiment_run_dir
        replacements = workspace.workspace_paths()
        expander = self.expander
        tpl_ext = TEMPLATE_EXTENSION

        def _expand_path(path):
            return ramble.util.path.substitute_path_variables(
                expander.expand_var(path), local_replacements=replacements
            )

        def _get_template_config(obj, name, tpl_config, obj_type):
            # Resolve the source path
            src_path_config = _expand_path(tpl_config["src_path"])
            if not src_path_config.endswith(tpl_ext):
                # Enforce the template extension to template's source path.
                src_path_config = src_path_config + tpl_ext
            if not os.path.isabs(src_path_config):
                # Search up the object chain to resolve source path
                found = False
                object_paths = [
                    e[1]
                    for e in ramble.repository.list_object_files(obj, obj_type)
                ]
                searched_paths = []
                for obj_path in object_paths:
                    src_path = os.path.join(
                        os.path.dirname(obj_path), src_path_config
                    )
                    if os.path.isfile(src_path):
                        found = True
                        break
                    searched_paths.append(src_path)
                if not found:
                    raise ApplicationError(
                        f"Object {obj.name} is missing template file {src_path_config}. "
                        f"Searched paths: {searched_paths}"
                    )
            else:
                if not os.path.isfile(src_path_config):
                    raise ApplicationError(
                        f"Template file {src_path_config} does not exist"
                    )
                src_path = src_path_config

            # Resolve the destination path
            dest_path_config = tpl_config["dest_path"]
            if dest_path_config is None:
                dest_path = os.path.basename(src_path)
                if dest_path.endswith(tpl_ext):
                    dest_path = dest_path[: -len(tpl_ext)]
            else:
                dest_path = _expand_path(dest_path_config)
            if not os.path.isabs(dest_path):
                dest_path = os.path.join(run_dir, dest_path)

            return {
                "name": name,
                **tpl_config,
                "src_path": src_path,
                "dest_path": dest_path,
            }

        cached_templates = []
        for obj_type, obj in self.objects():
            obj_tpls = []
            for when_set, tpl in obj.templates.items():
                if not self.expander.satisfies(
                    when_set, variant_set=self.experiment_variants()
                ):
                    continue

                obj_tpls.extend(
                    _get_template_config(
                        obj, name, tpl_conf, obj_type=obj_type
                    )
                    for name, tpl_conf in tpl.items()
                )
            if obj_tpls:
                cached_templates.append((obj, obj_tpls))

        self._cached_object_templates = cached_templates
        return self._cached_object_templates

    def _get_rendered_template_content(
        self, template_name, extra_vars_origin, rendering_stack=None
    ):
        """Retrieve and fully render template content, expanding includes in-place recursively"""
        if rendering_stack is None:
            rendering_stack = []

        if template_name in rendering_stack:
            cycle = " -> ".join(rendering_stack + [template_name])
            raise ApplicationError(
                f"Circular template inclusion detected: {cycle}"
            )

        rendering_stack.append(template_name)
        try:
            content = None
            extra_vars = extra_vars_origin.copy()

            if template_name in self.workspace._templates:
                content = self.workspace._templates[template_name]["contents"]
            else:
                found = False
                for obj, tpl_configs in self._object_templates():
                    for tpl_config in tpl_configs:
                        if tpl_config["name"] == template_name:
                            src_path = tpl_config["src_path"]
                            content = self.workspace.read_file_content(
                                src_path
                            )
                            extra_vars_dict = tpl_config.get("extra_vars")
                            if extra_vars_dict is not None:
                                extra_vars.update(extra_vars_dict)
                            extra_vars_func_name = tpl_config.get(
                                "extra_vars_func_name"
                            )
                            if extra_vars_func_name is not None:
                                extra_vars_func = getattr(
                                    obj, extra_vars_func_name
                                )
                                extra_vars.update(extra_vars_func())
                            found = True
                            break
                    if found:
                        break

            if content is None:
                raise ApplicationError(
                    f"Template '{template_name}' not found for inclusion."
                )

            def replace_include(match):
                child_tpl_name = match.group(1)
                return self._get_rendered_template_content(
                    child_tpl_name, extra_vars, rendering_stack
                )

            processed_content = re.sub(
                r"include\(\s*\{([^}]+)\}\s*\)", replace_include, content
            )

            return self.expander.expand_var(
                processed_content, extra_vars=extra_vars
            )
        finally:
            rendering_stack.pop()

    def _render_object_templates(self, extra_vars_origin):
        for _, tpl_configs in self._object_templates():
            for tpl_config in tpl_configs:
                rendered = self._get_rendered_template_content(
                    tpl_config["name"], extra_vars_origin, rendering_stack=[]
                )
                out_path = tpl_config["dest_path"]
                perm = tpl_config.get("content_perm", _DEFAULT_CONTENT_PERM)
                with open(out_path, "w+", encoding="utf-8") as f_out:
                    f_out.write(rendered)
                    f_out.write("\n")
                os.chmod(out_path, perm)

    def objects(self, exclude_types=None, yield_all=False):
        """Return a tuple for each object instance associated with the app_inst.

        The tuple format is (obj_type, obj_inst). This is used to iterate over
        all associated objects with the given app_inst.

        Args:
          exclude_types (list(obj_type) | None): object types to exclude
          yield_all (bool): If True, yield all registered objects in the MRO
        """
        if exclude_types is None:
            exclude_types = set()
        else:
            exclude_types = set(exclude_types)

        def _yield_registered(obj_inst):
            if obj_inst is None:
                return

            if not yield_all:
                obj_type = obj_inst._get_object_type()
                if obj_type and obj_type not in exclude_types:
                    yield (obj_type, obj_inst)
                return

            for cls in obj_inst.__class__.__mro__:
                if cls not in ApplicationBase._mro_obj_type_cache:
                    try:
                        spec = importlib.util.find_spec(cls.__module__)
                        if not spec or not spec.origin:
                            ApplicationBase._mro_obj_type_cache[cls] = (
                                None,
                                None,
                            )
                            continue
                        source_file = spec.origin
                    except (TypeError, OSError, AttributeError) as e:
                        # Workaround: Skip classes that do not have accessible source files.
                        # This occurs for base types like 'object' or compiled extensions
                        # in the MRO, which are not relevant for Ramble's inventory.
                        logger.debug(
                            f"Failed to find source for class {cls.__name__}: {e}"
                        )
                        ApplicationBase._mro_obj_type_cache[cls] = (None, None)
                        continue

                    found_type = False
                    for obj_type, repo_path in ramble.repository.paths.items():
                        for repo in repo_path.repos:
                            if source_file.startswith(repo.objects_path):
                                ApplicationBase._mro_obj_type_cache[cls] = (
                                    obj_type,
                                    source_file,
                                )
                                found_type = True
                                break
                        if found_type:
                            break

                    if not found_type:
                        ApplicationBase._mro_obj_type_cache[cls] = (None, None)

                obj_type, source_file = ApplicationBase._mro_obj_type_cache[
                    cls
                ]

                if obj_type is None or obj_type in exclude_types:
                    continue

                if cls == obj_inst.__class__:
                    yield (obj_type, obj_inst)
                else:
                    try:
                        # Workaround: Instantiate base classes using __new__
                        # to avoid side effects from __init__. Base classes
                        # are only used to retrieve metadata, so full
                        # initialization is unnecessary and often fragile.
                        new_inst = cls.__new__(cls)

                        # Set the source file, so its name property works
                        new_inst._file_path = source_file
                        new_inst._is_base_class = True

                        yield (obj_type, new_inst)
                    except (TypeError, AttributeError, ValueError) as e:
                        # If a base class fails to instantiate, it is likely
                        # because it requires arguments that are not
                        # provided here. We can safely skip these as they
                        # are not the concrete classes we are looking for.
                        logger.debug(
                            f"Failed to instantiate base class {cls.__name__}: {e}"
                        )

        object_precedence_order = [
            "_modifier_instances",
            "system",
            "platform",
            "workflow_manager",
            "package_manager",
            None,
        ]

        for attr_name in object_precedence_order:
            if attr_name:
                attr_val = getattr(self, attr_name, None)
                if attr_val and isinstance(attr_val, list):
                    for attr_inst in reversed(attr_val):
                        yield from _yield_registered(attr_inst)
                elif attr_val:
                    yield from _yield_registered(attr_val)
            else:
                yield from _yield_registered(self)

    def require_mpi_variables(self):
        self.keywords.update_keys(
            {
                self.keywords.n_ranks: {
                    "type": ramble.keywords.key_type.required,
                    "level": ramble.keywords.output_level.key,
                },
                self.keywords.processes_per_node: {
                    "type": ramble.keywords.key_type.required,
                    "level": ramble.keywords.output_level.key,
                },
                self.keywords.n_nodes: {
                    "type": ramble.keywords.key_type.required,
                    "level": ramble.keywords.output_level.key,
                },
            }
        )

    def is_mpi_required(self, workload_name):
        for exec_node in self.get_executable_graph(workload_name).walk():
            if isinstance(
                exec_node.attribute,
                ramble.util.executable.CommandExecutable,
            ):
                exec_cmd = exec_node.attribute
                if exec_cmd.mpi and self.expander.expand_var(
                    str(exec_cmd.mpi), typed=True
                ):
                    return True
        return False

    def defined_mpi_vars(self):
        mpi_vars_defined = set()

        for mpi_var in self.mpi_definitions:
            if mpi_var in self.variables:
                val = self.variables[mpi_var]
                if val is not None and str(val).strip() != "":
                    mpi_vars_defined.add(mpi_var)

        return mpi_vars_defined

    def set_required_variables(self, app_inst=None):
        """Set required variables from all objects"""

        def define_mpi_vars():
            mpi_required = self.is_mpi_required(self.expander.workload_name)

            mpi_vars_defined = self.defined_mpi_vars()
            mpi_vars_to_define = set()

            for mpi_var in self.mpi_definitions:
                if mpi_var not in mpi_vars_defined:
                    mpi_vars_to_define.add(mpi_var)

            for var_name in mpi_vars_to_define:
                formula = self.mpi_definitions[var_name]
                value = None
                # If two variables are defined, use the formula to compute the missing ones.
                if len(mpi_vars_defined) >= 2:
                    value = self.expander.expand_var(
                        formula, allow_passthrough=False
                    )
                # If there is not enough information to use the formulas, or they are not required.
                # Set missing vars to 0
                elif not mpi_required:
                    value = 0

                if value is not None:
                    self.define_variable(var_name, value)
                else:
                    self.missing_mpi_variables.add(var_name)

            if mpi_required:
                required_dict = {
                    "type": ramble.keywords.key_type.required,
                    "level": ramble.keywords.output_level.key,
                }
                for var_name in self.mpi_definitions:
                    self.keywords.update_keys({var_name: required_dict})

        define_mpi_vars()

        if self.keywords.accelerators_per_node not in self.variables:
            self.define_variable(self.keywords.accelerators_per_node, 0)
        if self.keywords.n_accelerators not in self.variables:
            self.define_variable(self.keywords.n_accelerators, 0)

        if self.keywords.n_threads not in self.variables:
            self.define_variable(self.keywords.n_threads, 1)

        for _, obj in self.objects():
            logger.debug(f"Setting required variables for {obj.name}")
            self.keywords.update_keys(obj.required_variables)
            if obj is not self and hasattr(obj, "set_required_variables"):
                obj.set_required_variables(self)

    def _format_docs_details(self, out):
        if self.workloads:
            out.write("<dt>Workloads:</dt>\n")
            out.write("<dd>\n")
            for when_set in self.workloads:
                for workload in self.workloads[when_set].values():
                    out.write("<details>\n")
                    out.write(f"<summary>{workload.name}</summary>\n")
                    out.write('<dl class="docutils">\n')
                    if workload.executables:
                        out.write("<dt>Executables:</dt>\n")
                        out.write("<dd>\n")
                        out.write(", ".join(workload.executables))
                        out.write("</dd>\n")
                    if workload.inputs:
                        out.write("<dt>Inputs:</dt>\n")
                        out.write("<dd>\n")
                        all_input_defs = {}
                        for input_conf in self.inputs.values():
                            for (
                                input_name,
                                input_def,
                            ) in input_conf.items():
                                if input_name not in all_input_defs:
                                    all_input_defs[input_name] = input_def

                        out.write('<dl class="docutils">\n')
                        for input_name in workload.inputs:
                            out.write(f"<dt>{escape(input_name, True)}</dt>\n")
                            input_def = all_input_defs.get(input_name)
                            if input_def and input_def.get("description"):
                                out.write("<dd>\n")
                                out.write(
                                    escape(input_def["description"], True)
                                )
                                out.write("</dd>\n")
                        out.write("</dl>\n")
                        out.write("</dd>\n")
                    if workload.variables:
                        out.write("<dt>Variables:</dt>\n")
                        out.write("<dd>\n")
                        out.write('<dl class="docutils">\n')
                        for var_when_set in workload.variables:
                            for var in workload.variables[var_when_set]:
                                out.write(f"<dt>{var.name}</dt>\n")
                                if var.description:
                                    out.write("<dd>\n")
                                    out.write(escape(var.description, True))
                                    out.write("</dd>\n")
                        out.write("</dl>\n")
                        out.write("</dd>\n")
                    out.write("</dl>\n")
                    out.write("</details>\n")
            out.write("</dd>\n")
