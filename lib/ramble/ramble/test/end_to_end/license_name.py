# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

from ramble.main import RambleCommand

pytestmark = pytest.mark.usefixtures(
    "mutable_config", "mutable_mock_workspace_path", "mutable_mock_apps_repo"
)

workspace = RambleCommand("workspace")

test_val = "test_val"


def license_param_core(app_name, make_workspace_from_config, test_licenses, expected_val):
    test_config = f"""
ramble:
  variables:
    mpi_command: mpirun -n 1
    batch_submit: ''
    processes_per_node: 1
  applications:
    {app_name}:
      workloads:
        template_wl:
          experiments:
            test:
              variables:
                n_ranks: '1'
  software:
    packages: {{}}
    environments: {{}}
"""

    ws, ws_name = make_workspace_from_config(test_config)

    license_path = os.path.join(ws.config_dir, "licenses.yaml")
    with open(license_path, "w+", encoding="utf-8") as f:
        f.write(test_licenses)

    ws._re_read()

    workspace("setup", "--dry-run", global_args=["-w", ws_name])

    license_inc_path = os.path.join(ws.root, "shared", "licenses", app_name, "license.inc")
    expected_vals = [expected_val] if isinstance(expected_val, str) else expected_val
    with open(license_inc_path, encoding="utf-8") as f:
        data = f.read()
        # Test the license is added to the include file
        for val in expected_vals:
            assert val in data

    exec_path = os.path.join(
        ws.root, "experiments", app_name, "template_wl", "test", "execute_experiment"
    )
    with open(exec_path, encoding="utf-8") as f:
        exec_data = f.read()
        assert f". {license_inc_path}" in exec_data


def test_license_name_parent(mutable_mock_apps_repo, make_workspace_from_config):
    app_name = "basic-inherited-nolicense"
    test_licenses = f"""
licenses:
  basic:
    set:
      TEST_VAR: {test_val}
"""
    expected_val = test_val
    license_param_core(app_name, make_workspace_from_config, test_licenses, expected_val)


def test_license_name_self_implicit(mutable_mock_apps_repo, make_workspace_from_config):
    app_name = "basic-inherited-nolicense"
    expected_val = test_val + "_imp"
    test_licenses = f"""
licenses:
  basic:
    set:
      TEST_VAR: {test_val}
  basic-inherited-nolicense:
    set:
      TEST_VAR: {expected_val}
"""
    license_param_core(app_name, make_workspace_from_config, test_licenses, expected_val)


def test_license_name_self_explicit(mutable_mock_apps_repo, make_workspace_from_config):
    app_name = "basic-inherited"
    expected_val = test_val + "_exp"
    test_licenses = f"""
licenses:
  basic:
    set:
      TEST_VAR: {test_val}
  basic-inherited:
    set:
      TEST_VAR: {expected_val}
"""
    license_param_core(app_name, make_workspace_from_config, test_licenses, expected_val)


def test_license_multiple_actions(mutable_mock_apps_repo, make_workspace_from_config):
    app_name = "basic-inherited-nolicense"
    test_licenses = f"""
licenses:
  basic:
    set:
      TEST_VAR: {test_val}
    append:
    - var-separator: ':'
      vars:
        APPEND_VAR: appended_val
"""
    license_param_core(
        app_name,
        make_workspace_from_config,
        test_licenses,
        [f"export TEST_VAR={test_val}", "appended_val"],
    )
