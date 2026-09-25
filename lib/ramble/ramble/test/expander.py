# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.expander
import ramble.variants


def exp_dict():
    return {
        "application_name": "foo",
        "application_spec": "foo@1.2",
        "workload_name": "bar",
        "experiment_name": "baz",
        "application_input_dir": "/workspace/inputs/foo",
        "workload_input_dir": "/workspace/inputs/foo/bar",
        "application_run_dir": "/workspace/experiments/foo",
        "workload_run_dir": "/workspace/experiments/foo/bar",
        "experiment_run_dir": "/workspace/experiments/foo/bar/baz",
        "env_name": "spack_foo.bar",
        "n_ranks": "4",
        "processes_per_node": "2",
        "n_nodes": "2",
        "cores_per_node": "16",
        "n_threads": "4",
        "var1": "{var2}",
        "var2": "{var3}",
        "var3": "3",
        "decimal.06.var": "foo",
        "size": '"0000.96"',  # Escaped as a string
        "test_mask": '"0x0"',
        "max_len": 9,
        "test_dict": {"test_key1": "test_val1", "test_key2": "test_val2"},
        "experiment_index": 5,
        "var4": "a-b",
        "test::var": "value",
    }


def build_variant_set():
    variant_set = ramble.variants.VariantSet()

    variants = {
        "test_variant": "defined",
        "package_manager": "spack",
        "workflow_manager": "slurm",
        "compiler": "gcc@14.2.0",
        "bool_true": True,
        "bool_false": False,
    }

    multi_value_variants = [
        ("package_manager_family", "spack"),
        ("workflow_manager_family", "slurm"),
    ]

    for name, value in variants.items():
        variant_set.default_variant(name, value)

    for name, value in multi_value_variants:
        variant_set.multi_value_variant(name, value)

    return variant_set


