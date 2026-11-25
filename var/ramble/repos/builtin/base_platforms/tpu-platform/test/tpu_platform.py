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
    return ramble.repository.paths[
        ramble.repository.ObjectTypes.base_platforms
    ].get_obj_class("tpu-platform")


def test_tpu_platform_gke_when_scoping(tpu_platform_cls):
    """Test GKE variables are scoped to workflow_manager=gke-mpi."""
    inst = tpu_platform_cls("/mock/path")
    unconditional = {
        var.name for var in inst.object_variables.get(frozenset(), [])
    }
    gke_key = frozenset(["workflow_manager=gke-mpi"])
    assert gke_key in inst.object_variables
    gke_vars = {var.name for var in inst.object_variables[gke_key]}

    for var_name in ("k8s_tpu_resource", "gke_tpu_accelerator"):
        assert var_name in gke_vars
        assert var_name not in unconditional


def test_tpu_platform_derived_variables(tpu_platform_cls):
    """Test derived TPU platform variable expressions expand properly."""
    inst = tpu_platform_cls("/mock/path")
    defaults = {
        var.name: var.default for var in inst.object_variables[frozenset()]
    }

    vars_map = {
        **defaults,
        "n_nodes": "2",
        "chips_per_node": "4",
        "cores_per_chip": "2",
        "tpu_device_path": "/dev/accel",
        "tpu_topology": "2x2x2",
    }
    expander = ramble.expander.Expander(vars_map, None)

    assert expander.expand_var_name("max_accelerators_per_node") == "8"
    assert expander.expand_var_name("accelerators_per_node") == "8"
    assert expander.expand_var_name("ici_size") == "16"
    assert (
        expander.expand_var_name("container_mounts") == "/dev/accel:/dev/accel"
    )
    assert expander.expand_var_name("tpu_mesh_shape") == "2x2x2"


def test_tpu_platform_processes_per_node_validator(tpu_platform_cls):
    """Test validator enforcing processes_per_node == 1."""
    inst = tpu_platform_cls("/mock/path")
    assert frozenset(["+validate_platform"]) in inst.validators
    validators = {
        name: val
        for v_dict in inst.validators.values()
        for name, val in v_dict.items()
    }
    assert "processes_per_node_tpu_platform_validation" in validators
    val_def = validators["processes_per_node_tpu_platform_validation"]
    predicate = val_def["predicate"]

    # When processes_per_node is 1, validation succeeds
    expander_valid = ramble.expander.Expander(
        {"processes_per_node": "1"}, None
    )
    assert expander_valid.evaluate_predicate(predicate) is True

    # When processes_per_node is not 1, validation fails
    expander_invalid = ramble.expander.Expander(
        {"processes_per_node": "2"}, None
    )
    assert expander_invalid.evaluate_predicate(predicate) is False

    expander_invalid_many = ramble.expander.Expander(
        {"processes_per_node": "4"}, None
    )
    assert expander_invalid_many.evaluate_predicate(predicate) is False
