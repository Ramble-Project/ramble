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

import ramble.workspace
from ramble.main import RambleCommand

pytestmark = pytest.mark.usefixtures(
    "mutable_config", "mutable_mock_workspace_path", "mutable_mock_apps_repo"
)

workspace = RambleCommand("workspace")


def test_registered_builtin_order(workspace_name):
    ws = ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "experiments",
        "register-builtin",
        "--wf",
        "test_wl2",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "mpi_command='mpirun -n {n_ranks}'",
        "-V",
        "package_manager=spack",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )

    workspace(
        "manage",
        "software",
        "--pkg",
        "zlib",
        "--spec",
        "zlib",
        global_args=global_args,
    )

    workspace(
        "manage",
        "software",
        "--env",
        "register-builtin",
        "--environment-packages",
        "zlib",
        global_args=global_args,
    )

    workspace("setup", "--dry-run", global_args=global_args)

    regex_order = [
        re.compile(r'echo "bar"'),
        re.compile(r'echo "foo"'),
        re.compile(r"\. .*spack.*setup-env.sh"),
        re.compile(r"spack env activate"),
        re.compile(r"mpirun.*baz"),
        re.compile(r'echo "dep-before-post-builtin"'),
        re.compile(r'echo "post-builtin"'),
        re.compile(r'echo "dep-after-post-builtin"'),
    ]

    found_order = [False for _ in regex_order]

    found_idx = 0

    rendered_script = os.path.join(
        ws.experiment_dir, "register-builtin", "test_wl2", "generated", "execute_experiment"
    )

    with open(rendered_script, encoding="utf-8") as f:
        for line in f:
            print(f"Line = '{line}'")
            cur_regex = regex_order[found_idx]
            if cur_regex.search(line):
                print(f"  -- Found! Moving to idx: {found_idx + 1}")
                found_order[found_idx] = True
                found_idx += 1

    assert all(found_order)
    assert found_idx == len(found_order)
