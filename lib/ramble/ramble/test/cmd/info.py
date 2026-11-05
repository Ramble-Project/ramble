# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import argparse
import re
from typing import Dict, List

import deprecation
import pytest

import ramble.cmd.common.info
import ramble.repository
from ramble.main import RambleCommand, RambleCommandError

info = RambleCommand("info")
repo = RambleCommand("repo")
create = RambleCommand("create")


@pytest.fixture(scope="module")
def parser():
    """Returns the parser for the module command"""
    prs = argparse.ArgumentParser()
    ramble.cmd.info.setup_parser(prs)
    return prs


@pytest.fixture()
def info_lines():
    lines = []
    return lines


@pytest.fixture()
def mock_print(monkeypatch, info_lines):

    def _print(*args):
        info_lines.extend(args)

    monkeypatch.setattr(ramble.cmd.common.info.color, "cprint", _print, raising=False)


@pytest.mark.parametrize("app", ["hostname"])
def test_it_just_runs(app):
    info(app)


@pytest.mark.parametrize("app_query", ["hostname"])
@pytest.mark.usefixtures("mock_print")
def test_info_fields(app_query, parser, info_lines):

    expected_fields = (
        "Description:",
        "pipelines",
        "tags",
    )

    args = parser.parse_args([app_query])
    ramble.cmd.info.info(parser, args)

    for text in expected_fields:
        match = [x for x in info_lines if text in x]
        assert match


@pytest.mark.parametrize("app_query", ["gromacs", "wrf"])
def test_spack_info_software(app_query):
    expected_fields = (
        "Description:",
        "executables",
        "pipelines",
        "setup:",
        "analyze:",
        "tags",
        "software_specs",
    )

    out = info("-v", app_query)

    for field in expected_fields:
        assert field in out


@pytest.mark.parametrize("app_query", ["wrfv3", "wrfv4"])
@deprecation.fail_if_not_removed
def test_deprecated_spack_info_software(app_query):
    expected_fields = (
        "Description:",
        "executables",
        "pipelines",
        "setup:",
        "analyze:",
        "tags",
        "software_specs",
    )

    out = info("-v", app_query)

    for field in expected_fields:
        assert field in out


@pytest.mark.parametrize(
    "app_query",
    [
        "zlib-configs",
    ],
)
def test_mock_spack_info_software(mock_applications, app_query):
    expected_fields = (
        "Description:",
        "executables",
        "pipelines",
        "setup:",
        "software_specs",
    )

    out = info("-v", app_query)

    for field in expected_fields:
        assert field in out


@pytest.mark.parametrize(
    "info_query",
    [
        ["--type", "modifiers", "apptainer"],
        ["--type", "modifier", "apptainer"],
        ["--type", "modifiers", "apptainer", "-vv"],
        ["--type", "package_managers", "spack"],
        ["--type", "package_manager", "spack"],
        ["--type", "package-manager", "spack"],
        ["--type", "workflow_managers", "slurm"],
        ["--type", "workflow_manager", "slurm"],
        ["--type", "workflow-manager", "slurm"],
    ],
)
def test_non_app_object_info_common_fields(info_query):
    expected_fields = (
        "Description",
        "object_variables",
    )
    out = info(*info_query)
    for field in expected_fields:
        assert field in out


def _get_shared_outputs():
    """Returns expected output of info directive for shared language"""

    shared_output = [
        # (section title, sample content, sample verbose content)
        ("maintainers", "maintainername", ""),
        ("tags", ["tag1", "tag2"], ""),
        ("known_versions", ["1.0", "2.0"], ["Version 1.0 of info", "Version 2.0 of info"]),
        ("figure_of_merit_contexts", "fom_context", ["fom context regex.*", "{test}"]),
        (
            "figures_of_merit",
            "fom_name",
            ["log_file: {log_file}", "fom regex.*", "test", "units: s"],
        ),
        ("package_manager_configs", "config_name", ["config:true", "package_manager=info"]),
        (
            "required_packages",
            "info-app-dep",
            ["application_version@1.0:", "package_manager=info", "+turn_on_required_directives"],
        ),
        ("compilers", "gcc12", ["gcc@12.2.0"]),
        ("software_specs", "info-app", ["info-app@5.0", "gcc12"]),
        ("archive_patterns", "{experiment_run_dir}/archive_test.*", ""),
        ("success_criteria", "success_criteria_name", ["string", "fom: test", "log.file"]),
        ("target_shells", "bash", ""),
        (
            "templates",
            "template_name",
            [
                "$workspace_shared/test_template.tpl",
                "test_template",
                "['+register_template_when']",
            ],
        ),
        (
            "validators",
            "validator_name",
            ["{n_nodes} == 1", "Give me a node, Vasili. One node only, please"],
        ),
        (
            "conflicts",
            "turn_on_required_directives=True",
            ["turn_on_required_directives conflicts with variant_default"],
        ),
        ("object_variables", "obj_var_name", ["default_obj_val", "An obj var"]),
        ("required_vars", "required_var_name", ["A required var", "type.required"]),
    ]

    return shared_output


