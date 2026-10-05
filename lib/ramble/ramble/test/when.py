# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import json
import os

import pytest

import ramble.config
import ramble.workspace
from ramble.error import ObjectValidationError, RambleCommandError
from ramble.main import RambleCommand
from ramble.pkg_man.builtin.spack_lightweight import ValidationFailedError

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
    "mutable_mock_apps_repo",
    "mock_modifiers",
)

config = RambleCommand("config")
workspace = RambleCommand("workspace")


def test_register_phase_when(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", "variants:register_phase_when:true", global_args=global_args)

        ws._re_read()
        output = workspace("setup", "--dry-run", global_args=global_args)

        assert "Test Phase" in output

        config("remove", "variants:register_phase_when:true", global_args=global_args)
        config("add", "variants:register_phase_when:false", global_args=global_args)

        ws._re_read()
        output = workspace("setup", "--dry-run", global_args=global_args)

        assert "Test Phase" not in output


def test_fom_context_enabled_when_true(workspace_name):
    global_args = ["-w", workspace_name]

    test_output = """
test when context 4.2
test when fom 5.6 test always 3.5
test inheritance 12.0
"""

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        ws.write()

        output_path = os.path.join(
            ws.experiment_dir, "when-directives", "test_wl", "generated", "test.out"
        )
        results_path = os.path.join(ws.results_dir, "results.latest.txt")

        workspace("setup", global_args=global_args)

        ws._re_read()
        with open(output_path, "w+", encoding="utf-8") as f:
            f.write(test_output)

        workspace("analyze", global_args=global_args)

        with open(results_path, encoding="utf-8") as f:
            results = f.read()

            assert "test always context" in results
            assert "3.5" in results
            assert "test when context" not in results
            assert "4.2" not in results

        config("add", "variants:register_fom_context_when:true", global_args=global_args)

        with ramble.config.override("config:overwrite_inventories", True):
            workspace("analyze", global_args=global_args)

        with open(results_path, encoding="utf-8") as f:
            results = f.read()

            assert "test always context" in results
            assert "3.5" in results
            assert "test when context" in results
            assert "4.2" in results


def test_fom_enabled_when_true(workspace_name):
    global_args = ["-w", workspace_name]

    test_output = """
test when context 4.2
test when fom 5.6 test always 3.5
test inheritance 12.0
"""

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        ws.write()

        output_path = os.path.join(
            ws.experiment_dir, "when-directives", "test_wl", "generated", "test.out"
        )
        results_path = os.path.join(ws.results_dir, "results.latest.txt")

        workspace("setup", global_args=global_args)

        with open(output_path, "w+", encoding="utf-8") as f:
            f.write(test_output)

        workspace("analyze", global_args=global_args)

        with open(results_path, encoding="utf-8") as f:
            results = f.read()

            assert "test always context" in results
            assert "3.5" in results
            assert "test_fom_when" not in results
            assert "5.6" not in results

        config("add", "variants:register_fom_context_when:true", global_args=global_args)
        config("add", "variants:register_fom_when:true", global_args=global_args)

        ws._re_read()
        with ramble.config.override("config:overwrite_inventories", True):
            workspace("analyze", global_args=global_args)

        with open(results_path, encoding="utf-8") as f:
            results = f.read()

            assert "test always context" in results
            assert "4.2" in results
            assert "test_fom_when" in results
            assert "5.6" in results


def test_fom_errors_when_context_not_found(workspace_name):
    global_args = ["-w", workspace_name]

    test_output = """
test when context 4.2
test when fom 5.6 test always 3.5
test inheritance 12.0
"""

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        ws.write()

        output_path = os.path.join(
            ws.experiment_dir, "when-directives", "test_wl", "generated", "test.out"
        )
        results_path = os.path.join(ws.results_dir, "results.latest.txt")

        workspace("setup", global_args=global_args)

        with open(output_path, "w+", encoding="utf-8") as f:
            f.write(test_output)

        workspace("analyze", global_args=global_args)

        with open(results_path, encoding="utf-8") as f:
            results = f.read()

            assert "test always context" in results
            assert "3.5" in results

        config("add", "variants:register_fom_when:true", global_args=global_args)

        ws._re_read()

        with pytest.raises(
            RambleCommandError,
            match=r"(?s)Command output:.*context 'test_context_when'.*is not found",
        ):
            workspace("analyze", global_args=global_args)


def test_same_fom_name_different_context(workspace_name):
    global_args = ["-w", workspace_name]

    test_output = """
'Always' fom in always context is decimal, 'always' fom in when context is integer
test when context 4.2
test when fom 5.6 test always 3.5
test inheritance 12.0
"""

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        ws.write()

        output_path = os.path.join(
            ws.experiment_dir, "when-directives", "test_wl", "generated", "test.out"
        )
        results_path = os.path.join(ws.results_dir, "results.latest.txt")

        ws._re_read()
        workspace("setup", global_args=global_args)

        with open(output_path, "w+", encoding="utf-8") as f:
            f.write(test_output)

        workspace("analyze", global_args=global_args)

        with open(results_path, encoding="utf-8") as f:
            results = f.read()

            assert "test always context" in results
            assert "3.5" in results
            assert "test when context" not in results
            assert "5.6" not in results

        config("add", "variants:register_fom_context_when:true", global_args=global_args)

        ws._re_read()
        with ramble.config.override("config:overwrite_inventories", True):
            workspace("analyze", global_args=global_args)

        with open(results_path, encoding="utf-8") as f:
            results = f.read()

            assert "test always context" in results
            assert "3.5" in results
            assert "test when context" in results
            assert "3 integer" in results


def test_fom_overwrites_when_inherited(workspace_name):
    global_args = ["-w", workspace_name]

    test_output = """
Parent FOM regex is decimal, child FOM regex is integer and should clobber parent FOM
test when context 4.2
test when fom 5.6 test always 3.5
test inheritance 12.0
"""

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives-inherited",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        ws.write()

        output_path = os.path.join(
            ws.experiment_dir, "when-directives-inherited", "test_wl", "generated", "test.out"
        )
        results_path = os.path.join(ws.results_dir, "results.latest.txt")

        ws._re_read()
        workspace("setup", global_args=global_args)

        with open(output_path, "w+", encoding="utf-8") as f:
            f.write(test_output)

        workspace("analyze", global_args=global_args)

        with open(results_path, encoding="utf-8") as f:
            results = f.read()

            assert "test always context" in results
            assert "3.5" in results
            assert "test inheritance context" not in results
            assert "12 integer" not in results

        config("add", "variants:register_inherited_fom_when:true", global_args=global_args)

        ws._re_read()

        with ramble.config.override("config:overwrite_inventories", True):
            output = workspace("analyze", global_args=global_args)

        assert "Overwriting with new definition from when-directives-inherited" in output

        with open(results_path, encoding="utf-8") as f:
            results = f.read()

            assert "test always context" not in results
            assert "3.5" not in results
            assert "test inheritance context" in results
            assert "12 integer" in results
            assert "12.0" not in results


@pytest.mark.parametrize(
    "validator_value,fails",
    [
        (True, True),
        (False, False),
    ],
)
def test_register_validator_when(workspace_name, validator_value, fails):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-variants",
            "--wf",
            "test_wl",
            "-v",
            "zlib_path=/not/a/path",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", "variants:inc_zlib:True", global_args=global_args)
        config("add", "variants:zlib_type:preferred", global_args=global_args)
        config("add", f"variants:validation:{validator_value}", global_args=global_args)

        ws._re_read()

        failed = False
        try:
            workspace("setup", global_args=global_args)
        except ObjectValidationError:
            failed = True

        if not fails:
            assert not failed
        else:
            assert failed


@pytest.mark.parametrize(
    "zlib_type,validation,fails",
    [
        ("preferred", True, True),
        ("preferred", False, False),
        ("testing", True, False),
    ],
)
def test_conflicts_when(workspace_name, zlib_type, validation, fails):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-variants",
            "--wf",
            "test_wl",
            "-v",
            "zlib_path=/not/a/path",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=2",
            "-v",
            "processes_per_node=1",
            global_args=global_args,
        )

        config("add", f"variants:zlib_type:{zlib_type}", global_args=global_args)
        config("add", f"variants:validation:{validation}", global_args=global_args)

        ws._re_read()

        failed = False
        try:
            workspace("setup", global_args=global_args)
        except ObjectValidationError as e:
            if "Conflict detected" in str(e):
                failed = True

        assert failed == fails


