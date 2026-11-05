# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

from ramble.error import RambleCommandError
from ramble.main import RambleCommand

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


def test_missing_required_dry_run(make_workspace_from_config):
    """Tests tty.die at end of ramble.application_types.spack._create_software_env"""
    test_config = """
ramble:
  variants:
    package_manager: spack
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: 30
    n_ranks: '{processes_per_node}*{n_nodes}'
    n_threads: '1'
  applications:
    wrf@3.9.1.1:
      workloads:
        CONUS_2p5km:
          experiments:
            eight_node:
              variables:
                n_nodes: '8'
  software:
    packages:
      gcc8:
        pkg_spec: gcc@8.2.0 target=x86_64
        compiler_spec: gcc@8.2.0
      intel-mpi:
        pkg_spec: intel-oneapi-mpi@2021.13.1
        compiler: gcc8
      wrf:
        pkg_spec: my_wrf@3.9.1.1 build_type=dm+sm compile_type=em_real nesting=basic ~pnetcdf
        compiler: gcc8
    environments:
      wrf:
        packages:
        - intel-mpi
        - wrf
"""

    ws, ws_name = make_workspace_from_config(test_config)

    with pytest.raises(RambleCommandError):
        workspace("setup", "--dry-run", global_args=["-w", ws_name])
    setup_log = os.path.join(ws.log_dir, "setup.latest.out")
    with open(setup_log, encoding="utf-8") as f:
        assert "Software spec wrf is not defined in environment wrf" in f.read()
