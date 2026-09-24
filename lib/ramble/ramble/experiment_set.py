# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import concurrent.futures
import fnmatch
import os
import sys
from enum import Enum
from functools import partial
from typing import Set

import ramble.config
import ramble.context
import ramble.error
import ramble.expander
import ramble.keywords
import ramble.renderer
import ramble.repository
from ramble.expander import Expander
from ramble.namespace import namespace
from ramble.util import cpus, naming
from ramble.util.logger import logger


class ExperimentSet:
    """Class to represent a full set of experiments

    This class contains logic to take sets of variable definitions and generate
    experiments from the variable hierarchy.

    Experiments are housed in the internal self.experiments dictionary. Keys of
    this dictionary are experiment names, while values are application
    instances.
    """

    # In order of lowest to highest precedence
    _contexts = Enum(
        "_contexts",
        ["global_conf", "base", "workspace", "application", "workload", "experiment", "required"],
    )

    def __init__(self, workspace):
        self.keywords = ramble.keywords.keywords
        """Create experiment set class"""
        self.experiments = {}
        self.experiment_order = []
        self.chained_experiments = {}
        self.chained_order = []
        self._workspace = workspace
        self.rendered_experiments = set()
        self._context = {}
        self._filtered_experiments_cache = {}

        for context in self._contexts:
            self._context[context] = ramble.context.Context()

        self.read_config_vars(workspace)

        # Set all workspace variables as base variables.
        workspace_context = ramble.context.Context()
        workspace_context.context_name = workspace.name
        workspace_context.variables = ramble.config.get(namespace.variables)
        workspace_context.env_variables = ramble.config.get(namespace.env_var)
        workspace_context.formatted_executables = ramble.config.get(
            namespace.formatted_executables
        )
        workspace_context.internals = ramble.config.get(namespace.internals)
        workspace_context.modifiers = ramble.config.get(namespace.modifiers)
        workspace_context.zips = ramble.config.get(namespace.zips)
        workspace_context.variants = ramble.config.get(namespace.variants)
        workspace_context.success_criteria = ramble.config.get(namespace.success)
        workspace_context.tables = ramble.config.get(namespace.tables)

        try:
            self.keywords.check_reserved_keys(workspace_context.variables)
        except ramble.keywords.RambleKeywordError as e:
            raise RambleVariableDefinitionError(f"Workspace variable error: {e}") from None

        self._set_context(self._contexts.workspace, workspace_context)

        # Set some base variables from the workspace definition.
        self.set_base_var(self.keywords.log_dir, workspace.log_dir)
        self.set_base_var(
            self.keywords.env_name, Expander.expansion_str(self.keywords.application_spec)
        )

    def read_config_vars(self, workspace):
        global_context = ramble.context.Context()
        global_context.context_name = self._contexts.global_conf.name
        global_context.variables = self.get_config_vars(workspace)
        global_context.env_variables = self.get_config_env_vars(workspace)
        global_context.n_repeats = ramble.config.get("config:n_repeats")
        self._set_context(self._contexts.global_conf, global_context)

    def get_config_vars(self, workspace):
        conf = ramble.config.config.get_config("config")
        if conf and namespace.variables in conf:
            site_vars = conf[namespace.variables]
            return site_vars
        return None

    def get_config_env_vars(self, workspace):
        conf = ramble.config.config.get_config("config")
        if conf and namespace.env_var in conf:
            site_env_vars = conf[namespace.env_var]
            return site_env_vars
        return None

    def set_base_var(self, var, val):
        """Set a base variable definition"""
        self._context[self._contexts.base].variables[var] = val

    def _set_context(self, context, in_context):
        """Abstraction method to set context attributes"""
        if context not in self._contexts:
            raise RambleVariableDefinitionError(f"Context {context} is not a valid context.")

        self._context[context] = in_context

    def set_application_context(self, app_context):
        """Set up current application context"""

        try:
            self.keywords.check_reserved_keys(app_context.variables)
        except ramble.keywords.RambleKeywordError as e:
            raise RambleVariableDefinitionError(
                f"In application {app_context.context_name}: {e}"
            ) from None

        self._set_context(self._contexts.application, app_context)

    def set_workload_context(self, workload_context):
        """Set up current workload context"""

        try:
            self.keywords.check_reserved_keys(workload_context.variables)
        except ramble.keywords.RambleKeywordError as e:
            namespace = f"{self.application_namespace}.{workload_context.context_name}"
            raise RambleVariableDefinitionError(f"In workload {namespace}: {e}") from None

        self._set_context(self._contexts.workload, workload_context)

    def set_experiment_context(
        self,
        experiment_context,
        warn_validation=True,
        die_on_validate_error=True,
        chained=False,
    ) -> list:
        """Set up current experiment context"""

        try:
            self.keywords.check_reserved_keys(experiment_context.variables)
        except ramble.keywords.RambleKeywordError as e:
            namespace = f"{self.workload_namespace}.{experiment_context.templates}"
            raise RambleVariableDefinitionError(f"In experiment {namespace}: {e}") from None

        self._set_context(self._contexts.experiment, experiment_context)
        return self._ingest_experiments(
            warn_validation=warn_validation,
            die_on_validate_error=die_on_validate_error,
            chained=chained,
        )

    @property
    def application_namespace(self):
        """Property to return application namespace (application spec)"""
        if self._context[self._contexts.application]:
            app_context = self._context[self._contexts.application]

            if app_context.version:
                return f"{app_context.context_name}@{app_context.version}"

            return app_context.context_name
        return None

    @property
    def workload_namespace(self):
        """Property to return workload namespace

        Workload namespaces are of the form: application_spec.workload_name
        """
        app_ns = self.application_namespace
        wl_ns = self._context[self._contexts.workload].context_name

        if app_ns and wl_ns:
            return f"{app_ns}.{wl_ns}"

        return None

    @property
    def experiment_namespace(self):
        """Property to return experiment namespace

        Experiment namespaces are of the form: application_spec.workload_name.experiment_name
        """
        wl_ns = self.workload_namespace
        exp_ns = self._context[self._contexts.experiment].context_name

        if wl_ns and exp_ns:
            return f"{wl_ns}.{exp_ns}"
        return None

    def _setup_experiment_minimal(
        self,
        workload_template_name,
        variables,
        context,
    ):
        """Perform minimal setup for an experiment instance."""
        expander = ramble.expander.Expander(variables, self)

        final_app_spec = expander.expand_var_name(
            self.keywords.application_spec, allow_passthrough=False
        )

        # Define some standard variables before the application is created
        # to ensure variables and variants can be defined correctly.
        variables[self.keywords.workload_template_name] = workload_template_name

        # Setup the application instance
        app_inst = ramble.repository.get(final_app_spec)
        variables[self.keywords.application_name] = app_inst.name
        app_inst.set_internals(context.internals)
        app_inst.set_variables_and_variants(variables, context.variants, self._workspace, self)
        app_inst.validate_version()
        app_inst.set_active_workload()
        app_inst.set_modifiers(context.modifiers)
        app_inst.set_required_variables()
        app_inst.set_chained_experiments(context.chained_experiments)
        app_inst.set_env_variable_sets(context.env_variables)
        app_inst.set_template(context.is_template)
        app_inst.set_tags(context.tags)
        app_inst.set_formatted_executables(context.formatted_executables)
        if app_inst.package_manager is not None:
            app_inst.package_manager.define_missing_packages(self._workspace)
            app_inst.define_variable(
                self.keywords.env_path,
                os.path.join(
                    app_inst.package_manager.package_manager_dir(self._workspace),
                    Expander.expansion_str(self.keywords.env_name),
                ),
            )

        return app_inst

    def _prepare_experiment(
        self,
        workload_template_name,
        exp_template_name,
        variables,
        context,
        repeats,
    ):
        """Prepare an experiment instance

        Create an experiment instance based on the input variables, context,
        repeats, and template name.

        Args:
            workload_template_name (str): Template name for workload
            experiment_template_name (str): Template name for experiments
            variables (dict): Dictionary of variables for this experiment
            context (Context): Context object for this experiment
            repeats (Repeats): Repeats object for this experiment

        Returns:
            app_inst: Instance of an application class for this experiment
        """

        experiment_suffix = ""
        # After generating the base experiment, append the index to repeat experiments
        variables[self.keywords.is_repeat_parent] = repeats.is_repeat_base
        variables[self.keywords.is_repeat_child] = False
        variables[self.keywords.repeat_index] = 0
        if repeats.repeat_index:
            experiment_suffix = f".{repeats.repeat_index}"
            variables[self.keywords.is_repeat_child] = True
            variables[self.keywords.repeat_index] = repeats.repeat_index

        app_inst = self._setup_experiment_minimal(workload_template_name, variables, context)

        final_wl_name = app_inst.expander.expand_var_name(
            self.keywords.workload_name, allow_passthrough=False
        )
        app_inst.define_variable(self.keywords.workload_name, final_wl_name)

        app_inst.repeats = repeats

        # Setup experiment name after modifiers are defined
        final_exp_name = app_inst.expander.expand_var(
            exp_template_name + experiment_suffix, allow_passthrough=False
        )

        app_inst.define_variable(
            self.keywords.experiment_template_name, exp_template_name + experiment_suffix
        )
        app_inst.define_variable(self.keywords.experiment_name, final_exp_name)

        app_inst.define_variable(
            self.keywords.log_file, os.path.join("{experiment_run_dir}", "{experiment_name}.out")
        )

        app_inst.define_variable(
            self.keywords.simplified_application_namespace,
            (
                naming.simplify_name(
                    app_inst.expander.expand_var_name(self.keywords.application_namespace)
                )
            ),
        )
        app_inst.define_variable(
            self.keywords.simplified_workload_namespace,
            naming.simplify_name(
                app_inst.expander.expand_var_name(self.keywords.workload_namespace)
            ),
        )
        app_inst.define_variable(
            self.keywords.simplified_experiment_namespace,
            naming.simplify_name(
                app_inst.expander.expand_var_name(self.keywords.experiment_namespace)
            ),
        )
        for name, value in self._workspace.workspace_paths().items():
            app_inst.define_variable(name, value)

        app_inst.define_variables_for_template_path()

        experiment_namespace = app_inst.expander.experiment_namespace
        app_inst.define_variable(self.keywords.experiment_namespace, experiment_namespace)

        return app_inst

    def _get_used_variables(
        self,
        workload_template_name,
        exp_template_name,
        variables,
        context,
    ):
        app_inst = self._setup_experiment_minimal(workload_template_name, variables, context)

        # The `_get_used_variables` is only called for the base experiment,
        # so no need to consider repeat suffix.
        exp_name = app_inst.expander.expand_var(exp_template_name, allow_passthrough=False)

        app_inst.define_variable(self.keywords.experiment_template_name, exp_template_name)
        app_inst.define_variable(self.keywords.experiment_name, exp_name)

        app_inst.define_variable(
            self.keywords.log_file, os.path.join("{experiment_run_dir}", "{experiment_name}.out")
        )
        app_inst.set_success_list(context.success_criteria)
        return app_inst.build_used_variables()

    def _process_render_object(
        self,
        render_item,
        workload_template_name,
        experiment_template_name,
        final_context,
        excluded_experiments,
    ):
        """Helper to render a base and its repeated experiments, for parallel execution."""
        experiment_vars, repeats = render_item
        processed_experiments = []
        wl_stats = {}
        # Expand and prepare base and repeated experiments
        # TODO: Exploit the relationship between base and repeated experiments,
        # to save up redundant works.
        # For instance, caching may be enabled for expanders across these experiments.
        for n in range(repeats.n_repeats + 1):
            cur_repeats = ramble.repeats.Repeats()
            if repeats.is_repeat_base:
                if n == 0:
                    cur_repeats.set_repeats(True, repeats.n_repeats)
                else:
                    cur_repeats.set_repeat_index(n)

            app_inst = self._prepare_experiment(
                workload_template_name,
                experiment_template_name,
                experiment_vars.copy(),
                final_context,
                cur_repeats,
            )

            final_exp_name = app_inst.expander.expand_var_name(self.keywords.experiment_name)
            final_exp_namespace = app_inst.expander.expand_var_name(
                self.keywords.experiment_namespace
            )

            wl_name = app_inst.expander.workload_name
            if wl_name not in wl_stats:
                wl_stats[wl_name] = {"passed_global": 0, "dropped_wl": 0}

            # Skip explicitly excluded experiments
            if final_exp_name not in excluded_experiments:
                active = True
                if namespace.where in final_context.exclude:
                    for expression in final_context.exclude[namespace.where]:
                        if app_inst.expander.evaluate_predicate(expression):
                            active = False
                            break

                if active:
                    wl_stats[wl_name]["passed_global"] += 1
                    wl_inst = app_inst.get_workload()
                    if wl_inst:
                        for expression in wl_inst.where:
                            if not app_inst.expander.evaluate_predicate(expression):
                                active = False
                                wl_stats[wl_name]["dropped_wl"] += 1
                                break
                        if active:
                            for expression in wl_inst.exclude_where:
                                if app_inst.expander.evaluate_predicate(expression):
                                    active = False
                                    wl_stats[wl_name]["dropped_wl"] += 1
                                    break

                if active:
                    app_inst.read_status()
                    processed_experiments.append((app_inst, final_exp_namespace, n == 0))
        return processed_experiments, wl_stats

    def render_experiment_set(
        self,
        app_name,
        workload_name,
        experiment_context,
        warn_validation=True,
        die_on_validate_error=True,
        chained=False,
    ) -> list:
        """Render a set of experiments for a specific application and workload

        This method will render a new set of experiments for a given app (input
        with app_name) and workload (input with workload_name, but could be
        an indirect variable reference). It takes a context object for the
        experiment, and will process any vectors and matrices to create
        multiple experiments.

        If `chained=True` these are added to this experiment set's
        chained_experiments list, rather than the base experiments list. Upon
        completion, all rendered experiment instances are returned in a list,
        to allow further processing. For example, if one wants to render
        chained experiments from the child experiment.

        Args:
            app_name (str): Name of application to render experiments for
            workload_name (str): Name, or template, of workload(s) to render
                                 experiments for
            experiment_context (ramble.context.Context): Context object for the
                                                         set of experiments to render
            warn_validation (bool): Whether validation warnings should print or not
            die_on_validate_error (bool): Whether validation errors should be fatal or not
            chained (bool): Whether the experiments are chained experiments or not

        Returns:
            list: List of application instances from the rendered set of experiments
        """
        app_context = ramble.context.Context()
        app_context.context_name = app_name

        wl_context = ramble.context.Context()
        wl_context.context_name = workload_name
        self.set_application_context(app_context)
        self.set_workload_context(wl_context)
        return self.set_experiment_context(
            experiment_context,
            warn_validation=warn_validation,
            die_on_validate_error=die_on_validate_error,
            chained=chained,
        )

    def _ingest_experiments(
        self, warn_validation=True, die_on_validate_error=True, chained=False
    ) -> list:
        """Ingest experiments based on the current context.

        Merge all contexts, and render individual experiments. Track these
        experiments within this experiment set.

        Args:
            warn_validation (bool): Whether rendering should print
                                    validation warnings or not
            die_on_validated_error (bool): Whether rendering should kill
                                           execution when validation errors are
                                           encountered or not
            chained (bool): Whether the rendered experiments should be added to
                            the chained experiments list, or the base
                            experiments list.

        Returns:
            list: List of application instances that are rendered
        """

        no_var_contexts = [
            self._contexts.global_conf,
            self._contexts.base,
            self._contexts.required,
        ]
        final_context = ramble.context.Context()

        for context in self._contexts:
            final_context.merge_context(self._context[context])

        for context in self._contexts:
            if context not in no_var_contexts:
                var_name = f"{context.name}_name"
                if var_name not in final_context.variables:
                    final_context.variables[var_name] = self._context[context].context_name

        # Set namespaces
        final_context.variables[self.keywords.application_spec] = self.application_namespace
        final_context.variables[self.keywords.application_namespace] = self.application_namespace
        final_context.variables[self.keywords.workload_namespace] = self.workload_namespace
        final_context.variables[self.keywords.experiment_namespace] = self.experiment_namespace

        # Set required variables for directories.
        final_context.variables[self.keywords.application_run_dir] = os.path.join(
            self._workspace.experiment_dir, Expander.expansion_str(self.keywords.application_spec)
        )
        final_context.variables[self.keywords.application_input_dir] = os.path.join(
            self._workspace.input_dir, Expander.expansion_str(self.keywords.application_spec)
        )

        final_context.variables[self.keywords.workload_run_dir] = os.path.join(
            Expander.expansion_str(self.keywords.application_run_dir),
            Expander.expansion_str(self.keywords.workload_name),
        )
        final_context.variables[self.keywords.workload_input_dir] = os.path.join(
            Expander.expansion_str(self.keywords.application_input_dir),
            Expander.expansion_str(self.keywords.workload_name),
        )

        final_context.variables[self.keywords.license_input_dir] = os.path.join(
            self._workspace.shared_license_dir,
            Expander.expansion_str(self.keywords.application_spec),
        )

        final_context.variables[self.keywords.experiment_run_dir] = os.path.join(
            Expander.expansion_str(self.keywords.workload_run_dir),
            Expander.expansion_str(self.keywords.experiment_name),
        )

        workload_template_name = final_context.variables[self.keywords.workload_name]
        experiment_template_name = final_context.variables[self.keywords.experiment_name]

        renderer = ramble.renderer.Renderer()

        render_group = ramble.renderer.RenderGroup("experiment", "create")
        render_group.variables = final_context.variables
        render_group.zips = final_context.zips
        render_group.matrices = final_context.matrices
        render_group.n_repeats = final_context.n_repeats
        render_group.used_variables = set()

        excluded_experiments = set()
        if final_context.exclude:
            exclude_group = ramble.renderer.RenderGroup("experiment", "exclude")
            exclude_group.copy_contents(render_group)
            perform_explicit_exclude = exclude_group.from_dict(
                experiment_template_name, final_context.exclude
            )

            if perform_explicit_exclude:
                for exclude_exp_vars, _ in renderer.render_objects(
                    exclude_group, ignore_used=False
                ):
                    expander = ramble.expander.Expander(exclude_exp_vars, self)
                    exclude_exp_name = expander.expand_var(
                        experiment_template_name, allow_passthrough=False
                    )
                    excluded_experiments.add(exclude_exp_name)

        exclude_where = []
        if final_context.exclude:
            if namespace.where in final_context.exclude:
                exclude_where = final_context.exclude[namespace.where]

        tracking_group = ramble.renderer.RenderGroup("experiment", "create")
        tracking_group.variables = final_context.variables
        tracking_group.zips = final_context.zips
        tracking_group.matrices = final_context.matrices
        tracking_group.n_repeats = final_context.n_repeats
        tracking_group.used_variables = set()

        used_variables: Set[str] = set()
        tracking_gen = renderer.render_objects(
            tracking_group, exclude_where=exclude_where, ignore_used=False, fatal=False
        )
        try:
            tracking_vars, _ = next(tracking_gen)
            exp_used_variables = self._get_used_variables(
                workload_template_name,
                experiment_template_name,
                tracking_vars,
                final_context,
            )
            used_variables = used_variables.union(exp_used_variables)
        except StopIteration:
            pass

        if exclude_where:
            temp_vars = final_context.variables.copy()
            if "tracking_vars" in locals():
                temp_vars.update(tracking_vars)

            temp_expander = ramble.expander.Expander(temp_vars, self)
            for where in exclude_where:
                try:
                    temp_expander.expand_var(where)
                except ramble.error.RambleError:
                    pass
            used_variables.update(temp_expander._used_variables)

        render_group.used_variables = used_variables.copy()

        workload_names = set()
        rendered_instances = []

        render_list = renderer.render_objects(render_group, exclude_where=exclude_where)

        all_processed_experiments = []

        worker_func = partial(
            self._process_render_object,
            workload_template_name=workload_template_name,
            experiment_template_name=experiment_template_name,
            final_context=final_context,
            excluded_experiments=excluded_experiments,
        )

        free_threading = hasattr(sys, "_is_gil_enabled") and (not sys._is_gil_enabled())
        if free_threading:
            # From experimentation, using more workers incurs overhead that discounts the benefit.
            # The tests were done against a workspace with plenty of parallelism to exploit,
            # and on a M4 laptop with 10 p-cores. For now, start with at most 2 workers.
            max_workers = min(2, cpus.cpus_available())
        else:
            max_workers = 1

        if max_workers == 1:
            results = [worker_func(item) for item in render_list]
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                results = list(executor.map(worker_func, render_list))

        overall_wl_stats = {}
        for processed_experiments, wl_stats in results:
            all_processed_experiments.extend(processed_experiments)
            for wl_name, stats in wl_stats.items():
                if wl_name not in overall_wl_stats:
                    overall_wl_stats[wl_name] = {
                        "passed_global": 0,
                        "dropped_wl": 0,
                        "processed": 0,
                    }
                overall_wl_stats[wl_name]["passed_global"] += stats["passed_global"]
                overall_wl_stats[wl_name]["dropped_wl"] += stats["dropped_wl"]

        # The results are now processed serially to update the experiment set state
        for app_inst, final_exp_namespace, is_base_experiment in all_processed_experiments:
            logger.debug(f"   Final name: {final_exp_namespace}")

            if final_exp_namespace in self.rendered_experiments:
                left_inst = self.get_experiment(final_exp_namespace)
                left_vars = left_inst.variables
                right_vars = app_inst.variables
                lkeys = set(left_vars.keys())
                rkeys = set(right_vars.keys())

                # Determine variables that are only in one of the two experiments
                left_unique_vars = lkeys - rkeys
                right_unique_vars = rkeys - lkeys
                common_vars = lkeys & rkeys

                independent_vars = set()
                for matrix in render_group.matrices:
                    for var_or_zip in matrix:
                        if var_or_zip in render_group.zips:
                            independent_vars.update(render_group.zips[var_or_zip])
                        else:
                            independent_vars.add(var_or_zip)
                for zip_vars in render_group.zips.values():
                    independent_vars.update(zip_vars)

                for var, val in final_context.variables.items():
                    if isinstance(val, list):
                        independent_vars.add(var)

                differing_independent_vars = [
                    var
                    for var in independent_vars
                    if var in left_vars and var in right_vars and left_vars[var] != right_vars[var]
                ]

                missing_vars = [
                    var
                    for var in differing_independent_vars
                    if var not in app_inst.expander._used_variables
                ]

                logger.warn(f"Two experiments are defined with the name {final_exp_namespace}")

                exp_template_var = self.keywords.experiment_template_name
                prev_block = left_vars.get(exp_template_var, "unknown")
                new_block = right_vars.get(exp_template_var, "unknown")

                if prev_block != new_block:
                    logger.warn(
                        "  -> Collision Origin: Across different YAML "
                        f"experiment blocks: '{prev_block}' vs '{new_block}'"
                    )
                elif independent_vars:
                    logger.warn(
                        "  -> Collision Origin: Within the same YAML "
                        f"experiment block: '{prev_block}' "
                        "(Matrix/Vector Expansion)"
                    )
                else:
                    logger.warn(
                        "  -> Collision Origin: Static definition "
                        "(No Matrix/Vector expansion active)"
                    )

                # Print warnings about experiment differences
                if left_unique_vars:
                    logger.warn("Variables unique to previously defined experiment:")
                    for var in left_unique_vars:
                        logger.warn(f"  - {var}")

                if right_unique_vars:
                    logger.warn("Variables unique to newly defined experiment:")
                    for var in right_unique_vars:
                        logger.warn(f"  - {var}")

                print_header = True
                for var in common_vars:
                    if left_vars[var] != right_vars[var]:
                        if print_header:
                            logger.warn("Variable differences between experiment definitions:")
                            print_header = False

                        diff = {"previous": left_vars[var], "new": right_vars[var]}
                        logger.warn(f"  - {var}: {diff}")

                if missing_vars:
                    logger.warn("")
                    logger.warn(
                        "==> SUGGESTION: Your experiment name template "
                        "does not distinguish between parallel expansions."
                    )
                    logger.warn(
                        "    To make the namespaces unique, add one or more "
                        "of these differing matrix variables into your "
                        f"'{prev_block}' template:"
                    )
                    for var in missing_vars:
                        logger.warn(f"    -> {{{var}}}")
                    logger.warn("")
                elif not independent_vars and prev_block == new_block:
                    logger.warn("")
                    logger.warn(
                        "==> SUGGESTION: Multiple distinct experiment "
                        "blocks in your YAML are using the same literal name."
                    )
                    logger.warn(
                        "    Rename one of the "
                        f"'{prev_block}' experiment blocks in your "
                        "YAML file."
                    )
                    logger.warn("")

                logger.die(f"Experiment {final_exp_namespace} is not unique.")

            # Only need to validate the base experiment
            if is_base_experiment:
                try:
                    app_inst.validate_experiment(
                        warn_validation=warn_validation,
                        die_on_validate_error=die_on_validate_error,
                    )
                except ramble.keywords.RambleKeywordError as e:
                    if die_on_validate_error:
                        raise RambleVariableDefinitionError(
                            f"In experiment {final_exp_namespace}: {e}"
                        ) from None

            workload_names.add(app_inst.expander.workload_name)
            if app_inst.expander.workload_name in overall_wl_stats:
                overall_wl_stats[app_inst.expander.workload_name]["processed"] += 1

            app_inst.define_variable(
                self.keywords.experiment_index,
                len(self.experiments) + len(self.chained_experiments) + 1,
            )
            app_inst.set_success_list(final_context.success_criteria)
            self.rendered_experiments.add(final_exp_namespace)
            rendered_instances.append(app_inst)
            if not chained:
                self.experiments[final_exp_namespace] = app_inst
                self.experiment_order.append(final_exp_namespace)
            else:
                self.add_chained_experiment(app_inst.expander.experiment_name, app_inst)

        for app_inst in rendered_instances:
            if app_inst.repeats.is_repeat_base:
                app_inst.read_status()

        for wl_name, stats in overall_wl_stats.items():
            if stats["passed_global"] > 0 and stats["processed"] == 0 and stats["dropped_wl"] > 0:
                logger.warn(
                    f"Workload {wl_name} generated zero valid experiments because they were "
                    "all filtered out by the workload's internal clauses."
                )

        self.define_scoped_tables(workload_names, experiment_template_name)
        return rendered_instances

    def define_scoped_tables(self, workload_names, experiment_template_name):
        # Generate focused tables for results
        app_context = self._context[self._contexts["application"]]
        for table in app_context.tables:
            results_table = self._workspace.results_tables.add_table_template(table)
            results_table.add_where(
                f"'{{application_name}}' == '{app_context.context_name}'",
            )

        wl_context = self._context[self._contexts["workload"]]
        for table in wl_context.tables:
            for workload_name in workload_names:
                results_table = self._workspace.results_tables.add_table_template(table)
                results_table.add_where(
                    [
                        f"'{{application_name}}' == '{app_context.context_name}'",
                        f"'{{workload_name}}' == '{workload_name}'",
                    ]
                )

        exp_context = self._context[self._contexts["experiment"]]
        for table in exp_context.tables:
            for workload_name in workload_names:
                results_table = self._workspace.results_tables.add_table_template(table)
                results_table.add_where(
                    [
                        f"'{{application_name}}' == '{app_context.context_name}'",
                        f"'{{workload_name}}' == '{workload_name}'",
                        f"'{experiment_template_name}' in '{{experiment_name}}'",
                    ]
                )

    def build_experiment_chains(self):
        base_experiments = self.experiment_order.copy()

        for experiment in base_experiments:
            instance = self.experiments[experiment]
            instance.create_experiment_chain()

    def all_experiment_tags(self):
        """Aggregate all tags from experiments in this experiment set

        Returns:
            set[str]: A set of all tags from the experiment set.
        """
        all_tags = set()
        for _, inst, _ in self.all_experiments():
            if inst.experiment_tags:
                for tag in inst.experiment_tags:
                    all_tags.add(tag)
        return all_tags

    def all_experiments(self):
        """Iterator over all experiments in this set"""
        count = 1

        for exp, inst in self.experiments.items():
            if inst.is_actionable:
                yield exp, inst, count
                count += 1

        for exp, inst in self.chained_experiments.items():
            if inst.is_actionable:
                yield exp, inst, count
                count += 1

    def template_experiments(self):
        """Iterator over template experiments in this set"""

        for exp, inst in self.experiments.items():
            if inst.is_template:
                yield exp, inst

        for exp, inst in self.chained_experiments.items():
            if inst.is_template:
                yield exp, inst

    def num_experiments(self):
        """Return the number of total experiments in this set"""
        count = 0
        for _, _, _ in self.all_experiments():
            count += 1
        return count

    def num_filtered_experiments(self, filters):
        """Return the number of filtered experiments in this set"""
        return len(self.filtered_experiments(filters))

    def clear_filter_cache(self):
        """Clear the filtered experiments cache"""
        self._filtered_experiments_cache.clear()

    def filtered_experiments(self, filters):
        """Return a filtered set of all experiments based on a logical expression

        Exclusion takes overrides inclusion. If conflicting filters are
        provided which both include, and exclude the same experiment, the
        experiment will be excluded.

        Args:
            expression: A logical expression to evaluate, with each experiment
        Yields:
            exp: The name of the experiment, if expression results in True
            inst: An application instance representing the experiment
        """
        include_where = tuple(sorted(filters.include_where)) if filters.include_where else ()
        exclude_where = tuple(sorted(filters.exclude_where)) if filters.exclude_where else ()
        tags = tuple(sorted(filters.tags)) if filters.tags else ()
        cache_key = (include_where, exclude_where, tags)

        if cache_key in self._filtered_experiments_cache:
            return self._filtered_experiments_cache[cache_key]

        filtered_list = []
        for exp, inst, idx in self.all_experiments():
            active = True

            if inst.repeats.is_repeat_base:
                inst.read_status()

            if filters.include_where:
                for expression in filters.include_where:
                    if not inst.expander.evaluate_predicate(expression):
                        active = False
                        break
            if not active:
                continue

            if filters.exclude_where:
                for expression in filters.exclude_where:
                    if inst.expander.evaluate_predicate(expression):
                        active = False
                        break
            if not active:
                continue

            if filters.tags:
                if not inst.has_tags(filters.tags):
                    active = False

            if active and inst.is_actionable:
                filtered_list.append((exp, inst, idx))

        self._filtered_experiments_cache[cache_key] = filtered_list
        return filtered_list

    def add_chained_experiment(self, name, instance):
        if name in self.chained_experiments:
            raise RambleExperimentSetError(
                "Cannot add already defined chained "
                + f"experiment {name} to this experiment set."
            )
        self.chained_experiments[name] = instance
        self.chained_order.append(name)

    def search_primary_experiments(self, pattern):
        """Search primary experiments using a glob syntax.

        NOTE: This does not search experiments defined in an experiment chain
        """
        return fnmatch.filter(self.experiment_order, pattern)

    def get_experiment(self, experiment):
        if experiment in self.experiments:
            return self.experiments[experiment]
        if experiment in self.chained_experiments:
            return self.chained_experiments[experiment]
        return None

    def get_var_from_experiment(self, experiment, variable):
        """Lookup a variable in a given experiment

        Does not error if invalid values are passed in, to allow @ symbol to
        pass through to rendered content.

        Args:
            experiment: A fully qualified experiment name (application.workload.experiment)
            variable: Name of variable to look up
        """

        exp_app = self.get_experiment(experiment)
        if not exp_app:
            return None

        return exp_app.expander.expand_var(variable)


class RambleExperimentSetError(ramble.error.RambleError):
    """Super class for all experiment set errors"""


class RambleVariableDefinitionError(RambleExperimentSetError):
    """Error when a ramble variable definition is invalid"""
