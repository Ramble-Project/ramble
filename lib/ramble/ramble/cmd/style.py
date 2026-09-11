# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import argparse
import fnmatch
import glob
import os
import re
import shlex
import shutil
import sys
import tempfile
from typing import Callable, Dict, Tuple

from llnl.util.filesystem import mkdirp, working_dir

import ramble.paths
from ramble import repository
from ramble.util.logger import logger

from spack.util.executable import ProcessError, which

description = "runs source code style checks on Ramble."
section = "developer"
level = "long"


def is_object(f):
    """Whether flake8 should consider a file as a core file or an object.

    We run flake8 with different exceptions for the core and for
    objects, since we allow `from ramble import *` and poking globals
    into objects.
    """
    return f.startswith("var/ramble/repos/") or "docs/tutorial/examples" in f


# List of patterns to include in checks.
include_patterns = [
    "bin/**",
    "lib/ramble/ramble/**",
    "var/ramble/repos/**",
    "share/ramble/scripts/**",
    "conftest.py",
]

# max line length we're enforcing (note: this duplicates what's in .flake8)
max_line_length = 99

# The black version used by the PR style test
_BLACK_GOLDEN_VERSION = "26.5.1"

common_object_exemptions = {
    # Exempt lines with urls and descriptions from overlong line errors.
    "E501": [
        r"^\s*homepage\s*=",
        r"^\s*url\s*=",
        r"^\s*git\s*=",
        r"^\s*svn\s*=",
        r"^\s*hg\s*=",
        r"^\s*list_url\s*=",
        r"^\s*version\(",
        r"^\s*variant\(",
        r"^\s*provides\(",
        r"^\s*extends\(",
        r"^\s*depends_on\(",
        r"^\s*conflicts\(",
        r"^\s*resource\(",
        r"^\s*patch\(",
    ],
    # Exempt '@when' decorated functions from redefinition errors.
    "F811": [
        r"^\s*@when\(.*\)",
    ],
}

base_class_file = repository.type_definitions[repository.ObjectTypes.base_classes]["file_name"]

# This is a dict that maps:
#   filename pattern ->
#     flake8 exemption code ->
#        list of patterns, for which matching lines should have codes applied.
#
# For each file, if the filename pattern matches, we'll add per-line
# exemptions if any patterns in the sub-dict match.
_raw_pattern_exemptions = {
    # exemptions applied only to application.py files.
    rf"application.py|{base_class_file}$": {
        # Allow 'from ramble.appkit import *' in applications,
        # but no other wildcards
        "F403": [r"^from ramble.appkit import \*$"],
        **common_object_exemptions,
    },
    # exemptions applied only to modifier.py files.
    rf"modifier.py|{base_class_file}$": {
        # Allow 'from ramble.modkit import *' in modifiers,
        # but no other wildcards
        "F403": [r"^from ramble.modkit import \*$"],
        **common_object_exemptions,
    },
    # exemptions applied only to package_manager.py files.
    rf"package_manager.py|{base_class_file}$": {
        # Allow 'from ramble.pkgmankit import *' in package_managers,
        # but no other wildcards
        "F403": [r"^from ramble.pkgmankit import \*$"],
        **common_object_exemptions,
    },
    # exemptions applied only to workflow_manager.py files.
    rf"workflow_manager.py|{base_class_file}$": {
        # Allow 'from ramble.wmkit import *' in workflow_managers,
        # but no other wildcards
        "F403": [r"^from ramble.wmkit import \*$"],
        **common_object_exemptions,
    },
    rf"platform.py|{base_class_file}$": {
        # Allow 'from ramble.platkit import *' in platforms,
        # but no other wildcards
        "F403": [r"^from ramble.platkit import \*$"],
        **common_object_exemptions,
    },
    rf"system.py|{base_class_file}$": {
        # Allow 'from ramble.syskit import *' in systems,
        # but no other wildcards
        "F403": [r"^from ramble.syskit import \*$"],
        **common_object_exemptions,
    },
    # exemptions applied to all files.
    r".py$": {
        "E501": [
            r"(https?|ftp|file)\:",  # URLs
            r'([\'"])[0-9a-fA-F]{32,}\1',  # long hex checksums
        ]
    },
}

# compile all regular expressions.
pattern_exemptions = {
    re.compile(file_pattern): {
        code: [re.compile(p) for p in patterns] for code, patterns in error_dict.items()
    }
    for file_pattern, error_dict in _raw_pattern_exemptions.items()
}

