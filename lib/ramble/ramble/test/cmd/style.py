# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import pytest

from ramble import main
from ramble.cmd import style

from spack.util.executable import which

style_cmd = main.RambleCommand("style")


def _require_tools(*tool_names):
    missing = [t for t in tool_names if which(t) is None]
    if missing:  # pragma: no cover
        pytest.skip(f"Required style tool(s) not installed: {', '.join(missing)}")


def _get_changed_files_with_fallback():
    files = []
    for base in [None, "origin/develop", "origin/main"]:
        try:
            files = style.changed_files(base=base, all_files=False)
            if files:
                break
        except Exception:
            pass
    return files


@pytest.mark.parametrize("tool", style.tool_names)
def test_style(tool, request):
    _require_tools(tool)
    fail_on_style = request.config.getoption("--fail-on-style")
    if fail_on_style:
        files = _get_changed_files_with_fallback()
        if files:
            out = style_cmd("--tool", tool, *files)
            assert f"{tool} checks were clean" in out
    else:
        out = style_cmd("--tool", tool, __file__)
        assert f"{tool} checks were clean" in out


@pytest.mark.parametrize(
    "content,expected_err",
    [
        ("import b\nimport a", "Imports are incorrectly sorted"),
    ],
)
def test_style_with_error(tmpdir, content, expected_err):
    _require_tools(*style.tool_names)
    with tmpdir.as_cwd():
        new_file = "new_file.py"
        with open(new_file, "w+", encoding="utf-8") as f:
            f.write(content)

        out = style_cmd(new_file, fail_on_error=False)
        assert style_cmd.returncode != 0
        assert expected_err in out


def test_changed_files_all():
    files = style.changed_files(all_files=True)
    # Currently there are more than 900 files checked for styling.
    # Use a smaller number here.
    assert len(files) > 500


def test_skip_tools():
    output = style_cmd("--skip", ",".join(style.tool_names))
    assert "Nothing to run" in output


def test_black_version_mismatch(capsys):
    class MockExecutable:
        def __init__(self, output):
            self.output = output
            self.returncode = 0

        def __call__(self, *args, **kwargs):
            return self.output

    mock_black = MockExecutable("black, 25.0.0")

    class MockArgs:
        fix = False
        root_relative = False
        repo_path = None

    args = MockArgs()

    style.run_black(mock_black, [], args)

    captured = capsys.readouterr()
    assert "WARNING: black version is 25.0.0" in captured.err
    assert (
        f"but the version used for the PR style test is {style._BLACK_GOLDEN_VERSION}"
        in captured.err
    )


def test_style_invalid_repo(tmpdir):
    with tmpdir.as_cwd():
        out = style_cmd("--repo-path", str(tmpdir), fail_on_error=False)
        assert style_cmd.returncode != 0
        assert "is not a valid Ramble repository" in out


def test_style_valid_repo():
    _require_tools(*style.tool_names)
    from ramble import paths

    builtin_mock_repo = paths.mock_builtin_path
    out = style_cmd("--repo-path", builtin_mock_repo)
    assert "style checks were clean" in out


def test_changed_files_git_failure(tmpdir):
    lib_dir = tmpdir.join("lib", "ramble", "ramble")
    lib_dir.ensure(dir=True)
    file1 = lib_dir.join("file1.py")
    file1.write("import os")
    file2 = tmpdir.join("conftest.py")
    file2.write("import sys")
    file3 = tmpdir.join("file3.py")
    file3.write("# file3")

    files = style.changed_files(root=str(tmpdir))

    assert "lib/ramble/ramble/file1.py" in files
    assert "conftest.py" in files
    assert "file3.py" not in files


@pytest.mark.parametrize(
    "tool,expected_err",
    [
        ("ruff", "unexpected argument '--bogus-option'"),
        ("black", "No such option: --bogus-option"),
        ("flake8", "unrecognized arguments: --bogus-option"),
        ("isort", "unrecognized arguments: --bogus-option"),
        ("mypy", "unrecognized arguments: --bogus-option"),
    ],
)
def test_style_tool_args(tool, expected_err):
    _require_tools(tool)
    # Test that invalid tool args cause failure (from the underlying tool itself)
    out = style_cmd(
        "--tool", tool, "--tool-args", f"{tool}:--bogus-option", __file__, fail_on_error=False
    )
    assert style_cmd.returncode != 0
    assert expected_err in out


def test_style_tool_args_invalid_tool():
    out = style_cmd(
        "--tool", "ruff", "--tool-args", "invalid_tool:--some-arg", __file__, fail_on_error=False
    )
    assert style_cmd.returncode != 0
    assert "Invalid tool name in --tool-args" in out


def test_style_tool_args_invalid_format():
    out = style_cmd(
        "--tool", "ruff", "--tool-args", "ruff--some-arg", __file__, fail_on_error=False
    )
    assert style_cmd.returncode != 0
    assert "Invalid --tool-args format" in out


def test_style_tool_args_multiple():
    _require_tools("ruff")
    out = style_cmd(
        "--fix",
        "--tool",
        "ruff",
        "--tool-args",
        "ruff:'--unsafe-fixes'",
        "--tool-args",
        "ruff:'--bad-arg'",
        __file__,
        fail_on_error=False,
    )
    assert style_cmd.returncode != 0
    assert "unexpected argument '--bad-arg'" in out


def test_style_external_repo(tmpdir):
    _require_tools("flake8")
    repo_config = tmpdir.join("repo.yaml")
    repo_config.write("repo:\n  namespace: test_external\n")

    app_dir = tmpdir.join("applications", "test_app")
    app_dir.ensure(dir=True)
    app_file = app_dir.join("application.py")
    app_file.write("# mock application file\n")

    out = style_cmd("--repo-path", str(tmpdir), "-a", "-t", "flake8")
    assert "style checks were clean" in out
    assert "applications/test_app/application.py" in out


def test_black_target_version_parsing(capsys):
    class MockExecutable:
        def __init__(self):
            self.args_received = []
            self.returncode = 0

        def __call__(self, *args, **kwargs):
            if "-h" in args:
                return "  -t, --target-version [py36|py37|py38|py39|py310|py311|py312]"
            self.args_received.extend(args)
            return ""

    mock_black = MockExecutable()

    class MockArgs:
        fix = False
        root_relative = False
        repo_path = None

    args = MockArgs()

    style.run_black(mock_black, ["lib/ramble/ramble/cmd/style.py"], args)

    expected_versions = ["py36", "py37", "py38", "py39", "py310", "py311", "py312"]
    for ver in expected_versions:
        assert "--target-version" in mock_black.args_received
        assert ver in mock_black.args_received
    assert "py313" not in mock_black.args_received


def test_changed_files_fallback(monkeypatch):
    calls = []

    def mock_changed_files(base, all_files):
        calls.append(base)
        if base == "origin/main":
            return ["file1.py"]
        elif base == "origin/develop":
            return []
        raise Exception("Mock error simulating missing branch")

    monkeypatch.setattr(style, "changed_files", mock_changed_files)

    files = _get_changed_files_with_fallback()
    assert files == ["file1.py"]
    # Check that it tried None, origin/develop, and origin/main in order
    assert calls == [None, "origin/develop", "origin/main"]
