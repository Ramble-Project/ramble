# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import collections
import contextlib
import functools
from typing import Any, Callable, List, Optional, Union

import ramble.language.language_base
import ramble.language.language_helpers
import ramble.success_criteria
import ramble.variants
from ramble.definitions.versions import ObjectVersion
from ramble.util.foms import FomType
from ramble.util.logger import logger
from ramble.util.spec_utils import SoftwareSpec

"""This module contains directives directives that are shared between multiple object types

Directives are functions that can be called inside an object
definition to modify the object, for example:

    .. code-block:: python

      class Gromacs(ExecutableApplication):
          # Required package directive
          required_package("gromacs", when=["package_manager_family=spack"])

In the above example, "required_package" is a ramble directive

Directives defined in this module are used by multiple object types, which
inherit from the SharedMeta class.
"""


SharedMeta = ramble.language.language_base.DirectiveMeta
shared_directive = functools.partial(
    ramble.language.language_base.DirectiveMeta.directive, language_type="shared"
)


def _add_specs(
    obj,
    target_dict_name,
    directive_name,
    name,
    pkg_spec,
    compiler=None,
    compiler_spec=None,
    package_manager=None,
    inject_if_missing=False,
    when=None,
):
    when_list = ramble.language.language_helpers.build_when_list(when, obj, name, directive_name)

    if package_manager is not None:
        logger.warn(
            f"The `package_manager` argument of the {directive_name} "
            f"directive in object {obj.name} is deprecated. Please "
            "transition this to use the `when` argument instead."
        )

    target_dict = getattr(obj, target_dict_name)
    if name not in target_dict:
        target_dict[name] = []

    target_dict[name].append(
        SoftwareSpec(
            name,
            pkg_spec,
            compiler=compiler,
            compiler_spec=compiler_spec,
            inject_if_missing=inject_if_missing,
            when=when_list,
        )
    )


def _add_list_attributes(obj, attr_name, values):
    base_list = getattr(obj, attr_name, [])
    setattr(obj, attr_name, sorted(set(base_list + list(values))))


@shared_directive(dicts=("executables", "custom_edit_functions"), init_value={})
def edit_file(
    name,
    file_path,
    match=None,
    replace=None,
    append=None,
    prepend=None,
    function=None,
    fail_on_error=True,
    when=None,
    **kwargs,
):
    """Adds an edit_file executable to this object

    Defines a new executable that uses Ramble's helper script to edit a file.

    Args:
        name (str): Name of the executable
        file_path (str): Path to the file to edit
        match (str): Regex pattern to match
        replace (str): Replacement string
        append (str): String to append to the end of the file
        prepend (str): String to prepend to the beginning of the file
        function (callable): A Python function to be used for editing the file.
                             The function must accept a single string argument
                             (the file content) and return a string (the modified
                             content). It must be a named top-level function.
                             Note: any imports or global variables used by the
                             function must be defined within the function body
                             itself, as only the function's source code is
                             serialized.
        fail_on_error (bool): If true, the experiment fails if the edit fails.
                              Defaults to True.
        when (list | None): List of when conditions to apply to directive
    """

    def _execute_edit_file(obj):
        import inspect
        import shlex

        from ramble.util.executable import CommandExecutable
        from ramble.util.file_editor import get_file_editor_exec_path

        origin_str = f"{getattr(obj, 'origin_type', 'object')} '{obj.name}'"

        if bool(match) != (replace is not None):
            raise ramble.language.language_helpers.DirectiveError(
                f"Directive '{name}' in {origin_str} requires both 'match' and 'replace' "
                "to be specified together."
            )

        if not any([match, append, prepend, function]):
            raise ramble.language.language_helpers.DirectiveError(
                f"Directive '{name}' in {origin_str} requires at least one action "
                "(match/replace, append, prepend, or function) to be specified."
            )

        script_path = get_file_editor_exec_path()
        template = [f'python "{script_path}" ' f"--mode regex --file {shlex.quote(file_path)}"]
        if match:
            template[0] += f" --match {shlex.quote(match)}"
        if replace is not None:
            template[0] += f" --replace {shlex.quote(replace)}"
        if append:
            template[0] += f" --append {shlex.quote(append)}"
        if prepend:
            template[0] += f" --prepend {shlex.quote(prepend)}"
        if function:
            import textwrap

            if not inspect.isfunction(function) or function.__name__ == "<lambda>":
                raise ramble.language.language_helpers.DirectiveError(
                    f"Directive '{name}' in {origin_str} requires a named top-level "
                    "function, not a lambda or a method."
                )

            sig = inspect.signature(function)
            if len(sig.parameters) != 1 or "self" in sig.parameters:
                raise ramble.language.language_helpers.DirectiveError(
                    f"Directive '{name}' in {origin_str} requires a function that "
                    "accepts exactly one argument (the file content), and does "
                    "not have a 'self' parameter."
                )

            # Use a unique name for the function in the helper script to avoid collisions
            unique_func_name = f"custom_edit_{name}_{function.__name__}"
            template[0] += (
                f" --function {unique_func_name} "
                f"--import-module {{experiment_run_dir}}/utilities/"
                f"{ramble.util.file_editor.CUSTOM_EDIT_FUNCTIONS_NAME}"
            )

            try:
                import ast

                raw_source = textwrap.dedent(inspect.getsource(function))
                parsed_ast = ast.parse(raw_source)
                has_value_return = any(
                    isinstance(node, ast.Return) and node.value is not None
                    for node in ast.walk(parsed_ast)
                )
                if not has_value_return:
                    raise ramble.language.language_helpers.DirectiveError(
                        f"Directive '{name}' in {origin_str} requires the function "
                        f"'{function.__name__}' to return a value."
                    )

                # Wrap the original function to give it a unique name and avoid collisions
                # while also ensuring it's defined in the script's scope.
                # We use a nested definition to avoid name conflicts with the original name
                # if multiple directives use different functions with same original name.
                wrapper = [
                    f"def {unique_func_name}(content):",
                    textwrap.indent(raw_source, "    "),
                    f"    return {function.__name__}(content)",
                ]
                obj.custom_edit_functions[name] = "\n".join(wrapper)
            except (OSError, TypeError):
                raise ramble.language.language_helpers.DirectiveError(
                    f"Directive '{name}' in {origin_str} could not retrieve source "
                    f"for function '{function.__name__}'."
                ) from None

        if not fail_on_error:
            template[0] += " || true"

        when_list = ramble.language.language_helpers.build_when_list(when, obj, name, "edit_file")
        when_set = frozenset(when_list)

        if not hasattr(obj, "executables"):
            obj.executables = {}

        if when_set not in obj.executables:
            obj.executables[when_set] = {}

        obj.executables[when_set][name] = CommandExecutable(name=name, template=template, **kwargs)

    return _execute_edit_file


