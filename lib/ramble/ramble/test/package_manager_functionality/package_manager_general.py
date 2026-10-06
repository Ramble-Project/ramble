# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.software_info
import ramble.workspace
from ramble.main import RambleCommand, RambleCommandError

workspace = RambleCommand("workspace")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)


@pytest.mark.maybeslow
@pytest.mark.parametrize(
    "pkgman_name,expect_success_setup",
    [
        ("none", True),
        (None, True),
        ("", True),
        ("spack", True),
        ("non-existent-pkgman", False),
    ],
)
def test_package_manager_names(pkgman_name, expect_success_setup):
    ws_name = f"test-{pkgman_name}"
    ws = ramble.workspace.create(ws_name)

    global_args = ["-w", ws_name]
    args = [
        "manage",
        "experiments",
        "hostname",
        "-V",
        f"package_manager={pkgman_name}",
        "--wf",
        "local",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "mpi_command=''",
        "-v",
        "batch_submit=''",
        "--default-variable-value",
        "1",
    ]

    ws._re_read()
    if expect_success_setup:
        workspace(*args, global_args=global_args)
        workspace("setup", "--dry-run", global_args=["-D", ws.root])
        assert os.path.isfile(os.path.join(ws.log_dir, "setup.latest.out"))
    else:
        with pytest.raises(RambleCommandError):
            workspace(*args, global_args=global_args)


def test_software_info_string():
    package = "zlib"
    version = "1.3.1"

    info = ramble.software_info.SoftwareInfo(name=package, version=version)
    text = info.to_version_text()
    assert package in text
    assert version in text
