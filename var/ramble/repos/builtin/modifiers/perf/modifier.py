# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import ramble.util.shell_utils
from ramble.modkit import *
from ramble.util.executable import CommandExecutable


class Perf(BasicModifier):
    """Define a modifier for capturing performance counters using 'perf'."""

    name = "perf"

    tags("performance-analysis", "pmu")

    mode("stat", description="Capture performance counters using 'perf stat'")
    mode(
        "record", description="Capture performance samples using 'perf record'"
    )

    default_mode("stat")

    archive_pattern("{experiment_run_dir}/perf_*")

    modifier_variable(
        "perf_path",
        default="perf",
        description="Path to the 'perf' binary",
        modes=["stat", "record"],
    )

    modifier_variable(
        "perf_events",
        default="cycles,instructions",
        description="Comma separated list of events to capture",
        modes=["stat", "record"],
    )

    modifier_variable(
        "perf_metrics",
        default="",
        description="Comma separated list of metric groups to capture",
        modes=["stat"],
    )

    modifier_variable(
        "perf_flags",
        default="-a",
        description="Additional flags for 'perf'",
        modes=["stat", "record"],
    )

    modifier_variable(
        "perf_subcommand",
        default="stat",
        description="Internal variable for the perf subcommand",
        modes=["stat"],
    )

    modifier_variable(
        "perf_subcommand",
        default="record",
        description="Internal variable for the perf subcommand",
        modes=["record"],
    )

    variant(
        "use_sudo",
        default=True,
        values=[True, False],
        description="Use 'sudo' when executing the 'perf' command",
    )

    modifier_variable(
        "sudo_prefix",
        default="sudo ",
        description="Prefix for running commands with sudo",
        modes=["stat", "record"],
        when=["+use_sudo"],
    )

    modifier_variable(
        "sudo_prefix",
        default="",
        description="Prefix for running commands with sudo",
        modes=["stat", "record"],
        when=["~use_sudo"],
    )

    executable_modifier("apply_perf")

    def apply_perf(self, exe_name, exe, app_inst=None):
        pre_cmds = []
        post_cmds = []

        shell = ramble.config.get("config:shell")
        last_pid_str = ramble.util.shell_utils.last_pid_var(shell)
        hostname_cmd = ramble.util.shell_utils.cmd_sub_str(shell, "uname -n")

        perf_cmd = "{perf_path} {perf_subcommand} {perf_flags}"

        events = self.expander.expand_var_name("perf_events")
        if events and events != "None":
            perf_cmd += f" -e {events}"

        metrics = self.expander.expand_var_name("perf_metrics")
        if metrics and metrics != "None":
            perf_cmd += f" -M '{metrics}'"

        log_path = (
            "{experiment_run_dir}/perf_{experiment_name}_"
            + hostname_cmd
            + ".out"
        )

        pre_cmds.append(
            CommandExecutable(
                f"start-perf-{exe_name}",
                template=[
                    f'perf_log="{log_path}"',
                    f'{{sudo_prefix}}{perf_cmd} > "$perf_log" 2>&1 &',
                    f"perf_pid={last_pid_str}",
                ],
                mpi=False,
                redirect="",
                output_capture="",
            )
        )

        post_cmds.append(
            CommandExecutable(
                f"stop-perf-{exe_name}",
                template=[
                    '{sudo_prefix}kill -INT "$perf_pid"',
                    "sleep 2",
                    'if ps -p "$perf_pid" > /dev/null; then {sudo_prefix}kill -9 "$perf_pid"; fi',
                ],
                mpi=False,
                redirect="",
                output_capture="",
            )
        )

        return pre_cmds, post_cmds

    figure_of_merit(
        "cycles",
        log_file="perf_{experiment_name}_*.out",
        fom_regex=r"\s+(?P<cycles>[\d,]+)\s+cycles",
        group_name="cycles",
        units="count",
    )

    figure_of_merit(
        "instructions",
        log_file="perf_{experiment_name}_*.out",
        fom_regex=r"\s+(?P<instructions>\d+)\s+instructions",
        group_name="instructions",
        units="count",
    )

    figure_of_merit(
        "ipc",
        log_file="perf_{experiment_name}_*.out",
        fom_regex=r"instructions\s+#\s+(?P<ipc>\d+\.\d+)\s+insn per cycle",
        group_name="ipc",
        units="insn/cycle",
    )

    figure_of_merit(
        "l1d_cache_refill",
        log_file="perf_{experiment_name}_*.out",
        fom_regex=r"\s+(?P<l1d_refill>\d+)\s+l1d_cache_refill",
        group_name="l1d_refill",
        units="count",
    )

    figure_of_merit(
        "l2d_cache_refill",
        log_file="perf_{experiment_name}_*.out",
        fom_regex=r"\s+(?P<l2d_refill>\d+)\s+l2d_cache_refill",
        group_name="l2d_refill",
        units="count",
    )

    figure_of_merit(
        "hnf_cache_miss",
        log_file="perf_{experiment_name}_*.out",
        fom_regex=r"\s+(?P<mesh_miss>\d+)\s+.*/hnf_cache_miss/",
        group_name="mesh_miss",
        units="count",
    )

    figure_of_merit(
        "read_bandwidth",
        log_file="perf_{experiment_name}_*.out",
        fom_regex=r"\s+(?P<read_bw>\d+\.?\d*)\s+.*/rni_actual_read_bandwidth/",
        group_name="read_bw",
        units="GB/s",
    )

    figure_of_merit(
        "write_bandwidth",
        log_file="perf_{experiment_name}_*.out",
        fom_regex=r"\s+(?P<write_bw>\d+\.?\d*)\s+.*/rni_actual_write_bandwidth/",
        group_name="write_bw",
        units="GB/s",
    )

    figure_of_merit(
        "backend_stall_pct",
        log_file="perf_{experiment_name}_*.out",
        fom_regex=r"(?P<be_pct>\d+\.\d+)\s+percent of slots\s+backend_bound",
        group_name="be_pct",
        units="%",
    )

    figure_of_merit(
        "branch_mispredict_pct",
        log_file="perf_{experiment_name}_*.out",
        fom_regex=r"(?P<br_pct>\d+\.\d+)\s+percent of slots\s+bad_speculation",
        group_name="br_pct",
        units="%",
    )