@shared_directive("executables")
def patch_file(
    name,
    file_path,
    patch_file,
    fail_on_error=True,
    when=None,
    **kwargs,
):
    """Adds a patch_file executable to this object

    Defines a new executable that uses Ramble's helper script to apply a patch.

    Args:
        name (str): Name of the executable
        file_path (str): Path to the file to patch
        patch_file (str): Path to the patch file
        fail_on_error (bool): If true, the experiment fails if the patch fails.
                              Defaults to True.
        when (list | None): List of when conditions to apply to directive
    """

    def _execute_patch_file(obj):
        import shlex

        from ramble.util.executable import CommandExecutable
        from ramble.util.file_editor import get_file_editor_exec_path

        script_path = get_file_editor_exec_path()
        template = [
            f'python "{script_path}" '
            f"--mode patch --file {shlex.quote(file_path)} --patch-file {shlex.quote(patch_file)}"
        ]

        if not fail_on_error:
            template[0] += " || true"

        when_list = ramble.language.language_helpers.build_when_list(when, obj, name, "patch_file")
        when_set = frozenset(when_list)

        if not hasattr(obj, "executables"):
            obj.executables = {}

        if when_set not in obj.executables:
            obj.executables[when_set] = {}

        obj.executables[when_set][name] = CommandExecutable(name=name, template=template, **kwargs)

    return _execute_patch_file


@shared_directive("archive_patterns")
def archive_pattern(pattern, when=None, **kwargs):
    """Adds a file pattern to be archived in addition to figure of merit logs

    Defines a new file pattern that will be archived during workspace archival.
    Archival will only happen for files that match the pattern when archival
    is being performed.

    Args:
      pattern (str): Pattern that refers to files to archive
      when (list | None): List of when conditions to apply to directive
    """

    def _execute_archive_pattern(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, pattern, "archive_pattern"
        )
        when_set = frozenset(when_list)
        if when_set not in obj.archive_patterns:
            obj.archive_patterns[when_set] = {}

        obj.archive_patterns[when_set][pattern] = pattern

    return _execute_archive_pattern


@shared_directive("figure_of_merit_contexts")
def figure_of_merit_context(name, regex, output_format, when=None, **kwargs):
    """Defines a context for figures of merit

    Defines a new context to contain figures of merit.

    Args:
      name (str): High level name of the context. Can be referred to in
                  the figure of merit
      regex (str): Regular expression, using group names, to match a context.
      output_format (str): String, using python keywords {group_name} to extract
                           group names from context regular expression.
      when (list | None): List of when conditions to apply to directive
    """

    def _execute_figure_of_merit_context(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "figure_of_merit_context"
        )
        when_key = frozenset(when_list)
        if when_key not in obj.figure_of_merit_contexts:
            obj.figure_of_merit_contexts[when_key] = {}

        obj.figure_of_merit_contexts[when_key][name] = {
            "regex": regex,
            "output_format": output_format,
            "when": when_list,
        }

    return _execute_figure_of_merit_context


@shared_directive("figures_of_merit")
def figure_of_merit(
    name,
    fom_regex=None,
    group_name=None,
    log_file="{log_file}",
    units="",
    contexts=None,
    fom_type: FomType = FomType.UNDEFINED,
    when=None,
    fom_map_key=None,
    **kwargs,
):
    """Adds a figure of merit to track for this object

    Defines a new figure of merit.

    Args:
      name (str): High level name of the figure of merit
      log_file (str): File the figure of merit can be extracted from
      fom_regex (str): A regular expression using named groups to extract the FOM
      group_name (str): The name of the group that the FOM should be pulled from
      units (str): The units associated with the FOM
      contexts (list(str) | None): List of contexts (defined by
                                   figure_of_merit_context) this figure of merit
                                   should exist in.
      fom_type (ramble.util.foms.FomType): The type of figure of merit
      when (list | None): List of when conditions to apply to directive
      fom_map_key: If supplied, this is treated as an in-memory (as opposed to file-based)
                   figure of merit, and its value is extracted using this key
    """

    def _execute_figure_of_merit(obj):
        if fom_map_key is None:
            if fom_regex is None or group_name is None:
                raise ramble.language.language_base.DirectiveError(
                    "`fom_regex` and `group_name` are required for defining file-based FOM"
                )
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "figure_of_merit"
        )
        when_key = frozenset(when_list)
        if when_key not in obj.figures_of_merit:
            obj.figures_of_merit[when_key] = {}

        context_list = contexts if contexts is not None else []
        context_key = frozenset(context_list)
        if context_key not in obj.figures_of_merit[when_key]:
            obj.figures_of_merit[when_key][context_key] = {}

        obj.figures_of_merit[when_key][context_key][name] = {
            "log_file": log_file,
            "regex": fom_regex,
            "group_name": group_name,
            "units": units,
            "contexts": context_list,
            "fom_type": fom_type,
            "origin_type": obj.origin_type if hasattr(obj, "origin_type") else "",
            "fom_map_key": fom_map_key,
            "when": when_list,
        }

    return _execute_figure_of_merit


