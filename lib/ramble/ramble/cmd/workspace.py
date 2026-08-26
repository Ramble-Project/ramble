# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import argparse
import itertools
import os
import sys
import tempfile
from collections import defaultdict
from typing import Callable, Dict

import deprecation

from llnl.util import tty
from llnl.util.tty.colify import colified, colify

import ramble.cmd
import ramble.cmd.filter_groups
import ramble.config
import ramble.expander
import ramble.filters
import ramble.pipeline
import ramble.repository
import ramble.software_environments
import ramble.spec
import ramble.util.colors as color
import ramble.workspace
import ramble.workspace.shell
from ramble import ramble_version
from ramble.cmd.common import arguments
from ramble.namespace import namespace
from ramble.util.format import when_order
from ramble.util.logger import logger

import spack.util.environment
from spack.util import string
from spack.util.editor import editor

description = "manage experiment workspaces"
section = "workspaces"
level = "short"


@deprecation.deprecated(
    deprecated_in="0.6.0",
    removed_in="0.7.0",
    current_version=ramble_version,
    details="Use the -V option instead",
)
def _deprecated_manage_experiments_arguments():
    pass


subcommands = [
    "activate",
    "archive",
    "bootstrap",
    "deactivate",
    "create",
    "concretize",
    "config",
    "setup",
    "analyze",
    "push-to-cache",
    "info",
    "edit",
    "mirror",
    "experiment-logs",
    ["list", "ls"],
    ["remove", "rm"],
    "generate-config",
    "manage",
]

manage_commands = ["experiments", "software", "includes", "modifiers", "filter-groups"]


def workspace_activate_setup_parser(subparser):
    """Set the current workspace"""
    shells = subparser.add_mutually_exclusive_group()
    shells.add_argument(
        "--sh",
        action="store_const",
        dest="shell",
        const="sh",
        help="print sh commands to activate the workspace",
    )
    shells.add_argument(
        "--csh",
        action="store_const",
        dest="shell",
        const="csh",
        help="print csh commands to activate the workspace",
    )
    shells.add_argument(
        "--fish",
        action="store_const",
        dest="shell",
        const="fish",
        help="print fish commands to activate the workspace",
    )
    shells.add_argument(
        "--bat",
        action="store_const",
        dest="shell",
        const="bat",
        help="print bat commands to activate the environment",
    )

    subparser.add_argument(
        "-p",
        "--prompt",
        action="store_true",
        default=False,
        help="decorate the command line prompt when activating",
    )

    ws_options = subparser.add_mutually_exclusive_group()
    ws_options.add_argument(
        "--temp",
        action="store_true",
        default=False,
        help="create and activate a workspace in a temporary directory",
    )
    ws_options.add_argument(
        "-d", "--dir", default=None, help="activate the workspace in this directory"
    )
    ws_options.add_argument(
        metavar="workspace",
        dest="activate_workspace",
        nargs="?",
        default=None,
        help="name of workspace to activate",
    )
    subparser.add_argument(
        "--parent-dir",
        metavar="dir",
        help="parent directory for the named workspace to activate",
    )
    subparser.add_argument(
        "--fg",
        "--filter-group",
        dest="filter_group",
        default=None,
        help="filter group to activate persistently",
    )


def create_temp_workspace_directory():
    """
    Returns the path of a temporary directory in which to
    create a workspace
    """
    return tempfile.mkdtemp(prefix="ramble-")


def workspace_activate(args):
    if not args.activate_workspace and not args.dir and not args.temp:
        logger.die("ramble workspace activate requires a workspace name, directory, or --temp")

    if not args.shell:
        ramble.cmd.common.shell_init_instructions(
            "ramble workspace activate", "    eval `ramble workspace activate {sh_arg} [...]`"
        )
        return 1

    workspace_name_or_dir = args.activate_workspace or args.dir

    # Temporary workspace
    if args.temp:
        workspace = create_temp_workspace_directory()
        workspace_path = os.path.abspath(workspace)
        short_name = os.path.basename(workspace_path)
        ramble.workspace.Workspace(workspace).write()

    # Named workspace
    elif (
        ramble.workspace.exists(workspace_name_or_dir, parent_dir=args.parent_dir) and not args.dir
    ):
        workspace_path = ramble.workspace.root(workspace_name_or_dir, parent_dir=args.parent_dir)
        short_name = workspace_name_or_dir

    # Workspace directory
    elif ramble.workspace.is_workspace_dir(workspace_name_or_dir):
        workspace_path = os.path.abspath(workspace_name_or_dir)
        short_name = os.path.basename(workspace_path)

    else:
        logger.die(f"No such workspace: '{workspace_name_or_dir}'")

    workspace_prompt = f"[{short_name}]"

    # We only support one active workspace at a time, so deactivate the current one.
    if ramble.workspace.active_workspace() is None:
        cmds = ""
        env_mods = spack.util.environment.EnvironmentModifications()
    else:
        cmds = ramble.workspace.shell.deactivate_header(shell=args.shell)
        env_mods = ramble.workspace.shell.deactivate()

    # Activate new workspace
    active_workspace = ramble.workspace.Workspace(workspace_path)
    enable_prompt = args.prompt or ramble.config.get("config:enable_workspace_prompt")
    cmds += ramble.workspace.shell.activate_header(
        ws=active_workspace,
        shell=args.shell,
        prompt=workspace_prompt if enable_prompt else None,
        filter_group=args.filter_group,
    )
    env_mods.extend(ramble.workspace.shell.activate(ws=active_workspace))
    cmds += env_mods.shell_modifications(args.shell)
    sys.stdout.write(cmds)


def workspace_deactivate_setup_parser(subparser):
    """deactivate any active workspace in the shell"""
    shells = subparser.add_mutually_exclusive_group()
    shells.add_argument(
        "--sh",
        action="store_const",
        dest="shell",
        const="sh",
        help="print sh commands to deactivate the workspace",
    )
    shells.add_argument(
        "--csh",
        action="store_const",
        dest="shell",
        const="csh",
        help="print csh commands to deactivate the workspace",
    )
    shells.add_argument(
        "--fish",
        action="store_const",
        dest="shell",
        const="fish",
        help="print fish commands to activate the workspace",
    )
    shells.add_argument(
        "--bat",
        action="store_const",
        dest="shell",
        const="bat",
        help="print bat commands to activate the environment",
    )


def workspace_deactivate(args):
    if not args.shell:
        ramble.cmd.common.shell_init_instructions(
            "ramble workspace deactivate",
            "    eval `ramble workspace deactivate {sh_arg}`",
        )
        return 1

    # Error out when -w, -W, -D flags are given, cause they are ambiguous.
    if args.workspace or args.no_workspace or args.workspace_dir:
        logger.die(
            "Calling ramble workspace deactivate with --workspace,"
            " --workspace-dir, and --no-workspace "
            "is ambiguous"
        )

    if ramble.workspace.active_workspace() is None:
        if ramble.workspace.RAMBLE_WORKSPACE_VAR not in os.environ:
            logger.die("No workspace is currently active.")

    cmds = ramble.workspace.shell.deactivate_header(args.shell)
    env_mods = ramble.workspace.shell.deactivate()
    cmds += env_mods.shell_modifications(args.shell)
    sys.stdout.write(cmds)


