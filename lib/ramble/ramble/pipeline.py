# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import glob
import itertools
import os
import shlex
import shutil
import stat
from enum import Enum

import llnl.util.filesystem as fs
from llnl.util import tty

import ramble.config
import ramble.expander
import ramble.experiment_result
import ramble.fetch_strategy
import ramble.software_environments
import ramble.stage
import ramble.uploader
import ramble.util.hashing
import ramble.util.path
import ramble.workspace
from ramble.namespace import namespace
from ramble.util import json_util
from ramble.util.colors import cprint
from ramble.util.file_util import create_symlink
from ramble.util.logger import logger

from spack.util.executable import Executable, which

if not ramble.config.get("config:disable_progress_bar", False):
    try:
        import tqdm
    except ModuleNotFoundError:
        logger.die("Module `tqdm` is not found. Ensure requirements.txt are installed.")


class Pipeline:
    """Base Class for all pipeline objects"""

    name = "base"

    def __init__(self, workspace, filters):
        """Create a new pipeline instance"""
        self.filters = filters
        self.workspace = workspace
        self.force_inventory = False
        self.action_string = "Operating on"
        self.suppress_per_experiment_prints = False
        self.suppress_run_header = False

        dt = self.workspace.date_string()
        log_file = f"{self.name}.{dt}.out"
        self.log_dir = os.path.join(self.workspace.log_dir, f"{self.name}.{dt}")
        self.log_dir_latest = os.path.join(self.workspace.log_dir, f"{self.name}.latest")
        self.log_path = os.path.join(self.workspace.log_dir, log_file)
        self.log_path_latest = os.path.join(self.workspace.log_dir, f"{self.name}.latest.out")

        self._software_environments = ramble.software_environments.SoftwareEnvironments(workspace)
        self.workspace.software_environments = self._software_environments
        self._experiment_set = workspace.build_experiment_set()
        self.updated_experiment_hashes = False

    @property
    def experiment_set(self):
        return self._experiment_set

    def _construct_experiment_hashes(self) -> bool:
        """Hash all of the experiments.

        Populate the workspace inventory information with experiment hash data.
        """
        changed = False
        for _, app_inst, _ in self._experiment_set.all_experiments():
            changed = app_inst.populate_inventory(
                self.workspace,
                force_compute=self.force_inventory,
            )
        return changed

    def _construct_workspace_hash(self):
        """Construct workspace inventory

        Assumes experiment hashes are already constructed and populated into
        the workspace.
        """
        workspace_inventory = os.path.join(self.workspace.root, self.workspace.inventory_file_name)
        workspace_hash_file = os.path.join(self.workspace.root, self.workspace.hash_file_name)

        files_exist = os.path.exists(workspace_inventory) and os.path.exists(workspace_hash_file)

        if not self.force_inventory and files_exist:
            with open(workspace_inventory, encoding="utf-8") as f:
                self.workspace.hash_inventory = json_util.load(f)

            self.workspace.workspace_hash = ramble.util.hashing.hash_json(
                self.workspace.hash_inventory
            )
        else:
            for exp, app_inst, _ in sorted(self._experiment_set.all_experiments()):
                if not (app_inst.is_template or app_inst.repeats.is_repeat_base):
                    self.workspace.hash_inventory["experiments"].append(
                        {
                            "name": exp,
                            "digest": app_inst.experiment_hash,
                            "contents": app_inst.hash_inventory,
                        }
                    )

            self.workspace.workspace_hash = ramble.util.hashing.hash_json(
                self.workspace.hash_inventory
            )
            with open(
                os.path.join(self.workspace.root, self.workspace.inventory_file_name),
                "w+",
                encoding="utf-8",
            ) as f:
                json_util.dump(self.workspace.hash_inventory, f)

            with open(
                os.path.join(self.workspace.root, self.workspace.hash_file_name),
                "w+",
                encoding="utf-8",
            ) as f:
                f.write(self.workspace.workspace_hash + "\n")

            self.workspace.update_metadata("workspace_digest", self.workspace.workspace_hash)

    def _prepare(self):
        """Perform preparation for pipeline execution"""
        self.updated_experiment_hashes = self._construct_experiment_hashes()

    def _execute(self):
        """Hook for executing the pipeline"""

        num_exps = self._experiment_set.num_filtered_experiments(self.filters)

        if logger.enabled:
            fs.mkdirp(self.log_dir)
            # Also create symlink to give known paths
            create_symlink(self.log_dir, self.log_dir_latest)

        if self.suppress_per_experiment_prints and not self.suppress_run_header:
            logger.all_msg(f"  Log files for experiments are stored in: {self.log_dir}")

        count = 1
        phase_total = 0

        for exp, app_inst, idx in self._experiment_set.filtered_experiments(self.filters):
            exp_log_path = app_inst.experiment_log_file(self.log_dir)

            experiment_index_value = app_inst.expander.expand_var_name(
                app_inst.keywords.experiment_index
            )

            if not self.suppress_per_experiment_prints:
                logger.all_msg(f"Experiment #{idx} ({count}/{num_exps}):")
                logger.all_msg(f"    name: {exp}")
                logger.all_msg(f"    root experiment_index: {experiment_index_value}")
                logger.all_msg(f"    log file: {exp_log_path}")

            with logger.add_log_context(exp_log_path):
                inv_str = json_util.dumps(app_inst.hash_inventory)
                logger.msg(f"Experiment inventory:\n{inv_str}")
                phase_list = list(
                    app_inst.get_pipeline_phases(self.name, phase_filters=self.filters.phases)
                )

                disable_progress = (
                    ramble.config.get("config:disable_progress_bar", False)
                    or self.suppress_per_experiment_prints
                )
                if not disable_progress:
                    try:
                        progress = tqdm.tqdm(
                            total=len(phase_list),
                            leave=True,
                            ascii=" >=",
                            bar_format="{l_bar}{bar}| Elapsed (s): {elapsed_s:.2f}",
                        )
                    except AttributeError:
                        logger.die(
                            "tqdm.tqdm is not found. Ensure requirements.txt are installed."
                        )
                for phase_idx, phase in enumerate(phase_list):
                    if not disable_progress:
                        progress.set_description(
                            f"Processing phase {phase} ({phase_idx}/{len(phase_list)})"
                        )
                    app_inst.run_phase(self.name, phase)
                    phase_total += 1
                    if not disable_progress:
                        progress.update()
                app_inst.print_phase_times(self.name, phase_filters=self.filters.phases)
                if not disable_progress:
                    progress.set_description("Experiment complete")
                    progress.close()

            if not self.suppress_per_experiment_prints:
                logger.all_msg(f"  Returning to log file: {logger.active_log()}")

            count += 1

        if phase_total == 0 and self.filters.phases != ramble.filters.ALL_PHASES:
            logger.warn("No valid phases were selected, please verify requested phases")

    def _complete(self):
        """Hook for performing pipeline actions after execution is complete"""
        self.workspace.update_metadata("ramble_version", ramble.util.version.get_version())
        if self.updated_experiment_hashes:
            try:
                self._construct_workspace_hash()
            except FileNotFoundError as e:
                tty.warn("Unable to construct workspace hash due to missing file")
                tty.warn(e)

        self.workspace.write_metadata()

    def run(self):
        """Run the full pipeline"""
        if not self.suppress_run_header:
            logger.all_msg("Streaming details to log:")
            logger.all_msg(f"  {self.log_path}")
            if self.workspace.dry_run:
                cprint("@*g{      -- DRY-RUN -- DRY-RUN -- DRY-RUN -- DRY-RUN -- DRY-RUN --}")

            experiment_count = self._experiment_set.num_filtered_experiments(self.filters)
            experiment_total = self._experiment_set.num_experiments()
            logger.all_msg(
                f"  {self.action_string} {experiment_count} out of "
                f"{experiment_total} experiments:"
            )

        with logger.add_log_context(self.log_path):
            if logger.enabled:
                create_symlink(self.log_path, self.log_path_latest)

            self._prepare()
            self._execute()
            self._complete()

    def _copy_workspace_root_files(self, workspace, dest_dir):
        root_files = [
            ramble.workspace.Workspace.inventory_file_name,
            ramble.workspace.Workspace.hash_file_name,
            self.workspace.inventory_file_name,
            self.workspace.hash_file_name,
            ramble.workspace.METADATA_FILE_NAME,
        ]
        for filename in root_files:
            src = os.path.join(workspace.root, filename)
            if os.path.exists(src):
                dest = os.path.join(dest_dir, filename)
                shutil.copyfile(src, dest)


