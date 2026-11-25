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

import ramble.repository
from ramble.main import RambleCommand

workspace = RambleCommand("workspace")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)


@pytest.fixture
def tpu_error_mod_cls():
    return ramble.repository.paths[
        ramble.repository.ObjectTypes.modifiers
    ].get_obj_class("tpu-error-detector")


def _get_fom_regex(cls, fom_name):
    for when_dict in cls.figures_of_merit.values():
        for ctx_dict in when_dict.values():
            if fom_name in ctx_dict:
                return ctx_dict[fom_name]["regex"]
    raise KeyError(f"FOM {fom_name} not found")


def test_tpu_error_detector_oom(tpu_error_mod_cls):
    """Test detection of TPU OOM errors."""
    fom_regex = _get_fom_regex(tpu_error_mod_cls, "TPU OOM Error Detected")
    pattern = re.compile(fom_regex)

    line1 = (
        "jaxlib.xla_extension.XlaRuntimeError: "
        "RESOURCE_EXHAUSTED: Out of memory"
    )
    assert pattern.search(line1) is not None

    line2 = "ResourceExhaustedError: failed to allocate 16GB"
    assert pattern.search(line2) is not None

    clean_line = "Step 1 completed successfully"
    assert pattern.search(clean_line) is None


def test_tpu_error_detector_host_memory(tpu_error_mod_cls):
    """Test detection of host memory / OOM-killer errors."""
    fom_regex = _get_fom_regex(tpu_error_mod_cls, "Host Memory Error Detected")
    pattern = re.compile(fom_regex)

    for sample in (
        "MemoryError: Unable to allocate 64.0 GiB for an array",
        "Out of memory: Killed process 12345 (python3) by OOM-killer",
        "srun: error: node0: task 0: Killed",
    ):
        assert pattern.search(sample) is not None, f"Failed to match: {sample}"


def test_tpu_error_detector_hardware(tpu_error_mod_cls):
    """Test detection of TPU hardware and driver errors."""
    fom_regex = _get_fom_regex(
        tpu_error_mod_cls,
        "TPU Hardware / Driver / Network Error Detected",
    )
    pattern = re.compile(fom_regex)

    samples = [
        "FATAL: TPU device reset occurred on node 0",
        "RuntimeError: Failed to initialize PJRT client: PermissionError: /dev/vfio/0",
        "PermissionError: /dev/accel/0",
        "ICI link failure detected on link 2",
        "Collective operation timed out after 600s",
        "SDC (Bit flips) Detected during matmul",
        "libtpu not found in python environment",
    ]
    for sample in samples:
        assert pattern.search(sample) is not None, f"Failed to match: {sample}"


def test_tpu_error_detector_compilation(tpu_error_mod_cls):
    """Test detection of TPU/XLA compilation errors."""
    fom_regex = _get_fom_regex(
        tpu_error_mod_cls, "TPU/XLA Compilation Error Detected"
    )
    pattern = re.compile(fom_regex)

    sample = "XlaRuntimeError: Mesh geometry does not match physical devices"
    assert pattern.search(sample) is not None


def test_tpu_error_detector_profiler_env_benchmark(tpu_error_mod_cls):
    """Test profiler, environment/configuration, and benchmark failure FOMs."""
    prof_regex = _get_fom_regex(tpu_error_mod_cls, "Profiler Error Detected")
    assert re.search(prof_regex, "Failed to start profiler: permission error")

    env_regex = _get_fom_regex(
        tpu_error_mod_cls,
        "TPU Environment / Configuration Error Detected",
    )
    assert re.search(env_regex, "bash: python3: command not found")

    bench_regex = _get_fom_regex(
        tpu_error_mod_cls, "TPU Benchmark Failure Detected"
    )
    assert re.search(bench_regex, "ERROR: Benchmark func failed during run")


def test_tpu_error_detector_workspace_analyze(make_workspace_from_config):
    """Test tpu-error-detector FOM extraction during workspace analysis."""
    ws, ws_name = make_workspace_from_config()
    global_args = ["-w", ws_name]

    workspace(
        "manage",
        "experiments",
        "hostname",
        "--wf",
        "local",
        "-e",
        "test_error",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        global_args=global_args,
    )
    workspace(
        "manage",
        "modifiers",
        "--add",
        "-n",
        "tpu-error-detector",
        global_args=global_args,
    )
    workspace("setup", "--dry-run", global_args=global_args)

    run_dir = os.path.join(
        ws.experiment_dir, "hostname", "local", "test_error"
    )
    with open(
        os.path.join(run_dir, "test_error.out"), "w", encoding="utf-8"
    ) as f:
        f.write(
            "node0.local\n"
            "ResourceExhaustedError: Out of memory allocating 32GB on TPU_0\n"
            "MemoryError: Unable to allocate host buffer\n"
            "RuntimeError: Failed to initialize PJRT client\n"
        )

    workspace("analyze", global_args=global_args)
    with open(
        os.path.join(ws.results_dir, "results.latest.txt"), encoding="utf-8"
    ) as f:
        results = f.read()
        assert (
            "TPU OOM Error Detected = ResourceExhaustedError: Out of memory"
            in results
        )
        assert (
            "Host Memory Error Detected = "
            "MemoryError: Unable to allocate host buffer"
        ) in results
        assert (
            "TPU Hardware / Driver / Network Error Detected = "
            "RuntimeError: Failed to initialize PJRT client"
        ) in results
