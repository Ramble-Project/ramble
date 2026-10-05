# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.workspace
from ramble.main import RambleCommand

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)

config = RambleCommand("config")
workspace = RambleCommand("workspace")


def test_spack_pip_multi_prefix(request, mock_applications):
    ws_name = request.node.name
    ws = ramble.workspace.create(ws_name)
    global_args = ["-w", ws_name]
    workspace(
        "manage",
        "experiments",
        "multi-package-manager-specs",
        "-V",
        "package_manager=spack-pip",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        global_args=global_args,
    )
    ws._re_read()
    workspace("concretize", global_args=global_args)
    with open(ws.config_file_path, encoding="utf-8") as f:
        data = f.read()
        assert "spack_pkg_spec: zlib" in data
        assert "pip_pkg_spec: requests" in data

    workspace("setup", "--dry-run", global_args=global_args)

    workspace("analyze", global_args=global_args)

    with open(
        os.path.join(ws.root, "results.latest.txt"), encoding="utf-8"
    ) as f:
        data = f.read()
        assert "SUCCESS" in data
        assert "FAILED" not in data


def test_spack_pip_ignores_unprefixed_spec(request, mock_applications):
    ws_name = request.node.name
    ws = ramble.workspace.create(ws_name)
    global_args = ["-w", ws_name]
    workspace(
        "manage",
        "experiments",
        "multi-package-manager-specs",
        "-V",
        "package_manager=spack-pip",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        global_args=global_args,
    )

    workspace(
        "manage",
        "software",
        "--pkg",
        "zlib",
        "--prefix",
        "spack",
        "--spec",
        "zlib",
        global_args=global_args,
    )

    workspace(
        "manage",
        "software",
        "--pkg",
        "requests",
        "--prefix",
        "pip",
        "--spec",
        "requests",
        global_args=global_args,
    )

    workspace(
        "manage",
        "software",
        "--pkg",
        "gcc",
        "--spec",
        "gcc",
        global_args=global_args,
    )

    workspace(
        "manage",
        "software",
        "--env",
        "multi-package-manager-specs",
        "--environment-packages",
        "zlib,requests,gcc",
        global_args=global_args,
    )

    ws._re_read()
    with open(ws.config_file_path, encoding="utf-8") as f:
        data = f.read()
        assert "spack_pkg_spec: zlib" in data
        assert "pip_pkg_spec: requests" in data
        assert "pkg_spec: gcc" in data

    workspace("setup", "--dry-run", global_args=global_args)

    env_path = os.path.join(
        ws.software_dir, "spack-pip", "multi-package-manager-specs"
    )
    with open(os.path.join(env_path, "spack.yaml"), encoding="utf-8") as f:
        data = f.read()
        assert "zlib" in data
        assert "requests" not in data
        assert "gcc" not in data

    with open(
        os.path.join(env_path, "requirements.txt"), encoding="utf-8"
    ) as f:
        data = f.read()
        assert "zlib" not in data
        assert "requests" in data
        assert "gcc" not in data

    workspace("analyze", global_args=global_args)

    with open(
        os.path.join(ws.root, "results.latest.txt"), encoding="utf-8"
    ) as f:
        data = f.read()
        assert "SUCCESS" in data
        assert "FAILED" not in data
