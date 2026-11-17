# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import re

import pytest

import ramble.filters
import ramble.pipeline
import ramble.util.ramble_yaml as syaml
import ramble.workspace
from ramble.main import RambleCommand
from ramble.util import json_util

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


@pytest.mark.maybeslow
@pytest.mark.filterwarnings("ignore:invalid decimal literal")
def test_dryrun_chained_experiments(mutable_config, mutable_mock_workspace_path, workspace_name):
    test_config = r"""
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
    intel-mpi-benchmarks:
      template: true
      workloads:
        pingpong:
          template: true
          experiments:
            pingpong_chain:
              template: true
              variables:
                n_ranks: '2'
        collective:
          template: true
          experiments:
            collective_chain:
              template: true
              variables:
                n_ranks: '2'
              chained_experiments:
              - name: 'intel-mpi-benchmarks.pingpong.pingpong_chain'
                command: '{execute_experiment}'
    gromacs:
      chained_experiments:
      - name: intel-mpi-benchmarks.collective.*
        command: '{execute_experiment}'
        order: 'after_root'
      workloads:
        water_bare:
          chained_experiments:
          - name: intel-mpi-benchmarks.*.collective_chain
            command: '{execute_experiment}'
            order: 'before_root'
            variables:
              n_ranks: '4'
          experiments:
            parent_test:
              chained_experiments:
              - name: intel-mpi-benchmarks.collective.collective_chain
                command: '{execute_experiment}'
                order: 'before_root'
              variables:
                n_nodes: '2'
  software:
    packages:
      gcc:
        pkg_spec: gcc@9.3.0 target=x86_64
      intel-mpi:
        pkg_spec: intel-oneapi-mpi@2021.13.1
        compiler: gcc
      imb:
        pkg_spec: intel-mpi-benchmarks
        compiler: gcc
      gromacs:
        pkg_spec: gromacs
        compiler: gcc
    environments:
      intel-mpi-benchmarks:
        packages:
        - imb
        - intel-mpi
      gromacs:
        packages:
        - gromacs
        - intel-mpi
"""

    mock_output_data = """
  14 100 1.5 1.0 2.0

# All processes entering MPI_Finalize
"""

    setup_type = ramble.pipeline.pipelines.setup
    setup_cls = ramble.pipeline.pipeline_class(setup_type)

    analyze_type = ramble.pipeline.pipelines.analyze
    analyze_cls = ramble.pipeline.pipeline_class(analyze_type)

    filters = ramble.filters.Filters()

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        config_path = os.path.join(ws.config_dir, ramble.workspace.CONFIG_FILE_NAME)

        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(test_config)

        ws.dry_run = True
        ws._re_read()

        setup_pipeline = setup_cls(ws, filters)
        setup_pipeline.run()

        template_dir = os.path.join(ws.experiment_dir, "intel-mpi-benchmarks")
        assert not os.path.exists(template_dir)

        parent_dir = os.path.join(ws.experiment_dir, "gromacs", "water_bare", "parent_test")
        script = os.path.join(parent_dir, "execute_experiment")
        assert os.path.exists(script)

        # Check all chained experiments are referenced
        with open(script, encoding="utf-8") as f:
            parent_script_data = f.read()

        for chain_idx in [1, 3, 5]:
            chained_script = os.path.join(
                parent_dir,
                "chained_experiments",
                rf"chain.{chain_idx}.intel-mpi-benchmarks.collective.collective_chain",
                "execute_experiment",
            )
            assert os.path.exists(chained_script)
            assert chained_script in parent_script_data

            # Check that experiment 1 has n_ranks = 4 instead of 2
            if chain_idx == 3:
                with open(chained_script, encoding="utf-8") as f:
                    assert "mpirun -n 4" in f.read()

        expected_order = [
            re.compile(r".*3.intel-mpi-benchmarks.collective.collective_chain.*"),
            re.compile(r".*5.intel-mpi-benchmarks.collective.collective_chain.*"),
            re.compile(r".*4.intel-mpi-benchmarks.pingpong.pingpong_chain.*"),
            re.compile(r".*2.intel-mpi-benchmarks.pingpong.pingpong_chain.*"),
            re.compile(r".*1.intel-mpi-benchmarks.collective.collective_chain.*"),
            re.compile(r".*0.intel-mpi-benchmarks.pingpong.pingpong_chain.*"),
        ]

        # Check prepend / append order is correct
        with open(script, encoding="utf-8") as f:

            for line in f:
                if expected_order[0].match(line):
                    expected_order.pop(0)

        # Ensure results contain chain information, and properly extract figures of merit
        chain_exp_name = r"chain.3.intel-mpi-benchmarks.collective.collective_chain"
        output_path_3 = os.path.join(
            parent_dir,
            "chained_experiments",
            chain_exp_name,
            f"gromacs.water_bare.parent_test.{chain_exp_name}.out",
        )

        with open(output_path_3, "w+", encoding="utf-8") as f:
            f.write(mock_output_data)

        analyze_pipeline = analyze_cls(ws, filters, output_formats=["json", "yaml"])
        analyze_pipeline.run()

        base_name = r"gromacs.water_bare.parent_test"
        collective_name = r"intel-mpi-benchmarks.collective.collective_chain"
        pingpong_name = r"intel-mpi-benchmarks.pingpong.pingpong_chain"

        chain_def = [
            f"{base_name}.chain.3.{collective_name}",
            f"{base_name}.chain.5.{collective_name}",
            f"{base_name}",
            f"{base_name}.chain.4.{pingpong_name}",
            f"{base_name}.chain.2.{pingpong_name}",
            f"{base_name}.chain.1.{collective_name}",
            f"{base_name}.chain.0.{pingpong_name}",
        ]

        names = ["results.latest.json", "results.latest.yaml"]
        loaders = [json_util.load, syaml.load]
        for name, loader in zip(names, loaders):
            with open(os.path.join(ws.root, name), encoding="utf-8") as f:
                data = loader(f)

                assert "experiments" in data

                for exp_def in data["experiments"]:
                    if (
                        exp_def["name"]
                        == r"gromacs.water_bare.parent_test."
                        + r"chain.3.intel-mpi-benchmarks.collective.collective_chain"
                    ):
                        assert exp_def["RAMBLE_STATUS"] == "SUCCESS"
                    else:
                        assert exp_def["RAMBLE_STATUS"] == "FAILED"
                    assert exp_def["EXPERIMENT_CHAIN"] == chain_def
