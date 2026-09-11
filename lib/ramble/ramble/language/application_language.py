# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import functools

import ramble.definitions.variables
import ramble.language.language_helpers
import ramble.language.shared_language
import ramble.workload
from ramble.error import DirectiveError

"""This package contains directives that can be used within an application.

Directives are functions that can be called inside an application
definition to modify then application, for example:

    .. code-block:: python

      class Gromacs(ExecutableApplication):
          # Workload directive:
          workload('water_bare', executables=['pre-process', 'execute-gen'],
               input='water_bare_hbonds')

In the above example, 'workload' is a ramble directive

There are many available directives, the majority of which are implemented here.

Some examples include:

  workload
  executable
  figure_of_merit
  figure_of_merit_context
  input_file

For a full list see below, or consult the existing application definitions for
examples

"""


ApplicationMeta = ramble.language.shared_language.SharedMeta
application_directive = functools.partial(ApplicationMeta.directive, language_type="application")


@application_directive("workloads")
def workload(
    name,
    executables=None,
    executable=None,
    input=None,
    inputs=None,
    tags=None,
    when=None,
    where=None,
    exclude_where=None,
    **kwargs,
):
    """Adds a workload to this application

    Defines a new workload that can be used within the context of
    its application.

    Args:
        executable (str): The name of an executable to be used
        executables (str): A list of executable names to be used
        input (str): Optional, name of an input be used
        inputs (str): Optional, A list of input names that will be used

    One of executable, or executables is required as an input argument.
    """

    def _execute_workload(app):
        all_execs = ramble.language.language_helpers.require_definition(
            executable, executables, app.executables, "executable", "executables", "workload"
        )

        all_inputs = ramble.language.language_helpers.merge_definitions(
            input, inputs, app.inputs, "input", "inputs", "workload"
        )

        when_list = ramble.language.language_helpers.build_when_list(when, app, name, "workload")
        when_set = frozenset(when_list)
        if when_set not in app.workloads:
            app.workloads[when_set] = {}

        app.workloads[when_set][name] = ramble.workload.Workload(
            name, all_execs, all_inputs, tags, where, exclude_where, when_list
        )

    return _execute_workload


@application_directive(
    dicts=("workload_groups", "workload_group_vars", "workload_group_env_vars", "workloads")
)
def workload_group(name, workloads=None, mode=None, when=None, **kwargs):
    """Adds a workload group to this application

    Defines a new workload group that can be used within the context of its
    application.

    Args:
        name (str): The name of the group
        workloads (list(str) | None): A list of workloads to be grouped
    """
    if workloads is None:
        workloads = []

    def _execute_workload_groups(app):
        when_list = ramble.language.language_helpers.build_when_list(
            when, app, name, "workload_group"
        )

        if name not in app.workload_groups:
            app.workload_groups[name] = ramble.workload.WorkloadGroup(
                name=name, workloads=workloads, when_list=when_list
            )
        else:
            app.workload_groups[name].add_workloads(
                workloads=workloads, when_list=when_list, mode=mode
            )

        # Apply any existing variables in the group to the workload
        if name in app.workload_group_vars:
            for var in app.workload_group_vars[name]:
                var_when_frozenset = frozenset(var.when)
                for workload in workloads:
                    for when_set in app.workloads:
                        if workload in app.workloads[when_set]:
                            if ramble.language.language_helpers.are_when_compatible(
                                when_set, var_when_frozenset
                            ):
                                app.workloads[when_set][workload].add_variable(var)

        if name in app.workload_group_env_vars:
            for env_var in app.workload_group_env_vars[name]:
                env_var_when_frozenset = frozenset(env_var.when)
                for workload in workloads:
                    for when_set in app.workloads:
                        if workload in app.workloads[when_set]:
                            if ramble.language.language_helpers.are_when_compatible(
                                when_set, env_var_when_frozenset
                            ):
                                app.workloads[when_set][workload].add_environment_variable(env_var)

    return _execute_workload_groups