@pytest.mark.parametrize(
    "version,validation,fails",
    [
        ("2.0", True, True),
        ("2.0", False, False),
        ("1.0", True, False),
    ],
)
def test_conflicts_version_when(workspace_name, version, validation, fails):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            f"when-variants@{version}",
            "--wf",
            "test_wl",
            "-v",
            "zlib_path=/not/a/path",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=2",
            "-v",
            "processes_per_node=1",
            global_args=global_args,
        )

        config("add", "variants:zlib_type:testing", global_args=global_args)
        config("add", f"variants:validation:{validation}", global_args=global_args)

        ws._re_read()

        failed = False
        try:
            workspace("setup", global_args=global_args)
        except ObjectValidationError as e:
            if "Conflict detected" in str(e):
                failed = True

        assert failed == fails


@pytest.mark.parametrize(
    "inc_value,type_value",
    [
        (True, "preferred"),
        (True, "testing"),
        (True, "modifier"),
        (False, "preferred"),
    ],
)
def test_formatted_exec_when(workspace_name, inc_value, type_value):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-variants",
            "--wf",
            "test_wl",
            "-v",
            "zlib_path=/not/a/path",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", f"variants:inc_zlib:{inc_value}", global_args=global_args)
        config("add", f"variants:zlib_type:{type_value}", global_args=global_args)

        if inc_value:
            inc_str = f"included with type of {type_value}"
        else:
            inc_str = "not included"
        test_str = f"     from_variant zlib {inc_str}"

        ws._re_read()
        workspace("setup", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-variants",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            assert test_str in data
            assert "{test_formatted_exec}" not in data


@pytest.mark.parametrize(
    "workload_name",
    ["test_wl", "test_unset_wl"],
)
def test_variable_when_workload_constraint(workspace_name, workload_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-variants",
            "--wf",
            workload_name,
            "-v",
            "zlib_path=/not/a/path",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        if workload_name == "test_wl":
            test_str = "Test when workload variable is_defined"
        else:
            test_str = "Test when workload variable {test_when_var}"

        ws._re_read()
        workspace("setup", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-variants",
            workload_name,
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            assert test_str in data


@pytest.mark.parametrize(
    "inc_value,type_value",
    [
        (True, "preferred"),
        (True, "testing"),
        (True, "modifier"),
        (False, "preferred"),
    ],
)
def test_variable_when(workspace_name, inc_value, type_value):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-variants",
            "--wf",
            "test_wl",
            "-v",
            "zlib_path=/not/a/path",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", f"variants:inc_zlib:{inc_value}", global_args=global_args)
        config("add", f"variants:zlib_type:{type_value}", global_args=global_args)

        if inc_value:
            test_str = f"Standard was {type_value}"
        else:
            test_str = "Standard was unincluded"

        ws._re_read()
        workspace("setup", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-variants",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            assert test_str in data


@pytest.mark.parametrize(
    "inc_value",
    [True, False],
)
def test_package_manager_variable_when(workspace_name, inc_value, mutable_mock_pkg_mans_repo):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-variants",
            "--wf",
            "test_wl",
            "-v",
            "zlib_path=/not/a/path",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=when-package-manager",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", f"variants:package_manager_included:{inc_value}", global_args=global_args)

        if inc_value:
            test_str = "PM test: included"
        else:
            test_str = "PM test: {pm_var_test}"

        ws._re_read()
        workspace("setup", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-variants",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            assert test_str in data


@pytest.mark.parametrize(
    "inc_value",
    [True, False],
)
def test_workflow_manager_variable_when(workspace_name, inc_value, mutable_mock_wms_repo):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-variants",
            "--wf",
            "test_wl",
            "-v",
            "zlib_path=/not/a/path",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "workflow_manager=when-workflow-manager",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", f"variants:workflow_manager_included:{inc_value}", global_args=global_args)

        if inc_value:
            test_str = "WM test: included"
        else:
            test_str = "WM test: {wm_var_test}"

        ws._re_read()
        workspace("setup", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-variants",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            assert test_str in data


@pytest.mark.parametrize(
    "inc_value",
    [True, False],
)
def test_modifier_variable_when(workspace_name, inc_value, mutable_mock_mods_repo):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:

        workspace(
            "manage",
            "experiments",
            "when-variants",
            "--wf",
            "test_wl",
            "-v",
            "zlib_path=/not/a/path",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config_path = os.path.join(ws.config_dir, "modifiers.yaml")
        with open(config_path, "w+", encoding="utf-8") as f:
            f.write("modifiers:\n")
            f.write(" - name: when-modifier\n")

        config("add", f"variants:modifier_included:{inc_value}", global_args=global_args)

        if inc_value:
            test_str = "MOD test: included"
        else:
            test_str = "MOD test: {mod_var_test}"

        ws._re_read()
        workspace("setup", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-variants",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            assert test_str in data


def test_success_criteria_when(workspace_name):
    global_args = ["-w", workspace_name]

    test_output = """
test when context 4.2
test when fom 5.6 test always 3.5
test inheritance 12.0
"""

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        ws.write()

        output_path = os.path.join(
            ws.experiment_dir, "when-directives", "test_wl", "generated", "test.out"
        )
        results_path = os.path.join(ws.results_dir, "results.latest.txt")

        workspace("setup", global_args=global_args)

        with open(output_path, "w+", encoding="utf-8") as f:
            f.write(test_output)

        workspace("analyze", global_args=global_args)

        with open(results_path, encoding="utf-8") as f:
            results = f.read()

            assert "FAILED" not in results
            assert "SUCCESS" in results

        config("add", "variants:success_criteria_when:true", global_args=global_args)

        ws._re_read()
        with ramble.config.override("config:overwrite_inventories", True):
            workspace("analyze", global_args=global_args)

        with open(results_path, encoding="utf-8") as f:
            results = f.read()

            assert "FAILED" in results
            assert "SUCCESS" not in results


def test_register_template_when(workspace_name):
    global_args = ["-w", workspace_name]

    test_template = """
echo "test template for {experiment_name}"
"""

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        ws.write()

        template_src_path = os.path.join(ws.shared_dir, "test_template.tpl")
        template_dest_path = os.path.join(
            ws.experiment_dir, "when-directives", "test_wl", "generated", "test_template"
        )

        workspace("setup", global_args=global_args)

        with open(template_src_path, "w+", encoding="utf-8") as f:
            f.write(test_template)

        workspace("setup", global_args=global_args)

        assert not os.path.exists(template_dest_path)

        config("add", "variants:register_template_when:true", global_args=global_args)

        ws._re_read()
        workspace("setup", global_args=global_args)

        assert os.path.exists(template_dest_path)

        with open(template_dest_path, encoding="utf-8") as f:
            generated_template = f.read()

            assert "test template for generated" in generated_template


@pytest.mark.parametrize(
    "include_builtin,builtin_found",
    [
        (True, True),
        (False, False),
    ],
)
def test_register_builtin_when(workspace_name, include_builtin, builtin_found):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", f"variants:register_builtin_when:{include_builtin}", global_args=global_args)

        test_str = 'echo "when-builtin"'

        ws._re_read()
        workspace("setup", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-directives",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            assert (test_str in data) == builtin_found


@pytest.mark.parametrize(
    "archive_variant_on,expected_pattern,unexpected_pattern",
    [
        (False, "archive_test_pattern_when_false.txt", "archive_test_pattern_when_true.txt"),
        (True, "archive_test_pattern_when_true.txt", "archive_test_pattern_when_false.txt"),
    ],
)
def test_archive_pattern_when(
    workspace_name,
    archive_variant_on,
    expected_pattern,
    unexpected_pattern,
    mutable_mock_mods_repo,
    mutable_mock_pkg_mans_repo,
):
    import os

    import ramble.workspace

    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "exec_when_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=when-package-manager",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config(
            "add",
            f"variants:archive_pattern_when:{str(archive_variant_on).lower()}",
            global_args=global_args,
        )

        workspace(
            "manage",
            "modifiers",
            "--add",
            "--name",
            "when-modifier",
            "-s",
            "workspace",
            "--on-executable",
            "*",
            global_args=global_args,
        )

        workspace("setup", "--dry-run", global_args=global_args)

        # Write dummy files to the experiment directory to be archived
        ws._re_read()
        experiment_set = ws.build_experiment_set()

        import ramble.filters

        expected_patterns = [expected_pattern]
        unexpected_patterns = [unexpected_pattern]
        for pattern_variation in ["when_mod", "when_pm"]:
            expected_patterns.append(expected_pattern.replace("when", pattern_variation))
            unexpected_patterns.append(unexpected_pattern.replace("when", pattern_variation))

        filters = ramble.filters.Filters()
        for _, app_inst, _ in experiment_set.filtered_experiments(filters):
            exp_dir = app_inst.expander.expand_var("{experiment_run_dir}")
            os.makedirs(exp_dir, exist_ok=True)

            # Write expected patterns
            for pat in expected_patterns:
                with open(os.path.join(exp_dir, pat), "w", encoding="utf-8") as f:
                    f.write("Expected")
            for pat in unexpected_patterns:
                with open(os.path.join(exp_dir, pat), "w", encoding="utf-8") as f:
                    f.write("Unexpected")

        # Run the archive pipeline
        workspace("archive", "--archive-pattern", "archive_test_pattern*", global_args=global_args)

        # Run the experiment-logs pipeline to cover LogsPipeline logic
        workspace("experiment-logs", global_args=global_args)

        archive_dir = ws.latest_archive_path

        # Verify the expected pattern is copied to the archive for the experiment
        for _exp, app_inst, _ in experiment_set.filtered_experiments(filters):
            exp_dir = app_inst.expander.expand_var("{experiment_run_dir}")

            for pat in expected_patterns:
                expected_archive_path = os.path.join(exp_dir.replace(ws.root, archive_dir), pat)
                assert os.path.exists(expected_archive_path)

            for pat in unexpected_patterns:
                unexpected_archive_path = os.path.join(exp_dir.replace(ws.root, archive_dir), pat)
                assert not os.path.exists(unexpected_archive_path)


@pytest.mark.parametrize(
    "exec_variant_on,exec_ver2_found,skipped_exec_found",
    [
        (False, False, False),
        (True, True, True),
    ],
)
def test_executable_when(workspace_name, exec_variant_on, exec_ver2_found, skipped_exec_found):
    global_args = ["-w", workspace_name]

    test_var = "when-executable-test"

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "exec_when_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-v",
            f"test_variable={test_var}",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", f"variants:executable_when:{exec_variant_on}", global_args=global_args)

        test_ver1_str = "echo 'executable version1'"
        test_ver2_str = "echo 'executable version2'"
        test_skipped_exec_str = "echo 'skipped-executable'"

        ws._re_read()
        workspace("setup", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-directives",
            "exec_when_wl",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            print(data)

            assert test_var in data
            assert (test_ver1_str in data) != exec_ver2_found
            assert (test_ver2_str in data) == exec_ver2_found
            assert (test_skipped_exec_str in data) == skipped_exec_found


def test_executable_errors_when_overlapping_conditions(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "exec_when_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", "variants:executable_error_when:true", global_args=global_args)

        ws._re_read()

        with pytest.raises(RambleCommandError):

            captured = workspace("setup", global_args=global_args)
            assert "test_exec_def_when is defined for overlapping `when` conditions" in captured


@pytest.mark.parametrize(
    "input_when,expected_input_file",
    [
        (False, "input1_false"),
        (True, "input1_true"),
    ],
)
def test_input_when(workspace_name, input_when, expected_input_file):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_inputs_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", f"variants:input_when:{input_when}", global_args=global_args)

        ws._re_read()
        workspace("setup", "--dry-run", global_args=global_args)

        log_file = os.path.join(
            ws.path,
            "logs",
            "setup.latest.out",
        )

        with open(log_file, encoding="utf-8") as f:
            data = f.read()

            assert expected_input_file in data
            assert ("input2" in data) == input_when


@pytest.mark.parametrize(
    "wl_def_when,expected_exec",
    [
        (False, "test_exec"),
        (True, "test_exec_def_when"),
    ],
)
def test_workload_definition_when(workspace_name, wl_def_when, expected_exec):
    global_args = ["-w", workspace_name]

    exec_test_str = {
        "test_exec": "echo '{test_variable}'",
        "test_exec_def_when": "echo 'executable version1'",
    }

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_workload_definition_when",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", f"variants:workload_definition_when:{wl_def_when}", global_args=global_args)

        ws._re_read()
        workspace("setup", "--dry-run", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-directives",
            "test_workload_definition_when",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            assert exec_test_str[expected_exec] in data


def test_workload_errors_when_not_enabled(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        config("add", "variants:workload_enabled_when:true", global_args=global_args)

        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_workload_enabled_when",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", "variants:workload_enabled_when:false", global_args=global_args)

        ws._re_read()

        with pytest.raises(RambleCommandError):

            captured = workspace("setup", global_args=global_args)
            assert (
                "test_workload_enabled_when is not defined for the active `when` conditions"
            ) in captured

        config("remove", "variants:workload_enabled_when:false", global_args=global_args)
        config("add", "variants:workload_enabled_when:true", global_args=global_args)

        ws._re_read()
        workspace("setup", "--dry-run", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-directives",
            "test_workload_enabled_when",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            assert "echo '{test_variable}'" in data


def test_workload_errors_when_overlapping_conditions(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", "variants:workload_defined_twice:true", global_args=global_args)

        ws._re_read()

        with pytest.raises(RambleCommandError):

            captured = workspace("setup", global_args=global_args)
            assert "test_wl is defined for overlapping `when` conditions" in captured


@pytest.mark.parametrize(
    "active_variant,active_workload,disabled_variant,disabled_workload",
    [
        ("group1", "test_wl2", "group2", "test_wl3"),
        ("group2", "test_wl3", "group1", "test_wl2"),
    ],
)
def test_workload_group_when(
    workspace_name, active_variant, active_workload, disabled_variant, disabled_workload
):
    global_args = ["-w", workspace_name]

    expected_commands = {
        "group1_test_wl": [
            "echo 'Test'",
            "export APP_ENV_VAR2=TEST_WL2_ENV_VAR",
        ],
        "group1_test_wl2": [
            "echo 'Var2'",
            "export APP_ENV_VAR2=TEST_WL2_ENV_VAR",
        ],
        "group2_test_wl": [
            "echo 'Test'",
            "export APP_ENV_VAR3=TEST_WL3_ENV_VAR",
        ],
        "group2_test_wl3": [
            "echo 'Var3'",
            "export APP_ENV_VAR3=TEST_WL3_ENV_VAR",
        ],
    }

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        config("add", f"variants:workload_group_options:{active_variant}", global_args=global_args)

        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            f"{active_workload}",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        ws._re_read()

        workspace("setup", "--dry-run", global_args=global_args)

        base_wl_exec_file = os.path.join(
            ws.experiment_dir, "when-directives", "test_wl", "generated", "execute_experiment"
        )

        active_wl_exec_file = os.path.join(
            ws.experiment_dir,
            "when-directives",
            f"{active_workload}",
            "generated",
            "execute_experiment",
        )

        disabled_wl_exec_file = os.path.join(
            ws.experiment_dir,
            "when-directives",
            f"{disabled_workload}",
            "generated",
            "execute_experiment",
        )

        with open(base_wl_exec_file, encoding="utf-8") as f:
            base_script = f.read()

            for cmd in expected_commands[f"{active_variant}_test_wl"]:
                assert cmd in base_script

            assert expected_commands[f"{disabled_variant}_test_wl"][1] not in base_script

            for cmd in expected_commands[f"{disabled_variant}_{disabled_workload}"]:
                assert cmd not in base_script

        with open(active_wl_exec_file, encoding="utf-8") as f:
            active_script = f.read()

            for cmd in expected_commands[f"{active_variant}_{active_workload}"]:
                assert cmd in active_script

            for cmd in expected_commands[f"{disabled_variant}_{disabled_workload}"]:
                assert cmd not in active_script

        assert not os.path.exists(disabled_wl_exec_file)


@pytest.mark.parametrize("obj", ["app", "mod", "wf_man", "pkg_man"])
def test_obj_env_var_when(workspace_name, obj, mutable_mock_wms_repo, mutable_mock_pkg_mans_repo):
    global_args = ["-w", workspace_name]

    exec_test_str = {
        "app": "export APP_ENV_VAR=APP_ENV_VAR_SET;",
        "mod": "export MOD_ENV_VAR=MOD_ENV_VAR_SET;",
        "wf_man": "export WORKFLOW_ENV_VAR=WF_ENV_VAR_SET;",
        "pkg_man": "export PACKAGE_ENV_VAR=PKG_ENV_VAR_SET;",
    }

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
        args = [
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=when-package-manager",
            "-V",
            "workflow_manager=when-workflow-manager",
            "--default-variable-value",
            "1",
        ]

        if obj == "app":
            config("add", "variants:app_env_var_included:true", global_args=global_args)
        elif obj == "mod":
            mod_config_path = os.path.join(ws.config_dir, "modifiers.yaml")
            with open(mod_config_path, "w+", encoding="utf-8") as f:
                f.write("modifiers:\n")
                f.write(" - name: when-modifier\n")
            config("add", "variants:mod_env_var_included:true", global_args=global_args)
        elif obj == "wf_man":
            config("add", "variants:workflow_manager_included:true", global_args=global_args)
            config(
                "add",
                "variants:workflow_manager_env_var_included:true",
                global_args=global_args,
            )
        elif obj == "pkg_man":
            config("add", "variants:package_manager_included:true", global_args=global_args)
            config(
                "add",
                "variants:package_manager_env_var_included:true",
                global_args=global_args,
            )

        workspace("manage", "experiments", *args, global_args=global_args)
        workspace("setup", "--dry-run", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-directives",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            for obj_under_test, test_str in exec_test_str.items():
                assert (test_str in data) == (obj_under_test == obj)


@pytest.mark.parametrize(
    "env_var_mod_when,expected_exec",
    [
        (False, False),
        (True, True),
    ],
)
def test_env_var_modification_when(workspace_name, env_var_mod_when, expected_exec):
    global_args = ["-w", workspace_name]

    exec_test_str = "export APP_ENV_VAR=APP_ENV_VAR_MODIFIED;"

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        mod_config_path = os.path.join(ws.config_dir, "modifiers.yaml")
        with open(mod_config_path, "w+", encoding="utf-8") as f:
            f.write("modifiers:\n")
            f.write(" - name: when-modifier\n")

        config(
            "add",
            f"variants:env_var_modification_active:{env_var_mod_when}",
            global_args=global_args,
        )

        ws._re_read()
        workspace("setup", "--dry-run", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-directives",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            assert (exec_test_str in data) == expected_exec


@pytest.mark.parametrize(
    "exec_mod_when,expected_exec",
    [
        (False, False),
        (True, True),
    ],
)
def test_executable_modification_when(workspace_name, exec_mod_when, expected_exec):
    global_args = ["-w", workspace_name]

    exec_test_str = "echo 'append executable'"

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        mod_config_path = os.path.join(ws.config_dir, "modifiers.yaml")
        with open(mod_config_path, "w+", encoding="utf-8") as f:
            f.write("modifiers:\n")
            f.write(" - name: when-modifier\n")

        config(
            "add",
            f"variants:exec_modifier_active:{exec_mod_when}",
            global_args=global_args,
        )

        ws._re_read()
        workspace("setup", "--dry-run", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-directives",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            assert (exec_test_str in data) == expected_exec


@pytest.mark.parametrize(
    "var_mod_when,modifier_mode,expected_exec",
    [
        (False, "standard", False),
        (True, "standard", False),
        (False, "test", False),
        (True, "test", True),
    ],
)
def test_variable_modification_when(workspace_name, var_mod_when, modifier_mode, expected_exec):
    global_args = ["-w", workspace_name]

    exec_original_str = "echo 'Test'"
    exec_test_str = "echo 'test var modified'"

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        mod_config_path = os.path.join(ws.config_dir, "modifiers.yaml")
        with open(mod_config_path, "w+", encoding="utf-8") as f:
            f.write("modifiers:\n")
            f.write(" - name: when-modifier\n")
            f.write(f"   mode: {modifier_mode}\n")

        config(
            "add",
            f"variants:variable_modification_active:{var_mod_when}",
            global_args=global_args,
        )

        ws._re_read()
        workspace("setup", "--dry-run", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-directives",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        with open(exec_file, encoding="utf-8") as f:
            data = f.read()

            assert (exec_original_str in data) != expected_exec
            assert (exec_test_str in data) == expected_exec


@pytest.mark.long
def test_package_manager_requirement_when(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=spack",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        mod_config_path = os.path.join(ws.config_dir, "modifiers.yaml")
        with open(mod_config_path, "w+", encoding="utf-8") as f:
            f.write("modifiers:\n")
            f.write(" - name: when-modifier\n")

        ws._re_read()
        workspace("setup", global_args=global_args)

        config(
            "add",
            "variants:pkg_man_reqt_fails_when_enabled:true",
            global_args=global_args,
        )

        ws._re_read()
        with pytest.raises(
            ValidationFailedError, match='Validation of: "spack list not-a-package" failed'
        ):
            workspace("setup", global_args=global_args)


@pytest.mark.parametrize("obj", ["app", "mod", "wf_man", "pkg_man"])
def test_obj_required_var_when(
    workspace_name, obj, mutable_mock_wms_repo, mutable_mock_pkg_mans_repo
):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
        args = [
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=when-package-manager",
            "-V",
            "workflow_manager=when-workflow-manager",
            "--default-variable-value",
            "1",
        ]

        if obj == "mod":
            mod_config_path = os.path.join(ws.config_dir, "modifiers.yaml")
            with open(mod_config_path, "w+", encoding="utf-8") as f:
                f.write("modifiers:\n")
                f.write(" - name: when-modifier\n")
                f.write("   mode: test")
        elif obj == "wf_man":
            config("add", "variants:workflow_manager_included:true", global_args=global_args)
        elif obj == "pkg_man":
            config("add", "variants:package_manager_included:true", global_args=global_args)

        workspace("manage", "experiments", *args, global_args=global_args)
        config("add", f"variants:{obj}_required_variable:true", global_args=global_args)

        with pytest.raises(ramble.experiment_set.RambleVariableDefinitionError):
            workspace("setup", "--dry-run", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-directives",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        assert not os.path.exists(exec_file)

        config("add", f"variables:test_{obj}_required_variable:'test'", global_args=global_args)

        ws._re_read()
        workspace("setup", "--dry-run", global_args=global_args)

        assert os.path.exists(exec_file)


@pytest.mark.parametrize("obj", ["app", "mod", "wf_man", "pkg_man"])
def test_obj_required_key_when(
    workspace_name, obj, mutable_mock_wms_repo, mutable_mock_pkg_mans_repo
):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
        args = [
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "-V",
            "package_manager=when-package-manager",
            "-V",
            "workflow_manager=when-workflow-manager",
            "--default-variable-value",
            "1",
        ]

        if obj == "mod":
            mod_config_path = os.path.join(ws.config_dir, "modifiers.yaml")
            with open(mod_config_path, "w+", encoding="utf-8") as f:
                f.write("modifiers:\n")
                f.write(" - name: when-modifier\n")
                f.write("   mode: test")
        elif obj == "wf_man":
            config("add", "variants:workflow_manager_included:true", global_args=global_args)
        elif obj == "pkg_man":
            config("add", "variants:package_manager_included:true", global_args=global_args)

        workspace("manage", "experiments", *args, global_args=global_args)
        config("add", f"variants:{obj}_required_key:true", global_args=global_args)

        with pytest.raises(ramble.experiment_set.RambleVariableDefinitionError):
            workspace("setup", "--dry-run", global_args=global_args)

        exec_file = os.path.join(
            ws.experiment_dir,
            "when-directives",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        assert not os.path.exists(exec_file)

        config("add", f"variables:test_{obj}_required_key:'test'", global_args=global_args)

        ws._re_read()
        workspace("setup", "--dry-run", global_args=global_args)

        assert os.path.exists(exec_file)

        workspace("analyze", "-f", "json", global_args=global_args)

        results_file = os.path.join(ws.results_dir, "results.latest.json")

        assert os.path.exists(results_file)

        with open(results_file, encoding="utf-8") as f:
            data = json.load(f)

        for exp in data["experiments"]:
            assert f"test_{obj}_required_key" in exp


@pytest.mark.parametrize(
    "variant_name",
    [
        "bad_spec",
        "bad_when",
    ],
)
def test_object_conflicts_expander_errors(workspace_name, variant_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "object-conflicts",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            global_args=global_args,
        )

        config("add", f"variants:{variant_name}:True", global_args=global_args)

        ws._re_read()
        workspace("setup", global_args=global_args)


def test_object_conflicts_no_msg(workspace_name):
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "object-conflicts",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            global_args=global_args,
        )

        config("add", "variants:nomsg:True", global_args=global_args)

        ws._re_read()
        with pytest.raises(
            ObjectValidationError,
            match=r"Conflict detected in 'object-conflicts': '\+nomsg' is active when \+nomsg",
        ):
            workspace("setup", global_args=global_args)


def test_object_conflicts_warn_only(workspace_name):
    from unittest.mock import patch

    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "object-conflicts",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            global_args=global_args,
        )

        config("add", "variants:nomsg:True", global_args=global_args)

        ws._re_read()
        with patch("ramble.util.logger.logger.warn") as mock_warn:
            ws.build_experiment_set(die_on_validate_error=False)
            mock_warn.assert_any_call(
                "Conflict detected in 'object-conflicts': '+nomsg' is active when +nomsg"
            )


def test_workload_group_variant_in_when_directive(workspace_name):
    ws_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name) as ws:
        workspace(
            "manage",
            "experiments",
            "when-directives",
            "--wf",
            "test_wl",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=ws_args,
        )

        workspace("setup", "--dry-run", global_args=ws_args)

        script = os.path.join(
            ws.experiment_dir,
            "when-directives",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        with open(script, encoding="utf-8") as f:
            content = f.read()
            assert "export GROUP_VARIANT_ENV_VAR=TEST_WL_GROUP_SET" in content

        # Change active work_group
        config("add", "variants:workload_group_options:group2", global_args=ws_args)
        workspace("setup", "--dry-run", global_args=ws_args)

        script = os.path.join(
            ws.experiment_dir,
            "when-directives",
            "test_wl",
            "generated",
            "execute_experiment",
        )

        with open(script, encoding="utf-8") as f:
            content = f.read()
            assert "GROUP_VARIANT_ENV_VAR" not in content