# Tools run in the given order
tool_names = ["isort", "black", "flake8", "mypy", "ruff"]

tools: Dict[str, Callable] = {}


# decorator for adding tools to the list
class tool:
    def __init__(self, name):
        self.name = name

    def __call__(self, fun):
        tools[self.name] = fun
        return fun


def changed_files(
    base=None, untracked=True, all_files=False, root=ramble.paths.prefix, is_external_repo=False
):
    """Get list of changed files in the Ramble repository."""

    git = which("git", required=True)

    if base is None:
        base = os.environ.get("GITHUB_BASE_REF", "develop")

    range = f"{base}..."

    git_args = [
        # Add changed files committed since branching off of develop
        ["diff", "--name-only", "--diff-filter=ACMR", range],
        # Add changed files that have been staged but not yet committed
        ["diff", "--name-only", "--diff-filter=ACMR", "--cached"],
        # Add changed files that are unstaged
        ["diff", "--name-only", "--diff-filter=ACMR"],
    ]

    # Add new files that are untracked
    if untracked:
        git_args.append(["ls-files", "--exclude-standard", "--other"])

    # add everything if the user asked for it
    if all_files:
        git_args.append(["ls-files", "--exclude-standard"])
    changed = set()

    with working_dir(root):
        try:
            git("rev-parse", "--is-inside-work-tree", output=str, error=str)
        except ProcessError:
            # if not a git repo, return all python files matching include patterns
            for f in glob.glob(os.path.join(root, "**", "*.py"), recursive=True):
                rel_f = os.path.relpath(f, root)
                if is_external_repo or any(fnmatch.fnmatch(rel_f, p) for p in include_patterns):
                    changed.add(rel_f)
            return sorted(changed)

        for arg_list in git_args:
            try:
                files = git(*(arg_list + ["--", "."]), output=str, error=str).split("\n")
            except ProcessError:
                continue

            for f in files:
                # Ignore non-Python files
                if not (f.endswith(".py") or f == "bin/ramble"):
                    continue

                # Only include files matching the include patterns for the core codebase
                if not is_external_repo and not any(
                    fnmatch.fnmatch(f, p) for p in include_patterns
                ):
                    continue

                # Exclude non-existent files
                if not os.path.exists(f):
                    continue

                changed.add(f)

    return sorted(changed)


def setup_parser(subparser):
    subparser.add_argument(
        "-b",
        "--base",
        action="store",
        default=None,
        help="select base branch for collecting list of modified files",
    )
    subparser.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="check all files, not just changed files",
    )
    subparser.add_argument(
        "-o",
        "--output",
        action="store_true",
        help="send filtered files to stdout as well as temp files",
    )
    subparser.add_argument(
        "-r",
        "--root-relative",
        action="store_true",
        default=False,
        help="print root-relative paths (default: cwd-relative)",
    )
    subparser.add_argument(
        "-U",
        "--no-untracked",
        dest="untracked",
        action="store_false",
        default=True,
        help="exclude untracked files from checks",
    )
    subparser.add_argument(
        "-f",
        "--fix",
        action="store_true",
        default=False,
        help="format automatically if possible with black",
    )
    subparser.add_argument(
        "-k",
        "--keep-temp",
        action="store_true",
        help="do not delete temporary directory where flake8 runs. "
        "use for debugging, to see filtered files",
    )
    tool_group = subparser.add_mutually_exclusive_group()
    tool_group.add_argument(
        "-t",
        "--tool",
        action="append",
        help=f"specify which tools to run (default: {','.join(tool_names)})",
    )
    tool_group.add_argument(
        "-s",
        "--skip",
        action="append",
        help=f"specify tools to skip (choose from {','.join(tool_names)})",
    )
    subparser.add_argument(
        "--repo-path",
        action="store",
        default=None,
        help="apply style checks and fixes to the given repository",
    )
    subparser.add_argument(
        "--tool-args",
        action="append",
        dest="tool_args",
        help="specify extra arguments to pass to tools (e.g., --tool-args ruff:'--unsafe-fixes')",
    )
    subparser.add_argument("files", nargs=argparse.REMAINDER, help="specific files to check")


def print_tool_header(tool, file_list):
    print("=======================================================")
    print(f"{tool}: running {tool} checks on ramble.")
    if file_list:
        print()
        print("Modified files:")
        for filename in file_list:
            print(f"  {filename.strip()}")
    print("=======================================================")


