# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
"""Perform tests of the util/path functions"""

import os

import pytest

import ramble.util.path
import ramble.workspace


@pytest.mark.parametrize(
    "path,expect",
    [
        ("rel/path", os.path.abspath("rel/path")),
        ("/abs/path", "/abs/path"),
        ("file:/abs/path", "file:/abs/path"),
        ("file:/abs/path/", "file:/abs/path"),
        ("gs://my-bucket", "gs://my-bucket"),
        ("gs://my-bucket/", "gs://my-bucket"),
        ("gs://my-bucket///", "gs://my-bucket"),
        ("/", "/"),
        ("///", "/"),
        ("", ""),
    ],
)
def test_normalize_path_or_url(path, expect):
    assert ramble.util.path.normalize_path_or_url(path) == expect


def test_substitute_config_variables():
    # Non-variable strings should return unchanged
    assert ramble.util.path.substitute_config_variables("simple/path", {}) == "simple/path"
    assert ramble.util.path.substitute_config_variables("", {}) == ""

    # Test variable substitutions
    local = {"custom": "/my/custom/path"}
    assert (
        ramble.util.path.substitute_config_variables("$custom/file", local)
        == "/my/custom/path/file"
    )
    assert (
        ramble.util.path.substitute_config_variables("${custom}/file", local)
        == "/my/custom/path/file"
    )
    assert (
        ramble.util.path.substitute_config_variables("$tempdir/foo", {})
        == f"{ramble.util.path.replacements['tempdir']}/foo"
    )


def test_substitute_workspace_path_variables(mutable_mock_workspace_path):
    with ramble.workspace.create("test_ws_path_vars") as ws:
        ws.write()
        assert ramble.util.path.substitute_path_variables("$workspace_root/repo") == os.path.join(
            ws.root, "repo"
        )
        assert ramble.util.path.substitute_path_variables(
            "$workspace_configs/ramble.yaml"
        ) == os.path.join(ws.config_dir, "ramble.yaml")
        assert ramble.util.path.canonicalize_path("$workspace_root/repo") == os.path.join(
            ws.root, "repo"
        )
        # Local replacements take precedence over workspace path variables
        assert (
            ramble.util.path.substitute_path_variables(
                "$workspace_root/repo", local_replacements={"workspace_root": "/override"}
            )
            == "/override/repo"
        )
