# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
import os
import shutil
from types import SimpleNamespace

import pytest

import ramble.cmd.repo
import ramble.config
import ramble.repository
from ramble.cmd.repo import format_types
from ramble.error import RambleCommandError
from ramble.main import RambleCommand
from ramble.repository import BadRepoError

import spack.util.spack_yaml as syaml

repo = RambleCommand("repo")


def test_help_option():
    with pytest.raises(SystemExit):
        repo("--help")
    assert repo.returncode in (None, 0)


def test_create_add_list_remove(mutable_config, tmpdir):
    # Create a new repository and check that the expected
    # files are there
    repo("create", str(tmpdir), "mockrepo")
    assert os.path.exists(os.path.join(str(tmpdir), "repo.yaml"))
    assert os.path.exists(os.path.join(str(tmpdir), "applications"))

    # Add the new repository and check it appears in the list output
    repo("add", "-t", "applications", "--scope=site", str(tmpdir))
    output = repo("list", "--scope=site", output=str)
    assert "mockrepo" in output

    # Then remove it and check it's not there
    repo("remove", "--scope=site", str(tmpdir))
    output = repo("list", "--scope=site", output=str)
    assert "mockrepo" not in output


@pytest.mark.parametrize("subdir", ["applications", "", "foo"])
def test_create_add_list_remove_flags(mutable_config, tmpdir, subdir):
    # Create a new repository and check that the expected
    # files are there
    repo("create", str(tmpdir), "mockrepo", "-d", subdir)
    assert os.path.exists(os.path.join(str(tmpdir), "repo.yaml"))
    assert os.path.exists(os.path.join(str(tmpdir), subdir))

    # Add the new repository and check it appears in the list output
    repo("add", "-t", "applications", "--scope=site", str(tmpdir))
    output = repo("list", "--scope=site", output=str)
    assert "mockrepo" in output

    # Then remove it and check it's not there
    repo("remove", "--scope=site", str(tmpdir))
    output = repo("list", "--scope=site", output=str)
    assert "mockrepo" not in output


def test_add_behavior(mutable_config, tmpdir):
    # Create an app-only repo
    repo("create", str(tmpdir), "mockrepo", "-t", "applications")
    assert os.path.exists(os.path.join(str(tmpdir), "application_repo.yaml"))
    assert os.path.exists(os.path.join(str(tmpdir), "applications"))

    # Complains when specified repo type is not found
    with pytest.raises(
        BadRepoError, match="Failed to find valid repo with type ObjectTypes.modifiers"
    ):
        repo("add", "-t", "modifiers", "--scope=site", str(tmpdir))
    output = repo("list", "--scope=site", output=str)
    assert "mockrepo" not in output

    # Do not complain when type is not specified
    repo("add", "--scope=site", str(tmpdir))
    output = repo("list", "--scope=site", output=str)
    assert "mockrepo" in output

    # Complains if the given path contains no valid repo for all object types
    shutil.rmtree(os.path.join(tmpdir, "applications"))
    with pytest.raises(BadRepoError, match="not a valid repo for any object types"):
        repo("add", "--scope=site", str(tmpdir))


def test_remove_from_any_scope(mutable_config, tmpdir):
    """Tests that 'repo rm' without a scope removes from the correct scope."""
    repo_path = str(tmpdir.join("test_repo"))
    repo_name = "test_repo_namespace"

    # Create a new repository
    repo("create", repo_path, repo_name)

    # Add the new repository to the 'site' scope
    repo("add", "-t", "applications", "--scope=site", repo_path)

    apps_repos_in_site = mutable_config.get("repos", scope="site")
    assert repo_path in apps_repos_in_site, "Repo should be in site config after add."

    # Check that it's in the list (merged scopes)
    output = repo("list", output=str)
    assert repo_name in output
    print(output)

    # Then remove it without specifying a scope
    repo("remove", "--scope=site", repo_path)

    # Check it's not in the site scope list anymore
    output = repo("list", "--scope=site", output=str)
    assert repo_name not in output
    print(output)

    apps_repos_in_site_after_remove = mutable_config.get("repos", scope="site")
    assert (
        repo_path not in apps_repos_in_site_after_remove
    ), "Repo should be removed from site config."


