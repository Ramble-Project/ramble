# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import ramble.repository
from ramble.language.language_base import DirectiveMeta
from ramble.util.logger import logger
from ramble.util.naming import NS_SEPARATOR

ObjectMixin = ramble.repository.get_base_class("object-mixin")


class UtilityBase(ObjectMixin, metaclass=DirectiveMeta):
    origin_type = "utility"
    _builtin_name = NS_SEPARATOR.join(
        ("utility_builtin", "{obj_name}", "{name}")
    )
    _language_types = ["utility", "shared"]
    _language_classes = _language_types
    pipelines = [
        "setup",
    ]

    utility_class = "UtilityBase"

    def __init__(self, file_path):
        super().__init__()

        self.object_variants = ramble.variants.VariantSet()
        for var_args in self.class_variants.values():
            self.object_variants.default_variant(**var_args)

        self.env_sources = getattr(self, "env_sources", {})
        self.env_sets = getattr(self, "env_sets", {})
        self.env_prepends = getattr(self, "env_prepends", {})
        self.env_appends = getattr(self, "env_appends", {})
        self.fetch_mappings = getattr(self, "fetch_mappings", {})
        self.bootstrappable = getattr(self, "bootstrappable", {})
        self.missing_error_messages = getattr(
            self, "missing_error_messages", {}
        )
        self.provided_executables = getattr(self, "provided_executables", {})

        self._file_path = file_path
        self.keywords = None

        self.object_variants.default_variant(
            self.origin_type,
            default=self.name,
            description="Name of external dependency for an experiment",
        )

    def validate_versions(
        self,
        min_version=None,
        max_version=None,
        env=None,
        origin_name=None,
        origin_type=None,
    ):
        """Check if the provided executables are available and satisfy version constraints.
        Uses the provided environment or the system environment if None.
        """
        import re
        import shutil
        import subprocess

        from ramble.definitions.versions import Version

        self.availability_error = None
        check_env = env if env is not None else os.environ.copy()

        # When using a custom environment, we need to extract its PATH for shutil.which
        # Default to the current process PATH if not in the custom environment
        search_path = check_env.get("PATH", os.environ.get("PATH", ""))

        # If the utility provides executables, check if they are in PATH
        if hasattr(self, "provided_executables") and self.provided_executables:
            for exec_list in self.provided_executables.values():
                # We could evaluate satisfy_when here, but for simple presence checks
                # we just check all provided executables. In the future this could be conditionally checked.
                for exec_info in exec_list:
                    exec_name = exec_info["executable"]
                    if not shutil.which(exec_name, path=search_path):
                        self.availability_error = (
                            f"Executable '{exec_name}' not found in PATH."
                        )
                        return False

                    version_cmd = exec_info.get("version_cmd")
                    version_regex = exec_info.get("version_regex")

                    if (
                        version_cmd
                        and version_regex
                        and (min_version or max_version)
                    ):
                        try:
                            import shlex

                            # Run the version command
                            result = subprocess.run(
                                shlex.split(version_cmd),
                                env=check_env,
                                capture_output=True,
                                text=True,
                                check=True,
                            )
                            output = result.stdout + result.stderr

                            # Extract the version using the regex
                            match = re.search(version_regex, output)
                            if not match:
                                self.availability_error = f"Could not determine version for '{exec_name}' using regex '{version_regex}'."
                                return False

                            current_version = match.group(1)

                            origin_str = (
                                f" (required by {origin_type} '{origin_name}')"
                                if origin_name and origin_type
                                else ""
                            )

                            # Compare versions
                            if min_version and Version(
                                current_version
                            ) < Version(min_version):
                                self.availability_error = f"Version {current_version} for '{exec_name}' is less than required minimum {min_version}{origin_str}."
                                return False
                            if max_version and Version(
                                current_version
                            ) > Version(max_version):
                                self.availability_error = f"Version {current_version} for '{exec_name}' is greater than required maximum {max_version}{origin_str}."
                                return False
                        except Exception as e:
                            # If anything fails (command fails, regex fails, version parse fails)
                            self.availability_error = f"Error checking version for '{exec_name}': {e}"
                            return False
            # If there are provided executables and we didn't return False, they are all present
            return True

        self.availability_error = (
            "No provided executables defined to check availability."
        )
        return False

    def is_available(self, workspace, min_version=None, max_version=None):
        """Check if the external dependency is already available on the system.
        If this returns True, Ramble will skip bootstrapping the external dependency.
        """
        return self.validate_versions(
            min_version=min_version, max_version=max_version
        )

    def setup_runner_environment(self, workspace, app_inst):
        """Return an EnvironmentModifications object to set when running commands within Ramble."""
        import spack.util.environment

        env_mod = spack.util.environment.EnvironmentModifications()
        utility_path = app_inst.variables.get(f"utility::{self.name}::path")
        if utility_path == "system":
            return env_mod

        expander = getattr(app_inst, "expander", None)
        if not expander and hasattr(app_inst, "app_inst"):
            expander = getattr(app_inst.app_inst, "expander", None)
        if not expander:
            import ramble.expander

            expander = ramble.expander.Expander(app_inst.variables, None)

        for when_key, configs in self.env_sources.items():
            if app_inst.satisfy_when(when_key):
                for config in configs:
                    script_path = expander.expand_var(config["script_path"])
                    if os.path.exists(script_path):
                        env_mod.extend(
                            spack.util.environment.EnvironmentModifications.from_sourcing_file(
                                script_path
                            )
                        )
                    elif not workspace.dry_run:
                        logger.warn(
                            f"External dependency setup script not found at {script_path}"
                        )

        for when_key, configs in self.env_sets.items():
            if app_inst.satisfy_when(when_key):
                for config in configs:
                    var = expander.expand_var(config["var"])
                    value = expander.expand_var(config["value"])
                    env_mod.set(var, value)

        for when_key, configs in self.env_prepends.items():
            if app_inst.satisfy_when(when_key):
                for config in configs:
                    var = expander.expand_var(config["var"])
                    value = expander.expand_var(config["value"])
                    env_mod.prepend_path(var, value)

        for when_key, configs in self.env_appends.items():
            if app_inst.satisfy_when(when_key):
                for config in configs:
                    var = expander.expand_var(config["var"])
                    value = expander.expand_var(config["value"])
                    env_mod.append_path(var, value)

        return env_mod

    def get_experiment_activation_command(self, workspace, app_inst):
        """Return a bash command string that activates this external dependency in the experiment's execution environment."""
        import ramble.config
        from ramble.util.shell_utils import source_str

        shell = ramble.config.get("config:shell")
        src_cmd = source_str(shell)

        commands = []
        utility_path = app_inst.variables.get(f"utility::{self.name}::path")
        if utility_path == "system":
            return ""

        expander = getattr(app_inst, "expander", None)
        if not expander and hasattr(app_inst, "app_inst"):
            expander = getattr(app_inst.app_inst, "expander", None)
        if not expander:
            import ramble.expander

            expander = ramble.expander.Expander(app_inst.variables, None)

        for when_key, configs in self.env_sources.items():
            if app_inst.satisfy_when(when_key):
                for config in configs:
                    script_path = expander.expand_var(config["script_path"])
                    cmd = f"{{source_cmd}} {script_path}"
                    cmd = cmd.replace("{source_cmd}", src_cmd)
                    commands.append(cmd)

        for when_key, configs in self.env_sets.items():
            if app_inst.satisfy_when(when_key):
                for config in configs:
                    var = expander.expand_var(config["var"])
                    value = expander.expand_var(config["value"])
                    commands.append(f"export {var}={value}")

        for when_key, configs in self.env_prepends.items():
            if app_inst.satisfy_when(when_key):
                for config in configs:
                    var = expander.expand_var(config["var"])
                    value = expander.expand_var(config["value"])
                    commands.append(f"export {var}={value}:${var}")

        for when_key, configs in self.env_appends.items():
            if app_inst.satisfy_when(when_key):
                for config in configs:
                    var = expander.expand_var(config["var"])
                    value = expander.expand_var(config["value"])
                    commands.append(f"export {var}=${var}:{value}")

        return "\n".join(commands)

    def map_fetch_kwargs(self, fetch_kwargs):
        """Hook to map custom external dependency variables to standard Ramble fetcher kwargs."""
        mapped = fetch_kwargs.copy()
        for when_key, configs in self.fetch_mappings.items():
            if not when_key:
                for config in configs:
                    utility_var = config["utility_var"]
                    fetch_var = config["fetch_var"]
                    fallback_for = config["fallback_for"]

                    if utility_var in mapped:
                        val = mapped.pop(utility_var)
                        if not any(k in mapped for k in fallback_for):
                            mapped[fetch_var] = val
        return mapped

    def modify_bootstrap(self, workspace, app_inst):
        """Hook to allow external dependency to modify its own bootstrap installation.

        Args:
            workspace: The current workspace object
            app_inst: The application instance that triggered the bootstrap
        """
