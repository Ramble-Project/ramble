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

    setup_env = os.path.join(paths.ramble_root, "share", "ramble", _SETUP_ENV_FILE[shell])
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
        ramble_exe = os.path.join(paths.ramble_root, "bin", "ramble")
        subprocess.run(
            [ramble_exe, "workspace", "rm", "-y", ws_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            check=False,
        )