def print_tool_result(tool, returncode):
    if returncode == 0:
        print(f"  {tool} checks were clean")
    else:
        print(f"  {tool} found errors")


def print_output(output, args):
    root = args.repo_path if args.repo_path is not None else ramble.paths.prefix
    if args.root_relative:
        # print results relative to repo root.
        print(output)
    else:
        # print results relative to current working directory
        def cwd_relative(path):
            return f"{os.path.relpath(os.path.join(root, path.group(1)), os.getcwd())}: ["

        for line in output.split("\n"):
            print(re.sub(r"^(.*): \[", cwd_relative, line))


def add_pattern_exemptions(line, codes):
    """Add a flake8 exemption to a line."""
    if line.startswith("#"):
        return line

    line = line.rstrip("\n")

    # Line is already ignored
    if line.endswith("# noqa"):
        return line + "\n"

    orig_len = len(line)
    codes = set(codes)

    # don't add E501 unless the line is actually too long, as it can mask
    # other errors like trailing whitespace
    if orig_len <= max_line_length and "E501" in codes:
        codes.remove("E501")
        if not codes:
            return line + "\n"

    exemptions = ",".join(sorted(codes))

    # append exemption to line
    if "# noqa: " in line:
        line += f",{exemptions}"
    elif line:  # ignore noqa on empty lines
        line += f"  # noqa: {exemptions}"

    # if THIS made the line too long, add an exemption for that
    if len(line) > max_line_length and orig_len <= max_line_length:
        line += ",E501"

    return line + "\n"


def filter_file(source, dest, output=False):
    """Filter a single file through all the patterns in pattern_exemptions."""

    # Prior to Python 3.8, `noqa: F811` needed to be placed on the `@when` line
    # Starting with Python 3.8, it must be placed on the `def` line
    # https://gitlab.com/pycqa/flake8/issues/583
    ignore_f811_on_previous_line = False

    if not os.path.isfile(source):
        return

    with open(source, encoding="utf-8") as infile:
        parent = os.path.dirname(dest)
        mkdirp(parent)

        with open(dest, "w", encoding="utf-8") as outfile:
            for line in infile:
                line_errors = []

                # pattern exemptions
                for file_pattern, errors in pattern_exemptions.items():
                    if not file_pattern.search(source):
                        continue

                    for code, patterns in errors.items():
                        for pattern in patterns:
                            if pattern.search(line):
                                line_errors.append(code)
                                break

                if "F811" in line_errors:
                    ignore_f811_on_previous_line = True
                elif ignore_f811_on_previous_line:
                    line_errors.append("F811")
                    ignore_f811_on_previous_line = False

                if line_errors:
                    line = add_pattern_exemptions(line, line_errors)

                outfile.write(line)
                if output:
                    sys.stdout.write(line)


def _split_file_list(file_list, args):
    """Return a tuple of (primary_files, obj_files)"""
    if args.repo_path is not None:
        return [], file_list
    return [f for f in file_list if not is_object(f)], [f for f in file_list if is_object(f)]


def get_tool_args(args, tool_name):
    """Helper to get tool-specific arguments from args."""
    if hasattr(args, "parsed_tool_args") and tool_name in args.parsed_tool_args:
        return args.parsed_tool_args[tool_name]
    return []


@tool("flake8")
def run_flake8(flake8_cmd, file_list, args):
    temp = tempfile.mkdtemp()
    returncode = 1
    extra_flake8_args = get_tool_args(args, "flake8")
    try:
        print_tool_header("flake8", file_list)

        # run flake8 on the temporary tree, once for core, once for objects
        root = args.repo_path if args.repo_path is not None else ramble.paths.prefix
        primary_file_list, object_file_list = _split_file_list(file_list, args)

        returncode = 0
        output = ""

        for group_name, files, f_name in (
            ("primary", primary_file_list, ".flake8"),
            ("object", object_file_list, ".flake8_objects"),
        ):
            if files:
                # filter files into temporary directory with exemptions added.
                dest_dir = os.path.join(temp, group_name)
                mkdirp(dest_dir)
                for filename in files:
                    src_path = os.path.join(root, filename)
                    dest_path = os.path.join(dest_dir, filename)
                    filter_file(src_path, dest_path, args.output)

                # Copy flake8 file so the paths will be relative to the new location
                f_path = os.path.join(ramble.paths.prefix, f_name)
                shutil.copy(f_path, dest_dir)
                if group_name == "primary":
                    qa_dir = os.path.join(dest_dir, "share", "ramble", "qa")
                    mkdirp(qa_dir)

                with working_dir(dest_dir):
                    output += flake8_cmd(
                        "--format",
                        "pylint",
                        f"--config={f_name}",
                        *(extra_flake8_args + ["."]),
                        fail_on_error=False,
                        output=str,
                        error=str,
                    )
                    returncode |= flake8_cmd.returncode

        print_output(output, args)

    finally:
        if args.keep_temp:
            print("Temporary files are in: ", temp)
        else:
            shutil.rmtree(temp, ignore_errors=True)

    print_tool_result("flake8", returncode)
    return returncode


