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
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


def test_wrfv4_aps_test(mutable_config, mutable_mock_workspace_path, workspace_name):
    test_config = """
ramble:
  variants:
    package_manager: spack
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '10'
    n_ranks: '{processes_per_node}*{n_nodes}'
    n_threads: '1'
  applications:
    wrfv4:
      workloads:
        CONUS_12km:
          experiments:
            modifier_test:
              modifiers:
              - name: intel-aps
                mode: mpi
                on_executable:
                - '*'
              variables:
                n_nodes: '1'
  software:
    packages:
      gcc:
        pkg_spec: gcc@8.5.0
      intel-mpi:
        pkg_spec: intel-oneapi-mpi@2021.13.1
        compiler: gcc
      wrfv4:
        pkg_spec: wrf@4.2 build_type=dm+sm compile_type=em_real nesting=basic ~chem ~pnetcdf
        compiler: gcc
      intel-oneapi-vtune:
        pkg_spec: intel-oneapi-vtune
    environments:
      wrfv4:
        packages:
        - wrfv4
        - intel-mpi
        - intel-oneapi-vtune
"""

    with ramble.workspace.create(workspace_name) as ws1:
        ws1.write()

        config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(test_config)

        ws1._re_read()

        workspace("setup", "--dry-run", global_args=["-w", workspace_name])

        software_path = os.path.join(
            __import__("glob").glob(os.path.join(ws1.software_dir, "spack*"))[0],
            "wrfv4",
            "spack.yaml",
        )
        with open(software_path, encoding="utf-8") as f:
            assert "intel-oneapi-vtune" in f.read()

        execute_script = os.path.join(
            ws1.experiment_dir, "wrfv4", "CONUS_12km", "modifier_test", "execute_experiment"
        )
        with open(execute_script, encoding="utf-8") as f:
            data = f.read()
            assert "aps -c mpi" in data
            assert "aps-report" in data
