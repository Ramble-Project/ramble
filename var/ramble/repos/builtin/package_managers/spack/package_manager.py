# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import glob
import os

from ramble.pkg_man.builtin.spack_lightweight import SpackLightweight
from ramble.pkgmankit import *
from ramble.util.command_runner import RunnerError


class Spack(SpackLightweight):
    """Full Spack package manager class definition

    This inherits from the spack-lightweight package manager, and extends it by
    adding the software_install and define_package_paths phases.
    """

    name = "spack"

    archive_pattern("{env_path}/spack.yaml")
    archive_pattern("{env_path}/spack.lock")

    register_phase(
        "software_install",
        pipeline="setup",
        run_after=["software_configure"],
        run_before=["evaluate_requirements"],
    )

    def _software_install(self, workspace, app_inst=None):
        """Install application's software using spack"""

        # See if we cached this already, and if so return
        env_path = app_inst.expander.env_path

        cache_tupl = ("spack-install", env_path)
        if workspace.check_cache(cache_tupl):
            logger.debug(f"{cache_tupl} already in cache.")
            return
        else:
            workspace.add_to_cache(cache_tupl)

        try:
            self.runner.set_dry_run(workspace.dry_run)
            self.runner.set_env(env_path)

            logger.msg("Installing software")

            self.runner.activate()
            self.runner.install()
        except RunnerError as e:
            logger.die(e)

    register_phase(
        "define_package_paths",
        pipeline="setup",
        run_after=["software_install", "evaluate_requirements"],
        run_before=["make_experiments"],
    )

    def _define_package_paths(self, workspace, app_inst=None):
        """Define variables containing the path to all spack packages

        For every spack package defined within an application context, define
        a variable that refers to that packages installation location.

        As an example:
        <ramble.yaml>
        spack:
          applications:
            wrfv4:
              wrf:
                base: wrf
                version: 4.2.2

        Would define a variable `wrf` that contains the installation path of
        wrf@4.2.2
        """

        logger.msg("Defining Spack variables")

        env_path = app_inst.expander.env_path
        env_files = (
            glob.glob(os.path.join(env_path, "*.yaml"))
            + [os.path.join(env_path, "spack.lock")]
            if env_path
            else []
        )
        cache = self.get_pkg_path_cache(workspace, env_path, env_files)
        app_context = app_inst.expander.expand_var_name(self.keywords.env_name)
        require_env = self.environment_required
        software_environments = workspace.software_environments
        software_environment = software_environments.render_environment(
            app_context, app_inst.expander, self, require=require_env
        )
        if software_environment is not None:
            # Try to resolve using local cache first
            unresolved_specs = []
            for (
                pkg_spec
            ) in software_environments.package_specs_for_environment(
                software_environment
            ):
                if pkg_spec in cache:
                    spack_pkg_name, pkg_path = cache.get(pkg_spec)
                    if spack_pkg_name not in app_inst.variables:
                        app_inst.define_variable(spack_pkg_name, pkg_path)
                        app_inst.define_variable(
                            f"{spack_pkg_name}_path", pkg_path
                        )
                    else:
                        logger.msg(
                            f"Variable {spack_pkg_name} defined. "
                            + "Skipping extraction from spack"
                        )
                else:
                    unresolved_specs.append(pkg_spec)
            if not unresolved_specs:
                return

            try:
                logger.debug("Resolving package paths using Spack")
                self.runner.set_dry_run(workspace.dry_run)
                self.runner.set_env(app_inst.expander.env_path)

                self.runner.activate()

                for pkg_spec in unresolved_specs:
                    spack_pkg_name, pkg_path = self.runner.get_package_path(
                        pkg_spec
                    )
                    if f"{spack_pkg_name}_path" not in app_inst.variables:
                        app_inst.define_variable(spack_pkg_name, pkg_path)
                        app_inst.define_variable(
                            f"{spack_pkg_name}_path", pkg_path
                        )
                        cache[pkg_spec] = (spack_pkg_name, pkg_path)
                    else:
                        logger.msg(
                            f"Variable {spack_pkg_name} defined. "
                            + "Skipping extraction from spack"
                        )
                        logger.msg(
                            f"Variable {spack_pkg_name}_path defined. "
                            + "Skipping extraction from spack"
                        )
                self.write_pkg_path_cache(workspace, env_path, env_files)

            except RunnerError as e:
                logger.die(e)

    register_builtin(
        "spack_activate",
        required=True,
        depends_on=["package_manager_builtin::spack::spack_source"],
    )
    register_builtin(
        "spack_deactivate",
        required=False,
        depends_on=["package_manager_builtin::spack::spack_source"],
    )

    register_phase(
        "software_configure", pipeline="mirror", run_before=["mirror_software"]
    )

    register_phase(
        "software_create_env",
        pipeline="mirror",
        run_before=["software_configure"],
    )