@pytest.mark.parametrize(
    "input,output,no_expand_vars,passes",
    [
        ("{var1}", "3", set(), 1),
        ("{var2}", "3", set(), 1),
        ("{var3}", "3", set(), 1),
        ("{application_name}", "foo", set(), 1),
        ("{n_nodes}", "2", set(), 1),
        ("{processes_per_node}", "2", set(), 1),
        ("{n_nodes}*{processes_per_node}", "4", set(), 1),
        ("2**4", "16", set(), 1),
        ("{((((16-10+2)/4)**2)*4)}", "16.0", set(), 1),
        ("gromacs +blas", "gromacs +blas", set(), 1),
        ("range(0, 5)", "[0, 1, 2, 3, 4]", set(), 1),
        ("{decimal.06.var}", "foo", set(), 1),
        ("{}", "{}", set(), 1),
        ("{{n_ranks}+2}", "6", set(), 1),
        ("{{n_ranks}*{var{processes_per_node}}:05d}", "00012", set(), 1),
        ("{{n_ranks}-1}", "3", set(), 1),
        ("{{{n_ranks}/2}:0.0f}", "2", set(), 1),
        ("{size}", "0000.96", {"size"}, 1),
        ("CPU(s)", "CPU(s)", set(), 1),
        ("str(1.5)", "1.5", set(), 1),
        ("int(1.5)", "1", set(), 1),
        ("float(1.5)", "1.5", set(), 1),
        ("ceil(0.6)", "1", set(), 1),
        ("floor(0.6)", "0", set(), 1),
        ("max(1, 5)", "5", set(), 1),
        ("min(1, 5)", "1", set(), 1),
        ('simplify_str("a.b_c")', "a-b-c", set(), 1),
        (r"\{experiment_name\}", "{experiment_name}", set(), 1),
        (r"\{experiment_name\}", "baz", set(), 2),
        (r"{\{experiment_name\}}", "{{experiment_name}}", set(), 1),
        (r"\\{experiment_name\\}", r"\{experiment_name\}", set(), 1),
        (r"\\{experiment_name\\}", "{experiment_name}", set(), 2),
        (r"\\{experiment_name\\}", "baz", set(), 3),
        ('"2.1.1" in ["2.1.1", "3.1.1", "4.2.1"]', "True", set(), 1),
        ('"2.1.2" in ["2.1.1", "3.1.1", "4.2.1"]', "False", set(), 1),
        ('"3.1.2" not in ["2.1.1", "3.1.1", "4.2.1"]', "True", set(), 1),
        ('"2.1.1" not in ["2.1.1", "3.1.1", "4.2.1"]', "False", set(), 1),
        ("{test_mask}", "0x0", {"test_mask"}, 1),
        ('re_search(r"bz$", {experiment_name})', "False", set(), 1),
        ('re_search("o+\\\\.b", {env_name})', "True", set(), 1),
        ('"foo" in "{env_name}"', "True", set(), 1),
        ('"c" in "{experiment_name}"', "False", set(), 1),
        ('"foo123" not in "{env_name}"', "True", set(), 1),
        ('"foo" not in "{env_name}"', "False", set(), 1),
        ('"{env_name}"[:{max_len}:1]', "spack_foo", set(), 1),
        ("not_a_slice[0]", "not_a_slice[0]", set(), 1),
        ("not_a_valid_slice[0:a]", "not_a_valid_slice[0:a]", set(), 1),
        ("{test_dict}", "{'test_key1': 'test_val1', 'test_key2': 'test_val2'}", set(), 1),
        ("{test_dict['test_key1']}", "test_val1", set(), 1),
        ("{test_dict['test_key2']}", "test_val2", set(), 1),
        ("{test_dict['missing_key']}", "{test_dict['missing_key']}", set(), 1),
        ("{test_dict[None]}", "{test_dict[None]}", set(), 1),
        ("maybe(env_name, foo)", "spack_foo.bar", set(), 1),
        ("maybe(not_a_var, foo)", "foo", set(), 1),
        ("maybe(not_a_var)", "", set(), 1),
        ("2.1.a", "2.1.a", set(), 1),
        ("{'key1':'val1'}", "{'key1':'val1'}", set(), 1),
        ("{'key1': 'val1'}", "{'key1': 'val1'}", set(), 1),
        ("{'key1': 'val1', 'key2': 'val2'}", "{'key1': 'val1', 'key2': 'val2'}", set(), 1),
        ("${job_id}", "${job_id}", set(), 1),
        ("${job_id:-}", "${job_id:-}", set(), 1),
        ("join_str(range(0, 5, 2), ': ')", "0: 2: 4", set(), 1),
        ("join_str(range(0, {cores_per_node}, {n_threads}))", "0,4,8,12", set(), 1),
        ('int("0b101110", 2)', "46", set(), 1),
        ("0b10 & 0b01", "0", set(), 1),
        ("0b10 | 0b01", "3", set(), 1),
        ("0b10 ^ 0b01", "3", set(), 1),
        ("~0", "-1", set(), 1),
        ("~2", "-3", set(), 1),
        ("0b10 << 1", "4", set(), 1),
        ("0b10 >> 1", "1", set(), 1),
        # Can be a handy way to select experiments to run
        ("(1 << {experiment_index} & 0b1011010) == 0", "True", set(), 1),
        ("$HOSTNAME", "$HOSTNAME", set(), 1),
        ("${HOSTNAME}", "${HOSTNAME}", set(), 1),
        ("log2(8)", "3.0", set(), 1),
        ("log10(100)", "2.0", set(), 1),
        ("sqrt(16)", "4.0", set(), 1),
        # Can also reference functions available in the math module directly
        ("math_sqrt(64)", "8.0", set(), 1),
        ("math_log(9, 3)", "2.0", set(), 1),
        ("math_not_exist(1)", "math_not_exist(1)", set(), 1),
        ("str_upper('foo')", "FOO", set(), 1),
        ("str_lower('FOO')", "foo", set(), 1),
        ("str_upper(foobar)", "FOOBAR", set(), 1),
        ("str_capitalize('foo')", "Foo", set(), 1),
        ("str_lstrip('AAAbbb', 'A')", "bbb", set(), 1),
        ("str_join('.', str_split('a b c 1'))", "a.b.c.1", set(), 1),
        ("str_no_such_method('a')", "str_no_such_method('a')", set(), 1),
        ("replace('abc', 'a', 'd')", "dbc", set(), 1),
        ("replace('{application_name}', 'f', 'F')", "Foo", set(), 1),
        ("str_upper({var4})", "A-B", set(), 1),
        ("{test::var}", "value", set(), 1),
        ("{n_ranks:05d}", "00004", set(), 1),
        ("1_01", "1_01", set(), 1),
        ("0x10", "0x10", set(), 1),
        ("{application_name}-1_01", "foo-1_01", set(), 1),
        ('not ("a" == "a")', "False", set(), 1),
        ('not ("a" == "b")', "True", set(), 1),
        ('not ("SETUP" == "SUCCESS")', "True", set(), 1),
        ('("SETUP" == "FAILED") and not ("SETUP" == "SUCCESS")', "False", set(), 1),
        ('("SETUP" == "SETUP") and not ("SETUP" == "SUCCESS")', "True", set(), 1),
    ],
)
def test_expansions(input, output, no_expand_vars, passes):
    expansion_vars = exp_dict()

    expander = ramble.expander.Expander(expansion_vars, None, no_expand_vars=no_expand_vars)

    step_input = input
    for _ in range(passes):
        step_input = expander.expand_var(step_input)
    final_output = step_input

    assert final_output == output


