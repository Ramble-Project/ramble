# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import ramble.success_criteria


def generate_file(path):
    file_contents = """
Some output
Into a log file
From
An
Experiment
Success string
Or maybe an exit code: 0
    """

    with open(path, "w+", encoding="utf-8") as f:
        f.write(file_contents)


def remark_all(crit_list, file_path):
    for c in crit_list:
        c.reset()

    with open(file_path, encoding="utf-8") as f:
        for line in f:
            for c in crit_list:
                if c.passed(line):
                    c.mark_found()
                if c.anti_matched(line):
                    c.mark_anti_found()


def test_single_criteria(tmpdir):
    log_path = tmpdir.join("log.out")
    generate_file(log_path)

    new_criteria = ramble.success_criteria.SuccessCriteria(
        "test", "string", r".*Success string.*", log_path
    )

    remark_all([new_criteria], log_path)

    assert new_criteria.ok()

    anti_criteria = ramble.success_criteria.SuccessCriteria(
        name="test-anti", mode="string", file=log_path, anti_match=r"Or maybe"
    )

    remark_all([anti_criteria], log_path)

    assert not anti_criteria.ok()


def test_criteria_list(tmpdir):
    log_path = tmpdir.join("log.out")
    generate_file(log_path)

    criteria_list = ramble.success_criteria.ScopedCriteriaList()

    criteria_list.add_criteria(
        "object_definitions",
        "test-success",
        "string",
        r".*Success string.*",
        log_path,
    )

    criteria_list.add_criteria("experiment", "test-exp", "string", r".*Experiment.*", log_path)

    remark_all([criteria for criteria, _ in criteria_list.all_criteria()], log_path)

    assert criteria_list.passed()

    criteria_list.add_criteria(
        scope="object_definitions",
        name="test-anti",
        mode="string",
        file=log_path,
        anti_match=r"From",
    )

    remark_all([criteria for criteria, _ in criteria_list.all_criteria()], log_path)

    assert not criteria_list.passed()


def test_success_criteria_globbing():
    from unittest.mock import MagicMock

    # Mock application instance and its expander
    app_inst = MagicMock()

    def expand_var(var, extra_vars=None):
        res = var
        if extra_vars:
            for k, v in extra_vars.items():
                res = res.replace(f"{{{k}}}", str(v))
        return res

    app_inst.expander.expand_var.side_effect = expand_var

    def evaluate_predicate(expr, extra_vars=None):
        expanded = expand_var(expr, extra_vars)
        # Handle simple > comparison for test
        if " > " in expanded:
            parts = expanded.split(" > ")
            return float(parts[0]) > float(parts[1])
        return True

    app_inst.expander.evaluate_predicate.side_effect = evaluate_predicate

    # Mock fom_values
    fom_values = {
        ("ctx-1", "null"): {
            "Bandwidth": {"value": 150},
            "Latency": {"value": 10},
        },
        ("ctx-2", "null"): {
            "Bandwidth": {"value": 250},
            "Latency": {"value": 5},
        },
        ("other-ctx", "null"): {
            "Bandwidth": {"value": 50},
        },
    }

    # Test globbing on context
    crit1 = ramble.success_criteria.SuccessCriteria(
        name="check_bw",
        mode="fom_comparison",
        fom_context="ctx-*",
        fom_name="Bandwidth",
        formula="{value} > 100",
    )

    # Both ctx-1 and ctx-2 have BW > 100
    assert crit1.passed(app_inst=app_inst, fom_values=fom_values)

    # Test globbing on FOM name
    crit2 = ramble.success_criteria.SuccessCriteria(
        name="check_all_ctx1",
        mode="fom_comparison",
        fom_context="ctx-1",
        fom_name="*",
        formula="{value} > 5",
    )
    # Both Bandwidth (150) and Latency (10) in ctx-1 are > 5
    assert crit2.passed(app_inst=app_inst, fom_values=fom_values)

    # Test failing globbing
    crit3 = ramble.success_criteria.SuccessCriteria(
        name="check_all_bw",
        mode="fom_comparison",
        fom_context="*",
        fom_name="Bandwidth",
        formula="{value} > 100",
    )
    # other-ctx has Bandwidth = 50, which is not > 100
    assert not crit3.passed(app_inst=app_inst, fom_values=fom_values)

    # Test no matches
    crit4 = ramble.success_criteria.SuccessCriteria(
        name="no_match",
        mode="fom_comparison",
        fom_context="non-existent",
        fom_name="*",
        formula="{value} > 0",
    )
    assert not crit4.passed(app_inst=app_inst, fom_values=fom_values)


