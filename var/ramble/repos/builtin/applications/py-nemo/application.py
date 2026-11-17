# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import os

from ruamel import yaml

import ramble.util.ramble_yaml as syaml
import ramble.util.yaml_generation
from ramble.appkit import *
from ramble.base_app.builtin.py_nemo import PyNemo as BasePyNemo

from spack.util.path import canonicalize_path


class PyNemo(BasePyNemo):
    """A scalable generative AI framework built for researchers and
    developers working on Large Language Models, Multimodal, and
    Speech AI (Automatic Speech Recognition and Text-to-Speech)

    model.ffn_hidden_size gets a default value of {4*{model.hidden_size}} if it
    can not be cast to an integer from the default config.
    """

    name = "py-nemo"

    maintainers("douglasjacobsen")

    archive_pattern("{experiment_run_dir}/{nemo_generated_config_name}")

    executable(
        "setup_transformer_cache",
        'bash -c "python3 -c \'from transformers import AutoTokenizer; AutoTokenizer.from_pretrained(\\"gpt2\\")\'"',
        use_mpi=True,
    )

    executable(
        "pretraining_exec",
        'bash -c "cd /opt/NeMo; git rev-parse HEAD; '
        "{custom_injected_string}; "
        "python3 -u /opt/NeMo/examples/nlp/language_modeling/megatron_gpt_pretraining.py "
        '--config-path={nemo_generated_config_path} --config-name={nemo_generated_config_name}"',
        use_mpi=True,
    )

    executable(
        "create_logs", "mkdir {exp_manager.explicit_log_dir}", use_mpi=False
    )

    input_file(
        "nemo_fetched_config",
        url="https://raw.githubusercontent.com/NVIDIA/NeMo-Framework-Launcher/refs/tags/{nemo_launcher_tag}/launcher_scripts/conf/{nemo_stage}/{nemo_model}/{nemo_config_name}.yaml",
        expand=False,
        target_dir="{model_inputs}",
        description="Base config for NeMo experiments",
    )

    workload(
        "pretraining",
        executables=[
            "create_logs",
            "setup_transformer_cache",
            "pretraining_exec",
        ],
        inputs=["nemo_fetched_config"],
    )

    workload_group("all_workloads", workloads=["pretraining"])
    workload_group("pretraining", workloads=["pretraining"])

    default_config_string = "{default_config_value}"

    workload_variable(
        "model_inputs",
        default="{workload_input_dir}/{nemo_stage}/{nemo_model}",
        description="NeMo model input directory",
        workload_group="pretraining",
    )

    workload_variable(
        "nemo_launcher_tag",
        default="24.07",
        description="Tag of NeMo-Framework-Launcher repo to extract inputs from (1.0 only)",
        workload_group="pretraining",
    )

    workload_variable(
        "nemo_model",
        default="gpt3",
        description="Model to run in NeMo",
        workload_group="pretraining",
    )

    workload_variable(
        "nemo_config_name",
        default="5b",
        description="Configuration name to run in NeMo. This is the name of the input "
        + "yaml file without the extension. e.g. 5b.yaml -> 5b, while "
        + "mixtral_8x22b.yaml -> mixtral_8x22b",
        workload_group="pretraining",
    )

    workload_variable(
        "nemo_base_config",
        default="{nemo_fetched_config}",
        description="Path to base config used for generating experiments. "
        + "Defaults to the fetched input, but can refer to a provided input.",
        workload_group="pretraining",
    )

    workload_variable(
        "nemo_generated_config_name",
        default="nemo.yaml",
        description="Name of nemo config file",
        workload_group="pretraining",
    )

    workload_variable(
        "nemo_generated_config_path",
        default="{experiment_run_dir}",
        description="Path where nemo config file is contained",
        workload_group="pretraining",
    )

    workload_variable(
        "nemo_remove_variables",
        default=[],
        description="Name of variables to remove from the base nemo config",
        workload_group="pretraining",
    )

    with when("+containerized"):
        workload_variable(
            "logs_mount",
            default="{exp_manager.explicit_log_dir}:{exp_manager.explicit_log_dir}",
            description="Container mount for results data",
            workload_group="pretraining",
        )

        workload_variable(
            "results_mount",
            default="{experiment_run_dir}:{experiment_run_dir}",
            description="Container mount for results data",
            workload_group="pretraining",
        )

        environment_variable(
            "NEMO_CONTAINER_MOUNTS",
            value="{logs_mount},{results_mount}",
            description="All container mounts in an environment variable",
            workload_group="pretraining",
        )

        workload_variable(
            "container_mounts",
            default="{logs_mount},{results_mount}",
            description="All container mounts in a ramble variable",
            workload_group="pretraining",
        )

    # Run parameters
    workload_variable(
        "run.name",
        default="{nemo_model}_{nemo_config_name}",
        description="Name of run",
        workload_group="pretraining",
    )
    workload_variable(
        "run.results_dir",
        default="{experiment_run_dir}",
        description="Experiment results directory",
        workload_group="pretraining",
    )
    workload_variable(
        "run.time_limit",
        default="6-00:00:00",
        description="Experiment time limit",
        workload_group="pretraining",
    )
    workload_variable(
        "run.dependency",
        default="singleton",
        description="Experiment dependency type",
        workload_group="pretraining",
    )

    # Trainer parameters
    workload_variable(
        "trainer.num_nodes",
        default="{n_nodes}",
        description="Number of nodes",
        workload_group="pretraining",
    )
    workload_variable(
        "trainer.devices",
        default="{gpus_per_node}",
        description="Number of devices per node",
        workload_group="pretraining",
    )
    workload_variable(
        "trainer.accelerator",
        default="gpu",
        description="Accelerator to use as device",
        workload_group="pretraining",
    )

    # Exp manager parameters
    workload_variable(
        "exp_manager.explicit_log_dir",
        default="{experiment_run_dir}/nemo_logs",
        description="Log directory for exp manager",
        workload_group="pretraining",
    )
    workload_variable(
        "exp_manager.exp_dir",
        default=None,
        description="Experiment directory for exp manager",
        workload_group="pretraining",
    )
    workload_variable(
        "exp_manager.name",
        default="{nemo_stage}_{nemo_model}_{nemo_config_name}",
        description="Exp manager name",
        workload_group="pretraining",
    )
    workload_variable(
        "exp_manager.wandb_logger_kwargs.project",
        default="nemo_{nemo_model}",
        description="wandb logger project",
        workload_group="pretraining",
    )
    workload_variable(
        "exp_manager.wandb_logger_kwargs.name",
        default="{nemo_model}_{nemo_config_name}",
        description="wandb logger name",
        workload_group="pretraining",
    )
    workload_variable(
        "exp_manager.checkpoint_callback_params.model_parallel_size",
        default="{model.tensor_model_parallel_size}*{model.pipeline_model_parallel_size}",
        description="Parallel size",
        workload_group="pretraining",
    )

    register_phase(
        "ingest_default_configs",
        pipeline="setup",
        run_before=["make_experiments"],
    )

    def _ingest_default_configs(self, workspace, app_inst):
        """Read config options from nemo_base_config, and define any that were
        not defined in the input ramble.yaml or workload definition."""

        base_config = get_file_path(
            canonicalize_path(
                self.expander.expand_var_name("nemo_base_config")
            ),
            workspace,
        )

        # Avoid problems with missing base config files
        if not os.path.exists(base_config):
            return

        config_data = ramble.util.yaml_generation.read_config_file(base_config)

        for option_name in ramble.util.yaml_generation.all_config_options(
            config_data
        ):
            if option_name not in self.variables:
                value = ramble.util.yaml_generation.get_config_value(
                    config_data, option_name
                )

                self.define_variable(option_name, value)

        # Ensure a default for ffn_hidden_size if not already set, and not an integer.
        ffn_hidden_size = ramble.util.yaml_generation.get_config_value(
            config_data, "model.ffn_hidden_size"
        )
        try:
            ffn_hidden_size = int(ffn_hidden_size)
        except ValueError:
            logger.warn(
                "NeMo attribute model.ffn_hidden_size can not be cast to an integer. "
                "Replacing with '{4*{model.hidden_size}}' to ensure this experiment runs."
            )
            ffn_hidden_size = "{4*{model.hidden_size}}"
        self.define_variable("model.ffn_hidden_size", ffn_hidden_size)

    register_phase(
        "write_config", pipeline="setup", run_after=["make_experiments"]
    )

    def _write_config(self, workspace, app_inst):
        base_config = get_file_path(
            canonicalize_path(
                self.expander.expand_var_name("nemo_base_config")
            ),
            workspace,
        )

        # Avoid errors for missing base config files
        if not os.path.exists(base_config):
            return

        # Remove all variables that should be removed
        remove_vars = self.expander.expand_var_name(
            "nemo_remove_variables", merge_used_stage=False, typed=True
        )
        self.expander.flush_used_variable_stage()

        config_data = ramble.util.yaml_generation.read_config_file(base_config)

        ramble.util.yaml_generation.apply_default_config_values(
            config_data, self, self.default_config_string
        )

        # Set config options in config_data
        for var_name in self.variables:
            if "." in var_name and len(var_name.split(".")) > 1:
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

                ramble.util.yaml_generation.set_config_value(
                    config_data, var_name, var_val, force=True
                )

        # Remove requested options
        for var_name in remove_vars:
            if "." in var_name and len(var_name.split(".")) > 1:
                ramble.util.yaml_generation.remove_config_value(
                    config_data, var_name
                )

        config_path = canonicalize_path(
            os.path.join(
                self.expander.expand_var("{nemo_generated_config_path}"),
                self.expander.expand_var("{nemo_generated_config_name}"),
            )
        )

        # Ensure all instances of ${data_dir} are replaced correctly
        config_str = yaml.dump(
            config_data,
            default_flow_style=False,
            width=syaml.maxint,
            Dumper=syaml.OrderedLineDumper,
        )

        config_str = config_str.replace(
            "${data_dir}",
            self.expander.expand_var("{workload_input_dir}/data"),
        )
        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(config_str)