@application_directive("executables")
def executable(name, template, when=None, **kwargs):
    """Adds an executable to this application

    Defines a new executable that can be used to configure workloads and
    experiments with.

    Executables may or may not use MPI.

    Args:
        name (str): Name of the executable
        template (list[str] | str): The template command this executable should generate from
        use_mpi (bool): determines if this executable should be
            wrapped with an `mpirun` like command or not
        mpi (bool): Alias for ``use_mpi``
        variables (dict): Dictionary of variable definitions to use for this
            executable only
        redirect (str): Optional, sets the path for outputs to be written to.
            defaults to {log_file}
        output_capture (str): Optional, Declare which output (stdout, stderr,
            both) to capture. Defaults to stdout
        run_in_background (bool): Optional, Declare if the command should
            run in the background. Defaults to False
        when (list | None): List of when conditions to apply to directive
    """

    def _execute_executable(app):
        from ramble.util.executable import CommandExecutable

        when_list = ramble.language.language_helpers.build_when_list(when, app, name, "executable")
        when_set = frozenset(when_list)
        if when_set not in app.executables:
            app.executables[when_set] = {}

        app.executables[when_set][name] = CommandExecutable(
            name=name, template=template, when=when_list, **kwargs
        )

    return _execute_executable


@application_directive("inputs")
def input_file(
    name,
    url,
    description,
    target_dir="{workload_input_dir}",
    sha256=None,
    extension=None,
    expand=True,
    when=None,
    **kwargs,
):
    """Adds an input file definition to this application

    Defines a new input file.
    An input file must define it's name, and a url where the input can be
    fetched from.

    Args:
        name (str): Name of the input file
        url (str): Path to the input file / archive
        description (str): Description of this input file
        target_dir (str): Optional, the directory where the archive will be
                               expanded. Defaults to the '{workload_input_dir}'
                               + os.sep + '{input_name}'
        sha256 (str): Optional, the expected sha256 checksum for the input file
        extension (str): Optiona, the extension to use for the input, if it isn't part of the
                              file name.
        expand (bool): Optional. Whether the input should be expanded or not. Defaults to True
        when (list | None): List of when conditions to apply to directive
    """

    def _execute_input_file(app):
        when_list = ramble.language.language_helpers.build_when_list(when, app, name, "input_file")
        when_set = frozenset(when_list)
        if when_set not in app.inputs:
            app.inputs[when_set] = {}

        input_dict = {
            "url": url,
            "description": description,
            "target_dir": target_dir,
            "sha256": sha256,
            "extension": extension,
            "expand": expand,
            "when": when_list,
        }
        input_dict.update(kwargs)
        app.inputs[when_set][name] = input_dict

    return _execute_input_file


