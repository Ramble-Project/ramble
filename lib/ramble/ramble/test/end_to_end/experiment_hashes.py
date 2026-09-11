# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import ramble.repository
import ramble.workspace
from ramble.main import RambleCommand
from ramble.util import json_util

ApplicationBase = ramble.repository.get_obj_class(
    "application-base", object_type=ramble.repository.ObjectTypes.base_classes
)


workspace = RambleCommand("workspace")


def test_experiment_hashes(mutable_config, mutable_mock_workspace_path, workspace_name):
    ws1 = ramble.workspace.create(workspace_name)

    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "experiments",
        "gromacs",
        "--wf",
        "water_bare",
        "-e",
        "unit_test",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "-V",
        "package_manager=spack",
        global_args=global_args,
    )

    workspace("concretize", global_args=global_args)
    workspace("setup", "--dry-run", global_args=global_args)

    experiment_inventory = os.path.join(
        ws1.experiment_dir,
        "gromacs",
        "water_bare",
        "unit_test",
        ApplicationBase._inventory_file_name,
    )

    workspace_inventory = os.path.join(ws1.root, ramble.workspace.Workspace.inventory_file_name)

    # Test experiment inventory
    assert os.path.isfile(experiment_inventory)
    with open(experiment_inventory, encoding="utf-8") as f:
        data = json_util.load(f)

    assert "object_configuration" in data
    assert data["object_configuration"] != []
    assert data["object_configuration"] is not None

    # Test Attributes
    expected_attrs = {"variables", "modifiers", "env_vars", "internals", "chained_experiments"}
    assert "attributes" in data
    for attr in data["attributes"]:
        if attr["name"] in expected_attrs:
            assert attr["digest"] != ""
            assert attr["digest"] is not None
            expected_attrs.remove(attr["name"])

    assert not expected_attrs

    # Test Templates
    expected_templates = {"execute_experiment"}
    assert "templates" in data
    for temp in data["templates"]:
        if temp["name"] in expected_templates:
            assert temp["digest"] != ""
            assert temp["digest"] is not None
            expected_templates.remove(temp["name"])

    assert not expected_templates

    # Test software environments
    import glob

    spack_dir = glob.glob(os.path.join(ws1.software_dir, "spack*"))[0]
    spack_dir_name = os.path.basename(spack_dir)
    expected_envs = {f"software/{spack_dir_name}/gromacs"}
    assert "software" in data
    for env in data["software"]:
        if env["name"] in expected_envs:
            assert env["digest"] != ""
            assert env["digest"] is not None
            expected_envs.remove(env["name"])

    assert not expected_envs

    # Test objects
    expected_objects = {}
    expected_objects["applications"] = {"gromacs"}
    expected_objects["workflow_managers"] = {"user-managed"}
    expected_objects["package_managers"] = {"spack", "spack-lightweight"}
    expected_objects["base_classes"] = {
        "executable-application",
        "application-base",
        "object-mixin",
    }
    for object_def in data["object_configuration"]:
        if "object_type" in object_def:
            obj_type = object_def["object_type"]
            if obj_type in expected_objects:
                if "name" in object_def and object_def["name"] in expected_objects[obj_type]:
                    expected_objects[obj_type].remove(object_def["name"])
                    assert object_def["digest"] != ""
                    assert object_def["digest"] is not None

    for obj_set in expected_objects.values():
        assert not obj_set

    # Test workspace inventory
    assert os.path.isfile(workspace_inventory)
    with open(workspace_inventory, encoding="utf-8") as f:
        data = json_util.load(f)

    # Test experiments
    expected_experiments = {"gromacs.water_bare.unit_test"}

    assert "experiments" in data
    for exp in data["experiments"]:
        if exp["name"] in expected_experiments:
            assert exp["digest"] != ""
            assert exp["digest"] is not None
            assert "contents" in exp
            expected_experiments.remove(exp["name"])

    assert not expected_experiments

    # Test versions
    expected_versions = {"ramble"}

    assert "versions" in data
    for ver in data["versions"]:
        if ver["name"] in expected_versions:
            assert ver["digest"] != ""
            assert ver["digest"] is not None
            expected_versions.remove(ver["name"])
    assert not expected_versions