@pytest.mark.parametrize(
    "input,output,no_expand_vars,passes",
    [
        ("{var1}", 3, set(), 1),
        ("{var2}", 3, set(), 1),
        ("{var3}", 3, set(), 1),
        ("{application_name}", "foo", set(), 1),
        ("{n_nodes}", 2, set(), 1),
        ("{processes_per_node}", 2, set(), 1),
        ("{n_nodes}*{processes_per_node}", 4, set(), 1),
        ("2**4", 16, set(), 1),
        ("{((((16-10+2)/4)**2)*4)}", 16.0, set(), 1),
        ('"gromacs +blas"', "gromacs +blas", set(), 1),
        ("range(0, 5)", [0, 1, 2, 3, 4], set(), 1),
        ("{decimal.06.var}", "foo", set(), 1),
        ("{}", {}, set(), 1),
        ("{{n_ranks}+2}", 6, set(), 1),
        ("{{n_ranks}*{var{processes_per_node}}:05d}", "00012", set(), 1),
        ("{{n_ranks}-1}", 3, set(), 1),
        ("{{{n_ranks}/2}:0.0f}", 2, set(), 1),
        ("{size}", 0.96, {"size"}, 1),
        ("CPU(s)", "CPU(s)", set(), 1),
        ("str(1.5)", 1.5, set(), 1),
        ("int(1.5)", 1, set(), 1),
        ("float(1.5)", 1.5, set(), 1),
        ("ceil(0.6)", 1, set(), 1),
        ("floor(0.6)", 0, set(), 1),
        ("max(1, 5)", 5, set(), 1),
        ("min(1, 5)", 1, set(), 1),
        ('simplify_str("a.b_c")', "a-b-c", set(), 1),
        (r"\{experiment_name\}", "{experiment_name}", set(), 1),
        (r"\{experiment_name\}", "baz", set(), 2),
        (r"{\{experiment_name\}}", "{{experiment_name}}", set(), 1),
        (r"\\{experiment_name\\}", r"\{experiment_name\}", set(), 1),
        (r"\\{experiment_name\\}", "{experiment_name}", set(), 2),
        (r"\\{experiment_name\\}", "baz", set(), 3),
        ('"2.1.1" in ["2.1.1", "3.1.1", "4.2.1"]', True, set(), 1),
        ('"2.1.2" in ["2.1.1", "3.1.1", "4.2.1"]', False, set(), 1),
        ("{test_mask}", 0, {"test_mask"}, 1),
        ("{var3} // {processes_per_node}", 1, set(), 1),
        ("-5 % 3", 1, set(), 1),
        ("2 and 1", 1, set(), 1),
        ("2 or 1", 2, set(), 1),
        ("randrange(2, 3, 1)", 2, set(), 1),
        ("randint(3, 3)", 3, set(), 1),
        ("~0", -1, set(), 1),
        ("~2", -3, set(), 1),
        ('not ("a" == "a")', False, set(), 1),
        ('not ("a" == "b")', True, set(), 1),
        ('not ("SETUP" == "SUCCESS")', True, set(), 1),
        ('("SETUP" == "FAILED") and not ("SETUP" == "SUCCESS")', False, set(), 1),
        ('("SETUP" == "SETUP") and not ("SETUP" == "SUCCESS")', True, set(), 1),
    ],
)
def test_typed_expansions(input, output, no_expand_vars, passes):
    expansion_vars = exp_dict()

    expander = ramble.expander.Expander(expansion_vars, None, no_expand_vars=no_expand_vars)

    step_input = input
    for _ in range(passes):
        step_input = expander.expand_var(step_input, typed=True)
    final_output = step_input

    assert final_output == output


