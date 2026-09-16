# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import glob
import os
from unittest.mock import patch

import pytest

import ramble.workspace
from ramble.main import RambleCommand
from ramble.pkg_man.builtin import spack_lightweight
from ramble.test.dry_run_helpers import search_files_for_string
from ramble.test.mock_spack_runner import MockSpackRunner

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


@pytest.mark.long
@patch.object(spack_lightweight, "SpackRunner", side_effect=MockSpackRunner)
def test_wrfv4_exclusions(
    mock_spack_runner, mutable_config, mutable_mock_workspace_path, workspace_name
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
              zips:
                partitions:
                - partition
                - processes_per_node
              matrix:
              - n_nodes
              - env_name
              - partitions
              exclude:
                variables:
                  n_nodes: '1'
                zips:
                  partitions:
                  - partition
                  - processes_per_node
                matrix:
                - env_name
                - partitions
                where:
                - '{n_nodes} == 16'
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

    test_licenses = """
licenses:
  wrfv4:
    set:
      WRF_LICENSE: port@server
"""

    test_compilers = """
compilers:
- compiler:
    spec: gcc@=13.2.0
    paths:
      cc: /usr/bin/gcc
      cxx: /usr/bin/g++
      f77: null
      fc: null
    flags: {}
    operating_system: rocky8
    target: x86_64
    modules: []
    environment: {}
    extra_rpaths: []
"""

    with ramble.workspace.create(workspace_name) as ws1:
        ws1.write()

        config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)
        license_path = os.path.join(ws1.config_dir, "licenses.yaml")
        compilers_path = os.path.join(
            ws1.config_dir, ramble.workspace.AUXILIARY_SOFTWARE_DIR_NAME, "compilers.yaml"
        )

        aux_software_path = os.path.join(
            ws1.config_dir, ramble.workspace.AUXILIARY_SOFTWARE_DIR_NAME
        )
        aux_software_files = ["packages.yaml", "my_test.sh"]

        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(test_config)

        with open(license_path, "w+", encoding="utf-8") as f:
            f.write(test_licenses)

        with open(compilers_path, "w+", encoding="utf-8") as f:
            f.write(test_compilers)

        for file in aux_software_files:
            file_path = os.path.join(aux_software_path, file)
            with open(file_path, "w+", encoding="utf-8") as f:
                f.write("")

        # Write a command template
        with open(os.path.join(ws1.config_dir, "full_command.tpl"), "w+", encoding="utf-8") as f:
            f.write("{command}")

        ws1._re_read()

        workspace("setup", "--dry-run", global_args=["-w", workspace_name])

        out_files = glob.glob(os.path.join(ws1.log_dir, "**", "*.out"), recursive=True)

        assert search_files_for_string(
            out_files,
            "Would download https://www2.mmm.ucar.edu/wrf/users/benchmark/v422/v42_bench_conus12km.tar.gz",
        )

        # Test software directories
        software_dirs = ["wrfv4", "wrfv4-portable"]
        software_base_dir = os.path.join(ws1.root, ramble.workspace.WORKSPACE_SOFTWARE_PATH)
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
            for file in aux_software_files:
                if not file.endswith(".yaml"):
                    file_path = os.path.join(software_path, file)
                    assert os.path.exists(file_path)

        expected_experiments = [
            "scaling_2_part1_wrfv4",
            "scaling_4_part1_wrfv4",
            "scaling_8_part1_wrfv4",
            "scaling_2_part2_wrfv4",
            "scaling_4_part2_wrfv4",
            "scaling_8_part2_wrfv4",
            "scaling_2_part1_wrfv4-portable",
            "scaling_4_part1_wrfv4-portable",
            "scaling_8_part1_wrfv4-portable",
            "scaling_2_part2_wrfv4-portable",
            "scaling_4_part2_wrfv4-portable",
            "scaling_8_part2_wrfv4-portable",
        ]

        excluded_experiments = [
            "scaling_1_part1_wrfv4",
            "scaling_16_part1_wrfv4",
            "scaling_1_part2_wrfv4",
            "scaling_16_part2_wrfv4",
            "scaling_1_part1_wrfv4-portable",
            "scaling_16_part1_wrfv4-portable",
            "scaling_1_part2_wrfv4-portable",
            "scaling_16_part2_wrfv4-portable",
        ]

        for exp in excluded_experiments:
            exp_dir = os.path.join(ws1.root, "experiments", "wrfv4", "CONUS_12km", exp)
            assert not os.path.isdir(exp_dir)

        # Test experiment directories
        for exp in expected_experiments:
            exp_dir = os.path.join(ws1.root, "experiments", "wrfv4", "CONUS_12km", exp)
            assert os.path.isdir(exp_dir)
            assert os.path.exists(os.path.join(exp_dir, "execute_experiment"))
            assert os.path.exists(os.path.join(exp_dir, "full_command"))

            with open(os.path.join(exp_dir, "full_command"), encoding="utf-8") as f:
                data = f.read()

                # Test the required environment variables exist
                assert 'export OMP_NUM_THREADS="1"' in data
                assert "export TEST_VAR=1" in data
                assert "unset TEST_VAR" in data

                # Test the expected portions of the execution command exist
                expected_editor = '_ramble_file_editor.py" --mode regex --file namelist.input'
                expected_fix_hour = (
                    expected_editor
                    + " --match ' start_hour.*' --replace"
                    + " ' start_hour                          = 23,'"
                )
                expected_fix_restart = (
                    expected_editor
                    + " --match ' restart .*' --replace"
                    + " ' restart                             = .true.,'"
                )
                assert expected_fix_hour in data
                assert expected_fix_restart in data
                assert "mpirun" in data

                assert "wrf.exe" in data

                # Test the run script has a reference to the experiment log file
                assert os.path.join(exp_dir, f"{exp}.out") in data

            with open(os.path.join(exp_dir, "execute_experiment"), encoding="utf-8") as f:
                data = f.read()

                # Test the required environment variables exist
                assert 'export OMP_NUM_THREADS="1"' in data
                assert "export TEST_VAR=1" in data
                assert "unset TEST_VAR" in data

                # Test the expected portions of the execution command exist
                expected_editor = '_ramble_file_editor.py" --mode regex --file namelist.input'
                expected_fix_hour = (
                    expected_editor
                    + " --match ' start_hour.*' --replace"
                    + " ' start_hour                          = 23,'"
                )
                expected_fix_restart = (
                    expected_editor
                    + " --match ' restart .*' --replace"
                    + " ' restart                             = .true.,'"
                )
                assert expected_fix_hour in data
                assert expected_fix_restart in data
                assert "mpirun" in data

                assert "wrf.exe" in data

                # Test the run script has a reference to the experiment log file
                assert os.path.join(exp_dir, f"{exp}.out") in data

                # Test that spack is used
                assert "spack env activate" in data

            # Create fake figures of merit.
            with open(os.path.join(exp_dir, "rsl.out.base"), "w+", encoding="utf-8") as f:
                for i in range(1, 6):
                    f.write(f"Timing for main: time 2019-11-27_00:00:00 on domain 1: {i}{i}.{i}\n")
                f.write("wrf: SUCCESS COMPLETE WRF\n")

            # Create files that match archive patterns
            new_file = os.path.join(exp_dir, "rsl.error.base")

            f = open(new_file, "w+", encoding="utf-8")
            f.close()

        workspace("analyze", "-f", "text", "json", "yaml", global_args=["-w", workspace_name])
        text_symlink_results_files = glob.glob(os.path.join(ws1.results_dir, "results.latest.txt"))
        text_results_files = glob.glob(os.path.join(ws1.results_dir, "results*.txt"))
        json_results_files = glob.glob(os.path.join(ws1.results_dir, "results*.json"))
        yaml_results_files = glob.glob(os.path.join(ws1.results_dir, "results*.yaml"))
        assert len(text_symlink_results_files) == 1
        assert len(text_results_files) == 2
        assert len(json_results_files) == 2
        assert len(yaml_results_files) == 2

        with open(text_results_files[0], encoding="utf-8") as f:
            data = f.read()
            assert "Average Timestep Time = 33.3 s" in data
            assert "Cumulative Timestep Time = 166.5 s" in data
            assert "Minimum Timestep Time = 11.1 s" in data
            assert "Maximum Timestep Time = 55.5 s" in data
            assert "Avg. Max Ratio Time = 0.6" in data
            assert "Number of timesteps = 5" in data
            assert "Software definitions:" in data
            assert "spack packages:" in data

        workspace("archive", global_args=["-w", workspace_name])

        assert ws1.latest_archive
        assert os.path.exists(ws1.latest_archive_path)

        for exp in expected_experiments:
            exp_dir = os.path.join(
                ws1.latest_archive_path, "experiments", "wrfv4", "CONUS_12km", exp
            )
            assert os.path.isdir(exp_dir)
            assert os.path.exists(os.path.join(exp_dir, "execute_experiment"))
            assert os.path.exists(os.path.join(exp_dir, "full_command"))
            assert os.path.exists(os.path.join(exp_dir, "rsl.out.base"))
            assert os.path.exists(os.path.join(exp_dir, "rsl.error.base"))