class AnalyzePipeline(Pipeline):
    """Class for the analyze pipeline"""

    name = "analyze"

    def __init__(
        self,
        workspace,
        filters,
        output_formats=None,
        upload=False,
        print_results=False,
        summary_only=False,
        fom_origin_types=None,
    ):
        super().__init__(workspace, filters)
        self.action_string = "Analyzing"
        self.output_formats = ["text"] if output_formats is None else output_formats
        self.upload_results = upload
        self.print_results = print_results
        self.summary_only = summary_only
        self.fom_origin_types = fom_origin_types

    def _prepare(self):

        # We only want to let the user run analyze if one of the following is true:
        # - At least one expeirment is set up
        # - `--dry-run` is enabled
        found_valid_experiment = False
        # Record how many non-analyzable experiments are encountered
        no_analyze_cnt = 0
        for _, app_inst, _ in self._experiment_set.filtered_experiments(self.filters):
            if not (app_inst.is_template or app_inst.repeats.is_repeat_base):
                if app_inst.get_status() != ramble.experiment_result.ExperimentStatus.UNKNOWN:
                    found_valid_experiment = True
            else:
                no_analyze_cnt += 1

        num_total_exps = self._experiment_set.num_experiments()
        num_filtered_exps = self._experiment_set.num_filtered_experiments(self.filters)
        if not found_valid_experiment and num_total_exps:
            if not num_filtered_exps:
                logger.die("No experiment left for analysis after filtering.")
            if num_filtered_exps == no_analyze_cnt:
                logger.die(
                    "No analyzeable experiment detected."
                    " All selected ones are either templates or the base of"
                    " repeated experiments."
                )
            logger.die(
                "No analyzeable experiment detected."
                " Make sure your workspace is setup with\n"
                "    ramble workspace setup"
            )

        super()._prepare()

    def _complete(self):
        super()._complete()
        self._experiment_set.clear_filter_cache()
        # Calculate statistics for repeats and inject into base experiment results
        for _, app_inst, _ in self._experiment_set.filtered_experiments(self.filters):

            if app_inst.repeats.n_repeats > 0:
                app_inst.calculate_statistics(self.workspace)
        self.workspace.dump_results(
            output_formats=self.output_formats,
            print_results=self.print_results,
            summary_only=self.summary_only,
            fom_origin_types=self.fom_origin_types,
        )

        self.workspace.dump_tables(self.experiment_set, self.filters)

        if self.upload_results:
            ramble.uploader.upload_results(self.workspace.results)