@shared_directive("compilers")
def define_compiler(
    name,
    pkg_spec,
    compiler_spec=None,
    compiler=None,
    package_manager=None,
    inject_if_missing=False,
    when=None,
    **kwargs,
):
    """Defines the compiler that will be used with this object

    Adds a new compiler spec to this object. Software specs should
    reference a compiler that has been added.

    Args:
        name (str): Name of compiler package
        pkg_spec (str): Package spec to install compiler
        compiler_spec (str): Compiler spec (if different from pkg_spec)
        compiler (str): Package name to use for compilation
        package_manager (str): Glob supported pattern to match package managers
                               this compiler applies to
        inject_if_missing (bool): Whether the package should be defined if a
                                  matching package is not already defined
        when (list | None): List of when conditions to apply to directive
    """

    def _execute_define_compiler(obj):
        _add_specs(
            obj,
            "compilers",
            "define_compiler",
            name,
            pkg_spec,
            compiler=compiler,
            compiler_spec=compiler_spec,
            package_manager=package_manager,
            inject_if_missing=inject_if_missing,
            when=when,
        )

    return _execute_define_compiler


@shared_directive("software_specs")
def software_spec(
    name,
    pkg_spec,
    compiler_spec=None,
    compiler=None,
    package_manager=None,
    inject_if_missing=False,
    when=None,
    **kwargs,
):
    """Defines a new software spec needed for this object.

    Adds a new software spec that this object
    needs to execute properly.

    Specs can be described as an mpi spec, which means they
    will depend on the MPI library within the resulting spack
    environment.

    Args:
        name (str): Name of package
        pkg_spec (str): Package spec to install package
        compiler_spec (str): Spec to use if this package will be used as a
                             compiler for another package
        compiler (str): Package name to use as compiler for compiling this package
        package_manager (str): Glob supported pattern to match package managers
                               this package applies to
        inject_if_missing (bool): Whether the package should be added to experiment
                                  environments automatically or not.
        when (list | None): List of when conditions to apply to directive
    """

    def _execute_software_spec(obj):
        _add_specs(
            obj,
            "software_specs",
            "software_spec",
            name,
            pkg_spec,
            compiler=compiler,
            compiler_spec=compiler_spec,
            package_manager=package_manager,
            inject_if_missing=inject_if_missing,
            when=when,
        )

    return _execute_software_spec


@shared_directive("package_manager_configs")
def package_manager_config(name, config, package_manager=None, when=None, **kwargs):
    """Defines a config option to set within a package manager

    Define a new config which will be passed to a package manager. The
    resulting experiment instance will pass the config to the package manager,
    which will control the logic of applying it.

    Args:
        name (str): Name of this configuration
        config (str): Configuration option to set
        package_manager (str): Name of the package manager this config should be used with
        when (list | None): List of when conditions to apply to directive
    """

    def _execute_package_manager_config(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "package_manager_config"
        )

        if package_manager is not None:
            logger.warn(
                "The `package_manager` argument of the package_manager_config "
                f"directive in object {obj.name} is deprecated. Please "
                "transition this to use the `when` argument instead."
            )

        obj.package_manager_configs[name] = {
            "config": config,
            "when": when_list,
        }

    return _execute_package_manager_config


@shared_directive("required_packages")
def required_package(name, package_manager=None, when=None, **kwargs):
    """Defines a new spack package that is required for this object
    to function properly.

    Args:
        name (str): Name of required package
        package_manager (str): Glob package manager name to apply this required package to
        when (list | None): List of when conditions to apply to directive
    """

    def _execute_required_package(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "package_manager_config"
        )

        if package_manager is not None:
            logger.warn(
                "The `package_manager` argument of the required_package "
                f"directive in object {obj.name} is deprecated. Please "
                "transition this to use the `when` argument instead."
            )

        obj.required_packages[name] = {"when": when_list}

    return _execute_required_package


@shared_directive("success_criteria")
def success_criteria(
    name,
    mode,
    match=None,
    file="{log_file}",
    fom_name=None,
    fom_context="null",
    formula=None,
    anti_match=None,
    when=None,
    **kwargs,
):
    """Defines a success criteria used by experiments of this object

    Adds a new success criteria to this object definition.

    These will be checked during the analyze step to see if a job exited properly.

    Args:
      name (str): The name of this success criteria
      mode (str): The type of success criteria that will be validated
                  Valid values are: 'string', 'application_function', and 'fom_comparison'
      match (str): For mode='string'. Value to check indicate success (if found, it
                   would mark success)
      file (str): For mode='string'. File success criteria should be located in
      fom_name (str): For mode='fom_comparison'. Name of fom for a criteria.
                      Accepts globbing.
      fom_context (str): For mode='fom_comparison'. Context the fom is contained
                         in. Accepts globbing.
      formula (str): For mode='fom_comparison'. Formula to use to evaluate success.
                     '{value}' keyword is set as the value of the FOM.
      anti_match (str): For mode='string'. Value to check indicate failure.
                        This setting and `match` are mutually exclusive.
      when (list | None): List of when conditions to apply to directive
    """

    def _execute_success_criteria(obj):
        valid_modes = ramble.success_criteria.SuccessCriteria._valid_modes
        if mode not in valid_modes:
            logger.die(f"Mode {mode} is not valid. Valid values are {valid_modes}")

        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "success_criteria"
        )
        when_set = frozenset(when_list)

        if when_set not in obj.success_criteria:
            obj.success_criteria[when_set] = {}

        obj.success_criteria[when_set][name] = {
            "mode": mode,
            "match": match,
            "anti_match": anti_match,
            "file": file,
            "fom_name": fom_name,
            "fom_context": fom_context,
            "formula": formula,
            "when": when_list,
        }

    return _execute_success_criteria


