# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import datetime
import os

from ramble.experiment_result import ExperimentStatus
from ramble.util import shell_utils
from ramble.wmkit import *

from spack.util.executable import (
    CommandNotFoundError,
    Executable,
    ProcessError,
)

# Mapping from squeue/sacct status to Ramble status
_STATUS_MAP = {
    "PD": ExperimentStatus.SUBMITTED,
    "R": ExperimentStatus.RUNNING,
    "CF": ExperimentStatus.SETUP,
    # Regard completing as complete
    "CG": ExperimentStatus.COMPLETE,
    "COMPLETING": ExperimentStatus.COMPLETE,
    "CA": ExperimentStatus.COMPLETE,
    "COMPLETED": ExperimentStatus.COMPLETE,
    "CANCELLED": ExperimentStatus.CANCELLED,
    "CANCELLED+": ExperimentStatus.CANCELLED,
    "F": ExperimentStatus.FAILED,
    "FAILED": ExperimentStatus.FAILED,
    "TO": ExperimentStatus.TIMEOUT,
    "TIMEOUT": ExperimentStatus.TIMEOUT,
}


class Slurm(WorkflowManagerBase):
    """Slurm workflow manager"""

    name = "slurm"

    maintainers("linsword13")

    tags("workflow", "slurm")

    workflow_manager_family("slurm")

    def __init__(self, file_path):
        super().__init__(file_path)

        self.runner = SlurmRunner()

    workflow_manager_variable(
        "workflow_banner",
        default="""# ****************************************************
# * Workflow manager: slurm
# * Execution script is: {slurm_experiment_sbatch}
# * Note: `execute_experiment` is sourced by the execution script.
# * Do not add `#SBATCH` headers to `execute_experiment`, as they will be ignored.
# ****************************************************
""",
        description="Banner to describe the workflow within execution templates",
    )

    workflow_manager_variable(
        name="job_name",
        default="{application_name}_{workload_name}_{experiment_name}",
        description="Slurm job name",
    )

    workflow_manager_variable(
        name="extra_sbatch_headers",
        default="",
        description="Extra sbatch headers added to slurm job script",
    )

    workflow_manager_variable(
        name="hostlist",
        default="$SLURM_JOB_NODELIST",
        description="hostlist variable used by various modifiers",
    )

    workflow_manager_variable(
        name="srun_args",
        default="-n {n_ranks}",
        description="Arguments supplied to srun",
    )

    workflow_manager_variable(
        name="mpi_command",
        default="srun {srun_args}",
        description="mpirun prefix, mostly served as an overridable default",
    )

    workflow_manager_variable(
        name="slurm_partition",
        default="",
        description="partition to submit job to, if unspecified, it uses the default partition",
    )

    workflow_manager_variable(
        name="workflow_node_id",
        default="${SLURM_NODEID}",
        description="node ID to be inserted at runtime",
    )

    workflow_manager_variable(
        name="slurm_execute_template_path",
        default="slurm_experiment_sbatch.tpl",
        description="Path to the custom template for generating the slurm sbatch job script. "
        "For a relative path, it is searched under the workflow manager's source directory. "
        "The path can contain workspace path variables such as $workspace_config.",
    )

    variant(
        "slurm_include_default_sbatch_headers",
        default=True,
        values=[True, False],
        description="Whether a set of default headers (such as #SBATCH --exclusive) should be included",
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
            if "sbatch" not in batch_submit_cmd:
                logger.warn(
                    "`sbatch` is missing in the given `batch_submit` command"
                )
        else:
            batch_submit_script = vars["slurm_experiment_sbatch"]
            batch_submit_cmd = f"sbatch {batch_submit_script}"
        return {
            "batch_submit_cmd": batch_submit_cmd,
        }

    register_template(
        name="batch_query",
        src_path="batch_query.tpl",
        dest_path="batch_query",
        extra_vars={
            "declare_status_map": shell_utils.gen_dict_definition(
                var_name="status_map", dict=_STATUS_MAP
            )
        },
    )

    register_template(
        name="batch_cancel",
        src_path="batch_cancel.tpl",
        dest_path="batch_cancel",
    )

    register_template(
        name="batch_wait",
        src_path="batch_wait.tpl",
        dest_path="batch_wait",
    )

    register_template(
        name="slurm_experiment_sbatch",
        src_path="{slurm_execute_template_path}",
    )

    register_template(
        name="batch_helpers",
        src_path="batch_helpers.tpl",
        dest_path="batch_helpers",
    )

    archive_pattern("{experiment_run_dir}/.slurm_*")

    @property
    def template_render_vars(self):
        app_inst = self.app_inst
        expander = app_inst.expander
        # Adding pre-defined and custom headers
        pragmas = [
            "#SBATCH -N {n_nodes}",
            "#SBATCH -J {job_name}",
            "#SBATCH -o {experiment_run_dir}/slurm-%j.out",
            "#SBATCH -e {experiment_run_dir}/slurm-%j.err",
        ]
        if expander.satisfies(
            "+slurm_include_default_sbatch_headers",
            variant_set=app_inst.experiment_variants(),
        ):
            pragmas.extend(
                [
                    "#SBATCH --ntasks-per-node {processes_per_node}",
                    "#SBATCH --gpus-per-node {gpus_per_node}",
                    "#SBATCH --exclusive",
                ]
            )
        partition = expander.expand_var_name("slurm_partition")
        if partition:
            pragmas.append("#SBATCH -p {slurm_partition}")
        extra_headers = expander.expand_var_name(
            "extra_sbatch_headers"
        ).strip()
        if extra_headers:
            pragmas.extend(extra_headers.splitlines())
        header_str = "\n".join(self.conditional_expand(pragmas))
        return {
            "workflow_pragmas": header_str,
            "workflow_hostfile_cmd": self.runner.get_hostfile_cmd(),
        }

    def _get_job_termination_overhead(self):
        # Get the duration between script end time and job termination time.
        run_dir = self.app_inst.expander.experiment_run_dir
        end_time_file = os.path.join(run_dir, ".slurm_script_end_time")
        job_id_file = os.path.join(run_dir, ".slurm_job")
        if not (os.path.isfile(end_time_file) and os.path.isfile(job_id_file)):
            return
        try:
            with open(end_time_file, encoding="utf-8") as f:
                script_end_time = float(f.read().strip())

            with open(job_id_file, encoding="utf-8") as f:
                job_id = f.read().strip()
            if not job_id:
                logger.warn(f"Job ID file {job_id_file} is empty")
                return

            sacct_cmd = Executable("sacct")
            job_end_time_str = sacct_cmd(
                "-j", job_id, "-X", "-n", "--format=End", output=str
            ).strip()
            # sacct by default reports timestamp in local timezone
            job_end_time = datetime.datetime.strptime(
                job_end_time_str, "%Y-%m-%dT%H:%M:%S"
            ).timestamp()
            duration = int(job_end_time - script_end_time)
        except (ProcessError, ValueError, OSError, CommandNotFoundError) as e:
            logger.warn(f"Failed to get job end time with error {e}")
        else:
            fom_key = "slurm-job-termination-overhead"
            self.figure_of_merit(
                "job-termination-overhead",
                units="s",
                fom_map_key=fom_key,
                fom_type=FomType.TIME,
            )
            self.add_inmem_fom_value(fom_key, duration)

    def _prepare_analysis(self, workspace):
        if workspace.dry_run:
            return
        expander = self.app_inst.expander
        query_script = expander.expand_var_name("batch_query")
        query_cmd = Executable(query_script)
        try:
            query_cmd(output=os.devnull)
        except (ProcessError, OSError) as e:
            # Only log a warning as this is not considered a critical step
            logger.warn(f"batch_query returns error {e}")
        self._get_job_termination_overhead()

    def get_status(self, workspace):
        expander = self.app_inst.expander
        run_dir = expander.expand_var_name("experiment_run_dir")
        job_id_file = os.path.join(run_dir, ".slurm_job")
        if not os.path.isfile(job_id_file):
            logger.warn("job_id file is missing")
            return ExperimentStatus.UNRESOLVED
        try:
            with open(job_id_file, encoding="utf-8") as f:
                job_id = f.read().strip()
        except OSError as e:
            logger.warn(f"Failed to read job_id file {job_id_file}: {e}")
            return ExperimentStatus.UNRESOLVED
        if not job_id:
            logger.warn(f"job_id file {job_id_file} is empty")
            return ExperimentStatus.UNRESOLVED

        self.runner.set_dry_run(workspace.dry_run)
        wm_status_raw = self.runner.get_status(job_id)
        status = _STATUS_MAP.get(wm_status_raw, ExperimentStatus.UNRESOLVED)
        if status == ExperimentStatus.UNRESOLVED:
            logger.warn(
                f"The slurm workflow manager failed to resolve the status of job {job_id}. "
                "Enable debug mode (`ramble -d`) for more detailed error messages."
            )
        return status

    # Extract some job-related FOMs
    for fom, fom_type in [
        ("id", FomType.INFO),
        ("status", FomType.CATEGORY),
        ("nodes", FomType.INFO),
        ("start", FomType.INFO),
        ("end", FomType.INFO),
        ("exit_code", FomType.CATEGORY),
    ]:
        figure_of_merit(
            f"job-{fom}",
            fom_regex=rf"\s*job_{fom}:\s*(?P<val>.*)",
            group_name="val",
            log_file="{experiment_run_dir}/.slurm_job_info",
            fom_type=fom_type,
        )

    figure_of_merit(
        "job-elapsed-seconds",
        fom_regex=r"\s*job_elapsed_seconds:\s*(?P<val>\d+)",
        group_name="val",
        units="s",
        log_file="{experiment_run_dir}/.slurm_job_info",
        fom_type=FomType.TIME,
    )

    # Capture sbatch script end time, in epoch seconds
    register_builtin(
        "capture_sbatch_script_end_time",
        required=True,
        injection_method="append",
    )

    def capture_sbatch_script_end_time(self):
        return "date +%s > {experiment_run_dir}/.slurm_script_end_time"

    # Capture slurm configs before the workload runs, just so that the configs
    # match closer when the job is submitted.
    register_builtin(
        "capture_slurm_config", required=True, injection_method="prepend"
    )

    def capture_slurm_config(self):
        return "scontrol show config > {experiment_run_dir}/.slurm_config"

    for fom in ["TopologyParam", "TopologyPlugin"]:
        figure_of_merit(
            f"slurm-config-{fom}",
            fom_regex=rf"\s*{fom}\s*=\s*(?P<val>\S+)",
            group_name="val",
            log_file="{experiment_run_dir}/.slurm_config",
            fom_type=FomType.CATEGORY,
        )

    success_criteria(
        "job-status-check",
        mode="fom_comparison",
        fom_name="job-status",
        formula="'{value}' == 'COMPLETE'",
    )

    register_validator(
        name="check_sbatch_in_execute_experiment",
        predicate="not file_contains('{workspace_configs}/execute_experiment.tpl', '(?m)^[ \\t]*#SBATCH')",
        message=(
            "In experiment {experiment_namespace}:\n"
            "  `execute_experiment` contains `#SBATCH` directives, "
            "which will be ignored.\n"
            "  Custom headers should be added to `extra_sbatch_headers` "
            "in the workspace configuration instead."
        ),
        fail_on_invalid=False,
    )


class SlurmRunner:
    """Runner for executing slurm commands"""

    def __init__(self, dry_run=False):
        self.dry_run = dry_run
        self.squeue_runner = None
        self.sacct_runner = None
        self.sinfo_runner = None

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

    def get_status(self, job_id):
        if self.dry_run:
            return None
        status_out = ""
        try:
            self._ensure_runner("squeue")
            squeue_args = ["-h", "-o", "%t", "-j", job_id]
            status_out = self.squeue_runner.command(
                *squeue_args, output=str, error=os.devnull
            )
        except (ProcessError, RunnerError, OSError) as e:
            logger.debug(
                f"squeue returns error {e}. This is normal if the job has already been completed."
            )
        if not status_out:
            try:
                self._ensure_runner("sacct")
                sacct_args = ["-o", "state", "-X", "-n", "-j", job_id]
                status_out = self.sacct_runner.command(*sacct_args, output=str)
            except (ProcessError, RunnerError, OSError) as e:
                logger.debug(
                    f"sacct returns error {e}. The status is not resolved correctly."
                )
        return status_out.strip()

    def get_partitions(self):
        if self.dry_run:
            return None
        try:
            self._ensure_runner("sinfo")
            sinfo_args = ["-h"]
            out = self.sinfo_runner.command(*sinfo_args, output=str).strip()
        except (ProcessError, RunnerError, OSError) as e:
            logger.debug(f"sinfo returns error {e}")
            return None
        partitions = set()
        default_partition = None
        for line in out.splitlines():
            info = line.split()
            if not info:
                continue
            name = info[0].strip()
            if name.endswith("*"):
                name = name[:-1]
                default_partition = name
            partitions.add(name)
        return {
            "default_partition": default_partition,
            "partitions": partitions,
        }

    def get_hostfile_cmd(self):
        return "scontrol show hostnames > {hostfile}"