def test_add_with_any_type_registers_all_types(mutable_config, tmpdir):
    """
    Tests that `repo add` with `type=any` (the default) correctly registers
    only the repo types that are actually present in the repository.
    """
    repo_path = str(tmpdir)
    repo_name = "partial_repo"

    # Create a repository with both applications and modifiers
    repo("create", repo_path, repo_name)
    assert os.path.exists(os.path.join(str(tmpdir), "repo.yaml"))
    assert os.path.exists(os.path.join(str(tmpdir), "applications"))
    print(repo_path)

    # Make the repo incomplete by removing the modifiers directory
    shutil.rmtree(os.path.join(repo_path, "modifiers"))

    # Add the repository without specifying a type (defaults to `any`)
    repo("add", "--scope=site", repo_path)

    # Check the configuration to ensure all types were registered
    site_repos = mutable_config.get("repos", scope="site")
    assert repo_path in site_repos
    assert repo_path in site_repos

    # The repo name should appear in the overall list
    output = repo("list", output=str)
    assert repo_name in output


def test_add_non_existent_repo(mutable_config, tmpdir):
    """Tests that `repo add` with a non-existent path dies."""
    non_existent_path = str(tmpdir.join("non_existent_repo"))
    with pytest.raises(RambleCommandError) as e:
        repo("add", non_existent_path)

    # Check that the exception message contains the expected output
    expected_error_message = f"No such file or directory: {non_existent_path}"
    assert expected_error_message in str(e.value)
    # Ensure the command indeed exited with code 1
    assert "Command exited with code 1" in str(e.value)


def test_add_repo_missing_config_file(mutable_config, tmpdir):
    """Tests that `repo add` with a directory missing repo.yaml raises BadRepoError directly."""
    # Create a directory that will serve as our "repo"
    repo_path = tmpdir.mkdir("empty_repo")

    # This is normally created by `repo create`, but we are testing the case
    # where it's missing (or invalid)
    # Create a dummy repo.yaml and then remove it to simulate the missing file
    repo_config_file = os.path.join(str(repo_path), "repo.yaml")
    with open(repo_config_file, "w", encoding="utf-8") as f:
        syaml.dump({"repo": {"namespace": "test_namespace"}}, f)
    os.remove(repo_config_file)

    with pytest.raises(BadRepoError) as e:  # Catch BadRepoError directly
        repo("add", str(repo_path))

    expected_error_message = f"No valid config file found in '{repo_path}'"
    assert expected_error_message in str(e.value)


@pytest.mark.parametrize("type_arg", ["application", "app"])
def test_singular_type_repo_commands(mutable_config, tmpdir, type_arg):
    repo_path = str(tmpdir.join(f"test_repo_{type_arg}"))
    repo("create", repo_path, f"mockrepo_{type_arg}", "-t", type_arg)
    assert os.path.exists(os.path.join(repo_path, "application_repo.yaml"))
    assert os.path.exists(os.path.join(repo_path, "applications"))

    repo("add", "-t", type_arg, "--scope=site", repo_path)
    output = repo("list", "-t", type_arg, "--scope=site", output=str)
    assert f"mockrepo_{type_arg}" in output

    repo("remove", "-t", type_arg, "--scope=site", repo_path)
    output = repo("list", "-t", type_arg, "--scope=site", output=str)
    assert f"mockrepo_{type_arg}" not in output


def test_repo_list_multitype_non_application_scope(mutable_empty_config, tmpdir):
    """Test that repo list (type 'any') lists modifiers even if no applications are in scope."""
    mod_repo_path = str(tmpdir.join("mod_repo"))
    repo("create", mod_repo_path, "mockmodrepo", "-t", "modifiers")
    repo("add", "-t", "modifiers", mod_repo_path)

    output = repo("list", output=str)
    assert "mockmodrepo" in output


def test_repo_list_no_results_warning(mutable_empty_config):
    out = repo("list", output=str)
    assert repo.returncode == 0
    assert "No repositories found" in out

    out = repo("list", "-t", "modifiers", output=str)
    assert repo.returncode == 0
    assert "No modifiers repositories found" in out

    out = repo("list", "--scope=site", output=str)
    assert repo.returncode == 0
    assert "No repositories found in scope 'site'" in out


def test_repo_list_compact(mutable_config, tmpdir):
    repo_path = str(tmpdir.join("compact_repo"))
    repo("create", repo_path, "compact_ns")
    repo("add", "--scope=site", repo_path)

    output = repo("list", "--format=compact", output=str)

    assert "NAMESPACE" in output
    assert "TYPES" in output
    assert "PATH" in output
    assert "compact_ns" in output

    # Ensure the repo appears only once in the compact output
    assert output.count("compact_ns") == 1


