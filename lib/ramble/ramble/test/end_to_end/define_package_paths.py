# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
from unittest.mock import patch

import pytest

import ramble.workspace
from ramble.main import RambleCommand
from ramble.pkg_man.builtin import spack_lightweight
from ramble.test.mock_spack_runner import MockSpackRunner

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)

workspace = RambleCommand("workspace")


def _spack_loc_log_line(pkg_spec):
    return f"with args: ['location', '-i', '{pkg_spec}']"


def test_define_package_paths(workspace_name):
    test_config = """
ramble:
  variants:
    package_manager: spack
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: '{execute_experiment}'
    processes_per_node: '1'
  applications:
    gromacs:
      workloads:
        water_bare:
          experiments:
            test1:
              variables:
                n_nodes: '1'
            test2:
              variables:
                n_nodes: '2'
  software:
    packages:
      gromacs:
        pkg_spec: gromacs
      intel-mpi:
        pkg_spec: intel-oneapi-mpi@2021.11.0
    environments:
      gromacs:
        packages:
        - gromacs
        - intel-mpi
"""
    ws = ramble.workspace.create(workspace_name)
    ws.write()

    config_path = os.path.join(ws.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws._re_read()

    workspace(
        "setup",
        "--dry-run",
        global_args=["-w", workspace_name],
    )

    # test1 should attempt to invoke `spack location -i` on dep packages.
    test1_log = os.path.join(ws.log_dir, "setup.latest", "gromacs.water_bare.test1.out")
    gromacs_log_line = _spack_loc_log_line("gromacs")
    impi_log_line = _spack_loc_log_line("intel-oneapi-mpi@2021.11.0")
    with open(test1_log, encoding="utf-8") as f:
        content = f.read()
        assert "Executing phase define_package_paths" in content
        assert content.count(gromacs_log_line) == 1
        assert content.count(impi_log_line) == 1

    # test2 should use cached paths without invoking spack.
    test2_log = os.path.join(ws.log_dir, "setup.latest", "gromacs.water_bare.test2.out")
    with open(test2_log, encoding="utf-8") as f:
        content = f.read()
        assert "Executing phase define_package_paths" in content
        assert gromacs_log_line not in content
        assert impi_log_line not in content


def test_package_path_variables(workspace_name):
    test_config = """
ramble:
  variants:
    package_manager: spack
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: '{execute_experiment}'
    processes_per_node: '1'
  applications:
    gromacs:
      workloads:
        water_bare:
          experiments:
            test1:
              variables:
                gromacs_path: '/test/path'
                n_nodes: '1'
            test2:
              variables:
                n_nodes: '2'
  software:
    packages:
      gromacs:
        pkg_spec: gromacs
      intel-mpi:
        pkg_spec: intel-oneapi-mpi@2021.11.0
    environments:
      gromacs:
        packages:
        - gromacs
        - intel-mpi
"""
    ws = ramble.workspace.create(workspace_name)
    ws.write()

    config_path = os.path.join(ws.config_dir, ramble.workspace.CONFIG_FILE_NAME)

    with open(config_path, "w+", encoding="utf-8") as f:
        f.write(test_config)

    ws._re_read()

    workspace(
        "setup",
        "--dry-run",
        global_args=["-w", workspace_name],
    )

    # test1 should attempt to invoke `spack location -i` on dep packages.
    # However this will not be cached in practice.
    test1_log = os.path.join(ws.log_dir, "setup.latest", "gromacs.water_bare.test1.out")
    gromacs_log_line = _spack_loc_log_line("gromacs")
    impi_log_line = _spack_loc_log_line("intel-oneapi-mpi@2021.11.0")
    with open(test1_log, encoding="utf-8") as f:
        content = f.read()
        assert "Executing phase define_package_paths" in content
        assert content.count(gromacs_log_line) == 1
        assert content.count(impi_log_line) == 1

    # test2 should not use a path, as test1 has a variable for the path defined
    test2_log = os.path.join(ws.log_dir, "setup.latest", "gromacs.water_bare.test2.out")
    with open(test2_log, encoding="utf-8") as f:
        content = f.read()
        assert "Executing phase define_package_paths" in content
        assert gromacs_log_line in content
        assert impi_log_line not in content


def test_pkg_path_disk_cache(mock_applications, workspace_name):
    ws = ramble.workspace.create(workspace_name)
    ws.write()
    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "experiments",
        "zlib",
        "-V",
        "package_manager=spack",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )

    mock_runner = MockSpackRunner()
    calls = []

    def mock_get_pkg_path(spec):
        calls.append(spec)
        return "zlib", f"/path/to/zlib_{len(calls)}"

    mock_runner.get_package_path = mock_get_pkg_path
    exec_script = os.path.join(
        ws.experiment_dir,
        "zlib",
        "ensure_installed",
        "generated",
        "execute_experiment",
    )

    with patch.object(spack_lightweight, "SpackRunner", return_value=mock_runner):
        workspace("concretize", global_args=global_args)

        # 1. --dry-run does not create cache file on disk
        workspace("setup", "--dry-run", global_args=global_args)
        cache_file = os.path.join(mock_runner.env_path, "ramble_spack_pkg_path_cache.json")
        assert not os.path.exists(cache_file)

        # 2. First setup resolves paths and writes JSON cache
        calls.clear()
        workspace("setup", global_args=global_args)
        assert len(calls) == 1
        assert os.path.isfile(cache_file)
        with open(exec_script, encoding="utf-8") as f:
            assert "/path/to/zlib_1/lib" in f.read()

        # 3. Second setup hits on-disk JSON cache without calling get_package_path
        workspace("setup", global_args=global_args)
        assert len(calls) == 1
        with open(exec_script, encoding="utf-8") as f:
            assert "/path/to/zlib_1/lib" in f.read()

        # 4. Env file content (hash) change invalidates and regenerates cache
        spack_lock = os.path.join(mock_runner.env_path, "spack.lock")
        orig_mtime = os.path.getmtime(spack_lock)
        with open(spack_lock, "w", encoding="utf-8") as f:
            f.write('{"roots": [{"spec":"zlib@1.3"}]}')
        os.utime(spack_lock, (orig_mtime, orig_mtime))

        workspace("setup", global_args=global_args)
        assert len(calls) == 2
        with open(exec_script, encoding="utf-8") as f:
            assert "/path/to/zlib_2/lib" in f.read()

        # 5. Env file timestamp change invalidates and regenerates cache
        future_mtime = os.path.getmtime(cache_file) + 10
        os.utime(spack_lock, (future_mtime, future_mtime))

        workspace("setup", global_args=global_args)
        assert len(calls) == 3
        with open(exec_script, encoding="utf-8") as f:
            assert "/path/to/zlib_3/lib" in f.read()
