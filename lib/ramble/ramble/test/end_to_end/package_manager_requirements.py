# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

from ramble.main import RambleCommand
from ramble.pkg_man.builtin.spack_lightweight import ValidationFailedError

pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


@pytest.mark.long
def test_package_manager_requirements_zlib(
    mock_applications,
    mock_modifiers,
    ensure_spack_runner,
    make_workspace_from_config,
):
    test_config = """
ramble:
  variants:
    package_manager: spack
  variables:
    mpi_command: ''
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '1'
    n_ranks: '1'
  modifiers:
  - name: spack-mod
  applications:
    zlib-configs:
      workloads:
        ensure_installed:
          experiments:
            test:
              variables: {}
  software:
    packages: {}
    environments:
      zlib-configs:
        packages: []
"""

    ws, ws_name = make_workspace_from_config(test_config)

    workspace("setup", global_args=["-w", ws_name])

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


def test_package_manager_requirements_error(
    mock_applications,
    mock_modifiers,
    ensure_spack_runner,
    make_workspace_from_config,
):
    test_config = """
ramble:
  variants:
    package_manager: spack
  variables:
    mpi_command: ''
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '1'
    n_ranks: '1'
  modifiers:
  - name: spack-failed-reqs
  applications:
    zlib-configs:
      workloads:
        ensure_installed:
          experiments:
            test:
              variables: {}
  software:
    packages: {}
    environments:
      zlib-configs:
        packages: []
"""

    ws, ws_name = make_workspace_from_config(test_config)

    with pytest.raises(
        ValidationFailedError, match='Validation of: "spack list not-a-package" failed'
    ):
        workspace("setup", global_args=["-w", ws_name])
