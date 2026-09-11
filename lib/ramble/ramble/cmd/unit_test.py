# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import argparse
import collections
import io
import os
import shutil
import sys

from llnl.util.filesystem import working_dir
from llnl.util.tty.colify import colify

import ramble.paths
import ramble.util.colors as color
import ramble.workspace
from ramble.util.logger import logger

description = "run ramble's unit tests (wrapper around pytest)"
section = "developer"
level = "long"


def setup_parser(subparser):
    subparser.add_argument(
        "-H",
        "--pytest-help",
        action="store_true",
        default=False,
        help="show full pytest help, with advanced options",
    )

    limited = subparser.add_mutually_exclusive_group()
    limited.add_argument(
        "--lib",
        action="store_true",
        default=False,
        help="run only tests under the lib directory",
    )
    limited.add_argument(
        "--obj",
        action="store_true",
        default=False,
        help="run only tests under the builtin object repo directory",
    )
    limited.add_argument(
        "-r",
        "--repo-path",
        default=None,
        dest="repo_path",
        help="run tests under the given object repo root (used for testing external object repo)",
    )
    subparser.add_argument(
        "--perf",
        action="store_true",
        default=False,
        help="run only performance tests",
    )
    subparser.add_argument(
        "--fail-on-style",
        action="store_true",
        default=False,
        help="fail unit tests if style is bad in the repository",
    )
    speed = subparser.add_mutually_exclusive_group()
    speed.add_argument(
        "--fast",
        action="store_true",
        default=False,
        help="run only fast tests (skip slow tests)",
    )
    speed.add_argument(
        "--slow",
        action="store_true",
        default=False,
        help="run only slow tests (skip fast tests)",
    )

    # extra ramble arguments to list tests
    list_group = subparser.add_argument_group("listing tests")
    list_mutex = list_group.add_mutually_exclusive_group()
    list_mutex.add_argument(
        "-l",
        "--list",
        action="store_const",
        default=None,
        dest="list",
        const="list",
        help="list test filenames",
    )
    list_mutex.add_argument(
        "-L",
        "--list-long",
        action="store_const",
        default=None,
        dest="list",
        const="long",
        help="list all test functions",
    )
    list_mutex.add_argument(
        "-N",
        "--list-names",
        action="store_const",
        default=None,
        dest="list",
        const="names",
        help="list full names of all tests",
    )

    # spell out some common pytest arguments, so they'll show up in help
    pytest_group = subparser.add_argument_group(
        "common pytest arguments (ramble unit-test --pytest-help for more)"
    )
    pytest_group.add_argument(
        "-s",
        action="append_const",
        dest="parsed_args",
        const="-s",
        help="print output while tests run (disable capture)",
    )
    pytest_group.add_argument(
        "-k",
        action="store",
        metavar="EXPRESSION",
        dest="expression",
        help="filter tests by keyword (can also use w/list options)",
    )
    pytest_group.add_argument(
        "--showlocals",
        action="append_const",
        dest="parsed_args",
        const="--showlocals",
        help="show local variable values in tracebacks",
    )

    # remainder is just passed to pytest
    subparser.add_argument("pytest_args", nargs=argparse.REMAINDER, help="arguments for pytest")


