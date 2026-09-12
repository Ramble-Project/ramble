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
from ramble.test.dry_run_helpers import search_files_for_string
from ramble.util.foms import SummaryFoms

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


@pytest.mark.long
def test_gromacs_repeats(mutable_config, mutable_mock_workspace_path, workspace_name):
    test_config = """
ramble:
  variants:
    package_manager: spack
  config:
    n_repeats: '2'
  variables:
    processes_per_node: 16
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: '{execute_experiment}'
  applications:
    gromacs:
      workloads:
        water_gmx50:
          experiments:
            pme_single_rank:
              variables:
                n_ranks: '1'
                n_threads: '1'
                size: '0003'
                type: 'pme'
            rf_single_rank:
              n_repeats: '1'
              variables:
                n_ranks: '1'
                n_threads: '1'
                size: '0003'
                type: 'rf'
        water_bare:
          experiments:
            pme_single_rank:
              variables:
                n_ranks: '1'
                n_threads: '1'
                size: '0003'
                type: 'pme'
  software:
    packages:
      gcc:
        pkg_spec: gcc@8.5.0
      intel-mpi:
        pkg_spec: intel-oneapi-mpi@2021.13.1
        compiler: gcc
      gromacs:
        pkg_spec: gromacs@2021.6
        compiler: gcc
    environments:
      gromacs:
        packages:
        - gromacs
        - intel-mpi
"""

    with ramble.workspace.create(workspace_name) as ws1:
        ws1.write()

        config_path = os.path.join(ws1.config_dir, ramble.workspace.CONFIG_FILE_NAME)

        aux_software_path = os.path.join(
            ws1.config_dir, ramble.workspace.AUXILIARY_SOFTWARE_DIR_NAME
        )
        aux_software_files = ["packages.yaml", "my_test.sh"]

        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(test_config)

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
            "Would download https://ftp.gromacs.org/pub/benchmarks/water_GMX50_bare.tar.gz",
        )

        # Test software directories
        software_dirs = ["gromacs"]
        software_base_dir = ws1.software_dir
        assert os.path.exists(software_base_dir)
        for software_dir in software_dirs:
            software_path = os.path.join(
                __import__("glob").glob(os.path.join(software_base_dir, "spack*"))[0], software_dir
            )
            assert os.path.exists(software_path)

            spack_file = os.path.join(software_path, "spack.yaml")
            assert os.path.exists(spack_file)
            for file in aux_software_files:
                if not file.endswith(".yaml"):
                    file_path = os.path.join(software_path, file)
                    assert os.path.exists(file_path)

        # Each tuple (workload, exp base, n_repeats) expands to 1 base exp plus n_repeats exps
        expected_experiments = [
            ("water_gmx50", "pme_single_rank", 2),
            ("water_gmx50", "rf_single_rank", 1),
            ("water_bare", "pme_single_rank", 2),
        ]

        # Test experiment directories
        for wl, exp, repeats in expected_experiments:
            # Test that the base experiment directory is not created
            base_exp_dir = os.path.join(ws1.root, "experiments", "gromacs", wl, exp)
            assert not os.path.isdir(base_exp_dir)
            assert not os.path.exists(os.path.join(base_exp_dir, "execute_experiment"))

            # Test each of the repeat directories
            for r in range(1, repeats + 1):
                repeat_exp_dir = f"{base_exp_dir}.{r}"
                assert os.path.isdir(repeat_exp_dir)
                assert os.path.exists(os.path.join(repeat_exp_dir, "execute_experiment"))

                # TODO: Create fake experiment figures of merit.
                with open(os.path.join(repeat_exp_dir, "md.log"), "w+", encoding="utf-8") as f:
                    f.write("               Core t (s)   Wall t (s)        (%)\n")
                    f.write(f"       Time:       {r}{r}.{r}{r}{r}       {r}.{r}{r}{r}    1000.1\n")
                    f.write("                 (ns/day)    (hour/ns)\n")

            # Test that the number of repeats is not exceeded
            excess_repeat_exp_dir = f"{base_exp_dir}.{repeats + 1}"
            assert not os.path.isdir(excess_repeat_exp_dir)
            assert not os.path.exists(os.path.join(excess_repeat_exp_dir, "execute_experiment"))

        workspace("analyze", "-f", "text", "json", "yaml", global_args=["-w", workspace_name])

        text_results_files = glob.glob(os.path.join(ws1.results_dir, "results*.txt"))
        json_results_files = glob.glob(os.path.join(ws1.results_dir, "results*.json"))
        yaml_results_files = glob.glob(os.path.join(ws1.results_dir, "results*.yaml"))

        # Match both the file and the symlink
        assert len(text_results_files) == 2
        assert len(json_results_files) == 2
        assert len(yaml_results_files) == 2

        for text_result in text_results_files:
            with open(text_result, encoding="utf-8") as f:
                data = f.read()
                assert "Core Time = 11.111 s" in data
                assert "Core Time = 22.222 s" in data
                assert "summary::mean = 16.666 s" in data
                assert "summary::harmonic_mean = 14.815 s" in data
                assert "summary::median = 16.666 s" in data
                assert "summary::variance = 61.727 s^2" in data
                assert "summary::stdev = 7.857 s" in data
                assert "summary::cv = 0.471" in data

        # When --summary-only, only the base experiments are included
        workspace("analyze", "-s", global_args=["-w", workspace_name])
        result_file = glob.glob(os.path.join(ws1.results_dir, "results.latest.txt"))[0]
        with open(result_file, encoding="utf-8") as f:
            data = f.read()
            assert "gromacs.water_bare.pme_single_rank" in data
            assert "gromacs.water_bare.pme_single_rank.1" not in data
            assert "gromacs.water_bare.pme_single_rank.2" not in data

        # Assert that "NA" stats are not displayed
        os.remove(result_file)
        workspace(
            "analyze", "-s", "--where", "'{type}' == 'rf'", global_args=["-w", workspace_name]
        )
        with open(result_file, encoding="utf-8") as f:
            data = f.read()
            assert f"summary::{SummaryFoms.N_TOTAL.value} = 1 repeats" in data
            assert "summary::mean = 11.111 s" in data
            assert "= NA" not in data