def workspace_create_setup_parser(subparser):
    """create a new workspace"""
    subparser.add_argument(
        "create_workspace", metavar="wrkspc", help="name of workspace to create"
    )
    subparser.add_argument("-c", "--config", help="configuration file to create workspace with")
    subparser.add_argument(
        "-t", "--template_execute", help="execution template file to use when creating workspace"
    )
    subparser.add_argument(
        "-d", "--dir", action="store_true", help="create a workspace in a specific directory"
    )
    subparser.add_argument(
        "--software-dir",
        metavar="dir",
        help="external directory to link as software directory in workspace",
    )
    subparser.add_argument(
        "--inputs-dir",
        metavar="dir",
        help="external directory to link as inputs directory in workspace",
    )
    subparser.add_argument(
        "--parent-dir",
        metavar="dir",
        help="parent directory for the new named workspace (must be in workspace_dirs)",
    )
    subparser.add_argument(
        "-a",
        "--activate",
        action="store_true",
        help="activate the created workspace, if specified. Default is false",
    )


def workspace_create(args):
    _workspace_create(
        args.create_workspace,
        args.dir,
        args.config,
        args.template_execute,
        software_dir=args.software_dir,
        inputs_dir=args.inputs_dir,
        activate=args.activate,
        parent_dir=args.parent_dir,
    )


def _workspace_create(
    name_or_path,
    dir=False,
    config=None,
    template_execute=None,
    software_dir=None,
    inputs_dir=None,
    activate=False,
    parent_dir=None,
):
    """Create a new workspace

    Arguments:
        name_or_path (str): name of the workspace to create, or path
                            to it
        dir (bool): if True, create a workspace in a directory instead
            of a named workspace
        config (str): path to a configuration file that should
                      generate the workspace
        template_execute (str): Path to a template execute script to
                                create the workspace with
        software_dir (str): Path to software dir that should be linked
                            instead of creating a new directory.
        inputs_dir (str): Path to inputs dir that should be linked
                          instead of creating a new directory.
        activate (bool): if True, activate the created workspace. Default is False.
    """

    # Sanity check file paths, to avoid half-creating an incomplete workspace
    for filepath in [config, template_execute]:
        if filepath and not os.path.isfile(filepath):
            logger.die(f"{filepath} file path invalid")

    read_default_template = True

    # Disallow generation of default template when both a config and a template
    # are specified
    if config and template_execute:
        read_default_template = False

    if dir:
        workspace = ramble.workspace.Workspace(
            name_or_path, read_default_template=read_default_template
        )
        ws_loc = workspace.path

    else:
        workspace = ramble.workspace.create(
            name_or_path, read_default_template=read_default_template, parent_dir=parent_dir
        )

        workspace.read_default_template = read_default_template
        ws_loc = name_or_path

    activate_cmd = f"ramble workspace activate {ws_loc}"
    if not activate:
        logger.msg(f"Created workspace in {ws_loc}")
        logger.msg("You can activate this workspace with:")
        logger.msg(f"  {activate_cmd}")

    workspace.write(inputs_dir=inputs_dir, software_dir=software_dir)

    if config:
        with open(config, encoding="utf-8") as f:
            workspace.read_config("workspace", f)
            workspace.write_config("workspace", force=True)

    if template_execute:
        with open(template_execute, encoding="utf-8") as f:
            _, file_name = os.path.split(template_execute)
            template_name = os.path.splitext(file_name)[0]
            workspace.read_template(template_name, f.read())
            workspace.write_templates()

    if activate:
        sys.stdout.write(activate_cmd)
    return workspace


def workspace_remove_setup_parser(subparser):
    """remove an existing workspace"""
    subparser.add_argument(
        "rm_wrkspc", metavar="workspace", nargs="+", help="workspace(s) to remove"
    )
    arguments.add_common_arguments(subparser, ["yes_to_all"])


def workspace_remove(args):
    """Remove a *named* workspace.

    This removes an environment managed by Ramble. Directory workspaces
    should be removed manually.
    """
    read_workspaces = []
    for workspace_name in args.rm_wrkspc:
        workspace = ramble.workspace.read(workspace_name)
        read_workspaces.append(workspace)

    logger.debug(f"Removal args: {args}")

    if not args.yes_to_all:
        answer = tty.get_yes_or_no(
            "Really remove %s %s?"
            % (
                string.plural(len(args.rm_wrkspc), "workspace", show_n=False),
                string.comma_and(args.rm_wrkspc),
            ),
            default=False,
        )
        if not answer:
            logger.die("Will not remove any workspaces")

    for workspace in read_workspaces:
        if workspace.active:
            logger.die(f"Workspace {workspace.name} can't be removed while activated.")

        workspace.destroy()
        logger.msg(f"Successfully removed workspace '{workspace.name}'")


def workspace_concretize_setup_parser(subparser):
    """Concretize a workspace"""
    subparser.add_argument(
        "-f",
        "--force-concretize",
        dest="force_concretize",
        action="store_true",
        help="Overwrite software environment configuration with defaults defined in application "
        + "definition",
        required=False,
    )
    subparser.add_argument(
        "--simplify",
        dest="simplify",
        action="store_true",
        help="Remove unused software and experiment templates from workspace config",
        required=False,
    )
    subparser.add_argument(
        "--quiet",
        "-q",
        dest="quiet",
        action="store_true",
        help="Silently ignore conflicting package definitions",
        required=False,
    )


def workspace_concretize(args):
    ws = ramble.cmd.require_active_workspace("workspace concretize", args.dry_run)

    if args.simplify:
        logger.debug("Simplifying workspace config")
        ws.simplify_software()
    else:
        logger.debug("Concretizing workspace")
        ws.concretize(force=args.force_concretize, quiet=args.quiet)


def workspace_bootstrap_setup_parser(subparser):
    """Bootstrap external utilities for a workspace"""
    arguments.add_common_arguments(
        subparser,
        [
            "where",
            "exclude_where",
            "filter_tags",
        ],
    )


def workspace_bootstrap(args):
    current_pipeline = ramble.pipeline.pipelines.bootstrap
    ws = ramble.cmd.require_active_workspace(cmd_name="workspace bootstrap")

    filters = ramble.filters.Filters(
        phase_filters=["bootstrap_utilities"],
        include_where_filters=getattr(args, "where", None),
        exclude_where_filters=getattr(args, "exclude_where", None),
        tags=getattr(args, "filter_tags", None),
    )

    pipeline_cls = ramble.pipeline.pipeline_class(current_pipeline)
    pipeline = pipeline_cls(ws, filters)
    with ws.write_transaction():
        workspace_run_pipeline(args, pipeline)


def workspace_run_pipeline(args, pipeline):
    profile_phases = getattr(args, "profile_phases", None)
    profile_phase_output = getattr(args, "profile_phase_output", None)
    if profile_phases:
        import line_profiler

        profiler = line_profiler.LineProfiler()
        profiler.enable()
        p_phases = set(itertools.chain.from_iterable(profile_phases))
        pipeline.workspace.profile_config = (profiler, p_phases)
    try:
        include_phase_dependencies = getattr(args, "include_phase_dependencies", None)
        if include_phase_dependencies:
            with ramble.config.override("config:include_phase_dependencies", True):
                pipeline.run()
        else:
            pipeline.run()
    finally:
        if profile_phases:
            try:
                profiler.disable()
            except ValueError as e:
                logger.debug(f"Failed to disable line_profiler: {e}")
            if profile_phase_output:
                with open(profile_phase_output, "w", encoding="utf-8") as f:
                    profiler.print_stats(stream=f, stripzeros=True)
                logger.msg(f"Phase profile stats written to {profile_phase_output}")
            else:
                profiler.print_stats(stripzeros=True)


def workspace_setup_setup_parser(subparser):
    """Setup a workspace"""
    subparser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="perform a dry run. Sets up directories and generates "
        + "all scripts. Prints commands that would be executed "
        + "for installation, and files that would be downloaded.",
    )

    arguments.add_common_arguments(
        subparser,
        [
            "phases",
            "include_phase_dependencies",
            "where",
            "exclude_where",
            "filter_tags",
            "profile_phases",
            "profile_phase_output",
            "filter_group",
            "exclude_filter_group",
        ],
    )


