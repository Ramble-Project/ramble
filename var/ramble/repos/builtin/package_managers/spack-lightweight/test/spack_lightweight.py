# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import sys
from unittest.mock import patch

import pytest

import ramble.workspace
from ramble.main import RambleCommand
from ramble.pkg_man.builtin import spack_lightweight
from ramble.test.mock_spack_runner import MockSpackRunner

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)

config = RambleCommand("config")
workspace = RambleCommand("workspace")


def test_container_push_cache_script(request):
    ws_name = request.node.name
    ws = ramble.workspace.create(ws_name)
    global_args = ["-w", ws_name]
    workspace(
        "manage",
        "experiments",
        "hostname",
        "-p",
        "spack-lightweight",
        "--wf",
        "local",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "container_registry_name=my-oci",
        "-v",
        "container_base_image=base-linux",
        "-v",
        "container_image_tag=my-tag",
        global_args=global_args,
    )
    ws._re_read()
    workspace("setup", global_args=["-w", ws_name])
    script_path = os.path.join(
        ws.experiment_dir,
        "hostname",
        "local",
        "generated",
        "push_container_image.sh",
    )
    # By default, the push script does not get generated
    assert not os.path.exists(script_path)
    with ramble.config.override(
        "config:spack:", {"buildcache": {"flags": "--private"}}
    ):
        config(
            "add",
            "variants:spack_push_container_image_script:true",
            global_args=global_args,
        )
        workspace("setup", global_args=["-w", ws_name])
    assert os.path.exists(script_path)
    with open(script_path, encoding="utf-8") as f:
        script = f.read()
        assert "spack/setup-env.sh" in script
        assert "spack env activate" in script
        assert "spack buildcache push" in script
        assert '--base-image "base-linux"' in script
        assert '--tag "my-tag" --private' in script


def test_spack_auxiliary_files(request):
    ws_name = request.node.name
    ws = ramble.workspace.create(ws_name)
    global_args = ["-w", ws_name]
    workspace(
        "manage",
        "experiments",
        "gromacs",
        "-p",
        "spack-lightweight",
        "--wf",
        "water_bare",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "opt_target=x86_64",
        global_args=global_args,
    )

    os.makedirs(ws.auxiliary_software_dir)
    with open(
        os.path.join(ws.auxiliary_software_dir, "packages.yaml"),
        "w+",
        encoding="utf-8",
    ) as f:
        f.write("""packages:
  all:
    target: ['{opt_target}']""")

    ws._re_read()

    workspace("concretize", global_args=["-w", ws_name])

    workspace("setup", "--dry-run", global_args=["-w", ws_name])
    spack_config = os.path.join(
        __import__("glob").glob(
            os.path.join(ws.software_dir, "spack-lightweight*")
        )[0],
        "gromacs",
        "spack.yaml",
    )

    with open(spack_config, encoding="utf-8") as f:
        data = f.read()
        assert "opt_target" not in data
        assert "x86_64" in data


def test_spack_push_to_cache(workspace_name, mock_applications):
    ws = ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "experiments",
        "zlib",
        "--wf",
        "ensure_installed",
        "-p",
        "spack",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "batch_submit={execute_experiment}",
        global_args=global_args,
    )

    # Add a compiler package
    if sys.platform == "darwin":
        compiler_spec = "apple-clang"
    else:
        compiler_spec = "gcc"
    workspace(
        "manage",
        "software",
        "--pkg",
        "comp",
        "--spec",
        compiler_spec,
        global_args=global_args,
    )

    # Add zlib package
    workspace(
        "manage",
        "software",
        "--pkg",
        "zlib",
        "--spec",
        "zlib",
        "--compiler",
        "comp",
        global_args=global_args,
    )

    # Define zlib environment
    workspace(
        "manage",
        "software",
        "--env",
        "zlib",
        "--environment-packages",
        "zlib",
        global_args=global_args,
    )

    with patch.object(
        spack_lightweight, "SpackRunner", return_value=MockSpackRunner()
    ):
        workspace(
            "setup",
            "--phases",
            "software_create_env",
            "software_configure",
            global_args=global_args,
        )

        cache_path = os.path.join(ws.root, "test_cache")

        workspace(
            "push-to-cache",
            "-d",
            cache_path,
            "--dry-run",
            global_args=global_args,
        )
