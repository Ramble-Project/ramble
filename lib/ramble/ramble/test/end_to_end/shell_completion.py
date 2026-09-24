# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Tests for Ramble's programmable bash tab completion.

These tests exercise ``share/ramble/ramble-completion.bash`` the way a user's
bash shell does: by sourcing ``setup-env.sh`` and calling the completion function.
"""

import os
import shutil
import subprocess

import pytest

from ramble import paths

pytestmark = pytest.mark.maybeslow

# Marker used to pair up a completion invocation with its output.
_CASE_MARKER = "RMBCASE"

# (completion invocation, substring expected in the completions)
#
# Note the invocations are inserted into a generated shell script verbatim,
# so they must be quoted as they would be when typed.
_COMPLETION_CASES = [
    # Top level subcommands
    ("ramble ''", "workspace"),
    ("ramble ''", "list"),
    ("ramble ''", "on"),
    # Prefix filtering
    ("ramble w", "workspace"),
    ("ramble work", "workspace"),
    # Nested subcommands
    ("ramble workspace ''", "analyze"),
    ("ramble workspace ''", "create"),
    ("ramble workspace ana", "analyze"),
    # Positional completions that shell out to ramble itself
    ("ramble list ''", "hostname"),
    ("ramble list host", "hostname"),
    # Flags are listed when the current word starts with a dash
    ("ramble -", "--help"),
    ("ramble -", "--version"),
    ("ramble workspace -", "--help"),
    ("ramble list -", "--help"),
    # Flags earlier in the line are ignored when picking the subcommand
    ("ramble -d workspace ''", "analyze"),
]

# Invocations that should produce no completions at all.
_EMPTY_COMPLETION_CASES = [
    "ramble isnotacommand",
    "ramble workspace isnotacommand",
]


@pytest.fixture(params=["bash", "zsh"])
def supported_shell(request):
    """Ensure shell is available on the system."""
    shell = request.param
    if not shutil.which(shell):
        pytest.skip(f"{shell} not found")
    return shell


def _completion_script(invocations):
    """Build a shell script that sources ramble and echoes each completion result."""
    setup_env = os.path.join(paths.share_path, "setup-env.sh")

    lines = [f'source "{setup_env}"']
    for index, invocation in enumerate(invocations):
        lines.append(f'echo "{_CASE_MARKER}{index}:$(_ramble_completions {invocation})"')

    return "\n".join(lines) + "\n"


def _run_completions(tmpdir, invocations, shell="bash"):
    """Run invocations under shell, returning {index: completion output}."""
    script_path = str(tmpdir.join(f"test_completion.{shell}"))
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(_completion_script(invocations))

    process = subprocess.run(
        [shell, script_path],
        capture_output=True,
        text=True,
        cwd=str(tmpdir),
        env=os.environ.copy(),
        check=False,
        timeout=600,
    )

    assert process.returncode == 0, (
        f"{shell} exited with {process.returncode}\n"
        f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}"
    )

    results = {}
    for line in process.stdout.splitlines():
        if line.startswith(_CASE_MARKER):
            index, _, output = line[len(_CASE_MARKER) :].partition(":")
            results[int(index)] = output.strip()

    assert len(results) == len(invocations), (
        f"expected {len(invocations)} results, got {len(results)}\n"
        f"stdout:\n{process.stdout}\nstderr:\n{process.stderr}"
    )

    return results


def test_completion_suggestions(tmpdir, supported_shell):
    """Shell completions contain the expected suggestions."""
    invocations = [case[0] for case in _COMPLETION_CASES]
    results = _run_completions(tmpdir, invocations, shell=supported_shell)

    for index, (invocation, expected) in enumerate(_COMPLETION_CASES):
        assert expected in results[index], (
            f"`{invocation}` under {supported_shell} should complete to something containing "
            f"'{expected}', but got '{results[index]}'"
        )


def test_completion_of_unknown_command_is_empty(tmpdir, supported_shell):
    """Unknown commands produce no completions instead of erroring."""
    results = _run_completions(tmpdir, _EMPTY_COMPLETION_CASES, shell=supported_shell)

    for index, invocation in enumerate(_EMPTY_COMPLETION_CASES):
        assert not results[index], (
            f"`{invocation}` under {supported_shell} should produce no completions, "
            f"but got '{results[index]}'"
        )


def test_every_subcommand_completes_help_flag(tmpdir, supported_shell):
    """Every subcommand has a completion function that offers --help.

    This catches completion functions that were renamed or never generated,
    which would otherwise only show up as silently missing completions.
    """
    subcommands = subprocess.run(
        [paths.ramble_script, "commands", "--format=subcommands"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\n")

    # Completing a word that starts with a dash lists flags, which avoids
    # invoking ramble to compute positional completions for every subcommand.
    invocations = [f"{s.strip()} -" for s in subcommands if s.strip()]
    results = _run_completions(tmpdir, invocations, shell=supported_shell)

    for index, invocation in enumerate(invocations):
        assert "--help" in results[index], (
            f"`{invocation}` under {supported_shell} should offer --help, "
            f"but got '{results[index]}'"
        )


def test_completion_cursor_in_middle_of_line(tmpdir, supported_shell):
    """Test completion when cursor is in the middle of a command line."""
    setup_env = os.path.join(paths.share_path, "setup-env.sh")
    script_path = str(tmpdir.join(f"test_midline.{supported_shell}"))
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(f"""source "{setup_env}"
COMP_LINE='ramble -d  list '
COMP_POINT=10
COMP_WORDS=(ramble -d list)
COMP_CWORD=2
COMP_KEY=9
COMP_TYPE=64
_bash_completion_ramble
echo "{_CASE_MARKER}:${{COMPREPLY[*]}}"
""")

    process = subprocess.run(
        [supported_shell, script_path],
        capture_output=True,
        text=True,
        cwd=str(tmpdir),
        env=os.environ.copy(),
        check=False,
    )
    assert process.returncode == 0
    output = ""
    for line in process.stdout.splitlines():
        if line.startswith(f"{_CASE_MARKER}:"):
            output = line.partition(":")[2]
            break
    assert "--help" in output
    assert "--all-help" in output


def test_workspace_activate_completion(tmpdir, supported_shell):
    """Test completion of workspace names for workspace activate."""
    setup_env = os.path.join(paths.share_path, "setup-env.sh")
    script_path = str(tmpdir.join(f"test_ws_completion.{supported_shell}"))
    ws_name = "test_ws_autocomp"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(f"""source "{setup_env}"
ramble workspace create {ws_name} > /dev/null 2>&1
echo "{_CASE_MARKER}:$(_ramble_completions ramble workspace activate '')"
ramble workspace remove -y {ws_name} > /dev/null 2>&1
""")

    process = subprocess.run(
        [supported_shell, script_path],
        capture_output=True,
        text=True,
        cwd=str(tmpdir),
        env=os.environ.copy(),
        check=False,
    )
    assert process.returncode == 0, f"{supported_shell} failed with {process.stderr}"
    output = ""
    for line in process.stdout.splitlines():
        if line.startswith(f"{_CASE_MARKER}:"):
            output = line.partition(":")[2]
            break
    words = output.split()
    assert ws_name in words
    assert "Workspaces" not in words
