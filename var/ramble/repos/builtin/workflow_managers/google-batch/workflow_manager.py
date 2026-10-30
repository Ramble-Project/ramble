# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

from ruamel import yaml

from ramble.experiment_result import ExperimentStatus
from ramble.util import shell_utils
from ramble.wmkit import *

from spack.util.executable import ProcessError

# Mapping from batch status to Ramble status
_STATUS_MAP = {
    "UNRESOLVED": ExperimentStatus.UNRESOLVED,
    "UNQUEUED": ExperimentStatus.UNQUEUED,
    "QUEUED": ExperimentStatus.SUBMITTED,
    "SCHEDULED": ExperimentStatus.SUBMITTED,
    "FAILED": ExperimentStatus.FAILED,
    "RUNNING": ExperimentStatus.RUNNING,
    "SUCCEEDED": ExperimentStatus.COMPLETE,
    "DELETION_IN_PROGRESS": ExperimentStatus.CANCELLED,
}


class GoogleBatch(WorkflowManagerBase):
    """Google Batch workflow manager"""

    name = "google-batch"

    maintainers("douglasjacobsen")

    tags("workflow", "google", "batch")

    workflow_manager_family("google-batch")

    def __init__(self, file_path):
        super().__init__(file_path)

        self.runner = GcloudRunner()

    workflow_manager_variable(
        "workflow_banner",
        default="""# ****************************************************
# * Workflow manager: google-batch
# * Submission command is: {batch_submit_cmd}
# * If this file is not part of the above path, it is unlikely that this file
# * is used when `ramble on` executes experiments.
# ****************************************************
""",
        description="Banner to describe the workflow within execution templates",
    )

    workflow_manager_variable(
        name="job_name",
        default='{simplify_str("{experiment_namespace}")}',
        description="Batch job name",
    )

    workflow_manager_variable(
        name="hostlist",
        default="`hostname`",
        description="hostlist variable used by various modifiers",
    )

    workflow_manager_variable(
        name="mpi_command",
        default="mpirun -n {n_ranks}",
        description="mpirun prefix, mostly served as an overridable default",
    )

    workflow_manager_variable(
        name="batch_machine_type",
        default="n2-standard-8",
        description="Default machine type for batch jobs.",
    )

    workflow_manager_variable(
        name="batch_machine_image",
        default="batch-hpc-rocky",
        values=["batch-cos", "batch-debian", "batch-hpc-rocky"],
        strict=False,
        description="Default machine image for batch jobs.",
    )

    workflow_manager_variable(
        name="batch_disk_size",
        default="30",
        description="Default machine size in GB for batch jobs.",
    )

    workflow_manager_variable(
        name="batch_job_zone",
        default="us-central1-a",
        description="Default zone for batch jobs.",
    )

    workflow_manager_variable(
        name="batch_job_region",
        default="us-central1",
        description="Default region for batch jobs.",
    )

    workflow_manager_variable(
        name="unformatted_batch_command",
        default="{unformatted_command_without_logs}",
        description="Command to expand and format for batch execution",
    )

    workflow_manager_variable(
        name="batch_project",
        default="",
        description="Google Cloud Platform Project to run batch job within.",
    )

    template_path = os.path.join("{experiment_run_dir}", "batch_config.yaml")

    default_submit_command = (
        "gcloud batch jobs submit --project {batch_project} "
        "--config " + template_path + " "
        "--location {batch_job_region} "
        "{job_name}"
    )

    workflow_manager_variable(
        name="batch_submit_cmd",
        default=default_submit_command,
        description="Command to submit batch job",
    )

    formatted_executable(
        "batch_formatted_command",
        prefix="",
        indentation="14",
        commands=["{unformatted_batch_command}"],
    )

    workflow_manager_variable(
        name="batch_submit_template_path",
        default="batch_config.yaml.tpl",
        description="Path to the custom template for generating the slurm sbatch job script. "
        "For a relative path, it is searched under the workflow manager's source directory. "
        "The path can contain workspace path variables such as $workspace_config.",
    )

    register_template(
        name="batch_config",
        src_path="batch_config.yaml.tpl",
        dest_path="batch_config.yaml",
    )

    register_template(
        name="batch_submit",
        src_path="batch_submit.tpl",
        dest_path="batch_submit",
        extra_vars_func="batch_submit_vars",
    )

    def _batch_submit_vars(self):
        vars = self.app_inst.variables
        old_var_name = "_old_batch_submit"
        if old_var_name in vars:
            batch_submit_cmd = vars[old_var_name]
            if "gcloud" not in batch_submit_cmd:
                logger.warn(
                    "`gcloud` is missing in the given `batch_submit` command"
                )
        else:
            batch_submit_cmd = self.default_submit_command

        return {
            "batch_submit_cmd": batch_submit_cmd,
        }

    register_template(
        name="batch_helpers",
        src_path="batch_helpers.tpl",
        dest_path="batch_helpers",
        extra_vars={
            "declare_status_map": shell_utils.gen_dict_definition(
                var_name="status_map", dict=_STATUS_MAP
            )
        },
    )

    register_template(
        name="batch_fetch_logs",
        src_path="batch_fetch_logs.tpl",
        dest_path="batch_fetch_logs",
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

    register_template(
        name="batch_clean",
        src_path="batch_clean.tpl",
        dest_path="batch_clean",
    )

    register_template(
        name="batch_wait",
        src_path="batch_wait.tpl",
        dest_path="batch_wait",
    )

    def get_status(self, workspace):
        expander = self.app_inst.expander
        run_dir = expander.expand_var_name("experiment_run_dir")
        job_file = os.path.join(run_dir, ".batch_job.yaml")
        status = ExperimentStatus.UNRESOLVED
        if not os.path.isfile(job_file):
            logger.warn(
                f"{self.name} job file is missing in experiment {expander.experiment_namespace}"
            )
            return status

        with open(job_file, encoding="utf-8") as f:
            job_data = yaml.safe_load(f)

        job_name = job_data["name"]

        self.runner.set_dry_run(workspace.dry_run)
        project = expander.expand_var_name("batch_project")
        location = expander.expand_var_name("batch_job_region")
        wm_status_raw = self.runner.get_status(project, location, job_name)
        status = _STATUS_MAP.get(wm_status_raw, ExperimentStatus.UNRESOLVED)
        if status == ExperimentStatus.UNRESOLVED:
            logger.warn(
                f"The {self.name} workflow manager failed to resolve the status of job {job_name}.\n "
                "Enable debug mode (`ramble -d`) for more detailed error messages."
            )
        return status


class GcloudRunner:
    """Runner for executing gcloud commands"""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.gcloud_runner = None
        self.run_dir = None

    def _ensure_runner(self, runner_name: str):
        attr = f"{runner_name}_runner"
        if getattr(self, attr) is None:
            setattr(
                self,
                attr,
                CommandRunner(name=runner_name, command=runner_name),
            )

    def set_dry_run(self, dry_run=False):
        """
        Set the dry_run state of this runner
        """
        self.dry_run = dry_run

    def get_status(self, project, location, job_name):
        if self.dry_run:
            return None
        self._ensure_runner("gcloud")
        status_args = [
            "batch",
            "jobs",
            "describe",
            "--project",
            project,
            "--location",
            location,
            job_name,
        ]
        try:
            status_out = self.gcloud_runner.command(
                *status_args, output=str, error=os.devnull
            )
        except ProcessError as e:
            status_out = ""
            logger.debug(
                f"`gcloud batch jobs describe` returns error {e}. This is normal if the job has already been completed."
            )

        yaml_status = yaml.safe_load(status_out)
        if (
            yaml_status
            and "status" in yaml_status
            and "state" in yaml_status["status"]
        ):
            return yaml_status["status"]["state"]
        return "UNRESOLVED"
