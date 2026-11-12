# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import os

from ramble.appkit import *

from spack.util.path import canonicalize_path


class PyNemo(ExecutableApplication):
    """Define a base class for PyNemo applications."""

    name = "py-nemo"

    tags(
        "machine-learning",
        "llm",
        "nlp",
        "nvidia-framework",
        "pytorch",
        "cuda",
        "python",
    )

    workload_group("pretraining", workloads=[])

    workload_variable(
        "custom_injected_string",
        default="tail /dev/null",
        description="Custom string to inject before execution NeMo workload",
        workload_group="pretraining",
    )
    workload_variable(
        "nemo_container_version",
        default="24.07",
        description="Version for NeMo container",
        workload_group="pretraining",
    )
    workload_variable(
        "nemo_stage",
        default="training",
        description="Stage to run in NeMo",
        workload_group="pretraining",
    )
    workload_variable(
        "cuda_visible_devices",
        environment_variable_name="CUDA_VISIBLE_DEVICES",
        default="0,1,2,3,4,5,6,7",
        description="Comma delimited list of CUDA device IDs.",
        workload_group="pretraining",
    )
    workload_variable(
        "transformers_offline",
        environment_variable_name="TRANSFORMERS_OFFLINE",
        default="0",
        description="Whether transformers are offline (0) or not (1)",
        workload_group="pretraining",
    )
    workload_variable(
        "torch_nccl_avoid_record_streams",
        environment_variable_name="TORCH_NCCL_AVOID_RECORD_STREAMS",
        default="1",
        description="Avoid (1) recording streams for Torch NCCL, or not (0)",
        workload_group="pretraining",
    )
    workload_variable(
        "nccl_nvls_enable",
        environment_variable_name="NCCL_NVLS_ENABLE",
        default="0",
        description="Enable (1) NCCL NVLS or not (0)",
        workload_group="pretraining",
    )
    workload_variable(
        "results_mount",
        environment_variable_name="NEMO_CONTAINER_MOUNTS",
        default="{experiment_run_dir}:{experiment_run_dir}",
        description="Container mount for results data",
        workload_group="pretraining",
    )
    workload_variable(
        "container_mounts",
        default="{results_mount}",
        description="All container mounts in a ramble variable",
        workload_group="pretraining",
    )
    environment_variable(
        "NEMO_HOST_VARS",
        value="TRANSFORMERS_OFFLINE,TORCH_NCCL_AVOID_RECORD_STREAMS,NCCL_NVLS_ENABLE,CUDA_VISIBLE_DEVICES",
        description="Host variables for NeMo",
        workload_group="pretraining",
    )
    workload_variable(
        "processed_log_file",
        default="{experiment_run_dir}/processed_{experiment_name}.out",
        description="Path to store processed NeMo output",
        workload_group="pretraining",
    )

    final_epoch_regex = (
        r"Epoch (?P<epoch_id>[0-9]+):\s+:\s+(?P<pct_complete>[0-9]+)%.*\s+"
        + r"(?P<step_idx>[0-9]+)\/(?P<max_itr>[0-9]+) \[(?P<elapsed_time>[0-9]+:[0-9]+)<"
        + r"(?P<remaining_time>[0-9]+:[0-9]+),(\s+v_num=(?P<v_num>.*),)* reduced_train_loss="
        + r"(?P<reduced_train_loss>[0-9]+\.[0-9]+), global_step=(?P<global_step>[0-9]+\.[0-9]+), "
        + r"consumed_samples=(?P<consumed_samples>[0-9]+\.[0-9]+), train_step_timing in s="
        + r"(?P<train_step_timing>[0-9]+\.[0-9]+)(, val_loss=(?P<val_loss>[0-9]+\.[0-9]+))*\]"
    )
    figure_of_merit(
        "Final Epoch ID",
        fom_regex=final_epoch_regex,
        group_name="epoch_id",
        log_file="{processed_log_file}",
    )
    figure_of_merit(
        "Final Step ID",
        fom_regex=final_epoch_regex,
        group_name="step_idx",
        log_file="{processed_log_file}",
    )
    figure_of_merit(
        "Final Elapsed Time",
        fom_regex=final_epoch_regex,
        group_name="elapsed_time",
        log_file="{processed_log_file}",
    )

    def _calc_elapsed_seconds(app):
        timestamp = app.get_fom_value("Final Elapsed Time")
        if not timestamp:
            return None
        elapsed_s = 0
        mult = 1
        for part in reversed(timestamp.split(":")):
            elapsed_s += int(part) * mult
            mult *= 60
        return elapsed_s

    figure_of_merit(
        "Final Elapsed Seconds",
        formula=_calc_elapsed_seconds,
        units="s",
    )
    figure_of_merit(
        "Final Remaining Time",
        fom_regex=final_epoch_regex,
        group_name="remaining_time",
        log_file="{processed_log_file}",
    )
    figure_of_merit(
        "Final Step Timing",
        fom_regex=final_epoch_regex,
        group_name="train_step_timing",
        log_file="{processed_log_file}",
    )

    per_epoch_regex = (
        r"Epoch (?P<epoch_id>[0-9]+):\s+:\s+(?P<pct_complete>[0-9]+)%\|.*"
        + r"\|\s+(?P<step_idx>[0-9]+)\/(?P<max_itr>[0-9]+)\s+\[(?P<elapsed_time>[0-9:]+)"
        + r"<(?P<remaining_time>[0-9:]+)(,\s+v_num=(?P<v_num>.*?))?"
        + r",\s+reduced_train_loss=(?P<reduced_train_loss>[0-9\.]+)"
        + r",\s+global_step=(?P<global_step>[0-9\.]+)"
        + r",\s+consumed_samples=(?P<consumed_samples>[0-9\.]+)"
        + r",\s+train_step_timing in s=(?P<train_step_timing>[0-9\.]+)"
        + r"(,\s+val_loss=(?P<val_loss>[0-9\.]+))?\]"
    )

    epoch_context_name = "Epoch ID - Step ID"
    figure_of_merit_context(
        epoch_context_name,
        regex=per_epoch_regex,
        output_format="{epoch_id}-{step_idx}/{max_itr}",
    )
    figure_of_merit(
        "Epoch ID",
        fom_regex=per_epoch_regex,
        group_name="epoch_id",
        log_file="{processed_log_file}",
        contexts=[epoch_context_name],
    )
    figure_of_merit(
        "Percent Complete",
        fom_regex=per_epoch_regex,
        group_name="pct_complete",
        units="%",
        log_file="{processed_log_file}",
        contexts=[epoch_context_name],
    )
    figure_of_merit(
        "Step ID",
        fom_regex=per_epoch_regex,
        group_name="step_idx",
        log_file="{processed_log_file}",
        contexts=[epoch_context_name],
    )
    figure_of_merit(
        "Elapsed Time",
        fom_regex=per_epoch_regex,
        group_name="elapsed_time",
        log_file="{processed_log_file}",
        contexts=[epoch_context_name],
    )
    figure_of_merit(
        "Remaining Time",
        fom_regex=per_epoch_regex,
        group_name="remaining_time",
        log_file="{processed_log_file}",
        contexts=[epoch_context_name],
    )
    figure_of_merit(
        "V Num",
        fom_regex=per_epoch_regex,
        group_name="v_num",
        log_file="{processed_log_file}",
        contexts=[epoch_context_name],
    )
    figure_of_merit(
        "Reduced Train Loss",
        fom_regex=per_epoch_regex,
        group_name="reduced_train_loss",
        log_file="{processed_log_file}",
        contexts=[epoch_context_name],
    )
    figure_of_merit(
        "Global Step",
        fom_regex=per_epoch_regex,
        group_name="global_step",
        log_file="{processed_log_file}",
        contexts=[epoch_context_name],
    )
    figure_of_merit(
        "Consumed Samples",
        fom_regex=per_epoch_regex,
        group_name="consumed_samples",
        log_file="{processed_log_file}",
        contexts=[epoch_context_name],
    )
    figure_of_merit(
        "Train Step Timing",
        fom_regex=per_epoch_regex,
        group_name="train_step_timing",
        log_file="{processed_log_file}",
        contexts=[epoch_context_name],
    )
    figure_of_merit(
        "Val Loss",
        fom_regex=per_epoch_regex,
        group_name="val_loss",
        log_file="{processed_log_file}",
        contexts=[epoch_context_name],
    )

    per_step_regex = (
        r"Training epoch\s(?P<epoch>[e0-9\.\-]+),\s.*iteration\s(?P<iteration>[e0-9\/\.\-]+)"
        r"[\s|]+lr:\s(?P<learning_rate>[e0-9\.\-]+)[\s|]+"
        r"global_batch_size:\s(?P<global_batch_size>[e0-9\.\-]+)"
        r"[\s|]+global_step:\s(?P<global_step>[e0-9\.\-]+)"
        r"[\s|]+reduced_train_loss:\s(?P<reduced_train_loss>[e0-9\.\-]+)"
        r"[\s|]+train_step_timing in s:\s(?P<train_step_timing>[e0-9\.\-]+)"
    )
    step_context_name = "Global Step ID"
    figure_of_merit_context(
        step_context_name,
        regex=per_step_regex,
        output_format="{global_step}",
    )
    figure_of_merit(
        "epoch",
        fom_regex=per_step_regex,
        group_name="epoch",
        log_file="{processed_log_file}",
        contexts=[step_context_name],
    )
    figure_of_merit(
        "iteration",
        fom_regex=per_step_regex,
        group_name="iteration",
        log_file="{processed_log_file}",
        contexts=[step_context_name],
    )
    figure_of_merit(
        "learning_rate",
        fom_regex=per_step_regex,
        group_name="learning_rate",
        log_file="{processed_log_file}",
        contexts=[step_context_name],
    )
    figure_of_merit(
        "reduced_train_loss",
        fom_regex=per_step_regex,
        group_name="reduced_train_loss",
        log_file="{processed_log_file}",
        contexts=[step_context_name],
    )
    figure_of_merit(
        "global_step",
        fom_regex=per_step_regex,
        group_name="global_step",
        log_file="{processed_log_file}",
        contexts=[step_context_name],
    )
    figure_of_merit(
        "train_step_timing",
        fom_regex=per_step_regex,
        group_name="train_step_timing",
        units="s",
        log_file="{processed_log_file}",
        contexts=[step_context_name],
    )

    success_criteria(
        "training-complete",
        mode="string",
        match=".*?`Trainer.fit` stopped: `max_steps=.*?` reached.",
        file="{processed_log_file}",
    )

    register_phase(
        "preprocess_log",
        pipeline="analyze",
        run_before=["analyze_experiments"],
    )

    def _preprocess_log(self, workspace, app_inst):
        log_file = get_file_path(
            canonicalize_path(self.expander.expand_var_name("log_file")),
            workspace,
        )

        if os.path.exists(log_file):
            with open(log_file, encoding="ISO-8859-1") as f:
                data = f.read()

            processed_log = self.expander.expand_var(
                "{experiment_run_dir}/processed_{experiment_name}.out"
            )

            with open(processed_log, "w+", encoding="utf-8") as f:
                f.write(
                    data.replace("\x13", "\n")
                    .replace("\x96\x88", "")
                    .replace("â", "")
                )
