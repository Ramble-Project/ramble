# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import json
import os
import stat

import pytest

import ramble.workspace
from ramble.main import RambleCommand

on = RambleCommand("on")
workspace = RambleCommand("workspace")

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
)

FAKE_SIF_ID = "11111111-2222-3333-4444-555555555555"


def _install_fake_apptainer(bin_dir, call_log):
    os.makedirs(bin_dir, exist_ok=True)
    script_path = os.path.join(bin_dir, "apptainer")
    script = f"""#!/bin/sh
set -e
echo "$@" >> "{call_log}"
cmd="$1"
shift
case "$cmd" in
  build|pull)
    sif_path="$1"
    mkdir -p "$(dirname "$sif_path")"
    echo "FAKE_SIF" > "$sif_path"
    ;;
  sif)
    sub="$1"
    if [ "$sub" = "header" ]; then
      echo "ID: {FAKE_SIF_ID}"
    fi
    ;;
  run)
    while [ "$#" -gt 0 ]; do
      case "$1" in
        *.sif)
          shift
          break
          ;;
        *)
          shift
          ;;
      esac
    done
    exec "$@"
    ;;
esac
"""
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    os.chmod(script_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IXGRP)


def _extract_apptainer_artifact_digest(inventory_data, container_name):
    for obj_conf in inventory_data.get("object_configuration", []):
        if (
            obj_conf.get("name") == "apptainer"
            and obj_conf.get("type") == "modifiers"
        ):
            for artifact in obj_conf.get("artifacts", []):
                if artifact.get("container_name") == container_name:
                    return artifact.get("digest")
    return None


def test_apptainer_build_from_def_refreshes_inventory(
    tmp_path, monkeypatch, request
):
    bin_dir = str(tmp_path / "bin")
    call_log = str(tmp_path / "apptainer_calls.log")
    _install_fake_apptainer(bin_dir, call_log)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")

    def_file = tmp_path / "verilator_test.def"
    def_file.write_text(
        "Bootstrap: docker\nFrom: rockylinux:9\n", encoding="utf-8"
    )

    ws_name = request.node.name
    test_config = f"""
ramble:
  modifiers:
  - name: apptainer
  variables:
    processes_per_node: 1
    n_nodes: 1
    mpi_command: ''
    batch_submit: '{{execute_experiment}}'
    container_uri: '{def_file}'
    container_name: 'verilator_test'
  applications:
    hostname:
      workloads:
        parallel:
          experiments:
            exp1:
              env_vars:
                set:
                  EXP_HASH_RECORDED: '{{experiment_hash}}'
            exp2:
              env_vars:
                set:
                  EXP_HASH_RECORDED: '{{experiment_hash}}'
  software:
    packages: {{}}
    environments: {{}}
"""
    with ramble.workspace.create(ws_name) as ws:
        ws.write()
        config_path = os.path.join(
            ws.config_dir, ramble.workspace.CONFIG_FILE_NAME
        )
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(test_config)
        ws._re_read()

        workspace("setup", global_args=["-D", ws.root])

        expected_sif = os.path.join(
            ws.input_dir, "hostname", "parallel", "verilator_test.sif"
        )
        assert os.path.isfile(expected_sif)

        with open(call_log, encoding="utf-8") as f:
            calls = [line.strip() for line in f if line.strip()]
        build_calls = [c for c in calls if c.startswith("build ")]
        pull_calls = [c for c in calls if c.startswith("pull ")]
        assert build_calls == [f"build {expected_sif} {def_file}"]
        assert pull_calls == []

        with open(
            os.path.join(
                ws.root, ramble.workspace.Workspace.inventory_file_name
            ),
            encoding="utf-8",
        ) as f:
            ws_inv = json.load(f)

        exp_digests = {
            entry["name"]: entry["digest"] for entry in ws_inv["experiments"]
        }
        assert len(exp_digests) == 2

        for exp_name in ("exp1", "exp2"):
            run_dir = os.path.join(
                ws.experiment_dir, "hostname", "parallel", exp_name
            )
            with open(
                os.path.join(run_dir, "ramble_inventory.json"),
                encoding="utf-8",
            ) as f:
                exp_inv = json.load(f)
            assert (
                _extract_apptainer_artifact_digest(exp_inv, "verilator_test")
                == FAKE_SIF_ID
            )

            full_name = f"hostname.parallel.{exp_name}"
            with open(
                os.path.join(run_dir, "execute_experiment"),
                encoding="utf-8",
            ) as f:
                exec_script = f.read()
            assert (
                f'export EXP_HASH_RECORDED="{exp_digests[full_name]}"'
                in exec_script
            )

        # Executing and analyzing must succeed without experiment hash mismatch,
        # and re-running setup must not rebuild an existing SIF image.
        on(global_args=["-D", ws.root])
        workspace("analyze", global_args=["-D", ws.root])
        workspace("setup", global_args=["-D", ws.root])

        with open(call_log, encoding="utf-8") as f:
            calls_after = [line.strip() for line in f if line.strip()]
        assert [c for c in calls_after if c.startswith("build ")] == [
            f"build {expected_sif} {def_file}"
        ]


def test_apptainer_pull_from_registry_uri(tmp_path, monkeypatch, request):
    bin_dir = str(tmp_path / "bin")
    call_log = str(tmp_path / "apptainer_calls.log")
    _install_fake_apptainer(bin_dir, call_log)
    monkeypatch.setenv("PATH", f"{bin_dir}:{os.environ.get('PATH', '')}")

    ws_name = request.node.name
    uri = "docker://rockylinux:9"
    test_config = f"""
ramble:
  modifiers:
  - name: apptainer
  variables:
    processes_per_node: 1
    n_nodes: 1
    mpi_command: ''
    batch_submit: '{{execute_experiment}}'
    container_uri: '{uri}'
    container_name: 'rocky9'
  applications:
    hostname:
      workloads:
        parallel:
          experiments:
            exp1: {{}}
  software:
    packages: {{}}
    environments: {{}}
"""
    with ramble.workspace.create(ws_name) as ws:
        ws.write()
        config_path = os.path.join(
            ws.config_dir, ramble.workspace.CONFIG_FILE_NAME
        )
        with open(config_path, "w", encoding="utf-8") as f:
            f.write(test_config)
        ws._re_read()

        workspace("setup", global_args=["-D", ws.root])

        expected_sif = os.path.join(
            ws.input_dir, "hostname", "parallel", "rocky9.sif"
        )
        assert os.path.isfile(expected_sif)

        with open(call_log, encoding="utf-8") as f:
            calls = [line.strip() for line in f if line.strip()]
        assert [c for c in calls if c.startswith("pull ")] == [
            f"pull {expected_sif} {uri}"
        ]
        assert [c for c in calls if c.startswith("build ")] == []

        run_dir = os.path.join(
            ws.experiment_dir, "hostname", "parallel", "exp1"
        )
        with open(
            os.path.join(run_dir, "ramble_inventory.json"),
            encoding="utf-8",
        ) as f:
            exp_inv = json.load(f)
        assert (
            _extract_apptainer_artifact_digest(exp_inv, "rocky9")
            == FAKE_SIF_ID
        )