def test_success_criteria_constant_values():
    """Mode, scope, and result values are user-facing and must remain stable."""
    from ramble.success_criteria import (
        ScopedCriteriaList,
        SuccessCriteria,
        SuccessCriteriaMode,
        SuccessCriteriaResult,
        SuccessCriteriaScope,
    )

    # Modes are used in the success_criteria directive and workspace configs
    assert SuccessCriteriaMode.STRING == "string"
    assert SuccessCriteriaMode.APPLICATION_FUNCTION == "application_function"
    assert SuccessCriteriaMode.FOM_COMPARISON == "fom_comparison"
    assert set(SuccessCriteria._valid_modes) == {
        "string",
        "application_function",
        "fom_comparison",
    }

    # Scopes appear in reported criteria names (config::<scope>::<name>)
    assert SuccessCriteriaScope.OBJECT_DEFINITIONS == "object_definitions"
    assert SuccessCriteriaScope.EXPERIMENT == "experiment"
    assert set(ScopedCriteriaList._valid_scopes) == {"object_definitions", "experiment"}

    # Results are written to results files
    assert SuccessCriteriaResult.PASSED == "PASSED"
    assert SuccessCriteriaResult.FAILED == "FAILED"


def test_success_criteria_fom_context_variable_expansion():
    from unittest.mock import MagicMock

    app_inst = MagicMock()
    exp_vars = {"Ns": 2000, "NBs": 384, "Ps": 12, "Qs": 16}

    def expand_var(var, extra_vars=None):
        res = var
        all_vars = dict(exp_vars)
        if extra_vars:
            all_vars.update(extra_vars)
        for k, v in all_vars.items():
            res = res.replace(f"{{{k}}}", str(v))
        return res

    app_inst.expander.expand_var.side_effect = expand_var

    def evaluate_predicate(expr, extra_vars=None):
        expanded = expand_var(expr, extra_vars)
        if " > " in expanded:
            parts = expanded.split(" > ")
            return float(parts[0]) > float(parts[1])
        return True

    app_inst.expander.evaluate_predicate.side_effect = evaluate_predicate

    fom_values = {
        ("N-NB-P-Q = 1000-384-12-16", "problem-name"): {
            "GFlops": {"value": 100.0},
        },
        ("N-NB-P-Q = 2000-384-12-16", "problem-name"): {
            "GFlops": {"value": 250.0},
        },
    }

    # Variable expansion in fom_context targets the matching context (Ns=2000)
    crit_pass = ramble.success_criteria.SuccessCriteria(
        name="hpl_target_pass",
        mode="fom_comparison",
        fom_context="N-NB-P-Q = {Ns}-{NBs}-{Ps}-{Qs}",
        fom_name="GFlops",
        formula="{value} > 200.0",
    )
    assert crit_pass.passed(app_inst=app_inst, fom_values=fom_values)

    # Fails when the targeted context does not meet the formula threshold
    crit_fail = ramble.success_criteria.SuccessCriteria(
        name="hpl_target_fail",
        mode="fom_comparison",
        fom_context="N-NB-P-Q = {Ns}-{NBs}-{Ps}-{Qs}",
        fom_name="GFlops",
        formula="{value} > 300.0",
    )
    assert not crit_fail.passed(app_inst=app_inst, fom_values=fom_values)

    # Fails when expanded fom_context does not match any recorded context
    exp_vars["Ns"] = "1000 2000"
    crit_no_match = ramble.success_criteria.SuccessCriteria(
        name="hpl_no_match",
        mode="fom_comparison",
        fom_context="N-NB-P-Q = {Ns}-{NBs}-{Ps}-{Qs}",
        fom_name="GFlops",
        formula="{value} > 0",
    )
    assert not crit_no_match.passed(app_inst=app_inst, fom_values=fom_values)