@pytest.mark.long
def test_repeat_stats(mutable_config, mutable_mock_workspace_path, workspace_name):
    test_config = """
ramble:
  variables:
    n_nodes: 1
    processes_per_node: 1
    mpi_command: ''
    batch_submit: '{execute_experiment}'
  applications:
    sleep:
      workloads:
        sleep:
          experiments:
            sleep_test:
              n_repeats: 3
"""
    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
        config_path = os.path.join(ws.config_dir, ramble.workspace.CONFIG_FILE_NAME)
        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(test_config)
        ws._re_read()

        workspace("setup", "--dry-run", global_args=["-w", workspace_name])

        base_exp_dir = os.path.join(ws.root, "experiments", "sleep", "sleep", "sleep_test")
        for r in range(1, 4):
            dir = f"{base_exp_dir}.{r}"
            log_path = os.path.join(dir, f"{os.path.basename(dir)}.out")
            with open(log_path, "w+", encoding="utf-8") as f:
                f.write(f"{r}:0.0elapsed\n")
                # Purposely fail the last experiment
                if r != 3:
                    f.write(f"Sleep for {60 * r} seconds\n")

        workspace("analyze", "-s", global_args=["-w", workspace_name])
        result_file = glob.glob(os.path.join(ws.results_dir, "results.latest.txt"))[0]
        with open(result_file, encoding="utf-8") as f:
            data = f.read()
            assert f"summary::{SummaryFoms.N_TOTAL.value} = 3 repeats" in data
            assert f"summary::{SummaryFoms.N_SUCCESS.value} = 2 repeats" in data
            assert "summary::min = 1.0 minutes" in data
            # Assert that the last experiment is not included in the stats
            assert "summary::max = 2.0 minutes" in data
            assert "summary::mean = 1.5 minutes" in data
            assert "mode:\n      value = Sleep" in data


def test_repeat_info(mutable_config, mutable_mock_workspace_path, workspace_name):
    test_config = """
ramble:
  variables:
    n_nodes: 1
    processes_per_node: 1
    mpi_command: ''
    batch_submit: '{execute_experiment}'
  applications:
    sleep:
      workloads:
        sleep:
          experiments:
            sleep_test:
              n_repeats: 3
"""

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
        config_path = os.path.join(ws.config_dir, ramble.workspace.CONFIG_FILE_NAME)
        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(test_config)
        ws._re_read()

        output = workspace("info", global_args=["-w", workspace_name])

        assert "Experiment 1:" in output
        assert "Experiment 2:" in output
        assert "Experiment 3:" in output
        assert "Experiment 4:" in output
