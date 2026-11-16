# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.platkit import *


class CpuPlatform(PlatformBase):
    """Platform representing a node with primarily CPU compute capabilities"""

    name = "cpu-platform"

    variable(
        "max_accelerators_per_node",
        default="0",
        description="CPU nodes are expected to have no accelerators",
    )
