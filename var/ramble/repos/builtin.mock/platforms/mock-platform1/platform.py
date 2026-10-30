# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.platkit import *


class MockPlatform1(PlatformBase):
    """An example mock platform"""

    name = "mock-platform1"

    platform_family("test")

    variable(
        "max_accelerators_per_node",
        default="0",
        description="Accelerators on each node",
    )
    variable(
        "max_threads_per_core", default="1", description="Threads on each node"
    )
    variable(
        "max_sockets_per_node", default="2", description="Sockets on each node"
    )
    variable(
        "max_cores_per_node", default="4", description="Cores on each node"
    )

    with when("package_manager_family=spack"):
        auxiliary_software_file(
            "spack_packages",
            src_path="packages.yaml.tpl",
            dest_path="packages.yaml",
        )
        package_manager_config(
            "platform_target",
            "packages:all:target:[zen5]",
        )

    variable(
        "max_memory_per_node",
        description="Memory per node in GB",
        default="20",
    )

    variable(
        "system_variant1",
        default="foo",
        description="Variable to determine variant value",
    )