class ArchivePipeline(Pipeline):
    """Class for the archive pipeline"""

    name = "archive"

    def __init__(
        self,
        workspace,
        filters,
        create_tar=False,
        archive_prefix=None,
        upload_url=None,
        include_secrets=False,
        archive_patterns=None,
    ):
        super().__init__(workspace, filters)
        self.action_string = "Archiving"
        self.create_tar = create_tar
        self.upload_url = upload_url
        self.include_secrets = include_secrets
        self.archive_prefix = archive_prefix
        self.archive_name = None
        self.archive_patterns = archive_patterns.copy() if archive_patterns else []

    def _prepare(self):
        super()._prepare()
        date_str = self.workspace.date_string()

        # Use the basename from the path as the name of the workspace.
        # If we use `self.workspace.name` we get the path multiple times.

        if not self.archive_prefix:
            self.archive_prefix = os.path.basename(self.workspace.path)

        self.archive_name = f"{self.archive_prefix}-archive-{date_str}"

        archive_path = os.path.join(self.workspace.archive_dir, self.archive_name)
        fs.mkdirp(archive_path)

        self._copy_workspace_root_files(self.workspace, archive_path)

        # Copy current configs
        archive_configs = os.path.join(
            self.workspace.latest_archive_path, ramble.workspace.WORKSPACE_CONFIG_PATH
        )
        _copy_tree(self.workspace.config_dir, archive_configs)

        # Copy shared files
        archive_shared = os.path.join(
            self.workspace.latest_archive_path, ramble.workspace.WORKSPACE_SHARED_PATH
        )

        excluded_secrets = set()
        if not self.include_secrets:
            excluded_secrets.add(ramble.workspace.LICENSE_INC_NAME)

        fs.mkdirp(archive_shared)
        for root, dirs, files in os.walk(self.workspace.shared_dir):
            if "bootstrapped_utilities" in dirs:
                dirs.remove("bootstrapped_utilities")
            rel_dir = os.path.relpath(root, self.workspace.shared_dir)
            target_dir = os.path.join(archive_shared, rel_dir)
            for name in files:
                if name not in excluded_secrets:
                    src = os.path.join(root, name)
                    dest = os.path.join(target_dir, name)
                    fs.mkdirp(target_dir)
                    shutil.copy(src, dest)

        # Copy logs, but omit all symlinks (i.e. "latest")
        archive_logs = os.path.join(
            self.workspace.latest_archive_path, ramble.workspace.WORKSPACE_LOG_PATH
        )
        fs.mkdirp(archive_logs)
        for root, _, files in os.walk(self.workspace.log_dir):
            if os.path.islink(root):
                continue
            rel_dir = os.path.relpath(root, self.workspace.log_dir)
            target_dir = os.path.join(archive_logs, rel_dir)
            for name in files:
                src = os.path.join(root, name)
                if not os.path.islink(src) and os.path.isfile(src):
                    dest = os.path.join(target_dir, name)
                    fs.mkdirp(target_dir)
                    shutil.copyfile(src, dest)

        # Copy tools directory
        tools_dir = os.path.join(self.workspace.shared_dir, "bootstrapped_utilities")
        if os.path.exists(tools_dir):
            archive_tools = os.path.join(
                self.workspace.latest_archive_path,
                ramble.workspace.WORKSPACE_SHARED_PATH,
                "bootstrapped_utilities",
            )
            _copy_tree(tools_dir, archive_tools)

        for pattern in itertools.chain(
            self.archive_patterns,
            [os.path.join(ramble.workspace.WORKSPACE_RESULTS_PATH, "results.*")],
        ):
            # Escape workspace root incase it contains glob characters.
            pattern_path = glob.escape(self.workspace.root) + os.sep + pattern
            for file in glob.glob(pattern_path):
                dest_dir = os.path.dirname(
                    file.replace(self.workspace.root, self.workspace.latest_archive_path)
                )
                fs.mkdirp(dest_dir)
                shutil.copy(file, dest_dir)

        archive_path_latest = os.path.join(self.workspace.archive_dir, "archive.latest")
        create_symlink(archive_path, archive_path_latest)

    def _complete(self):
        super()._complete()
        archive_url = (
            self.upload_url if self.upload_url else ramble.config.get("config:archive_url")
        )
        archive_url = archive_url.rstrip("/") if archive_url else None

        if self.create_tar:
            tar_extension = ".tar.gz"
            tar = which("tar", required=True)
            tar_path = self.archive_name + tar_extension
            with fs.working_dir(self.workspace.archive_dir):
                tar("-czf", tar_path, self.archive_name)

            tar_path_latest = os.path.join(
                self.workspace.archive_dir, "archive.latest" + tar_extension
            )

            create_symlink(tar_path, tar_path_latest)

            logger.debug(f"Archive url: {archive_url}")

            if archive_url:
                # Perform Upload
                tar_path = self.workspace.latest_archive_path + tar_extension
                remote_tar_path = archive_url + "/" + self.workspace.latest_archive + tar_extension
                _upload_file(tar_path, remote_tar_path)
                logger.all_msg(f"Archive Uploaded to {remote_tar_path}")

                # Record upload URL to workspace metadata
                self.workspace.update_metadata("archive_url", remote_tar_path)
                self.workspace.write_metadata()
        else:
            logger.debug(f"Archive url: {archive_url}")

            if archive_url:
                import ramble.util.web as web_util

                remote_dir_path = archive_url + "/" + self.workspace.latest_archive
                web_util.push_dir_to_url(self.workspace.latest_archive_path, remote_dir_path)
                logger.all_msg(f"Uncompressed Archive Uploaded to {remote_dir_path}")

                # Record upload URL to workspace metadata
                self.workspace.update_metadata("archive_url", remote_dir_path)
                self.workspace.write_metadata()