def workspace_setup(args):
    current_pipeline = ramble.pipeline.pipelines.setup
    ws = ramble.cmd.require_active_workspace("workspace setup", args.dry_run)

    args.where = ramble.filters.resolve_and_apply_filter_groups(args, args.where)

    filters = ramble.filters.Filters(
        phase_filters=args.phases,
        include_where_filters=args.where,
        exclude_where_filters=args.exclude_where,
        tags=args.filter_tags,
    )

    pipeline_cls = ramble.pipeline.pipeline_class(current_pipeline)

    logger.debug("Setting up workspace")
    pipeline = pipeline_cls(ws, filters)

    with ws.read_transaction():
        workspace_run_pipeline(args, pipeline)


def workspace_analyze_setup_parser(subparser):
    """Analyze a workspace"""
    subparser.add_argument(
        "-f",
        "--formats",
        dest="output_formats",
        nargs="+",
        default=["text"],
        help="list of output formats to write." + "Supported formats are json, yaml, or text",
        required=False,
    )

    subparser.add_argument(
        "-u",
        "--upload",
        dest="upload",
        action="store_true",
        help="Push experiment data to remote store (as defined in config)",
        required=False,
    )

    subparser.add_argument(
        "-p",
        "--print-results",
        dest="print_results",
        action="store_true",
        help="print out the analysis result",
    )

    subparser.add_argument(
        "--fom-origin-types",
        dest="fom_origin_types",
        nargs="+",
        action="append",
        help="FOM origin types to include in analysis output. "
        + "Accepts space-delimited lists and can be specified multiple times.",
        required=False,
    )

    subparser.add_argument(
        "-s",
        "--summary-only",
        dest="summary_only",
        action="store_true",
        help="print out only the summary stats for repeated experiments",
    )

    arguments.add_common_arguments(
        subparser,
        [
            "phases",
            "include_phase_dependencies",
            "where",
            "exclude_where",
            "filter_tags",
            "profile_phases",
            "profile_phase_output",
            "filter_group",
            "exclude_filter_group",
        ],
    )


def workspace_analyze(args):
    current_pipeline = ramble.pipeline.pipelines.analyze
    ws = ramble.cmd.require_active_workspace("workspace analyze", args.dry_run)
    ws.repeat_success_strict = ramble.config.get("config:repeat_success_strict")

    args.where = ramble.filters.resolve_and_apply_filter_groups(args, args.where)

    filters = ramble.filters.Filters(
        phase_filters=args.phases,
        include_where_filters=args.where,
        exclude_where_filters=args.exclude_where,
        tags=args.filter_tags,
    )

    if args.fom_origin_types:
        fom_origin_types = [item for sublist in args.fom_origin_types for item in sublist]
    else:
        fom_origin_types = None

    pipeline_cls = ramble.pipeline.pipeline_class(current_pipeline)

    logger.debug("Analyzing workspace")
    pipeline = pipeline_cls(
        ws,
        filters,
        output_formats=args.output_formats,
        upload=args.upload,
        print_results=args.print_results,
        summary_only=args.summary_only,
        fom_origin_types=fom_origin_types,
    )

    with ws.read_transaction():
        workspace_run_pipeline(args, pipeline)


def workspace_push_to_cache(args):
    current_pipeline = ramble.pipeline.pipelines.pushtocache
    ws = ramble.cmd.require_active_workspace("workspace pushtocache", args.dry_run)

    filters = ramble.filters.Filters(
        phase_filters="*",
        include_where_filters=args.where,
        exclude_where_filters=args.exclude_where,
        tags=args.filter_tags,
    )
    pipeline_cls = ramble.pipeline.pipeline_class(current_pipeline)

    pipeline = pipeline_cls(ws, filters, spack_cache_path=args.cache_path)

    workspace_run_pipeline(args, pipeline)


def workspace_push_to_cache_setup_parser(subparser):
    """push workspace envs to a given buildcache"""

    subparser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="perform a dry run. Acts like it will push "
        + "to a cache, but will not actually create a cache.",
    )

    subparser.add_argument(
        "-d", dest="cache_path", default=None, required=True, help="Path to cache."
    )

    arguments.add_common_arguments(
        subparser,
        ["where", "exclude_where", "filter_tags", "profile_phases", "profile_phase_output"],
    )


def workspace_config_setup_parser(subparser):
    """Squashed workspace config"""

    actions = subparser.add_mutually_exclusive_group(required=True)

    actions.add_argument(
        "--print-squash",
        "-p",
        action="store_true",
        help="Print a squashed workspace configuration",
    )

    actions.add_argument(
        "--simplify-software",
        "--ss",
        action="store_true",
        help="Simplify the software configuration section of this workspace",
    )

    actions.add_argument(
        "--simplify-variables",
        "--sv",
        action="store_true",
        help="Simplify the variables configuration section of this workspace",
    )

    subparser.add_argument(
        "--include-section",
        "-i",
        dest="included_section",
        nargs="+",
        default=["*"],
        help="list of patterns to include configuration section, "
        + "when printing the squashed config",
        required=False,
    )

    subparser.add_argument(
        "--exclude-section",
        "-e",
        dest="excluded_section",
        nargs="+",
        default=[],
        help="list of patterns to exclude configuration section, "
        + "when printing the squashed config. Overrides included section.",
        required=False,
    )


def workspace_config(args):
    ws = ramble.cmd.require_active_workspace("workspace squashed-config", args.dry_run)

    if args.print_squash:
        ws.squash_and_print_config(args.included_section, args.excluded_section)
    elif args.simplify_software:
        ws.simplify_software()
    elif args.simplify_variables:
        ws.simplify_variables()


def workspace_info_setup_parser(subparser):
    """Information about a workspace"""
    software_opts = subparser.add_mutually_exclusive_group()
    software_opts.add_argument(
        "--software",
        action="store_true",
        help="If set, used software stack information will be printed",
    )

    software_opts.add_argument(
        "--all-software",
        action="store_true",
        help="If set, all software stack information will be printed",
    )

    subparser.add_argument(
        "--templates", action="store_true", help="If set, workspace templates will be printed"
    )

    subparser.add_argument(
        "--expansions", action="store_true", help="If set, variable expansions will be printed"
    )

    subparser.add_argument(
        "--tags", action="store_true", help="If set, experiment tags will be printed"
    )

    subparser.add_argument(
        "--phases", action="store_true", help="If set, phase information will be printed"
    )

    subparser.add_argument(
        "--variants", action="store_true", help="If set, experiment variants will be printed"
    )

    subparser.add_argument(
        "--executables", action="store_true", help="If set, experiment executables will be printed"
    )

    subparser.add_argument(
        "--utilities", action="store_true", help="If set, bootstrapped utilities will be printed"
    )

    arguments.add_common_arguments(
        subparser,
        ["where", "exclude_where", "filter_tags", "filter_group", "exclude_filter_group"],
    )

    subparser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="level of verbosity. Add flags to "
        + "increase description of workspace\n"
        + "level 1 enables software, tags, templates, and variants\n"
        + "level 2 enables executables, expansions, and phases\n",
    )


