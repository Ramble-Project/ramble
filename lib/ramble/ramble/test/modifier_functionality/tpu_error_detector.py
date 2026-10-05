# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import re

import pytest

import ramble.repository


@pytest.fixture
def tpu_error_mod_cls():
    return ramble.repository.paths[ramble.repository.ObjectTypes.modifiers].get_obj_class(
        "tpu-error-detector"
    )


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

    line1 = "jaxlib.xla_extension.XlaRuntimeError: RESOURCE_EXHAUSTED: Out of memory"
    assert pattern.search(line1) is not None

    line2 = "ResourceExhaustedError: failed to allocate 16GB"
    assert pattern.search(line2) is not None

    clean_line = "Step 1 completed successfully"
    assert pattern.search(clean_line) is None


def test_tpu_error_detector_hardware(tpu_error_mod_cls):
    """Test detection of TPU hardware and driver errors."""
    fom_regex = _get_fom_regex(tpu_error_mod_cls, "TPU Hardware / Driver / Network Error Detected")
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
    fom_regex = _get_fom_regex(tpu_error_mod_cls, "TPU/XLA Compilation Error Detected")
    pattern = re.compile(fom_regex)

    sample = "XlaRuntimeError: Mesh geometry does not match physical devices"
    assert pattern.search(sample) is not None