@application_directive(
    dicts=("workload_group_vars", "workload_group_env_vars", "workload_groups", "workloads")
)
def workload_variable(
    name,
    default=None,
    description="",
    values=None,
    strict: bool = True,
    workload=None,
    workloads=None,
    workload_group=None,
    workload_defaults=None,
    expandable: bool = True,
    track_used: bool = True,
    when=None,
    environment_variable_name=None,
    **kwargs,
):
    """Define a new variable to be used in experiments

    Defines a new variable that can be defined within the
    experiments.yaml config file, to control various aspects of
    an experiment.

    These are specific to each workload.

    Args:
        name (str): Name of variable to define
        default: Default value of variable definition
        description (str): Description of variable's purpose
        values (list): Optional list of suggested values for this variable
        strict (bool): If True (the default) and values is not None, the variable's value
                       will be validated against the values list.
        workload (str): Single workload this variable is used in
        workloads (list): List of modes this variable is used in
        workload_group (str): Name of workload group this variable is used in.
        workload_defaults (dict): Dictionary mapping workload names to default values.
                                  Mututally exclusive with workload, workloads, workload_group,
                                  and default.
        expandable (bool): True if the variable should be expanded, False if not.
        track_used (bool): True if the variable should be tracked as used,
                           False if not. Can help with allowing lists without vectorizing
                           experiments.
        when (list | None): List of when conditions to apply to directive
        environment_variable_name (str | None): If not None, an environment variable of this name
                                                will be defined with the value of this variable.
    """

    def _execute_workload_variable(app):
        # Always apply passes workload/workloads
        all_workloads = ramble.language.language_helpers.merge_definitions(
            workload, workloads, app.workloads, "workload", "workloads", "workload_variable"
        )

        when_list = ramble.language.language_helpers.build_when_list(
            when, app, name, "workload_variable"
        )

        if environment_variable_name is not None:
            env_var = ramble.definitions.variables.EnvironmentVariable(
                environment_variable_name,
                value=f"{{{name}}}",
                description=description,
                method="set",
                when=when_list,
            )
        else:
            env_var = None

        validation = strict and values

        # If a workload map is passed, handle that.
        if workload_defaults:
            if any([workload, workloads, workload_group, default]):
                raise DirectiveError(
                    "workload_defaults cannot be used with workload, workloads, "
                    "workload_group, or default"
                )

            for wl_name, wl_default in workload_defaults.items():
                workload_var = ramble.definitions.variables.Variable(
                    name,
                    default=wl_default,
                    description=description or f"Default for {name} for {wl_name}",
                    values=values,
                    expandable=expandable,
                    when=when_list,
                    **kwargs,
                )
                workload_var_when_frozenset = frozenset(workload_var.when)
                for when_set, app_workloads in app.workloads.items():
                    if wl_name in app_workloads:
                        if ramble.language.language_helpers.are_when_compatible(
                            when_set, workload_var_when_frozenset
                        ):
                            app.workloads[when_set][wl_name].add_variable(workload_var.copy())
                            if validation:
                                ramble.language.language_helpers.add_variable_validator(
                                    app, name, values, when_list, wl_name=wl_name
                                )
                            if env_var is not None:
                                app.workloads[when_set][wl_name].add_environment_variable(
                                    env_var.copy()
                                )
            return

        # Handle the remainder of the workload_variable directive, if
        # workload_defaults was not passed
        workload_var = ramble.definitions.variables.Variable(
            name,
            default=default,
            description=description,
            values=values,
            expandable=expandable,
            when=when_list,
            **kwargs,
        )

        workload_var_when_frozenset = frozenset(workload_var.when)
        for when_set, app_workloads in app.workloads.items():
            for wl_name in all_workloads:
                if wl_name in app_workloads:
                    if ramble.language.language_helpers.are_when_compatible(
                        when_set, workload_var_when_frozenset
                    ):
                        app.workloads[when_set][wl_name].add_variable(workload_var.copy())
                        if validation:
                            ramble.language.language_helpers.add_variable_validator(
                                app, name, values, when_list, wl_name=wl_name
                            )
                        if env_var:
                            app.workloads[when_set][wl_name].add_environment_variable(
                                env_var.copy()
                            )

        if workload_group is not None:
            workload_group_inst = app.workload_groups[workload_group]

            if workload_group not in app.workload_group_vars:
                app.workload_group_vars[workload_group] = []

            # Track which vars we add to, to allow us to re-apply during inheritance
            app.workload_group_vars[workload_group].append(workload_var.copy())
            if env_var:
                if workload_group not in app.workload_group_env_vars:
                    app.workload_group_env_vars[workload_group] = []
                app.workload_group_env_vars[workload_group].append(env_var.copy())

            for when_set, app_workloads in app.workloads.items():
                for (
                    wl_group_when_set,
                    workload_group_list,
                ) in workload_group_inst.workloads.items():
                    # Apply the variable
                    # Add wl group 'when' to variable to defer satisfies evaluation
                    workload_var_copy = workload_var.copy()
                    workload_var_copy.when += wl_group_when_set
                    var_when_frozenset = frozenset(workload_var_copy.when)

                    if env_var:
                        env_var_copy = env_var.copy()
                        env_var_copy.when += wl_group_when_set
                    else:
                        env_var_copy = None

                    for wl_name in workload_group_list:
                        if wl_name in app_workloads:
                            if ramble.language.language_helpers.are_when_compatible(
                                when_set, var_when_frozenset
                            ):
                                app.workloads[when_set][wl_name].add_variable(workload_var_copy)
                                if validation:
                                    ramble.language.language_helpers.add_variable_validator(
                                        app, name, values, when_list, wl_name=wl_name
                                    )
                                if env_var_copy:
                                    app.workloads[when_set][wl_name].add_environment_variable(
                                        env_var_copy
                                    )

        if not all_workloads and workload_group is None:
            raise DirectiveError("A workload or workload group is required")

    return _execute_workload_variable


@application_directive(dicts="license_names", init_value=[])
def license_name(name, **kwargs):
    """Add a new license name directive, to specify license name in a declarative way.

    Args:
        name (str): name to use during license lookup and propagation
    """

    def _execute_license_name(obj):
        license_from_base = getattr(obj, "license_names", [])

        # Here it is essential to copy, otherwise we might add to an empty list in the parent
        # It is important that we preserve order
        obj.license_names = list(dict.fromkeys(license_from_base + [name]))

    return _execute_license_name


