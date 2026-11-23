# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.modkit import *
from ramble.util.executable import CommandExecutable


class JaxDistributed(BasicModifier):
    """Launcher modifier for distributed JAX execution.

    Bootstraps the JAX coordinator address and port across cluster environments
    (GKE, Slurm, Google Batch, PBS, LSF, MPI, or localhost fallback) and ensures
    JAX coordination variables are passed into containerized sandboxes.
    """

    name = "jax-distributed"
    tags("tpu", "jax")
    maintainers("tteggelit")

    mode("standard", description="Standard JAX distributed launcher mode")
    mode(
        "node-local",
        description="Configure node-local TPU initialization for single-host workloads",
    )
    default_mode("standard")

    modifier_variable(
        "jax_coordinator_port",
        default="8471",
        description="Port for JAX distributed coordination service",
        modes=["standard"],
    )

    modifier_variable(
        "jax_coordinator_address",
        default="",
        description="Override JAX coordinator IP/hostname (auto-discovered if empty)",
        modes=["standard"],
    )

    required_variable(
        "node_local_libtpu_init_args",
        description="LIBTPU_INIT_ARGS flags for node-local (single-host) TPU initialization",
        modes=["node-local"],
    )

    # Register environment variable modifications so ContainerBase forwards them into container_env_vars
    env_var_modification(
        "JAX_COORDINATOR_ADDRESS",
        modification="${JAX_COORDINATOR_ADDRESS:-{jax_coordinator_address}}",
        method="set",
        modes=["standard"],
    )
    env_var_modification(
        "JAX_COORDINATOR_PORT",
        modification="${JAX_COORDINATOR_PORT:-{jax_coordinator_port}}",
        method="set",
        modes=["standard"],
    )
    env_var_modification(
        "JAX_NUM_PROCESSES",
        modification="${JAX_NUM_PROCESSES:-}",
        method="set",
        modes=["standard"],
    )
    env_var_modification(
        "JAX_PROCESS_ID",
        modification="${JAX_PROCESS_ID:-}",
        method="set",
        modes=["standard"],
    )

    # Node-local mode environment variables for single-host execution on multi-host TPU slices
    env_var_modification(
        "TPU_HOST_BOUNDS",
        modification="1,1,1",
        method="set",
        modes=["node-local"],
    )
    env_var_modification(
        "TPU_SKIP_MDS_QUERY",
        modification="true",
        method="set",
        modes=["node-local"],
    )
    env_var_modification(
        "TPU_WORKER_ID",
        modification="0",
        method="set",
        modes=["node-local"],
    )
    env_var_modification(
        "TPU_WORKER_HOSTNAMES",
        modification="localhost",
        method="set",
        modes=["node-local"],
    )
    env_var_modification(
        "LIBTPU_INIT_ARGS",
        modification="{node_local_libtpu_init_args}",
        method="append",
        separator=" ",
        modes=["node-local"],
    )

    executable_modifier("jax_coordinator_setup", usage_filter="once")

    def jax_coordinator_setup(
        self, executable_name, executable, app_inst=None
    ):
        pre_cmds = []
        post_cmds = []

        if self._usage_mode == "node-local":
            return pre_cmds, post_cmds

        coord_script = (
            'if [ -z "${JAX_COORDINATOR_ADDRESS:-}" ]; then\n'
            '    if [ -n "${MEGASCALE_COORDINATOR_ADDRESS:-}" ]; then\n'
            '        export JAX_COORDINATOR_ADDRESS="${MEGASCALE_COORDINATOR_ADDRESS%%:*}"\n'
            '    elif [ -n "${TPU_WORKER_HOSTNAMES:-}" ]; then\n'
            '        export JAX_COORDINATOR_ADDRESS="${TPU_WORKER_HOSTNAMES%%,*}"\n'
            '    elif [ -n "${SLURM_JOB_NODELIST:-}" ] && command -v scontrol >/dev/null 2>&1; then\n'
            '        export JAX_COORDINATOR_ADDRESS=$(scontrol show hostnames "$SLURM_JOB_NODELIST" | head -n 1)\n'
            '    elif [ -n "${BATCH_HOSTS_FILE:-}" ] && [ -f "${BATCH_HOSTS_FILE}" ]; then\n'
            '        export JAX_COORDINATOR_ADDRESS=$(head -n 1 "${BATCH_HOSTS_FILE}")\n'
            '        export JAX_NUM_PROCESSES="${JAX_NUM_PROCESSES:-${BATCH_TASK_COUNT:-1}}"\n'
            '        export JAX_PROCESS_ID="${JAX_PROCESS_ID:-${BATCH_TASK_INDEX:-0}}"\n'
            "    elif [ -f /etc/mpi/hostfile ]; then\n"
            "        export JAX_COORDINATOR_ADDRESS=$(awk 'NF && $1 !~ /^#/ {print $1; exit}' /etc/mpi/hostfile)\n"
            '    elif [ -n "${PBS_NODEFILE:-}" ] && [ -f "${PBS_NODEFILE}" ]; then\n'
            '        export JAX_COORDINATOR_ADDRESS=$(head -n 1 "${PBS_NODEFILE}")\n'
            '    elif [ -n "${LSB_HOSTS:-}" ]; then\n'
            "        export JAX_COORDINATOR_ADDRESS=$(echo \"${LSB_HOSTS}\" | awk '{print $1}')\n"
            '    elif [ -z "${OMPI_MCA_orte_hnp_uri:-}" ] && [ -z "${KUBERNETES_SERVICE_HOST:-}" ]; then\n'
            '        export JAX_COORDINATOR_ADDRESS="127.0.0.1"\n'
            '        export JAX_NUM_PROCESSES="${JAX_NUM_PROCESSES:-1}"\n'
            '        export JAX_PROCESS_ID="${JAX_PROCESS_ID:-0}"\n'
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

        return pre_cmds, post_cmds
