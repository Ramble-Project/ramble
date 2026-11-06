# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import pathlib
import re
import shlex
import shutil
import sys
import tempfile

import llnl.util.filesystem as fs

from ramble.pkgmankit import *
from ramble.util.command_runner import RunnerError
from ramble.util.logger import logger

import spack.util.spack_yaml as syaml
from spack.util.executable import ProcessError, which


class SpackLightweight(PackageManagerBase):
    requires_utility("spack")
    """Lightweight version of Spack package manager class definition

    This implements most of the logic for the spack package manager. The
    primary difference is the software_install and define_package_paths are not
    executed during setup, as they should be deferred to installation time.

    The installation portion is not defined in this class, as applications that
    require this should add this on separately.
    """

    name = "spack-lightweight"

    _spec_prefix = "spack"

    package_manager_family("spack")

    def __init__(self, file_path):
        super().__init__(file_path)
        self.output_prefix = self._spec_prefix

        self._runner = None

    name_regex = re.compile(r"\s*(?P<name>[\w-]+).*")

    def package_name_from_spec(self, spec):
        m = self.name_regex.match(spec)
        pkg_name = None
        if m:
            pkg_name = m.group("name")

        return pkg_name

    @property
    def runner(self):
        env = None
        app_inst = self._get_app_inst()
        if hasattr(app_inst, "experiment_runner_env"):
            env = app_inst.experiment_runner_env

        if self._runner is None or self._runner.env != env:
            self._runner = SpackRunner(env=env)
        return self._runner

    variant(
        "spack_install_compilers",
        default=True,
        description="Whether spack should install compilers or not",
    )

    register_phase(
        "software_install_requested_compilers",
        pipeline="setup",
        run_after=["software_create_env"],
        when="+spack_install_compilers",
    )

    def _software_install_requested_compilers(self, workspace, app_inst=None):
        """Install compilers an application uses"""

        # See if we cached this already, and if so return
        env_path = app_inst.expander.env_path
        if not env_path:
            raise PackageManagerError("Ramble env_path is set to None.")
        logger.msg("Installing compilers")

        cache_tupl = ("spack-compilers", env_path)
        if workspace.check_cache(cache_tupl):
            logger.debug(f"{cache_tupl} already in cache.")
            return
        else:
            workspace.add_to_cache(cache_tupl)

        try:
            self.runner.set_compiler_config_dir(
                workspace.auxiliary_software_dir
            )
            self.runner.set_dry_run(workspace.dry_run)

            app_context = app_inst.expander.expand_var_name(
                self.keywords.env_name
            )

            require_env = self.environment_required
            software_envs = workspace.software_environments
            software_env = software_envs.render_environment(
                app_context, app_inst.expander, self, require=require_env
            )

            if software_env is not None:
                for (
                    pkg_spec,
                    compiler_spec,
                ) in software_envs.compiler_specs_for_environment(
                    software_env
                ):
                    logger.debug(
                        f"Installing compiler: {compiler_spec} with pkg_spec {pkg_spec}"
                    )
                    self.runner.install_compiler(pkg_spec, compiler_spec)

        except RunnerError as e:
            logger.die(e)

    def merge_software_file(self, existing_file: str, new_file: str):
        """Merge a software file into an existing file

        If the files will be YAML files, uses Spack's config commands to handle
        merging. If they are not, new file always overwrites existing file.

        Args:
            existing_file: Path to existing file to merge into
            new_file: Path to stage file that will be merged
        """
        file_name = os.path.basename(new_file)
        file_name_parts = os.path.splitext(file_name)
        added = False
        if file_name_parts[-1] == ".yaml":
            try:
                self.runner.add_config_file(new_file)
                added = True
            except SystemExit:
                added = False

        if not added:
            if os.path.isfile(existing_file):
                logger.warn(
                    "Auxiliary software file is overwriting an existing file.\n"
                    f"   Existing file: {existing_file}\n"
                    f"   New file: {new_file}\n"
                )
            shutil.copyfile(new_file, existing_file)

    register_phase("software_create_env", pipeline="setup")
    register_phase("software_create_env", pipeline="pushdeployment")

    def _software_create_env(self, workspace, app_inst=None):
        """Create the spack environment for this experiment

        Extract all specs this experiment uses, and write the spack environment
        file for it.
        """

        logger.msg("Creating Spack environment")

        # Ignore externally active spack environment
        if "SPACK_ENV" in os.environ and not os.path.isdir(
            os.environ["SPACK_ENV"]
        ):
            _spack_vars = ["SPACK_ENV", "SPACK_ENV_VIEW"]
            for var in _spack_vars:
                os.environ.pop(var, None)

        # See if we cached this already, and if so return
        env_path = app_inst.expander.env_path
        if not env_path:
            raise PackageManagerError("Ramble env_path is set to None.")

        cache_tupl = ("spack-env", env_path)
        if workspace.check_cache(cache_tupl):
            logger.debug(f"{cache_tupl} already in cache.")
            return
        else:
            workspace.add_to_cache(cache_tupl)

        for _, obj in reversed(list(app_inst.objects())):
            for config in obj.package_manager_configs.values():
                if obj.satisfy_when(config["when"]):
                    self.runner.add_config(config["config"])

        try:
            self.runner.set_dry_run(workspace.dry_run)
            self.runner.create_env(
                app_inst.expander.expand_var_name(self.keywords.env_path)
            )
            self.runner.activate()

            env_context = app_inst.expander.expand_var_name(
                self.keywords.env_name
            )
            require_env = self.environment_required
            software_envs = workspace.software_environments
            software_env = software_envs.render_environment(
                env_context, app_inst.expander, self, require=require_env
            )
            stage_env_path = None
            if software_env is not None:
                if isinstance(software_env, ExternalEnvironment):
                    stage_env_path = self.runner.create_stage_env()
                    self.runner.copy_from_external_env(
                        software_env.external_env, stage_env_path
                    )
                else:
                    for (
                        pkg_spec
                    ) in software_envs.package_specs_for_environment(
                        software_env
                    ):
                        self.runner.add_spec(pkg_spec)

                    added_packages = set(self.runner.added_packages())
                    for pkg, conf in app_inst.required_packages.items():
                        if (
                            self.satisfy_when(conf["when"])
                            and pkg not in added_packages
                        ):
                            logger.die(
                                f"Software spec {pkg} is not defined "
                                f"in environment {env_context}, but is "
                                f"required by the {self.name} application "
                                "definition"
                            )

                    for mod_inst in app_inst._modifier_instances:
                        for pkg, conf in mod_inst.required_packages.items():
                            if (
                                app_inst.expander.satisfies(
                                    conf["when"],
                                    variant_set=self.experiment_variants(
                                        include_modifier=mod_inst
                                    ),
                                )
                                and pkg not in added_packages
                            ):
                                logger.die(
                                    f"Software spec {pkg} is not defined "
                                    f"in environment {env_context}, but is "
                                    f"required by the {mod_inst.name} modifier "
                                    "definition"
                                )

                    stage_env_path = self.runner.create_stage_env()

            if stage_env_path:
                self.runner.apply_configs(stage_path=stage_env_path)

            self.render_object_auxiliary_software_files(
                workspace, app_inst, stage_path=stage_env_path
            )

            self.runner.migrate_stage_env(
                stage_env_path,
                app_inst.expander.expand_var_name(self.keywords.env_path),
            )

            self.runner.deactivate()

        except RunnerError as e:
            logger.die(e)

    register_phase(
        "software_configure",
        pipeline="setup",
        run_after=[
            "software_create_env",
            "software_install_requested_compilers",
        ],
    )

    def _software_configure(self, workspace, app_inst=None):
        """Concretize the spack environment for this experiment

        Perform spack's concretize step on the software environment generated
        for  this experiment.
        """

        logger.msg("Concretizing Spack environment")

        # See if we cached this already, and if so return
        env_path = app_inst.expander.env_path

        cache_tupl = ("concretize-env", env_path)
        if workspace.check_cache(cache_tupl):
            logger.debug(f"{cache_tupl} already in cache.")
            return
        else:
            workspace.add_to_cache(cache_tupl)

        try:
            self.runner.set_dry_run(workspace.dry_run)

            self.runner.activate()

            env_concretized = self.runner.concretized

            if not env_concretized:
                self.runner.concretize()

        except RunnerError as e:
            logger.die(e)

    register_phase(
        "evaluate_requirements",
        pipeline="setup",
        run_before=["make_experiments"],
    )

    def _evaluate_requirements(self, workspace, app_inst=None):
        """Evaluate all requirements for this experiment"""

        for mod_inst in app_inst._modifier_instances:
            for req in mod_inst.all_package_manager_requirements():
                expanded_req = {}
                for key, val in vars(req).items():
                    expanded_req[key] = app_inst.expander.expand_var(val)
                self.runner.validate_command(**expanded_req)

    register_phase("mirror_software", pipeline="mirror")

    def _mirror_software(self, workspace, app_inst=None):
        """Mirror software source for this experiment using spack"""
        import re

        logger.msg("Mirroring software")

        # See if we cached this already, and if so return
        env_path = app_inst.expander.env_path
        if not env_path:
            raise PackageManagerError("Ramble env_path is set to None.")

        if not os.path.exists(env_path) or not os.path.isfile(
            os.path.join(env_path, "spack.lock")
        ):
            raise PackageManagerError(
                f"Spack environment {env_path} does not exist, or has not been concretized."
            )

        cache_tupl = ("spack-mirror", env_path)
        if workspace.check_cache(cache_tupl):
            logger.debug(f"{cache_tupl} already in cache.")
            return
        else:
            workspace.add_to_cache(cache_tupl)

        try:
            self.runner.set_dry_run(workspace.dry_run)
            self.runner.set_env(env_path)

            self.runner.activate()

            mirror_output = self.runner.mirror_environment(
                workspace.software_mirror_path
            )

            present = 0
            added = 0
            failed = 0

            present_regex = re.compile(r"\s+(?P<num>[0-9]+)\s+already present")
            present_match = present_regex.search(mirror_output)
            if present_match:
                present = int(present_match.group("num"))

            added_regex = re.compile(r"\s+(?P<num>[0-9]+)\s+added")
            added_match = added_regex.search(mirror_output)
            if added_match:
                added = int(added_match.group("num"))

            failed_regex = re.compile(r"\s+(?P<num>[0-9]+)\s+failed to fetch.")
            failed_match = failed_regex.search(mirror_output)
            if failed_match:
                failed = int(failed_match.group("num"))

            added_start = len(workspace.software_mirror_stats.new)
            for i in range(added_start, added_start + added):
                workspace.software_mirror_stats.new[i] = i

            present_start = len(workspace.software_mirror_stats.present)
            for i in range(present_start, present_start + present):
                workspace.software_mirror_stats.present[i] = i

            error_start = len(workspace.software_mirror_stats.errors)
            for i in range(error_start, error_start + failed):
                workspace.software_mirror_stats.errors.add(i)

        except RunnerError as e:
            if self.environment_required:
                logger.die(e)

    register_phase("push_to_spack_cache", pipeline="pushtocache", run_after=[])

    def _push_to_spack_cache(self, workspace, app_inst=None):

        # Test if experiment requires an environment
        env_required = self.environment_required

        env_path = app_inst.expander.env_path
        cache_tupl = ("push-to-cache", env_path)
        if workspace.check_cache(cache_tupl):
            logger.debug(f"{cache_tupl} already pushed, skipping")
            return
        else:
            workspace.add_to_cache(cache_tupl)

        try:
            self.runner.set_dry_run(workspace.dry_run)
            self.runner.set_env(env_path, require_exists=env_required)
            self.runner.activate()

            app_context = app_inst.expander.expand_var_name(
                self.keywords.env_name
            )
            software_envs = workspace.software_environments
            require_env = self.environment_required
            software_env = software_envs.render_environment(
                app_context, app_inst.expander, self, require=require_env
            )
            compiler_specs = [
                spec
                for spec, _ in software_envs.compiler_specs_for_environment(
                    software_env
                )
            ]

            self.runner.push_to_spack_cache(
                workspace.spack_cache_path, compiler_specs
            )

            # push_to_spack_cache deactivates env, this is here for safety.
            self.runner.deactivate()
        except RunnerError as e:
            if self.environment_required:
                logger.die(e)

    @PackageManagerBase.workspace_cache
    def get_version(self, workspace=None):
        return self.runner.get_version()

    def populate_inventory(
        self, workspace, force_compute=False, require_exist=False
    ):
        """Add software environment information to hash inventory"""

        env_path = self.app_inst.expander.env_path
        self.runner.set_dry_run(workspace.dry_run)
        self.runner.set_env(env_path, require_exists=False)
        self.runner.activate()

        self.app_inst.hash_inventory["software"].append(
            {
                "name": self.runner.env_path.replace(
                    workspace.root + os.path.sep, ""
                ),
                "package_manager": self.name,
                "digest": self.runner.inventory_hash(),
            }
        )
        self.runner.deactivate()

    def _clean_hash_variables(self, workspace, variables):
        """Perform spack specific cleanup of variables before hashing"""

        self.runner.configure_env(
            self.app_inst.expander.expand_var_name(self.keywords.env_path)
        )
        self.runner.activate()

        for var in variables:
            if isinstance(variables[var], str):
                variables[var] = variables[var].replace(
                    "\n".join(self.runner.generate_source_command()),
                    "spack_source",
                )
                variables[var] = variables[var].replace(
                    "\n".join(self.runner.generate_activate_command()),
                    "spack_activate",
                )

        self.runner.deactivate()

        super()._clean_hash_variables(workspace, variables)

    register_phase(
        "deploy_spack_artifacts",
        pipeline="pushdeployment",
        run_after=["software_create_env", "deploy_artifacts"],
    )

    def _deploy_spack_artifacts(self, workspace, app_inst=None):
        env_path = app_inst.expander.env_path

        try:
            self.runner.set_dry_run(workspace.dry_run)
            self.runner.set_env(env_path)
            self.runner.activate()

            # Hard-code a repo.yaml for spack packages
            # TODO: Put spack packages based on their original namespaces
            repo_root = os.path.join(
                workspace.deployment_repos_dir, "spack", "obj_repo"
            )
            fs.mkdirp(repo_root)
            with open(
                os.path.join(repo_root, "repo.yaml"), "w+", encoding="utf-8"
            ) as f:
                f.write("repo:\n")
                f.write("  namespace: obj_repo\n")

            for _, pkg_def in self.runner.package_definitions():
                pkg_dir_name = os.path.basename(os.path.dirname(pkg_def))
                pkg_dir = os.path.join(repo_root, "packages", pkg_dir_name)
                fs.mkdirp(pkg_dir)
                shutil.copyfile(pkg_def, os.path.join(pkg_dir, "package.py"))

            self.runner.deactivate()

        except RunnerError as e:
            if self.environment_required:
                logger.die(e)

    register_builtin(
        "spack_source", required=True, depends_on=["builtin::env_vars"]
    )
    register_builtin(
        "spack_activate",
        required=True,
        depends_on=[
            "package_manager_builtin::spack-lightweight::spack_source"
        ],
    )
    register_builtin(
        "spack_deactivate",
        required=False,
        depends_on=[
            "package_manager_builtin::spack-lightweight::spack_source"
        ],
    )

    def spack_source(self):
        if (
            hasattr(self.app_inst, "variables")
            and "utility::spack::activation_command" in self.app_inst.variables
        ):
            if self.app_inst.variables["utility::spack::activation_command"]:
                return ["{utility::spack::activation_command}"]
        return self.runner.generate_source_command()

    def spack_activate(self):
        self.runner.configure_env(
            self.app_inst.expander.expand_var_name(self.keywords.env_path)
        )
        self.runner.activate()
        cmds = self.runner.generate_activate_command()
        self.runner.deactivate()
        return cmds

    def spack_deactivate(self):
        return self.runner.generate_deactivate_command()

    def environment_load_commands(self):
        return self.spack_activate()

    def environment_unload_commands(self):
        return self.spack_deactivate()

    def get_spec_str(self, pkg, all_pkgs, compiler):
        """Return a spec string for the given pkg

        Args:
            pkg (RenderedPackage): Reference to a rendered package
            all_pkgs (dict): All related packages
            compiler (boolean): True if this pkg is used as a compiler
        """
        if compiler and pkg.compiler_spec:
            out_str = pkg.compiler_spec
        else:
            out_str = pkg.spec

        if compiler:
            return out_str

        if pkg.compiler in all_pkgs[self.name]:
            out_str += " %" + all_pkgs[self.name][pkg.compiler].spec_str(
                all_pkgs, compiler=True
            )
        elif pkg.compiler:
            out_str += f" (built with {pkg.compiler})"
        return out_str

    def get_package_list(self, workspace):
        """Augment the owning experiment's results with software stack information

        This is called by the `add_software_to_results` phase registered in the base
        package manager class.
        """
        del workspace
        self.runner.activate()
        pkg_list = list(self.runner.package_provenance())
        self.runner.deactivate()
        return pkg_list

    package_manager_variable(
        "container_registry_name",
        default="non-existent",
        description="Name of the container registry to push image to",
    )

    package_manager_variable(
        "container_base_image",
        default="",
        description="Base image for the container",
    )

    package_manager_variable(
        "container_image_tag",
        default="",
        description="Tag for the container image",
    )

    variant(
        "spack_push_container_image_script",
        default=False,
        values=[True, False],
        description="When set, create a script for pushing the container image",
    )

    register_template(
        name="push_container_image",
        src_path="push_container_image.sh.tpl",
        dest_path="push_container_image.sh",
        extra_vars_func="push_container_image_vars",
        when=["+spack_push_container_image_script"],
    )

    def _push_container_image_vars(self):
        self.runner.activate()
        source_cmd = "\n".join(self.runner.generate_source_command())
        activate_cmd = "\n".join(self.runner.generate_activate_command())
        self.runner.deactivate()
        user_flags = ramble.config.get(
            f"{self.runner.buildcache_config_name}:flags"
        )
        if user_flags is not None:
            additional_args = user_flags
        else:
            additional_args = ""
        return {
            "source_cmd": source_cmd,
            "activate_cmd": activate_cmd,
            "additional_args": additional_args,
        }


