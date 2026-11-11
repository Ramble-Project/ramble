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
def test_shell_wrapper_cd(shell, tmpdir):
    """Test `ramble cd` navigation, quoting, top-level flags, help, and error handling."""
    if not shutil.which(shell):
        pytest.skip(f"{shell} not found")

    setup_env = os.path.join(paths.share_path, _SETUP_ENV_FILE[shell])
    spaced_ws = str(tmpdir.mkdir("ws with spaces"))
    plain_ws = str(tmpdir.mkdir("ws_plain"))
    for ws_dir in (spaced_ws, plain_ws):
        subprocess.run(
            [paths.ramble_script, "workspace", "create", "-d", ws_dir],
            check=True,
            capture_output=True,
            text=True,
        )

    help_file = str(tmpdir.join("cd_help.txt"))
    sh_script = "\n".join(
        [
            f'source "{setup_env}"',
            "ramble cd --ramble-root || exit 1",
            'echo "PWD1:$(pwd)"',
            "ramble cd --module-dir || exit 2",
            'echo "PWD2:$(pwd)"',
            f'ramble cd -w "{spaced_ws}" || exit 3',
            'echo "PWD3:$(pwd)"',
            f'ramble -D "{spaced_ws}" cd configs || exit 4',
            'echo "PWD4:$(pwd)"',
            f'ramble cd -w"{spaced_ws}" || exit 5',
            'echo "PWD5:$(pwd)"',
            f'ramble cd --workspace="{plain_ws}" configs || exit 6',
            'echo "PWD6:$(pwd)"',
            f'ramble -D"{spaced_ws}" cd shared || exit 7',
            'echo "PWD7:$(pwd)"',
            f'ramble cd -hr > "{help_file}" || exit 8',
            'echo "PWD_AFTER_HELP:$(pwd)"',
            "if ramble cd definitely_nonexistent_target_xyz 2>/dev/null; then exit 9; fi",
            'echo "PWD_AFTER_FAIL:$(pwd)"',
        ]
    )
    script_templates = {
        "bash": sh_script
        + "\n"
        + "echo \"SUBSHELL_PWD:$(bash -c 'ramble cd --ramble-root && pwd')\" || exit 10",
        "zsh": sh_script,
        "tcsh": "\n".join(
            [
                'set prompt=""',
                f'setenv RAMBLE_ROOT "{paths.prefix}"',
                f'source "{setup_env}"',
                "ramble cd --ramble-root",
                "if ( $status != 0 ) exit 1",
                'echo "PWD1:`pwd`"',
                "ramble cd --module-dir",
                "if ( $status != 0 ) exit 2",
                'echo "PWD2:`pwd`"',
                f'ramble cd -w "{spaced_ws}"',
                "if ( $status != 0 ) exit 3",
                'echo "PWD3:`pwd`"',
                f'ramble -D "{spaced_ws}" cd configs',
                "if ( $status != 0 ) exit 4",
                'echo "PWD4:`pwd`"',
                f'ramble cd -w"{spaced_ws}"',
                "if ( $status != 0 ) exit 5",
                'echo "PWD5:`pwd`"',
                f'ramble cd --workspace="{plain_ws}" configs',
                "if ( $status != 0 ) exit 6",
                'echo "PWD6:`pwd`"',
                f'ramble -D"{spaced_ws}" cd shared',
                "if ( $status != 0 ) exit 7",
                'echo "PWD7:`pwd`"',
                f'( ramble cd -hr ) > "{help_file}"',
                "if ( $status != 0 ) exit 8",
                'echo "PWD_AFTER_HELP:`pwd`"',
                "ramble cd definitely_nonexistent_target_xyz >& /dev/null",
                "if ( $status == 0 ) exit 9",
                'echo "PWD_AFTER_FAIL:`pwd`"',
            ]
        ),
        "fish": "\n".join(
            [
                f'source "{setup_env}"',
                "ramble cd --ramble-root; or exit 1",
                'echo "PWD1:"(pwd)',
                "ramble cd --module-dir; or exit 2",
                'echo "PWD2:"(pwd)',
                f'ramble cd -w "{spaced_ws}"; or exit 3',
                'echo "PWD3:"(pwd)',
                f'ramble -D "{spaced_ws}" cd configs; or exit 4',
                'echo "PWD4:"(pwd)',
                f'ramble cd -w"{spaced_ws}"; or exit 5',
                'echo "PWD5:"(pwd)',
                f'ramble cd --workspace="{plain_ws}" configs; or exit 6',
                'echo "PWD6:"(pwd)',
                f'ramble -D"{spaced_ws}" cd shared; or exit 7',
                'echo "PWD7:"(pwd)',
                f'ramble cd -hr > "{help_file}"; or exit 8',
                'echo "PWD_AFTER_HELP:"(pwd)',
                "ramble cd definitely_nonexistent_target_xyz 2>/dev/null; and exit 9",
                'echo "PWD_AFTER_FAIL:"(pwd)',
            ]
        ),
    }

    test_script_path = str(tmpdir.join(f"test_cd.{shell}"))
    with open(test_script_path, "w", encoding="utf-8") as f:
        f.write(script_templates[shell] + "\n")

    cmd = [shell, "-f", test_script_path] if shell == "tcsh" else [shell, test_script_path]
    process = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(tmpdir),
        env=os.environ.copy(),
        check=False,
    )
    assert process.returncode == 0, f"stderr:\n{process.stderr}\nstdout:\n{process.stdout}"

    kv = dict(line.partition(":")[::2] for line in process.stdout.splitlines() if ":" in line)
    expected_shared = os.path.realpath(os.path.join(spaced_ws, "shared"))
    assert os.path.realpath(kv["PWD1"]) == os.path.realpath(paths.prefix)
    assert os.path.realpath(kv["PWD2"]) == os.path.realpath(paths.module_path)
    assert os.path.realpath(kv["PWD3"]) == os.path.realpath(spaced_ws)
    assert os.path.realpath(kv["PWD4"]) == os.path.realpath(os.path.join(spaced_ws, "configs"))
    assert os.path.realpath(kv["PWD5"]) == os.path.realpath(spaced_ws)
    assert os.path.realpath(kv["PWD6"]) == os.path.realpath(os.path.join(plain_ws, "configs"))
    assert os.path.realpath(kv["PWD7"]) == expected_shared
    assert os.path.realpath(kv["PWD_AFTER_HELP"]) == expected_shared
    assert os.path.realpath(kv["PWD_AFTER_FAIL"]) == expected_shared
    if shell == "bash":
        assert os.path.realpath(kv["SUBSHELL_PWD"]) == os.path.realpath(paths.prefix)
    with open(help_file, encoding="utf-8") as hf:
        assert "usage: ramble cd" in hf.read()
