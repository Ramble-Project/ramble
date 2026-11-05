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

import ramble.filters
import ramble.pipeline
import ramble.workspace
from ramble.main import RambleCommand
from ramble.test.dry_run_helpers import search_files_for_string

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


def test_nested_compilers_are_installed(
    mutable_config, mutable_mock_workspace_path, capsys, workspace_name
):
    # Use a bunch of compiler versions not actually present in Spack,
    # to avoid the test accidentally hit cases where the asked-for
    # compilers actually exist.
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
    wrf:
      workloads:
        CONUS_12km:
          experiments:
            test{n_nodes}_{env_name}:
              variables:
                n_nodes: '1'
  software:
    packages:
      gcc8:
        pkg_spec: gcc@8.5.1
      gcc9:
        pkg_spec: gcc@9.3.1
        compiler: gcc8
      gcc10:
        pkg_spec: gcc@10.1.1
        compiler: gcc9
      intel:
        pkg_spec: intel-oneapi-mpi@2021.13.1
        compiler: gcc10
      wrf:
        pkg_spec: wrf@4.2 build_type=dm+sm compile_type=em_real nesting=basic ~chem ~pnetcdf
        compiler: gcc10
    environments:
      wrf:
        packages:
        - wrf
        - intel
"""

    setup_type = ramble.pipeline.pipelines.setup
    setup_cls = ramble.pipeline.pipeline_class(setup_type)
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

        gcc8_str = "gcc@8.5.1"
        gcc9_str = "gcc@9.3.1"
        gcc10_str = "gcc@10.1.1"

        out_files = glob.glob(os.path.join(ws.log_dir, "**", "*.out"), recursive=True)

        assert search_files_for_string(out_files, gcc8_str)
        assert search_files_for_string(out_files, gcc9_str)
        assert search_files_for_string(out_files, gcc10_str)
