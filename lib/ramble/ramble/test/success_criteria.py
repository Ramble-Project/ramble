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


def test_success_criteria_context_variables():
    from unittest.mock import MagicMock

    app_inst = MagicMock()

    def evaluate_predicate(expr, extra_vars=None):
        res = expr
        if extra_vars:
            for k, v in extra_vars.items():
                res = res.replace(f"{{{k}}}", str(v))
        # Simple evaluation of predicate expression for testing
        return bool(eval(res, {"__builtins__": {}}, {}))

    app_inst.expander.expand_var.side_effect = lambda x, **kwargs: x
    app_inst.expander.evaluate_predicate.side_effect = evaluate_predicate

    # Mock standard context_key (tuple of length 3 with frozenset of vars)
    context_vars = frozenset([("N", 276480), ("NB", 384), ("P", 12), ("Q", 16)])
    context_key = ("N-NB-P-Q = 276480-384-12-16", "problem-name", context_vars)

    fom_values = {
        context_key: {
            "GFlops": {"value": 15400.0},
        }
    }

    # 1. Test formula using both context variable {N} and FOM {value}
    crit = ramble.success_criteria.SuccessCriteria(
        name="test_context_var_pass",
        mode="fom_comparison",
        fom_context="N-NB-P-Q =*",
        fom_name="GFlops",
        formula="{N} == 276480 and {value} > 12000",
    )
    assert crit.passed(app_inst=app_inst, fom_values=fom_values)

    # 2. Test unsatisfied condition ({N} != 1000) should fail
    crit_fail = ramble.success_criteria.SuccessCriteria(
        name="test_context_var_fail",
        mode="fom_comparison",
        fom_context="N-NB-P-Q =*",
        fom_name="GFlops",
        formula="{N} == 1000 and {value} > 12000",
    )
    assert not crit_fail.passed(app_inst=app_inst, fom_values=fom_values)

    # 3. Test string-to-numeric casting for regex captured groups
    str_context_vars = frozenset([("N", "276480"), ("ratio", "1.5"), ("tag", "fast")])
    str_context_key = ("str-ctx", "def", str_context_vars)
    str_fom_values = {
        str_context_key: {
            "GFlops": {"value": 15400.0},
        }
    }
    crit_str_cast = ramble.success_criteria.SuccessCriteria(
        name="test_str_cast",
        mode="fom_comparison",
        fom_context="str-ctx",
        fom_name="GFlops",
        formula="{N} > 200000 and {ratio} > 1.0 and '{tag}' == 'fast' and {value} > 12000",
    )
    assert crit_str_cast.passed(app_inst=app_inst, fom_values=str_fom_values)

    # 4. Test edge case: ensure context variable named 'value' does not overwrite FOM value
    colliding_vars = frozenset([("value", 999), ("N", 276480)])
    colliding_context_key = ("colliding-ctx", "def", colliding_vars)
    colliding_fom_values = {
        colliding_context_key: {
            "GFlops": {"value": 15400.0},
        }
    }
    crit_collision = ramble.success_criteria.SuccessCriteria(
        name="test_collision",
        mode="fom_comparison",
        fom_context="colliding-ctx",
        fom_name="GFlops",
        formula="{value} == 15400.0 and {N} == 276480",
    )
    assert crit_collision.passed(app_inst=app_inst, fom_values=colliding_fom_values)

    # 5. Test short/malformed context_key (length < 3 or non-tuple) handles safely
    short_context_key = ("short-ctx", "def")
    short_fom_values = {
        short_context_key: {
            "GFlops": {"value": 15400.0},
        }
    }
    crit_short = ramble.success_criteria.SuccessCriteria(
        name="test_short_ctx",
        mode="fom_comparison",
        fom_context="short-ctx",
        fom_name="GFlops",
        formula="{value} > 12000",
    )
    assert crit_short.passed(app_inst=app_inst, fom_values=short_fom_values)
