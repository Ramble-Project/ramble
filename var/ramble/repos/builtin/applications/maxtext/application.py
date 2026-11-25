# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import glob
import json
import os

from ruamel.yaml.error import YAMLError

import ramble.util.ramble_yaml as ryaml
from ramble.appkit import *
from ramble.expander import Expander
from ramble.util import stats
from ramble.util.path import canonicalize_path


class Maxtext(ExecutableApplication):
    """MaxText is a high performance, highly scalable, open-source LLM written
    in pure Python/Jax and targeting Google Cloud TPUs and GPUs for training
    and inference. MaxText achieves high MFUs and scales from single host to
    very large clusters while staying simple and "optimization-free" thanks to
    the power of Jax and the XLA compiler.
    """

    name = "maxtext"

    maintainers("dapomeroy")

    tags("machine-learning", "llm", "jax", "cuda")

    executable(
        "train",
        template=[
            "bash -c 'METRICS_FILE=\"{metrics_file}\"; python3 {train_path} {config_path} run_name={run_name} metrics_file=$METRICS_FILE'"
        ],
        use_mpi=True,
    )

    input_file(
        "base_config",
        url="{base_config_source}",
        description="Base configuration base.yml",
        expand=False,
    )
    input_file(
        "model_config",
        url="{model_config_source}",
        description="Additional config to override base.yml",
        expand=False,
    )

    workload(
        "train", executable="train", inputs=["base_config", "model_config"]
    )
    all_workloads = ["train"]

    run_name = (
        Expander.expansion_str("experiment_name") + "_$(date +%Y-%m-%d-%H-%M)"
    )

    # Maxtext configuration and runtime parameters
    # To add Maxtext model inputs as experiment variables in Ramble, prefix them with 'maxtext.' in ramble.yaml
    workload_variable(
        "maxtext_path",
        default="$HOME/maxtext",
        description="Path to maxtext root",
        workloads=all_workloads,
    )
    workload_variable(
        "train_path",
        default="{maxtext_path}/MaxText/train.py",
        description="Path to train.py",
        workloads=all_workloads,
    )
    workload_variable(
        "config_path",
        default="{experiment_run_dir}/base.yml",
        description="Path to config",
        workloads=all_workloads,
    )
    workload_variable(
        "base_config_source",
        default="{maxtext_path}/MaxText/configs/base.yml",
        description="Path or URL to base config",
        workloads=all_workloads,
    )
    workload_variable(
        "model_config_source",
        default="None",
        description="path or URL to secondary model config",
        workloads=all_workloads,
    )
    workload_variable(
        "run_name",
        default=run_name,
        description="Run name",
        workloads=all_workloads,
    )
    workload_variable(
        "metrics_file",
        default="{experiment_run_dir}/metrics_{workflow_node_id}.txt",
        description="For testing, local file that stores scalar metrics. If empty, no metrics are written.",
        workloads=all_workloads,
    )

    # Pyxis/Enroot parameters
    with when("+containerized"):
        workload_variable(
            "maxtext_mount",
            default="{maxtext_path}:{maxtext_path}",
            description="Container mount for maxtext root",
            workloads=all_workloads,
        )
        workload_variable(
            "container_mounts",
            default="{maxtext_mount}",
            description="All container mounts in a ramble variable",
            workloads=all_workloads,
        )

    log_str = os.path.join("{experiment_run_dir}", "metrics.out")
    float_or_sci_regex = r"[+-]?[0-9]+(?:\.[0-9]*(?:[eE][+-]?[0-9]+)?)?"

    # Summary FOMs over all steps
    figure_of_merit(
        "Total TFLOPS",
        log_file=log_str,
        fom_regex=r"Total TFLOPS: (?P<totaltflops>[0-9\.]+)",
        group_name="totaltflops",
        units="TFLOPS",
    )
    figure_of_merit(
        "Total Weights",
        log_file=log_str,
        fom_regex=r"Total Weights: (?P<totalweights>[0-9\.]+)",
        group_name="totalweights",
        units="weights",
    )
    figure_of_merit(
        "Total Steps",
        log_file=log_str,
        fom_regex=r"Total Steps: (?P<totalsteps>[0-9\.]+)",
        group_name="totalsteps",
        units="steps",
    )
    figure_of_merit(
        "Number of Devices",
        log_file=log_str,
        fom_regex=r"Number of Devices: (?P<numdevices>[0-9\.]+)",
        group_name="numdevices",
        units="devices",
    )

    # Step FOMs
    fom_parts = [
        ("Step", "step", r"[0-9\.]+"),
        ("Avg Seconds", "secs", r"[0-9\.]+"),
        ("Avg TFLOP/s/device", "tflops", r"[0-9\.]+"),
        ("Avg Tokens/device", "tokens", r"[0-9\.]+"),
        ("Avg Tokens/s/device", "tokens_sec", r"[0-9\.]+"),
        ("Avg Loss", "loss", float_or_sci_regex),
        ("Avg MoE Load Balancing Loss", "moe_lb_loss", float_or_sci_regex),
        ("Avg Grad Norm", "grad_norm", float_or_sci_regex),
        ("Avg Param Norm", "param_norm", float_or_sci_regex),
        ("Avg Raw Grad Norm", "raw_grad_norm", float_or_sci_regex),
        ("Avg Current Learning Rate", "learn_rate", float_or_sci_regex),
    ]

    fom_regex = ""
    for fom_name, fom_group, fom_part_regex in fom_parts:
        fom_regex += rf"\s*{fom_name}:\s+(?P<{fom_group}>{fom_part_regex}),*"

    figure_of_merit_context("step", regex=fom_regex, output_format="{step}")
    figure_of_merit(
        "Avg Seconds",
        log_file=log_str,
        fom_regex=fom_regex,
        group_name="secs",
        units="s",
        contexts=["step"],
    )
    figure_of_merit(
        "Avg TFLOP Per Second Per Device",
        log_file=log_str,
        fom_regex=fom_regex,
        group_name="tflops",
        units="TFLOP/s/device",
        contexts=["step"],
    )
    figure_of_merit(
        "Avg Tokens Per Device",
        log_file=log_str,
        fom_regex=fom_regex,
        group_name="tokens",
        units="Tokens/device",
        contexts=["step"],
    )
    figure_of_merit(
        "Avg Tokens Per Second Per Device",
        log_file=log_str,
        fom_regex=fom_regex,
        group_name="tokens_sec",
        units="Tokens/s/device",
        contexts=["step"],
    )
    figure_of_merit(
        "Avg Loss",
        log_file=log_str,
        fom_regex=fom_regex,
        group_name="loss",
        units="",
        contexts=["step"],
    )
    figure_of_merit(
        "Avg MoE Load Balancing Loss",
        log_file=log_str,
        fom_regex=fom_regex,
        group_name="moe_lb_loss",
        units="",
        contexts=["step"],
    )
    figure_of_merit(
        "Avg Grad Norm",
        log_file=log_str,
        fom_regex=fom_regex,
        group_name="grad_norm",
        units="",
        contexts=["step"],
    )
    figure_of_merit(
        "Avg Param Norm",
        log_file=log_str,
        fom_regex=fom_regex,
        group_name="param_norm",
        units="",
        contexts=["step"],
    )
    figure_of_merit(
        "Avg Raw Grad Norm",
        log_file=log_str,
        fom_regex=fom_regex,
        group_name="raw_grad_norm",
        units="",
        contexts=["step"],
    )
    figure_of_merit(
        "Avg Current Learning Rate",
        log_file=log_str,
        fom_regex=fom_regex,
        group_name="learn_rate",
        units="",
        contexts=["step"],
    )

    def _get_inputs(self, workspace, app_inst):
        try:
            super()._get_inputs(workspace, app_inst)
        except Exception:
            pass  # Override get_inputs errors and instead check files below

        if not workspace.dry_run:
            base_config = app_inst.expander.expand_var("{base_config}")
            if not os.path.exists(base_config):
                logger.die(f"Base config file not found: {base_config}")

            model_config = app_inst.expander.expand_var("{model_config}")
            if not os.path.exists(model_config):
                logger.debug(f"Model config file not found: {model_config}")

    register_phase(
        "create_config", pipeline="setup", run_after=["make_experiments"]
    )

    def _create_config(self, workspace, app_inst):
        """Ramble will load the base.yml config from the MaxText Spack install
        directory, update the variables for each experiment, and write a new
        base.yml config into each experiment directory.

        Variables are updated with the following order of precedence:
          1) As defined in ramble.yaml, if specified
          2) As defined in base.yml, if specified
          3) Default specified in this file

        Any variables defined in the base.yml that are not specified in this
        file as a workload_variable will pass through unaltered."""

        base_config = get_file_path(
            canonicalize_path(app_inst.expander.expand_var("{base_config}")),
            workspace,
        )

        # Avoid problems with missing base config files
        if not os.path.exists(base_config):
            return

        with open(base_config, encoding="utf-8") as conf:
            try:
                config_data = ryaml.load(conf)
                logger.debug(f"Loaded config as dict: \n{config_data}")
            except YAMLError:
                logger.die(
                    "YAML Error: Failed to load config file: {base_config}"
                )

        # Update base config with secondary model config, if it exists
        model_config = get_file_path(
            canonicalize_path(app_inst.expander.expand_var("{model_config}")),
            workspace,
        )

        model_config_data = {}
        if os.path.exists(model_config):
            with open(model_config, encoding="utf-8") as conf:
                try:
                    model_config_data = ryaml.load(conf)
                    logger.debug(
                        f"Loaded config as dict: \n{model_config_data}"
                    )

                    for var_name, var_val in model_config_data.items():
                        config_data[var_name] = var_val
                except YAMLError:
                    logger.die("YAML Error: Failed to load config file.")

        # Set config options prefixed with 'maxtext.' from Ramble variables in config_data
        for var_name in self.variables:
            if "maxtext." in var_name and len(var_name.split(".")) > 1:
                var_val = self.expander.expand_var(
                    self.expander.expansion_str(var_name), typed=True
                )

                # Convert any invalid tuples back to their default strings.
                if isinstance(var_val, tuple):
                    var_val = self.expander.expand_var(
                        self.expander.expansion_str(var_name)
                    )
                elif isinstance(var_val, list):
                    for i in range(len(var_val)):
                        var_val[i] = self.expander.expand_var(
                            var_val[i], typed=True
                        )

                config_data[var_name.removeprefix("maxtext.")] = var_val

        new_config_path = os.path.join(
            self.expander.experiment_run_dir, "base.yml"
        )

        with open(new_config_path, "w", encoding="utf-8") as config_out:
            config_out.write(
                f"# This config was generated by Ramble from source config(s): \n# {base_config}"
            )
            if model_config_data:
                config_out.write(f"\n# {model_config}")
            config_out.write("\n")
            ryaml.dump(config_data, default_flow_style=True, stream=config_out)

    def _prepare_analysis(self, workspace, app_inst):
        """Reads JSON metrics_files output from MaxText and formats them in a new file
        to be processed as FOMs by Ramble."""

        metrics_filename = get_file_path(
            canonicalize_path(
                app_inst.expander.expand_var_name("metrics_file")
            ),
            workspace,
        )

        # Avoid issues with non-existent metrics files
        if not os.path.exists(metrics_filename):
            return

        workflow_node_id = app_inst.expander.expand_var_name(
            "workflow_node_id"
        )
        if workflow_node_id in metrics_filename:
            metrics_filename = metrics_filename.replace(workflow_node_id, "*")
            logger.debug(
                f"Workflow node ID expansion detected. Searching for files with pattern {metrics_filename}"
            )

        metrics_path = os.path.join(
            app_inst.expander.experiment_run_dir, metrics_filename
        )
        metrics_files = sorted(glob.glob(metrics_path))

        if not metrics_files:
            logger.die(
                f"Unable to locate metrics file(s) at:\n    {metrics_path}"
            )

        imported_metrics_data = []
        for file in metrics_files:
            try:
                with open(file, encoding="utf-8") as f:
                    imported_metrics_data.append(f.read().strip())
            except FileNotFoundError:
                logger.debug(f"File not found: {file}")
            except Exception as e:
                logger.debug(f"An error occurred when reading file: {file}\n")
                logger.debug(f"Error: {e}")
        imported_metrics_data = "\n".join(imported_metrics_data)

        aggregated_metrics = {}
        metrics_list = []
        total_tflops = None
        total_weights = None
        num_devices = None

        expected_metrics = {
            "perf/step_time_seconds": "Seconds",
            "perf/per_device_tflops_per_sec": "TFLOP/s/device",
            "perf/per_device_tokens": "Tokens/device",
            "perf/per_device_tokens_per_sec": "Tokens/s/device",
            "learning/loss": "Loss",
            "learning/moe_lb_loss": "MoE Load Balancing Loss",
            "learning/grad_norm": "Grad Norm",
            "learning/param_norm": "Param Norm",
            "learning/raw_grad_norm": "Raw Grad Norm",
            "learning/current_learning_rate": "Current Learning Rate",
        }

        try:
            for line in imported_metrics_data.splitlines():
                line_dict = json.loads(line)
                current_step = line_dict["step"]

                if not total_tflops:
                    total_tflops = line_dict["perf/per_device_tflops"]
                if not total_weights:
                    total_weights = line_dict["learning/total_weights"]

                if current_step not in aggregated_metrics:
                    aggregated_metrics[current_step] = {}

                for metric in expected_metrics:
                    if metric not in aggregated_metrics[current_step]:
                        aggregated_metrics[current_step][metric] = [
                            line_dict[metric]
                        ]
                    else:
                        aggregated_metrics[current_step][metric].append(
                            line_dict[metric]
                        )

            for step, data in aggregated_metrics.items():
                formatted_metrics = [f"Step: {step}"]

                for metric, title in expected_metrics.items():
                    metric_values = data[metric]

                    if metric_values:
                        if not num_devices:
                            num_devices = len(metric_values)

                        mean = stats.StatsMean()
                        formatted_metrics.append(
                            f"Avg {title}: {mean.compute(metric_values)}"
                        )
                    else:
                        logger.debug(
                            "No data found for Step {step} metric {metric}"
                        )

                line_out = ", ".join(formatted_metrics)
                metrics_list.append(line_out)

            metrics_outfile_path = os.path.join(
                app_inst.expander.experiment_run_dir, "metrics.out"
            )

            with open(
                metrics_outfile_path, "w", encoding="utf-8"
            ) as metrics_out:
                metrics_out.write(f"Total TFLOPS: {total_tflops}\n")
                metrics_out.write(f"Total Weights: {total_weights}\n")
                metrics_out.write(
                    f"Total Steps: {max(aggregated_metrics.keys()) + 1}\n"
                )
                metrics_out.write(f"Number of Devices: {num_devices}\n")
                for line in metrics_list:
                    metrics_out.write(line + "\n")

        except Exception as e:
            logger.die(f"Error reading metrics data: {e}")
