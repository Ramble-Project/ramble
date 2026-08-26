# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import ramble.repository
import ramble.util.class_attributes
import ramble.variants
from ramble.language.shared_language import SharedMeta
from ramble.language.utility_language import UtilityMeta
from ramble.util.logger import logger
from ramble.util.naming import NS_SEPARATOR

ObjectMixin = ramble.repository.get_base_class("object-mixin")


class UtilityBase(ObjectMixin, metaclass=UtilityMeta):
    origin_type = "utility"
    _builtin_name = NS_SEPARATOR.join(
        ("utility_builtin", "{obj_name}", "{name}")
    )
    _language_classes = [UtilityMeta, SharedMeta]
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

        ramble.util.class_attributes.convert_class_attributes(self)

        self._file_path = file_path
        self.keywords = None

        self.object_variants.default_variant(
            self.origin_type,
            default=self.name,
            description="Name of external dependency for an experiment",
        )

    def _check_exact_match_via_vcs(self, exec_path, exact_version):
        """Check if the provided executable matches the exact version via VCS history."""
        import os
        import shutil
        import subprocess

        if not exec_path or not exact_version:
            return False

        # Resolve symlinks to find the actual repository directory
        real_exec_path = os.path.realpath(exec_path)
        exec_dir = os.path.dirname(real_exec_path)
        if not exec_dir:
            return False

        # Git check
        if shutil.which("git"):
            try:
                is_git = subprocess.run(
                    [
                        "git",
                        "-C",
                        exec_dir,
                        "rev-parse",
                        "--is-inside-work-tree",
                    ],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                    check=False,
                )
                if is_git.returncode == 0 and is_git.stdout.strip() == "true":
                    head_hash_res = subprocess.run(
                        ["git", "-C", exec_dir, "rev-parse", "HEAD"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                        check=False,
                    )
                    exact_hash_res = subprocess.run(
                        [
                            "git",
                            "-C",
                            exec_dir,
                            "rev-parse",
                            f"{exact_version}^{{commit}}",
                        ],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        universal_newlines=True,
                        check=False,
                    )
                    if (
                        head_hash_res.returncode == 0
                        and exact_hash_res.returncode == 0
                    ):
                        head_hash = head_hash_res.stdout.strip()
                        exact_hash = exact_hash_res.stdout.strip()
                        if (
                            head_hash
                            and exact_hash
                            and head_hash == exact_hash
                        ):
                            return True
            except Exception:
                pass

        # Future VCS checks can be added here (e.g., hg, svn)

        return False

    def validate_versions(
        self,
        min_version=None,
        max_version=None,
        exact_version=None,
        env=None,
        origin_name=None,
        origin_type=None,
        path=None,
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
        search_path = (
            path
            if path is not None
            else check_env.get("PATH", os.environ.get("PATH", ""))
        )

        # If the utility provides executables, check if they are in PATH
        if hasattr(self, "provided_executables") and self.provided_executables:
            for exec_list in self.provided_executables.values():
                # We could evaluate satisfy_when here, but for simple presence checks
                # we just check all provided executables. In the future this could be conditionally checked.
                for exec_info in exec_list:
                    exec_name = exec_info["executable"]
                    exec_path = shutil.which(exec_name, path=search_path)
                    if not exec_path:
                        self.availability_error = (
                            f"Executable '{exec_name}' not found in PATH."
                        )
                        return False

                    version_cmd = exec_info.get("version_cmd")
                    version_regex = exec_info.get("version_regex")

                    origin_str = (
                        f" (required by {origin_type} '{origin_name}')"
                        if origin_name and origin_type
                        else ""
                    )

                    # Check exact version via VCS if available
                    exact_match_via_vcs = self._check_exact_match_via_vcs(
                        exec_path, exact_version
                    )

                    if (
                        exact_match_via_vcs
                        and not min_version
                        and not max_version
                    ):
                        continue

                    if (
                        version_cmd
                        and version_regex
                        and (min_version or max_version or exact_version)
                    ):
                        try:
                            import shlex

                            # Run the version command
                            result = subprocess.run(
                                shlex.split(version_cmd),
                                env=check_env,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True,
                                check=True,
                            )
                            output = result.stdout + result.stderr

                            # Extract the version using the regex
                            match = re.search(version_regex, output)
                            if not match:
                                if exact_version and exact_match_via_vcs:
                                    # Git confirmed it, so lack of regex match is fine
                                    current_version = None
                                else:
                                    self.availability_error = f"Could not determine version for '{exec_name}' using regex '{version_regex}'."
                                    return False
                            else:
                                current_version = match.group(1)

                            # Compare versions
                            if (
                                min_version
                                and current_version
                                and Version(current_version)
                                < Version(min_version)
                            ):
                                self.availability_error = f"Version {current_version} for '{exec_name}' is less than required minimum {min_version}{origin_str}."
                                return False
                            if (
                                max_version
                                and current_version
                                and Version(current_version)
                                > Version(max_version)
                            ):
                                self.availability_error = f"Version {current_version} for '{exec_name}' is greater than required maximum {max_version}{origin_str}."
                                return False
                            if exact_version and not exact_match_via_vcs:
                                exact_version_str = str(exact_version)
                                if not current_version or (
                                    current_version != exact_version_str
                                    and not re.search(
                                        r"(?<![\w.])"
                                        + re.escape(exact_version_str)
                                        + r"(?![\w.])",
                                        output,
                                    )
                                ):
                                    self.availability_error = f"Version '{current_version}' (or output) for '{exec_name}' does not match required exact version '{exact_version}'{origin_str}."
                                    return False
                        except Exception as e:
                            if exact_version and exact_match_via_vcs:
                                pass
                            else:
                                # If anything fails (command fails, regex fails, version parse fails)
                                self.availability_error = f"Error checking version for '{exec_name}': {e}"
                                return False
                    elif exact_version and not exact_match_via_vcs:
                        self.availability_error = f"Exact version '{exact_version}' requested for '{exec_name}', but no version command is defined and it does not match git history."
                        return False

            # If there are provided executables and we didn't return False, they are all present
            return True

        self.availability_error = (
            "No provided executables defined to check availability."
        )
        return False

    def is_available(
        self,
        workspace,
        min_version=None,
        max_version=None,
        exact_version=None,
        path=None,
    ):
        """Check if the external dependency is already available on the system.
        If this returns True, Ramble will skip bootstrapping the external dependency.
        """
        return self.validate_versions(
            min_version=min_version,
            max_version=max_version,
            exact_version=exact_version,
            path=path,
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
