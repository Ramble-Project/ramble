# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import glob
import os

import pytest

from llnl.util import tty

import ramble.workspace
from ramble.main import RambleCommand

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)

workspace = RambleCommand("workspace")


def _setup_workspace(make_workspace_from_config):
    test_config = """
ramble:
  variables:
    mpi_command: ''
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '1'
  applications:
    hostname:
      workloads:
        local:
          experiments:
            test:
              variables:
                n_nodes: '1'
  software:
    packages: {}
    environments: {}
"""
    ws, ws_name = make_workspace_from_config(test_config)

    workspace("setup", "--dry-run", global_args=["-w", ws_name])
    exp_out = os.path.join(ws.experiment_dir, "hostname", "local", "test", "test.out")
    with open(exp_out, "w+", encoding="utf-8") as f:
        f.write("test-user.c.googlers.com\n")
    return ws, ws_name


def test_analyze_fom_output(make_workspace_from_config):
    ws, ws_name = _setup_workspace(make_workspace_from_config)

    workspace("analyze", "-p", global_args=["-w", ws_name])
    result_file = glob.glob(os.path.join(ws.results_dir, "results.latest.txt"))[0]

    with open(result_file, encoding="utf-8") as f:
        content = f.read()
        assert "default (null) context figures of merit" in content
        assert "possible hostname = test-user.c.googlers.com" in content


def test_analyze_print(monkeypatch, make_workspace_from_config):
    _, ws_name = _setup_workspace(make_workspace_from_config)

    msg_list = []

    def _msg(msg, *args, **kwargs):
        msg_list.append(msg)

    # Assert whether the print is present or not
    monkeypatch.setattr(tty, "msg", _msg)

    workspace("analyze", global_args=["-w", ws_name])
    assert not any(m.startswith("Results from the analysis pipeline") for m in msg_list)

    msg_list = []
    workspace("analyze", "-p", global_args=["-w", ws_name])
    assert any(m.startswith("Results from the analysis pipeline") for m in msg_list)