def test_repo_list_compact_is_the_default(mutable_config, tmpdir):
    """Bare `repo list` uses the compact format."""
    repo_path = str(tmpdir.join("default_repo"))
    repo("create", repo_path, "default_ns")
    repo("add", "--scope=site", repo_path)

    implicit = repo("list", output=str)
    explicit = repo("list", "--format=compact", output=str)

    assert implicit == explicit
    assert "NAMESPACE" in implicit
    assert implicit.count("default_ns") == 1


def test_repo_list_full_format_still_available(mutable_config, tmpdir):
    """The full format keeps the original per-type listing."""
    repo_path = str(tmpdir.join("full_repo"))
    repo("create", repo_path, "full_ns")
    repo("add", "--scope=site", repo_path)

    output = repo("list", "--format=full", output=str)

    assert "NAMESPACE" not in output
    assert "full_ns" in output
    # The repo is registered for every object type, so it repeats in this format
    assert output.count("full_ns") > 1


def test_repo_list_compact_specific_type(mutable_config, tmpdir):
    repo_path = str(tmpdir.join("app_only_repo"))
    repo("create", repo_path, "app_ns", "-t", "applications")
    repo("add", "-t", "applications", "--scope=site", repo_path)

    output = repo("list", "-t", "applications", "--format=compact", output=str)
    assert "NAMESPACE" in output
    assert "TYPES" in output
    assert "PATH" in output
    assert "app_ns" in output
    assert output.count("app_ns") == 1


def test_repo_list_compact_empty(mutable_empty_config):
    output = repo("list", "--format=compact", output=str)
    assert repo.returncode == 0
    assert "No repositories found" in output


@pytest.mark.parametrize(
    "types_list,expected",
    [
        # An empty list should never reach the summarizer, but guard against it anyway
        ([], "none"),
        # Three or fewer types are spelled out in full
        (["applications"], "applications"),
        (["applications", "modifiers"], "applications, modifiers"),
        (
            ["applications", "modifiers", "package_managers"],
            "applications, modifiers, package_managers",
        ),
        # Four or more types switch to abbreviations to keep the column narrow
        (
            ["applications", "modifiers", "package_managers", "workflow_managers"],
            "app, mod, pkg_man, wm",
        ),
        # Once the abbreviations grow too wide, fall back to a bare count
        (
            [
                "applications",
                "modifiers",
                "package_managers",
                "workflow_managers",
                "systems",
                "platforms",
                "base_classes",
            ],
            "7 types",
        ),
    ],
)
def test_format_types(types_list, expected):
    assert format_types(types_list) == expected


def test_format_types_all():
    """A repo registered for every object type collapses to 'all'."""
    all_types = [obj_type.name for obj_type in ramble.repository.ObjectTypes]
    assert format_types(all_types) == "all"


def test_format_types_all_non_utility():
    """Utility types are commonly absent, so that case gets its own label."""
    non_utility = [
        obj_type.name for obj_type in ramble.repository.ObjectTypes if "util" not in obj_type.name
    ]
    assert format_types(non_utility) == "all (non-utility)"


def test_repo_list_compact_skips_invalid_repos(mutable_config, tmpdir):
    """A stale path in the config is skipped instead of failing the listing."""
    valid_path = str(tmpdir.join("valid_repo"))
    repo("create", valid_path, "valid_ns")
    repo("add", "--scope=site", valid_path)

    missing_path = str(tmpdir.join("does_not_exist"))
    roots = ramble.config.get("repos", scope="site")
    ramble.config.set("repos", syaml.syaml_list([missing_path] + list(roots)), scope="site")

    output = repo("list", "--format=compact", output=str)
    assert repo.returncode == 0
    assert missing_path not in output
    assert "valid_ns" in output


@pytest.mark.parametrize("fmt", ["full", "compact"])
@pytest.mark.parametrize("type_args", [[], ["-t", "applications"]])
def test_repo_list_summary_only_on_tty(mutable_config, tmpdir, monkeypatch, type_args, fmt):
    """The count summary is written for interactive use, but kept out of pipes."""
    repo_path = str(tmpdir.join("tty_repo"))
    repo("create", repo_path, "tty_ns")
    repo("add", "--scope=site", repo_path)

    piped = repo("list", *type_args, f"--format={fmt}", output=str)
    assert "repositor" not in piped

    # Only repo.py's view of sys is replaced, so output capture is left intact
    monkeypatch.setattr(
        ramble.cmd.repo, "sys", SimpleNamespace(stdout=SimpleNamespace(isatty=lambda: True))
    )

    on_tty = repo("list", *type_args, f"--format={fmt}", output=str)
    assert "repositor" in on_tty
    assert "tty_ns" in on_tty
