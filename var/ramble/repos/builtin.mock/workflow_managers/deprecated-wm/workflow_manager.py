# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.wmkit import *


class DeprecatedWm(WorkflowManagerBase):
    """Mock workflow manager to test declarative deprecations."""

    name = "deprecated-wm"

    deprecate(
        deprecated_in="0.7.0",
        removed_in="99.0.0",
        replacement="slurm",
    )

    def get_status(self, workspace):
        """Return status of a given job"""
        return
