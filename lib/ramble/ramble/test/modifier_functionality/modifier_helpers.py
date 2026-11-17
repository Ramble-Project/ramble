# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import ramble.util.ramble_yaml as syaml


def check_software_env(base_dir, tests):
    """Validate software environments

    Input arguments:
    - base_dir: the software directory tests should validate against
    - tests: list of tuples. Each tuple should be (env_name, expected_contents).

    This method will validate that expected_contents exists in the spack.yaml
    file in the corresponding env_name.
    """
    for test_env, test_content in tests:
        env_dir = os.path.join(base_dir, test_env)
        assert os.path.exists(env_dir)

        spack_file = os.path.join(env_dir, "spack.yaml")
        assert os.path.isfile(spack_file)

        with open(spack_file, encoding="utf-8") as f:
            assert test_content in f.read()


def check_execute_script(script_path, tests):
    assert os.path.isfile(script_path)
    with open(script_path, encoding="utf-8") as f:
        data = f.read()
        for test in tests:
            assert test in data


def named_modifier(name, mode=None):
    modifier_def = syaml.syaml_dict()
    modifier_def["name"] = name
    if mode is not None:
        modifier_def["mode"] = mode
    return modifier_def


def intel_aps_modifier():
    modifier_def = named_modifier("intel-aps")
    modifier_def["mode"] = "mpi"
    modifier_def["on_executable"] = syaml.syaml_list()
    modifier_def["on_executable"].append("*")
    return modifier_def


def intel_aps_answer():
    expected_software = [("gromacs", "intel-oneapi-vtune"), ("gromacs", "gromacs")]
    expected_strs = ["aps -c mpi", "aps-report"]
    return expected_software, expected_strs


def lscpu_modifier():
    modifier_def = named_modifier("lscpu")
    modifier_def["mode"] = "standard"
    modifier_def["on_executable"] = syaml.syaml_list()
    modifier_def["on_executable"].append("*")
    return modifier_def


def lscpu_answer():
    expected_software = [
        ("gromacs", "gromacs"),
    ]
    expected_strs = [
        "lscpu",
    ]
    return expected_software, expected_strs


def env_var_append_paths_modifier():
    modifier_def = named_modifier("append-env-var-mod-paths")
    modifier_def["mode"] = "test"
    modifier_def["on_executable"] = syaml.syaml_list()
    modifier_def["on_executable"].append("*")
    return modifier_def


def env_var_append_paths_modifier_answer():
    expected_software = [
        ("gromacs", "gromacs"),
    ]
    expected_strs = ['export test_var="${test_var}:test_val"']
    return expected_software, expected_strs


def env_var_append_vars_modifier():
    modifier_def = named_modifier("append-env-var-mod-vars")
    modifier_def["mode"] = "test"
    modifier_def["on_executable"] = syaml.syaml_list()
    modifier_def["on_executable"].append("*")
    return modifier_def


def env_var_append_vars_modifier_answer():
    expected_software = [
        ("gromacs", "gromacs"),
    ]
    expected_strs = [
        'export test_var="${test_var},test_val"',
    ]
    return expected_software, expected_strs


def env_var_prepend_paths_modifier():
    modifier_def = named_modifier("prepend-env-var-mod-paths")
    modifier_def["mode"] = "test"
    modifier_def["on_executable"] = syaml.syaml_list()
    modifier_def["on_executable"].append("*")
    return modifier_def


def env_var_prepend_paths_modifier_answer():
    expected_software = [
        ("gromacs", "gromacs"),
    ]
    expected_strs = [
        'export test_var="test_val:${test_var}"',
    ]
    return expected_software, expected_strs


def env_var_set_modifier():
    modifier_def = named_modifier("set-env-var-mod")
    modifier_def["mode"] = "test"
    modifier_def["on_executable"] = syaml.syaml_list()
    modifier_def["on_executable"].append("*")
    return modifier_def


def env_var_set_modifier_answer():
    expected_software = [
        ("gromacs", "gromacs"),
    ]
    expected_strs = ["export test_var=test_val", 'export mask_env_var="0x0"']
    return expected_software, expected_strs


def env_var_unset_modifier():
    modifier_def = named_modifier("unset-env-var-mod")
    modifier_def["mode"] = "test"
    modifier_def["on_executable"] = syaml.syaml_list()
    modifier_def["on_executable"].append("*")
    return modifier_def


def env_var_unset_modifier_answer():
    expected_software = [
        ("gromacs", "gromacs"),
    ]
    expected_strs = [
        "unset test_var",
    ]
    return expected_software, expected_strs
