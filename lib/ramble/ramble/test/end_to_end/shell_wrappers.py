# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import shutil
import subprocess

import pytest

from ramble import paths

pytestmark = pytest.mark.maybeslow

_SHELLS_TO_TEST = ["bash", "zsh", "fish", "tcsh"]

_SETUP_ENV_FILE = {
    "bash": "setup-env.sh",
    "zsh": "setup-env.sh",
    "fish": "setup-env.fish",
    "tcsh": "setup-env.csh",
}


@pytest.mark.parametrize("shell", _SHELLS_TO_TEST)
def test_shell_wrapper_source_clean(shell, tmpdir):
    """Test that sourcing setup-env emits no errors on stderr."""
    if not shutil.which(shell):
        pytest.skip(f"{shell} not found")

    setup_env = os.path.join(paths.share_path, _SETUP_ENV_FILE[shell])
    test_script_path = str(tmpdir.join(f"test_source_clean.{shell}"))

    prefix = 'set prompt=""\n' if shell == "tcsh" else ""
    with open(test_script_path, "w", encoding="utf-8") as f:
        f.write(f'{prefix}source "{setup_env}"\n')

    process = subprocess.run(
        [shell, test_script_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        cwd=str(tmpdir),
        env=os.environ.copy(),
        check=False,
    )

    assert process.returncode == 0
    assert process.stderr == ""


@pytest.mark.parametrize("shell", _SHELLS_TO_TEST)
def test_shell_wrapper_workspace_activate_missing(shell, tmpdir):
    """Test activation of missing workspace fails with proper exit code."""
    if not shutil.which(shell):
        pytest.skip(f"{shell} not found")

    setup_env = os.path.join(paths.share_path, _SETUP_ENV_FILE[shell])
    test_script_path = str(tmpdir.join("test_missing.sh"))

    with open(test_script_path, "w", encoding="utf-8") as f:
        f.write(f"""
source "{setup_env}"
ramble workspace activate non_existent_workspace
""")

    cmd = [shell, test_script_path]
    process = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        cwd=str(tmpdir),
        env=os.environ.copy(),
        check=False,
    )

    assert process.returncode == 1