def workspace_info(args):
    def _hashable_val(val):
        if isinstance(val, (list, tuple)):
            return tuple(_hashable_val(x) for x in val)
        elif isinstance(val, dict):
            return tuple(
                (k, _hashable_val(v)) for k, v in sorted(val.items(), key=lambda x: str(x[0]))
            )
        return val

    ws = ramble.cmd.require_active_workspace("workspace info", args.dry_run)

    args.where = ramble.filters.resolve_and_apply_filter_groups(args, args.where)

    # Enable verbose mode
    if args.verbose >= 1:
        args.software = True
        args.tags = True
        args.templates = True
        args.variants = True

    if args.verbose >= 2:
        args.expansions = True
        args.phases = True
        args.executables = True
        args.utilities = True

    color.cprint(f'{color.section_title("Workspace: ")}{ws.name}')
    color.cprint("")
    color.cprint(f'{color.section_title("Location: ")}{ws.path}')

    # Print workspace templates that currently exist
    if args.templates:
        color.cprint("")
        color.cprint(color.section_title("Workspace Templates:"))
        for template, _ in ws.all_templates():
            color.cprint(f"    {template}")

    # Print workspace variables information
    workspace_vars = ws.get_workspace_vars()

    ws.software_environments = ramble.software_environments.SoftwareEnvironments(ws)
    software_environments = ws.software_environments

    # Build experiment set
    experiment_set = ws.build_experiment_set()

    if args.tags:
        color.cprint("")
        all_tags = experiment_set.all_experiment_tags()
        color.cprint(color.section_title("All experiment tags:"))
        color.cprint(colified(all_tags, indent=4))

    # Print experiment information
    # We built a "print_experiment_set" to access the scopes of variables for each
    # experiment, rather than having merged scopes as we do in the base experiment_set.
    # The base experiment_set is used to list *all* experiments.
    all_pipelines = {}
    color.cprint("")
    color.cprint(color.section_title("Experiments:"))

    # Build an index of experiments to avoid re-rendering them in the loops below
    experiment_index_map = defaultdict(list)
    app_names_cache = {}
    for exp_name, app_inst, _ in experiment_set.all_experiments():
        experiment_template_name = app_inst.variables[app_inst.keywords.experiment_template_name]
        if app_inst.repeats.repeat_index:
            suffix = f".{app_inst.repeats.repeat_index}"
            if experiment_template_name.endswith(suffix):
                experiment_template_name = experiment_template_name[: -len(suffix)]

        app_ns_raw = app_inst.variables[app_inst.keywords.application_namespace]
        if app_ns_raw not in app_names_cache:
            app_ns_spec = ramble.spec.Spec(app_ns_raw)
            app_name = app_inst.variables[app_inst.keywords.application_name]
            try:
                repo_ns = (
                    app_ns_spec.namespace
                    or ramble.repository.paths[ramble.repository.ObjectTypes.applications]
                    .repo_for_obj(app_name)
                    .namespace
                )
            except Exception:
                repo_ns = app_ns_spec.namespace

            names = {app_name, app_ns_spec.fullname, f"app.{app_name}"}
            if repo_ns:
                names.add(f"{repo_ns}.{app_name}")
                names.add(f"{repo_ns}.app.{app_name}")

            app_names_cache[app_ns_raw] = tuple(names)

        for a_name in app_names_cache[app_ns_raw]:
            key = (
                a_name,
                app_inst.variables[app_inst.keywords.workload_template_name],
                experiment_template_name,
            )
            experiment_index_map[key].append(exp_name)

    # Construct filters here...
    filters = ramble.filters.Filters(
        phase_filters=[],
        include_where_filters=args.where,
        exclude_where_filters=args.exclude_where,
        tags=args.filter_tags,
    )

    for workloads, application_context in ws.all_applications():
        for experiments, workload_context in ws.all_workloads(workloads):
            for _, experiment_context in ws.all_experiments(experiments):
                print_header = True
                # Define variable printing groups.
                var_indent = "        "
                var_group_names = [
                    color.config_title("Config"),
                    color.section_title("Workspace"),
                    color.nested_1("Application"),
                    color.nested_2("Workload"),
                    color.nested_3("Experiment"),
                ]
                header_base = color.nested_4("Variables from")
                config_vars = ramble.config.config.get("config:variables")

                # Retrieve experiments from index
                key = (
                    application_context.context_name,
                    workload_context.context_name,
                    experiment_context.context_name,
                )
                matching_experiments = experiment_index_map.get(key, [])

                for exp_name in matching_experiments:
                    app_inst = experiment_set.get_experiment(exp_name)

                    # Apply filters manually since we are iterating a raw list
                    active = True
                    if filters.include_where:
                        for expression in filters.include_where:
                            if not app_inst.expander.evaluate_predicate(expression):
                                active = False
                                break
                    if not active:
                        continue

                    if filters.exclude_where:
                        for expression in filters.exclude_where:
                            if app_inst.expander.evaluate_predicate(expression):
                                active = False
                                break
                    if not active:
                        continue

                    if filters.tags:
                        if not app_inst.has_tags(filters.tags):
                            active = False

                    if not active:
                        continue

                    if (
                        args.software or args.all_software
                    ) and app_inst.package_manager is not None:
                        software_environments.render_environment(
                            app_inst.expander.expand_var("{env_name}"),
                            app_inst.expander,
                            app_inst.package_manager,
                            require=app_inst.package_manager.requires_software_environment,
                        )
                        # Track this env as used, for printing purposes
                        software_environments.use_environment(
                            app_inst.package_manager, app_inst.expander.expand_var("{env_name}")
                        )

                    if print_header:
                        color.cprint(
                            color.nested_1("  Application: ") + application_context.escaped_name
                        )
                        color.cprint(
                            color.nested_2("    Workload: ") + workload_context.escaped_name
                        )
                        print_header = False

                    # Aggregate pipeline phases
                    if args.phases:
                        for pipeline in app_inst.pipelines:
                            if pipeline not in all_pipelines:
                                all_pipelines[pipeline] = set()
                            for phase in app_inst.get_pipeline_phases(pipeline):
                                all_pipelines[pipeline].add(phase)

                    experiment_index = app_inst.expander.expand_var_name(
                        app_inst.keywords.experiment_index
                    )

                    if app_inst.is_template:
                        prefix = f"      Template Experiment {experiment_index}: "
                        color.cprint(f"{color.nested_3(prefix)}{exp_name}")
                    elif app_inst.repeats.is_repeat_base:
                        prefix = f"      Repeat Base Experiment {experiment_index}: "
                        color.cprint(f"{color.nested_3(prefix)}{exp_name}")
                    else:
                        prefix = f"      Experiment {experiment_index}: "
                        color.cprint(f"{color.nested_3(prefix)}{exp_name}")

                    if args.tags:
                        color.cprint(f"        Experiment Tags: {app_inst.experiment_tags}")

                    if args.variants:
                        color.cprint(color.nested_4("        Variants: "))
                        variant_set = set()
                        for _, obj in app_inst.objects():
                            variant_set = variant_set.union(
                                obj.experiment_variants().as_set(
                                    expander=app_inst.expander, for_output=True
                                )
                            )
                        for variant in sorted(variant_set, key=when_order):
                            color.cprint(f"          - {variant}")

                    if args.executables:
                        color.cprint(color.nested_4("        Executables: "))
                        app_inst.define_variables_for_template_path()
                        exec_graph = app_inst.get_executable_graph(app_inst.expander.workload_name)
                        for executable in exec_graph.walk():
                            color.cprint(f"          {executable.key}")

                    if args.expansions:
                        var_groups = [
                            config_vars,
                            workspace_vars,
                            application_context.variables,
                            workload_context.variables,
                            experiment_context.variables,
                        ]

                        # Print each group that has variables in it
                        for group, name in zip(var_groups, var_group_names):
                            if group:
                                header = f"{header_base} {name}"
                                app_inst.print_vars(
                                    header=header, vars_to_print=group, indent=var_indent
                                )

                        app_inst.print_internals(indent=var_indent)
                        app_inst.print_chain_order(indent=var_indent)

    if args.phases:
        for pipeline in sorted(all_pipelines.keys()):
            color.cprint("")
            color.cprint(color.section_title(f"Phases for {pipeline} pipeline:"))
            colify(all_pipelines[pipeline], indent=4)

    # Print software stack information
    if args.software or args.all_software:
        color.cprint("")
        color.cprint(color.section_title("Software Stack:"))
        only_used_software = args.software
        color.cprint(
            software_environments.info(
                verbosity=args.verbose, indent=4, color_level=1, only_used=only_used_software
            )
        )

    if args.utilities:
        color.cprint("")
        color.cprint(color.section_title("Bootstrapped Utilities:"))

        all_utilities = {}
        for workloads, _application_context in ws.all_applications():
            for experiments, _workload_context in ws.all_workloads(workloads):
                for _exp_contents, _experiment_context in ws.all_experiments(experiments):
                    app_ctx = _application_context.context_name
                    wl_ctx = _workload_context.context_name
                    exp_ctx = _experiment_context.context_name
                    full_exp_name = f"{app_ctx}.{wl_ctx}.{exp_ctx}"
                    app_inst = experiment_set.get_experiment(full_exp_name)

                    if not app_inst:
                        continue

                    for _, obj in app_inst.objects():
                        if hasattr(obj, "required_utilities"):
                            for when_key, utilities in obj.required_utilities.items():
                                if obj.satisfy_when(when_key):
                                    for utility_name, utility_conf in utilities.items():
                                        if utility_name not in all_utilities:
                                            all_utilities[utility_name] = set()

                                        conf_tuple = tuple(
                                            sorted(
                                                (k, _hashable_val(v))
                                                for k, v in utility_conf.items()
                                                if k != "when"
                                            )
                                        )
                                        all_utilities[utility_name].add(conf_tuple)

        if not all_utilities:
            color.cprint("    None")
        else:
            ws_utilities = ws.get_workspace_utilities() or {}
            for utility_name, confs in sorted(all_utilities.items()):
                color.cprint(color.nested_1(f"    {utility_name}:"))

                # Check for workspace override
                if utility_name in ws_utilities:
                    override_conf = dict(ws_utilities[utility_name])
                    color.cprint(f"      Configuration: {override_conf} (Workspace Override)")
                    continue

                for conf in sorted(confs):
                    conf_dict = dict(conf)
                    color.cprint(f"      Configuration: {conf_dict}")