class MirrorPipeline(Pipeline):
    """Class for the mirror pipeline"""

    name = "mirror"

    def __init__(self, workspace, filters, mirror_path=None):
        super().__init__(workspace, filters)
        self.action_string = "Mirroring"
        self.mirror_path = mirror_path

    def _prepare(self):
        self.workspace.create_mirror(self.mirror_path)

    def _complete(self):
        verb = "updated" if self.workspace.mirror_existed else "created"
        logger.msg(
            f"Successfully {verb} spack software in {self.workspace.mirror_path}",
            "Archive stats:",
            f"  {len(self.workspace.software_mirror_stats.present):<4} already present",
            f"  {len(self.workspace.software_mirror_stats.new):<4} added",
            f"  {len(self.workspace.software_mirror_stats.errors):<4} failed to fetch.",
        )

        logger.msg(
            f"Successfully {verb} inputs in {self.workspace.mirror_path}",
            "Archive stats:",
            f"  {len(self.workspace.input_mirror_stats.present):<4} already present",
            f"  {len(self.workspace.input_mirror_stats.new):<4} added",
            f"  {len(self.workspace.input_mirror_stats.errors):<4} failed to fetch.",
        )

        if self.workspace.input_mirror_stats.errors:
            logger.error("Failed downloads:")
            tty.colify(
                (s.cformat("{name}") for s in list(self.workspace.input_mirror_stats.errors)),
                output=logger.active_stream(),
            )
            logger.die("Mirroring has errors.")