def do_list(args, extra_args):
    """Print a lists of tests than what pytest offers."""

    def colorize(c, prefix):
        if isinstance(prefix, tuple):
            return "::".join(color.colorize(f"@{c}{{{p}}}") for p in prefix if p != "()")
        return color.colorize(f"@{c}{{{prefix}}}")

    # Run test collection with quiet mode, to extract a list of <path>::<test_name>.
    old_output = sys.stdout
    try:
        sys.stdout = output = io.StringIO()
        try:
            import pytest

            pytest.main(["--collect-only", "-q"] + extra_args)
        except ImportError:
            logger.die(
                "Pytest python module not found. Ensure requirements-dev.txt are installed."
            )
    finally:
        sys.stdout = old_output

    lines = output.getvalue().split("\n")
    tests = collections.defaultdict(set)
    # collect tests into sections
    for line in lines:
        if "::" not in line:
            continue
        [path, test_name] = line.split("::", 1)
        # dedupe parametrized tests
        if "[" in test_name:
            test_name = test_name[: test_name.index("[")]
        tests[path].add(test_name)

    if args.list == "list":
        files = tests.keys()
        color_files = [colorize("B", file) for file in sorted(files)]
        colify(color_files)
    elif args.list == "long":
        for prefix, functions in sorted(tests.items()):
            path = colorize("*B", prefix) + "::"
            color_functions = [colorize("c", f) for f in sorted(functions)]
            color.cprint(path)
            colify(color_functions, indent=4)
            print()
    else:  # args.list == "names"
        all_functions = [
            colorize("*B", prefix) + "::" + colorize("c", f)
            for prefix, functions in sorted(tests.items())
            for f in sorted(functions)
        ]
        colify(all_functions)


def add_back_pytest_args(args, unknown_args):
    """Add parsed pytest args, unknown args, and remainder together.

    We add some basic pytest arguments to the Ramble parser to ensure that
    they show up in the short help, so we have to reassemble things here.
    """
    result = args.parsed_args or []
    if args.lib:
        result += ["--ignore-glob", "var/ramble/repos/*"]
    elif args.obj:
        result += ["--ignore-glob", "lib/ramble/ramble/test/*"]
    elif args.repo_path:
        result += ["--repo-path", args.repo_path]
    if args.perf:
        result += ["--perf"]
    if args.fast:
        result += ["--fast"]
    if args.slow:
        result += ["--slow"]
    if args.fail_on_style:
        result += ["--fail-on-style"]
    result += unknown_args or []
    result += args.pytest_args or []
    if args.expression:
        result += ["-k", args.expression]
    return result


def unit_test(parser, args, unknown_args):
    if args.pytest_help:
        # make the pytest.main help output more accurate
        sys.argv[0] = "ramble test"
        try:
            import pytest

            return pytest.main(["-h"])
        except ImportError:
            logger.die(
                "Pytest python module not found. Ensure requirements-dev.txt are installed."
            )

    # add back any parsed pytest args we need to pass to pytest
    pytest_args = add_back_pytest_args(args, unknown_args)

    pytest_root = args.repo_path or ramble.paths.ramble_root

    # conftest.py and pytest.ini live in the root of the ramble repository.
    # need to ensure the same when repo_path is specified.
    copied_conftest_path = None
    copied_ini_path = None
    copied_test_path = None
    try:
        with working_dir(pytest_root):

            def _ensure_path_in_cwd(filename, src_root=ramble.paths.ramble_root):
                if not os.path.exists(filename):
                    shutil.copyfile(os.path.join(src_root, filename), filename)
                    return os.path.join(os.getcwd(), filename)
                return None

            if args.repo_path is not None:
                copied_conftest_path = _ensure_path_in_cwd("conftest.py")
                copied_ini_path = _ensure_path_in_cwd("pytest.ini")
                # This specific test should be run against custom repos, so copy it over.
                copied_test_path = _ensure_path_in_cwd(
                    "setup_analyze.py", src_root=os.path.join(ramble.paths.test_path, "end_to_end")
                )

            if args.list:
                do_list(args, pytest_args)
                return

            with ramble.workspace.no_active_workspace():
                try:
                    import pytest

                    return pytest.main(pytest_args)
                except ImportError:
                    logger.die(
                        "Pytest python module not found. "
                        "Ensure requirements-dev.txt are installed."
                    )
    finally:
        if copied_conftest_path is not None:
            os.remove(copied_conftest_path)
        if copied_ini_path is not None:
            os.remove(copied_ini_path)
        if copied_test_path is not None:
            os.remove(copied_test_path)
