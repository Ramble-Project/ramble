# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import json
import os

from llnl.util.tty.colify import colified

import ramble.cmd
import ramble.uploader
import ramble.util.colors as color
from ramble.util.logger import logger

import spack.util.spack_yaml as syaml

description = "take actions on experiment results"
section = "results"
level = "short"


def setup_parser(subparser):
    sp = subparser.add_subparsers(metavar="SUBCOMMAND", dest="results_command")

    upload_parser = sp.add_parser(
        "upload", help=results_upload.__doc__, description=results_upload.__doc__
    )
    upload_parser.add_argument("filename", help="path of file to upload")

    index_parser = sp.add_parser(
        "index", help=results_index.__doc__, description=results_index.__doc__
    )
    index_parser.add_argument(
        "-v",
        "--all-vars",
        dest="all_vars",
        action="store_true",
        help="print all variable names",
        required=False,
    )
    index_parser.add_argument("-f", "--file", help="path of results file")

    report_parser = sp.add_parser(
        "report", help=results_report.__doc__, description=results_report.__doc__
    )
    report_parser.add_argument(
        "--workspace",
        dest="workspace",
        metavar="WRKSPC",
        action="store",
        help="the workspace to report on",
    )

    # The plot type should be exclusive, and only one plot type is supported per invocation
    plot_type_group = report_parser.add_mutually_exclusive_group(required=True)
    plot_type_group.add_argument(
        "--strong-scaling",
        dest="strong_scaling",
        nargs="+",
        help="generate a scaling report, requires two args: [y-axis metric] [x-axis metric]"
        "[optional: group by]",
        required=False,
    )
    plot_type_group.add_argument(
        "--weak-scaling",
        dest="weak_scaling",
        nargs="+",
        help="generate a scaling report, requires two args: [y-axis metric] [x-axis metric]"
        "[optional: group by]",
        required=False,
    )
    plot_type_group.add_argument(
        "--multi-line",
        dest="multi_line",
        nargs="+",
        help="generate a scaling report, requires two args: [y-axis metric] [x-axis metric]"
        "[optional: group by]",
        required=False,
    )
    plot_type_group.add_argument(
        "--compare",
        dest="compare",
        nargs="+",
        help="generate a comparison report, requires at least two args: [FOM 1] [Additional FOMs]"
        "[optional: group by(s)]",
        required=False,
    )
    plot_type_group.add_argument(
        "--foms",
        dest="foms",
        action="store_true",
        help="generate a FOM report, showing values of FOMs for each experiment",
        required=False,
    )
    report_parser.add_argument(
        "--pandas-where",
        dest="where",
        action="store",
        help="Down select data to plot (useful for complex workspaces with collisions). Takes"
        " pandas query format",
        required=False,
    )
    report_parser.add_argument(
        "-n",
        "--normalize",
        dest="normalize",
        action="store_true",
        help=(
            "Normalize charts where possible. For scaling charts, this requires fom_type to be "
            "specified as either 'time' or 'throughput' in the application definition."
        ),
        required=False,
    )
    report_parser.add_argument(
        "--logx", dest="logx", action="store_true", help=("Plot X axis as log"), required=False
    )
    report_parser.add_argument(
        "--logy", dest="logy", action="store_true", help=("Plot Y axis as log"), required=False
    )
    report_parser.add_argument(
        "--simplify-names",
        dest="simplify_names",
        action="store_true",
        help="Simplify experiment names on the x-axis by stripping common prefixes and suffixes",
        required=False,
    )

    # TODO: should this make it into the final cut? Only applies to multi line -- remove
    report_parser.add_argument(
        "--split-by",
        dest="split_by",
        # nargs="+",
        # action="append",
        # default=["simplified_workload_namespace"],
        action="store",
        default="simplified_workload_namespace",
        help=("Ramble Variable to split out into different plots"),
        required=False,
    )
    report_parser.add_argument("-f", "--file", help="path of results file")


def results_upload(args):
    """Imports Ramble experiment results from JSON file and uploads them as
    specified in the upload block of Ramble's config file."""
    imported_results = import_results_file(args.filename)

    ramble.uploader.upload_results(imported_results)