class BootstrapPipeline(Pipeline):
    """Class for the bootstrap pipeline"""

    name = "bootstrap"

    def __init__(self, workspace, filters):
        super().__init__(workspace, filters)
        self.action_string = "Bootstrapping"


class SetupPipeline(Pipeline):
    """Class for the setup pipeline"""

    name = "setup"

    def __init__(self, workspace, filters):
        super().__init__(workspace, filters)
        self.force_inventory = True
        self.action_string = "Setting up"

    def _prepare(self):
        super()._prepare()

        # Ensure workspace utilities are written before execution scripts are built
        if hasattr(self.workspace, "write_utilities"):
            self.workspace.write_utilities()

        # Write custom edit functions to each experiment's run directory
        import llnl.util.filesystem as fs

        import ramble.util.file_editor

        for _, app_inst, _ in self._experiment_set.filtered_experiments(self.filters):
            custom_functions = []
            if hasattr(app_inst, "custom_edit_functions"):
                for func_source in app_inst.custom_edit_functions.values():
                    if func_source not in custom_functions:
                        custom_functions.append(func_source)

            if custom_functions:
                exp_run_dir = app_inst.expander.experiment_run_dir
                fs.mkdirp(os.path.join(exp_run_dir, "utilities"))
                script_path = os.path.join(
                    exp_run_dir, "utilities", ramble.util.file_editor.CUSTOM_EDIT_FUNCTIONS_NAME
                )
                # Ensure the module has the required imports
                copyright_header = (
                    "# Copyright 2022-2026 The Ramble Authors\n"
                    "#\n"
                    "# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or\n"
                    "# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license\n"
                    "# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your\n"
                    "# option. This file may not be copied, modified, or distributed\n"
                    "# except according to those terms.\n\n"
                )
                module_content = (
                    copyright_header + "import re\nimport os\n\n" + "\n\n".join(custom_functions)
                )
                with open(script_path, "w+", encoding="utf-8") as f:
                    f.write(module_content)

        experiment_file = open(self.workspace.all_experiments_path, "w+", encoding="utf-8")
        shell = ramble.config.get("config:shell")
        shell_path = os.path.join("/bin/", shell)
        experiment_file.write(f"#!{shell_path}\n")
        self.workspace.experiments_script = experiment_file

    def _complete(self):
        super()._complete()
        self.workspace.experiments_script.close()
        experiment_file_path = os.path.join(
            self.workspace.root, self.workspace.all_experiments_path
        )
        os.chmod(experiment_file_path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IROTH | stat.S_IXOTH)


