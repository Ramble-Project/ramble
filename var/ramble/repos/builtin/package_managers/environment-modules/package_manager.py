# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import re
from typing import List

import llnl.util.filesystem as fs

import ramble.config
import ramble.software_info
import ramble.util.hashing
from ramble.pkgmankit import *
from ramble.util.shell_utils import source_str


class EnvironmentModules(PackageManagerBase):
    """Definition for using environment-modules as a package manager

    This definition allows experiments to use environment-modules to manage the
    software used in an experiment. It assumes the `module` command will be in
    the path of the experiment at execution time.
    """

    name = "environment-modules"

    maintainers("douglasjacobsen")

    _spec_prefix = "environment_modules"

    _list_file = ".environment_modules_list"

    package_manager_family("environment-modules")

    register_phase(
        "write_module_commands",
        pipeline="setup",
        run_before=["make_experiments"],
    )

    name_regex = re.compile(r"\s*(?P<name>[\w-]+).*")

    def package_name_from_spec(self, spec):
        m = self.name_regex.match(spec)
        pkg_name = None
        if m:
            pkg_name = m.group("name")

        return pkg_name

    def _generate_loads_content(self, workspace):
        if not hasattr(self, "_load_string"):
            app_context = self.app_inst.expander.expand_var_name(
                self.keywords.env_name
            )

            require_env = self.environment_required

            software_envs = workspace.software_environments
            software_env = software_envs.render_environment(
                app_context, self.app_inst.expander, self, require=require_env
            )

            load_content = []

            if software_env is not None:
                load_content.extend(
                    f"module load {spec}"
                    for spec in software_envs.package_specs_for_environment(
                        software_env
                    )
                )

            self._load_string = "\n".join(load_content)

        return self._load_string

    def populate_inventory(self, workspace, force_compute=False):
        env_path = self.app_inst.expander.env_path
        env_hash = ramble.util.hashing.hash_string(
            self._generate_loads_content(workspace)
        )

        self.app_inst.hash_inventory["software"].append(
            {
                "name": env_path.replace(workspace.root + os.path.sep, ""),
                "package_manager": self.name,
                "digest": env_hash,
            }
        )

    def _write_module_commands(self, workspace, app_inst=None):
        env_path = app_inst.expander.env_path

        module_file_path = os.path.join(env_path, "module_loads")

        fs.mkdirp(env_path)

        loads_content = self._generate_loads_content(workspace)

        with open(module_file_path, "w+", encoding="utf-8") as f:
            f.write(loads_content)

    register_builtin("module_load", required=True)

    def module_load(self):
        shell = ramble.config.get("config:shell")
        return [f"{source_str(shell)} " + "{env_path}/module_loads"]

    register_builtin("module_list", required=True, depends_on=["module_load"])

    def module_list(self):
        list_file = "{experiment_run_dir}/" + self._list_file
        return [
            f"module list &> {list_file}",
        ]

    def get_package_list(self, workspace):
        del workspace
        app_inst = self.app_inst
        list_file = app_inst.expander.expand_var(
            f"{{experiment_run_dir}}/{self._list_file}"
        )

        if not os.path.exists(list_file):
            return []

        pkg_list = []
        pkg_regex = re.compile(r"\S+$")
        with open(list_file, encoding="utf-8") as f:
            packages = re.split(r"[0-9]*\)", f.read())
            for spec in packages:
                cleaned = spec.strip()
                m = pkg_regex.match(cleaned)
                if m:
                    parts = cleaned.split("/")
                    name = parts[0].strip()
                    version = "/".join(parts[1:]) if len(parts) > 1 else ""
                    pkg_list.append(
                        ramble.software_info.SoftwareInfo(
                            name=name, version=version
                        )
                    )
        return pkg_list

    def environment_load_commands(self) -> List[str]:
        return self.module_load()

    def environment_unload_commands(self) -> List[str]:
        return ["module purge"]
