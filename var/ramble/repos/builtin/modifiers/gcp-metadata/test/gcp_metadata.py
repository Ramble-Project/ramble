# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

from ramble.main import RambleCommand

workspace = RambleCommand("workspace")


@pytest.mark.parametrize(
    "mode,prefix,suffix,expected_id_cmd,expected_host_cmd",
    [
        (
            "standard",
            None,
            None,
            'pdsh -R ssh -w nodeset-0 \'curl -s -f -w "\\n" "http://metadata.google.internal/computeMetadata/v1/instance/id" -H "Metadata-Flavor: Google" \' >',
            'pdsh -R ssh -N -w nodeset-0 \'curl -s -f -w "\\n" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/physical_host" -H "Metadata-Flavor: Google" \' >',
        ),
        (
            "local",
            None,
            None,
            'curl -s -f -w "\\n" "http://metadata.google.internal/computeMetadata/v1/instance/id" -H "Metadata-Flavor: Google"  >',
            'curl -s -f -w "\\n" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/physical_host" -H "Metadata-Flavor: Google"  >',
        ),
        (
            "standard",
            "pdsh -R ssh -N -w {hostlist} '",
            "'",
            'pdsh -R ssh -w nodeset-0 \'curl -s -f -w "\\n" "http://metadata.google.internal/computeMetadata/v1/instance/id" -H "Metadata-Flavor: Google" \' >',
            'pdsh -R ssh -N -w nodeset-0 \'curl -s -f -w "\\n" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/physical_host" -H "Metadata-Flavor: Google" \' >',
        ),
        (
            "standard",
            "pdsh -R ssh -N -w {hostlist}",
            "| sort",
            'pdsh -R ssh -w nodeset-0 \'curl -s -f -w "\\n" "http://metadata.google.internal/computeMetadata/v1/instance/id" -H "Metadata-Flavor: Google" \' | sort >',
            'pdsh -R ssh -N -w nodeset-0 \'curl -s -f -w "\\n" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/physical_host" -H "Metadata-Flavor: Google" \' | sort >',
        ),
        (
            "local",
            "",
            "'",
            'curl -s -f -w "\\n" "http://metadata.google.internal/computeMetadata/v1/instance/id" -H "Metadata-Flavor: Google"  >',
            'curl -s -f -w "\\n" "http://metadata.google.internal/computeMetadata/v1/instance/attributes/physical_host" -H "Metadata-Flavor: Google"  >',
        ),
    ],
    ids=[
        "standard_default",
        "local_default",
        "standard_quoted",
        "standard_custom_suffix",
        "local_stray_quote",
    ],
)
def test_gcp_metadata_quoting(
    make_workspace_from_config,
    mode,
    prefix,
    suffix,
    expected_id_cmd,
    expected_host_cmd,
):
    ws, ws_name = make_workspace_from_config()
    global_args = ["-w", ws_name]
    exp_args = [
        "manage",
        "experiments",
        "hostname",
        "--wf",
        "local",
        "-e",
        "test",
        "-v",
        "n_nodes=2",
        "-v",
        "processes_per_node=1",
        "-v",
        "hostlist=nodeset-0",
    ]
    if prefix is not None:
        exp_args.extend(["-v", f"metadata_parallel_prefix={prefix}"])
    if suffix is not None:
        exp_args.extend(["-v", f"metadata_parallel_suffix={suffix}"])

    workspace(*exp_args, global_args=global_args)
    workspace(
        "manage",
        "modifiers",
        "--add",
        "-n",
        "gcp-metadata",
        "-m",
        mode,
        global_args=global_args,
    )
    workspace("setup", "--dry-run", global_args=global_args)
    run_dir = os.path.join(ws.experiment_dir, "hostname", "local", "test")
    with open(
        os.path.join(run_dir, "execute_experiment"), encoding="utf-8"
    ) as f:
        content = f.read()
        assert expected_id_cmd in content
        assert expected_host_cmd in content