@shared_directive("builtins")
def register_builtin(
    name,
    required=True,
    injection_method="prepend",
    depends_on=None,
    dependents=None,
    when=None,
    **kwargs,
):
    """Register a builtin

    Builtins are methods that return lists of strings. These methods represent
    a way to write python code to generate executables for building up
    workloads.

    Manual injection of a builtins can be performed through modifying the
    execution order in the internals config section.

    Modifier builtins are named:
    `modifier_builtin::modifier_name::method_name`.

    Application modifiers are named:
    `builtin::method_name`.

    Package manager builtins are named:
    `package_manager_builtin::package_manager_name::method_name`.

    As an example, if the following builtin was defined:

    .. code-block:: python

      register_builtin('example_builtin', required=True)
      def example_builtin(self):
        ...

    Its fully qualified name would be:
    * `modifier_builtin::test-modifier::example_builtin` when defined in a
    modifier named `test-modifier`
    * `builtin::example_builtin` when defined in an application

    The 'required' attribute marks a builtin as required for all workloads. This
    will ensure the builtin is added to the workload if it is not explicitly
    added. If required builtins are not explicitly added to a workload, they
    are injected into the list of executables, based on the injection_method
    attribute.

    The 'injection_method' attribute controls where the builtin will be
    injected into the executable list.
    Options are:
    - 'prepend' -- This builtin will be injected before the executables for the experiment
    - 'append' -- This builtin will be injected after the executables for the experiment

    NOTE: When specifying explicit dependencies, cycles can be created which
    will cause an error when trying to construct the final executable order.
    One possible way to resolve those issues is to make sure that builtins
    which depend on each other have the same injection method (or at least do
    not have conflicting injection methods). As an example, if builtin `a` has
    an injection method of prepend, and builtin `b` lists `a` as a dependent
    but has an injection method of append, then this will create a cycle. If b
    has it's injection method updated to be `prepend` the cycle will be
    resolved.

    Args:
        name (str): Name of builtin (should be the name of a class method) to register
        required (bool): Whether the builtin will be auto-injected or not
        injection_method (str): The method of injecting the builtin. Can be
                                'prepend' or 'append'
        depends_on (list(str) | None): The names of builtins this builtin depends on
                                       (and must execute after).
        dependents (list(str) | None): The names of builtins that should come
                                       after this builtin
        when (list | None): List of when conditions to apply to directive
    """
    if depends_on is None:
        depends_on = []
    if dependents is None:
        dependents = []

    supported_injection_methods = ["prepend", "append"]

    def _store_builtin(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "register_builtin"
        )
        when_key = frozenset(when_list)
        if when_key not in obj.builtins:
            obj.builtins[when_key] = {}

        if injection_method not in supported_injection_methods:
            raise ramble.language.language_base.DirectiveError(
                f"Object {obj.name} defines builtin {name} with an invalid "
                f"injection method of {injection_method}.\n"
                f"Valid methods are {str(supported_injection_methods)}"
            )

        builtin_name = obj._builtin_name.format(obj_name=obj.name, name=name)

        obj.builtins[when_key][builtin_name] = {
            "name": name,
            "required": required,
            "injection_method": injection_method,
            "depends_on": depends_on.copy(),
            "dependents": dependents.copy(),
            "when": when_list,
        }

    return _store_builtin


@shared_directive("phase_definitions")
def register_phase(name, pipeline=None, run_before=None, run_after=None, when=None, **kwargs):
    """Register a phase

    Phases are portions of a pipeline that will execute when
    executing a full pipeline.

    Registering a phase allows an object to know what the phases
    dependencies are, to ensure the execution order is correct.

    If called multiple times, the dependencies are combined together. Only one
    instance of a phase will show up in the resulting dependency list for a phase.

    Args:
      name (str): The name of the phase. Phases are functions named '_<phase>'.
      pipeline (str): The name of the pipeline this phase should be registered into.
      run_before (list(str) | None): A list of phase names this phase should run before
      run_after (list(str) | None): A list of phase names this phase should run after
      when (list | None): List of when conditions to apply to directive
    """
    if run_before is None:
        run_before = []
    if run_after is None:
        run_after = []

    def _execute_register_phase(obj):
        import ramble.util.graph

        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "register_phase"
        )

        if pipeline not in obj.pipelines:
            raise ramble.language.language_base.DirectiveError(
                "Directive register_phase was "
                f'given an invalid pipeline "{pipeline}"\n'
                "Available pipelines are: "
                f" {obj.pipelines}"
            )

        if not isinstance(run_before, list):
            raise ramble.language.language_base.DirectiveError(
                "Directive register_phase was "
                "given an invalid type for "
                "the run_before attribute in object "
                f"{obj.name}"
            )

        if not isinstance(run_after, list):
            raise ramble.language.language_base.DirectiveError(
                "Directive register_phase was "
                "given an invalid type for "
                "the run_after attribute in object "
                f"{obj.name}"
            )

        if not hasattr(obj, f"_{name}"):
            raise ramble.language.language_base.DirectiveError(
                "Directive register_phase was "
                f"given an undefined phase {name} "
                f"in object {obj.name}"
            )

        if pipeline not in obj.phase_definitions:
            obj.phase_definitions[pipeline] = {}

        if name in obj.phase_definitions[pipeline]:
            phase_node = obj.phase_definitions[pipeline][name]
        else:
            phase_node = ramble.util.graph.GraphNode(name)

        for before in run_before:
            phase_node.order_before(before)

        for after in run_after:
            phase_node.order_after(after)

        phase_node.when = when_list

        obj.phase_definitions[pipeline][name] = phase_node

    return _execute_register_phase


