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

pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


def test_package_manager_config_zlib(mock_applications, workspace_name):
    test_config = """
ramble:
  variants:
    package_manager: spack
  variables:
    mpi_command: ''
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '1'
    n_ranks: '1'
  applications:
    zlib-configs:
      workloads:
        ensure_installed:
          experiments:
            test:
              variables: {}
  software:
    packages:
      zlib:
        pkg_spec: 'zlib'
    environments:
      zlib-configs:
        packages:
        - zlib
"""

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        config_path = os.path.join(ws.config_dir, ramble.workspace.CONFIG_FILE_NAME)

        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(test_config)
        ws._re_read()

        workspace("setup", "--dry-run", global_args=["-w", workspace_name])

        spack_yaml = os.path.join(
            __import__("glob").glob(os.path.join(ws.software_dir, "spack*"))[0],
            "zlib-configs",
            "spack.yaml",
        )

        assert os.path.isfile(spack_yaml)

        with open(spack_yaml, encoding="utf-8") as f:
            data = f.read()
            assert "config:" in data
            assert "debug: true" in data