def import_results_file(filename):
    """
    Import Ramble experiment results from a JSON or YAML file.

    Returns a results dictionary.
    """
    logger.debug("File to import:")
    logger.debug(filename)

    with open(filename, encoding="utf-8") as imported_file:
        logger.msg(f"Importing results file: {filename}")

        ext = os.path.splitext(filename)[1]
        if ext.lower() == ".json":
            try:
                results_dict = json.load(imported_file)
                # Check if data contains an experiment
                if results_dict.get("experiments"):
                    return results_dict
                else:
                    logger.die("Unable to parse file: Does not contain valid data to import.")
            except ValueError:
                logger.die("Unable to parse file: Invalid JSON formatting.")
        elif ext.lower() in (".yml", ".yaml"):
            try:
                results_dict = syaml.load(imported_file)
                # Check if data contains an experiment
                if results_dict.get("experiments"):
                    return results_dict
                else:
                    logger.die("Unable to parse file: Does not contain valid data to import.")
            except ValueError:
                logger.die("Unable to parse file: Invalid YAML formatting.")
        else:
            logger.die("Unable to parse file: Please provide a valid JSON or YAML results file.")


def _load_results(args):
    """Loads results from a file or workspace to use for reports.

    Check for results in this order:
        1. via ``ramble results report -f FILENAME``
        2. via ``ramble -w WRKSPC`` or ``ramble -D DIR`` or
        ``ramble results report --workspace WRKSPC``(arguments)
        3. via a path in the ramble.workspace.RAMBLE_WORKSPACE_VAR environment variable.
    """
    results_dict = {}

    if args.file:
        if os.path.exists(args.file):
            results_dict = import_results_file(args.file)
        else:
            logger.die(f"Cannot find file {args.file}")
    else:
        ramble_ws = ramble.cmd.find_workspace_path(args)

        if not ramble_ws:
            logger.die(
                "ramble results report requires either a results filename, "
                "a command line workspace, or an active workspace"
            )

        logger.debug("Looking for workspace results file...")
        json_results_path = os.path.join(ramble_ws, "results.latest.json")
        yaml_results_path = os.path.join(ramble_ws, "results.latest.yaml")
        if os.path.exists(json_results_path):
            logger.debug(f"Importing {json_results_path}")
            results_dict = import_results_file(json_results_path)
        elif os.path.exists(yaml_results_path):
            logger.debug(f"Importing {yaml_results_path}")
            results_dict = import_results_file(yaml_results_path)
        else:
            logger.die(
                "No JSON or YAML results file was found. Please run "
                "'ramble workspace analyze -f json'."
            )
    return results_dict


def _print_attr_dict(attr_dict: dict, n_indent=0):
    for attr, values in attr_dict.items():
        indentation = " " * n_indent
        color.cprint(f"{indentation}{color.title_color(attr, n_indent)}:")
        if isinstance(values, dict):
            _print_attr_dict(values, n_indent + 4)
        else:
            color.cprint(colified(sorted(values), tty=True, indent=n_indent + 4))


def results_index(args):
    """List attributes in results including FOMs and template variables"""
    import ramble.reports

    results_dict = _load_results(args)
    filtered_experiments = ramble.reports.filter_exp_results(results_dict["experiments"])
    result_index = ramble.reports.generate_result_index(
        filtered_experiments, all_vars=args.all_vars
    )
    for obj_name, obj_dict in result_index.items():
        if obj_dict:
            color.cprint(color.title_color(f'{obj_name.replace("_", " ").title()}:'))
            if obj_name == "All Variables" and not args.all_vars:
                continue
            _print_attr_dict(obj_dict, n_indent=4)


def results_report(args):
    """Create a report with charts from Ramble experiment results."""
    import ramble.reports

    results_dict = _load_results(args)

    if "workspace_name" in results_dict:
        ws_name = results_dict["workspace_name"]
    else:
        ws_name = "unknown_workspace"

    if args.workspace:
        ws_name = str(args.workspace)

    filtered_experiments = ramble.reports.filter_exp_results(results_dict["experiments"])
    ramble.reports.make_report(filtered_experiments, ws_name, args)


def results(parser, args):
    action = {
        "upload": results_upload,
        "index": results_index,
        "report": results_report,
    }
    action[args.results_command](args)
