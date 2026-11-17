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
from ramble.util.path import canonicalize_path


class PyCosmoflow(ExecutableApplication):
    """This is a an implementation of the CosmoFlow 3D convolutional neural
    network for benchmarking. It is written in TensorFlow with the Keras API
    and uses Horovod for distributed training.
    """

    name = "py-cosmoflow"

    tags("machine-learning", "hpc-ml", "tensorflow", "cosmology")

    default_config_string = "{default_config_value}"

    input_file(
        "cosmoUniverse_mini",
        url="https://portal.nersc.gov/project/dasrepo/cosmoflow-benchmark/cosmoUniverse_2019_05_4parE_tf_v2_mini.tar",
        description="Cosmoflow Universe - Mini input",
    )

    input_file(
        "cosmoUniverse",
        url="https://portal.nersc.gov/project/dasrepo/cosmoflow-benchmark/cosmoUniverse_2019_05_4parE_tf_v2.tar",
        description="Cosmoflow Universe - Main input",
    )

    input_file(
        "mlperf-hpc",
        url="https://github.com/mlcommons/hpc/archive/refs/heads/main.tar.gz",
        description="MLPerf HPC Repo",
    )

    executable(
        "execute",
        "python {mlperf-hpc}/cosmoflow/train.py -d --rank-gpu {cosmoflow_config}",
        use_mpi=True,
    )

    workload(
        "cosmoUniverse_mini",
        executables=["execute"],
        inputs=["cosmoUniverse_mini", "mlperf-hpc"],
    )

    workload(
        "cosmoUniverse",
        executables=["execute"],
        inputs=["cosmoUniverse", "mlperf-hpc"],
    )

    workload_group(
        "all_workloads", workloads=["cosmoUniverse_mini", "cosmoUniverse"]
    )

    workload_variable(
        "dockerfile_path",
        default="{workload_input_dir}/Dockerfile_{docker_tensorflow_version}",
        description="Dockerfile for cosmoflow from the MLPerf-HPC repo",
        workload_group="all_workloads",
    )

    workload_variable(
        "docker_tag_name",
        default="cosmoflow",
        description="Name of docker image tag",
        workload_group="all_workloads",
    )

    workload_variable(
        "docker_tag_version",
        default="1.0",
        description="Version of docker image tag",
        workload_group="all_workloads",
    )

    workload_variable(
        "docker_tensorflow_version",
        default="22.11-tf2-py3",
        description="Version of tensorflow base container to use",
        workload_group="all_workloads",
    )

    workload_variable(
        "cosmoflow_config",
        default=os.path.join("{experiment_run_dir}", "cosmo.yaml"),
        description="Name of generated input for cosmoflow",
        workload_group="all_workloads",
    )

    workload_variable(
        "data.data_dir",
        default="{cosmoUniverse_mini}",
        description="Cosmoflow Data Directory",
        workload_group="all_workloads",
    )

    workload_variable(
        "data.n_train",
        default="1024",
        description="Number of training data sets",
        workload="cosmoUniverse_mini",
    )

    workload_variable(
        "data.n_valid",
        default="1024",
        description="Number of valid data sets",
        workload="cosmoUniverse_mini",
    )

    workload_variable(
        "data.n_train",
        default="524288",
        description="Number of training data sets",
        workload="cosmoUniverse",
    )

    workload_variable(
        "data.n_valid",
        default="65536",
        description="Number of valid data sets",
        workload="cosmoUniverse",
    )

    workload_variable(
        "mlperf.org",
        default="ramble",
        description="Organization for reporting MLPerf results",
        workload_group="all_workloads",
    )

    workload_variable(
        "mlperf.division",
        default="experiments",
        description="Division for reporting MLPerf results",
        workload_group="all_workloads",
    )

    workload_variable(
        "mlperf.status",
        default="unknown",
        description="Cluster status for reporting MLPerf results",
        workload_group="all_workloads",
    )

    workload_variable(
        "mlperf.platform",
        default="unknown",
        description="Platform name for reporting MLPerf results",
        workload_group="all_workloads",
    )

    workload_variable(
        "output_dir",
        default="{experiment_run_dir}",
        description="Experiment output directory",
        workload_group="all_workloads",
    )

    workload_variable(
        "cosmoflow_base_config",
        default=os.path.join(
            "{mlperf-hpc}", "cosmoflow", "configs", "cosmo.yaml"
        ),
        description="Base configuration file to generate cosmoflow inputs from",
        workload_group="all_workloads",
    )

    figure_of_merit(
        "Best Epoch",
        fom_regex=r".*?INFO\s+epoch: (?P<idx>[0-9]+)",
        group_name="idx",
        units="",
    )

    figure_of_merit(
        "Best Epoch Loss",
        fom_regex=r".*?INFO\s+loss: (?P<loss>[0-9\.]+)",
        group_name="loss",
        units="",
    )

    figure_of_merit(
        "Best Epoch LR",
        fom_regex=r".*?INFO\s+lr: (?P<lr>[0-9\.]+)",
        group_name="lr",
        units="",
    )

    figure_of_merit(
        "Best Epoch Mean Absolute Error",
        fom_regex=r".*?INFO\s+mean_absolute_error: (?P<abs_err>[0-9\.]+)",
        group_name="abs_err",
        units="",
    )

    figure_of_merit(
        "Best Epoch Time",
        fom_regex=r".*?INFO\s+time: (?P<time>[0-9\.]+)",
        group_name="time",
        units="s",
    )

    figure_of_merit(
        "Best Epoch Val Loss",
        fom_regex=r".*?INFO\s+val_loss: (?P<val_loss>[0-9\.]+)",
        group_name="val_loss",
        units="",
    )

    figure_of_merit(
        "Best Epoch Val Mean Absolute Error",
        fom_regex=r".*?INFO\s+val_mean_absolute_error: (?P<val_error>[0-9\.]+)",
        group_name="val_error",
        units="",
    )

    figure_of_merit(
        "Total epoch time",
        fom_regex=r".*?INFO\s+Total epoch time: (?P<total_time>[0-9\.]+)",
        group_name="total_time",
        units="s",
    )

    figure_of_merit(
        "Mean epoch time",
        fom_regex=r".*?INFO\s+Mean epoch time: (?P<mean_time>[0-9\.]+)",
        group_name="mean_time",
        units="s",
    )

    register_phase(
        "create_cosmoflow_dockerfile",
        pipeline="setup",
        run_after=["get_inputs"],
        run_before=["ingest_default_configs"],
    )

    def _create_cosmoflow_dockerfile(self, workspace, app_inst):
        """Render the template Dockerfile for building"""

        base_dockerfile = canonicalize_path(
            os.path.join(os.path.dirname(self._file_path), "Dockerfile")
        )

        # Avoid problems with missing docker file, but this shouldn't happen
        # because the file is next to the modifier.py
        #  if not os.path.exists(base_dockerfile):
        #  return

        new_dockerfile_path = self.expander.expand_var_name("dockerfile_path")
        dockerfile_dir = os.path.dirname(new_dockerfile_path)
        mkdirp(dockerfile_dir)

        with open(base_dockerfile, encoding="utf-8") as f:
            dockerfile = f.read()

        with open(new_dockerfile_path, "w+", encoding="utf-8") as f:
            f.write(self.expander.expand_var(dockerfile))

    register_phase(
        "ingest_default_configs", pipeline="setup", run_after=["get_inputs"]
    )

    def _ingest_default_configs(self, workspace, app_inst):
        """Read config options from nemo_base_config, and define any that were
        not defined in the input ramble.yaml or workload definition."""

        base_config = get_file_path(
            canonicalize_path(
                self.expander.expand_var_name("cosmoflow_base_config")
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

    register_phase(
        "write_config", pipeline="setup", run_after=["make_experiments"]
    )

    def _write_config(self, workspace, app_inst):

        base_config = get_file_path(
            canonicalize_path(
                self.expander.expand_var_name("cosmoflow_base_config")
            ),
            workspace,
        )

        if not os.path.exists(base_config):
            return

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

        # Set output dir:
        ramble.util.yaml_generation.set_config_value(
            config_data,
            "output_dir",
            self.expander.expand_var_name("output_dir"),
        )

        # Create string of yaml data.
        config_str = yaml.dump(
            config_data,
            default_flow_style=False,
            width=syaml.maxint,
            Dumper=syaml.OrderedLineDumper,
        )

        # Write out experiment config
        config_path = canonicalize_path(
            self.expander.expand_var("{cosmoflow_config}"),
        )

        with open(config_path, "w+", encoding="utf-8") as f:
            f.write(config_str)
