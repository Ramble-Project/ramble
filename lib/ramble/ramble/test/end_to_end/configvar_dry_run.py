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

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures(
    "mutable_config", "mutable_mock_workspace_path", "workspace_deactivate"
)

workspace = RambleCommand("workspace")


@pytest.mark.maybeslow
def test_configvar_dry_run(make_workspace_from_config):
    test_scopes = ["site", "system", "user"]

    var_name1 = "test1"
    var_name2 = "envtestvar"
    var_val = 3

    test_config = """
ramble:
  variants:
    package_manager: spack
  variables:
    mpi_command: 'mpirun -n {{n_ranks}} -ppn {{processes_per_node}}'
    batch_submit: 'batch_submit {{execute_experiment}}'
    partition: 'part1'
    processes_per_node: '16'
    n_threads: '1'
  applications:
    openfoam:
      workloads:
        motorbike:
          experiments:
            "{}_test_{{{var_name}}}":
              variables:
                n_ranks: "{{{var_name}}}"
            "{}_test_{{{var_name}}}":
              variables:
                n_ranks: "{{{var_name}}}"
            "{}_test_{{{var_name}}}":
              variables:
                n_ranks: "{{{var_name}}}"
  software:
    packages:
      gcc:
        pkg_spec: gcc@8.5.0
      intel:
        pkg_spec: intel-oneapi-mpi@2021.13.1
        compiler: gcc
      openfoam:
        pkg_spec: openfoam
        compiler: gcc
    environments:
      openfoam:
        packages:
        - openfoam
        - intel
""".format(*test_scopes, var_name=var_name1)

    config = ramble.main.RambleCommand("config")

    expected_experiments = []
    for scope in test_scopes:
        config("--scope", scope, "add", f"variables:{var_name1}:{var_val}")
        expected_experiments.append(f"{scope}_test_{var_val}")

    for i, scope in enumerate(test_scopes):
        config("--scope", scope, "add", f"env_vars:set:{var_name2}{i}:{var_val}")

    ws, ws_name = make_workspace_from_config(test_config)

    workspace("setup", "--dry-run", global_args=["-w", ws_name])

    software_dir = "openfoam"
    software_base_dir = os.path.join(ws.root, ramble.workspace.WORKSPACE_SOFTWARE_PATH)
    assert os.path.exists(software_base_dir)

    software_path = (
        __import__("glob").glob(os.path.join(software_base_dir, "spack*"))[0] + "/" + software_dir
    )
    assert os.path.exists(software_path)

    for i, exp in enumerate(expected_experiments):
        exp_dir = os.path.join(ws.root, "experiments", "openfoam", "motorbike", exp)
        assert os.path.isdir(exp_dir)
        assert os.path.exists(os.path.join(exp_dir, "execute_experiment"))

        with open(os.path.join(exp_dir, "execute_experiment"), encoding="utf-8") as f:
            data = f.read()
            # Test the license exists
            assert f"export {var_name2}{i}={var_val}" in data