@tool("black")
def run_black(black_cmd, file_list, args):
    print_tool_header("black", file_list)

    version_out = black_cmd("--version", output=str, error=str)
    match = re.search(r"black,\s*(\d+\.\d+\.\d+)", version_out)
    if match:
        installed_version = match.group(1)
        if installed_version != _BLACK_GOLDEN_VERSION:
            print(
                f"WARNING: black version is {installed_version}, "
                f"but the version used for the PR style test is {_BLACK_GOLDEN_VERSION}. "
                f"Please update black to {_BLACK_GOLDEN_VERSION} to ensure consistency.",
                file=sys.stderr,
            )

    help_out = black_cmd("-h", output=str, error=str)
    supported_versions = set()
    help_match = re.search(r"--target-version\s+\[([^\]]+)\]", help_out)
    if help_match:
        supported_versions = set(help_match.group(1).split("|"))

    desired_versions = ["py36", "py37", "py38", "py39", "py310", "py311", "py312", "py313"]
    target_args = []
    for ver in desired_versions:
        if ver in supported_versions:
            target_args.extend(["--target-version", ver])

    common_args: Tuple[str, ...] = (
        "--config",
        os.path.join(ramble.paths.prefix, "pyproject.toml"),
    )
    if not args.fix:
        common_args += ("--check", "--diff")
    common_args += tuple(target_args)
    common_args += tuple(get_tool_args(args, "black"))
    primary_files, obj_files = _split_file_list(file_list, args)
    output = ""
    returncode = 0

    # Operate on primary and object files spearately with varying configs.
    if primary_files:
        output += black_cmd(
            *(common_args + tuple(primary_files)), fail_on_error=False, output=str, error=str
        )
        returncode |= black_cmd.returncode

    if obj_files:
        output += black_cmd(
            *(
                common_args
                + ("--config", os.path.join(ramble.paths.prefix, "pyproject_objects.toml"))
                + tuple(obj_files)
            ),
            fail_on_error=False,
            output=str,
            error=str,
        )
        returncode |= black_cmd.returncode

    print_output(output, args)
    print_tool_result("black", returncode)
    return returncode


@tool("isort")
def run_isort(isort_cmd, file_list, args):
    isort_args: Tuple[str, ...] = ("--sp", os.path.join(ramble.paths.prefix, "pyproject.toml"))
    if not args.fix:
        isort_args += ("--check", "--diff")
    isort_args += tuple(get_tool_args(args, "isort"))
    output = ""
    returncode = 0
    primary_files, obj_files = _split_file_list(file_list, args)
    if primary_files:
        output += isort_cmd(
            *(isort_args + tuple(primary_files)), fail_on_error=False, output=str, error=str
        )
        returncode |= isort_cmd.returncode
    if obj_files:
        output += isort_cmd(
            *(isort_args + ("-w", "79") + tuple(obj_files)),
            fail_on_error=False,
            output=str,
            error=str,
        )
        returncode |= isort_cmd.returncode
    print_output(output, args)
    print_tool_result("isort", returncode)
    return returncode


@tool("mypy")
def run_mypy(mypy_cmd, file_list, args):
    if args.repo_path is not None:
        print("Skipping mypy for external repository.")
        return 0
    print_tool_header("mypy", file_list)

    config_file = os.path.join(ramble.paths.prefix, "pyproject.toml")
    mypy_args = ["--config-file", config_file]
    mypy_args.extend(get_tool_args(args, "mypy"))

    if file_list:
        mypy_files = [
            f for f in file_list if f.startswith(("lib/ramble/ramble/", "share/ramble/scripts/"))
        ]
        if not mypy_files:
            print_tool_result("mypy", 0)
            return 0
        mypy_args.extend(mypy_files)

    output = mypy_cmd(*mypy_args, fail_on_error=False, output=str, error=str)
    returncode = mypy_cmd.returncode

    print_output(output, args)
    print_tool_result("mypy", returncode)
    return returncode


