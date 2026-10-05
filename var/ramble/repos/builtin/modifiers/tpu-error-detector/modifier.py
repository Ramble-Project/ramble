# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.modkit import *


class TpuErrorDetector(BasicModifier):
    """Modifier to detect TPU, JAX, and XLA errors in experiment logs."""

    name = "tpu-error-detector"

    tags("tpu", "diagnostics")

    maintainers("simrankaurb", "tileggett")

    mode("standard", description="Standard TPU error detection mode")
    default_mode("standard")

    figure_of_merit(
        "TPU OOM Error Detected",
        fom_regex=r"(?i)(?P<oom_error>.*(ResourceExhaustedError|Resource exhausted|Out of memory).*)",
        group_name="oom_error",
        units="",
        fom_type=FomType.INFO,
    )

    figure_of_merit(
        "Host Memory Error Detected",
        fom_regex=r"(?i)(?P<host_mem_error>.*(MemoryError|OOM-killer|Killed).*)",
        group_name="host_mem_error",
        units="",
        fom_type=FomType.INFO,
    )

    figure_of_merit(
        "TPU Hardware / Driver / Network Error Detected",
        fom_regex=r"(?i)(?P<hardware_error>.*(TPU device reset|Hardware error|Failed to initialize PJRT client|Failed to initialize PJRT|PjRtClient|Collective operation timed out|ICI link failure|libtpu not found|PermissionError:.*(/dev/vfio|/dev/accel)|SDC \(Bit flips\) Detected|TearDownMesh|STOP_SESSION\s+failed).*)",
        group_name="hardware_error",
        units="",
        fom_type=FomType.INFO,
    )

    figure_of_merit(
        "TPU/XLA Compilation Error Detected",
        fom_regex=r"(?i)(?P<comp_error>.*(XlaRuntimeError|XLA compiler|failed to compile|Mesh geometry does not match physical devices|TypeError).*)",
        group_name="comp_error",
        units="",
        fom_type=FomType.INFO,
    )

    figure_of_merit(
        "Profiler Error Detected",
        fom_regex=r"(?i)(?P<profiler_error>.*(Failed to start profiler|profiler runtime|permission error).*)",
        group_name="profiler_error",
        units="",
        fom_type=FomType.INFO,
    )

    figure_of_merit(
        "TPU Environment / Configuration Error Detected",
        fom_regex=r"(?i)(?P<env_config_error>.*(incompatible environment|command not found|No such file or directory).*)",
        group_name="env_config_error",
        units="",
        fom_type=FomType.INFO,
    )

    figure_of_merit(
        "TPU Benchmark Failure Detected",
        fom_regex=r"(?i)(?P<bench_fail>.*Benchmark func failed.*)",
        group_name="bench_fail",
        units="",
        fom_type=FomType.INFO,
    )
