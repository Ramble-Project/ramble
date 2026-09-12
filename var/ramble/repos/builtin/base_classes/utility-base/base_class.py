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

import spack.util.environment

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
            except Exception as e:
                logger.debug(f"VCS check for {exec_path} failed: {e}")

        # Future VCS checks can be added here (e.g., hg, svn)

        return False

    def get_version(self, env=None, path=None, return_output=False):
        """Discover the version of this utility.
        Uses the provided environment or the system environment if None.
        Returns the version of the first valid provided executable.
        """
        import re
        import shutil
        import subprocess

        check_env = env.copy() if env is not None else os.environ.copy()

        if hasattr(self, "_runner_env") and env is None:
            self._runner_env.apply_modifications(check_env)

        env_path = check_env.get("PATH", os.environ.get("PATH", ""))
        if path and path != "system":
            bin_path = os.path.join(path, "bin")
            search_path = f"{bin_path}{os.pathsep}{path}"
        else:
            search_path = env_path

        if hasattr(self, "provided_executables") and self.provided_executables:
            for exec_list in self.provided_executables.values():
                for exec_info in exec_list:
                    exec_name = exec_info["executable"]
                    exec_path = shutil.which(exec_name, path=search_path)

                    if not exec_path:
                        continue

                    version_cmd = exec_info.get("version_cmd")
                    version_regex = exec_info.get("version_regex")

                    if version_cmd and version_regex:
                        try:
                            import shlex

                            cmd = shlex.split(version_cmd)
                            if cmd and cmd[0] == exec_name:
                                cmd[0] = exec_path

                            # Run the version command
                            result = subprocess.run(
                                cmd,
                                env=check_env,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True,
                                check=True,
                            )
                            output = result.stdout + result.stderr

                            # Extract the version using the regex
                            match = re.search(version_regex, output)
                            current_version = match.group(1) if match else None
                            if return_output:
                                return current_version, output
                            return current_version
                        except Exception as e:
                            logger.debug(
                                f"Error checking version for '{exec_name}': {e}"
                            )

        if return_output:
            return None, ""
        return None

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

        from ramble.definitions.versions import Version

        self.availability_error = None
        check_env = env if env is not None else os.environ.copy()

        env_path = check_env.get("PATH", os.environ.get("PATH", ""))
        if path and path != "system":
            bin_path = os.path.join(path, "bin")
            search_path = f"{bin_path}{os.pathsep}{path}"
        else:
            search_path = env_path

        if hasattr(self, "provided_executables") and self.provided_executables:
            for exec_list in self.provided_executables.values():
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
                            current_version, output = self.get_version(
                                env=env, path=path, return_output=True
                            )

                            if not current_version:
                                if exact_version and exact_match_via_vcs:
                                    current_version = None
                                else:
                                    self.availability_error = f"Could not determine version for '{exec_name}' using regex '{version_regex}'."
                                    return False

                            if current_version:
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

    def setup_runner_environment(self, workspace, obj_inst, path=None):
        """Return an EnvironmentModifications object to set when running commands within Ramble.

        Args:
            workspace (ramble.workspace.Workspace): Reference to the workspace that is being
                                                    acted on
            obj_inst: Instance of an object that contains this utility definition
            path (str): Optional string defining the path this utility should be found in

        Returns:
            EnvironmentModification: A reference to the environment modifications that should be
                                     applied for this utility.
        """
        if hasattr(obj_inst, "_get_app_inst"):
            app_inst = obj_inst._get_app_inst()
        else:
            app_inst = obj_inst

        expander = getattr(app_inst, "expander", None)
        if not expander and hasattr(app_inst, "app_inst"):
            expander = getattr(app_inst.app_inst, "expander", None)
        if not expander:
            import ramble.expander

            expander = ramble.expander.Expander(
                getattr(app_inst, "variables", {}) or {}, None
            )

        path_var = f"utility::{self.name}::path"
        utility_path = path
        if utility_path is None:
            val = None
            if (
                hasattr(app_inst, "variables")
                and app_inst.variables is not None
                and path_var in app_inst.variables
            ):
                val = app_inst.variables[path_var]
            elif (
                obj_inst is not None
                and hasattr(obj_inst, "variables")
                and obj_inst.variables is not None
                and path_var in obj_inst.variables
            ):
                val = obj_inst.variables[path_var]
            elif (
                hasattr(expander, "_variables")
                and expander._variables is not None
                and path_var in expander._variables
            ):
                val = expander._variables[path_var]

            if val is not None:
                utility_path = expander.expand_var(val)

        if not hasattr(self, "_runner_env_cache"):
            self._runner_env_cache = {}
        cache_key = (id(obj_inst), utility_path)
        if cache_key in self._runner_env_cache:
            return self._runner_env_cache[cache_key]

        env_mod = spack.util.environment.EnvironmentModifications()
        if utility_path == "system":
            self._runner_env = env_mod
            self._runner_env_cache[cache_key] = env_mod
            return env_mod

        def _satisfies(when_key):
            if hasattr(obj_inst, "satisfy_when"):
                return obj_inst.satisfy_when(when_key)
            if hasattr(app_inst, "satisfy_when"):
                return app_inst.satisfy_when(when_key)
            return True

        for when_key, configs in self.env_sources.items():
            if _satisfies(when_key):
                for config in configs:
                    script_path = expander.expand_var(config["script_path"])
                    if os.path.exists(script_path):
                        env_mod.extend(
                            spack.util.environment.EnvironmentModifications.from_sourcing_file(
                                script_path
                            )
                        )
                    elif not getattr(workspace, "dry_run", False):
                        logger.warn(
                            f"External dependency setup script not found at {script_path}"
                        )

        for when_key, configs in self.env_sets.items():
            if _satisfies(when_key):
                for config in configs:
                    var = expander.expand_var(config["var"])
                    value = expander.expand_var(config["value"])
                    env_mod.set(var, value)

        for when_key, configs in self.env_prepends.items():
            if _satisfies(when_key):
                for config in configs:
                    var = expander.expand_var(config["var"])
                    value = expander.expand_var(config["value"])
                    env_mod.prepend_path(var, value)

        for when_key, configs in self.env_appends.items():
            if _satisfies(when_key):
                for config in configs:
                    var = expander.expand_var(config["var"])
                    value = expander.expand_var(config["value"])
                    env_mod.append_path(var, value)

        self._runner_env = env_mod
        self._runner_env_cache[cache_key] = env_mod
        return self._runner_env

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
