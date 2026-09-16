# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import glob
import os

import pytest

import llnl.util.filesystem as fs

import ramble.workspace
from ramble.main import RambleCommand
from ramble.test.dry_run_helpers import search_files_for_string

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


@pytest.mark.long
def test_included_configuration_files(mutable_config, mutable_mock_workspace_path, workspace_name):

    test_config = """
ramble:
  include:
  - $workspace_root/test_configs
  variants:
    package_manager: spack
    validate_platform: false
    validate_system: false
  applications: {}
  software:
    packages: {}
    environments: {}
"""
    test_variables = """variables:
  mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
  batch_submit: 'batch_submit {execute_experiment}'
  partition: ['part1', 'part2']
  processes_per_node: ['16', '36']
  n_ranks: '{processes_per_node}*{n_nodes}'
  n_threads: '1'
"""

    test_applications = """applications:
  wrfv4:
    variables:
      env_name: ['wrfv4', 'wrfv4-portable']
    workloads:
      CONUS_12km:
        experiments:
          scaling_{n_nodes}_{partition}_{env_name}:
            success_criteria:
            - name: 'timing'
              mode: 'string'
              match: '.*Timing for main.*'
              file: '{experiment_run_dir}/rsl.out.base'
            env_vars:
              set:
                OMP_NUM_THREADS: '{n_threads}'
                TEST_VAR: '1'
              append:
              - var-separator: ', '
                vars:
                  TEST_VAR: 'add_var'
              - paths:
                  TEST_VAR: 'new_path'
              prepend:
              - paths:
                  TEST_VAR: 'pre_path'
              unset:
              - TEST_VAR
            variables:
              n_nodes: ['1', '2', '4', '8', '16']
            matrix:
            - n_nodes
            - env_name
"""

    test_software = """software:
  packages:
    gcc:
      pkg_spec: gcc@8.5.0
    intel-mpi:
      pkg_spec: intel-oneapi-mpi@2021.13.1
      compiler: gcc
    wrfv4:
      pkg_spec: wrf@4.2 build_type=dm+sm compile_type=em_real nesting=basic ~chem ~pnetcdf
      compiler: gcc
    wrfv4-portable:
      pkg_spec: 'wrf@4.2 build_type=dm+sm compile_type=em_real
        nesting=basic ~chem ~pnetcdf target=x86_64'
      compiler: gcc
  environments:
    wrfv4:
      packages:
      - wrfv4
      - intel-mpi
    wrfv4-portable:
      packages:
      - wrfv4-portable
      - intel-mpi
"""

    with ramble.workspace.create(workspace_name) as ws1:
        ws1.write()

        config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(test_config)

        test_configs_path = os.path.join(ws1.root, "test_configs")
        fs.mkdirp(test_configs_path)

        with open(
            os.path.join(test_configs_path, "applications.yaml"), "w+", encoding="utf-8"
        ) as f:
            f.write(test_applications)

        with open(os.path.join(test_configs_path, "variables.yaml"), "w+", encoding="utf-8") as f:
            f.write(test_variables)

        with open(os.path.join(test_configs_path, "software.yaml"), "w+", encoding="utf-8") as f:
            f.write(test_software)

        ws1._re_read()

        workspace("setup", "--dry-run", global_args=["-w", workspace_name])

        out_files = glob.glob(os.path.join(ws1.log_dir, "**", "*.out"), recursive=True)

        assert search_files_for_string(
            out_files,
            "Would download https://www2.mmm.ucar.edu/wrf/users/benchmark/v422/v42_bench_conus12km.tar.gz",
        )

        # Test software directories
        software_dirs = ["wrfv4", "wrfv4-portable"]
        software_base_dir = ws1.software_dir
        assert os.path.exists(software_base_dir)
        for software_dir in software_dirs:
            software_path = (
                __import__("glob").glob(os.path.join(software_base_dir, "spack*"))[0]
                + "/"
                + software_dir
            )
            assert os.path.exists(software_path)

            spack_file = os.path.join(software_path, "spack.yaml")
            assert os.path.exists(spack_file)

        expected_experiments = [
            "scaling_1_part1_wrfv4",
            "scaling_2_part1_wrfv4",
            "scaling_4_part1_wrfv4",
            "scaling_8_part1_wrfv4",
            "scaling_16_part1_wrfv4",
            "scaling_1_part2_wrfv4",
            "scaling_2_part2_wrfv4",
            "scaling_4_part2_wrfv4",
            "scaling_8_part2_wrfv4",
            "scaling_16_part2_wrfv4",
            "scaling_1_part1_wrfv4-portable",
            "scaling_2_part1_wrfv4-portable",
            "scaling_4_part1_wrfv4-portable",
            "scaling_8_part1_wrfv4-portable",
            "scaling_16_part1_wrfv4-portable",
            "scaling_1_part2_wrfv4-portable",
            "scaling_2_part2_wrfv4-portable",
            "scaling_4_part2_wrfv4-portable",
            "scaling_8_part2_wrfv4-portable",
            "scaling_16_part2_wrfv4-portable",
        ]

        # Test experiment directories
        for exp in expected_experiments:
            exp_dir = os.path.join(ws1.root, "experiments", "wrfv4", "CONUS_12km", exp)
            assert os.path.isdir(exp_dir)
            assert os.path.exists(os.path.join(exp_dir, "execute_experiment"))
