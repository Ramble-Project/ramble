# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.modkit import *


class TpuNodeLocal(BasicModifier):
    """Modifier for single-host (node-local) TPU initialization.

    Configures ``libtpu`` and TPU runtime environment variables so independent
    single-host workloads can initialize local TPU chips on multi-host slices
    without querying the GCE Metadata Server or coordinating across hosts.
    """

    name = "tpu-node-local"
    tags("tpu", "jax")
    maintainers("tteggelit")

    mode("standard", description="Standard node-local TPU initialization mode")
    default_mode("standard")

    conflict(
        "modifier=jax-distributed",
        msg=(
            "tpu-node-local cannot be used with jax-distributed. "
            "Remove one of the modifiers, or set 'jax-distributed' mode to "
            "'disabled' to suppress automatic injection."
        ),
    )

    required_variable(
        "node_local_libtpu_init_args",
        description="LIBTPU_INIT_ARGS flags for node-local (single-host) TPU initialization",
        modes=["standard"],
    )

    # Register environment variable modifications so ContainerBase forwards them into container_env_vars
    env_var_modification(
        "TPU_HOST_BOUNDS",
        modification="1,1,1",
        method="set",
        modes=["standard"],
    )
    env_var_modification(
        "TPU_SKIP_MDS_QUERY",
        modification="true",
        method="set",
        modes=["standard"],
    )
    env_var_modification(
        "TPU_WORKER_ID",
        modification="0",
        method="set",
        modes=["standard"],
    )
    env_var_modification(
        "TPU_WORKER_HOSTNAMES",
        modification="localhost",
        method="set",
        modes=["standard"],
    )
    env_var_modification(
        "LIBTPU_INIT_ARGS",
        modification="{node_local_libtpu_init_args}",
        method="append",
        separator=" ",
        modes=["standard"],
    )