@pytest.mark.parametrize("shell", _SHELLS_TO_TEST)
def test_shell_wrapper_workspace_lifecycle(shell, tmpdir):
    """Test workspace creation, activation and deactivation."""
    if not shutil.which(shell):
        pytest.skip(f"{shell} not found")

    setup_env = os.path.join(paths.share_path, _SETUP_ENV_FILE[shell])
    test_script_path = str(tmpdir.join(f"test_lifecycle.{shell}"))
    ws_name = f"test_ws_lifecycle_{shell}"

    script_templates = {
        "bash": f"""
source "{setup_env}"
ramble workspace create {ws_name} || exit 1
ramble workspace activate {ws_name} || exit 2
ramble workspace deactivate || exit 3
ramble workspace create -a {ws_name} && exit 4
exit 0
""",
        "zsh": f"""
source "{setup_env}"
ramble workspace create {ws_name} || exit 1
ramble workspace activate {ws_name} || exit 2
ramble workspace deactivate || exit 3
ramble workspace create -a {ws_name} && exit 4
exit 0
""",
        "tcsh": f"""
# The set prompt is needed as tcsh doesn't tolerate undefined variables.
set prompt=""
source "{setup_env}"
ramble workspace create {ws_name}
if ( $status != 0 ) exit 1
ramble workspace activate {ws_name}
if ( $status != 0 ) exit 2
ramble workspace deactivate
if ( $status != 0 ) exit 3
ramble workspace create -a {ws_name}
if ( $status == 0 ) exit 4
exit 0
""",
        "fish": f"""
source "{setup_env}"
ramble workspace create {ws_name}; or exit 1
ramble workspace activate {ws_name}; or exit 2
ramble workspace deactivate; or exit 3
ramble workspace create -a {ws_name}; and exit 4
exit 0
""",
    }
    script_content = script_templates[shell]

    with open(test_script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    try:
        cmd = [shell, test_script_path]
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=str(tmpdir),
            env=os.environ.copy(),
            check=False,
        )
        if process.returncode != 0:
            print(process.stdout)
            print(process.stderr)
        assert process.returncode == 0
    finally:
        ramble_exe = paths.ramble_script
        subprocess.run(
            [ramble_exe, "workspace", "rm", "-y", ws_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )


@pytest.mark.parametrize("shell", _SHELLS_TO_TEST)
def test_shell_wrapper_workspace_filter_group(shell, tmpdir):
    """Test workspace activation with filter group and deactivation."""
    if not shutil.which(shell):
        pytest.skip(f"{shell} not found")

    setup_env = os.path.join(paths.share_path, _SETUP_ENV_FILE[shell])
    test_script_path = str(tmpdir.join(f"test_fg.{shell}"))
    ws_name = f"test_ws_fg_{shell}"

    script_templates = {
        "bash": f"""
source "{setup_env}"
ramble workspace create {ws_name} || exit 1
ramble -w {ws_name} workspace manage filter-groups add -n foo --where "n_nodes == 1" || exit 2
ramble workspace activate {ws_name} --fg foo || exit 3
if [ "$RAMBLE_ACTIVE_FILTER_GROUP" != "foo" ]; then exit 4; fi
ramble workspace deactivate || exit 5
if [ ! -z ${{RAMBLE_ACTIVE_FILTER_GROUP+x}} ]; then exit 6; fi
exit 0
""",
        "zsh": f"""
source "{setup_env}"
ramble workspace create {ws_name} || exit 1
ramble -w {ws_name} workspace manage filter-groups add -n foo --where "n_nodes == 1" || exit 2
ramble workspace activate {ws_name} --fg foo || exit 3
if [ "$RAMBLE_ACTIVE_FILTER_GROUP" != "foo" ]; then exit 4; fi
ramble workspace deactivate || exit 5
if [ ! -z ${{RAMBLE_ACTIVE_FILTER_GROUP+x}} ]; then exit 6; fi
exit 0
""",
        "tcsh": f"""
set prompt=""
source "{setup_env}"
ramble workspace create {ws_name}
if ( $status != 0 ) exit 1
ramble -w {ws_name} workspace manage filter-groups add -n foo --where "n_nodes == 1"
if ( $status != 0 ) exit 2
ramble workspace activate {ws_name} --fg foo
if ( $status != 0 ) exit 3
if ( "$RAMBLE_ACTIVE_FILTER_GROUP" != "foo" ) exit 4
ramble workspace deactivate
if ( $status != 0 ) exit 5
if ( $?RAMBLE_ACTIVE_FILTER_GROUP ) exit 6
exit 0
""",
        "fish": f"""
source "{setup_env}"
ramble workspace create {ws_name}; or exit 1
ramble -w {ws_name} workspace manage filter-groups add -n foo --where "n_nodes == 1"; or exit 2
ramble workspace activate {ws_name} --fg foo; or exit 3
if test "$RAMBLE_ACTIVE_FILTER_GROUP" != "foo"; exit 4; end
ramble workspace deactivate; or exit 5
if set -q RAMBLE_ACTIVE_FILTER_GROUP; exit 6; end
exit 0
""",
    }
    script_content = script_templates[shell]

    with open(test_script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    try:
        cmd = [shell, test_script_path]
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=str(tmpdir),
            env=os.environ.copy(),
            check=False,
        )
        if process.returncode != 0:
            print(process.stdout)
            print(process.stderr)
        assert process.returncode == 0
    finally:
        ramble_exe = paths.ramble_script
        subprocess.run(
            [ramble_exe, "workspace", "rm", "-y", ws_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )


@pytest.mark.parametrize("shell", _SHELLS_TO_TEST)
def test_shell_wrapper_workspace_activate_create(shell, tmpdir):
    """Test `ramble workspace activate --create` across shell wrappers."""
    if not shutil.which(shell):
        pytest.skip(f"{shell} not found")

    setup_env = os.path.join(paths.share_path, _SETUP_ENV_FILE[shell])
    test_script_path = str(tmpdir.join(f"test_activate_create.{shell}"))
    ws_name = f"test_ws_act_create_{shell}"
    dir_ws = str(tmpdir.join(f"dir_ws_{shell}"))

    sh_script = f"""
source "{setup_env}"
ramble workspace activate --create {ws_name} || exit 1
case "$RAMBLE_WORKSPACE" in *{ws_name}) ;; *) exit 2 ;; esac
ramble workspace deactivate || exit 3
ramble workspace activate --create {ws_name} || exit 4
case "$RAMBLE_WORKSPACE" in *{ws_name}) ;; *) exit 5 ;; esac
ramble workspace activate --create -d "{dir_ws}" || exit 6
if [ "$RAMBLE_WORKSPACE" != "{dir_ws}" ]; then exit 7; fi
ramble workspace activate --create -d "{dir_ws}" || exit 8
if [ "$RAMBLE_WORKSPACE" != "{dir_ws}" ]; then exit 9; fi
ramble workspace deactivate || exit 10
exit 0
"""
    script_templates = {
        "bash": sh_script,
        "zsh": sh_script,
        "tcsh": f"""
set prompt=""
source "{setup_env}"
ramble workspace activate --create {ws_name}
if ( $status != 0 ) exit 1
if ( "$RAMBLE_WORKSPACE" !~ *{ws_name} ) exit 2
ramble workspace deactivate
if ( $status != 0 ) exit 3
ramble workspace activate --create {ws_name}
if ( $status != 0 ) exit 4
if ( "$RAMBLE_WORKSPACE" !~ *{ws_name} ) exit 5
ramble workspace activate --create -d "{dir_ws}"
if ( $status != 0 ) exit 6
if ( "$RAMBLE_WORKSPACE" != "{dir_ws}" ) exit 7
ramble workspace activate --create -d "{dir_ws}"
if ( $status != 0 ) exit 8
if ( "$RAMBLE_WORKSPACE" != "{dir_ws}" ) exit 9
ramble workspace deactivate
if ( $status != 0 ) exit 10
exit 0
""",
        "fish": f"""
source "{setup_env}"
ramble workspace activate --create {ws_name}; or exit 1
string match -q "*{ws_name}" "$RAMBLE_WORKSPACE"; or exit 2
ramble workspace deactivate; or exit 3
ramble workspace activate --create {ws_name}; or exit 4
string match -q "*{ws_name}" "$RAMBLE_WORKSPACE"; or exit 5
ramble workspace activate --create -d "{dir_ws}"; or exit 6
if test "$RAMBLE_WORKSPACE" != "{dir_ws}"; exit 7; end
ramble workspace activate --create -d "{dir_ws}"; or exit 8
if test "$RAMBLE_WORKSPACE" != "{dir_ws}"; exit 9; end
ramble workspace deactivate; or exit 10
exit 0
""",
    }
    script_content = script_templates[shell]

    with open(test_script_path, "w", encoding="utf-8") as f:
        f.write(script_content)

    try:
        cmd = [shell, test_script_path]
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            cwd=str(tmpdir),
            env=os.environ.copy(),
            check=False,
        )
        if process.returncode != 0:
            print(process.stdout)
            print(process.stderr)
        assert process.returncode == 0
        assert "Created and activated workspace" not in process.stdout
        assert process.stderr.count(f"Created and activated workspace in {ws_name}") == 1
        assert process.stderr.count(f"Created and activated workspace in {dir_ws}") == 1
    finally:
        ramble_exe = paths.ramble_script
        subprocess.run(
            [ramble_exe, "workspace", "rm", "-y", ws_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