@shared_directive(dicts="maintainers", init_value=[])
def maintainers(*names: str, **kwargs):
    """Add a new maintainer directive, to specify maintainers in a declarative way.

    Args:
        names (str): GitHub username(s) for the maintainer. Can provide
                        multiple names as separate arguments.
    """

    def _execute_maintainers(obj):
        _add_list_attributes(obj, "maintainers", names)

    return _execute_maintainers


@shared_directive(dicts="tags", init_value=[])
def tags(*values: str, **kwargs):
    """Add a new tag directive, to specify tags in a declarative way.

    Args:
        values (str): Values to mark as a tag. Can provide multiple values
                         as separate arguments.
    """

    def _execute_tags(obj):
        _add_list_attributes(obj, "tags", values)

    return _execute_tags


@shared_directive("class_families")
def class_family(*names: str, **kwargs):
    """Add a new family to this object

    Args:
        names (str): Name of family to apply to this object
    """

    def _define_class_family(obj):
        for name in names:
            obj.class_families[name] = True

    return _define_class_family


@shared_directive(dicts="shell_support_pattern", init_value=None)
def target_shells(shell_support_pattern=None, **kwargs):
    """Directive to specify supported shells.

    If not specified, i.e., not directly specified or inherited from the base,
    then it assumes all shells are supported.

    Args:
        shell_support_pattern (str): The glob pattern that is used to match
                                     with the configured shell
    """

    def _execute_target_shells(obj):
        if shell_support_pattern is not None:
            obj.shell_support_pattern = shell_support_pattern

    return _execute_target_shells


@shared_directive("templates")
def register_template(
    name: str,
    src_path: str,
    dest_path: Optional[str] = None,
    define_var: bool = True,
    extra_vars: Optional[dict] = None,
    extra_vars_func: Optional[str] = None,
    output_perm=None,
    when: Optional[List[str]] = None,
    **kwargs,
):
    """Directive to define an object-specific template to be rendered into experiment run_dir.

    For instance, `register_template(name="foo", src_path="foo.tpl", dest_path="foo.sh")`
    expects a "foo.tpl" template defined alongside the object source, and uses that to
    render a file under "{experiment_run_dir}/foo.sh". The rendered path can also be
    referenced with the `foo` variable name.

    Args:
        name: The name of the template. It is also used as the variable name
              that an experiment can use to reference the rendered path, if
              `define_var` is true.
        src_path: The location of the template. It can either point
                  to an absolute or a relative path. It knows how to resolve
                  workspace paths such as `$workspace_shared`. A relative path
                  is relative to the containing directory of the object source.
        dest_path: If present, the location of the rendered output. It can either point
                   to an absolute or a relative path. It knows how to resolve
                   workspace paths such as `$workspace_shared`. A relative path
                   is relative to the `experiment_run_dir`. If not given, it will
                   use the same name as the template (optionally drop the .tpl extension)
                   and placed under `experiment_run_dir`.
        define_var: Controls if a variable named `name` should be defined.
        extra_vars: If present, the variable dict is used as extra variables to
                    render the template.
        extra_vars_func: If present, the name of the function to call to return
                         a dict of extra variables used to render the template.
                         This option is combined together with and takes precedence
                         over `extra_vars`, if both are present.
        output_perm: The chmod mask for the rendered output file.
        when: List of when conditions to apply to directive
    """

    def _define_template(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "register_template"
        )
        when_key = frozenset(when_list)
        if when_key not in obj.templates:
            obj.templates[when_key] = {}

        var_name = name if define_var else None
        extra_vars_func_name = f"_{extra_vars_func}" if extra_vars_func is not None else None
        obj.templates[when_key][name] = {
            "src_path": src_path,
            "dest_path": dest_path,
            "var_name": var_name,
            "extra_vars": extra_vars,
            "extra_vars_func_name": extra_vars_func_name,
            "output_perm": output_perm,
            "when": when_list,
        }

    return _define_template


@shared_directive("formatted_executables")
def formatted_executable(
    name: str,
    commands: list,
    prefix: str = "",
    indentation: int = 0,
    join_separator: str = "\n",
    when=None,
    **kwargs,
):
    """Define a new formatted execution for this object

    Args:
        name: Name of the new formatted executable
        prefix: Prefix for each line of the formatted executable
        indentation: Number of spaces to indent before the prefix of each line
        join_separator: String to use when separating the commands during formatting
        commands: List of commands to expand when generating the formatted executable
        when (list | None): List of when conditions to apply to directive
    """

    def _define_formatted_executable(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "formatted_executable"
        )

        when_set = frozenset(when_list)

        if when_set not in obj.formatted_executables:
            obj.formatted_executables[when_set] = {}

        obj.formatted_executables[when_set][name] = {
            "prefix": prefix,
            "indentation": indentation,
            "join_separator": join_separator,
            "commands": commands.copy(),
            "when": when_list,
        }

    return _define_formatted_executable