# If an app has no FOM defined, analyze should not fail due to the lack of FOMs
def test_analyze_success_with_no_fom_defined(mock_applications, workspace_name):
    global_args = ["-w", workspace_name]
    ws = ramble.workspace.create(workspace_name)
    workspace(
        "manage",
        "experiments",
        "validation",
        "-v",
        "n_nodes=2",
        "-v",
        "processes_per_node=1",
        "-v",
        "batch_submit={execute_experiment}",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    ws._re_read()
    workspace("setup", "--dry-run", global_args=global_args)
    workspace("analyze", global_args=["-w", workspace_name])
    result_file = os.path.join(ws.results_dir, "results.latest.txt")
    with open(result_file, encoding="utf-8") as f:
        content = f.read()
        assert "Status = SUCCESS" in content


# If app has FOM defined, analyze fails when no FOM is detected from the experiment
def test_analyze_fail_with_no_fom_detected(mock_applications, workspace_name):
    global_args = ["-w", workspace_name]
    ws = ramble.workspace.create(workspace_name)
    workspace(
        "manage",
        "experiments",
        "basic",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "batch_submit={execute_experiment}",
        "--wf",
        "working_wl",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    ws._re_read()
    workspace("setup", "--dry-run", global_args=global_args)
    workspace("analyze", global_args=["-w", workspace_name])
    result_file = os.path.join(ws.results_dir, "results.latest.txt")
    with open(result_file, encoding="utf-8") as f:
        content = f.read()
        assert "Status = FAILED" in content


def test_analyze_fail_with_workflow_manager(
    monkeypatch, mock_applications, make_workspace_from_config
):
    test_config = """
ramble:
  variants:
    workflow_manager: user-managed
  variables:
    mpi_command: ''
    batch_submit: '{execute_experiment}'
    processes_per_node: '1'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test:
              variables:
                n_nodes: '1'
"""
    ws, ws_name = make_workspace_from_config(test_config)
    workspace_flags = ["-w", ws_name]

    workspace("setup", "--dry-run", global_args=workspace_flags)

    # Inject mock workflow manager status COMPLETE but provide no valid FOM output
    import ramble.wmkit

    monkeypatch.setattr(
        ramble.wmkit.WorkflowManagerBase,
        "get_status",
        lambda self, workspace: ramble.experiment_result.ExperimentStatus.COMPLETE,
    )

    workspace("analyze", global_args=workspace_flags)
    result_file = os.path.join(ws.results_dir, "results.latest.txt")
    with open(result_file, encoding="utf-8") as f:
        content = f.read()
        assert "Status = FAILED" in content


def test_analyze_fom_origin_types_filter(mock_applications, make_workspace_from_config):
    test_config = """
ramble:
  variables:
    mpi_command: 'mpirun -n {n_ranks} -ppn {processes_per_node}'
    batch_submit: 'batch_submit {execute_experiment}'
    processes_per_node: '1'
    n_ranks: '{processes_per_node}*{n_nodes}'
  applications:
    basic:
      workloads:
        test_wl:
          experiments:
            test:
              variables:
                n_nodes: '1'
  software:
    packages: {}
    environments: {}
"""
    ws, ws_name = make_workspace_from_config(test_config)

    workspace_flags = ["-w", ws_name]

    workspace("setup", "--dry-run", global_args=workspace_flags)

    exp_dir = os.path.join(ws.root, "experiments", "basic", "test_wl", "test")
    with open(os.path.join(exp_dir, "test.out"), "w+", encoding="utf-8") as f:
        f.write("12.3 seconds\n")

    output = workspace("analyze", "-p", global_args=workspace_flags)
    assert "default (null) context figures of merit" in output
    assert "test_fom = 12.3" in output

    # Ensure application FOMs are displayed
    output_filtered = workspace(
        "analyze", "--fom-origin-types", "application", "-p", global_args=workspace_flags
    )
    assert "default (null) context figures of merit" in output
    assert "test_fom = 12.3" in output

    # Use a non-existent origin type to filter out all FOMs
    output_filtered = workspace(
        "analyze", "--fom-origin-types", "foo", "-p", global_args=workspace_flags
    )
    # Ensure context without FOMs is not displayed
    assert "default (null) context figures of merit" not in output_filtered
    assert "test_fom = 12.3" not in output_filtered

    # Test option handling
    output_filtered = workspace(
        "analyze",
        "--fom-origin-types",
        "application",
        "--fom-origin-types",
        "foo",
        "-p",
        global_args=workspace_flags,
    )

    assert "default (null) context figures of merit" in output_filtered
    assert "test_fom = 12.3" in output_filtered

    output_filtered = workspace(
        "analyze", "--fom-origin-types", "application", "foo", "-p", global_args=workspace_flags
    )

    assert "default (null) context figures of merit" in output_filtered
    assert "test_fom = 12.3" in output_filtered


def test_analyze_garbage_output(make_workspace_from_config):
    """Test analyze can tolerate invalid UTF-8 bytes in the log file"""
    ws, ws_name = _setup_workspace(make_workspace_from_config)

    exp_out = os.path.join(ws.experiment_dir, "hostname", "local", "test", "test.out")
    with open(exp_out, "wb") as f:
        f.write(b"\x9e\ntest-user.c.googlers.com\n")

    workspace("analyze", "-p", global_args=["-w", ws_name])
    result_file = glob.glob(os.path.join(ws.results_dir, "results.latest.txt"))[0]

    with open(result_file, encoding="utf-8") as f:
        content = f.read()
        assert "possible hostname = test-user.c.googlers.com" in content


def test_analyze_hpl_fom_context_variable_expansion(make_workspace_from_config):
    """Test HPL calculator and standard workloads expand variables in fom_context"""
    test_config = """
ramble:
  variants:
    package_manager: user-managed
  variables:
    mpi_command: ''
    batch_submit: '{execute_experiment}'
    n_nodes: 2
    processes_per_node: 2
    hpl_path: '/usr/bin'
  applications:
    hpl:
      workloads:
        calculator:
          experiments:
            calc_test:
              variables:
                memory_per_node: 215
                block_size: 384
              success_criteria:
              - name: 'target_gflops'
                mode: 'fom_comparison'
                fom_name: 'GFlops'
                fom_context: 'N-NB-P-Q = {Ns}-{NBs}-{Ps}-{Qs}'
                formula: '{value} > 1000'
        standard:
          experiments:
            std_multi_test:
              variables:
                Ns: '1000 221184'
                Optimal-N: 221184
                NBs: 384
                Ps: 2
                Qs: 2
              success_criteria:
              - name: 'target_gflops'
                mode: 'fom_comparison'
                fom_name: 'GFlops'
                fom_context: 'N-NB-P-Q = {Optimal-N}-{NBs}-{Ps}-{Qs}'
                formula: '{value} > 1000'
"""
    ws, ws_name = make_workspace_from_config(test_config)
    workspace("setup", "--dry-run", global_args=["-w", ws_name])

    calc_out = os.path.join(ws.experiment_dir, "hpl", "calculator", "calc_test", "calc_test.out")
    with open(calc_out, "w+", encoding="utf-8") as f:
        f.write(
            "T/V                N    NB     P     Q               Time                 Gflops\n"
            "--------------------------------------------------------------------------------\n"
            "WR00L2L2      221184   384     2     2              10.00              1.500e+04\n"
        )

    std_out = os.path.join(
        ws.experiment_dir, "hpl", "standard", "std_multi_test", "std_multi_test.out"
    )
    with open(std_out, "w+", encoding="utf-8") as f:
        f.write(
            "T/V                N    NB     P     Q               Time                 Gflops\n"
            "--------------------------------------------------------------------------------\n"
            "WR00L2L2        1000   384     2     2               1.00              5.000e+01\n"
            "WR00L2L2      221184   384     2     2              10.00              1.500e+04\n"
        )

    workspace("analyze", global_args=["-w", ws_name])
    result_file = os.path.join(ws.results_dir, "results.latest.txt")
    with open(result_file, encoding="utf-8") as f:
        content = f.read()
        assert content.count("Status = SUCCESS") == 2
        assert content.count("config::experiment::target_gflops = PASSED") == 2


def test_analyze_hpcg_calculator_values(make_workspace_from_config):
    """Test HPCG calculator workload computes matrix_size during analyze"""
    test_config = """
ramble:
  variants:
    package_manager: user-managed
  variables:
    mpi_command: ''
    batch_submit: '{execute_experiment}'
    n_nodes: 1
    processes_per_node: 1
    hpcg_path: '/usr/bin'
  applications:
    hpcg:
      workloads:
        calculator:
          experiments:
            calc_test:
              variables:
                memory_per_rank: '4.0'
                out_file: '{experiment_run_dir}/{experiment_name}.out'
              success_criteria:
              - name: 'check_calculated_size'
                mode: 'fom_comparison'
                fom_name: 'Status'
                formula: "'{matrix_size}' == '168 168 168' and '{value}' == 'VALID'"
"""
    ws, ws_name = make_workspace_from_config(test_config)
    workspace("setup", "--dry-run", global_args=["-w", ws_name])

    calc_out = os.path.join(ws.experiment_dir, "hpcg", "calculator", "calc_test", "calc_test.out")
    with open(calc_out, "w+", encoding="utf-8") as f:
        f.write(
            "Final Summary::HPCG result is VALID with a GFLOP/s rating of=12.34\n"
            "Final Summary::HPCG 2.4 rating for historical reasons is=12.00\n"
        )

    workspace("analyze", global_args=["-w", ws_name])
    result_file = os.path.join(ws.results_dir, "results.latest.txt")
    with open(result_file, encoding="utf-8") as f:
        content = f.read()
        assert "Status = SUCCESS" in content
        assert "config::experiment::check_calculated_size = PASSED" in content
