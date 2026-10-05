# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.repository


@pytest.fixture
def tpu_platform_cls():
    return ramble.repository.paths[ramble.repository.ObjectTypes.base_platforms].get_obj_class(
        "tpu-platform"
    )


def test_tpu_platform_topology_math_trillium(tpu_platform_cls):
    """Test topology math for Trillium (v6e, cores_per_chip=1)."""
    # 2x2: single node (4 chips)
    res = tpu_platform_cls.topology_math("2x2", cores_per_chip=1)
    assert res["total_chips"] == 4
    assert res["ici_size"] == 4
    assert res["tpu_mesh_shape"] == "2x2"

    # 2x4: 2 nodes (8 chips)
    res = tpu_platform_cls.topology_math("2x4", cores_per_chip=1)
    assert res["total_chips"] == 8
    assert res["ici_size"] == 8
    assert res["tpu_mesh_shape"] == "4x2"

    # 4x4: 4 nodes (16 chips)
    res = tpu_platform_cls.topology_math("4x4", cores_per_chip=1)
    assert res["total_chips"] == 16
    assert res["ici_size"] == 16
    assert res["tpu_mesh_shape"] == "4x4"


def test_tpu_platform_topology_math_ironwood(tpu_platform_cls):
    """Test topology math for Ironwood (v7x, cores_per_chip=2)."""
    # 2x2x1: single node (4 chips, 8 tensor cores)
    res = tpu_platform_cls.topology_math("2x2x1", cores_per_chip=2)
    assert res["total_chips"] == 4
    assert res["ici_size"] == 8
    assert res["tpu_mesh_shape"] == "2x2x2"

    # 2x2x2: 2 nodes (8 chips, 16 tensor cores)
    res = tpu_platform_cls.topology_math("2x2x2", cores_per_chip=2)
    assert res["total_chips"] == 8
    assert res["ici_size"] == 16
    assert res["tpu_mesh_shape"] == "4x2x2"

    # 4x4x4: 16 nodes (64 chips, 128 tensor cores)
    res = tpu_platform_cls.topology_math("4x4x4", cores_per_chip=2)
    assert res["total_chips"] == 64
    assert res["ici_size"] == 128
    assert res["tpu_mesh_shape"] == "16x4x2"


def test_tpu_platform_topology_math_invalid(tpu_platform_cls):
    """Test invalid topology string raises ValueError."""
    with pytest.raises(ValueError, match="Invalid TPU topology"):
        tpu_platform_cls.topology_math("invalid_topology")


def test_tpu_platform_invariants(tpu_platform_cls):
    """Test TPU platform invariants and default variables."""
    inst = tpu_platform_cls("/mock/path")
    assert inst.name == "tpu-platform"

    vars_dict = {
        var.name: var.default for var_list in inst.object_variables.values() for var in var_list
    }
    assert vars_dict["processes_per_node"] == "1"
    assert vars_dict["tpu_device_path"] == "/dev/vfio"
    assert vars_dict["chips_per_node"] == "4"
    assert vars_dict["cores_per_chip"] == "1"
    assert vars_dict["tpu_topology"] == "2x2x1"


def test_tpu_platform_processes_per_node_validator(tpu_platform_cls):
    """Test validator enforcing processes_per_node == 1."""
    import ramble.expander

    inst = tpu_platform_cls("/mock/path")
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
