# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import ast
import os
import re
import shutil
import sys
import urllib.parse

import llnl.util.filesystem as fs

from ramble.error import ApplicationError
from ramble.pkgmankit import *
from ramble.util.executable import PrefixedExecutable, which
from ramble.util.format import when_order
from ramble.util.hashing import hash_string
from ramble.util.logger import logger
from ramble.util.shell_utils import source_str

from spack.util.executable import Executable

# The collection of attributes pulled from Python sysconfig.get_paths()
# This is used to expose the two site_packages paths of a given Python
# installation.
_SYSCONFIG_PATH_ATTRIBUTES = ("purelib", "platlib")


class Pip(PackageManagerBase):
    """Pip package manager class definition"""

    name = "pip"

    _spec_prefix = "pip"

    package_manager_family("pip")

    archive_pattern(os.path.join("{env_path}", "requirements.txt"))
    archive_pattern(os.path.join("{env_path}", "requirements.lock"))

    for attr_name in _SYSCONFIG_PATH_ATTRIBUTES:
        package_manager_variable(
            f"pip_{attr_name}_path",
            default="",
            description=f"Path to {attr_name} site-packages directory for pip venv. Set during workspace setup.",
        )

    def __init__(self, file_path):
        super().__init__(file_path)

        self._runner = None

    @property
    def runner(self):
        if self._runner is None:
            self._runner = PipRunner()
        return self._runner

    name_regex = re.compile(r"\s*(?P<name>[\w-]+).*")

    def package_name_from_spec(self, spec):
        m = self.name_regex.match(spec)
        pkg_name = None
        if m:
            pkg_name = m.group("name")

        return pkg_name

    register_builtin(
        "pip_activate", required=True, depends_on=["builtin::env_vars"]
    )

    def pip_activate(self):
        self.runner.configure_env(self.app_inst.expander.env_path)
        return self.runner.generate_activate_command()

    register_builtin(
        "pip_deactivate",
        required=False,
        depends_on=["pip_activate"],
    )

    def pip_deactivate(self):
        return self.runner.generate_deactivate_command()

    register_phase("software_create_env", pipeline="setup")

    def _software_create_env(self, workspace, app_inst=None):
        """Create the virtual env for the experiment"""

        logger.msg("Creating venv + pip environment")

        env_path = app_inst.expander.env_path
        if not env_path:
            raise ApplicationError("Ramble env_path is set to None")

        cache_tupl = ("pip-env", env_path)
        if workspace.check_cache(cache_tupl):
            logger.debug(f"{cache_tupl} already in cache")
            return
        else:
            workspace.add_to_cache(cache_tupl)

        self.runner.set_dry_run(workspace.dry_run)
        self.runner.create_env(env_path)

        env_context = app_inst.expander.expand_var_name(self.keywords.env_name)
        require_env = self.environment_required
        software_envs = workspace.software_environments
        software_env = software_envs.render_environment(
            env_context, app_inst.expander, self, require=require_env
        )
        if software_env:
            if isinstance(software_env, ExternalEnvironment):
                self.runner.copy_from_external_env(software_env.external_env)
            else:
                for pkg_spec in software_envs.package_specs_for_environment(
                    software_env
                ):
                    self.runner.add_spec(pkg_spec)
                self.runner.generate_requirement_file()

    register_phase(
        "software_install", pipeline="setup", run_after=["software_create_env"]
    )

    def _software_install(self, workspace, app_inst=None):
        """Install packages using pip"""
        logger.msg("Installing packages")

        env_path = app_inst.expander.env_path
        if not env_path:
            raise ApplicationError("Ramble env_path is set to None")

        cache_tupl = ("pip-install", env_path)
        if workspace.check_cache(cache_tupl):
            logger.debug(f"{cache_tupl} already in cache")
            return
        else:
            workspace.add_to_cache(cache_tupl)

        env_context = app_inst.expander.expand_var_name(self.keywords.env_name)
        logger.debug(f" Required environment: {self.environment_required}")
        try:
            self.runner.set_dry_run(workspace.dry_run)
            self.runner.configure_env(env_path)
            self.runner.install()

            installed_pkgs = self.runner.installed_packages()
            for pkg, conf in app_inst.required_packages.items():
                if (
                    self.satisfy_when(conf["when"])
                    and pkg not in installed_pkgs
                ):
                    sorted_vars = sorted(
                        self.experiment_variants().as_set(for_output=True),
                        key=when_order,
                    )
                    logger.die(
                        f"Package {pkg} is not installed "
                        f"in environment {env_context}, but is "
                        f"required by the {app_inst.name} application "
                        "definition\n",
                        f"{sorted_vars}\n",
                        f"{conf['when']}",
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
                        and pkg not in installed_pkgs
                    ):
                        logger.die(
                            f"Package {pkg} is not installed "
                            f"in environment {env_context}, but is "
                            f"required by the {mod_inst.name} modifier "
                            "definition"
                        )
        except RunnerError as e:
            if self.environment_required:
                logger.die(e)

    register_phase(
        "define_package_paths",
        pipeline="setup",
        run_after=["software_install"],
        run_before=["make_experiments"],
    )

    def _define_package_paths(self, workspace, app_inst=None):
        """Define variables containing the path to pip packages"""

        logger.msg("Defining pip package path variables")

        env_path = app_inst.expander.env_path
        if not env_path:
            raise ApplicationError("Ramble env_path is set to None")

        self.runner.define_site_package_paths(app_inst)

        if self.environment_required:
            self.runner.set_dry_run(workspace.dry_run)
            self.runner.configure_env(env_path)
            env_files = [
                os.path.join(env_path, self.runner._requirement_file_name),
                os.path.join(env_path, self.runner._lock_file_name),
            ]
            cache = self.get_pkg_path_cache(workspace, env_path, env_files)
            prev_size = len(cache)
            self.runner.define_path_vars(app_inst, cache)
            if len(cache) != prev_size:
                self.write_pkg_path_cache(workspace, env_path, env_files)

    def get_spec_str(self, pkg, all_pkgs, compiler):
        """Return a spec string for the given pkg

        Args:
            pkg (RenderedPackage): Reference to a rendered package
            all_pkgs (dict): All related packages
            compiler (bool): True if this pkg is used as a compiler
        """
        return pkg.spec

    @PackageManagerBase.workspace_cache
    def get_version(self, workspace=None):
        return self.runner.get_version()

    def populate_inventory(
        self, workspace, force_compute=False, require_exist=False
    ):
        """Add software environment information to hash inventory"""

        env_path = self.app_inst.expander.env_path
        self.runner.set_dry_run(workspace.dry_run)
        self.runner.configure_env(env_path)

        self.app_inst.hash_inventory["software"].append(
            {
                "name": self.runner.env_path.replace(
                    workspace.root + os.path.sep, ""
                ),
                "package_manager": self.name,
                "digest": self.runner.inventory_hash(),
            }
        )

    register_phase("warn_mirror_support", pipeline="mirror")

    def _warn_mirror_support(self, workspace, app_inst=None):
        del workspace, app_inst  # unused arguments
        logger.warn(
            f"Mirroring software using {self.name} is not currently supported. "
            "If a software mirror is required, it needs to be set up outside of Ramble"
        )

    def get_package_list(self, workspace):
        """Augment the owning experiment's results with software stack information

        This is called by the `add_software_to_results` phase registered in the base
        package manager class.
        """
        env_path = self.app_inst.expander.env_path
        self.runner.set_dry_run(workspace.dry_run)
        self.runner.configure_env(env_path)

        return list(self.runner.package_provenance())

    def environment_load_commands(self):
        self.runner.configure_env(self.app_inst.expander.env_path)
        return self.runner.generate_activate_command()

    def environment_unload_commands(self):
        return self.runner.generate_deactivate_command()