@pytest.mark.parametrize(
    "input,output",
    [
        ("application_name", "foo"),
        ("workload_name", "bar"),
        ("experiment_name", "baz"),
        ("var1", "3"),
        ("var2", "3"),
        ("var3", "3"),
    ],
)
def test_expand_var_name(input, output):
    expansion_vars = exp_dict()

    expander = ramble.expander.Expander(expansion_vars, None)

    assert expander.expand_var_name(input) == output


def test_expansion_namespaces():
    expansion_vars = exp_dict()

    expander = ramble.expander.Expander(expansion_vars, None)

    assert expander.application_name == "foo"
    assert expander.application_namespace == "foo@1.2"
    assert expander.workload_namespace == "foo@1.2.bar"
    assert expander.experiment_namespace == "foo@1.2.bar.baz"


@pytest.mark.parametrize(
    "input_list,output",
    [
        (["package_manager=spack"], True),
        (["test_variant=defined", "package_manager=spack"], True),
        (["test_variant=undefined", "package_manager=spack"], False),
        (["test_variant=undefined", "package_manager=spack", "workflow_manager=slurm"], False),
        (["test_variant=defined", "package_manager=spack", "workflow_manager=slurm"], True),
        (["compiler=gcc@14.2.0"], True),
        (["+bool_true"], True),
        (["bool_true=True"], True),
        (["bool_true=true"], True),
        (["bool_true=False"], False),
        (["bool_true=false"], False),
        (["~bool_true"], False),
        (["~bool_false"], True),
        (["bool_false=False"], True),
        (["bool_false=false"], True),
        (["bool_false=True"], False),
        (["bool_false=true"], False),
        (["+bool_false"], False),
    ],
)
def test_satisfies_works(input_list, output):
    variants = build_variant_set()

    expansion_vars = exp_dict()

    expander = ramble.expander.Expander(expansion_vars, None)

    satisfied = expander.satisfies(input_list, variant_set=variants)

    assert satisfied == output


def test_variable_mutation():
    """Test that variable changes are reflected in expansions"""
    expansion_vars = {"my_dict": {"key": 1}}

    expander = ramble.expander.Expander(expansion_vars, None)

    in_str = "{my_dict['key']}"

    res1 = expander.expand_var(in_str)
    assert res1 == "1"

    # sneaky mutation
    expander._variables["my_dict"]["key"] = 2
    res2 = expander.expand_var(in_str)
    assert res2 == "2"


