# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.repository import ObjectTypes, get


def test_utility_base_validate_exact_version_via_vcs(monkeypatch):
    """Test that an exact version request passes if VCS check passes, ignoring version output."""
    SpackClass = type(get("spack", ObjectTypes.utilities))
    spack_inst = SpackClass("/path/to/spack")

    def mock_shutil_which(cmd, *args, **kwargs):
        if cmd == "spack":
            return "/usr/local/bin/spack"
        elif cmd == "git":
            return "/usr/bin/git"
        return None

    monkeypatch.setattr("shutil.which", mock_shutil_which)

    def mock_check_vcs(self, exec_path, exact_version):  # noqa: E501
        # Mock VCS check returning True
        return True

    monkeypatch.setattr(SpackClass, "_check_exact_match_via_vcs", mock_check_vcs)

    def mock_subprocess_run(cmd, *args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = "Spack 0.19.0\n"
            stderr = ""

        return MockResult()

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    # exact_version='commit-hash' which is not in output, but vcs says True
    assert spack_inst.validate_versions(exact_version="commit-hash") is True
    assert spack_inst.availability_error is None


def test_utility_base_validate_exact_version_via_fallback_output(monkeypatch):
    """Test that an exact version request passes if VCS fails but
    output contains the exact version."""
    SpackClass = type(get("spack", ObjectTypes.utilities))
    spack_inst = SpackClass("/path/to/spack")

    def mock_shutil_which(cmd, *args, **kwargs):
        if cmd == "spack":
            return "/usr/local/bin/spack"
        return None

    monkeypatch.setattr("shutil.which", mock_shutil_which)

    def mock_check_vcs(self, exec_path, exact_version):  # noqa: E501
        # Mock VCS check returning False
        return False

    monkeypatch.setattr(SpackClass, "_check_exact_match_via_vcs", mock_check_vcs)

    def mock_subprocess_run(cmd, *args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = "Spack 0.19.0 (commit-hash)\n"
            stderr = ""

        return MockResult()

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    # exact_version='commit-hash' which is in output
    assert spack_inst.validate_versions(exact_version="commit-hash") is True
    assert spack_inst.availability_error is None


def test_utility_base_validate_exact_version_failure(monkeypatch):
    """Test that an exact version request fails if both VCS
    and output do not contain the exact version."""
    SpackClass = type(get("spack", ObjectTypes.utilities))
    spack_inst = SpackClass("/path/to/spack")

    def mock_shutil_which(cmd, *args, **kwargs):
        if cmd == "spack":
            return "/usr/local/bin/spack"
        return None

    monkeypatch.setattr("shutil.which", mock_shutil_which)

    def mock_check_vcs(self, exec_path, exact_version):  # noqa: E501
        # Mock VCS check returning False
        return False

    monkeypatch.setattr(SpackClass, "_check_exact_match_via_vcs", mock_check_vcs)

    def mock_subprocess_run(cmd, *args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = "Spack 0.19.0\n"
            stderr = ""

        return MockResult()

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    # exact_version='commit-hash' not in output, vcs says False
    assert spack_inst.validate_versions(exact_version="commit-hash") is False
    assert spack_inst.availability_error is not None
    assert "does not match required exact version" in spack_inst.availability_error


def test_utility_base_vcs_check_logic(monkeypatch):
    """Test the VCS check logic specifically."""
    SpackClass = type(get("spack", ObjectTypes.utilities))
    spack_inst = SpackClass("/path/to/spack")

    def mock_shutil_which(cmd, *args, **kwargs):
        if cmd == "git":
            return "/usr/bin/git"
        return None

    monkeypatch.setattr("shutil.which", mock_shutil_which)

    def mock_subprocess_run(cmd, *args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = ""
            stderr = ""

        res = MockResult()
        if "--is-inside-work-tree" in cmd:
            res.stdout = "true"
        elif "HEAD" in cmd:
            res.stdout = "123456"
        elif "789abc^{commit}" in cmd:
            # Different commit
            res.stdout = "789abc"
        elif "123456^{commit}" in cmd:
            # Same commit
            res.stdout = "123456"
        return res

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    # Test exact match via vcs (fails)
    assert spack_inst._check_exact_match_via_vcs("/path/to/spack/bin/spack", "789abc") is False

    # Test exact match via vcs (succeeds)
    assert spack_inst._check_exact_match_via_vcs("/path/to/spack/bin/spack", "123456") is True


def test_utility_base_vcs_early_returns():
    """Test early return paths in _check_exact_match_via_vcs."""
    SpackClass = type(get("spack", ObjectTypes.utilities))
    spack_inst = SpackClass("/path/to/spack")

    assert spack_inst._check_exact_match_via_vcs("", "123") is False
    assert spack_inst._check_exact_match_via_vcs("/some/path", "") is False
    assert spack_inst._check_exact_match_via_vcs(None, None) is False
    # Path without a directory component
    assert spack_inst._check_exact_match_via_vcs("spack", "123") is False


def test_utility_base_vcs_exception(monkeypatch):
    """Test exception handling in _check_exact_match_via_vcs."""
    SpackClass = type(get("spack", ObjectTypes.utilities))
    spack_inst = SpackClass("/path/to/spack")

    def mock_shutil_which(cmd, *args, **kwargs):
        if cmd == "git":
            return "/usr/bin/git"
        return None

    monkeypatch.setattr("shutil.which", mock_shutil_which)

    def mock_subprocess_run(cmd, *args, **kwargs):
        raise Exception("Some subprocess error")

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    assert spack_inst._check_exact_match_via_vcs("/path/to/spack", "123") is False


def test_utility_base_validate_versions_exceptions(monkeypatch):
    """Test exception handling during version string validation."""
    SpackClass = type(get("spack", ObjectTypes.utilities))
    spack_inst = SpackClass("/path/to/spack")

    def mock_shutil_which(cmd, *args, **kwargs):
        if cmd == "spack":
            return "/usr/local/bin/spack"
        return None

    monkeypatch.setattr("shutil.which", mock_shutil_which)

    def mock_subprocess_run(*args, **kwargs):
        raise Exception("Command failed")

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    # Test exact match via vcs True, exception swallowed
    def mock_check_vcs_true(*args, **kwargs):
        return True

    monkeypatch.setattr(SpackClass, "_check_exact_match_via_vcs", mock_check_vcs_true)
    assert spack_inst.validate_versions(exact_version="123") is True

    # Test exact match via vcs False, exception fails validation
    def mock_check_vcs_false(*args, **kwargs):
        return False

    monkeypatch.setattr(SpackClass, "_check_exact_match_via_vcs", mock_check_vcs_false)
    assert spack_inst.validate_versions(exact_version="123") is False
    assert spack_inst.availability_error is not None


def test_utility_base_validate_versions_with_path(monkeypatch):
    """Test that validate_versions correctly uses the path parameter if provided."""
    SpackClass = type(get("spack", ObjectTypes.utilities))
    spack_inst = SpackClass("/path/to/spack")

    def mock_shutil_which(cmd, path=None, **kwargs):
        if cmd == "spack" and path == "/custom/path/to/spack/bin":
            return "/custom/path/to/spack/bin/spack"
        return None

    monkeypatch.setattr("shutil.which", mock_shutil_which)

    def mock_subprocess_run(cmd, *args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = "Spack 0.19.0\n"
            stderr = ""

        return MockResult()

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    # Validation should fail without the path parameter
    assert spack_inst.validate_versions(min_version="0.18.0") is False
    assert "not found in PATH" in spack_inst.availability_error

    # Validation should succeed with the path parameter
    assert (
        spack_inst.validate_versions(min_version="0.18.0", path="/custom/path/to/spack/bin")
        is True
    )
    assert spack_inst.availability_error is None


class _MockUtility(get("spack", ObjectTypes.utilities).__class__):  # type: ignore
    name = "mock_util"
    class_variants = {
        "dummy_variant": {"name": "dummy_variant", "default": "True", "description": "dummy"}
    }
    env_prepends = {"default": [{"var": "PATH", "value": "/mock/path"}]}
    env_appends = {"default": [{"var": "LD_LIBRARY_PATH", "value": "/mock/lib"}]}
    provided_executables = {
        "mock_exe_no_ver": [{"executable": "mock_exe_no_ver"}],
        "mock_exe_with_ver": [
            {
                "executable": "mock_exe_with_ver",
                "version_cmd": "mock_exe_with_ver --version",
                "version_regex": r"Version (.*)",
            }
        ],
    }


def test_utility_base_variants():
    """Test line 39: class_variants loop inside __init__"""
    inst = _MockUtility("/mock/path")
    assert inst.object_variants is not None


def test_utility_base_validate_versions_no_version_cmd(monkeypatch):
    """Test lines 262-263: exact_version requested but no version_cmd."""
    inst = _MockUtility("/mock/path")

    def mock_shutil_which(cmd, *args, **kwargs):
        return "/mock/path/mock_exe_no_ver"

    monkeypatch.setattr("shutil.which", mock_shutil_which)

    def mock_check_vcs(self, exec_path, exact_version):  # noqa: E501
        return False

    monkeypatch.setattr(_MockUtility, "_check_exact_match_via_vcs", mock_check_vcs)

    original = inst.provided_executables
    inst.provided_executables = {"mock_exe_no_ver": original["mock_exe_no_ver"]}

    res = inst.validate_versions(exact_version="1.0.0")
    assert res is False
    assert "but no version command is defined" in inst.availability_error

    inst.provided_executables = original


def test_utility_base_validate_versions_regex_fails_but_vcs_true(monkeypatch):
    """Test lines 212-217: regex fails but exact_match_via_vcs is True."""
    inst = _MockUtility("/mock/path")

    def mock_shutil_which(cmd, *args, **kwargs):
        return "/mock/path/mock_exe_with_ver"

    monkeypatch.setattr("shutil.which", mock_shutil_which)

    def mock_check_vcs(self, exec_path, exact_version):  # noqa: E501
        return True

    monkeypatch.setattr(_MockUtility, "_check_exact_match_via_vcs", mock_check_vcs)

    def mock_subprocess_run(cmd, *args, **kwargs):
        class MockResult:
            returncode = 0
            stdout = "Some random output without version\n"
            stderr = ""

        return MockResult()

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)

    original = inst.provided_executables
    inst.provided_executables = {"mock_exe_with_ver": original["mock_exe_with_ver"]}

    res = inst.validate_versions(exact_version="1.0.0")
    assert res is True
    inst.provided_executables = original


def test_utility_base_get_env_workspace_modifications():
    """Test env_prepends and env_appends in setup_runner_environment."""
    inst = _MockUtility("/mock/path")
    import ramble.expander

    class MockAppInst:
        def __init__(self):
            self.variables = {"foo": "bar", "utility::mock_util::path": "/mock/path"}
            self.expander = ramble.expander.Expander(self.variables, None)

        def satisfy_when(self, *args, **kwargs):
            return True

    class MockWorkspace:
        dry_run = True

    app_inst = MockAppInst()
    env_mod = inst.setup_runner_environment(MockWorkspace(), app_inst)
    assert env_mod is not None


def test_utility_base_get_experiment_activation_command():
    """Test lines 363-365, 383-387, 390-394: env_prepends and env_appends, and expander init."""
    inst = _MockUtility("/mock/path")

    class MockAppInst:
        def __init__(self):
            self.variables = {"utility::mock_util::path": "/custom/path"}

        def satisfy_when(self, *args, **kwargs):
            return True

    app_inst = MockAppInst()
    cmd = inst.get_experiment_activation_command(None, app_inst)

    assert "export PATH=/mock/path:$PATH" in cmd
    assert "export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/mock/lib" in cmd


def test_utility_base_validate_versions_subprocess_execution(monkeypatch, tmpdir):
    """Test subprocess execution for validate_versions."""
    import os
    import stat

    script_path = str(tmpdir.join("fake_spack.sh"))
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write('if [ "$1" = "--version" ]; then\n')
        f.write('    echo "0.19.0"\n')
        f.write("else\n")
        f.write('    echo "Error"\n')
        f.write("    exit 1\n")
        f.write("fi\n")

    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)

    SpackClass = type(get("spack", ObjectTypes.utilities))
    spack_inst = SpackClass("/path/to/spack")

    # Overwrite the command to use our fake script
    spack_inst.provided_executables[frozenset()][0]["version_cmd"] = f"{script_path} --version"

    def mock_shutil_which(cmd, *args, **kwargs):
        if cmd == "spack":
            return script_path
        return None

    monkeypatch.setattr("shutil.which", mock_shutil_which)

    def mock_check_vcs(*args, **kwargs):
        return False

    monkeypatch.setattr(SpackClass, "_check_exact_match_via_vcs", mock_check_vcs)

    # Test successful max_version match
    assert spack_inst.validate_versions(max_version="0.20.0") is True

    # Test failed max_version match
    assert spack_inst.validate_versions(max_version="0.18.0") is False
    assert "greater than required maximum" in spack_inst.availability_error

    # Test failed min_version match
    assert spack_inst.validate_versions(min_version="0.20.0") is False
    assert "less than required minimum" in spack_inst.availability_error

    # Test failed exact_version match
    assert spack_inst.validate_versions(exact_version="0.18.0") is False
    assert "does not match required exact version" in spack_inst.availability_error


def test_utility_base_validate_versions_subprocess_fails(monkeypatch, tmpdir):
    """Test subprocess execution failure."""
    import os
    import stat

    script_path = str(tmpdir.join("fake_fail.sh"))
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write("exit 1\n")

    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IEXEC)

    SpackClass = type(get("spack", ObjectTypes.utilities))
    spack_inst = SpackClass("/path/to/spack")

    spack_inst.provided_executables[frozenset()][0]["version_cmd"] = script_path

    def mock_shutil_which(cmd, *args, **kwargs):
        if cmd == "spack":
            return script_path
        return None

    monkeypatch.setattr("shutil.which", mock_shutil_which)

    def mock_check_vcs(*args, **kwargs):
        return False

    monkeypatch.setattr(SpackClass, "_check_exact_match_via_vcs", mock_check_vcs)

    assert spack_inst.validate_versions(exact_version="0.18.0") is False
    assert "Error checking version" in spack_inst.availability_error


def test_utility_base_class_variants():
    """Test line 39: class_variants loop inside __init__ with proper directive"""
    from ramble.toolkit import variant

    SpackClass = type(get("spack", ObjectTypes.utilities))

    class TestVariantUtility(SpackClass):
        name = "test_var_util"
        __module__ = "ramble.app"
        variant("test_variant", default="True", description="test")

    inst = TestVariantUtility("/mock/path")
    assert len(inst.class_variants) > 0