class PushToCachePipeline(Pipeline):
    """Class for the pushtocache pipeline"""

    name = "pushtocache"

    def __init__(self, workspace, filters, spack_cache_path=None):
        super().__init__(workspace, filters)
        self.action_string = "Pushing to Spack Cache"
        self.spack_cache_path = spack_cache_path

    def _prepare(self):
        super()._prepare()
        self.workspace.spack_cache_path = self.spack_cache_path

    def _complete(self):
        super()._complete()
        logger.msg(f"Pushed envs to spack cache {self.spack_cache_path}")


class ExecutePipeline(Pipeline):
    """class for the `execute` (`on`) pipeline"""

    name = "execute"

    def __init__(
        self,
        workspace,
        filters,
        executor="{batch_submit}",
        suppress_per_experiment_prints=True,
        suppress_run_header=False,
    ):
        super().__init__(workspace, filters)
        self.action_string = "Executing"
        self.executor = executor
        self.suppress_per_experiment_prints = suppress_per_experiment_prints
        self.suppress_run_header = suppress_run_header

    def _execute(self):
        super()._execute()

        resolve_env_vars = ramble.config.get("config:resolve_variables_in_subprocesses", False)

        if not self.suppress_run_header:
            logger.all_msg("Running executors...")

        for _, app_inst, _ in self._experiment_set.filtered_experiments(self.filters):
            if app_inst.is_template:
                logger.debug(f"{app_inst.name} is a template. Skipping execution.")
                continue
            if app_inst.repeats.is_repeat_base:
                logger.debug(f"{app_inst.name} is a repeat base. Skipping execution.")
                continue

            app_inst.define_variables_for_template_path()
            exec_str = app_inst.expander.expand_var(self.executor)
            if resolve_env_vars:
                exec_str = os.path.expandvars(exec_str)
            exec_parts = shlex.split(exec_str)
            exec_name = exec_parts[0]
            exec_args = exec_parts[1:]

            executor = which(exec_name)
            if executor is None:
                # attempt searching inside the run directory
                if not os.path.isabs(exec_name):
                    alt_exec_path = os.path.join(app_inst.expander.experiment_run_dir, exec_name)
                    executor = which(alt_exec_path)

            if executor is None:
                # Attempt the execution, even though it won't succeed.
                # The raised os error gives better reason for troubleshooting
                # (like whether the exec doesn't exist, or due to missing permission.)
                executor = Executable(exec_name)

            executor(*exec_args)


