# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import shutil
import tarfile

import pytest

import ramble.stage
import ramble.util.hashing
from ramble.main import RambleCommand

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)

workspace = RambleCommand("workspace")


def test_get_inputs_disk_cache(make_workspace_from_config, tmpdir, monkeypatch):
    """Verify get_inputs skips already-staged inputs across setup runs."""
    src_dir = tmpdir.mkdir("archive_src")
    src_file = src_dir.join("data.txt")
    src_file.write("payload")

    archive_path = str(tmpdir.join("deck.tar.gz"))
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(str(src_file), arcname="data.txt")

    raw_archive_path = str(tmpdir.join("raw_deck.tar.gz"))
    shutil.copyfile(archive_path, raw_archive_path)

    sha = ramble.util.hashing.hash_file(archive_path)

    test_config = f"""
ramble:
  config:
    bootstrap_utilities: false
  variables:
    mpi_command: ''
    batch_submit: '{{execute_experiment}}'
    processes_per_node: '1'
  applications:
    hostname:
      internals:
        custom_inputs:
          expanded_deck:
            url: file://{archive_path}
            sha256: {sha}
            expand: true
          raw_deck:
            url: file://{raw_archive_path}
            sha256: {sha}
            expand: false
            target_dir: '{{workload_input_dir}}/raw'
        custom_workloads:
          cached_wl:
            executables: [serial]
            inputs: [expanded_deck, raw_deck]
      workloads:
        cached_wl:
          experiments:
            exp_{{idx}}:
              variables:
                n_ranks: '1'
                idx: ['1', '2']
"""
    ws, ws_name = make_workspace_from_config(test_config)
    global_args = ["-w", ws_name]

    # 1. --dry-run does not create cache file on disk
    workspace("setup", "--phases", "get_inputs", "--dry-run", global_args=global_args)
    assert not os.path.exists(ws.input_cache_path)

    # 2. First setup stages both inputs and persists ramble_input_cache.json
    workspace("setup", "--phases", "get_inputs", global_args=global_args)
    assert os.path.isfile(ws.input_cache_path)
    staged_data = os.path.join(ws.input_dir, "hostname", "cached_wl", "deck", "data.txt")
    staged_raw = os.path.join(ws.input_dir, "hostname", "cached_wl", "raw", "raw_deck.tar.gz")
    assert os.path.isfile(staged_data)
    assert os.path.isfile(staged_raw)

    # 3. Second setup hits on-disk cache and skips InputStage.fetch completely
    fetch_calls = []
    orig_fetch = ramble.stage.InputStage.fetch

    def spy_fetch(self, *args, **kwargs):
        fetch_calls.append(self.name)
        return orig_fetch(self, *args, **kwargs)

    monkeypatch.setattr(ramble.stage.InputStage, "fetch", spy_fetch)

    workspace("setup", "--phases", "get_inputs", global_args=global_args)
    assert fetch_calls == []

    # 4. Removing the expanded input directory invalidates only that entry
    shutil.rmtree(os.path.dirname(staged_data))
    workspace("setup", "--phases", "get_inputs", global_args=global_args)
    assert len(fetch_calls) == 1
    assert os.path.isfile(staged_data)
