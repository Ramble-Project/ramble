# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""This is the implementation of the Ramble command line executable.

In a normal Ramble installation, this is invoked from the bin/ramble script
after the system path is set up.
"""

import argparse
import contextlib
import operator
import os
import pstats
import re
import shlex
import signal
import sys
import traceback
import warnings
from typing import Any, Dict, List, Optional, cast

import jsonschema
import ruamel

import llnl.util.lang
import llnl.util.tty.colify
from llnl.util import tty

import ramble.cmd
import ramble.cmd.common.arguments
import ramble.config
import ramble.paths
import ramble.repository
import ramble.util.colors as color
import ramble.util.version
import ramble.workspace
import ramble.workspace.shell
from ramble.error import RambleCommandError, RambleError
from ramble.util.logger import logger

import spack.util.debug
import spack.util.environment
from spack.util.executable import CommandNotFoundError

_USAGE_SPACES_RE = re.compile(r"[ ]{2,}")
_USAGE_CHARS_RE = re.compile(r"\[-(.)\]")
_USAGE_OPT_RE = re.compile(r"\[-.\] ?")

#: names of profile statistics
stat_names = pstats.Stats.sort_arg_dict_default

#: help levels in order of detail (i.e., number of commands shown)
levels = ["short", "long"]

#: intro text for help at different levels
intro_by_level = {
    "short": "These are common ramble commands:",
    "long": "Complete list of ramble commands:",
}

#: control top-level ramble options shown in basic vs. advanced help
options_by_level = {"short": ["h", "k", "V", "color", "d"], "long": "all"}

#: Longer text for each section, to show in help
section_descriptions = {
    "admin": "administration",
    "basic": "query applications",
    "config": "configuration",
    "developer": "developer",
    "help": "more help",
    "system": "system",
}

#: preferential command order for some sections (e.g., build pipeline is
#: in execution order, not alphabetical)
section_order = {
    "basic": ["list", "info", "find"],
}

#: Properties that commands are required to set.
required_command_properties = ["level", "section", "description"]

#: Recorded directory where ramble command was originally invoked
ramble_working_dir = None
ramble_ld_library_path = os.environ.get("LD_LIBRARY_PATH", "")


def set_working_dir():
    """Change the working directory to getcwd, or ramble prefix if no cwd."""
    global ramble_working_dir
    try:
        ramble_working_dir = os.getcwd()
    except OSError:
        os.chdir(ramble.paths.prefix)
        ramble_working_dir = ramble.paths.prefix


def add_all_commands(parser):
    """Add all ramble subcommands to the parser."""
    for cmd in ramble.cmd.all_commands():
        parser.add_command(cmd)


def index_commands():
    """create an index of commands by section for this help level"""
    index: Dict[str, Dict[str, List[str]]] = {}
    for command in ramble.cmd.all_commands():
        cmd_module = ramble.cmd.get_module(command)

        # make sure command modules have required properties
        for p in required_command_properties:
            prop = getattr(cmd_module, p, None)
            if not prop:
                logger.die(f"Command doesn't define a property '{p}': {command}")

        # add commands to lists for their level and higher levels
        for level in reversed(levels):
            level_sections = index.setdefault(level, {})
            commands = level_sections.setdefault(cmd_module.section, [])
            commands.append(command)
            if level == cmd_module.level:
                break

    return index


class RambleHelpFormatter(argparse.RawTextHelpFormatter):
    def _format_actions_usage(self, actions, groups):
        """Formatter with more concise usage strings."""
        usage = super()._format_actions_usage(actions, groups)

        # Eliminate any occurrence of two or more consecutive spaces
        usage = _USAGE_SPACES_RE.sub(" ", usage)

        # compress single-character flags that are not mutually exclusive
        # at the beginning of the usage string
        chars = "".join(_USAGE_CHARS_RE.findall(usage))
        usage = _USAGE_OPT_RE.sub("", usage)
        if chars:
            usage = f"[-{chars}] {usage}"
        return usage.strip()

    def add_arguments(self, actions):
        actions = sorted(actions, key=operator.attrgetter("option_strings"))
        super().add_arguments(actions)


class RambleArgumentParser(argparse.ArgumentParser):
    def format_help_sections(self, level):
        """Format help on sections for a particular verbosity level.

        Args:
            level (str): 'short' or 'long' (more commands shown for long)
        """
        if level not in levels:
            raise ValueError(f"level must be one of: {levels}")

        # lazily add all commands to the parser when needed.
        add_all_commands(self)

        """Print help on subcommands in neatly formatted sections."""
        formatter = self._get_formatter()

        # Create a list of subcommand actions. Argparse internals are nasty!
        # Note: you can only call _get_subactions() once.  Even nastier!
        if not hasattr(self, "actions"):
            subparsers = getattr(self, "_subparsers", None)
            actions = getattr(subparsers, "_actions", []) if subparsers else []
            self.actions = (
                actions[-1]._get_subactions()
                if actions and hasattr(actions[-1], "_get_subactions")
                else []
            )

        # make a set of commands not yet added.
        remaining = set(ramble.cmd.all_commands())

        def add_group(group):
            formatter.start_section(group.title)
            formatter.add_text(group.description)
            formatter.add_arguments(group._group_actions)
            formatter.end_section()

        def add_subcommand_group(title, commands):
            """Add informational help group for a specific subcommand set."""
            cmd_set = set(commands)

            # make a dict of commands of interest
            cmds = {a.dest: a for a in self.actions if a.dest in cmd_set}

            # add commands to a group in order, and add the group
            group = argparse._ArgumentGroup(self, title=title)
            for name in commands:
                group._add_action(cmds[name])
                if name in remaining:
                    remaining.remove(name)
            add_group(group)

        # select only the options for the particular level we're showing.
        show_options = options_by_level[level]
        if show_options != "all":
            opts = {
                opt.option_strings[0].strip("-"): opt for opt in self._optionals._group_actions
            }

            new_actions = [opts[letter] for letter in show_options]
            self._optionals._group_actions = new_actions

        # custom, more concise usage for top level
        help_options = self._optionals._group_actions
        help_options = help_options + [self._positionals._group_actions[-1]]
        formatter.add_usage(self.usage, help_options, self._mutually_exclusive_groups)

        # description
        formatter.add_text(self.description)

        # start subcommands
        formatter.add_text(intro_by_level[level])

        # add argument groups based on metadata in commands
        index = index_commands()
        sections = index[level]

        for section in sorted(sections):
            if section == "help" or section == "secret":
                continue  # Cover help in the epilog.

            group_description = section_descriptions.get(section, section)

            to_display = sections[section]
            commands: List[str] = []

            # add commands whose order we care about first.
            if section in section_order:
                commands.extend(cmd for cmd in section_order[section] if cmd in to_display)

            # add rest in alphabetical order.
            commands.extend(cmd for cmd in sorted(sections[section]) if cmd not in commands)

            # add the group to the parser
            add_subcommand_group(group_description, commands)

        # optionals
        add_group(self._optionals)

        # epilog
        formatter.add_text(f"""{section_descriptions['help']}:
  ramble help --all       list all commands and options
  ramble help <command>   help on a specific command
  ramble help --spec      help on the application specification syntax
  ramble docs             open https://ramble.readthedocs.io/ in a browser