#
# workspace list
#


def workspace_list_setup_parser(subparser):
    """list available workspaces"""
    subparser.add_argument(
        "--parent-dir",
        metavar="dir",
        help="filter workspaces by parent directory",
    )
    subparser.add_argument(
        "--merged",
        action="store_true",
        help="list a merged set of workspaces across all parent directories",
    )


def workspace_list(args):
    if args.merged:
        names = ramble.workspace.all_workspace_names(parent_dir=args.parent_dir)

        color_names = []
        for name in names:
            if ramble.workspace.active(name):
                name = color.colorize(f"@*g{{{name}}}")
            color_names.append(name)

        # say how many there are if writing to a tty
        if sys.stdout.isatty():
            if not names:
                logger.msg("No workspaces")
            else:
                logger.msg(f"{len(names)} workspaces")

        colify(color_names, indent=4)
    else:
        if args.parent_dir:
            wspaths = ramble.workspace.get_workspace_path()
            canonical_parent = ramble.util.path.canonicalize_path(args.parent_dir)
            if canonical_parent not in wspaths:
                raise ramble.workspace.RambleWorkspaceError(
                    f"Directory '{args.parent_dir}' is not in configured workspace_dirs"
                )
            wspaths = [canonical_parent]
        else:
            wspaths = ramble.workspace.get_workspace_path()

        for i, wspath in enumerate(wspaths):
            if i > 0:
                color.cprint("")
            color.cprint(color.section_title("Workspaces from dir:") + " " + wspath)
            names = ramble.workspace.all_workspace_names(parent_dir=wspath)

            color_names = []
            for name in names:
                if ramble.workspace.active(name):
                    name = color.colorize(f"@*g{{{name}}}")
                color_names.append(name)

            # say how many there are if writing to a tty
            if sys.stdout.isatty():
                if not names:
                    logger.msg("No workspaces")
                else:
                    logger.msg(f"{len(names)} workspaces")

            colify(color_names, indent=4)


def workspace_edit_setup_parser(subparser):
    """edit workspace config or template"""
    subparser.add_argument(
        "-f",
        "--file",
        dest="filename",
        default=None,
        help="Open a single file by filename",
        required=False,
    )

    subparser.add_argument(
        "-c",
        "--config-only",
        dest="config_only",
        action="store_true",
        help="Only open config files",
        required=False,
    )

    subparser.add_argument(
        "-t",
        "--template-only",
        dest="template_only",
        action="store_true",
        help="Only open template files",
        required=False,
    )

    subparser.add_argument(
        "-l",
        "--license-only",
        dest="license_only",
        action="store_true",
        help="Only open license config files",
        required=False,
    )

    subparser.add_argument(
        "--all",
        dest="all_files",
        action="store_true",
        help="Open all yaml and template files in workspace config directory",
        required=False,
    )

    subparser.add_argument(
        "-p", "--print-file", action="store_true", help="print the file name that would be edited"
    )

    subparser.add_argument(
        "editor_args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass into editor, following the list of files",
    )


def workspace_edit(args, unknown_args):
    ramble_ws = ramble.cmd.find_workspace_path(args)

    if not ramble_ws:
        logger.die(
            "ramble workspace edit requires either a command "
            "line workspace or an active workspace"
        )

    config_file = ramble.workspace.config_file(ramble_ws)
    template_files = ramble.workspace.all_template_paths(ramble_ws)

    edit_files = [config_file]
    edit_files.extend(template_files)

    if args.filename:
        expander = ramble.expander.Expander(
            ramble.workspace.Workspace.get_workspace_paths(ramble_ws), None
        )
        # If filename contains expansion strings, edit expanded path. Else assume configs dir.
        expanded_filename = expander.expand_var(args.filename)
        if expanded_filename != args.filename:
            edit_files = [expanded_filename]
        else:
            edit_files = [ramble.workspace.get_filepath(ramble_ws, expanded_filename)]
    elif args.config_only:
        edit_files = [config_file]
    elif args.template_only:
        edit_files = template_files
    elif args.license_only:
        licenses_file = [ramble.workspace.licenses_file(ramble_ws)]
        edit_files = licenses_file
    elif args.all_files:
        edit_files = ramble.workspace.all_config_files(ramble_ws) + template_files

    if args.print_file:
        for f in edit_files:
            print(f)
    else:
        try:
            if unknown_args:
                logger.debug(f"Passing {unknown_args} to editor...")
            edit_files += unknown_args or []
            editor(*edit_files)
        except TypeError:
            logger.die("No valid editor was found.")