@tool("ruff")
def run_ruff(ruff_cmd, file_list, args):
    # Even though Ruff hasn't reached v1 yet, it has been effective in catching
    # issues like unused imports that flake8 misses.
    if not file_list:
        print("No changed Python files to check.")
        return 0
    if args.repo_path is not None:
        print("Skipping ruff for external repository.")
        return 0

    config_file = os.path.join(ramble.paths.prefix, "pyproject.toml")
    ruff_args = ["check", "--config", config_file, "--force-exclude"]

    if args.fix:
        ruff_args.append("--fix")

    ruff_args.extend(get_tool_args(args, "ruff"))

    print_tool_header("ruff", file_list)
    ruff_args.extend(file_list)

    output = ruff_cmd(*ruff_args, fail_on_error=False, output=str, error=str)
    returncode = ruff_cmd.returncode

    print_output(output, args)
    print_tool_result("ruff", returncode)
    return returncode


def validate_toolset(arg_value):
    """Validate --tool and --skip arguments (sets of optionally comma-separated tools)."""
    tools = set(",".join(arg_value).split(","))  # allow args like 'black,flake8'
    for tool in tools:
        if tool not in tool_names:
            print(f"Invalid tool: {tool}, choose from: {', '.join(tool_names)}")
    return tools


def style(parser, args):
    file_list = args.files
    root = args.repo_path if args.repo_path is not None else ramble.paths.prefix

    if args.repo_path is not None:
        try:
            repository.Repo(args.repo_path)
        except repository.BadRepoError as e:
            logger.die(f"'{args.repo_path}' is not a valid Ramble repository: {e}")

    if file_list:

        def root_relative(path):
            return os.path.relpath(os.path.abspath(os.path.realpath(path)), root)

        file_list = [root_relative(p) for p in file_list]

    # process --tool and --skip arguments
    selected = set(tool_names)
    if args.tool is not None:
        selected = validate_toolset(args.tool)
    if args.skip is not None:
        selected -= validate_toolset(args.skip)

    if not selected:
        print("Nothing to run.")
        return

    tools_to_run = [t for t in tool_names if t in selected]

    args.parsed_tool_args = {}
    if args.tool_args:
        for tool_arg_str in args.tool_args:
            if ":" not in tool_arg_str:
                logger.die(
                    f"Invalid --tool-args format: '{tool_arg_str}'. "
                    "Expected 'tool_name:arguments'"
                )
            tool_name, tool_args = tool_arg_str.split(":", 1)
            tool_name = tool_name.strip()
            if tool_name not in tool_names:
                logger.die(
                    f"Invalid tool name in --tool-args: '{tool_name}'. "
                    f"Choose from: {', '.join(tool_names)}"
                )
            parsed_args = shlex.split(tool_args)
            if tool_name in args.parsed_tool_args:
                args.parsed_tool_args[tool_name].extend(parsed_args)
            else:
                args.parsed_tool_args[tool_name] = parsed_args

    returncode = 0

    with working_dir(root):
        arg_flags = []
        # First, try with the original flags
        arg_flags.append([args.base, args.untracked, args.all])
        # Next, try with the a base of `origin/develop`
        arg_flags.append(["origin/develop", args.untracked, args.all])
        # Next, try with the a base of `origin/main`
        arg_flags.append(["origin/main", args.untracked, args.all])
        # Next, force listing all files
        arg_flags.append(["HEAD", args.untracked, True])
        is_external_repo = args.repo_path is not None
        while not file_list:
            try:
                base, untracked, list_all = arg_flags.pop(0)
                file_list = changed_files(
                    base, untracked, list_all, root=root, is_external_repo=is_external_repo
                )
                break
            except ProcessError as e:
                file_list = None
                if not arg_flags:
                    raise e

        for tool_name in tools_to_run:
            print(f"Running {tool_name} check")
            returncode |= tools[tool_name](which(tool_name, required=True), file_list, args)

    if returncode != 0:
        print("style checks found errors.")
        sys.exit(1)
    else:
        print("style checks were clean.")
