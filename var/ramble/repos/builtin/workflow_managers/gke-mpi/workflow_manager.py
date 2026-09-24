# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import shutil
import textwrap

from ramble.wmkit import *

from spack.util.executable import Executable, ProcessError


class GkeMpi(WorkflowManagerBase):
    """GKE workflow manager that uses the MPI operator"""

    name = "gke-mpi"

    maintainers("linsword13")

    tags("workflow", "gke", "mpi")

    variant(
        "containerized",
        default=True,
        description="GKE MPI runs in containers",
    )

    workflow_manager_variable(
        name="job_name",
        default="{application_name}-{workload_name}-{experiment_name}",
        description="GKE job name",
    )

    workflow_manager_variable(
        name="extra_metadata",
        default="",
        description="Extra line-separated key:val pairs for the metadata section",
    )

    workflow_manager_variable(
        name="cores_per_node",
        default="{processes_per_node}",
        description="Cores per node",
    )

    workflow_manager_variable(
        name="container_image",
        default="",
        description="url to the container image",
    )

    workflow_manager_variable(
        name="extra_container_config_files",
        default="",
        description="extra line-separated list of config files to be mapped to containers",
    )

    workflow_manager_variable(
        name="container_work_dir",
        default="/config",
        description="working directory inside the container",
    )

    workflow_manager_variable(
        name="launcher_execute_script_template",
        default="launcher_execute_script.tpl",
        description="execute script template for the launcher",
    )

    register_template(
        name="launcher_execute_script",
        src_path="{launcher_execute_script_template}",
    )

    workflow_manager_variable(
        name="worker_execute_script_template",
        default="worker_execute_script.tpl",
        description="execute script template for the workers",
    )

    register_template(
        name="worker_execute_script",
        src_path="{worker_execute_script_template}",
    )

    register_template(
        name="gke_mpi_yaml",
        src_path="gke_mpi.yaml.tpl",
        dest_path="gke_mpi.yaml",
        extra_vars_func="gke_mpi_yaml_vars",
    )

    def _gke_mpi_yaml_vars(self):
        expander = self.app_inst.expander
        extra_metadata_str = expander.expand_var_name("extra_metadata")
        launcher_script = expander.expand_var_name("launcher_execute_script")
        worker_script = expander.expand_var_name("worker_execute_script")
        if extra_metadata_str:
            extra_metadata_section = textwrap.indent(
                extra_metadata_str, " " * 2
            )
        else:
            extra_metadata_section = ""

        return {
            "extra_metadata_section": extra_metadata_section,
            "launcher_script_path": os.path.join(
                "/config", os.path.basename(launcher_script)
            ),
            "worker_script_path": os.path.join(
                "/config", os.path.basename(worker_script)
            ),
        }

    register_template(
        name="kustomization.yaml",
        src_path="kustomization.yaml.tpl",
        dest_path="kustomization.yaml",
        extra_vars_func="kustomization_yaml_vars",
    )

    def _kustomization_yaml_vars(self):
        files = ["{launcher_execute_script}", "{worker_execute_script}"]
        expander = self.app_inst.expander
        extra_files_str = expander.expand_var_name(
            "extra_container_config_files"
        )
        if extra_files_str:
            files.extend(extra_files_str.split("\n"))
        file_lines = "\n".join(
            [expander.expand_var(f.lstrip("- ")) for f in files]
        )
        lines = [
            "configMapGenerator:",
            "- name: gke-mpi-config",
            "  files:",
            textwrap.indent(file_lines, "  - "),
            "generatorOptions:",
            # For some reason kustomization does not apply the generated name properly.
            # So disable the suffix as a workaround.
            "  disableNameSuffixHash: true",
        ]
        config_map_gen_section = "\n".join(lines)
        return {
            "config_map_gen_section": config_map_gen_section,
        }

    register_template(
        name="batch_submit",
        src_path="batch_submit.tpl",
        dest_path="batch_submit",
    )

    register_template(
        name="batch_query",
        src_path="batch_query.tpl",
        dest_path="batch_query",
    )

    register_template(
        name="batch_cancel",
        src_path="batch_cancel.tpl",
        dest_path="batch_cancel",
    )

    # A convenience for printing the deployment config
    register_template(
        name="batch_print_deployment",
        src_path="batch_print_deployment.tpl",
        dest_path="batch_print_deployment",
    )

    def _prepare_analysis(self, workspace):
        if workspace.dry_run:
            return
        expander = self.app_inst.expander
        query_script = expander.expand_var_name("batch_query")
        query_cmd = Executable(query_script)
        try:
            query_cmd(output=os.devnull)
        except ProcessError as e:
            logger.warn(f"batch_query returns error {e}")
        run_dir = expander.expand_var_name("experiment_run_dir")
        launcher_log = os.path.join(run_dir, "launcher.log")
        if os.path.exists(launcher_log):
            log_file = expander.expand_var_name("log_file")
            shutil.copy2(launcher_log, log_file)

    def get_status(self, workspace):
        """Return status of a given job"""
        return
