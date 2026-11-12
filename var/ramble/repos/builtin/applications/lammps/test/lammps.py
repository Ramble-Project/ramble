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

workspace = RambleCommand("workspace")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)


def test_lammps_timestep_variables(workspace_name):
    global_args = ["-w", workspace_name]
    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "lammps",
            "--wf",
            "intel.lj",
            "-e",
            "test_exp",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-v",
            "mpi_command=mpirun -n {n_ranks}",
            "-v",
            "batch_submit={execute_experiment}",
            global_args=global_args,
        )
        workspace("setup", "--dry-run", global_args=global_args)

        run_dir = os.path.join(
            ws.experiment_dir, "lammps", "intel.lj", "test_exp"
        )
        with open(
            os.path.join(run_dir, "execute_experiment"), encoding="utf-8"
        ) as f:
            content = f.read()
            expected_editor = (
                '_ramble_file_editor.py" --mode regex --file input.txt'
            )
            assert (
                f"{expected_editor} --match 't index .*[0-9]+' --replace 't index 7900'"
                in content
            )
            assert (
                f"{expected_editor} --match 'w index .*[0-9]+' --replace 'w index 10'"
                in content
            )
            assert (
                f"{expected_editor} --match 'm index .*[0-9]+' --replace 'm index 1'"
                in content
            )
