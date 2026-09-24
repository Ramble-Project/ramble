# Copyright 2022-2025 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.config
import ramble.workspace
from ramble.main import RambleCommand
from ramble.namespace import namespace

workspace = RambleCommand("workspace")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)


def test_google_batch_workflow_default(request):
    workspace_name = request.node.name

    global_args = ["-w", workspace_name]

    variants_conf = r"""
variants:
  workflow_manager: google-batch
"""

    ws = ramble.workspace.create(workspace_name)

    ws.write()

    variants_path = os.path.join(ws.config_dir, "variants.yaml")

    with open(variants_path, "w+", encoding="utf-8") as f:
        f.write(variants_conf)

    workspace(
        "manage",
        "experiments",
        "hostname",
        "--wf",
        "local",
        "-v",
        "n_ranks=1",
        "-v",
        "n_nodes=1",
        global_args=global_args,
    )

    ws._re_read()

    # Remove batch submit definition
    ws_vars = ramble.config.get(namespace.variables)
    if "batch_submit" in ws_vars:
        del ws_vars["batch_submit"]
    ramble.config.config.update_config(
        namespace.variables, ws_vars, scope=ws.ws_file_config_scope_name()
    )
    ws.write()

    ws._re_read()

    workspace("setup", "--dry-run", global_args=global_args)

    exp_dir = os.path.join(ws.experiment_dir, "hostname", "local", "generated")
    files = [
        f
        for f in os.listdir(exp_dir)
        if os.path.isfile(os.path.join(exp_dir, f))
    ]
    assert "batch_submit" in files
    assert "batch_query" in files
    assert "batch_cancel" in files
    assert "batch_wait" in files
    assert "batch_config.yaml" in files
