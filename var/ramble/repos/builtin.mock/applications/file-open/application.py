# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import ramble.util.ramble_yaml as ryaml
from ramble.appkit import *


class FileOpen(ExecutableApplication):
    name = "file-open"

    executable("foo", "echo 'bar'", use_mpi=False)

    workload("test_wl", executable="foo")

    register_phase(
        "load_config", pipeline="setup", run_after=["make_experiments"]
    )

    def _load_config(self, workspace, app_inst):
        config_path = get_file_path(
            os.path.join("file-open", "my", "config.yaml"), workspace
        )
        with open(config_path, encoding="utf-8") as conf:
            ryaml.load(conf)
            logger.info(f"Config loaded from {config_path}")
