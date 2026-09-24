# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

from ramble.main import RambleCommand

pytestmark = pytest.mark.usefixtures("mutable_config")

list = RambleCommand("list")


def test_list():
    output = list()
    assert "hostname" in output


def test_list_filter():
    output = list("host*")
    assert "hostname" in output


@pytest.mark.maybeslow
def test_list_search_description():
    output = list("--search-description", "example")
    assert "hostname" in output


def test_list_tags():
    output = list("--tags", "test-app")
    assert "hostname" in output


def test_list_format_name_only():
    output = list("--format", "name_only")
    assert "hostname" in output


@pytest.mark.maybeslow
def test_list_format_version_json():
    output = list("--format", "version_json")
    assert '  {"name": "hostname"' in output
    import json

    print(" Test output =")
    print(output)
    json.loads(output)


@pytest.mark.maybeslow
def test_list_format_html():
    output = list("--format", "html")
    assert '<div class="section" id="gromacs">' in output
    assert "<dt>Workloads:</dt>" in output
    assert "<details>" in output
    assert "<summary>lignocellulose</summary>" in output
    assert "<dt>Executables:</dt>" in output
    assert "execute" in output
    assert "<dt>Variables:</dt>" in output
    assert "<dt>mdrun</dt>" in output
    # Assert on input_file descriptions
    assert "<dt>lignocellulose</dt>" in output
    assert "A model of cellulose and lignocellulosic biomass in an aqueous solution" in output
    assert "</details>" in output


@pytest.mark.maybeslow
def test_list_base_html():
    output = list("--type", "base_applications", "--format", "html")
    assert '<div class="section" id="hpl">' in output


@pytest.mark.parametrize(
    "type_arg",
    [
        "applications",
        "application",
        "app",
        "base_applications",
        "base_application",
        "base-application",
        "modifiers",
        "modifier",
        "package_managers",
        "package_manager",
        "package-manager",
        "workflow_managers",
        "workflow_manager",
    ],
)
def test_list_types(type_arg):
    output = list("--type", type_arg)
    assert output is not None
    assert len(output) > 0


def test_list_update(tmpdir):
    update_file = tmpdir.join("output")

    # not yet created when list is run
    list("--update", str(update_file))
    assert update_file.exists()
    with update_file.open() as f:
        assert f.read()

    # created but older than any package
    with update_file.open("w") as f:
        f.write("empty\n")
    update_file.setmtime(0)
    list("--update", str(update_file))
    assert update_file.exists()
    with update_file.open() as f:
        assert f.read() != "empty\n"

    # newer than any packages
    with update_file.open("w") as f:
        f.write("empty\n")
    list("--update", str(update_file))
    assert update_file.exists()
    with update_file.open() as f:
        assert f.read() == "empty\n"


def test_list_no_results_warning():
    out = list("nonexistent_app_name_xyz")
    assert list.returncode == 0
    assert "No applications found matching filter 'nonexistent_app_name_xyz'" in out

    out = list("--tags", "nonexistent_tag_xyz")
    assert list.returncode == 0
    assert "No applications found matching tags 'nonexistent_tag_xyz'" in out

    out = list("--type", "modifiers", "nonexistent_mod_xyz")
    assert list.returncode == 0
    assert "No modifiers found matching filter 'nonexistent_mod_xyz'" in out

    out = list("--tags", "nonexistent_tag", "nonexistent_app")
    assert list.returncode == 0
    assert (
        "No applications found matching filter 'nonexistent_app' and tags 'nonexistent_tag'" in out
    )