@application_directive("cleanups")
def cleanup(
    name,
    regex,
    directory=None,
    recurse=False,
    description="",
    pre=False,
    post=False,
    when=None,
    **kwargs,
):
    """Adds a cleanup operation to the application.

    This directive defines a cleanup step that removes files matching a
    regular expression from a specified directory.

    Args:
        name (str): Name of the cleanup operation.
        regex (str): Regex passed to `find` to match files and directories to be deleted.
        directory (str): The directory to perform the cleanup in. Defaults to {experiment_run_dir}.
        recurse (bool): Whether to search for files recursively in subdirectories.
        description (str): Description of the cleanup operation.
        pre (bool): Whether to run this cleanup before the main application execution.
        post (bool): Whether to run this cleanup after the main application execution.
        when (list | None): List of when conditions to apply to this directive.
    """

    def _define_cleanup(obj):
        if not pre and not post:
            raise DirectiveError(
                f"Cleanup directive '{name}' must set at least one of 'pre' or 'post' to True."
            )
        when_list = ramble.language.language_helpers.build_when_list(when, obj, name, "cleanup")
        when_set = frozenset(when_list)
        if when_set not in obj.cleanups:
            obj.cleanups[when_set] = {}

        obj.cleanups[when_set][name] = {
            "description": description,
            "regex": regex,
            "directory": directory,
            "recurse": recurse,
            "pre": pre,
            "post": post,
            "when": when_list,
        }

    return _define_cleanup


@application_directive("executables")
def stage_files(
    src=None,
    dst=None,
    stages=None,
    name=None,
    method="user-defined",
    when=None,
    **kwargs,
):
    """Adds an executable that stages an input file or directory.

    Defines a new executable that copies or links a file or directory
    from a source to a destination. This is useful for staging input
    files that are not managed by the `input_file` directive.

    The staging method is controlled by the `stage_method` configuration
    option, which can be set to 'cp', 'rsync', 'symbolic_link', 'hard_link',
    or 'install' (for files only).

    Args:
        src (str | None): The source path of the file or directory.
        dst (str | None): The destination path. If src is passed in, and dst is
                          not, dst defaults to the experiment_run_dir.
        stages (list(tuple(str, str)) | None): A list of tuples describing pairs
                                               of src, dest locations to stage.
        name (str | None): The name of the executable. Defaults to 'stage-files'.
        method (str): The method to use for this stage. Can be one of:
                      "user-defined", "cp", "rsync", "symbolic_link",
                      "hard_link", "install"
        when (list | None): List of when conditions to apply to this directive.
    """

    valid_methods = ["user-defined", "cp", "rsync", "symbolic_link", "hard_link", "install"]

    method_map = {
        "cp": "cp -Lr",
        "rsync": "rsync -Lr",
        "symbolic_link": "ln -sf",
        "hard_link": "ln -f",
        "install": "install -m 755",
    }

    def _execute_stage_files(app):
        import os

        import ramble.config
        from ramble.util.executable import CommandExecutable

        exec_name = name if name else "stage-files"

        when_list = ramble.language.language_helpers.build_when_list(
            when, app, exec_name, "stage_files"
        )
        when_set = frozenset(when_list)
        if when_set not in app.executables:
            app.executables[when_set] = {}

        if (
            exec_name in app.executables[when_set]
            and not app.executables[when_set][exec_name].allow_extension
        ):
            raise DirectiveError(
                f"stage_files directive on application {app.name} is creating "
                f"has name attribute of '{exec_name}' which already exists "
                "as an executable. Please provide a unique name attribute."
            )

        if method not in valid_methods:
            raise DirectiveError(
                f"stage_files directive on application {app.name} was given an "
                f"invalid method argument of {method}.\n"
                f"Valid methods include: {valid_methods}"
            )

        stage_method = method
        if stage_method == "user-defined":
            cfg = ramble.config.config
            stage_method = cfg.get("config", {}).get("stage_method", "cp")
        stage_cmd = method_map[stage_method]

        template = []

        if src is not None:
            if dst is not None:
                parent_dir = os.path.dirname(dst)
                if parent_dir and parent_dir != ".":
                    template.insert(0, f"mkdir -p {parent_dir}")
                template.append(f"{stage_cmd} {src} {dst}")
            else:
                template.append(f"{stage_cmd} {src} {{experiment_run_dir}}/.")

        if isinstance(stages, list):
            for pair_src, pair_dst in stages:
                parent_dir = os.path.dirname(pair_dst)
                if parent_dir and parent_dir != ".":
                    template.append(f"mkdir -p {parent_dir}")

                template.append(f"{stage_cmd} {pair_src} {pair_dst}")

        app.executables[when_set][exec_name] = CommandExecutable(
            name=exec_name, template=template, allow_extension=True, when=when_list, **kwargs
        )

    return _execute_stage_files