@shared_directive("validators")
def register_validator(
    name: str,
    predicate: str,
    message: str,
    fail_on_invalid: bool = True,
    when=None,
    **kwargs,
):
    """Directive to define a validator for the object.

    Args:
        name: The name of the validator.
        predicate: The expression to be evaluated (expanded). If it expands to False,
                   then the validation fails.
        message: The message given when the validation fails. This can contain Ramble
                 variables.
        fail_on_invalid: When true, this fails the experiment setup, otherwise it logs
                         a warning. The default is True.
        when (list | None): List of when conditions to apply to directive
    """

    def _define_validator(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "register_validator"
        )
        when_key = frozenset(when_list)

        if when_key not in obj.validators:
            obj.validators[when_key] = {}

        obj.validators[when_key][name] = {
            "predicate": predicate,
            "message": message,
            "fail_on_invalid": fail_on_invalid,
            "when": when_list,
        }

    return _define_validator


@shared_directive("required_utilities")
def requires_utility(
    name: str,
    when=None,
    allow_external: bool = True,
    **kwargs,
):
    """Directive to declare an external dependency.

    Args:
        name: Name of the external dependency required (e.g. spack)
        allow_external: Whether or not the dependency can be satisfied by a system installation
        when: List of when conditions to apply to directive
        **kwargs: Optional configuration overrides for the dependency (e.g. version). Also
            supports ``min_version`` and ``max_version`` to constrain the required version.
    """

    def _define_requires_utility(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "requires_utility"
        )
        when_key = frozenset(when_list)

        if when_key not in obj.required_utilities:
            obj.required_utilities[when_key] = {}

        obj.required_utilities[when_key][name] = kwargs.copy()

        parsed_allow_external = True
        if isinstance(allow_external, str) and allow_external.lower() == "false":
            parsed_allow_external = False
        elif not isinstance(allow_external, str):
            parsed_allow_external = bool(allow_external)

        obj.required_utilities[when_key][name]["allow_external"] = parsed_allow_external
        obj.required_utilities[when_key][name]["when"] = when_list

    return _define_requires_utility


@shared_directive("conflicts")
def conflict(
    conflict_spec: str,
    when: Optional[Union[str, List[str]]] = None,
    msg: Optional[str] = None,
    **kwargs,
):
    """Defines a conflict for this object.

    Args:
        conflict_spec: The trigger condition (e.g., `+variant`, `compiler=gcc`)
        when: Optional conditional under which the conflict occurs
        msg: Optional custom error/warning message
    """

    def _execute_conflicts(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, conflict_spec, "conflicts"
        )

        when_key = frozenset(when_list)
        if when_key not in obj.conflicts:
            obj.conflicts[when_key] = []

        obj.conflicts[when_key].append(
            {
                "conflict_spec": conflict_spec,
                "message": msg,
                "when": when_list,
            }
        )

    return _execute_conflicts


@shared_directive("object_variables")
def variable(
    name: str,
    default,
    description: str,
    values: Optional[list] = None,
    strict: bool = True,
    expandable: bool = True,
    track_used: bool = False,
    when=None,
    error_context="variable",
    environment_variable_name: Optional[str] = None,
    scoped: bool = False,
    **kwargs,
):
    """Define a variable for this modifier

    Args:
        name (str): Name of variable to define
        default: Default value of variable definition
        description (str): Description of variable's purpose
        values (list): Optional list of suggested values for this variable
        strict (bool): If True (the default) and values is not None, the variable's value
                       will be validated against the values list.
        expandable (bool): True if the variable should be expanded, False if not.
        track_used (bool): True if the variable should be tracked as used,
                           False if not. Can help with allowing lists without vectorizing
                           experiments.
        when (list | None): List of when conditions to apply to directive
        environment_variable_name (str | None): If not None, an environment variable of this name
                                                will be defined with the value of this variable.
    """

    def _define_variable(obj):
        import ramble.definitions.variables

        var_name = name
        if scoped:
            var_name = f"{obj.origin_type}::{obj.name}::{name}"

        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, var_name, error_context
        )

        when_set = frozenset(when_list)

        if when_set not in obj.object_variables:
            obj.object_variables[when_set] = []

        obj.object_variables[when_set].append(
            ramble.definitions.variables.Variable(
                var_name,
                default=default,
                description=description,
                values=values,
                expandable=expandable,
                when=when_list,
                **kwargs,
            )
        )

        if strict and values is not None:
            ramble.language.language_helpers.add_variable_validator(
                obj, var_name, values, when_list
            )

        if environment_variable_name is not None:
            if when_set not in obj.object_environment_variables:
                obj.object_environment_variables[when_set] = []

            obj.object_environment_variables[when_set].append(
                ramble.definitions.variables.EnvironmentVariable(
                    environment_variable_name,
                    value=f"{{{var_name}}}",
                    description=description,
                    method="set",
                    when=when_list,
                )
            )

    return _define_variable


