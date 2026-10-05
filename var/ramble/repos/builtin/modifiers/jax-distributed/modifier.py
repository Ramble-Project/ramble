# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.modkit import *


class JaxDistributed(BasicModifier):
    """Launcher modifier for distributed JAX execution.

    Bootstraps the JAX coordinator address and port from the cluster environment
    (Slurm, Google Batch, or localhost fallback) and ensures task coordination
    variables are passed into containerized sandboxes.
    """

    name = "jax-distributed"
    tags("tpu", "jax", "distributed", "slurm")
    maintainers("tteggelit")

    mode("standard", description="Standard JAX distributed launcher mode")
    default_mode("standard")

    modifier_variable(
        "jax_coordinator_port",
        default="8471",
        description="Port for JAX distributed coordination service",
    )

    modifier_variable(
        "jax_coordinator_address",
        default="",
        description="Override JAX coordinator IP/hostname (auto-discovered if empty)",
    )

    modifier_variable(
        "jax_export_node_rank",
        default=False,
        description="Prefix commands with NODE_RANK for scripts requiring NODE_RANK",
    )

    # Register environment variable modifications so ContainerBase forwards them into container_env_vars
    env_var_modification(
        "JAX_COORDINATOR_ADDRESS",
        modification="${JAX_COORDINATOR_ADDRESS:-127.0.0.1}",
        method="set",
    )
    env_var_modification(
        "JAX_COORDINATOR_PORT",
        modification="${JAX_COORDINATOR_PORT:-{jax_coordinator_port}}",
        method="set",
    )
    env_var_modification(
        "SLURM_PROCID",
        modification="${SLURM_PROCID:-${BATCH_TASK_INDEX:-0}}",
        method="set",
    )
    env_var_modification(
        "SLURM_NTASKS",
        modification="${SLURM_NTASKS:-${BATCH_TASK_COUNT:-1}}",
        method="set",
    )
    env_var_modification(
        "SLURM_NODEID",
        modification="${SLURM_NODEID:-${BATCH_TASK_INDEX:-0}}",
        method="set",
    )

    executable_modifier("jax_coordinator_setup", usage_filter="once")

    def jax_coordinator_setup(
        self, executable_name, executable, app_inst=None
    ):
        from ramble.util.executable import CommandExecutable

        pre_cmds = []
        post_cmds = []

        coord_script = (
            'if [ -z "${JAX_COORDINATOR_ADDRESS:-}" ]; then\n'
            '    if [ -n "${SLURM_JOB_NODELIST:-}" ] && command -v scontrol >/dev/null 2>&1; then\n'
            '        export JAX_COORDINATOR_ADDRESS=$(scontrol show hostnames "$SLURM_JOB_NODELIST" | head -n 1)\n'
            "    else\n"
            '        export JAX_COORDINATOR_ADDRESS="127.0.0.1"\n'
            "    fi\n"
            "fi\n"
            "export JAX_COORDINATOR_PORT=${JAX_COORDINATOR_PORT:-{jax_coordinator_port}}"
        )

        pre_cmds.append(
            CommandExecutable(
                "jax-coordinator-bootstrap",
                template=[coord_script],
                mpi=False,
                redirect="",
                output_capture="",
            )
        )

        if self.expander and str(
            self.expander.expand_var("{jax_export_node_rank}")
        ).lower() in ("true", "1"):
            if executable.mpi:
                executable.template = [
                    f"NODE_RANK=${{SLURM_NODEID:-${{BATCH_TASK_INDEX:-0}}}} {cmd}"
                    for cmd in executable.template
                ]

        return pre_cmds, post_cmds
