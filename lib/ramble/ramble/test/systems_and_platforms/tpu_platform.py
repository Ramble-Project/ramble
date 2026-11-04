# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.expander
import ramble.repository


@pytest.fixture
def tpu_platform_cls():
    return ramble.repository.paths[ramble.repository.ObjectTypes.base_platforms].get_obj_class(
        "tpu-platform"
    )


def test_tpu_platform_invariants(tpu_platform_cls):
    """Test TPU platform invariants and default variables."""
    inst = tpu_platform_cls("/mock/path")
    assert inst.name == "tpu-platform"

    vars_dict = {
        var.name: var.default for var_list in inst.object_variables.values() for var in var_list
    }
    assert vars_dict["processes_per_node"] == "1"
    assert vars_dict["tpu_device_path"] == "/dev/vfio"
    assert vars_dict["k8s_tpu_resource"] == "google.com/tpu"
    assert "gke_tpu_accelerator" in vars_dict
    expected_init_args = (
        "--xla_tpu_use_enhanced_launch_barrier=false "
        "--megascale_error_reporter_abort_on_hang=true"
    )
    assert vars_dict["node_local_libtpu_init_args"] == expected_init_args
    assert vars_dict["chips_per_node"] == "4"
    assert vars_dict["cores_per_chip"] == "1"
    assert vars_dict["hbm_per_device_gb"] == "32"
    assert vars_dict["tpu_topology"] == "2x2x1"


def test_tpu_platform_hbm_end_elements_formula():
    """Test HBM end_elements formula expansion across TPU platform HBM capacities."""
    formula = "{1 << int(floor(log2({hbm_per_device_gb} * (1024 ** 3) * 0.20 / 4)))}"
    expected_by_hbm_gb = {
        "16": "536870912",  # v5e (2^29)
        "32": "1073741824",  # v4, v6e (2^30)
        "95": "4294967296",  # v5p (2^32)
        "192": "8589934592",  # v7x (2^33)
    }
    for hbm_gb, expected in expected_by_hbm_gb.items():
        expander = ramble.expander.Expander({"hbm_per_device_gb": hbm_gb}, None)
        assert expander.expand_var(formula) == expected


def test_tpu_platform_processes_per_node_validator(tpu_platform_cls):
    """Test validator enforcing processes_per_node == 1."""
    inst = tpu_platform_cls("/mock/path")
    assert frozenset(["+validate_platform"]) in inst.validators
    validators = {name: val for v_dict in inst.validators.values() for name, val in v_dict.items()}
    assert "processes_per_node_tpu_platform_validation" in validators
    val_def = validators["processes_per_node_tpu_platform_validation"]
    predicate = val_def["predicate"]

    # When processes_per_node is 1, validation succeeds
    expander_valid = ramble.expander.Expander({"processes_per_node": "1"}, None)
    assert expander_valid.evaluate_predicate(predicate) is True

    # When processes_per_node is not 1, validation fails
    expander_invalid = ramble.expander.Expander({"processes_per_node": "2"}, None)
    assert expander_invalid.evaluate_predicate(predicate) is False

    expander_invalid_many = ramble.expander.Expander({"processes_per_node": "4"}, None)
    assert expander_invalid_many.evaluate_predicate(predicate) is False
