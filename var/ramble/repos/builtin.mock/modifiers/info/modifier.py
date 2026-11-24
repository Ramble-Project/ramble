# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.modkit import *


class Info(BasicModifier):
    """Mock modifier to test info command. Should include all directives."""

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

    variant(
        "enable_auto_env_var",
        default=False,
        values=[True, False],
        description="Turn on auto env vars",
    )

    variable(
        "obj_var_name",
        default="default_obj_val",
        description="An obj var",
        when=["variant_name=a_variant_val"],
    )

    variable(
        "obj_auto_env_var",
        default="abc",
        description="A variable with env-var generation",
        environment_variable_name="OBJ_AUTO_ENV_VAR",
        when=["+enable_auto_env_var"],
    )

    environment_variable(
        "ENV_VAR_NAME",
        value="ENVVARVAL",
        description="test var",
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

    def builtin_name(test, **kwargs):
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

    # Modifier language directives
    mode("info-mode", "Info mode")
    mode("another-mode", "Another mode")
    default_mode("info-mode")

    modifier_variable(
        "mod_var_name",
        mode="info-mode",
        default="default_mod_var_val",
        description="A wl var",
        when=["variant_name=variant_default"],
    )

    executable_modifier(
        "exec_modifier_name",
        when=["+exec_modifier_active"],
    )

    def exec_modifier_name(self, exec_name, executable, app_inst=None):
        prepend_execs = []
        append_execs = [
            ramble.util.executable.CommandExecutable(
                name="test_exec_modifier_exec",
                template="echo 'append executable'",
                redirect=None,
                output_capture=None,
            )
        ]

        return prepend_execs, append_execs

    variable_modification(
        "var_mod_name",
        modification="test var modified",
        method="set",
        mode="test",
        when=["+variable_modification_active"],
    )

    package_manager_requirement(
        "list not-a-package",
        validation_type="not_empty",
        modes=["another-mode"],
    )

    env_var_modification(
        "ENV_VAR_MOD",
        modification="ENV_VAR_MOD_SET",
        method="set",
        mode="info-mode",
    )

    env_var_modification(
        "APP_ENV_VAR",
        method="unset",
        modes=["info-mode", "another-mode"],
    )

    env_var_modification(
        "ENV_VAR_MOD",
        modification="PREPEND",
        method="prepend",
        when=["info_mode=another-mode"],
    )

    env_var_modification(
        "ENV_VAR_MOD",
        modification="APPEND",
        method="append",
        mode="info-mode",
        separator="_",
    )
