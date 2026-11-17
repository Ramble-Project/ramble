# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest
from ruamel import yaml

import ramble.expander
import ramble.util.ramble_yaml as syaml
import ramble.util.yaml_generation


@pytest.fixture(scope="session")
def yaml_config(tmpdir_factory):
    test_data = {}

    test_data["foo"] = {}
    test_data["foo"]["foo2"] = {}
    test_data["foo"]["foo2"]["foo3"] = "foo4"

    test_data["bar"] = {}
    test_data["bar"]["bar2"] = {}
    test_data["bar"]["bar_str"] = "bar"
    test_data["bar"]["bar2"]["bar3"] = "bar4"
    test_data["bar"]["bar2"][32] = 0.3

    test_data["baz"] = {}
    test_data["baz"]["baz2"] = "baz"

    path = str(tmpdir_factory.mktemp("config.yaml").join("config"))
    with open(path, "w+", encoding="utf-8") as f:
        yaml.dump(
            test_data,
            default_flow_style=False,
            width=syaml.maxint,
            Dumper=syaml.OrderedLineDumper,
            stream=f,
        )
    return path


def test_read_config_file(yaml_config):
    read_data = ramble.util.yaml_generation.read_config_file(yaml_config)
    assert "foo" in read_data
    assert "foo2" in read_data["foo"]
    assert "bar" in read_data
    assert "bar2" in read_data["bar"]
    assert 32 in read_data["bar"]["bar2"]
    assert "baz" in read_data
    assert "baz2" in read_data["baz"]


def test_all_config_options(yaml_config):
    read_data = ramble.util.yaml_generation.read_config_file(yaml_config)
    all_configs = ramble.util.yaml_generation.all_config_options(read_data)

    assert "foo.foo2.foo3" in all_configs
    assert "bar.bar2.bar3" in all_configs
    assert "bar.bar_str" in all_configs
    assert "baz.baz2" in all_configs


def test_get_config_value(yaml_config):
    read_data = ramble.util.yaml_generation.read_config_file(yaml_config)

    config_tests = [
        ("foo.foo2.foo3", "foo4"),
        ("bar.bar_str", "bar"),
        ("bar.bar2.bar3", "bar4"),
        ("baz.baz2", "baz"),
        ("bar.bar2.32", 0.3),
    ]

    for config, ans in config_tests:
        test_val = ramble.util.yaml_generation.get_config_value(read_data, config)
        assert test_val == ans


def test_set_config_value(yaml_config):
    read_data = ramble.util.yaml_generation.read_config_file(yaml_config)

    ramble.util.yaml_generation.set_config_value(read_data, "foo.foo2.foo3", "foo_set")
    assert read_data["foo"]["foo2"]["foo3"] == "foo_set"

    # Test without forcing
    ramble.util.yaml_generation.set_config_value(read_data, "foo.bar.baz", "test")
    assert "bar" not in read_data["foo"]

    # Test with forcing
    ramble.util.yaml_generation.set_config_value(read_data, "foo.bar.baz", "test", force=True)
    assert read_data["foo"]["bar"]["baz"] == "test"


def test_remove_config_value(yaml_config):
    read_data = ramble.util.yaml_generation.read_config_file(yaml_config)

    # Test parent removal
    ramble.util.yaml_generation.remove_config_value(read_data, "foo.foo2.foo3")
    assert "foo" not in read_data

    # Test partial removal
    ramble.util.yaml_generation.remove_config_value(read_data, "bar.bar_str")
    assert "bar_str" not in read_data["bar"]
    assert "bar2" in read_data["bar"]


def test_apply_default_config_values(mutable_mock_apps_repo):
    config_data = {"foo": {"bar": "baz"}}
    default_config_string = "{default_config_value}"
    app_inst = mutable_mock_apps_repo.get("basic")
    app_inst.variables = {"foo.bar": ""}
    expansion_vars = {
        "workload_name": "test_wl",
        "foo.bar": default_config_string,
    }
    app_inst.expander = ramble.expander.Expander(expansion_vars, None)

    assert app_inst.variables["foo.bar"] == ""
    ramble.util.yaml_generation.apply_default_config_values(
        config_data, app_inst, default_config_string
    )
    assert app_inst.variables["foo.bar"] == "baz"
