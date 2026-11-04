# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.platkit import *


class TpuPlatform(PlatformBase):
    """Platform representing a node with available Google Cloud TPU accelerator capabilities.

    TPU quantities and execution parameters are set through the following variables:
    - n_accelerators: Global number of accelerators in an experiment
    - accelerators_per_node: Number of accelerators to use per node
    - chips_per_node: Physical TPU ASIC count per host VM
    - cores_per_chip: Tensor cores per physical TPU ASIC
    - tpu_topology: Physical TPU interconnect topology (e.g. 2x2, 2x2x1, 2x2x2, 4x4x4)
    - tpu_mesh_shape: Logical TPU mesh shape
    - ici_size: Total ICI size across the TPU topology
    - tpu_device_path: Device passthrough path (/dev/vfio or /dev/accel)
    """

    name = "tpu-platform"

    variant(
        "accelerator",
        default=True,
        description="TPU Platforms should have a TPU accelerator by default",
    )

    variant(
        "accelerator_type",
        default="TPU",
        values=["TPU"],
        description="Type of accelerator on this platform",
    )

    # TPU execution: exactly 1 host process manages local chips
    variable(
        "processes_per_node",
        default="1",
        values=["1"],
        description="TPU workloads strictly require 1 host process per node",
    )

    with when("+validate_platform"):
        register_validator(
            "processes_per_node_tpu_platform_validation",
            predicate="{processes_per_node} == 1",
            message="TPU workloads strictly require processes_per_node to be 1, but {processes_per_node} were specified",
        )

    variable(
        "chips_per_node",
        default="4",
        description="Number of physical TPU chips (ASICs) per host VM",
    )

    variable(
        "cores_per_chip",
        default="1",
        description="Tensor cores per TPU chip",
    )

    variable(
        "hbm_per_device_gb",
        default="32",
        description="HBM capacity per TPU device in GiB",
    )

    variable(
        "max_accelerators_per_node",
        default="{chips_per_node} * {cores_per_chip}",
        description="Maximum number of TPU accelerators per node",
    )

    variable(
        "accelerators_per_node",
        default="{max_accelerators_per_node}",
        description="Number of TPU accelerators to use per node",
    )

    variable(
        "tpu_device_path",
        default="/dev/vfio",
        description="Host device path for TPU accelerator passthrough (/dev/vfio or /dev/accel)",
    )

    variable(
        "container_mounts",
        default="{tpu_device_path}:{tpu_device_path}",
        description="Container mounts for TPU accelerator device passthrough",
    )

    variable(
        "k8s_tpu_resource",
        default="google.com/tpu",
        description="Kubernetes resource name for TPU requests/limits on GKE",
        when=["workflow_manager=gke-mpi"],
    )

    variable(
        "gke_tpu_accelerator",
        default="",
        description="GKE nodeSelector label value for cloud.google.com/gke-tpu-accelerator",
        when=["workflow_manager=gke-mpi"],
    )

    variable(
        "node_local_libtpu_init_args",
        default="--xla_tpu_use_enhanced_launch_barrier=false --megascale_error_reporter_abort_on_hang=true",
        description="LIBTPU_INIT_ARGS flags for node-local (single-host) TPU initialization",
    )

    variable(
        "tpu_topology",
        default="2x2x1",
        description="TPU interconnect topology string (e.g. 2x2, 2x2x1, 2x2x2, 4x4x4)",
    )

    variable(
        "tpu_mesh_shape",
        default="{tpu_topology}",
        description="Logical TPU mesh shape",
    )

    variable(
        "ici_size",
        default="{n_nodes} * {chips_per_node} * {cores_per_chip}",
        description="Total ICI size across the TPU topology",
    )

    variable(
        "max_sockets_per_node",
        default="1",
        description="Maximum number of sockets per node",
    )

    variable(
        "max_threads_per_core",
        default="2",
        description="Maximum number of threads per core",
    )

    variable(
        "max_cores_per_node",
        default="64",
        description="Maximum number of host CPU cores per node",
    )

    variable(
        "max_memory_per_node",
        default="128",
        description="Maximum host memory per node in GB",
    )

    variable(
        "optimization_target",
        default="x86_64_v3",
        description="Spack optimization target for this platform",
    )

    variable(
        "portable_target",
        default="x86_64",
        description="Portable Spack optimization target for this platform",
    )
