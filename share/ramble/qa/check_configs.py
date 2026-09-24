#!/usr/bin/env python3
# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import argparse
import glob
import os
import shutil
import sys
import tempfile

import llnl.util.tty
from ruamel.yaml.error import YAMLError

import ramble.config
import ramble.error
import ramble.paths
import ramble.schema.workspace
import ramble.workspace

import spack.error
import spack.util.spack_yaml as syaml

ramble_root = ramble.paths.prefix

# These example configs are intentionally invalid for demonstration purposes
SKIPPED_SEMANTIC_FILES = {
    "tutorial_7_base_config.yaml",
    "tutorial_7_matrix_config.yaml",
}


def parse_args(args=None):
    parser = argparse.ArgumentParser(
        description="Validate workspace configurations against Ramble's workspace "
        "schema and semantic experiment construction."
    )
    parser.add_argument(
        "files",
        nargs="*",
        metavar="FILE",
        help="Specific configuration file(s) to validate. If omitted, all example configs are checked.",
    )
    return parser.parse_args(args)


def validate_schema(file_path):
    """Validate file against workspace schema."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = syaml.load(f)
    except (syaml.SpackYAMLError, YAMLError) as e:
        raise ramble.config.ConfigError(f"Invalid YAML syntax: {e}") from e

    if data is None or not isinstance(data, dict):
        raise ramble.config.ConfigError("Empty or invalid YAML mapping")

    if "ramble" not in data:
        raise ramble.config.ConfigError("Missing top-level 'ramble' section")

    ramble.config.validate(data, ramble.schema.workspace.schema, filename=file_path)


def validate_semantics(file_path):
    """Ingest configuration into a workspace and build the experiment set."""
    tmp_dir = tempfile.mkdtemp(prefix="ramble_check_configs_")
    try:
        cfg_dir = os.path.join(tmp_dir, "configs")
        os.makedirs(cfg_dir, exist_ok=True)
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        with open(os.path.join(cfg_dir, "ramble.yaml"), "w", encoding="utf-8") as f:
            f.write(content)

        ws = ramble.workspace.Workspace(tmp_dir, read_default_template=False)
        ramble.workspace.activate(ws)
        try:
            with llnl.util.tty.SuppressOutput(msg_enabled=False, warn_enabled=False):
                exp_set = ws.build_experiment_set()
            return len(exp_set.experiments)
        except SystemExit as e:
            raise ramble.error.RambleError(
                f"Experiment generation terminated unexpectedly (exit code {e.code})"
            ) from e
        finally:
            ramble.workspace.deactivate()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main(argv=None):
    args = parse_args(argv)

    if args.files:
        files = [os.path.abspath(f) for f in args.files]
    else:
        examples_dir = os.path.join(ramble_root, "examples")
        yaml_pattern = os.path.join(examples_dir, "**", "*.yaml")
        yml_pattern = os.path.join(examples_dir, "**", "*.yml")
        files = sorted(glob.glob(yaml_pattern, recursive=True))
        files.extend(sorted(glob.glob(yml_pattern, recursive=True)))

    if not files:
        print("No configuration files found to validate.")
        return 0

    print(
        f"Validating {len(files)} configuration(s) "
        "[Schema & Semantic]..."
    )

    schema_failures = 0
    semantic_failures = 0

    for file_path in files:
        rel_path = os.path.relpath(file_path, ramble_root)
        fname = os.path.basename(file_path)

        # Schema validation
        try:
            validate_schema(file_path)
        except (ramble.config.ConfigError, syaml.SpackYAMLError, YAMLError) as e:
            print(f"  FAILED [Schema]: {rel_path}\n    {e}", file=sys.stderr)
            schema_failures += 1
            continue

        # Semantic validation
        if fname in SKIPPED_SEMANTIC_FILES:
            print(
                f"  PASSED: {rel_path} "
                "(skipped semantic check - intentional tutorial error)"
            )
            continue

        semantic_err = None
        n_experiments = 0

        try:
            n_experiments = validate_semantics(file_path)
        except (ramble.error.RambleError, spack.error.SpackError) as e:
            semantic_err = f"{type(e).__name__}: {e}"

        if semantic_err:
            err_msg = semantic_err.split("\n")[0]
            print(f"  FAILED [Semantic]: {rel_path}\n    {err_msg}", file=sys.stderr)
            semantic_failures += 1
        else:
            print(f"  PASSED: {rel_path} ({n_experiments} experiments)")

    total_failures = schema_failures + semantic_failures
    if total_failures > 0:
        print(
            f"\nError: {total_failures}/{len(files)} configuration(s) failed validation "
            f"({schema_failures} schema, {semantic_failures} semantic).",
            file=sys.stderr,
        )
        return 1

    print(f"\nAll {len(files)} configuration(s) passed validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
