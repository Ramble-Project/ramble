# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from enum import Enum

import ramble.util.ramble_yaml as syaml

SCOPES = Enum("SCOPES", ["workspace", "application", "workload", "experiment"])


def dry_run_config(
    section_name, injections, config_path, app_name, wl_name, batch_cmd="batch_submit"
):
    """Creates a new configuration with modifiers injected

    Input argument injections is a list of tuples. Each tuple has two
    values, and takes the form:

    (scope, injection_dict)

    scope is the scope the injection dict should be injected into
    injection_dict is a dict representing the new injection into the config

    config_path is the path to the config file that should be written
    """
    ramble_dict = syaml.syaml_dict()
    ramble_dict["ramble"] = syaml.syaml_dict()
    test_dict = ramble_dict["ramble"]

    test_dict["variants"] = syaml.syaml_dict()
    test_dict["variables"] = syaml.syaml_dict()
    test_dict["applications"] = syaml.syaml_dict()
    test_dict["applications"][app_name] = syaml.syaml_dict()
    test_dict["software"] = syaml.syaml_dict()

    variants_dict = test_dict["variants"]
    variants_dict["package_manager"] = "spack"

    software_dict = test_dict["software"]
    software_dict["packages"] = syaml.syaml_dict()
    software_dict["environments"] = syaml.syaml_dict()

    ws_var_dict = test_dict["variables"]
    ws_var_dict["mpi_command"] = "mpirun -n {n_ranks} -ppn {processes_per_node}"
    ws_var_dict["batch_submit"] = f"{batch_cmd} {{execute_experiment}}"
    ws_var_dict["processes_per_node"] = "16"
    ws_var_dict["n_ranks"] = "{processes_per_node}*{n_nodes}"
    ws_var_dict["n_threads"] = "1"
    ws_var_dict["modeless_required_var"] = "1"

    app_dict = test_dict["applications"][app_name]
    app_dict["workloads"] = syaml.syaml_dict()
    app_dict["workloads"][wl_name] = syaml.syaml_dict()

    workload_dict = app_dict["workloads"][wl_name]
    workload_dict["experiments"] = syaml.syaml_dict()
    workload_dict["experiments"]["test_exp"] = syaml.syaml_dict()

    exp_dict = workload_dict["experiments"]["test_exp"]
    exp_dict["variables"] = syaml.syaml_dict()
    exp_dict["variables"]["n_nodes"] = "1"

    for scope, injection_dict in injections:
        if scope == SCOPES.workspace:
            dict_to_mod = test_dict
        elif scope == SCOPES.application:
            dict_to_mod = app_dict
        elif scope == SCOPES.workload:
            dict_to_mod = workload_dict
        elif scope == SCOPES.experiment:
            dict_to_mod = exp_dict

        if section_name not in dict_to_mod:
            dict_to_mod[section_name] = syaml.syaml_list()

        dict_to_mod[section_name].append(injection_dict.copy())

    with open(config_path, "w+", encoding="utf-8") as f:
        syaml.dump(ramble_dict, stream=f)


def search_files_for_string(file_list, string):
    for file in file_list:
        with open(file, encoding="utf-8") as f:
            if string in f.read():
                return True
    return False