@shared_directive(
    dicts=(
        "object_environment_variables",
        "workload_group_env_vars",
        "workload_groups",
        "workloads",
    )
)
def environment_variable(
    name,
    value,
    description,
    method="set",
    append_separator=",",
    workload=None,
    workloads=None,
    workload_group=None,
    when=None,
    **kwargs,
):
    """Define an environment variable to be used in experiments. Workload args
    are only applicable to application definitions.

    Args:
        name (str): Name of environment variable to define
        value (str): Value to set env-var to
        description (str): Description of the env-var
        method (str): The method to use when defining the env-var.
                      Can be "set", "append", or "prepend"
        workload (str): Name of app workload this env-var should be added to
        workloads (list(str)): List of app workload names this env-var should be
                               added to
        workload_group (str): Name of app workload group this env-var should be
                               added to
        when (list | None): List of when conditions to apply to directive
    """

    def _execute_environment_variable(obj):
        supported_methods = ["set", "append", "prepend"]
        if method not in supported_methods:
            raise ramble.language.language_base.DirectiveError(
                "environment_variable directive given an invalid method of "
                f"{method}. Supported methods are {str(supported_methods)}"
            )

        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "environment_variable"
        )

        workload_env_var = ramble.definitions.variables.EnvironmentVariable(
            name,
            value=value,
            description=description,
            method=method,
            append_separator=append_separator,
            when=when_list,
            **kwargs,
        )

        if workload or workloads or workload_group:
            if obj.origin_type != "application":
                raise ramble.language.language_base.DirectiveError(
                    f"A workload argument was provided for environment variable {name} in object "
                    f"{obj.name}. Workload arguments are only valid in an application definition."
                )

            all_workloads = ramble.language.language_helpers.merge_definitions(
                workload, workloads, obj.workloads, "workload", "workloads", "environment_variable"
            )

            env_var_when_frozenset = frozenset(workload_env_var.when)
            for when_set, app_workloads in obj.workloads.items():
                for wl_name in all_workloads:
                    if wl_name in app_workloads:
                        if ramble.language.language_helpers.are_when_compatible(
                            when_set, env_var_when_frozenset
                        ):
                            obj.workloads[when_set][wl_name].add_environment_variable(
                                workload_env_var.copy()
                            )

            if workload_group is not None:
                workload_group_inst = obj.workload_groups[workload_group]

                if workload_group not in obj.workload_group_env_vars:
                    obj.workload_group_env_vars[workload_group] = []

                obj.workload_group_env_vars[workload_group].append(workload_env_var.copy())

                # TODO: See if there's a way to clean this up. We can't evaluate 'when' here due to
                # lack of expander, so this merges the 'when' of wl group with the 'when' of vars
                # and env vars to be evaluated later. It adds each var or env var to all workloads
                # that match the name, but the merged 'when' ensures they're only activated for the
                # correct workload group conditions.
                wl_group_when_map = collections.defaultdict(list)
                for wl_group_when_set, wl_group_workloads in workload_group_inst.workloads.items():
                    for wl_name in wl_group_workloads:
                        wl_group_when_map[wl_name].append(wl_group_when_set)

                for app_wl_name, wl_group_when_sets in wl_group_when_map.items():
                    for wl_group_when_set in wl_group_when_sets:
                        workload_env_var_copy = workload_env_var.copy()
                        workload_env_var_copy.when.extend(wl_group_when_set)
                        env_var_when_frozenset = frozenset(workload_env_var_copy.when)

                        for when_set, app_workloads in obj.workloads.items():
                            if app_wl_name in app_workloads:
                                if ramble.language.language_helpers.are_when_compatible(
                                    when_set, env_var_when_frozenset
                                ):
                                    obj.workloads[when_set][app_wl_name].add_environment_variable(
                                        workload_env_var_copy
                                    )
        else:
            when_set = frozenset(when_list)
            if when_set not in obj.object_environment_variables:
                obj.object_environment_variables[when_set] = []

            obj.object_environment_variables[when_set].append(workload_env_var.copy())

    return _execute_environment_variable


@shared_directive("class_variants")
def variant(
    name: str,
    default: Optional[Any] = None,
    description: str = "",
    values: Optional[Union[collections.abc.Sequence, Callable[[Any], bool]]] = None,
    **kwargs,
):

    def _define_variant(obj):
        """Define a new variant in the input object

        Args:
            obj: Input ramble object to define variant inside.
            name (str): Name of variant to define
            default: Default value of the new variant
            description (str): Description of the variant
            values: Values for variant.
        """
        ramble.variants.validate_variant(name)

        args_dict = {
            "name": name,
            "default": default,
            "description": description,
            "values": values,
        }
        args_dict.update(kwargs)

        obj.class_variants[name] = args_dict

    return _define_variant


@shared_directive("scripts_to_source")
def source_script(
    script_path: str,
    when=None,
    **kwargs,
):
    """Add a script that should be sourced before executing

    Args:
        script_path (str): Path to the script to source
        when (list | None): List of when conditions to apply to directive
    """

    def _execute_source_script(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, script_path, "source_script"
        )
        obj.scripts_to_source.append({"path": script_path, "when": when_list})

    return _execute_source_script


@shared_directive("known_versions")
def version(
    number: str,
    description: str = "",
    preferred: bool = False,
    **kwargs,
):
    """Define a new version in the input object

    Args:
        number: Version number (Python packaging version format)
        description: Description of this version
        preferred: Mark this version as preferred. Only one version can be preferred.
    """

    def _define_version(obj):
        new_version = ObjectVersion(
            version_number=number,
            description=description,
            origin_type=obj.origin_type,
            preferred=preferred,
            version_to_pep440=obj.version_to_pep440,
            pep440_to_version=obj.pep440_to_version,
        )

        # Ensure only one version is marked as preferred
        if new_version.preferred:
            curr_preferred = obj.__dict__.get("_preferred_version", None)
            curr_class = obj.__dict__.get("_preferred_version_class", None)
            curr_directive = getattr(
                ramble.language.language_base.DirectiveMeta,
                "_current_directive",
                None,
            )
            this_class = getattr(curr_directive, "_defining_class", None)

            if curr_preferred is None or (this_class is not None and curr_class != this_class):
                obj._preferred_version = new_version
                obj._preferred_version_class = this_class
            elif curr_preferred.version == new_version.version:
                # Ignore identical preferred versions, which happens when app is subclassed
                pass
            else:
                raise ramble.language.language_base.DirectiveError(
                    f"Object {obj.name} already has a preferred version "
                    f"({curr_preferred.version}). Only one version can be marked preferred."
                )
        obj.known_versions[number] = new_version

    return _define_version