def test_extra_vars_propagation():
    """Test that extra_vars are propagated properly"""
    expansion_vars = {
        "my_dict": {"key": 1},
        "my_val": 10,
        "my_bool": 1,
    }

    expander = ramble.expander.Expander(expansion_vars, None)

    in_str_dict = "{my_dict['key']}"
    assert expander.expand_var(in_str_dict) == "1"
    assert expander.expand_var(in_str_dict, extra_vars={"my_dict": {"key": 3}}) == "3"

    in_str_bin = "{{my_val} * 2}"
    assert expander.expand_var(in_str_bin) == "20"
    assert expander.expand_var(in_str_bin, extra_vars={"my_val": 5}) == "10"

    in_str_un = "{~{my_val}}"
    assert expander.expand_var(in_str_un) == "-11"
    assert expander.expand_var(in_str_un, extra_vars={"my_val": 1}) == "-2"

    in_str_func = "{max({my_val}, 15)}"
    assert expander.expand_var(in_str_func) == "15"
    assert expander.expand_var(in_str_func, extra_vars={"my_val": 20}) == "20"

    in_str_bool = "{{my_bool} and ({my_val} > 5)}"
    assert expander.expand_var(in_str_bool) == "True"
    assert expander.expand_var(in_str_bool, extra_vars={"my_val": 4}) == "False"
    assert expander.expand_var(in_str_bool, extra_vars={"my_bool": 0}) == "0"


def test_expander_copy_preserves_no_expand_vars():
    expansion_vars = {
        "var1": "{var2}",
        "var2": "3",
    }
    expander = ramble.expander.Expander(expansion_vars, None, no_expand_vars={"var1"})
    assert expander.expand_var("{var1}") == "{var2}"

    copied = expander.copy()
    assert copied.expand_var("{var1}") == "{var2}"


def test_expander_short_circuit_plain_and_escaped_strings():
    expansion_vars = {
        "var1": "value1",
        "var2": "value2",
        "nested": "{var1}",
    }
    expander = ramble.expander.Expander(expansion_vars, None)

    # Plain strings without delimiters
    assert expander.expand_var("plain_string") == "plain_string"
    assert expander.expand_var("/workspace/inputs/dir") == "/workspace/inputs/dir"
    assert expander.expand_var("gcc@14.2.0") == "gcc@14.2.0"

    # Plain math strings without delimiters
    assert expander.expand_var("2 + 3") == "5"
    assert expander.expand_var("4 * 5") == "20"

    # Template strings
    assert expander.expand_var("{var1}") == "value1"
    assert expander.expand_var("prefix_{var2}_suffix") == "prefix_value2_suffix"
    assert expander.expand_var("{nested}") == "value1"

    # Escaped curly braces
    assert expander.expand_var(r"\{escaped\}") == "{escaped}"
    assert expander.expand_var(r"\{var1\}") == "{var1}"
    assert expander.expand_var(r"prefix_\{var1\}_suffix") == "prefix_{var1}_suffix"

    # Enum expansion within templates
    from enum import Enum

    class StatusEnum(str, Enum):
        SETUP = "SETUP"

    enum_expander = ramble.expander.Expander({"status": StatusEnum.SETUP}, None)
    assert enum_expander.expand_var("{status}") == "SETUP"


def test_pow2_range_function():
    from ramble.expander import pow2_range

    assert pow2_range(8) == [1, 2, 4, 8]
    assert pow2_range(1, 16) == [1, 2, 4, 8, 16]
    assert pow2_range(2, 16) == [2, 4, 8, 16]
    assert pow2_range(1, 15) == [1, 2, 4, 8]
    assert pow2_range(1, 16, inclusive=False) == [1, 2, 4, 8]
    assert pow2_range(1, 1) == [1]
    assert pow2_range(1, 1, inclusive=False) == []
    assert pow2_range(16, 4) == []
    assert pow2_range(0) == []
    assert pow2_range(-1, 8) == []
    assert pow2_range(3, 24) == [3, 6, 12, 24]


def test_pow2_range_in_expander():
    expander = ramble.expander.Expander({"max_nodes": "16"}, None)

    assert expander.expand_lists("pow2_range(1, 16)") == [1, 2, 4, 8, 16]
    assert expander.expand_lists("power2_range(1, 16)") == [1, 2, 4, 8, 16]

    res = expander.expand_var("pow2_range(1, {max_nodes})", typed=True)
    assert res == [1, 2, 4, 8, 16]

    res_alias = expander.expand_var("power2_range(1, {max_nodes})", typed=True)
    assert res_alias == [1, 2, 4, 8, 16]