""")

        # determine help from format above
        return formatter.format_help()

    def add_subparsers(self, **kwargs):
        """Ensure that sensible defaults are propagated to subparsers"""
        kwargs.setdefault("metavar", "SUBCOMMAND")

        # From Python 3.7 we can require a subparser, earlier versions
        # of argparse will error because required=True is unknown
        if sys.version_info[:2] > (3, 6):
            kwargs.setdefault("required", True)

        sp = super().add_subparsers(**kwargs)
        # This monkey patching is needed for Python 3.6, which supports
        # having a required subparser but doesn't expose the API used above
        if sys.version_info[:2] == (3, 6):
            sp.required = True

        old_add_parser = sp.add_parser

        def add_parser(name, **kwargs):
            kwargs.setdefault("formatter_class", RambleHelpFormatter)
            return old_add_parser(name, **kwargs)

        cast(Any, sp).add_parser = add_parser
        return sp

    def add_command(self, cmd_name):
        """Add one subcommand to this parser."""
        # lazily initialize any subparsers
        if not hasattr(self, "subparsers"):
            # remove the dummy "command" argument.
            if self._actions[-1].dest == "command":
                self._remove_action(self._actions[-1])
            self.subparsers = self.add_subparsers(metavar="COMMAND", dest="command")

        if cmd_name not in self.subparsers._name_parser_map:
            # each command module implements a parser() function, to which we
            # pass its subparser for setup.
            module = ramble.cmd.get_module(cmd_name)

            # build a list of aliases
            alias_list = []
            aliases = ramble.config.get("config:aliases")
            if aliases:
                alias_list = [k for k, v in aliases.items() if shlex.split(v)[0] == cmd_name]

            subparser = self.subparsers.add_parser(
                cmd_name,
                aliases=alias_list,
                help=module.description,
                description=module.description,
            )
            module.setup_parser(subparser)

        # return the callable function for the command
        return ramble.cmd.get_command(cmd_name)

    def format_help(self, level="short"):
        if self.prog == "ramble":
            # use format_help_sections for the main ramble parser, but not
            # for subparsers
            return self.format_help_sections(level)
        else:
            # in subparsers, self.prog is, e.g., 'ramble list'
            return super().format_help()

    def _check_value(self, action, value):
        # converted value must be one of the choices (if specified)
        if action.choices is not None and value not in action.choices:
            cols = llnl.util.tty.colify.colified(sorted(action.choices), indent=4, tty=True)
            msg = f"invalid choice: {value!r} choose from:\n{cols}"
            raise argparse.ArgumentError(action, msg)


def make_argument_parser(**kwargs):
    """Create an basic argument parser without any subcommands added."""
    if "color" in kwargs and sys.version_info < (3, 14):
        # The color argument was only added since Python 3.14.
        # See https://docs.python.org/3/library/argparse.html#color.
        kwargs.pop("color")

    kwargs.setdefault("prog", "ramble")

    parser = RambleArgumentParser(
        formatter_class=RambleHelpFormatter,
        add_help=False,
        description=("A flexible benchmark experiment manager."),
        **kwargs,
    )

    # stat names in groups of 7, for nice wrapping.
    stat_lines = list(zip(*(iter(stat_names),) * 7))

    parser.add_argument(
        "-h",
        "--help",
        dest="help",
        action="store_const",
        const="short",
        default=None,
        help="show this help message and exit",
    )
    parser.add_argument(
        "-H",
        "--all-help",
        dest="help",
        action="store_const",
        const="long",
        default=None,
        help="show help for all commands (same as ramble help --all)",
    )
    parser.add_argument(
        "--color",
        action="store",
        default=os.environ.get("RAMBLE_COLOR", "auto"),
        choices=("always", "never", "auto"),
        help="when to colorize output (default: auto)",
    )
    parser.add_argument(
        "-c",
        "--config",
        default=None,
        action="append",
        dest="config_vars",
        help="add one or more custom, one off config settings.",
    )
    parser.add_argument(
        "-C",
        "--config-scope",
        dest="config_scopes",
        action="append",
        metavar="DIR",
        help="add a custom configuration scope",
    )
    parser.add_argument(
        "-d",
        "--debug",
        action="count",
        default=0,
        help="write out debug messages " "(more d's for more verbosity: -d, -dd, -ddd, etc.)",
    )
    parser.add_argument(
        "--disable-passthrough",
        action="store_true",
        help="disable passthrough of expansion variables for debugging",
    )
    parser.add_argument(
        "-N",
        "--disable-logger",
        action="store_true",
        help="disable the ramble logger. All output will be printed to stdout.",
    )
    parser.add_argument(
        "-A",
        "--aggregate-warnings",
        action="store_true",
        help="aggregate warnings from the ramble logger to the end of "
        + "execution. May lose context information",
    )
    parser.add_argument(
        "-S",
        "--suppress-warnings",
        action="store_true",
        help="suppress warnings from the ramble logger.",
    )
    parser.add_argument(
        "-P",
        "--disable-progress-bar",
        action="store_true",
        help="disable the progress bars while setting up experiments.",
    )

    parser.add_argument("--timestamp", action="store_true", help="Add a timestamp to tty output")
    parser.add_argument("--pdb", action="store_true", help="run ramble under the pdb debugger")

    workspace_group = parser.add_mutually_exclusive_group()
    workspace_group.add_argument(
        "-w",
        "--workspace",
        dest="workspace",
        metavar="WRKSPC",
        action="store",
        help="run with a specific workspace (see ramble workspace)",
    )
    workspace_group.add_argument(
        "-D",
        "--workspace-dir",
        dest="workspace_dir",
        metavar="DIR",
        action="store",
        help="run with a workspace directory (ignore named workspaces)",
    )
    workspace_group.add_argument(
        "-W",
        "--no-workspace",
        dest="no_workspace",
        action="store_true",
        help="run without any workspaces activated (see ramble workspace)",
    )
    parser.add_argument(
        "--use-workspace-repo",
        action="store_true",
        help="when running in a workspace, use its application repository",
    )

    parser.add_argument(
        "--resolve-variables-in-subprocesses",
        action="store_true",
        help="Allow resolution of environment variables when launching subprocesses",
    )

    parser.add_argument(
        "-k",
        "--insecure",
        action="store_true",
        help="do not check ssl certificates when downloading",
    )
    parser.add_argument(
        "-l",
        "--enable-locks",
        action="store_true",
        dest="locks",
        default=None,
        help="use filesystem locking (default)",
    )
    parser.add_argument(
        "-L",
        "--disable-locks",
        action="store_false",
        dest="locks",
        help="do not use filesystem locking (unsafe)",
    )
    parser.add_argument(
        "-m",
        "--mock",
        action="store_true",
        help="use the builtin.mock repository instead of builtin",
    )
    parser.add_argument(
        "--overwrite-inventories",
        action="store_true",
        help="enables all workspace actions to overwrite experiment inventories",
    )

    for obj in ramble.repository.ObjectTypes:
        objname = obj.name.replace("_", "-")
        print_name = obj.name.replace("_", " ")
        parser.add_argument(
            f"--mock-{objname}",
            action="store_true",
            help=f"use mock {print_name} instead of real ones",
        )

    # TODO (dwj): Do we need this?
    # parser.add_argument(
    #   # '-b', '--bootstrap', action='store_true',
    #   # help="use bootstrap configuration (bootstrap store, config, externals)")
    parser.add_argument(
        "-p",
        "--profile",
        action="store_true",
        dest="ramble_profile",
        help="profile execution using cProfile",
    )
    parser.add_argument(
        "--sorted-profile",
        default=None,
        metavar="STAT",
        help="profile and sort by one or more of:\n[%s]"
        % ",\n ".join([", ".join(line) for line in stat_lines]),
    )
    parser.add_argument(
        "--lines",
        default=20,
        action="store",
        help="lines of profile output or 'all' (default: 20)",
    )
    parser.add_argument(
        "--profile-restrictions",
        default="",
        action="store",
        help=(
            "Comma-separated restrictions applied to the cProfiler. "
            "When specified, it takes precedence over `--lines`. "
            "Example: `--profile-restrictions 'logger,5'` limits the list to functions with "
            "'logger' in the path, and then shows the first 5 of them. "
            "See https://docs.python.org/3/library/profile.html#pstats.Stats.print_stats for more "
            "details."
        ),
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="print additional output during builds"
    )
    parser.add_argument(
        "--stacktrace",
        action="store_true",
        default="RAMBLE_STACKTRACE" in os.environ,
        help="add stacktraces to all printed statements",
    )
    parser.add_argument(
        "-V", "--version", action="store_true", help="show version number and exit"
    )

    return parser


def send_warning_to_tty(message, *args):
    """Redirects messages to ramble.util.logger.logger.warn."""
    logger.warn(message)


def mock_repositories(objects):
    import spack.util.spack_yaml as syaml

    for obj in objects:
        obj_section = ramble.repository.type_definitions[obj]["config_section"]
        key = syaml.syaml_str(obj_section)
        cast(Any, key).override = True

        ramble.config.config.scopes["command_line"].sections[obj_section] = syaml.syaml_dict(
            [(key, [ramble.paths.mock_builtin_path])]
        )

        ramble.repository.paths[obj] = ramble.repository.create(
            ramble.config.config, object_type=obj
        )


def setup_main_options(args):
    """Configure ramble globals based on the basic options."""
    # Assign a custom function to show warnings
    warnings.showwarning = send_warning_to_tty

    # Set up environment based on args.
    tty.set_verbose(args.verbose)
    tty.set_debug(args.debug)
    tty.set_stacktrace(args.stacktrace)

    # debug must be set first so that it can even affect behavior of
    # errors raised by ramble.config.

    if args.debug:
        ramble.error.debug = args.debug
        spack.util.debug.register_interrupt_handler()
        ramble.config.set("config:debug", True, scope="command_line")
        spack.util.environment.tracing_enabled = True
    if args.timestamp:
        tty.set_timestamp(True)

    # override lock configuration if passed on command line
    if args.locks is not None:
        if args.locks is False:
            spack.util.lock.check_lock_safety(ramble.paths.prefix)
        ramble.config.set("config:locks", args.locks, scope="command_line")

    # override disable_passthrough configuration if passed on command line
    if args.disable_passthrough:
        ramble.config.set("config:disable_passthrough", True, scope="command_line")

    if args.disable_logger:
        ramble.config.set("config:disable_logger", True, scope="command_line")

    logger.enabled = not ramble.config.get("config:disable_logger", False)

    if args.aggregate_warnings:
        ramble.config.set("config:aggregate_warnings", True, scope="command_line")

    if args.suppress_warnings:
        ramble.config.set("config:suppress_warnings", True, scope="command_line")

    if args.disable_progress_bar:
        ramble.config.set("config:disable_progress_bar", True, scope="command_line")

    if args.overwrite_inventories:
        ramble.config.set("config:overwrite_inventories", True, scope="command_line")

    objects_to_mock = set()
    if args.mock:
        for obj in ramble.repository.ObjectTypes:
            objects_to_mock.add(obj)

    for obj in ramble.repository.ObjectTypes:
        if hasattr(args, f"mock_{obj.name}") and getattr(args, f"mock_{obj.name}"):
            objects_to_mock.add(obj)

    mock_repositories(objects_to_mock)

    # If the user asked for it, don't check ssl certs.
    if args.insecure:
        logger.warn("You asked for --insecure. Will NOT check SSL certificates.")
        ramble.config.set("config:verify_ssl", False, scope="command_line")

    # If the user asked for it allow env-vars to resolve in subprocess calls
    if args.resolve_variables_in_subprocesses:
        ramble.config.set("config:resolve_variables_in_subprocesses", True, scope="command_line")

    # Use the ramble config command to handle parsing the config strings
    for config_var in args.config_vars or []:
        ramble.config.add(fullpath=config_var, scope="command_line")

    # when to use color (takes always, auto, or never)
    color.set_color_when(args.color)


def _invoke_command(command, parser, args, unknown_args):
    """Run a ramble command *without* setting ramble global options."""
    try:
        if ramble.cmd.common.arguments.allows_unknown_args(command):
            return_val = command(parser, args, unknown_args)
        else:
            if unknown_args:
                logger.die(f'unrecognized arguments: {" ".join(unknown_args)}')
            return_val = command(parser, args)
    except ramble.expander.WorkloadNotDefinedError as e:
        logger.error(e)
        return 1

    # Allow commands to return and error code if they want
    return 0 if return_val is None else return_val


class RambleCommand:
    """Callable object that invokes a ramble command (for testing).

    Example usage::

        list = RambleCommand('list')
        list('hostname')

    Use this to invoke Ramble commands directly from Python and check
    their output.
    """

    def __init__(self, command_name):
        """Create a new RambleCommand that invokes ``command_name`` when called.

        Args:
            command_name (str): name of the command to invoke
        """
        self.parser = make_argument_parser()
        self.command = self.parser.add_command(command_name)
        self.command_name = command_name

    def __call__(self, *argv, **kwargs):
        """Invoke this RambleCommand.

        Args:
            argv (list): command line arguments.

        Keyword Args:
            fail_on_error (optional bool): Don't raise an exception on error
            global_args (optional list): List of global ramble arguments:
                simulates ``ramble [global_args] [command] [*argv]``

        Returns:
            str: combined output and error as a string

        On return, if ``fail_on_error`` is False, return value of command
        is set in ``returncode`` property, and the error is set in the
        ``error`` property.  Otherwise, raise an error.
        """
        # set these before every call to clear them out
        self.returncode = None
        self.error = None
        self.binary_output = b""
        self.output = ""

        prepend = kwargs.get("global_args", [])

        args, unknown = self.parser.parse_known_args(prepend + [self.command_name] + list(argv))

        fail_on_error = kwargs.get("fail_on_error", True)

        # activate a workspace if one was specified on the command line

        if not args.no_workspace:
            ws = ramble.cmd.find_workspace(args)
            if ws:
                ramble.workspace.shell.activate(ws)
        else:
            ramble.workspace.shell.deactivate()

        try:
            with self.capture_output(enable=True):
                self.returncode = _invoke_command(self.command, self.parser, args, unknown)

        except SystemExit as e:
            self.returncode = e.code

        except BaseException as e:
            logger.debug(e)
            self.error = e
            if fail_on_error:
                raise
        finally:
            self.output = self.binary_output.decode("utf-8", errors="replace")

        if fail_on_error and self.returncode not in (None, 0):
            raise RambleCommandError(
                "Command exited with code %s: %s(%s).\nCommand output:\n\n%s"
                % (
                    self.returncode,
                    self.command_name,
                    ", ".join("'%s'" % a for a in argv),
                    self.output,
                )
            )

        return self.output

    def _log_command_output(self, out):
        logger.debug("Command output:\n%s" % self.output)

    @contextlib.contextmanager
    def capture_output(self, enable: bool = True):
        import io
        import os
        import sys
        import tempfile

        if not enable:
            yield self
            return

        with tempfile.TemporaryFile(mode="w+b") as tmp_file:
            fds = set()
            for stream in (sys.stdout, sys.stderr):
                try:
                    fds.add(stream.fileno())
                except (io.UnsupportedOperation, AttributeError):
                    pass
            fds.update((1, 2))
            saved_fds = {fd: os.dup(fd) for fd in fds}

            sys.stdout.flush()
            sys.stderr.flush()

            for fd in fds:
                os.dup2(tmp_file.fileno(), fd)

            saved_stdout = sys.stdout
            saved_stderr = sys.stderr

            new_out = io.TextIOWrapper(
                os.fdopen(os.dup(tmp_file.fileno()), "wb"), encoding="utf-8"
            )
            new_err = io.TextIOWrapper(
                os.fdopen(os.dup(tmp_file.fileno()), "wb"), encoding="utf-8"
            )
            sys.stdout = new_out
            sys.stderr = new_err

            try:
                yield self
            finally:
                sys.stdout.flush()
                sys.stderr.flush()
                new_out.close()
                new_err.close()

                sys.stdout = saved_stdout
                sys.stderr = saved_stderr

                for fd, saved_fd in saved_fds.items():
                    os.dup2(saved_fd, fd)
                    os.close(saved_fd)
                tmp_file.seek(0)
                self.binary_output = tmp_file.read()


def _profile_wrapper(command, parser, args, unknown_args):
    import cProfile

    from ramble.util import conversions

    if args.profile_restrictions:
        restrictions_raw = args.profile_restrictions.split(",")
    else:
        restrictions_raw = [args.lines if args.lines != "all" else -1]
    restrictions = [conversions.convert_to_number(v) for v in restrictions_raw]

    # allow comma-separated list of fields
    sortby = ["time"]
    if args.sorted_profile:
        sortby = args.sorted_profile.split(",")
        for stat in sortby:
            if stat not in stat_names:
                logger.die(f"Invalid sort field: {stat}")

    try:
        # make a profiler and run the code.
        pr = cProfile.Profile()
        pr.enable()
        return _invoke_command(command, parser, args, unknown_args)

    finally:
        pr.disable()

        # print out profile stats.
        stats = pstats.Stats(pr, stream=sys.stderr)
        stats.sort_stats(*sortby)
        stats.print_stats(*restrictions)


def resolve_alias(cmd_name, cmd):
    """Resolves aliases in the given command.

    Args:
        cmd_name: command name.
        cmd: command line arguments.

    Returns:
        tuple[str, list[str]]: new command name and arguments.
    """
    all_commands = ramble.cmd.all_commands()
    aliases = ramble.config.get("config:aliases")

    if aliases:
        for key, value in aliases.items():
            if " " in key:
                logger.warn(
                    f"Alias '{key}' (mapping to '{value}') contains a space"
                    ", which is not supported."
                )
            if key in all_commands:
                logger.warn(
                    f"Alias '{key}' (mapping to '{value}') attempts to override"
                    " built-in command."
                )

    if cmd_name not in all_commands:
        if aliases:
            alias = aliases.get(cmd_name)
        else:
            alias = None

        if alias is not None:
            alias_parts = shlex.split(alias)
            cmd_name = alias_parts[0]
            cmd = alias_parts + cmd[1:]

    return cmd_name, cmd


def _main(argv=None):
    """Logic for the main entry point for the Ramble command.

    ``main()`` calls ``_main()`` and catches any errors that emerge.

    ``_main()`` handles:

    1. Parsing arguments;
    2. Setting up configuration; and
    3. Finding and executing a Ramble command.

    Args:
        argv (list | None): command line arguments, NOT including
            the executable name. If None, parses from ``sys.argv``.

    """
    # ------------------------------------------------------------------------
    # main() is tricky to get right, so be careful where you put things.
    #
    # Things in this first part of `main()` should *not* require any
    # configuration. This doesn't include much -- setting up th parser,
    # restoring some key environment variables, very simple CLI options, etc.
    # ------------------------------------------------------------------------

    # Create a parser with a simple positional argument first.  We'll
    # lazily load the subcommand(s) we need later. This allows us to
    # avoid loading all the modules from ramble.cmd when we don't need
    # them, which reduces startup latency.
    parser = make_argument_parser()
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args, unknown = parser.parse_known_args(argv)

    # Recover stored LD_LIBRARY_PATH variables from ramble shell function
    # This is necessary because MacOS System Integrity Protection clears
    # (DY?)LD_LIBRARY_PATH variables on process start.
    # Ramble clears these variables before building and installing applications,
    # but needs to know the prior state for commands like
    # `ramble workspace activate that modify the user environment.
    recovered_vars = ("LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH", "DYLD_FALLBACK_LIBRARY_PATH")
    for var in recovered_vars:
        stored_var_name = f"RAMBLE_{var}"
        if stored_var_name in os.environ:
            os.environ[var] = os.environ[stored_var_name]

    # Just print help and exit if run with no arguments at all
    no_args = (len(sys.argv) == 1) if argv is None else (not argv)
    if no_args:
        parser.print_help()
        return 1

    # -h, -H, and -V are special as they do not require a command, but
    # all the other options do nothing without a command.
    if args.version:
        print(ramble.util.version.get_version())
        return 0
    elif args.help:
        sys.stdout.write(parser.format_help(level=args.help))
        return 0
    elif unknown:
        logger.die(f'unrecognized arguments: {" ".join(unknown)}')

    # ------------------------------------------------------------------------
    # This part of the `main()` sets up Ramble's configuration.
    #
    # We set command line options (like --debug), then command line config
    # scopes, then workspace configuration here.
    # ------------------------------------------------------------------------

    # make ramble.config aware of any command line configuration scopes
    if args.config_scopes:
        ramble.config.command_line_scopes = args.config_scopes

    # ensure options on ramble command come before everything
    setup_main_options(args)

    # activate a workspace if one was specified on the command line
    workspace_format_error: Optional[Exception] = None
    if not args.no_workspace:
        try:
            ws = ramble.cmd.find_workspace(args)
            if ws:
                ramble.workspace.shell.activate(ws)
        # print the context but delay this exception so that commands like
        # `ramble config edit` can still work with a bad workspace.
        except ramble.workspace.RambleActiveWorkspaceError as e:
            workspace_format_error = e
        except ramble.config.ConfigFormatError as e:
            e.print_context()
            workspace_format_error = e
        except jsonschema.exceptions.ValidationError as e:
            e.print_context()
            workspace_format_error = e
        except (ruamel.yaml.parser.ParserError, ruamel.yaml.scanner.ScannerError) as e:
            workspace_format_error = e

    # ------------------------------------------------------------------------
    # Things that require configuration should go below here
    # ------------------------------------------------------------------------

    # At this point we've considered all the options to ramble itself, so we
    # need a command or we're done.
    if not args.command:
        parser.print_help()
        return 1

    # Try to load the particular command the caller asked for.
    cmd_name = args.command[0]
    cmd_name, args.command = resolve_alias(cmd_name, args.command)

    # set up a bootstrap context, if asked.
    # bootstrap context needs to include parsing the command, b/c things
    # like `ConstraintAction` and `ConfigSetAction` happen at parse time.
    bootstrap_context = llnl.util.lang.nullcontext()

    with bootstrap_context:
        suppress_warnings = ramble.config.get("config:suppress_warnings")
        aggregate_warnings = suppress_warnings or ramble.config.get("config:aggregate_warnings")
        logger.aggregate_warnings(on=aggregate_warnings)
        err = finish_parse_and_run(parser, cmd_name, args, workspace_format_error)

        if not suppress_warnings:
            logger.all_warnings()
        return err


def finish_parse_and_run(parser, cmd_name, main_args, workspace_format_error):
    """Finish parsing after we know the command to run."""
    # add the found command to the parser and re-run then re-parse
    command = parser.add_command(cmd_name)
    args, unknown = parser.parse_known_args(main_args.command)
    # Copy global options that are accessed by subcommands
    args.workspace_dir = main_args.workspace_dir
    args.workspace = main_args.workspace
    args.no_workspace = main_args.no_workspace
    args.sorted_profile = main_args.sorted_profile
    args.lines = main_args.lines
    args.profile_restrictions = main_args.profile_restrictions

    # Now that we know what command this is and what its args are, determine
    # whether we can continue with a bad workspace and raise if not.
    edit_cmds = ["workspace", "config"]
    allowed_subcommands = ["edit", "list", "deactivate"]

    if workspace_format_error:
        raise_error = False
        if cmd_name.strip() in edit_cmds:
            subcommand = getattr(args, f"{cmd_name}_command", None)

            if subcommand != "deactivate":
                raise_error = True
                logger.msg(
                    "Error while reading workspace config. In some cases this can be "
                    + "avoided by passing `-W` to ramble or by running\n"
                    + "`ramble workspace deactivate`"
                )
                if subcommand in allowed_subcommands:
                    raise_error = False

        if raise_error:
            raise workspace_format_error

    # many operations will fail without a working directory.
    set_working_dir()

    # now we can actually execute the command.
    if main_args.ramble_profile or main_args.sorted_profile:
        _profile_wrapper(command, parser, args, unknown)
    elif main_args.pdb:
        import pdb  # noqa: T100

        pdb.runctx("_invoke_command(command, parser, args, unknown)", globals(), locals())
        return 0
    else:
        return _invoke_command(command, parser, args, unknown)


def main(argv=None):
    """This is the entry point for the Ramble command.

    ``main()`` itself is just an error handler -- it handles errors for
    everything in Ramble that makes it to the top level.

    The logic is all in ``_main()``.

    Args:
        argv (list | None): command line arguments, NOT including
            the executable name. If None, parses from sys.argv.

    """
    try:
        return _main(argv)

    except RambleError as e:
        logger.debug(e)
        e.die()  # gracefully die on any RambleErrors

    except CommandNotFoundError as e:
        e.message = e.message.replace("spack requires", "ramble requires")
        raise

    except KeyboardInterrupt:
        if ramble.config.get("config:debug"):
            raise
        sys.stderr.write("\n")
        logger.error("Keyboard interrupt.")
        return signal.SIGINT.value

    except SystemExit as e:
        if ramble.config.get("config:debug"):
            traceback.print_exc()
        return e.code

    except Exception as e:
        if ramble.config.get("config:debug"):
            raise
        logger.error(e)
        return 3
