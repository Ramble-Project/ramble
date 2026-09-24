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
from ramble.util import json_util

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
    "mutable_mock_apps_repo",
    "workspace_deactivate",
)

workspace = RambleCommand("workspace")
on = RambleCommand("on")


@pytest.mark.maybeslow
def test_analyze_with_fom_filter(workspace_name):
    global_args = ["-w", workspace_name]
    ws1 = ramble.workspace.create(workspace_name)
    ws1.write()

    workspace(
        "manage",
        "experiments",
        "fom-log-path",
        "--wf",
        "test",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "batch_submit=bash",
        "-v",
        "mpi_command=",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    ws1._re_read()

    workspace("setup", global_args=global_args)
    on(global_args=global_args)

    out = workspace("analyze", "--where", "{n_nodes} == 1", global_args=global_args)
    assert "fom-log-path.test.test_experiment" in out

    out = workspace(
        "analyze",
        "--where",
        "{n_nodes} == 2",
        global_args=["-w", workspace_name],
        fail_on_error=False,
    )
    assert "No experiment left for analysis after filtering." in out


@pytest.mark.maybeslow
def test_workspace_analyze_results_cache(workspace_name):
    global_args = ["-w", workspace_name]
    ws = ramble.workspace.create(workspace_name)
    ws.write()

    workspace(
        "manage",
        "experiments",
        "fom-log-path",
        "--wf",
        "test",
        "-e",
        "test_experiment",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "batch_submit={execute_experiment}",
        "-v",
        "mpi_command=",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    ws._re_read()

    workspace("setup", global_args=global_args)
    on(global_args=global_args)

    exp_dir = os.path.join(ws.experiment_dir, "fom-log-path", "test", "test_experiment")
    cache_file = os.path.join(exp_dir, "ramble_results_cache.json")
    log_file = os.path.join(exp_dir, "log.file")
    results_json = os.path.join(ws.results_dir, "results.latest.json")

    # Before analyze, cache file should not exist
    assert not os.path.exists(cache_file)

    # First analyze: creates cache
    workspace("analyze", "-f", "json", global_args=global_args)
    assert os.path.exists(cache_file)

    with open(results_json, encoding="utf-8") as f:
        res1 = json_util.load(f)

    assert res1["experiments"][0]["EXPERIMENT_STATUS"] == "SUCCESS"
    assert res1["experiments"][0]["RAMBLE_STATUS"] == "SUCCESS"
    assert res1["experiments"][0]["CONTEXTS"][0]["foms"][0]["name"] == "test_fom"
    assert res1["experiments"][0]["CONTEXTS"][0]["foms"][0]["value"] == "test"

    # Second analyze: should read from cache
    workspace("analyze", "-f", "json", global_args=global_args)

    with open(results_json, encoding="utf-8") as f:
        res2 = json_util.load(f)

    assert res1 == res2

    # Check analyze log indicates reading from cache
    exp_log = os.path.join(ws.log_dir, "analyze.latest", "fom-log-path.test.test_experiment.out")
    with open(exp_log, encoding="utf-8") as f:
        log_content = f.read()
    assert "Reading experiment results from cache file" in log_content

    # Invalidate cache by modifying log file with newer timestamp
    cache_mtime = os.path.getmtime(cache_file)
    os.utime(cache_file, (cache_mtime - 2, cache_mtime - 2))
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("fom: test_updated\n")

    workspace("analyze", "-f", "json", global_args=global_args)

    with open(results_json, encoding="utf-8") as f:
        res3 = json_util.load(f)

    assert res3["experiments"][0]["EXPERIMENT_STATUS"] == "SUCCESS"
    assert res3["experiments"][0]["CONTEXTS"][0]["foms"][0]["value"] == "test_updated"

    with open(exp_log, encoding="utf-8") as f:
        log_content = f.read()
    assert "Invalidating experiment results cache: timestamp difference" in log_content

    # Cache hit should still work even if source log file is removed
    os.remove(log_file)
    assert not os.path.exists(log_file)
    workspace("analyze", "-f", "json", global_args=global_args)

    with open(results_json, encoding="utf-8") as f:
        res4 = json_util.load(f)
    assert res4["experiments"][0]["EXPERIMENT_STATUS"] == "SUCCESS"
    assert res4["experiments"][0]["CONTEXTS"][0]["foms"][0]["value"] == "test_updated"

    # Invalidate cache by removing cache file; since log_file is missing, FOM cannot be extracted
    os.remove(cache_file)
    assert not os.path.exists(cache_file)

    workspace("analyze", "-f", "json", global_args=global_args)
    assert os.path.exists(cache_file)

    with open(results_json, encoding="utf-8") as f:
        res5 = json_util.load(f)
    # Success criteria should fail because log.file is missing
    assert res5["experiments"][0]["EXPERIMENT_STATUS"] == "FAILED"

    # Recreate log file with new FOM (simulate older cache)
    cache_mtime = os.path.getmtime(cache_file)
    os.utime(cache_file, (cache_mtime - 2, cache_mtime - 2))
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("fom: test_restored\n")

    workspace("analyze", "-f", "json", global_args=global_args)
    with open(results_json, encoding="utf-8") as f:
        res6 = json_util.load(f)
    assert res6["experiments"][0]["EXPERIMENT_STATUS"] == "SUCCESS"
    assert res6["experiments"][0]["CONTEXTS"][0]["foms"][0]["value"] == "test_restored"

    # Invalidate cache by changing experiment hash
    with open(cache_file, encoding="utf-8") as f:
        cache_data = json_util.load(f)
    cache_data["experiment_hash"] = "stale_hash"
    with open(cache_file, "w", encoding="utf-8") as f:
        json_util.dump(cache_data, f)

    workspace("analyze", "-f", "json", global_args=global_args)
    with open(exp_log, encoding="utf-8") as f:
        log_content = f.read()
    assert "Invalidating experiment results cache: experiment hash difference" in log_content
