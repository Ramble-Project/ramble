# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

from ramble.modkit import *


class ContainerBase(BasicModifier):
    """This base modifier contains many of the variable and method definitions
    that containerized runtimes need to implement individual modifiers. It is
    used as a layer to standardize the interface for the containerized runtimes,
    to give them a consistent behavior within Ramble."""

    name = "container-base"

    tags("container")

    maintainers("douglasjacobsen")

    variant(
        "containerized",
        default=True,
        description="Whether this experiment is run inside a container",
    )

    mode("standard", description="Standard execution mode")
    default_mode("standard")

    required_variable(
        "container_uri",
        description="The variable controls the URI the container is pulled from. "
        "This should be of the format accepted by this container runtime.",
        modes=["standard"],
    )

    modifier_variable(
        "container_mounts",
        default="",
        description="Comma delimited list of mount points for the container. Filled in by modifier",
        modes=["standard"],
    )

    modifier_variable(
        "container_env_vars",
        default="",
        description="Comma delimited list of environments to import into container. Filled in by modifier",
        modes=["standard"],
    )

    modifier_variable(
        "container_extract_dir",
        default="{workload_input_dir}",
        description="Directory where the extracted paths will be stored",
        modes=["standard"],
    )

    modifier_variable(
        "container_extract_paths",
        default="[]",
        description="List of paths to extract from the sqsh file into the {workload_input_dir}. "
        + "Will have paths of {workload_input_dir}/enroot_extractions/{path_basename}",
        modes=["standard"],
        track_used=False,
    )

    def _build_runner(
        self, runtime, check_software_env=False, app_inst=None, dry_run=False
    ):
        """Construct command runner for container runtime"""

        runner_name = f"{runtime}_runner"

        if (
            not hasattr(self, runner_name)
            or getattr(self, runner_name) is None
        ):
            path = None
            # If using spack, load spack environment before getting container runtime exec path
            if check_software_env and app_inst.package_manager is not None:
                if app_inst.package_manager.spec_prefix == "spack":
                    app_inst.package_manager.runner.activate()
                    _, base = app_inst.package_manager.runner.get_package_path(
                        runtime
                    )
                    app_inst.package_manager.runner.deactivate()

                    if base and os.path.exists(base):
                        test_path = os.path.join(base, "bin")
                        if os.path.isdir(test_path):
                            path = test_path

            exec_runner = CommandRunner(
                name=runtime,
                command=runtime,
                dry_run=dry_run,
                path=path,
            )

            setattr(self, runner_name, exec_runner)

    register_phase(
        "define_container_variables",
        pipeline="setup",
        run_before=["get_inputs"],
    )

    def _define_container_variables(self, workspace, app_inst=None):
        """Define helper variables for working with containerized experiments

        To ensure it is defined properly, construct a comma delimited list of
        environment variable names that will be added into the
        container_env_vars variable.
        """

        def extract_names(itr, name_set=None):
            """Extract names of environment variables from the environment variable action sets

            Given an iterator over environment variable action sets, extract
            the names of the environment variables.

            Modifies the name_set argument inplace.
            """
            if name_set is None:
                name_set = set()
            for action, conf in itr:
                if action in ["set", "unset"]:
                    for name in conf:
                        name_set.add(name)
                elif action == "prepend":
                    for group in conf:
                        for name in group["paths"]:
                            name_set.add(name)
                elif action == "append":
                    for group in conf:
                        for name in group["vars"]:
                            name_set.add(name)

        # Define container_env-vars
        set_names = set()

        for env_var_set in app_inst._env_variable_sets:
            extract_names(env_var_set.items(), set_names)

        for mod_inst in app_inst._modifier_instances:
            for env_var_mod in mod_inst.all_env_var_modifications():
                set_names.add(env_var_mod.name)

        env_var_list = ",".join(set_names)
        app_inst.define_variable("container_env_vars", env_var_list)

        # Define container_mounts
        input_mounts = app_inst.expander.expand_var("{container_mounts}")

        workload = app_inst.get_workload()

        exp_mount = "{experiment_run_dir}:{experiment_run_dir}"
        if len(workload.inputs) > 0:
            exp_mount += ",{workload_input_dir}:{workload_input_dir}"

        expanded_exp_mount = app_inst.expander.expand_var(exp_mount)

        if (
            exp_mount not in input_mounts
            and expanded_exp_mount not in input_mounts
        ):
            add_mod = True
            for when_set, var_mod_dict in self.variable_modifications.items():
                if self.expander.satisfies(
                    when_set, self.experiment_variants()
                ):
                    if "container_mounts" in var_mod_dict:
                        add_mod = False
                        break
            if add_mod:
                self.variable_modification(
                    "container_mounts",
                    modification=exp_mount,
                    separator=",",
                    method="append",
                    mode=self._usage_mode,
                )
