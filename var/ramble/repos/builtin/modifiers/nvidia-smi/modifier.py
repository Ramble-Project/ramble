# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.modkit import *


class NvidiaSmi(BasicModifier):
    """Define a modifier for nvidia-smi

    nvidia-smi is a command line utility, based on top of the NVIDIA Management
    Library (NVML), intended to aid in the management and monitoring of NVIDIA
    GPU devices.
    https://developer.nvidia.com/nvidia-system-management-interface
    """

    name = "nvidia-smi"

    tags("gpu-utility", "diagnostics", "nvidia-tool")

    maintainers("samskillman")

    variable(
        "gpus_per_node",
        default=8,
        description="The number of GPUs per node.",
    )

    mode("standard", description="Standard execution mode for nvidia-smi")
    default_mode("standard")

    variable_modification(
        "nvidia_smi_log",
        "{experiment_run_dir}/nvidia_smi_output.log",
        method="set",
        modes=["standard"],
    )

    archive_pattern("nvidia_smi_output.log", modes=["standard"])

    # FOMs from 'collect' executable
    # Example Output:
    # 0, NVIDIA A100-SXM4-80GB, 535.161.07, P0, 00000000:C4:04.0, 1650222031058, GPU-e6a1d5e1-9a00-c86a-769a-1e2d4d438a4d, 44.38, 700.00, 1095, 2010
    # 1, NVIDIA A100-SXM4-80GB, 535.161.07, P0, 00000000:C5:04.0, 1650222031066, GPU-f9b0c0a0-1b1a-2e2d-3f3g-4h4i5j6k7l8m, 43.99, 700.00, 1095, 2010

    figure_of_merit_context(
        "gpu",
        regex=r"^(?P<gpu_index>\d+),",
        output_format="GPU {gpu_index}",
        log_file="{nvidia_smi_log}",
    )

    figure_of_merit(
        "GPU Name",
        fom_regex=r"^\d+, (?P<gpu_name>[^,]+),",
        group_name="gpu_name",
        units="",
        fom_type=FomType.CATEGORY,
        contexts=["gpu"],
        log_file="{nvidia_smi_log}",
    )

    figure_of_merit(
        "Driver Version",
        fom_regex=r"^\d+, [^,]+, (?P<driver_version>[^,]+),",
        group_name="driver_version",
        units="",
        fom_type=FomType.CATEGORY,
        contexts=["gpu"],
        log_file="{nvidia_smi_log}",
    )

    figure_of_merit(
        "Performance State",
        fom_regex=r"^\d+, [^,]+, [^,]+, (?P<pstate>[^,]+),",
        group_name="pstate",
        units="",
        fom_type=FomType.CATEGORY,
        contexts=["gpu"],
        log_file="{nvidia_smi_log}",
    )

    figure_of_merit(
        "PCI Bus ID",
        fom_regex=r"^\d+, [^,]+, [^,]+, [^,]+, (?P<pci_bus_id>[^,]+),",
        group_name="pci_bus_id",
        units="",
        fom_type=FomType.INFO,
        contexts=["gpu"],
        log_file="{nvidia_smi_log}",
    )

    figure_of_merit(
        "Serial Number",
        fom_regex=r"^\d+, [^,]+, [^,]+, [^,]+, [^,]+, (?P<serial>[^,]+),",
        group_name="serial",
        units="",
        fom_type=FomType.INFO,
        contexts=["gpu"],
        log_file="{nvidia_smi_log}",
    )

    figure_of_merit(
        "UUID",
        fom_regex=r"^\d+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, (?P<uuid>[^,]+),",
        group_name="uuid",
        units="",
        fom_type=FomType.INFO,
        contexts=["gpu"],
        log_file="{nvidia_smi_log}",
    )

    figure_of_merit(
        "Power Draw",
        fom_regex=r"^\d+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, (?P<power_draw>[^,]+),",
        group_name="power_draw",
        units="W",
        fom_type=FomType.MEASURE,
        contexts=["gpu"],
        log_file="{nvidia_smi_log}",
    )

    figure_of_merit(
        "Power Limit",
        fom_regex=r"^\d+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, (?P<power_limit>[^,]+),",
        group_name="power_limit",
        units="W",
        fom_type=FomType.MEASURE,
        contexts=["gpu"],
        log_file="{nvidia_smi_log}",
    )

    figure_of_merit(
        "Graphics Clock",
        fom_regex=r"^\d+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, (?P<graphics_clock>[^,]+),",
        group_name="graphics_clock",
        units="MHz",
        fom_type=FomType.MEASURE,
        contexts=["gpu"],
        log_file="{nvidia_smi_log}",
    )

    figure_of_merit(
        "Memory Clock",
        fom_regex=r"^\d+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, [^,]+, (?P<mem_clock>[^,]+)",
        group_name="mem_clock",
        units="MHz",
        fom_type=FomType.MEASURE,
        contexts=["gpu"],
        log_file="{nvidia_smi_log}",
    )

    figure_of_merit(
        "GPU Count",
        fom_regex=r"GPU Count: (?P<gpu_count>\d+)",
        group_name="gpu_count",
        units="",
        fom_type=FomType.MEASURE,
        log_file="{nvidia_smi_log}",
    )

    success_criteria(
        "gpu_count_check",
        mode="fom_comparison",
        fom_name="GPU Count",
        formula="{value} == {gpus_per_node}",
    )

    register_builtin("nvidia_smi_exec")

    def nvidia_smi_exec(self):
        return [
            "nvidia-smi --query-gpu=index,name,driver_version,pstate,pci.bus_id,serial,uuid,power.draw,power.limit,clocks.gr,clocks.mem --format=csv,noheader,nounits > {nvidia_smi_log}",
            'echo "GPU Count: $(wc -l < {nvidia_smi_log})" >> {nvidia_smi_log}',
        ]