def _get_application_outputs():
    """Returns expected output of info directive for application language"""

    app_output = [
        # (section title, sample content, sample verbose content)
        (
            "pipelines",
            [
                "analyze",
                "archive",
                "mirror",
                "setup",
                "pushdeployment",
                "pushtocache",
                "execute",
                "logs",
            ],
            "",
        ),
        (
            "workloads",
            "wl_name",
            [
                "['exec_name']",  # workload attribute
                "variant_name=variant_default",  # variable when condition
                "wl_var_name",  # workload variable
                "default_wl_val",  # variable attribute
                "Unconditional",  # env var when condition
                "ENV_VAR_NAME",  # env var
                "ENVVARVAL",  # env var attribute
            ],
        ),
        ("workload_groups", "wl_group", ["wl_name"]),
        ("executables", "exec_name", ["template", "exec template", "{log_file}"]),
        ("inputs", "input_name", ["file:///tmp/test_file.log", "{workload_input_dir}"]),
        ("builtins", ["builtin::env_vars", "builtin::builtin_name"], ["env_vars", "builtin_name"]),
        (
            "registered_phases",
            ["mirror", "setup", "analyze"],
            ["mirror_inputs", "get_inputs", "after_make_experiments", "analyze_experiments"],
        ),
    ]

    out = _get_shared_outputs()
    out.extend(app_output)

    return out


def _get_modifier_outputs():
    """Returns expected output of info directive for modifier language"""

    mod_output = [
        # (section title, sample content, sample verbose content)
        (
            "pipelines",
            [
                "analyze",
                "archive",
                "mirror",
                "setup",
                "pushtocache",
                "execute",
                "logs",
            ],
            "",
        ),
        ("builtins", "modifier_builtin::info::builtin_name", "builtin_name"),
        ("registered_phases", "setup", "after_make_experiments"),
        ("modes", ["disabled", "info-mode", "another-mode"], ["Info mode", "Another mode"]),
        (
            "variable_modifications",
            "var_mod_name",
            ["test var modified", "['+variable_modification_active', 'info_mode=test']"],
        ),
        ("executable_modifiers", "exec_modifier_name", "+exec_modifier_active"),
        (
            "env_var_modifications",
            ["ENV_VAR_MOD", "APP_ENV_VAR"],
            ["ENV_VAR_MOD_SET", "info_mode=info-mode", "APPEND", "unset", "PREPEND"],
        ),
        (
            "package_manager_requirements",
            "list not-a-package",
            ["not_empty", "info_mode=another-mode"],
        ),
    ]

    out = _get_shared_outputs()
    out.extend(mod_output)

    return out


def _get_package_manager_outputs():
    """Returns expected output of info directive for package manager language"""

    pkg_man_output = [
        # (section title, sample content, sample verbose content)
        (
            "pipelines",
            [
                "analyze",
                "archive",
                "mirror",
                "setup",
                "pushdeployment",
                "pushtocache",
                "execute",
                "logs",
            ],
            "",
        ),
        ("builtins", "package_manager_builtin::info::builtin_name", "builtin_name"),
        ("registered_phases", "setup", "after_make_experiments"),
        ("object_variables", "pm_var_name", ["default_pm_var_val", "A PM variable"]),
        (
            "families",
            "package_manager_family=info-package-manager",
            "package_manager_family=info-package-manager",
        ),
    ]

    out = _get_shared_outputs()
    out.extend(pkg_man_output)

    return out


def _get_workflow_manager_outputs():
    """Returns expected output of info directive for workflow manager language"""

    pkg_man_output = [
        # (section title, sample content, sample verbose content)
        (
            "pipelines",
            [
                "analyze",
                "setup",
                "execute",
            ],
            "",
        ),
        ("builtins", "workflow_manager_builtin::info::builtin_name", "builtin_name"),
        ("registered_phases", "setup", "after_make_experiments"),
        (
            "object_variables",
            ["wm_var_name", "workflow_pragmas", "workflow_hostfile_cmd"],
            [
                "default_wm_var_val",
                "A WM variable",
                "Pragmas to apply",
                "Hostfile command to apply",
            ],
        ),
        (
            "families",
            "workflow_manager_family=info-workflow-manager",
            "workflow_manager_family=info-workflow-manager",
        ),
    ]

    out = _get_shared_outputs()
    out.extend(pkg_man_output)

    return out


