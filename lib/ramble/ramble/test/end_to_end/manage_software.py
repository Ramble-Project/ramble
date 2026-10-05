# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.workspace
from ramble.main import RambleCommand

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


def test_manage_software(mutable_config, mutable_mock_workspace_path, workspace_name):
    with ramble.workspace.create(workspace_name) as ws1:
        ws1.write()

        config_path = ws1.config_file_path

        workspace(
            "manage",
            "experiments",
            "wrf",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=["-w", workspace_name],
        )
        workspace("concretize", global_args=["-w", workspace_name])

        ws1._re_read()

        with open(config_path, encoding="utf-8") as f:
            content = f.read()
            # Check that wrf has a package, and the package is in an environment
            assert "pkg_spec: wrf" in content
            assert "- wrfv4-{application::wrf::version}" in content

            # Check that intel-mpi was defined
            assert "pkg_spec: intel-oneapi-mpi" in content

            # Check that gcc was defined
            assert "gcc@14.2.0" in content

            # Check that the (soon to be new) definition of gcc is not defined
            assert "gcc@14.3.0" not in content

        # Change the GCC package definition
        workspace(
            "manage",
            "software",
            "--pkg",
            "gcc14",
            "--overwrite",
            "--package-spec",
            "gcc@14.3.0",
            global_args=["-w", workspace_name],
        )

        with open(config_path, encoding="utf-8") as f:
            content = f.read()
            assert "gcc@14.3.0" in content

        # Delete configs for wrf
        workspace(
            "manage",
            "software",
            "--remove",
            "--env",
            "wrf",
            "--pkg",
            "wrfv4-{application::wrf::version}",
            global_args=["-w", workspace_name],
        )
        workspace(
            "manage",
            "software",
            "--remove",
            "--pkg",
            "intel-mpi",
            global_args=["-w", workspace_name],
        )
        workspace(
            "manage", "software", "--remove", "--pkg", "gcc14", global_args=["-w", workspace_name]
        )
        workspace(
            "manage",
            "software",
            "--env",
            "foo",
            "--environment-packages",
            "bar,baz",
            global_args=["-w", workspace_name],
        )

        with open(config_path, encoding="utf-8") as f:
            content = f.read()

            # Check that new env definitions are found
            assert "foo" in content
            assert "bar" in content
            assert "baz" in content

            # Check that removed definitions no longer exist
            assert "intel-mpi" not in content
            assert "gcc" not in content
            assert "- wrf" not in content