class LogsPipeline(Pipeline):
    """class for the `logs` pipeline"""

    name = "logs"

    def __init__(
        self,
        workspace,
        filters,
        first_only=False,
        suppress_per_experiment_prints=True,
        suppress_run_header=True,
    ):
        super().__init__(workspace, filters)
        self.action_string = "Getting log information for"
        self.first_only = first_only
        self.suppress_per_experiment_prints = suppress_per_experiment_prints
        self.suppress_run_header = suppress_run_header

    def _execute(self):
        def print_archive_files(app_inst, pattern_title, archive_patterns):
            print_header = True
            if archive_patterns:
                for when_set, patterns in archive_patterns.items():
                    if not app_inst.expander.satisfies(
                        reqs=when_set, variant_set=app_inst.experiment_variants()
                    ):
                        continue
                    for pattern in patterns.values():
                        exp_pattern = app_inst.expander.expand_var(pattern)
                        if not os.path.isabs(exp_pattern):
                            exp_pattern = os.path.join(
                                app_inst.expander.experiment_run_dir, exp_pattern
                            )
                        for file in glob.glob(exp_pattern):
                            # Only print the header if a file matched the glob
                            if print_header:
                                logger.all_msg(f"    Archive files from {pattern_title}:")
                                print_header = False
                            logger.all_msg(f"    - {file}")

        super()._execute()

        if not self.suppress_run_header:
            logger.all_msg("Finding log information...")

        for exp, app_inst, _ in self._experiment_set.filtered_experiments(self.filters):
            if app_inst.is_template:
                continue
            if app_inst.repeats.is_repeat_base:
                continue

            log_file = app_inst.expander.expand_var_name("log_file")
            logger.all_msg(f"Experiment: {exp}")
            logger.all_msg(f"    Experiment log file: {log_file}")

            analysis_logs, _, _ = app_inst.analysis_dicts(app_inst.success_list)

            logger.all_msg("    Auxiliary experiment logs:")
            for log in analysis_logs:
                logger.all_msg(f"    - {log}")

            print_archive_files(app_inst, "application", app_inst.archive_patterns)
            if app_inst.package_manager:
                pm_name = app_inst.package_manager.name
                print_archive_files(
                    app_inst,
                    f"package manager {pm_name}",
                    app_inst.package_manager.archive_patterns,
                )

            for mod in app_inst.modifier_instances:
                print_archive_files(app_inst, f"modifier {mod.name}", mod.archive_patterns)

            if self.first_only:
                break


