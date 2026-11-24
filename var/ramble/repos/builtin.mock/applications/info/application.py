# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.appkit import *


class Info(ExecutableApplication):
    """Mock application to test info command. Should include all directives."""

    name = "info"

    # Shared language directives
    maintainers("maintainername")

    tags("tag1", "tag2")

    version("1.0", description="Version 1.0 of info", preferred=True)
    version("2.0", description="Version 2.0 of info")

    variant(
        "variant_name",
        default="variant_default",
        values=["variant_default", "a_variant_val"],
        description="A variant",
    )

    variant(
        "turn_on_required_directives",
        default=False,
        values=[True, False],
        description="Keep required directives off by default for testing",
    )

    variable(
        "obj_var_name",
        default="default_obj_val",
        description="An obj var",
        when=["variant_name=a_variant_val"],
    )

    required_variable(
        "required_var_name",
        description="A required var",
        when=["+turn_on_required_directives"],
    )

    archive_pattern("{experiment_run_dir}/archive_test.*")

    figure_of_merit_context(
        "fom_context", regex=r"fom context regex.*", output_format="{test}"
    )

    figure_of_merit(
        "fom_name",
        fom_regex=r"fom regex.*",
        group_name="test",
        units="s",
    )

    with when("application_version@1.0:"):

        define_compiler("gcc12", pkg_spec="gcc@12.2.0")

        software_spec(
            "info-app",
            pkg_spec="info-app@5.0",
            compiler="gcc12",
        )

        package_manager_config(
            "config_name",
            "config:true",
            when="package_manager=info",
        )

        required_package(
            "info-app-dep",
            when=["package_manager=info", "+turn_on_required_directives"],
        )

        success_criteria(
            "success_criteria_name",
            mode="string",
            match=r"fom: test",
            file="log.file",
        )

    register_builtin("builtin_name", required=True)

    def builtin_name():
        return ['echo "builtin"']

    register_phase(
        "after_make_experiments",
        pipeline="setup",
        run_after=["make_experiments"],
    )

    def _after_make_experiments(self, workspace, app_inst=None):
        logger.all_msg("Inside a phase: after_make_experiments")

    target_shells("bash")

    register_template(
        "template_name",
        src_path="$workspace_shared/test_template.tpl",
        dest_path="test_template",
        when=["+register_template_when"],
    )

    formatted_executable(
        "formatted_exec_name",
        prefix="",
        indentation="4",
        commands=["{unformatted_batch_command}"],
    )

    register_validator(
        name="validator_name",
        predicate="{n_nodes} == 1",
        message=("Give me a node, Vasili. One node only, please"),
        fail_on_invalid=False,
    )

    conflict(
        "turn_on_required_directives=True",
        when="variant_name=variant_default",
        msg="turn_on_required_directives conflicts with variant_default",
    )

    deprecate(
        deprecated_in="0.7.0",
        removed_in="99.0.0",
        replacement="new-info",
        msg="Use new-info instead",
        when=["+turn_on_required_directives"],
    )

    # Application language directives
    license_name("license_name")

    executable(
        "exec_name", template=["exec template", "command"], use_mpi=False
    )

    workload("wl_name", executables=["exec_name"], input="input_name")
    workload_group("wl_group", workloads=["wl_name"])

    input_file(
        "input_name", url="file:///tmp/test_file.log", description="A file"
    )

    workload_variable(
        "wl_var_name",
        default="default_wl_val",
        description="A wl var",
        workload="wl_name",
        when=["variant_name=variant_default"],
    )

    variable(
        "obj_var_name",
        default="default_obj_val",
        description="An obj var",
        when=["variant_name=a_variant_val"],
    )

    environment_variable(
        "ENV_VAR_NAME",
        value="ENVVARVAL",
        description="test var",
        workload="wl_name",
    )