package_name_regex = re.compile(
    r"\s*(?P<pkg_name>[A-Z0-9][A-Z0-9._-]*[A-Z0-9]|[A-Z0-9]).*", re.IGNORECASE
)


def _extract_pkg_name(pkg_spec):
    """Best-effort to extract pkg name from spec

    This is only used by the runner for dry-run cases.
    It only handles name-based specifier.
    """

    match = package_name_regex.match(pkg_spec)
    return match.group("pkg_name") if match else None


class PipSoftwareInfo(ramble.software_info.SoftwareInfo):
    # TODO: should this "parse" function have a unified interface?
    def parse_from_string(self, in_str):
        """Construct a package dictionary from a package string

        Args:
            in_str (str): String representing a package, as output from `pip freeze`

        Returns:
            (dict): Dictionary representing the package information
        """

        if not in_str:
            return

        parts = in_str.replace("\n", "").split("==")

        if len(parts) <= 1:
            return

        self.version = parts[1]

        if "[" in parts[0]:
            name_parts = parts[0].replace("]", "").split("[")
            self.name = name_parts[0].strip()
            self.variants = name_parts[1]
        else:
            self.name = parts[0].strip()
            self.variants = ""


class PipRunner(CommandRunner):
    """Runner for executing pip+venv commands."""

    _venv_name = ".venv"
    _requirement_file_name = "requirements.txt"
    _lock_file_name = "requirements.lock"

    install_config_name = "config:pip:install"

    def __init__(self, dry_run=False):
        super().__init__(name="pip", command=sys.executable, dry_run=dry_run)
        if self.command is None:
            self.bs_python = PrefixedExecutable(sys.executable)
        else:
            self.bs_python = self.command
        self.env_path = None
        self.configs = []
        self.specs = set()
        self.installed = False

    def configure_env(self, path):
        """Configure the venv path for subsequent commands"""
        self.env_path = path

    def create_env(self, env_path):
        """Ensure a venv environment is created"""
        if os.path.exists(env_path) and not os.path.isdir(env_path):
            raise RunnerError(f"Unable to create environment {env_path}")

        if not os.path.exists(env_path):
            fs.mkdirp(env_path)

        if not self.dry_run:
            if not os.path.exists(os.path.join(env_path, self._venv_name)):
                self.execute(
                    self.bs_python,
                    ["-m", "venv", os.path.join(env_path, self._venv_name)],
                )

        # Ensure subsequent commands use the created env now.
        self.env_path = env_path

    def reset_bs_python(self, exec=None, path=None):
        if isinstance(exec, Executable):
            self.bs_python = exec
        elif isinstance(path, str):
            self.bs_python = which("python", path=path) or PrefixedExecutable(
                sys.executable
            )
        else:
            self.bs_python = which("python") or PrefixedExecutable(
                sys.executable
            )

    def _get_venv_python(self):
        if self.dry_run:
            return self.bs_python.copy()
        return Executable(
            os.path.join(self.env_path, self._venv_name, "bin", "python")
        )

    def install(self):
        """Invoke pip install"""
        self._check_env_configured()
        if self.installed:
            logger.debug("Installation already done, skipping")
            return
        req_file = os.path.join(self.env_path, self._requirement_file_name)
        if not os.path.exists(req_file):
            raise RunnerError(f"{req_file} does not exist")
        installer = self._get_venv_python()
        installer.add_default_arg("-m")
        installer.add_default_arg("pip")
        installer_flags = ramble.config.get(
            f"{self.install_config_name}:flags"
        )
        install_args = ["install", "-r", req_file, *installer_flags]
        freeze_args = ["freeze", "-r", req_file]
        self.execute(installer, install_args)
        out = self.execute(installer, freeze_args, return_output=True)
        if out is not None:
            lock_file = os.path.join(self.env_path, self._lock_file_name)
            with open(lock_file, "w", encoding="utf-8") as f:
                f.write(out)
        self.installed = True

    def _get_activate_script_path(self):
        return os.path.join(self.env_path, self._venv_name, "bin", "activate")

    def _check_env_configured(self):
        """Check if virtual env is configured"""
        if not self.env_path:
            raise RunnerError("env_path is not configured")
        if self.dry_run:
            return
        script_path = self._get_activate_script_path()
        if not os.path.exists(script_path):
            raise RunnerError("virtual env is not configured")

    def generate_activate_command(self):
        """Generate a command to activate a virtual env"""
        return [f"{source_str(self.shell)} {self._get_activate_script_path()}"]

    def generate_deactivate_command(self):
        """Generate a command to deactivate a virtual env"""
        return ["deactivate"]

    def _generate_requirement_content(self):
        contents = os.linesep.join(sorted(self.specs))
        contents += os.linesep
        return contents

    def generate_requirement_file(self):
        """Generate a requirements.txt file"""
        self._check_env_configured()
        contents = self._generate_requirement_content()
        req_file = os.path.join(self.env_path, self._requirement_file_name)
        lock_file = os.path.join(self.env_path, self._lock_file_name)
        if os.path.exists(req_file) and os.path.exists(lock_file):
            existing_req_mtime = os.path.getmtime(req_file)
            existing_lock_mtime = os.path.getmtime(lock_file)
            if existing_lock_mtime >= existing_req_mtime:
                with open(req_file, encoding="utf-8") as f:
                    if f.read() == contents:
                        self.installed = True
                        logger.debug("requirement file already up-to-date")
                        return
        with open(req_file, "w", encoding="utf-8") as f:
            f.write(contents)

    def copy_from_external_env(self, external_env_path):
        """Copy requirements from an external env

        This will attempt `pip freeze` from the given external env_path
        and writes the output requirements.txt to the current env_path.
        """
        self._check_env_configured()
        dest = os.path.join(self.env_path, self._requirement_file_name)
        # When a file is given, assume it's a requirements.txt.
        if os.path.isfile(external_env_path):
            logger.msg(
                f"Treat {external_env_path} as an externally defined requirements.txt file"
            )
            shutil.copyfile(external_env_path, dest)
            return
        parsed_path = urllib.parse.urlparse(external_env_path)
        if parsed_path.scheme:
            fetcher = ramble.fetch_strategy.URLFetchStrategy(
                url=external_env_path
            )
            with ramble.stage.InputStage(
                fetcher,
                path=os.path.dirname(dest),
                name=os.path.basename(dest),
            ) as stage:
                stage.fetch()
            return
        # Assume the given external_env_path already points to a venv path,
        # If not, also attempt path/.venv/.
        maybe_paths = ["", self._venv_name]
        ext_python_path = None
        for p in maybe_paths:
            exe_path = os.path.join(external_env_path, p, "bin", "python")
            if os.path.exists(exe_path):
                ext_python_path = exe_path
                break
        if not ext_python_path:
            raise RunnerError(
                f"The given external env path {external_env_path} does not point to a valid venv "
                "or requirements.txt file"
            )
        ext_python = Executable(ext_python_path)
        out = self.execute(
            ext_python, ["-m", "pip", "freeze"], return_output=True
        )
        if out is not None:
            with open(dest, "w", encoding="utf-8") as f:
                f.write(out)

    def define_path_vars(self, app_inst, cache):
        """Define path variables"""
        self._check_env_configured()
        if self.dry_run:
            return
        lock_file = os.path.join(self.env_path, self._lock_file_name)
        if not lock_file:
            raise RunnerError(f"Lock file {lock_file} is missing")
        pkgs = []
        with open(lock_file, encoding="utf-8") as f:
            for line in f:
                # pip freeze generates such a comment, which serves as a divider
                # for packages that are added as deps of the ones defined directly.
                # This is a crude way to avoid defining path vars for
                # packages that are not defined in ramble config.
                if "added by pip freeze" in line:
                    break
                if "==" in line:
                    pkgs.append(line.split("==")[0].strip())
        unresolved_pkgs = []
        for pkg in pkgs:
            if pkg in cache:
                pkg_path = cache.get(pkg)
                if f"{pkg}_path" not in app_inst.variables:
                    # Intentionally not define the deprecated `pkg` variable
                    app_inst.define_variable(f"{pkg}_path", pkg_path)
                else:
                    logger.msg(
                        f"Variable {pkg}_path defined. "
                        + "Skipping extraction from pip"
                    )
            else:
                unresolved_pkgs.append(pkg)
        if not unresolved_pkgs:
            return

        logger.debug("Resolving package paths using pip")
        exe = self._get_venv_python()
        exe.add_default_arg("-m")
        exe.add_default_arg("pip")
        exe.add_default_arg("show")
        for pkg in unresolved_pkgs:
            pkg_info_raw = self.execute(exe, [pkg], return_output=True)
            pkg_path = None
            for line in pkg_info_raw.split(os.linesep):
                info = line.split(":")
                if info[0].strip() == "Location":
                    pkg_path = info[1].strip()
            if not pkg_path:
                raise RunnerError(
                    f"Failed to find installed path for package {pkg}"
                )
            cache[pkg] = pkg_path
            if f"{pkg}_path" not in app_inst.variables:
                app_inst.define_variable(f"{pkg}_path", pkg_path)
            else:
                logger.msg(
                    f"Variable {pkg}_path defined. "
                    + "Skipping extraction from pip"
                )

    def define_site_package_paths(self, app_inst):
        """Define site_package paths into variables"""
        self._check_env_configured()
        logger.debug("Resolving site package paths")
        exe = self._get_venv_python()
        paths_info_raw = exe(
            "-c", "import sysconfig; print(sysconfig.get_paths())", output=str
        )
        paths_info = ast.literal_eval(paths_info_raw)
        for attr_name in _SYSCONFIG_PATH_ATTRIBUTES:
            attr_value = paths_info.get(attr_name)
            if attr_value is not None:
                app_inst.define_variable(f"pip_{attr_name}_path", attr_value)

    def add_spec(self, spec):
        """Add a package spec to the pip environment"""
        self._check_env_configured()
        self.specs.add(spec)

    def get_version(self):
        if self.dry_run:
            return "unknown"
        # The bootstrap python should have the same version as the venv one.
        # Use the bootstrap one here as get_version may be called (for instance for compute hash)
        # before the venv environment is constructed.
        out = self.execute(
            self.bs_python, ["-m", "pip", "--version"], return_output=True
        )
        match = re.search(r"pip (?P<version>[\d.]+) from", out).group(
            "version"
        )
        return match

    def inventory_hash(self):
        """Create a hash for ramble inventory purposes"""
        return hash_string(self._generate_requirement_content())

    def installed_packages(self):
        """Return a set of installed packages based on the lock file"""
        self._check_env_configured()
        pkgs = set()
        if self.dry_run:
            for spec in self.specs:
                pkg_name = _extract_pkg_name(spec)
                if pkg_name:
                    pkgs.add(pkg_name)
        else:
            with open(
                os.path.join(self.env_path, self._lock_file_name),
                encoding="utf-8",
            ) as f:
                reqs = f
                for req in reqs:
                    if "==" in req:
                        pkgs.add(req.split("==")[0].strip())
        return pkgs

    def package_provenance(self):
        """Iterator over package information dictionaries

        Examine the package definitions in the environment lock file. Yield
        each valid package dictionary created from lines in the lock file.

        Yields:
            (dict): Package information dictionary
        """

        lock_file = os.path.join(self.env_path, self._lock_file_name)

        if os.path.exists(lock_file):
            with open(lock_file, encoding="utf-8") as f:
                for line in f:
                    software_info = PipSoftwareInfo()
                    software_info.parse_from_string(line.replace("\n", ""))

                    if software_info.name:
                        yield software_info
