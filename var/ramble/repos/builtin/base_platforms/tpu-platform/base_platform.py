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

    TOPOLOGY_TO_MESH = {
        # tpu7x / 3D
        "2x2x1": "2x2x2",
        "2x2x2": "4x2x2",
        "2x2x4": "4x4x2",
        "2x4x4": "8x4x2",
        "4x4x4": "16x4x2",
        # v6e / 2D
        "2x2": "2x2",
        "2x4": "4x2",
        "4x4": "4x4",
        "4x8": "8x4",
        "8x8": "8x8",
        "8x16": "16x8",
        "16x16": "16x16",
    }

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

    register_validator(
        "processes_per_node_tpu_platform_validation",
        predicate="{processes_per_node} == 1",
        message="TPU workloads strictly require processes_per_node to be 1, but got {processes_per_node}",
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
        default="4",
        description="Total ICI size across the TPU topology",
    )

    # Baseline performance thresholds (defaults per platform, overridable)
    variable(
        "min_gemm_tflops",
        default="0.0",
        description="Minimum GEMM throughput in TFLOP/s/device",
    )

    variable(
        "min_hbm_bw",
        default="0.0",
        description="Minimum HBM memory bandwidth in GB/s",
    )

    variable(
        "min_h2d_bw",
        default="0.0",
        description="Minimum Host-to-Device transfer bandwidth in GiB/s",
    )

    @classmethod
    def topology_math(cls, topology, cores_per_chip=1):
        """Calculate total chips, physical mesh shape, and ICI size from topology.

        Args:
            topology (str): Topology string, e.g. "2x2x1" or "2x2"
            cores_per_chip (int): Tensor cores per chip (default: 1)

        Returns:
            dict: Dictionary with 'total_chips', 'tpu_mesh_shape', and 'ici_size'
        """
        dims = [int(d) for d in str(topology).split("x") if d.isdigit()]
        if not dims:
            raise ValueError(f"Invalid TPU topology: '{topology}'")

        total_chips = 1
        for d in dims:
            total_chips *= d

        cores = int(cores_per_chip)
        ici_size = total_chips * cores

        top_str = str(topology)
        if cores > 1 and top_str in cls.TOPOLOGY_TO_MESH:
            mesh_shape = cls.TOPOLOGY_TO_MESH[top_str]
        elif cores == 1 and top_str in cls.TOPOLOGY_TO_MESH:
            mesh_shape = cls.TOPOLOGY_TO_MESH[top_str]
        else:
            scaled_dims = [dims[0] * cores] + dims[1:]
            mesh_shape = "x".join(str(d) for d in scaled_dims)

        return {
            "total_chips": total_chips,
            "tpu_mesh_shape": mesh_shape,
            "ici_size": ici_size,
        }