def workspace_archive_setup_parser(subparser):
    """archive current workspace state"""
    subparser.add_argument(
        "--tar-archive",
        "-t",
        action="store_true",
        dest="tar_archive",
        help="create a tar.gz of the archive directory for backing up.",
    )

    subparser.add_argument(
        "--prefix",
        "-p",
        dest="archive_prefix",
        default=None,
        help="Specify archive prefix to customize output filename.",
    )

    subparser.add_argument(
        "--upload-url",
        "-u",
        dest="upload_url",
        default=None,
        help=(
            "URL to upload workspace archive into "
            "(uploads tarball if -t is set, or uncompressed folder if omitted)."
        ),
    )

    subparser.add_argument(
        "--include-secrets",
        action="store_true",
        help="If set, secrets are included in the archive. Default is false",
    )

    subparser.add_argument(
        "--archive-pattern",
        dest="archive_patterns",
        nargs="+",
        action="append",
        help=(
            "patterns to specify additionally files that will be included in the archive. "
            "Paths are relative to workspace root."
        ),
    )

    arguments.add_common_arguments(
        subparser,
        [
            "phases",
            "include_phase_dependencies",
            "where",
            "exclude_where",
            "profile_phases",
            "profile_phase_output",
        ],
    )


def workspace_archive(args):
    current_pipeline = ramble.pipeline.pipelines.archive
    ws = ramble.cmd.require_active_workspace("workspace archive", args.dry_run)

    filters = ramble.filters.Filters(
        phase_filters=args.phases,
        include_where_filters=args.where,
        exclude_where_filters=args.exclude_where,
    )

    archive_patterns = (
        list(itertools.chain.from_iterable(args.archive_patterns)) if args.archive_patterns else []
    )

    pipeline_cls = ramble.pipeline.pipeline_class(current_pipeline)
    pipeline = pipeline_cls(
        ws,
        filters,
        create_tar=args.tar_archive,
        archive_prefix=args.archive_prefix,
        upload_url=args.upload_url,
        include_secrets=args.include_secrets,
        archive_patterns=archive_patterns,
    )

    workspace_run_pipeline(args, pipeline)


def workspace_mirror_setup_parser(subparser):
    """mirror current workspace state"""
    subparser.add_argument(
        "-d", dest="mirror_path", default=None, required=True, help="Path to create mirror in."
    )

    subparser.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        help="perform a dry run. Creates package environments, "
        + "prints package manager specific commands that would be executed "
        + "for creating the mirror.",
    )

    arguments.add_common_arguments(
        subparser,
        [
            "phases",
            "include_phase_dependencies",
            "where",
            "exclude_where",
            "profile_phases",
            "profile_phase_output",
        ],
    )


def workspace_mirror(args):
    current_pipeline = ramble.pipeline.pipelines.mirror
    ws = ramble.cmd.require_active_workspace("workspace archive", args.dry_run)

    filters = ramble.filters.Filters(
        phase_filters=args.phases,
        include_where_filters=args.where,
        exclude_where_filters=args.exclude_where,
    )
    pipeline_cls = ramble.pipeline.pipeline_class(current_pipeline)

    pipeline = pipeline_cls(ws, filters, mirror_path=args.mirror_path)

    workspace_run_pipeline(args, pipeline)
    pipeline.run()


def workspace_manage_experiments_setup_parser(subparser):
    """manage experiment definitions"""
    arguments.add_common_arguments(subparser, ["application"])

    subparser.add_argument(
        "--workload-filter",
        "--wf",
        dest="workload_filters",
        action="append",
        help="glob filter to use when selecting workloads in the application. "
        + "Workload is kept if it matches any filter.",
    )

    subparser.add_argument(
        "--variable-filter",
        "--vf",
        dest="variable_filters",
        action="append",
        help="glob filter to use when selecting variables in the workloads. "
        + "Variable is kept if it matches any filter.",
    )

    subparser.add_argument(
        "--variable-definition",
        "-v",
        dest="variable_definitions",
        action="append",
        help="variable definition to set in the generated experiments. "
        + "Given in the form key=value",
    )

    subparser.add_argument(
        "--variant-definition",
        "-V",
        dest="variant_definitions",
        action="append",
        help="variant definition to set in the generated experiments. "
        + "Given in the form name=value",
    )

    subparser.add_argument(
        "--experiment-name",
        "-e",
        dest="experiment_name",
        default="generated",
        help="name of generated experiment",
    )

    # TODO: remove in 0.7.0
    subparser.add_argument(
        "--package-manager",
        "-p",
        dest="package_manager",
        default=None,
        help="(DEPRECATED) name of (optional) package manager to use within the experiment scope. "
        + "Use --variant-definition/-V package_manager=PACKAGE_MANAGER, instead",
    )

    # TODO: remove in 0.7.0
    subparser.add_argument(
        "--workflow-manager",
        "--wm",
        dest="workflow_manager",
        default=None,
        help="(DEPRECATED) name of (optional) workflow manager to use within the experiment "
        + "scope. Use --variant-definition/-V workflow_manager=WORKFLOW_MANAGER, instead",
    )

    subparser.add_argument(
        "--dry-run",
        "--print",
        dest="dry_run",
        action="store_true",
        help="perform a dry run. Print resulting config to screen and not "
        + "to the workspace configuration file",
    )

    subparser.add_argument(
        "--overwrite",
        dest="overwrite",
        action="store_true",
        help="overwrite existing definitions with newly generated definitions",
    )

    variable_control = subparser.add_mutually_exclusive_group()
    variable_control.add_argument(
        "--include-default-variables",
        "-i",
        action="store_true",
        help="whether to include default variable values in the resulting config",
    )

    variable_control.add_argument(
        "--workload-name-variable",
        "-w",
        default=None,
        metavar="VAR",
        help="variable name to collapse workloads in",
    )

    subparser.add_argument(
        "--zip",
        "-z",
        dest="zips",
        action="append",
        help="zip to define for the experiments, in the format zipname=[zipvar1,zipvar2]",
    )

    subparser.add_argument(
        "--matrix",
        "-m",
        dest="matrix",
        help="comma delimited list of variable names to matrix in the experiments",
    )

    subparser.add_argument(
        "--default-variable-value",
        default="",
        help="default value for any required, but undefined, variable. Default is '' "
        "which is likely to cause validation errors",
    )


def workspace_manage_experiments(args):
    """Perform experiment management"""

    if args.package_manager or args.workflow_manager:
        _deprecated_manage_experiments_arguments()

    ws = ramble.cmd.find_workspace(args)

    if ws is None:
        logger.warn("No active workspace found. Defaulting to `--dry-run`")

        root = tempfile.TemporaryDirectory()
        ws = ramble.workspace.Workspace(str(root))
        ws.dry_run = True
    else:
        ws.dry_run = args.dry_run

    workload_filters = ["*"]
    if args.workload_filters:
        workload_filters = args.workload_filters

    variable_filters = ["*"]
    if args.variable_filters:
        variable_filters = args.variable_filters

    variable_definitions = []
    if args.variable_definitions:
        variable_definitions = args.variable_definitions

    variant_definitions = args.variant_definitions if args.variant_definitions else []

    zips = []
    if args.zips:
        zips = args.zips

    matrix = None
    if args.matrix:
        matrix = args.matrix

    ws.add_experiments(
        args.application,
        args.workload_name_variable,
        workload_filters,
        args.include_default_variables,
        args.default_variable_value,
        variable_filters,
        variable_definitions,
        variant_definitions,
        args.experiment_name,
        args.package_manager,
        args.workflow_manager,
        zips,
        matrix,
        args.overwrite,
    )

    if ws.dry_run:
        ws.print_config()


