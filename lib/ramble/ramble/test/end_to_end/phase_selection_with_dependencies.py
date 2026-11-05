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

import ramble.workspace
from ramble.main import RambleCommand

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


@pytest.fixture(scope="function")
def enable_verbose():
    import llnl.util.tty

    old_setting = llnl.util.tty._verbose
    llnl.util.tty._verbose = True
    yield
    llnl.util.tty._verbose = old_setting


@pytest.mark.long
def test_workspace_phase_selection_with_dependencies(
    mutable_config, mutable_mock_workspace_path, enable_verbose, workspace_name
):
    test_config = """
ramble:
  variants:
    package_manager: spack
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    partition: ['part1', 'part2']
    processes_per_node: ['16', '36']
    n_ranks: '{processes_per_node}*{n_nodes}'
    n_threads: '1'
  applications:
    wrf:
      variables:
        env_name: ['wrf', 'wrf-portable']
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
  software:
    packages:
      gcc:
        pkg_spec: gcc@8.5.0
      intel-mpi:
        pkg_spec: intel-oneapi-mpi@2021.13.1
        compiler: gcc
      wrf:
        pkg_spec: wrf@4.2 build_type=dm+sm compile_type=em_real nesting=basic ~chem ~pnetcdf
        compiler: gcc
      wrf-portable:
        pkg_spec: 'wrf@4.2 build_type=dm+sm compile_type=em_real
          nesting=basic ~chem ~pnetcdf target=x86_64'
        compiler: gcc
    environments:
      wrf:
        packages:
        - wrf
        - intel-mpi
      wrf-portable:
        packages:
        - wrf-portable
        - intel-mpi
"""

    test_licenses = """
licenses:
  wrf:
    set:
      WRF_LICENSE: port@server
"""

    with ramble.workspace.create(workspace_name) as ws1:
        ws1.write()

        config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)
        license_path = os.path.join(ws1.config_dir, "licenses.yaml")

        aux_software_path = os.path.join(
            ws1.config_dir, ramble.workspace.AUXILIARY_SOFTWARE_DIR_NAME
        )
        aux_software_files = ["packages.yaml", "my_test.sh"]

        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(test_config)

        with open(license_path, "w+", encoding="utf-8") as f:
            f.write(test_licenses)

        for file in aux_software_files:
            file_path = os.path.join(aux_software_path, file)
            with open(file_path, "w+", encoding="utf-8") as f:
                f.write("")

        # Write a command template
        with open(os.path.join(ws1.config_dir, "full_command.tpl"), "w+", encoding="utf-8") as f:
            f.write("{command}")

        ws1._re_read()

        output = workspace("info", "-vv", global_args=["-w", workspace_name])
        assert "Phases for setup pipeline:" in output
        assert "get_inputs" in output
        assert "make_experiments" in output
        assert "Phases for analyze pipeline:" in output
        assert "Phases for archive pipeline:" in output
        assert "Phases for mirror pipeline:" in output

        workspace(
            "setup",
            "--phases",
            "make_*",
            "--include-phase-dependencies",
            "--dry-run",
            global_args=["-v", "-w", workspace_name],
        )

        out_files = glob.glob(os.path.join(ws1.log_dir, "setup.*", "*.out"), recursive=True)

        expected_phase_order = ["get_inputs", "software_create_env", "make_experiments"]
        for file in out_files:
            found = [False, False, False]
            cur_found = 0
            with open(file, encoding="utf-8") as f:
                for line in f:
                    if expected_phase_order[cur_found] in line:
                        found[cur_found] = True
                        cur_found += 1

                    if cur_found == len(found):
                        break

            assert all(found)
