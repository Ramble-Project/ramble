# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import ramble.workspace
from ramble.main import RambleCommand

workspace = RambleCommand("workspace")


def test_nested_modifier_var(
    mutable_mock_workspace_path, mutable_applications, mock_modifiers, workspace_name
):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws1:

        workspace(
            "manage",
            "experiments",
            "gromacs",
            "--wf",
            "water_bare",
            "-e",
            "test",
            "-v",
            "n_nodes=1",
            "-v",
            "n_ranks=1",
            "-v",
            "modeless_required_var=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        workspace("concretize", global_args=global_args)

        template_path = os.path.join(ws1.config_dir, "test_template.tpl")

        with open(template_path, "w+", encoding="utf-8") as f:
            f.write("{level1_mod_var}")

        modifier_config_path = os.path.join(ws1.config_dir, "modifiers.yaml")

        with open(modifier_config_path, "w+", encoding="utf-8") as f:
            f.write("modifiers:\n")
            f.write("- name: test-mod\n")
            f.write("  mode: test\n")

        workspace("setup", "--dry-run", global_args=global_args)

        exec_script = os.path.join(
            ws1.experiment_dir, "gromacs", "water_bare", "test", "test_template"
        )

        with open(exec_script, encoding="utf-8") as f:
            data = f.read()
            assert "testing nested" in data
            assert "{level1_mod_var}" not in data
            assert "{level2_mod_var}" not in data