def workspace_manage_software_setup_parser(subparser):
    """manage workspace software definitions"""

    subparser.add_argument(
        "--environment-name",
        "--env",
        dest="environment_name",
        metavar="ENV",
        help="Name of environment to define",
    )

    env_types = subparser.add_mutually_exclusive_group()
    env_types.add_argument(
        "--environment-packages",
        dest="environment_packages",
        help="Comma separated list of packages to add into environment",
        metavar="PKG1,PKG2,PKG2",
    )

    env_types.add_argument(
        "--external-env",
        dest="external_env_path",
        help="Path to external environment description",
        metavar="PATH",
    )

    subparser.add_argument(
        "--package-name",
        "--pkg",
        dest="package_name",
        metavar="NAME",
        help="Name of package to define",
    )

    subparser.add_argument(
        "--package-spec",
        "--pkg-spec",
        "--spec",
        dest="package_spec",
        metavar="SPEC",
        help="Value for the pkg_spec attribute in the defined package",
    )

    subparser.add_argument(
        "--compiler-package",
        "--compiler-pkg",
        "--compiler",
        dest="compiler_package",
        metavar="PKG",
        help="Value for the compiler attribute in the defined package",
    )

    subparser.add_argument(
        "--compiler-spec",
        dest="compiler_spec",
        metavar="SPEC",
        help="Value for the compiler_spec attribute in the defined package",
    )

    subparser.add_argument(
        "--package-manager-prefix",
        "--prefix",
        dest="package_manager_prefix",
        metavar="PREFIX",
        help="Prefix for defined package attributes. "
        "Resulting attributes will be {prefix}_pkg_spec.",
    )

    modify_types = subparser.add_mutually_exclusive_group()
    modify_types.add_argument(
        "--remove",
        "--delete",
        action="store_true",
        help="Whether to remove named package and environment definitions if they exist.",
    )

    modify_types.add_argument(
        "--overwrite",
        "-o",
        action="store_true",
        help="Whether to overwrite existing definitions or not.",
    )

    subparser.add_argument(
        "--dry-run",
        "--print",
        dest="dry_run",
        action="store_true",
        help="perform a dry run. Print resulting config to screen and not "
        + "to the workspace configuration file",
    )


def workspace_manage_software(args):
    """Execute workspace manage software command"""
    ws = ramble.cmd.find_workspace(args)

    if ws is None:
        import tempfile

        logger.warn("No active workspace found. Defaulting to `--dry-run`")

        root = tempfile.TemporaryDirectory()
        ws = ramble.workspace.Workspace(str(root))
        ws.dry_run = True
    else:
        ws.dry_run = args.dry_run

    if args.package_name:
        ws.manage_packages(
            args.package_name,
            args.package_spec,
            args.compiler_package,
            args.compiler_spec,
            args.package_manager_prefix,
            args.remove,
            args.overwrite,
        )

    if args.environment_name:
        ws.manage_environments(
            args.environment_name,
            args.environment_packages,
            args.external_env_path,
            args.remove,
            args.overwrite,
        )

    if ws.dry_run:
        ws.print_config()


def workspace_manage_includes_setup_parser(subparser):
    """manage workspace includes"""
    actions = subparser.add_mutually_exclusive_group()
    actions.add_argument(
        "--list", "-l", action="store_true", help="whether to print existing includes"
    )

    actions.add_argument(
        "--remove",
        "-r",
        dest="remove_pattern",
        metavar="PATTERN",
        help="whether to remove an existing include by name / pattern",
    )

    actions.add_argument(
        "--remove-index",
        dest="remove_index",
        type=int,
        metavar="IDX",
        help="whether to remove an existing include by index",
    )

    actions.add_argument(
        "--add", "-a", dest="add_include", metavar="PATH", help="whether to add a new include"
    )


def workspace_manage_includes(args):
    """Execute workspace manage include command"""

    ws = ramble.cmd.require_active_workspace(cmd_name="workspace manage includes")

    if args.list:
        with ws.read_transaction():
            workspace_dict = ws._get_workspace_dict()
            if namespace.include in workspace_dict[namespace.ramble]:
                includes = workspace_dict[namespace.ramble][namespace.include]
                if includes:
                    logger.msg("Workspace includes:")
                    for idx, include in enumerate(includes):
                        logger.msg(f"{idx}: {include}")
                    return
            logger.msg("Workspace contains no includes.")
    elif args.remove_index is not None:
        with ws.write_transaction():
            ws.remove_include(index=args.remove_index)
    elif args.remove_pattern:
        with ws.write_transaction():
            ws.remove_include(pattern=args.remove_pattern)
    elif args.add_include:
        with ws.write_transaction():
            ws.add_include(args.add_include)


def workspace_manage_modifiers_setup_parser(subparser):
    """manage workspace modifiers"""
    actions = subparser.add_mutually_exclusive_group(required=True)
    actions.add_argument(
        "--list", "-l", action="store_true", help="whether to print existing modifiers"
    )

    actions.add_argument(
        "--add",
        action="store_true",
        help="whether to remove an existing modifier by index",
    )

    actions.add_argument(
        "--remove",
        action="store_true",
        help="whether to remove an existing modifier by index",
    )

    subparser.add_argument(
        "--mod-index",
        "-i",
        dest="remove_index",
        default=None,
        type=int,
        metavar="INDEX",
        help="index of modifier to remove, only used with --remove",
    )

    subparser.add_argument(
        "--scope",
        "-s",
        dest="scope",
        metavar="SCOPE",
        default=None,
        help="scope of modifier to manage. Can be a glob when removing. Of the form "
        "<application_name>:<workload_name>:<experiment_name> or 'workspace' to "
        "manage workspace modifiers.",
    )

    subparser.add_argument(
        "--name",
        "-n",
        dest="name",
        metavar="NAME",
        default=None,
        help="name of modifier to manage. Can be a glob when removing, and defaults to '*'. "
        "Should be the name of a modifier object.",
    )

    subparser.add_argument(
        "--mode",
        "-m",
        dest="mode",
        metavar="MODE",
        default=None,
        help="mode of modifier to manage. Can be a glob when removing, and defaults to None, "
        "using the default for the modifier. ",
    )

    subparser.add_argument(
        "--on-executable",
        "-e",
        dest="on_executable",
        metavar="EXEC_LIST",
        default=None,
        help="list of 'on_executable' strings to apply for a new modifier. Ignored when removing. "
        "Should be of the form '[<pattern1>,<pattern2>,<pattern3>...]'",
    )

    subparser.add_argument(
        "--dry-run",
        action="store_true",
        help="whether to print the config without editing it, or to edit it directly.",
    )


def workspace_manage_modifiers(args):
    """Execute workspace manage modifiers command"""

    ws = ramble.cmd.require_active_workspace(cmd_name="workspace manage modifiers")

    if args.remove:
        remove_index = None
        if args.remove_index is not None:
            remove_index = args.remove_index

        with ws.write_transaction():
            removed = ws.remove_modifier(
                remove_index=remove_index,
                scope_pattern=args.scope,
                name_pattern=args.name,
                mode_pattern=args.mode,
                dry_run=args.dry_run,
            )

            if args.dry_run:
                ws.print_config()

            if removed > 1:
                logger.msg(f"Removed {removed} modifiers from workspace.")
            elif removed == 1:
                logger.msg(f"Removed {removed} modifier from workspace.")
            else:
                logger.msg("No modifiers matched criteria. 0 modifiers removed from workspace.")

    elif args.add:
        with ws.write_transaction():
            added = ws.add_modifier(
                scope=args.scope,
                name_pattern=args.name,
                mode=args.mode,
                on_executable=args.on_executable,
                dry_run=args.dry_run,
            )

            if args.dry_run:
                ws.print_config()

            if added > 1:
                logger.msg(f"Added {added} modifiers to workspace.")
            elif added == 1:
                logger.msg(f"Added {added} modifier to workspace.")
            else:
                logger.msg("No modifiers matched criteria. 0 modifiers added to workspace.")
    elif args.list:
        with ws.read_transaction():
            ws.print_modifiers()


