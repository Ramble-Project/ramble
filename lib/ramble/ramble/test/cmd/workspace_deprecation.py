# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import deprecation
import pytest

import ramble.workspace
from ramble.main import RambleCommand

pytestmark = pytest.mark.usefixtures("mutable_mock_workspace_path")


workspace = RambleCommand("workspace")


@deprecation.fail_if_not_removed
def test_workspace_edit_only_flags_deprecation(workspace_name, deprecated_call):
    ws = ramble.workspace.create(workspace_name)
    ws.write()
    global_args = ["-w", workspace_name]

    with deprecated_call():
        out = workspace("edit", "--config-only", "--print-file", global_args=global_args).strip()
        assert out == ramble.workspace.config_file(ws.root)

    with deprecated_call():
        out = workspace("edit", "--template-only", "--print-file", global_args=global_args).strip()
        assert out == ws.template_path("execute_experiment")

    with deprecated_call():
        out = workspace("edit", "--license-only", "--print-file", global_args=global_args).strip()
        assert out == ramble.workspace.licenses_file(ws.root)