@pytest.mark.parametrize(
    "object_type, expected_output, verbose",
    [
        ("applications", _get_application_outputs(), False),
        ("applications", _get_application_outputs(), True),
        ("modifiers", _get_modifier_outputs(), False),
        ("modifiers", _get_modifier_outputs(), True),
        ("package_managers", _get_package_manager_outputs(), False),
        ("package_managers", _get_package_manager_outputs(), True),
        ("workflow_managers", _get_workflow_manager_outputs(), False),
        ("workflow_managers", _get_workflow_manager_outputs(), True),
    ],
)
def test_info_directives(
    mutable_mock_apps_repo,
    mock_modifiers,
    mutable_mock_wms_repo,
    mutable_mock_pkg_mans_repo,
    object_type,
    expected_output,
    verbose,
):
    def parse_output_by_section(output: str, section_titles: List[str]) -> Dict[str, str]:
        section_titles_to_search = []
        # add format chars to match section titles "title:" or "# title #" but
        # ignore the same title nested within a section
        for section in expected_output:
            section_titles_to_search.append("\n" + section[0] + ":\n")
            section_titles_to_search.append("\n# " + section[0] + " #\n")

        regex_pattern = "(" + "|".join(section_titles_to_search) + ")"
        parts = re.split(regex_pattern, output)
        sections = {}

        i = 1
        while i < len(parts):
            # remove the extra format chars to match the expected output
            title = parts[i].replace("#", "").replace(":", "").strip()
            content = parts[i + 1].strip()
            sections[title] = content
            i += 2

        return sections

    section_titles = [section[0] for section in expected_output]

    if verbose:
        out = info("--type", object_type, "info", "-v")
    else:
        out = info("--type", object_type, "info")

    out_dict = parse_output_by_section(out, section_titles)

    for section, values, verbose_values in expected_output:

        section_content = out_dict[section]

        if isinstance(values, str):
            assert values in section_content
        else:
            for val in values:
                assert val in section_content
        if verbose:
            if isinstance(verbose_values, str):
                assert verbose_values in section_content
            else:
                for val in verbose_values:
                    assert val in section_content


def test_info_object_name_formats(mutable_mock_apps_repo):
    output = info("basic")
    assert "basic" in output
    output = info("basic-inherited")
    assert "basic-inherited" in output
    output = info("basic_inherited")
    assert "basic-inherited" in output
    output = info("basic_underscores")
    assert "basic_underscores" in output
    output = info("basic-underscores")
    assert "basic_underscores" in output


def test_info_conflicts_pattern(mutable_mock_apps_repo):
    # When pattern matches, conflict should be printed
    out = info(
        "--type",
        "applications",
        "-v",
        "--attrs",
        "conflicts",
        "-p",
        "*turn_on_required_directives*",
        "info",
    )
    assert "turn_on_required_directives=True" in out
    assert "turn_on_required_directives conflicts with variant_default" in out

    # When pattern does not match, conflict should not be printed
    out = info(
        "--type", "applications", "-v", "--attrs", "conflicts", "-p", "*not_matching*", "info"
    )
    assert "turn_on_required_directives=True" not in out
    assert "turn_on_required_directives conflicts with variant_default" not in out


def test_info_namespaced_spec(mutable_config, tmpdir):
    repo_path = str(tmpdir.join("test_repo"))
    repo_ns = "mockrepo"

    try:
        for t in ramble.repository.ObjectTypes:
            ramble.repository.paths[t]._instance = None

        repo("create", repo_path, repo_ns)
        repo("add", "-t", "applications", "--scope=site", repo_path)

        for t in ramble.repository.ObjectTypes:
            ramble.repository.paths[t]._instance = None

        create(f"{repo_ns}.app.test-app")

        out = info(f"{repo_ns}.app.test-app")
        assert "Description" in out

    finally:
        for t in ramble.repository.ObjectTypes:
            ramble.repository.paths[t]._instance = None


def test_info_invalid_attribute():
    with pytest.raises(RambleCommandError, match="Attribute 'd' is not valid"):
        info("gromacs", "--attributes", "d")


def test_info_attributes_with_spaces():
    out = info("gromacs", "--attributes", "maintainers, workloads")
    assert "maintainers" in out
    assert "workloads" in out


def test_info_fom_type_formatting():
    out = info("intel-mpi-benchmarks", "-v", "--attrs", "figures_of_merit")
    assert "fom_type: Undefined" in out
    assert "FomType.UNDEFINED" not in out
