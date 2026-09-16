# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.workspace
from ramble.main import RambleCommand
from ramble.test.dry_run_helpers import SCOPES, dry_run_config
from ramble.test.modifier_functionality import modifier_helpers

workspace = RambleCommand("workspace")


@pytest.mark.parametrize(
    "scope",
    [
        SCOPES.workspace,
        SCOPES.application,
        SCOPES.workload,
        SCOPES.experiment,
    ],
)
@pytest.mark.parametrize(
    "factory,answer",
    [
        (modifier_helpers.intel_aps_modifier, modifier_helpers.intel_aps_answer),
        (modifier_helpers.lscpu_modifier, modifier_helpers.lscpu_answer),
    ],
)
def test_gromacs_single_full_modifier_dry_run(
    mutable_mock_workspace_path, mutable_applications, scope, factory, answer, workspace_name
):
    test_modifiers = [
        (scope, factory()),
    ]

    software_tests, expected_strs = answer()

    with ramble.workspace.create(workspace_name) as ws1:
        ws1.write()

        config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

        dry_run_config("modifiers", test_modifiers, config_path, "gromacs", "water_bare")

        ws1._re_read()

        workspace("concretize", global_args=["-D", ws1.root])
        workspace("setup", "--dry-run", global_args=["-D", ws1.root])

        # Test software directories
        software_base_dir = __import__("glob").glob(os.path.join(ws1.software_dir, "spack*"))[0]

        modifier_helpers.check_software_env(software_base_dir, software_tests)

        exp_script = os.path.join(
            ws1.experiment_dir, "gromacs", "water_bare", "test_exp", "execute_experiment"
        )

        modifier_helpers.check_execute_script(exp_script, expected_strs)


@pytest.mark.parametrize(
    "scope",
    [
        SCOPES.workspace,
        SCOPES.application,
        SCOPES.workload,
        SCOPES.experiment,
    ],
)
@pytest.mark.parametrize(
    "mod_name,answer",
    [
        ("intel-aps", modifier_helpers.intel_aps_answer),
        ("lscpu", modifier_helpers.lscpu_answer),
    ],
)
def test_gromacs_single_stub_modifier_dry_run(
    mutable_mock_workspace_path, mutable_applications, scope, mod_name, answer
):
    workspace_name = "test_gromacs_single_modifier_dry_run"

    test_modifiers = [
        (scope, modifier_helpers.named_modifier(mod_name)),
    ]

    software_tests, expected_strs = answer()

    with ramble.workspace.create(workspace_name) as ws1:
        ws1.write()

        config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

        dry_run_config("modifiers", test_modifiers, config_path, "gromacs", "water_bare")

        ws1._re_read()

        workspace("concretize", global_args=["-D", ws1.root])
        workspace("setup", "--dry-run", global_args=["-D", ws1.root])

        # Test software directories
        software_base_dir = __import__("glob").glob(os.path.join(ws1.software_dir, "spack*"))[0]

        modifier_helpers.check_software_env(software_base_dir, software_tests)

        exp_script = os.path.join(
            ws1.experiment_dir, "gromacs", "water_bare", "test_exp", "execute_experiment"
        )

        modifier_helpers.check_execute_script(exp_script, expected_strs)
