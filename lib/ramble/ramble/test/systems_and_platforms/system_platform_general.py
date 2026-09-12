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

import ramble.software_info
import ramble.workspace
from ramble.main import RambleCommand

import spack.util.spack_yaml as syaml

workspace = RambleCommand("workspace")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)


def test_system_platform_works(workspace_name, mock_platforms, mock_systems, ensure_spack_runner):
    ws = ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]
    workspace(
        "manage",
        "experiments",
        "gromacs",
        "--wf",
        "lignocellulose",
        "-v",
        "n_ranks={processes_per_node}*{n_nodes}",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node={max_cores_per_node}",
        "-V",
        "system=spack-slurm-sys",
        "-V",
        "system-variant1=bar",
        global_args=global_args,
    )

    workspace("concretize", "--dry-run", global_args=global_args)

    # Verify there is spack info in the workspace
    with open(ws.config_file_path, encoding="utf-8") as f:
        data = f.read()
        assert "gromacs@{application::gromacs::version}" in data
        assert "intel-mpi" in data
        assert "intel-oneapi-mpi" in data

    workspace("setup", "--dry-run", global_args=["-D", ws.root])

    env_file = os.path.join(
        __import__("glob").glob(os.path.join(ws.software_dir, "spack*"))[0],
        "gromacs",
        "spack.yaml",
    )
    # Verify the packages.yaml files were merged
    with open(env_file, encoding="utf-8") as f:
        spack_config = syaml.load(stream=f)

    assert "spack" in spack_config
    assert "packages" in spack_config["spack"]
    assert "openmpi" in spack_config["spack"]["packages"]
    assert "buildable" in spack_config["spack"]["packages"]["openmpi"]
    assert "externals" in spack_config["spack"]["packages"]["openmpi"]

    # Verify slurm portions of execute script (to show workflow was applied)
    exec_file = os.path.join(
        ws.experiment_dir, "gromacs", "lignocellulose", "generated", "slurm_experiment_sbatch"
    )
    assert os.path.isfile(exec_file)
    with open(exec_file, encoding="utf-8") as f:
        data = f.read()
        assert "SBATCH" in data

    payload_file = os.path.join(
        ws.experiment_dir, "gromacs", "lignocellulose", "generated", "execute_experiment"
    )
    assert os.path.isfile(payload_file)
    with open(payload_file, encoding="utf-8") as f:
        payload_data = f.read()
        # Ensure cores_per_node=4 propagated, and srun is used from slurm
        assert "srun -n 4" in payload_data
    # Verify command variables were "defined"
    log_file = os.path.join(ws.log_dir, "setup.latest", "gromacs.lignocellulose.generated.out")
    expected = "max_nodes = 4 (dry-run) from 'sinfo -p " "mock-partition -O 'Nodes' | tail -n 1'"
    with open(log_file, encoding="utf-8") as f:
        data = f.read()
        assert expected in data


def test_platform_validator_threads_per_core(workspace_name, mock_platforms, mock_systems):
    ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]
    workspace(
        "manage",
        "experiments",
        "gromacs",
        "--wf",
        "lignocellulose",
        "-v",
        "n_ranks={processes_per_node}*{n_nodes}",
        "-v",
        "n_nodes=1",
        "-v",
        "n_threads=2",
        "-v",
        "processes_per_node=3",
        "-V",
        "system=spack-slurm-sys",
        global_args=global_args,
    )

    err_regex = re.escape(
        "Validator 'threads_per_node_platform_validation' (defined in 'mock-platform1') "
        "fails with message: 'Number of threads per node (2 * 3) exceeds max cores per node (4)'"
    )

    with pytest.raises(ramble.error.ObjectValidationError, match=err_regex):
        workspace("info", "--dry-run", global_args=global_args)


def test_skipping_platform_validator_threads_per_core(
    workspace_name, mock_platforms, mock_systems
):
    ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]
    workspace(
        "manage",
        "experiments",
        "gromacs",
        "--wf",
        "lignocellulose",
        "-v",
        "n_ranks={processes_per_node}*{n_nodes}",
        "-v",
        "n_nodes=1",
        "-v",
        "n_threads=2",
        "-v",
        "processes_per_node=3",
        "-V",
        "system=spack-slurm-sys",
        "-V",
        "validate_platform=false",
        global_args=global_args,
    )

    workspace("concretize", "--dry-run", global_args=global_args)
    workspace("info", "--dry-run", global_args=global_args)


def test_platform_validator_accelerators_per_node(workspace_name, mock_platforms, mock_systems):
    ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]
    workspace(
        "manage",
        "experiments",
        "gromacs",
        "--wf",
        "lignocellulose",
        "--default-variable-value",
        "1",
        "-v",
        "n_ranks=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "accelerators_per_node=2",
        "-V",
        "system=spack-slurm-sys",
        "-V",
        "accelerator=true",
        global_args=global_args,
    )

    err_regex = re.escape(
        "Validator 'accelerators_per_node_platform_validation' (defined in 'mock-platform1') "
        "fails with message: 'Number of accelerators per node (2) exceeds max accelerators "
        "on node (0)'"
    )

    workspace("concretize", "--dry-run", global_args=global_args)
    with pytest.raises(ramble.error.ObjectValidationError, match=err_regex):
        workspace("info", "--dry-run", global_args=global_args)


def test_system_validator_n_nodes(workspace_name, mock_platforms, mock_systems):
    ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]
    workspace(
        "manage",
        "experiments",
        "gromacs",
        "--wf",
        "lignocellulose",
        "--default-variable-value",
        "1",
        "-v",
        "n_nodes=10",
        "-v",
        "processes_per_node=1",
        "-V",
        "system=spack-slurm-sys",
        global_args=global_args,
    )

    err_regex = re.escape(
        "Validator 'n_nodes_system_validation' (defined in 'spack-slurm-sys') fails with message: "
        "'Number of nodes requested (10) exceeds max nodes (4)'"
    )

    with pytest.raises(ramble.error.ObjectValidationError, match=err_regex):
        workspace("info", "--dry-run", global_args=global_args)


def test_system_validator_n_ranks(workspace_name, mock_platforms, mock_systems):
    ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]
    workspace(
        "manage",
        "experiments",
        "gromacs",
        "--wf",
        "lignocellulose",
        "--default-variable-value",
        "1",
        "-v",
        "n_ranks=10",
        "-v",
        "n_nodes=2",
        "-V",
        "system=spack-slurm-sys",
        global_args=global_args,
    )

    err_regex = re.escape(
        "Validator 'n_ranks_system_validation' (defined in 'spack-slurm-sys') fails with "
        "message: 'Total number of ranks (10) exceeds max cores (4 * 2)'"
    )

    with pytest.raises(ramble.error.ObjectValidationError, match=err_regex):
        workspace("info", "--dry-run", global_args=global_args)