spack_namespace = "spack"

package_name_regex = re.compile(r"[\s-]*(?P<package_name>[\w][\w-]+).*")


class SpackSoftwareInfo(ramble.software_info.SoftwareInfo):
    def parse_from_string(self, in_str):
        """Construct a package dictionary from a comma delimited spec string

        Args:
            in_str (str): Comma delimited string from spack about a package spec.
                          It is assumed to be of the format:
                          {name},{version},{compiler_name},{compiler_version},{variants}

        Returns:
            (dict): Dictionary representing the package information
        """
        parts = in_str.split(",")

        if len(parts) >= 1:
            self.name = parts[0].strip()

            if len(parts) >= 2:
                self.version = parts[1]

            if len(parts) >= 3:
                self.compiler = parts[2]

            if len(parts) >= 4:
                self.compiler_version = parts[3]

            if len(parts) >= 5:
                self.target = parts[4]

            if len(parts) >= 6:
                self.variants = ",".join(parts[5:]).strip()


class SpackRunner(CommandRunner):
    """Runner for executing several spack commands

    The SpackRunner class is primarily used to manage spack environments
    for executing experiments under.

    This class provides methods for creating and manaving spack environments,
    and for ensuring required compilers are installed. It also provides a
    method for generating variables that can be used to ensure a spack env
    is loaded within an execution script.
    """

    env_key = "SPACK_ENV"

    global_config_name = "config:spack:global"
    install_config_name = "config:spack:install"
    compiler_find_config_name = "config:spack:compiler_find"
    buildcache_config_name = "config:spack:buildcache"
    concretize_config_name = "config:spack:concretize"
    env_create_config_name = "config:spack:env_create"

    env_create_args = ["env", "create", "-d", "."]

    compiler_find_args = ["compiler", "find"]

    # This cache is to avoid duplicate spack compiler calls for pkg_specs within an env
    _compiler_cache: dict = {}

    _allowed_config_files = [
        "compilers.yaml",
        "concretizer.yaml",
        "mirrors.yaml",
        "repos.yaml",
        "packages.yaml",
        "modules.yaml",
        "config.yaml",
        "upstreams.yaml",
        "bootstrap.yaml",
        "spack.yaml",
        "spack_includes.yaml",
    ]

    def __init__(self, shell="bash", dry_run=False, env=None):
        """
        Ensure spack is found in the path, and setup some default variables.
        """

        try:
            super().__init__(
                name="spack",
                command="spack",
                shell=shell,
                dry_run=dry_run,
                env=env,
            )

            self.spack = self.command
            self.installer = self.spack.copy()
            self.installer.add_default_prefix(
                ramble.config.get(f"{self.install_config_name}:prefix")
            )
            self.installer.add_default_arg("install")

            self.concretizer = self.spack.copy()
            self.concretizer.add_default_prefix(
                ramble.config.get(f"{self.concretize_config_name}:prefix")
            )
            self.concretizer.add_default_arg("concretize")

            # Add default arguments to spack command.
            # This allows us to inject custom config scope dirs
            # primarily for unit testing.
            global_args = ramble.config.get(f"{self.global_config_name}:flags")
            if global_args is not None:
                for arg in shlex.split(global_args):
                    self.spack.add_default_arg(arg)

            self.spack_dir = os.path.dirname(
                os.path.dirname(self.spack.exe[0])
            )
        except RunnerError:
            self.shell = shell
            self.spack = None
            self.installer = None
            self.concretizer = None
            self.spack_dir = os.path.join("missing", "path")

        if self.shell == "bash":
            script = "setup-env.sh"
        elif self.shell == "csh":
            script = "setup-env.csh"
        elif self.shell == "fish":
            script = "setup-env.fish"
        else:
            script = "setup-env.sh"
        self.source_script = os.path.join(
            self.spack_dir, "share", "spack", script
        )

        self.bs_python = CommandRunner(
            "python", command=sys.executable, dry_run=dry_run, env=env
        )
        self.concretized = False
        self.hash = None
        self.env_path = None
        self.active = False
        self.compilers = []
        self.includes = []
        self.dry_run = dry_run
        self.compiler_config_dir = None
        self.configs = []
        self.configs_applied = False
        self.env_contents = []

    def get_spack_python(self):
        if self.dry_run:
            return self.bs_python
        return which(
            "python",
            path=os.path.join(self.env_path, "ramble", "bin"),
        )

    def get_version(self):
        """Get spack's version"""
        import importlib.util

        from ramble.util.version import get_git_hash

        spack_version = None
        if self.spack:
            version_spec = importlib.util.spec_from_file_location(
                "spack_version",
                os.path.join(
                    self.spack_dir, "lib", "spack", "spack", "__init__.py"
                ),
            )
            version_mod = importlib.util.module_from_spec(version_spec)
            version_spec.loader.exec_module(version_mod)

            spack_version = version_mod.spack_version
            spack_hash = get_git_hash(path=self.spack_dir)

            if spack_hash:
                spack_version += f" ({spack_hash})"

        return spack_version

    def set_compiler_config_dir(self, path=None):
        """
        Set the config path to use when installing compilers
        """
        self.compiler_config_dir = path

    def set_env(self, env_path, require_exists=True):
        if require_exists:
            if not os.path.isdir(env_path) or not os.path.exists(
                os.path.join(env_path, "spack.yaml")
            ):
                logger.die(f"Path {env_path} is not a spack environment")

        self.env_path = env_path

    def generate_source_command(self, shell="bash"):
        """
        Generate a string to source spack into an environment
        """

        commands = [". %s" % self.source_script]

        return commands

    def generate_activate_command(self, shell="bash"):
        """
        Generate a string to activate a spack environment
        """

        commands = []
        if self.active:
            commands.append("spack env activate %s" % self.env_path)

        return commands

    def generate_deactivate_command(self, shell="bash"):
        """
        Generate a string to deactivate a spack environment
        """

        commands = []

        if self.active:
            commands.append("spack env deactivate")

        return commands

    def configure_env(self, path):
        """
        Configured the spack environment path for subsequent spack commands
        """

        # Ensure subsequent commands use the created env now.
        self.env_path = path

    def add_config(self, config):
        """
        Add a config option to this spack environment.
        """
        self.configs.append(config)

    def create_env(self, path, output=None, error=None):
        """
        Ensure a spack environment is created, and set the path to it within
        this runner.
        """
        if os.path.exists(path) and not os.path.isdir(path):
            raise RunnerError("Unable to create environment %s" % path)

        if not os.path.exists(path):
            fs.mkdirp(path)

        # Create a spack env
        if not os.path.exists(os.path.join(path, "spack.yaml")):
            env_create_flags = ramble.config.get(
                f"{self.env_create_config_name}:flags"
            )
            env_create_args = self.env_create_args.copy()
            if env_create_flags:
                for flag in shlex.split(env_create_flags):
                    env_create_args.append(flag)
            with fs.working_dir(path):
                self._run_command(self.spack, env_create_args)

        # Ensure subsequent commands use the created env now.
        self.env_path = path

    def load_compiler(self, spec):
        """
        Add commands to load a package to the executable
        """
        if self.shell == "bash":
            regex = re.compile(
                r"\A.*export (?P<var>[\S^=]+)=(?P<val>[\S]+);\Z"
            )
            shell_flag = "--sh"
        elif self.shell == "csh":
            regex = re.compile(
                r"\A.*setenv (?P<var>[\S^=]+) (?P<val>[\S]+);\Z"
            )
            shell_flag = "--csh"
        elif self.shell == "fish":
            regex = re.compile(
                r"\A.*set -gx (?P<var>[\S^=]+) (?P<val>[\S]+);\Z"
            )
            shell_flag = "--fish"
        else:
            raise RunnerError("Shell %s not supported" % self.shell)

        self._load_compiler_shell(spec, shell_flag, regex)

    def _load_compiler_shell(self, spec, shell_flag, regex):
        args = ["load", "--first", shell_flag, spec]

        load_cmds = self.execute(self.spack, args, return_output=True)

        if load_cmds is not None:
            for cmd in load_cmds.split("\n"):
                env_var = regex.match(cmd)
                if env_var:
                    self.spack.add_default_env(
                        env_var.group("var"), env_var.group("val")
                    )
                    self.installer.add_default_env(
                        env_var.group("var"), env_var.group("val")
                    )
                    self.concretizer.add_default_env(
                        env_var.group("var"), env_var.group("val")
                    )

    def install_compiler(self, pkg_spec, compiler_spec):
        """
        Ensure a compiler is installed, before using it to install packages
        within an environment.

        This command always executes outside of an environment.

        If it is executed within an environment, then it adds the compiler to
        the list of environment specs. This can cause conflicts if an
        incompatible package is explicitly added to the environment later.

        Also, if it is added to an environment, sometimes it will cause a
        compiler to be installed multiple times with different base compilers.
        """
        active_env = None
        if self.active:
            active_env = self.spack.default_env[self.env_key]
            if self.env_key in self.spack.default_env:
                del self.spack.default_env[self.env_key]
                del self.installer.default_env[self.env_key]
                del self.concretizer.default_env[self.env_key]

        comp_info_args = []
        if self.compiler_config_dir:
            comp_info_args.extend(["-C", self.env_path])
        comp_info_args.extend(["compiler", "info", compiler_spec])

        compiler_find_flags = ramble.config.get(
            f"{self.compiler_find_config_name}:flags"
        )
        compiler_find_args = self.compiler_find_args.copy()
        if compiler_find_flags:
            for flag in shlex.split(compiler_find_flags):
                compiler_find_args.append(flag)

        cache_key = (compiler_spec, self.compiler_config_dir, self.env_path)
        if cache_key in self._compiler_cache:
            has_compiler = self._compiler_cache[cache_key]
        else:
            if not self.dry_run:
                self._run_command(self.spack, compiler_find_args)

            try:
                self._cmd_start(self.spack, comp_info_args)
                self.spack(
                    *comp_info_args, output=os.devnull, error=os.devnull
                )
                self._cmd_end(self.spack, comp_info_args)
                has_compiler = True
            except ProcessError:
                has_compiler = False
            self._compiler_cache[cache_key] = has_compiler

        if has_compiler:
            logger.msg(f"{compiler_spec} is already an available compiler")
            return

        args = []

        install_flags = ramble.config.get(f"{self.install_config_name}:flags")
        if install_flags is not None:
            args.extend(shlex.split(install_flags))

        args.append(pkg_spec)

        self.execute(self.installer, args)

        self.load_compiler(pkg_spec)

        self.execute(self.spack, compiler_find_args)

        self._compiler_cache[cache_key] = True

        if not self.dry_run:
            self.compilers.append(pkg_spec)

            if self.active:
                self.spack.add_default_env(self.env_key, active_env)
                self.installer.add_default_env(self.env_key, active_env)
                self.concretizer.add_default_env(self.env_key, active_env)

    def activate(self):
        """
        Ensure the spack environment is active in subsequent commands.
        """
        if not self.env_path:
            raise NoPathRunnerError(
                "Environment runner has no path configured"
            )

        if self.spack:
            self.spack.add_default_env(self.env_key, self.env_path)
            self.installer.add_default_env(self.env_key, self.env_path)
            self.concretizer.add_default_env(self.env_key, self.env_path)

        self.active = True

    def deactivate(self):
        """
        Ensure the spack environment is not active in subsequent commands.
        """
        if not self.env_path:
            raise NoPathRunnerError(
                "Environment runner has no path configured"
            )

        if (
            self.spack
            and self.active
            and self.env_key in self.spack.default_env
        ):
            del self.spack.default_env[self.env_key]
            del self.installer.default_env[self.env_key]
            del self.concretizer.default_env[self.env_key]
        self.active = False

    def _check_active(self):
        if not self.env_path:
            raise NoPathRunnerError(
                "Environment runner has no path configured"
            )

        if not self.active:
            raise NoActiveEnvironmentError(
                "Runner has no active " + "environment to work with."
            )

    def add_spec(self, spec):
        """
        Add a spec to the spack environment.

        This command requires an active spack environment.
        """
        self._check_active()

        if spec not in self.env_contents:
            self.env_contents.append(spec)

    def added_packages(self):
        """
        Return a list of base package names that are added to an environment
        """
        self._check_active()

        pkg_names = []

        for pkg in self.env_contents:
            match = package_name_regex.match(pkg)
            if match:
                pkg_names.append(match.group("package_name"))

        return pkg_names

    def add_include_file(self, include_file):
        """
        Add an include file to this spack environment.

        This file needs to be a config section supported by spack, otherwise
        spack will error. So, we validate against a list of supported sections.
        """

        file_name = os.path.basename(include_file)
        if file_name in self._allowed_config_files:
            self.includes.append(include_file)

    def apply_configs(self, stage_path=None):
        """
        Add all defined configs to the environment
        """

        if not self.configs:
            return

        if not stage_path:
            self._check_active()

        env_path = stage_path if stage_path else self.env_path

        config_args = ["-D", env_path, "config", "add"]

        for config in self.configs:
            args = config_args.copy()
            args.append(config)

            self._run_command(self.spack, args)

    def add_config_file(self, config_path, stage_path=None):

        if not stage_path:
            self._check_active()

        env_path = self.env_path if not stage_path else stage_path

        args = ["-D", env_path, "config", "add", "-f", config_path]

        output = self._run_command(
            self.spack, args, allow_failure=True, return_output=True
        )

        return output

    def copy_from_external_env(self, env_name_or_path, stage_path=None):
        """
        Copy an external spack environment file into the generated environment.

        env_name_or_path can be either:
         - Name of a named spack environment
         - Path to an external spack environment

         Sets self.concretized if a spack.lock file is found in the env

         Args:
         - env_name_or_path: Name or path to existing spack environment
        """

        if not stage_path:
            self._check_active()
        env_path = self.env_path if not stage_path else stage_path

        named_location_args = ["location", "-e", env_name_or_path]

        # If the path doesn't exist, check if it's a named environment
        path = env_name_or_path
        if not os.path.exists(path):
            try:
                path = self._run_command(
                    self.spack, named_location_args, return_output=True
                )
            # If a named environment fails, copy directly from the path
            except ProcessError:
                raise InvalidExternalEnvironment(
                    f"{path} is not a spack environment."
                ) from None

        found_lock = False

        lock_file = os.path.join(path, "spack.lock")
        if os.path.exists(lock_file):
            found_lock = True
            shutil.copyfile(lock_file, os.path.join(env_path, "spack.lock"))

        conf_file = os.path.join(path, "spack.yaml")
        if not os.path.exists(conf_file):
            raise InvalidExternalEnvironment(
                f"{path} is not a spack environment."
            )

        shutil.copyfile(conf_file, os.path.join(self.env_path, "spack.yaml"))

        self.concretized = found_lock

    def _env_file_dict(self):
        """Construct a dictionary with the env file contents in it"""
        env_file = syaml.syaml_dict()
        env_file[spack_namespace] = syaml.syaml_dict()
        env_file[spack_namespace]["concretizer"] = syaml.syaml_dict()
        env_file[spack_namespace]["concretizer"]["unify"] = True

        link_type = ramble.config.get("config:spack:env_view:link_type")
        env_file[spack_namespace]["view"] = syaml.syaml_dict()
        env_file[spack_namespace]["view"]["default"] = syaml.syaml_dict()
        env_file[spack_namespace]["view"]["default"]["root"] = os.path.join(
            self.env_path, "ramble"
        )
        env_file[spack_namespace]["view"]["default"]["link_type"] = link_type

        env_file[spack_namespace]["specs"] = syaml.syaml_list()
        # Ensure the specs content are consistently sorted.
        # Otherwise the hash checking may artificially miss due to ordering.
        env_file[spack_namespace]["specs"].extend(sorted(self.env_contents))

        env_file[spack_namespace]["include"] = self.includes

        return env_file

    def create_stage_env(self):
        """Create a staging environment

        This method creates a temporary environment, where we can configure it
        properly before deciding if it has changed relative to an existing
        environment.
        """
        self._check_active()

        env_file = self._env_file_dict()

        # Generate a temp environment, so we can diff the environments
        tmpdir = tempfile.mkdtemp()
        tmp_path = str(tmpdir)
        self.create_env(tmp_path)
        tmp_env_file = os.path.join(tmp_path, "spack.yaml")

        with open(tmp_env_file, "w+", encoding="utf-8") as f:
            syaml.dump_config(env_file, default_flow_style=False, stream=f)

        return tmp_path

    def migrate_stage_env(self, stage_env_path: str, ws_env_path: str):
        """Determine if a stage env should be kept by checking it against an existing env.
        If it is kept, replace the existing env with it.

        Args:
            stage_env_path (str): Path for the environment stage
            ws_env_path (str): Path for environment in workspace

        Returns:
            (bool): Whether the env was migrated or not
        """
        migrate = False

        if not ws_env_path or not stage_env_path:
            return False

        stage_files = pathlib.Path(stage_env_path).glob("*.yaml")
        self.env_path = ws_env_path
        for file in stage_files:
            env_file = pathlib.Path(
                str(file).replace(str(stage_env_path), str(self.env_path))
            )
            if os.path.isfile(env_file):
                new_hash = ramble.util.hashing.hash_file(file)
                old_hash = ramble.util.hashing.hash_file(env_file)
                if new_hash != old_hash:
                    migrate = True
            else:
                migrate = True

            if migrate:
                break

        if migrate:
            logger.debug(
                f"Content for environment has changed. Regenerating {self.env_path}"
            )
            self.deactivate()
            self.create_env(path=ws_env_path)
            self.activate()
            shutil.rmtree(self.env_path, ignore_errors=True)
            shutil.copytree(str(stage_env_path), str(self.env_path))

            spack_hash = self.inventory_hash()

            with open(
                os.path.join(self.env_path, "ramble.hash"),
                "w+",
                encoding="utf-8",
            ) as f:
                f.write(spack_hash)
        else:
            spack_lock_file = os.path.join(self.env_path, "spack.lock")

            if os.path.isfile(spack_lock_file):
                self.concretized = True

            logger.debug(
                f"Content for environment {self.env_path} has not changed. "
                "Skipping regeneration"
            )

        return migrate

    def concretize(self):
        """
        Concretize a spack environment.

        This command requires an active spack environment.
        """
        self._check_active()

        if self.concretized:
            logger.msg(
                f"Environment {self.env_path} is already concretized. Skipping concretize..."
            )
            return

        concretize_flags = ramble.config.get(
            f"{self.concretize_config_name}:flags"
        )

        args = []
        if concretize_flags is not None:
            args.extend(shlex.split(concretize_flags))

        self.execute(self.concretizer, args)

        self.concretized = True

    def inventory_hash(self):
        """
        Create a hash of the spack.lock file for ramble inventory purposes

        This command requires an active spack environment.
        """
        self._check_active()

        env_data = syaml.load_config(
            syaml.dump_config(self._env_file_dict(), default_flow_style=False)
        )
        self.hash = ramble.util.hashing.hash_json(env_data)

        return self.hash

    def install(self):
        """
        Install spack packages that have been added to an environment.

        This command requires an active spack environment.
        """
        self._check_active()

        install_flags = ramble.config.get(f"{self.install_config_name}:flags")

        args = []

        if install_flags is not None:
            args.extend(shlex.split(install_flags))

        self.execute(self.installer, args)

    def get_package_path(self, package_spec):
        """Return the installation directory for a package"""
        name_regex = re.compile(r"(?P<name>[a-zA-Z0-9\-_]+).*")
        loc_args = ["location", "-i"]
        loc_args.extend(shlex.split(package_spec))

        name_args = ["find", "--format={name}"]
        name_args.extend(shlex.split(package_spec))

        name = self.execute(self.spack, name_args, return_output=True)
        location = self.execute(self.spack, loc_args, return_output=True)

        if name is None:
            name = shlex.split(package_spec)[0]
            name_match = name_regex.match(name)
            if name_match:
                name = name_match.group("name")
        else:
            # Remove newlines and whitespace from name
            name = name.replace("\n", "").strip()

        if location is None:
            location = os.path.join(
                "dry-run", "path", "to", shlex.split(package_spec)[0]
            )
        else:
            # Remove newlines and whitespace from location
            location = location.replace("\n", "").strip()

        return (name, location)

    def mirror_environment(self, mirror_path):
        """Create a spack mirror from the activated environment"""
        self._check_active()

        args = [
            "mirror",
            "create",
            "--all",  # All packages in the environment
            "-D",  # Include dependencies
            "-d",
            mirror_path,
        ]

        out_str = self.execute(self.spack, args, return_output=True)

        if out_str is None:
            return """
  %-4d already present
  %-4d added
  %-4d failed to fetch.""" % (
                0,
                0,
                0,
            )

        return out_str.strip()

    def get_env_hash_list(self):
        self._check_active()
        args = ["find", "--format", "/{hash}"]
        output = (
            self._run_command(self.spack, args, return_output=True)
            .strip()
            .replace("\n", " ")
        )
        return output

    def push_to_spack_cache(self, spack_cache_path, compiler_specs):
        """Push packages for a given env to the spack cache"""
        self._check_active()

        hash_list = self.get_env_hash_list()

        base_args = ["buildcache", "push"]
        user_flags = ramble.config.get(f"{self.buildcache_config_name}:flags")

        logger.debug(f"Running with user flags: {user_flags}")

        if user_flags is not None:
            base_args.extend(shlex.split(user_flags))

        base_args.extend([spack_cache_path])

        args = base_args.copy()
        args.extend([hash_list])

        self.execute(self.spack, args, return_output=True)

        # Attempt to push compilers too
        self.deactivate()  # need to not be in env to find the user compiler

        for compiler_spec in compiler_specs:
            logger.debug("Pushing " + compiler_spec)
            args = base_args.copy()
            args.append(compiler_spec)

            # We cannot push system/extern compilers, so this call must tolerate failures
            self.execute(
                self.spack, args, allow_failure=True, return_output=True
            )

    def validate_command(
        self,
        command="",
        validation_type="not_empty",
        package_manager="spack",
        regex=None,
        **kwargs,
    ):
        regex_validations = ["contains_regex", "does_not_contain_regex"]

        args = command.split()

        compiled_regex = None
        if validation_type in regex_validations and regex:
            compiled_regex = re.compile(regex)

        output = self.execute(self.spack, args, return_output=True)

        if output is not None:
            logger.debug(" Validation output:")
            logger.debug(output)
            if validation_type == "empty":
                if output != "":
                    self._raise_validation_error(command, validation_type)
            elif validation_type == "not_empty":
                if output == "":
                    self._raise_validation_error(command, validation_type)
            elif validation_type == "contains_regex":
                found = False
                for line in output.split("\n"):
                    if compiled_regex.match(line):
                        found = True
                if not found:
                    self._raise_validation_error(command, validation_type)
            elif validation_type == "does_not_contain_regex":
                for line in output.split("\n"):
                    if compiled_regex.match(line):
                        self._raise_validation_error(command, validation_type)

    def package_definitions(self):
        """For each package in this environment, yield the path to its application.py file"""
        package_def_name = "package.py"
        location_args = ["location", "-p"]

        self._check_active()

        for pkg in self.env_contents:
            args = location_args.copy()
            args.append(pkg)

            path = self.execute(self.spack, args, return_output=True).rstrip()

            if path is not None:
                yield pkg, os.path.join(path, package_def_name)

    def package_provenance(self):
        """Iterator over package information dictionaries

        Call spack to determine the package information in the current
        environment. Yield each valid package dictionary.

        Yields:
            (dict): Package information dictionary
        """
        find_args = [
            "find",
            '--format="{name},{version},{compiler.name},{compiler.version},{target},{variants}"',
            "-c",
        ]

        lock_file = os.path.join(self.env_path, "spack.lock")
        if os.path.exists(lock_file):
            all_info = self.execute(
                self.spack, find_args, return_output=True
            ).replace('"', "")

            if all_info:
                for info_line in all_info.split("\n"):
                    pkg_parts = info_line.split(" ")
                    if len(pkg_parts) == 1:
                        info = pkg_parts[0]
                    else:
                        # Remove status markers from first 3 if present
                        info = (
                            info_line[:3]
                            .replace("[+]", "")
                            .replace("[^]", "")
                            .replace(" - ", "")
                            .replace("[-]", "")
                            .replace("[e]", "")
                            + info_line[3:]
                        )

                    software_info = SpackSoftwareInfo()
                    software_info.parse_from_string(info)

                    if software_info.name:
                        yield software_info


class NoActiveEnvironmentError(RunnerError):
    """Raised when an environment command is executed without an active
    environment."""


class InvalidExternalEnvironment(RunnerError):
    """Raised when an invalid external spack environment is passed in"""
