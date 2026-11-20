# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import ramble.config
from ramble.appkit import *

import spack.util.executable


class SpackStack(ExecutableApplication):
    """Application definition for creating a spack software stack

    This application definition is used solely to create spack software stacks.

    As such, compiler installation and concretization are handled by
    `ramble workspace setup` but environment installation is handled
    as part of the experiment.

    The `spack install` phase happens with the '{mpi_command}' prefix to
    accelerate package installation.

    The experiments are considered successful if the installation completed.

    This application should be used with the `spack-lightweight` package manager.
    """

    name = "spack-stack"

    maintainers("douglasjacobsen")

    tags("spack", "software-stack", "build-tool")

    executable(
        "configure",
        template=[
            'spack config add "config:install_tree:padded_length:{padded_length}"'
        ],
        use_mpi=False,
    )

    executable("install", "spack install {install_flags}", use_mpi=True)
    workload(
        "create",
        executables=[
            "builtin::remove_env_files",
            "builtin::find_externals",
            "configure",
            "install",
            "builtin::remove_packages",
        ],
    )

    executable("uninstall", "spack uninstall {uninstall_flags}", use_mpi=True)

    workload("remove", executables=["uninstall"])

    workload(
        "remove",
        executables=[
            "uninstall",
        ],
    )

    workload_variable(
        "install_flags",
        default="--fail-fast",
        description="Flags to use for `spack install`",
        workloads=["create"],
    )

    workload_variable(
        "external_packages",
        default=[],
        description="List of packages to `spack external find` and mark not buildable",
        workloads=["create"],
    )

    workload_variable(
        "removed_packages",
        default=[],
        description="List of packages to remove from the environment after installation is complete",
        workloads=["create"],
    )

    workload_variable(
        "padded_length",
        default="512",
        description="Length to pad install prefixes with",
        workloads=["create"],
    )

    workload_variable(
        "uninstall_flags",
        default="--all -y",
        description="Flags to use for `spack uninstall`",
        workloads=["remove"],
    )

    success_criteria(
        "view-updated", mode="string", match=r".*?==> Updating view at"
    )

    pkg_regex = r"\s*==\> (?P<name>.*?) Successfully installed (?P<spec>.*)"

    figure_of_merit(
        "Previously installed packages",
        fom_regex=r"\s*==\> (?P<quant>.*?) of the packages are already installed",
        group_name="quant",
        units="",
    )

    figure_of_merit(
        "{pkg_name} installed",
        fom_regex=r"\s*==\> (?P<pkg_name>.*?): Successfully installed (?P<spec>.*)",
        group_name="spec",
        units="",
    )

    figure_of_merit_context(
        "Package", regex=pkg_regex, output_format="({name}, {spec})"
    )

    fom_parts = [
        "Autoreconf",
        "Bootstrap",
        "Build",
        "Cmake",
        "Configure",
        "Edit",
        "Install",
        "Post-install",
        "Stage",
        "Total",
    ]
    for fom_part in fom_parts:
        full_regex = r".*?\s*" + fom_part + r":\s+(?P<fom>[0-9\.]+)s"
        figure_of_merit(
            fom_part,
            fom_regex=full_regex,
            group_name="fom",
            units="s",
            contexts=["Package"],
        )

    register_builtin("remove_env_files", required=False)

    def remove_env_files(self):
        cmds = ["rm -f {env_path}/spack.lock", "rm -rf {env_path}/.spack-env"]
        return cmds

    register_builtin("find_externals", required=False)

    def find_externals(self):
        """Inject commands to find external non buildable packages

        This allows spack find external system packages before building,
        to ensure system packages are used for some dependencies.
        """
        cmds = []

        # Package finding is only supported in bash or sh
        if ramble.config.get("config:shell") in ["sh", "bash"]:
            # Do not expand the `external_packages` variable, so it will not be
            # used to render experiments.
            external_packages = self.expander.expand_var_name(
                "external_packages", merge_used_stage=False, typed=True
            )
            self.expander.flush_used_variable_stage()
            cmds.extend(
                f"spack external find --not-buildable {pkg}"
                for pkg in external_packages
            )
        return cmds

    register_builtin("remove_packages", required=False)

    def remove_packages(self):
        """Inject command to uninstall selected packages.

        This allows spack to omit some packages from a buildcache by
        uninstalling them after the whole environment is installed.
        """
        cmds = []

        # Package removal is only supported in bash or sh
        if ramble.config.get("config:shell") in ["sh", "bash"]:
            # Do not expand the `removed_packages` variable, so it will not be
            # used to render experiments.
            packages_to_remove = self.expander.expand_var_name(
                "removed_packages", merge_used_stage=False, typed=True
            )
            self.expander.flush_used_variable_stage()
            for pkg in packages_to_remove:
                cmds.append(
                    f'grep "{pkg}" ' + "{env_path}/spack.yaml &> /dev/null"
                )
                cmds.append("if [ $? -eq 0 ]; then")
                cmds.append(f"  spack uninstall {pkg}")
                cmds.append(f"  spack remove {pkg}")
                cmds.append("fi")
        return cmds

    def evaluate_success(self):
        import ramble.util.ramble_yaml as ryaml

        if not self.expander.satisfies("package_manager_family=spack"):
            return True

        spack_file = self.expander.expand_var("{env_path}/spack.yaml")
        spec_list = []

        # Only evaluate if this is a spack package manager
        if (
            self.package_manager is None
            or "spack" not in self.package_manager.name
        ):
            return True

        if not os.path.isfile(spack_file):
            return False

        with open(spack_file, encoding="utf-8") as f:
            spack_data = ryaml.load_config(f)

        logger.debug(f"Spack data: {spack_data}")

        spec_list.extend(spack_data["spack"]["specs"])

        self.package_manager.runner.set_env(self.expander.env_path)
        self.package_manager.runner.activate()

        # Spack find errors if a spec is provided that is not installed.
        for spec in spec_list:
            try:
                self.package_manager.runner.spack("find", spec, output=str)
            except spack.util.executable.ProcessError:
                return False
        return True
