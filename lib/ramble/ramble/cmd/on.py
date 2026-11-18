# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import ramble.cmd
import ramble.config
import ramble.filters
import ramble.pipeline
from ramble.cmd.common import arguments

description = '"And now\'s the time, the time is now" (execute workspace experiments)'
section = "workspaces"
level = "short"


def setup_parser(subparser):
    subparser.add_argument(
        "--executor",
        metavar="executor",
        dest="executor",
        help="execution template for each experiment",
        required=False,
    )

    subparser.add_argument(
        "--enable-per-experiment-prints",
        action="store_true",
        dest="per_experiment_prints_on",
        help="Enable per experiment prints (phases and log paths).",
    )

    subparser.add_argument(
        "--suppress-run-header",
        action="store_true",
        dest="run_header_off",
        help="Disable the logger header.",
    )

    arguments.add_common_arguments(
        subparser,
        [
            "where",
            "exclude_where",
            "filter_tags",
            "filter_group",
            "exclude_filter_group",
        ],
    )


def ramble_on(args):
    current_pipeline = ramble.pipeline.pipelines.execute
    ws = ramble.cmd.require_active_workspace(cmd_name="on")

    executor = args.executor if args.executor else "{batch_submit}"

    filters = ramble.filters.Filters.from_args(args)

    debug = ramble.config.get("config:debug")
    suppress_per_experiment_prints = not debug and not args.per_experiment_prints_on
    suppress_run_header = not debug and args.run_header_off

    pipeline_cls = ramble.pipeline.pipeline_class(current_pipeline)
    pipeline = pipeline_cls(
        ws,
        filters,
        executor=executor,
        suppress_per_experiment_prints=suppress_per_experiment_prints,
        suppress_run_header=suppress_run_header,
    )

    with ws.read_transaction():
        pipeline.run()


def on(parser, args):
    """Execute `ramble_on` command"""
    ramble_on(args)
