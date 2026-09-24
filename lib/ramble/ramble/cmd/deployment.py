# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
from typing import Callable, Dict

import llnl.util.filesystem as fs

import ramble.cmd.common
import ramble.config
from ramble.cmd.common import arguments
from ramble.main import RambleCommand
from ramble.util import json_util
from ramble.util.logger import logger

import spack.util.url as surl

description = "manage workspace deployments"
section = "workspaces"
level = "short"

subcommands = [
    "push",
    "pull",
]


def deployment_push_setup_parser(subparser):
    """Push a workspace deployment"""
    subparser.add_argument(
        "--tar-archive",
        "-t",
        action="store_true",
        dest="tar_archive",
        help="create a tar.gz of the deployment directory.",
    )

    subparser.add_argument(
        "--deployment-name",
        "-d",
        dest="deployment_name",
        default=None,
        help="Name for deployment. Uses workspace name if not set.",
    )

    subparser.add_argument(
        "--upload-url",
        "-u",
        dest="upload_url",
        default=None,
        help="URL to upload deployment into. Upload tar if `-t` is specified..",
    )

    arguments.add_common_arguments(
        subparser,
        [
            "phases",
            "include_phase_dependencies",
            "where",
            "exclude_where",
            "filter_tags",
            "filter_group",
            "exclude_filter_group",
        ],
    )


def deployment_push(args):
    import ramble.cmd
    import ramble.filters
    import ramble.pipeline

    current_pipeline = ramble.pipeline.pipelines.pushdeployment
    ws = ramble.cmd.require_active_workspace(cmd_name="deployment push")

    args.where = ramble.filters.resolve_and_apply_filter_groups(args, args.where)

    filters = ramble.filters.Filters(
        phase_filters=args.phases,
        include_where_filters=args.where,
        exclude_where_filters=args.exclude_where,
        tags=args.filter_tags,
    )

    pipeline_cls = ramble.pipeline.pipeline_class(current_pipeline)

    pipeline = pipeline_cls(
        ws,
        filters,
        create_tar=args.tar_archive,
        upload_url=args.upload_url,
        deployment_name=args.deployment_name,
    )

    with ws.write_transaction():
        deployment_run_pipeline(args, pipeline)


def deployment_pull_setup_parser(subparser):
    """Pull a workspace deployment into current workspace"""
    subparser.add_argument(
        "--deployment-path",
        "-p",
        "-u",
        dest="deployment_path",
        help="Path to deployment that should be pulled",
        required=True,
    )


def deployment_pull(args):
    import ramble.cmd
    import ramble.fetch_strategy
    import ramble.pipeline
    import ramble.stage
    import ramble.util.path

    def pull_file(src, dest):
        fetcher = ramble.fetch_strategy.URLFetchStrategy(url=src)
        stage_dir = os.path.dirname(dest)
        fs.mkdirp(stage_dir)
        with ramble.stage.InputStage(fetcher, path=stage_dir, name=os.path.basename(src)) as stage:
            stage.fetch()

    ws = ramble.cmd.require_active_workspace(cmd_name="deployment pull")

    with ws.write_transaction():
        # Fetch deployment index first:
        push_cls = ramble.pipeline.PushDeploymentPipeline

        # Handle local relative path
        deployment_path = ramble.util.path.normalize_path_or_url(args.deployment_path)

        remote_index_path = surl.join(
            deployment_path, ramble.pipeline.PushDeploymentPipeline.index_filename
        )
        local_index_path = os.path.join(ws.root, push_cls.index_filename)

        try:
            pull_file(remote_index_path, local_index_path)
        except ramble.fetch_strategy.FetchError:
            logger.die(
                "Error extracting deployment index file.\n"
                "   Make sure your deployment was pushed with "
                "`ramble deployment push` before pulling it."
            )

        with open(local_index_path, encoding="utf-8") as f:
            index_data = json_util.load(f)

        for file in index_data[push_cls.index_namespace]:
            src = surl.join(deployment_path, file)
            dest = os.path.join(ws.root, file)
            if os.path.exists(dest):
                fs.force_remove(dest)

            try:
                pull_file(src, dest)
            except ramble.fetch_strategy.FetchError:
                logger.die(
                    f"Error fetching file {file} from deployment. "
                    "Deployment may be corrupt or incomplete."
                )

        legacy_obj_repo_path = os.path.join(
            ws.root, ramble.pipeline.PushDeploymentPipeline.legacy_object_repo_name
        )
        # Read in legacy deployment repo if it exists
        if os.path.exists(legacy_obj_repo_path):
            repo_cmd = RambleCommand("repo")
            repo_cmd("add", legacy_obj_repo_path, global_args=["-D", ws.root])

        ramble_repos_path = os.path.join(ws.root, "object_repos", "ramble")
        if os.path.exists(ramble_repos_path):
            repo_cmd = RambleCommand("repo")
            for maybe_repo in os.listdir(ramble_repos_path):
                maybe_repo_dir = os.path.join(ramble_repos_path, maybe_repo)
                if os.path.isdir(maybe_repo_dir) and os.path.exists(
                    os.path.join(maybe_repo_dir, ramble.repository.unified_config)
                ):
                    repo_cmd("add", maybe_repo_dir, global_args=["-D", ws.root])


def deployment_run_pipeline(args, pipeline):
    include_phase_dependencies = getattr(args, "include_phase_dependencies", None)
    if include_phase_dependencies:
        with ramble.config.override("config:include_phase_dependencies", True):
            pipeline.run()
    else:
        pipeline.run()


#: Dictionary mapping subcommand names and aliases to functions
subcommand_functions: Dict[str, Callable] = {}


def setup_parser(subparser):
    ramble.cmd.common.setup_subcommands_from_prefix(
        subparser=subparser,
        dest="deployment_command",
        subcommands=subcommands,
        prefix="deployment",
        globals_dict=globals(),
        subcommand_functions=subcommand_functions,
    )


def deployment(parser, args):
    """Look for a function called deployment_<name> and call it."""
    action = subcommand_functions[args.deployment_command]
    action(args)
