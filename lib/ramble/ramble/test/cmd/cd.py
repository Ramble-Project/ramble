# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import llnl.util.filesystem as fs

import ramble.paths
from ramble.error import RambleCommandError
from ramble.main import RambleCommand

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
    "mutable_mock_apps_repo",
    "workspace_deactivate",
)

cd = RambleCommand("cd")
workspace = RambleCommand("workspace")


def test_cd_without_shell_wrapper_prints_instructions():
    with pytest.raises(RambleCommandError) as exc_info:
        cd()
    msg = str(exc_info.value)
    assert "To set up shell support" in msg
    assert "cd `ramble location --first --existing ...`" in msg


def test_cd_requires_existing_paths_and_picks_first_match(
    make_workspace_from_config, tmpdir, monkeypatch
):
    monkeypatch.setenv("_RAMBLE_CD_WRAPPER", "1")

    uncreated_user = os.path.abspath(str(tmpdir.join("uncreated_user_ramble")))
    monkeypatch.setattr(ramble.paths, "user_config_path", uncreated_user)
    with pytest.raises(RambleCommandError, match="does not exist"):
        cd("--user-config")

    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks}'
    batch_submit: '{execute_experiment}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            scale_1:
              variables:
                n_ranks: '1'
                n_nodes: '1'
            scale_2:
              variables:
                n_ranks: '2'
                n_nodes: '2'
    tagged-1:
      workloads:
        test_wl:
          experiments:
            exp_b:
              variables:
                n_ranks: '1'
                n_nodes: '1'
"""
    ws, _ = make_workspace_from_config(test_config, activate=True)
    exp2_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl", "scale_2"))
    basic_wl_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl"))

    with pytest.raises(RambleCommandError, match="does not exist"):
        cd("results")

    with pytest.raises(RambleCommandError, match="ramble workspace setup"):
        cd("scale_1")

    # Partial setup: cd filters to existing directories before selecting the first match
    fs.mkdirp(exp2_dir)
    assert cd("*scale*").strip() == exp2_dir

    workspace("setup", "--dry-run")

    # Missing subpath inside an already-setup experiment should not suggest workspace setup
    with pytest.raises(RambleCommandError) as exc_info:
        cd("scale_1/no_such_subdir")
    assert "does not exist" in str(exc_info.value)
    assert "ramble workspace setup" not in str(exc_info.value)

    # Multiple matches emit a navigation warning and resolve to the first match
    out_cd = cd("test_wl")
    assert "Matched 2 workloads" in out_cd
    assert out_cd.strip().splitlines()[-1] == basic_wl_dir
