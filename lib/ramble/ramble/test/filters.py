# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.filters
from ramble.error import RambleError


def test_translate_group_to_predicate():
    # Test empty group
    assert ramble.filters.translate_group_to_predicate({}) == "True"
    assert ramble.filters.translate_group_to_predicate(None) == "True"

    # Test only where
    group_only_where = {"where": ["{n_nodes} < 4", "{workload} == 'foo'"]}
    assert (
        ramble.filters.translate_group_to_predicate(group_only_where)
        == "(({n_nodes} < 4) and ({workload} == 'foo'))"
    )

    # Test only exclude_where
    group_only_exclude = {"exclude_where": ["{mpi} == 'tcp'", "{platform} == 'bar'"]}
    assert (
        ramble.filters.translate_group_to_predicate(group_only_exclude)
        == "(not ({mpi} == 'tcp') and not ({platform} == 'bar'))"
    )

    # Test both
    group_both = {"where": ["{n_nodes} < 4"], "exclude_where": ["{mpi} == 'tcp'"]}
    assert (
        ramble.filters.translate_group_to_predicate(group_both)
        == "(({n_nodes} < 4)) and (not ({mpi} == 'tcp'))"
    )


def test_expand_filter_groups():
    filter_groups_defs = {
        "small-scale": {"where": ["{n_nodes} < 4"]},
        "single-node": {"where": ["{n_nodes} == 1"]},
        "tcp-only": {"exclude_where": ["{mpi} != 'tcp'"]},
    }

    # Test empty expression
    assert ramble.filters.expand_filter_groups("", filter_groups_defs) == "True"
    assert ramble.filters.expand_filter_groups(None, filter_groups_defs) == "True"

    # Test single group
    assert (
        ramble.filters.expand_filter_groups("small-scale", filter_groups_defs)
        == "( (({n_nodes} < 4)) )"
    )

    # Test logical expression
    assert (
        ramble.filters.expand_filter_groups("small-scale and not single-node", filter_groups_defs)
        == "( (({n_nodes} < 4)) ) and not ( (({n_nodes} == 1)) )"
    )

    # Test parentheses
    assert (
        ramble.filters.expand_filter_groups(
            "(small-scale or tcp-only) and not single-node", filter_groups_defs
        )
        == "( ( (({n_nodes} < 4)) ) or ( (not ({mpi} != 'tcp')) ) ) and not ( (({n_nodes} == 1)) )"
    )

    # Test invalid group
    with pytest.raises(RambleError):
        ramble.filters.expand_filter_groups("invalid-group", filter_groups_defs)

    # Test invalid characters
    with pytest.raises(RambleError):
        ramble.filters.expand_filter_groups("small-scale & tcp-only", filter_groups_defs)

    # Test None defs
    assert ramble.filters.expand_filter_groups("", None) == "True"
    with pytest.raises(RambleError):
        ramble.filters.expand_filter_groups("small-scale", None)


def test_translate_group_to_predicate_empty_lists():
    # Test group with empty lists (should return "True" at line 54)
    group_empty_lists = {"where": [], "exclude_where": []}
    assert ramble.filters.translate_group_to_predicate(group_empty_lists) == "True"


def test_resolve_and_apply_filter_groups(mutable_config):
    class MockArgs:
        def __init__(self, filter_group=None, exclude_filter_group=None):
            self.filter_group = filter_group
            self.exclude_filter_group = exclude_filter_group

    # Mock filter groups in config
    ramble.config.set(
        "filter_groups",
        {"small": {"where": ["{n_nodes} < 4"]}, "tcp": {"exclude_where": ["{mpi} != 'tcp'"]}},
        scope="user",
    )

    # Case 1: Neither CLI nor Env
    assert ramble.filters.resolve_and_apply_filter_groups(MockArgs(), None) is None
    assert ramble.filters.resolve_and_apply_filter_groups(MockArgs(), [["existing"]]) == [
        ["existing"]
    ]

    # Case 2: CLI --filter-group
    args = MockArgs(filter_group="small")
    res = ramble.filters.resolve_and_apply_filter_groups(args, None)
    assert len(res) == 1
    assert "small" in res[0][0] or "{n_nodes}" in res[0][0]

    # Case 3: CLI --exclude-filter-group
    args = MockArgs(exclude_filter_group="tcp")
    res = ramble.filters.resolve_and_apply_filter_groups(args, None)
    assert len(res) == 1
    assert "not ( ( (not ({mpi} != 'tcp')) ) )" in res[0][0]

    # Case 4: Both CLI
    args = MockArgs(filter_group="small", exclude_filter_group="tcp")
    res = ramble.filters.resolve_and_apply_filter_groups(args, None)
    assert len(res) == 1
    assert "( ( (({n_nodes} < 4)) ) ) and not ( ( (not ({mpi} != 'tcp')) ) )" in res[0][0]

    # Case 5: Env var only
    import os

    os.environ["RAMBLE_ACTIVE_FILTER_GROUP"] = "small"
    try:
        args = MockArgs()
        res = ramble.filters.resolve_and_apply_filter_groups(args, None)
        assert len(res) == 1
        assert "small" in res[0][0] or "{n_nodes}" in res[0][0]
    finally:
        del os.environ["RAMBLE_ACTIVE_FILTER_GROUP"]

    # Case 6: CLI overrides Env var
    os.environ["RAMBLE_ACTIVE_FILTER_GROUP"] = "small"
    try:
        args = MockArgs(filter_group="tcp")
        res = ramble.filters.resolve_and_apply_filter_groups(args, None)
        assert len(res) == 1
        assert "tcp" in res[0][0] or "{mpi}" in res[0][0]
        assert "small" not in res[0][0] and "{n_nodes}" not in res[0][0]
    finally:
        del os.environ["RAMBLE_ACTIVE_FILTER_GROUP"]

    # Case 7: Failure path (invalid group)
    args = MockArgs(filter_group="invalid")
    with pytest.raises(SystemExit):
        ramble.filters.resolve_and_apply_filter_groups(args, None)


def test_validate_filter_group_name():
    # Test valid names
    ramble.filters.validate_filter_group_name("small")
    ramble.filters.validate_filter_group_name("small-scale")
    ramble.filters.validate_filter_group_name("small_scale")
    ramble.filters.validate_filter_group_name("group-1")

    # Test reserved keywords (should fail)
    with pytest.raises(RambleError):
        ramble.filters.validate_filter_group_name("and")
    with pytest.raises(RambleError):
        ramble.filters.validate_filter_group_name("OR")
    with pytest.raises(RambleError):
        ramble.filters.validate_filter_group_name("not")

    # Test invalid characters (should fail)
    with pytest.raises(RambleError):
        ramble.filters.validate_filter_group_name("small scale")
    with pytest.raises(RambleError):
        ramble.filters.validate_filter_group_name("small.scale")
    with pytest.raises(RambleError):
        ramble.filters.validate_filter_group_name("small&scale")


def test_filters_from_args(mutable_config):
    class MockArgs:
        phases = ["setup"]
        where = [["{n_nodes} == 1"]]
        exclude_where = [["{n_nodes} > 2"]]
        filter_tags = [["tag1", "tag2"]]
        filter_group = None
        exclude_filter_group = None

    filters = ramble.filters.Filters.from_args(MockArgs())
    assert filters.phases == ["setup"]
    assert filters.include_where == ["{n_nodes} == 1"]
    assert filters.exclude_where == ["{n_nodes} > 2"]
    assert filters.tags == {"tag1", "tag2"}

    overridden = ramble.filters.Filters.from_args(MockArgs(), phase_filters=["analyze"])
    assert overridden.phases == ["analyze"]
