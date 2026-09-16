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

pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")


@pytest.mark.maybeslow
def test_spack_package_manager_provenance_zlib(mock_applications, workspace_name):
    ws = ramble.workspace.create(workspace_name)

    global_args = ["-w", workspace_name]

    pm = "spack"
    workspace(
        "manage",
        "experiments",
        "zlib",
        "-p",
        pm,
        "--default-variable-value",
        "1",
        global_args=global_args,
    )

    # FIXME: This is a good candidate for a fixure if other tests need this pattern
    # Write spack config to avoid doing a real install
    spack_config = f"""config:
      install_tree:
        root: {ws.root}/{{env_name}} # this path has a max length of 127
    """

    from llnl.util.filesystem import mkdirp

    aux_dir = os.path.join(ws.config_dir, ramble.workspace.AUXILIARY_SOFTWARE_DIR_NAME)
    mkdirp(aux_dir)

    with open(os.path.join(aux_dir, "config.yaml"), "w", encoding="utf-8") as f:
        f.write(spack_config)

    with patch.object(spack_lightweight, "SpackRunner", return_value=MockSpackRunner()):
        workspace("concretize", global_args=global_args)

        workspace("setup", global_args=global_args)

        spack_yaml = os.path.join(
            __import__("glob").glob(os.path.join(ws.software_dir, f"{pm}*"))[0],
            "zlib",
            "spack.yaml",
        )
        spack_lock = os.path.join(
            __import__("glob").glob(os.path.join(ws.software_dir, f"{pm}*"))[0],
            "zlib",
            "spack.lock",
        )

        assert os.path.isfile(spack_yaml)

        with open(spack_yaml, encoding="utf-8") as f:
            data = f.read()
            assert "- zlib" in data

        assert os.path.isfile(spack_lock)

        with open(spack_lock, encoding="utf-8") as f:
            data = f.read()
            assert '"spec":"zlib"' in data

        out_log = os.path.join(
            ws.experiment_dir, "zlib", "ensure_installed", "generated", "generated.out"
        )

        with open(out_log, "w+", encoding="utf-8") as f:
            f.write("libz.so.2\n")

        workspace("analyze", global_args=global_args)

        results_file = os.path.join(ws.results_dir, "results.latest.txt")
        assert os.path.isfile(results_file)

        with open(results_file, encoding="utf-8") as f:
            data = f.read()
            assert "Software definitions" in data
            assert "spack packages:" in data
            assert "zlib @" in data

        workspace("analyze", "-f", "json", global_args=global_args)

        results_file = os.path.join(ws.results_dir, "results.latest.json")
        assert os.path.isfile(results_file)

        with open(results_file, encoding="utf-8") as f:
            import json

            data = json.load(f)
            for d in data["experiments"]:
                pkg_list = d["SOFTWARE"]["spack"]
                names = [pkg["name"] for pkg in pkg_list]
                assert "SOFTWARE" in d
                assert "spack" in d["SOFTWARE"]
                assert "zlib" in names


def test_usermanged_package_manager_provenance_zlib(mock_applications, workspace_name):
    ws = ramble.workspace.create(workspace_name)

    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "experiments",
        "zlib",
        "-p",
        "user-managed",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )

    # Add Software
    workspace(
        "manage",
        "software",
        "--package-name",
        "zlib",
        "--package-spec",
        "zlib@1.3.1",
        global_args=global_args,
    )

    # Use software in env
    workspace(
        "manage",
        "software",
        "--environment-name",
        "zlib",
        "--environment-packages",
        "zlib",
        global_args=global_args,
    )

    workspace("setup", global_args=global_args)
    workspace("analyze", global_args=global_args)

    results_file = os.path.join(ws.results_dir, "results.latest.txt")

    assert os.path.isfile(results_file)

    with open(results_file, encoding="utf-8") as f:
        data = f.read()
        assert "Software definitions" in data
        assert "user-managed packages:" in data
        assert "zlib @1.3.1" in data