@shared_directive(dicts="enable_strict_versions", init_value=True)
def strict_versions(strict: bool = True, **kwargs):
    """Directive to specify if the object has strict versioning.
    If true, only known versions can be used in experiments.

    Args:
        strict (bool): Whether strict versioning is enabled.
    """

    def _execute_strict_versions(obj):
        obj.enable_strict_versions = strict

    return _execute_strict_versions


@shared_directive(dicts="required_vars")
def required_variable(
    var: str,
    results_level="variable",
    description=None,
    mode=None,
    modes=None,
    when=None,
    **kwargs,
):
    """Mark a variable as being required by this modifier

    Args:
        var (str): Variable name to mark as required
        results_level (str): 'variable' or 'key'. If 'key', variable is promoted to
                             a key within JSON or YAML formatted results.
        description (str | None): Description of the required variable.
        mode (str | None): mode that the required check should be applied to. The
                            default None means apply to all modes.
        modes (list[str] | None): modes that the required check should be applied to. The
                            default None means apply to all modes.
        when (list | None): List of when conditions to apply the required check.
    """

    def _mark_required_var(obj):
        if mode or modes:
            if obj.origin_type and obj.origin_type == "modifier":
                when_lists = ramble.language.language_helpers.merge_conditions(
                    obj, "required_variable", "mode", "modes", mode=mode, modes=modes, when=when
                )
            else:
                raise ramble.language.language_base.DirectiveError(
                    f"A mode argument was provided for required variable {var} in object "
                    f"{obj.name}. Mode arguments are only valid in a modifier definition."
                )
        else:
            when_lists = [
                ramble.language.language_helpers.build_when_list(
                    when, obj, var, "required_variable"
                )
            ]

        if results_level not in ["key", "variable"]:
            raise ramble.language.language_base.DirectiveError(
                "The results_level argument for required variable "
                f"{var} is set to {results_level}.\n"
                "Valid options are 'key' or 'variable'."
            )

        output_level = ramble.keywords.output_level.variable
        if results_level == "key":
            output_level = ramble.keywords.output_level.key

        if var not in obj.required_vars:
            obj.required_vars[var] = {
                "type": ramble.keywords.key_type.required,
                "level": output_level,
                "description": description,
                "when": [],
            }

        for when_list in when_lists:
            obj.required_vars[var]["when"].append(when_list)

    return _mark_required_var


@shared_directive("auxiliary_software_files")
def auxiliary_software_file(name, src_path, dest_path, when=None, **kwargs):
    """Defines an auxiliary software file

    Args:
      name (str): Name of the auxiliary file
      src_path (str): Source path of the auxiliary file
      dest_path (str): Destination path of the auxiliary file
    """

    def _execute_auxiliary_software_file(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "auxiliary_software_files"
        )

        when_key = frozenset(when_list)
        if when_key not in obj.auxiliary_software_files:
            obj.auxiliary_software_files[when_key] = {}
        obj.auxiliary_software_files[when_key][name] = {
            "src_path": src_path,
            "dest_path": dest_path,
            "consumed": False,
        }

    return _execute_auxiliary_software_file


@shared_directive("command_variables")
def command_variable(
    name,
    command,
    dry_run_value,
    description="",
    expandable=True,
    track_used=True,
    when=None,
    **kwargs,
):
    """Defines an variable, backed by a command

    Args:
      name (str): Name of the variable
      command (str): Command to execute to get the variable value
      dry_run_value (str): Value to use when part of a dry-run
      description (str): Description of variable
    """

    def _execute_command_variable(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, name, "command_variable"
        )

        when_key = frozenset(when_list)
        if when_key not in obj.command_variables:
            obj.command_variables[when_key] = []

        obj.command_variables[when_key].append(
            ramble.definitions.variables.CommandVariable(
                name=name,
                command=command,
                dry_run_value=dry_run_value,
                description=description,
                expandable=expandable,
                track_used=track_used,
                when=when_list,
            )
        )

    return _execute_command_variable


@contextlib.contextmanager
def when(condition):
    ramble.language.language_base.DirectiveMeta.push_to_context(condition)
    try:
        yield
    finally:
        ramble.language.language_base.DirectiveMeta.pop_from_context()


@contextlib.contextmanager
def default_args(**kwargs):
    ramble.language.language_base.DirectiveMeta.push_default_args(kwargs)
    try:
        yield
    finally:
        ramble.language.language_base.DirectiveMeta.pop_default_args()


@shared_directive("object_modifiers")
def modifier(
    name: str,
    mode: Optional[str] = None,
    on_executable: Optional[List[str]] = None,
    when=None,
    **kwargs,
):
    """Automatically include a modifier when this object is used

    Adds a modifier to be included in experiments that use this object.

    Args:
        name: Name of the modifier to include
        mode: Mode to apply for the modifier
        on_executable: List of executables the modifier should be applied to
        when: Condition or conditions when this modifier should be included
        **kwargs: Additional configuration parameters for the modifier
    """

    def _execute_modifier(obj):
        when_list = ramble.language.language_helpers.build_when_list(when, obj, name, "modifier")
        mod_dict = {"name": name}
        if mode is not None:
            mod_dict["mode"] = mode
        if on_executable is not None:
            mod_dict["on_executable"] = on_executable
        mod_dict.update(kwargs)
        when_key = frozenset(when_list)
        if when_key not in obj.object_modifiers:
            obj.object_modifiers[when_key] = []
        obj.object_modifiers[when_key].append(mod_dict)

    return _execute_modifier