def workspace_manage_filter_groups_setup_parser(subparser):
    """manage workspace filter groups"""
    scopes_metavar = ramble.config.scopes_metavar

    subparser.add_argument(
        "--scope",
        choices=ramble.config.scopes_choices(include_workspace=True),
        metavar=scopes_metavar,
        default=None,
        help="configuration scope to modify/list",
    )

    actions = subparser.add_subparsers(metavar="ACTION", dest="action")

    add_parser = actions.add_parser("add", help="add a filter group")
    add_parser.add_argument("-n", "--name", required=True, help="name of filter group")
    add_parser.add_argument(
        "--where",
        action="append",
        help="inclusive filter expression. Can be specified multiple times.",
    )
    add_parser.add_argument(
        "--exclude-where",
        dest="exclude_where",
        action="append",
        help="exclusive filter expression. Can be specified multiple times.",
    )

    remove_parser = actions.add_parser("remove", aliases=["rm"], help="remove a filter group")
    remove_parser.add_argument("-n", "--name", required=True, help="name of filter group")

    list_parser = actions.add_parser("list", help="list defined filter groups")
    list_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="show the filter group definition for each",
    )
    actions.add_parser("blame", help="show defined filter groups with sources")


def workspace_manage_filter_groups(args):
    """Execute workspace manage filter-groups command"""
    ws = ramble.cmd.require_active_workspace(cmd_name="workspace manage filter-groups")

    if args.action == "add":
        workspace_manage_filter_groups_add(ws, args)
    elif args.action in ("remove", "rm"):
        workspace_manage_filter_groups_remove(ws, args)
    elif args.action == "list":
        workspace_manage_filter_groups_list(ws, args)
    elif args.action == "blame":
        workspace_manage_filter_groups_blame(ws, args)


def _resolve_workspace_manage_scope(ws, args, default_scope):
    scope = args.scope if args.scope else default_scope
    if scope:
        try:
            scope = ramble.config.resolve_scope(scope)
        except ValueError as e:
            logger.die(str(e))
    return scope


def workspace_manage_filter_groups_add(ws, args):
    scope = _resolve_workspace_manage_scope(ws, args, ws.ws_file_config_scope_name())
    ramble.cmd.filter_groups.filter_groups_add(scope, args)


def workspace_manage_filter_groups_remove(ws, args):
    scope = _resolve_workspace_manage_scope(ws, args, ws.ws_file_config_scope_name())
    ramble.cmd.filter_groups.filter_groups_remove(scope, args)


def workspace_manage_filter_groups_list(ws, args):
    verbose = getattr(args, "verbose", False)
    resolved_scope_name = None
    if args.scope:
        resolved_scope_name = _resolve_workspace_manage_scope(ws, args, None)

    ramble.cmd.filter_groups.print_filter_groups(
        resolved_scope_name=resolved_scope_name,
        original_scope_name=args.scope,
        verbose=verbose,
    )


def workspace_manage_filter_groups_blame(ws, args):
    ramble.config.config.print_section("filter_groups", blame=True)


def workspace_generate_config_setup_parser(subparser):
    """generate current workspace config"""
    workspace_manage_experiments_setup_parser(subparser)


def workspace_generate_config(args):
    """Generate a configuration file for this ramble workspace"""
    workspace_manage_experiments(args)


def workspace_experiment_logs_setup_parser(subparser):
    """print log information for workspace"""
    default_filters = subparser.add_mutually_exclusive_group()
    default_filters.add_argument(
        "--limit-one", action="store_true", help="only print the first log information block"
    )

    default_filters.add_argument(
        "--first-failed",
        action="store_true",
        help="only print the information for the first failed experiment. "
        + "Requires `ramble workspace analyze` to have been run previously",
    )

    default_filters.add_argument(
        "--failed", action="store_true", help="print only failed experiment logs"
    )

    arguments.add_common_arguments(
        subparser,
        ["where", "exclude_where", "filter_tags"],
    )


def workspace_experiment_logs(args):
    """Print log information for workspace"""
    current_pipeline = ramble.pipeline.pipelines.logs
    ws = ramble.cmd.require_active_workspace("workspace experiment-logs", args.dry_run)

    first_only = args.limit_one or args.first_failed
    where_filter = args.where.copy() if args.where else []
    exclude_filter = args.exclude_where.copy() if args.exclude_where else []
    only_failed = args.first_failed or args.failed

    if only_failed:
        exclude_filter.append(["'{experiment_status}' == 'SUCCESS'"])

    filters = ramble.filters.Filters(
        include_where_filters=where_filter,
        exclude_where_filters=exclude_filter,
        tags=args.filter_tags,
    )

    pipeline_cls = ramble.pipeline.pipeline_class(current_pipeline)
    pipeline = pipeline_cls(ws, filters, first_only=first_only)
    with ws.write_transaction():
        workspace_run_pipeline(args, pipeline)


#: Dictionary mapping subcommand names and aliases to functions
subcommand_functions: Dict[str, Callable] = {}


def sanitize_arg_name(base_name):
    """Allow function names to be remapped (eg `-` to `_`)"""
    formatted_name = base_name.replace("-", "_")
    return formatted_name


def setup_parser(subparser):
    sp = subparser.add_subparsers(metavar="SUBCOMMAND", dest="workspace_command")

    for name in subcommands:
        if isinstance(name, (list, tuple)):
            name, aliases = name[0], name[1:]
        else:
            aliases = []

        # add commands to subcommands dict
        function_name = sanitize_arg_name(f"workspace_{name}")

        function = globals()[function_name]
        for alias in [name] + aliases:
            subcommand_functions[alias] = function

        # make a subparser and run the command's setup function on it
        setup_parser_cmd_name = sanitize_arg_name(f"workspace_{name}_setup_parser")
        setup_parser_cmd = globals()[setup_parser_cmd_name]

        subsubparser = sp.add_parser(
            name,
            aliases=aliases,
            help=setup_parser_cmd.__doc__,
            description=setup_parser_cmd.__doc__,
        )
        setup_parser_cmd(subsubparser)

        # inject --dry-run into subcommands
        if "--dry-run" not in subsubparser._option_string_actions:
            subsubparser.add_argument(
                "--dry-run",
                dest="dry_run",
                action="store_true",
                help=f"perform a dry run of the {name} command",
            )


def workspace(parser, args, unknown_args):
    """Look for a function called workspace_<name> and call it."""
    action = subcommand_functions[args.workspace_command]
    if unknown_args:
        arguments.validate_unknown_args(action, unknown_args)

    if arguments.allows_unknown_args(action):
        action(args, unknown_args)
    else:
        action(args)


manage_subcommand_functions: Dict[str, Callable] = {}


def workspace_manage(args):
    """Look for a function for the manage subcommand, and execute it."""
    action = manage_subcommand_functions[args.manage_command]
    action(args)


def workspace_manage_setup_parser(subparser):
    """manage workspace definitions"""
    sp = subparser.add_subparsers(metavar="SUBCOMMAND", dest="manage_command")

    for name in manage_commands:
        if isinstance(name, (list, tuple)):
            name, aliases = name[0], name[1:]
        else:
            aliases = []

        # add commands to subcommands dict
        function_name = sanitize_arg_name(f"workspace_manage_{name}")

        function = globals()[function_name]
        for alias in [name] + aliases:
            manage_subcommand_functions[alias] = function

        # make a subparser and run the command's setup function on it
        setup_parser_cmd_name = sanitize_arg_name(f"workspace_manage_{name}_setup_parser")
        setup_parser_cmd = globals()[setup_parser_cmd_name]

        subsubparser = sp.add_parser(
            name,
            aliases=aliases,
            help=setup_parser_cmd.__doc__,
            description=setup_parser_cmd.__doc__,
        )
        setup_parser_cmd(subsubparser)