class PushDeploymentPipeline(Pipeline):
    """class for the `prepare-deployment` pipeline"""

    name = "pushdeployment"
    index_filename = "index.json"
    index_namespace = "deployment_files"
    tar_extension = ".tar.gz"
    legacy_object_repo_name = "object_repo"

    def __init__(
        self, workspace, filters, create_tar=False, upload_url=None, deployment_name=None
    ):
        super().__init__(workspace, filters)

        workspace_expander = ramble.expander.Expander(ramble.config.get(namespace.variables), None)

        self.action_string = "Pushing deployment of"
        self.create_tar = create_tar
        self.force_inventory = True

        if upload_url:
            expanded_url = workspace_expander.expand_var(upload_url)
            self.upload_url = ramble.util.path.normalize_path_or_url(expanded_url)
        else:
            self.upload_url = None

        if deployment_name:
            expanded_name = workspace_expander.expand_var(deployment_name)
            workspace.deployment_name = expanded_name
            self.deployment_name = expanded_name
        else:
            self.deployment_name = workspace.name

    def _execute(self):
        configs_dir = os.path.join(
            self.workspace.named_deployment, ramble.workspace.WORKSPACE_CONFIG_PATH
        )
        fs.mkdirp(configs_dir)

        _copy_tree(self.workspace.config_dir, configs_dir)

        aux_software_dir = os.path.join(configs_dir, ramble.workspace.AUXILIARY_SOFTWARE_DIR_NAME)
        fs.mkdirp(aux_software_dir)

        tools_dir = os.path.join(self.workspace.shared_dir, "bootstrapped_utilities")
        if os.path.exists(tools_dir):
            deployment_tools = os.path.join(
                self.workspace.named_deployment,
                ramble.workspace.WORKSPACE_SHARED_PATH,
                "bootstrapped_utilities",
            )
            _copy_tree(tools_dir, deployment_tools)

        super()._execute()

    def _deployment_files(self):
        """Yield the full path to each file in a deployment"""
        for root, _, files in os.walk(self.workspace.named_deployment):
            for name in files:
                yield os.path.join(root, name)

    def _complete(self):
        super()._complete()

        # Copy inventory files into deployment
        self._copy_workspace_root_files(self.workspace, self.workspace.named_deployment)

        # Create an index.json of the deployment
        deployment_index = {self.index_namespace: []}
        for file in self._deployment_files():
            deployment_index[self.index_namespace].append(
                file.replace(self.workspace.named_deployment + os.path.sep, "")
            )
        index_file = os.path.join(self.workspace.named_deployment, self.index_filename)
        with open(index_file, "w+", encoding="utf-8") as f:
            f.write(json_util.dumps(deployment_index))

        tar_path = os.path.join(
            self.workspace.deployments_dir, self.deployment_name + self.tar_extension
        )
        if self.create_tar:
            tar = which("tar", required=True)
            with fs.working_dir(self.workspace.deployments_dir):
                tar("-czf", tar_path, self.deployment_name)

        if self.upload_url:
            remote_base = self.upload_url + "/" + self.deployment_name

            for file in self._deployment_files():
                dest = file.replace(self.workspace.named_deployment, remote_base)
                _upload_file(file, dest)

            if self.create_tar:
                stage_dir = self.workspace.deployments_dir
                tar_path = os.path.join(stage_dir, self.deployment_name + self.tar_extension)
                remote_tar_path = self.upload_url + "/" + self.deployment_name + self.tar_extension
                _upload_file(tar_path, remote_tar_path)

        logger.all_msg(f"Deployment created in: {self.workspace.named_deployment}")
        if self.create_tar:
            logger.all_msg(f"  Tar of deployment created in: {tar_path}")
        if self.upload_url:
            remote_base = self.upload_url + "/" + self.deployment_name
            logger.all_msg(f"  Deployment uploaded to: {remote_base}")


def _copy_tree(src_dir, dest_dir):
    """Copy all files in src_dir to dest_dir"""
    for root, _, files in os.walk(src_dir):
        rel_dir = os.path.relpath(root, src_dir)
        target_dir = os.path.join(dest_dir, rel_dir)
        for name in files:
            src = os.path.join(root, name)
            dest = os.path.join(target_dir, name)
            fs.mkdirp(target_dir)
            shutil.copyfile(src, dest)


def _upload_file(src_file, dest_file):
    stage_dir = os.path.dirname(src_file)
    fetcher = ramble.fetch_strategy.URLFetchStrategy(src_file)
    fetcher.stage = ramble.stage.DIYStage(stage_dir)
    fetcher.stage.archive_file = src_file
    fetcher.archive(dest_file)


pipelines = Enum(
    "pipelines",
    [
        "analyze",
        "archive",
        "bootstrap",
        "mirror",
        "setup",
        "pushtocache",
        "execute",
        "pushdeployment",
        "logs",
    ],
)

_pipeline_map = {
    pipelines.analyze: AnalyzePipeline,
    pipelines.archive: ArchivePipeline,
    pipelines.bootstrap: BootstrapPipeline,
    pipelines.mirror: MirrorPipeline,
    pipelines.setup: SetupPipeline,
    pipelines.pushtocache: PushToCachePipeline,
    pipelines.execute: ExecutePipeline,
    pipelines.pushdeployment: PushDeploymentPipeline,
    pipelines.logs: LogsPipeline,
}


def pipeline_class(name):
    """Factory for determining a pipeline class from its name"""

    if name not in _pipeline_map:
        logger.die(
            f"Pipeline {name} is not valid.\n" f"Valid pipelines are {_pipeline_map.keys()}"
        )

    return _pipeline_map[name]
