# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import ramble.config
import ramble.filters
import ramble.pipeline
import ramble.workspace
from ramble.main import RambleCommand


def test_workspace_bootstrap_utilities(make_workspace_from_config, monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda x, **kwargs: None)

    test_config = """
ramble:
  utilities:
    spack:
      git: https://github.com/my/ext_dep.git
      commit: v2.0
"""
    ws, ws_name = make_workspace_from_config(test_config, activate=True)
    workspace = RambleCommand("workspace")
    workspace(
        "manage",
        "experiments",
        "hostname",
        "--wf",
        "serial",
        "-v",
        "n_ranks=1",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        global_args=["-w", ws_name],
    )
    ws._re_read()

    # In order to test bootstrap, we need an object with required_utilities
    filters = ramble.filters.Filters()

    with ws:
        setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)

        # Retrieve the app instance to mock the external dependency definition
        app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))

        # Manually attach required_utilities to the instance
        app_inst.required_utilities = {
            frozenset([]): {
                "spack": {
                    "git": "https://github.com/spack/spack.git",
                    "commit": "v1.0",
                }
            }
        }

        ws.dry_run = True
        with ramble.config.override("config:bootstrap_utilities", True):
            setup_pipeline.run()

    assert hasattr(app_inst, "_bootstrapped_utility_paths")
    assert "spack" in app_inst._bootstrapped_utility_paths
    # Verify the external dependency directory is correct
    ext_dep_dir = app_inst._bootstrapped_utility_paths["spack"]
    assert ext_dep_dir.endswith(os.path.join("bootstrapped_utilities", "spack", "v2.0", "source"))
    assert "utility::spack::activation_command" in app_inst.variables
    assert "source" in app_inst.variables["utility::spack::activation_command"]


def test_workspace_bootstrap_utilities_from_modifier(
    mutable_config,
    mutable_mock_workspace_path,
    mock_applications,
    mock_modifiers,
    workspace_name,
):
    workspace = RambleCommand("workspace")
    global_args = ["-w", workspace_name]

    with ramble.workspace.create(workspace_name):
        workspace(
            "manage",
            "experiments",
            "basic",
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
        workspace(
            "manage",
            "modifiers",
            "--add",
            "--name",
            "requires-utility-mod",
            "--scope",
            "workspace",
            global_args=global_args,
        )

        ws = ramble.workspace.active_workspace()
        filters = ramble.filters.Filters()
        setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)
        ws.dry_run = True
        with ramble.config.override("config:bootstrap_utilities", True):
            setup_pipeline.run()

        app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))
        assert "spack" in app_inst.utilities
        assert app_inst.utilities["spack"]["git"] == "https://github.com/spack/spack.git"
        assert app_inst.utilities["spack"]["commit"] == "v1.5"
        assert app_inst.utilities["spack"]["allow_external"] is False
        assert len(app_inst._utility_instances) == 1
        assert app_inst._utility_instances[0].name == "spack"
        assert app_inst._utility_instances[0].utility_config == app_inst.utilities["spack"]
        # Calling build_utility_instances again should return early from cached instances
        cached_instances = list(app_inst._utility_instances)
        app_inst.build_utility_instances()
        assert app_inst._utility_instances == cached_instances
        assert hasattr(app_inst, "_bootstrapped_utility_paths")
        assert "spack" in app_inst._bootstrapped_utility_paths
        ext_dep_dir = app_inst._bootstrapped_utility_paths["spack"]
        assert ext_dep_dir.endswith(
            os.path.join("bootstrapped_utilities", "spack", "v1.5", "source")
        )


def test_missing_utility_from_workspace_config_error(
    make_workspace_from_config, mock_applications
):
    test_config = """
ramble:
  utilities:
    non_existent_utility:
      git: https://github.com/my/ext_dep.git
"""
    _, ws_name = make_workspace_from_config(test_config, activate=True)
    workspace = RambleCommand("workspace")
    out = workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-v",
        "n_ranks=1",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        global_args=["-w", ws_name],
        fail_on_error=False,
    )

    assert workspace.returncode != 0
    assert "The following utilities were required, but do not exist." in out
    assert "  - non_existent_utility" in out
    assert "To view the available utilities, use `ramble list --type utilities`" in out


def test_missing_required_utility_from_object_error(
    make_workspace_from_config, mock_applications, capsys
):
    ws, ws_name = make_workspace_from_config(activate=True)
    workspace = RambleCommand("workspace")
    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-v",
        "n_ranks=1",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        global_args=["-w", ws_name],
    )
    ws._re_read()

    filters = ramble.filters.Filters()
    setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)
    app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))

    app_inst.required_utilities = {
        frozenset([]): {
            "missing_util_b": {},
            "missing_util_a": {},
        }
    }
    app_inst._utility_instances = []

    with pytest.raises(SystemExit):
        app_inst.build_utility_instances()

    captured = capsys.readouterr()
    assert "The following utilities were required, but do not exist." in captured.err
    assert "  - missing_util_a\n  - missing_util_b" in captured.err
    assert "To view the available utilities, use `ramble list --type utilities`" in captured.err


def test_bootstrap_utilities_edge_cases(
    make_workspace_from_config, mock_applications, monkeypatch
):
    test_config = """
ramble:
  utilities:
    spack:
      git: https://github.com/my/ext_dep.git
      when: ["some_cond"]
"""
    ws, ws_name = make_workspace_from_config(test_config, activate=True)
    workspace = RambleCommand("workspace")
    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-v",
        "n_ranks=1",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        "-v",
        "spack_version=expanded_commit",
        global_args=["-w", ws_name],
    )
    ws._re_read()

    filters = ramble.filters.Filters()
    setup_pipeline = ramble.pipeline.SetupPipeline(ws, filters)
    app_inst = next(iter(setup_pipeline.experiment_set.experiments.values()))

    app_inst.required_utilities = {
        frozenset([]): {
            "missing_repo_util": {},
            "spack": {"git": "https://github.com/spack/spack.git"},
        }
    }

    SpackClass = type(
        ramble.repository.paths[ramble.repository.ObjectTypes.utilities].get("spack")
    )
    monkeypatch.setattr(SpackClass, "is_available", lambda *a, **k: True)
    monkeypatch.setattr(SpackClass, "validate_versions", lambda *a, **k: True)

    with ramble.config.override("config:bootstrap_utilities", True):
        app_inst._bootstrap_utilities(ws)
    assert app_inst._bootstrapped_utility_paths["spack"] == "system"
    assert app_inst.variables["utility::spack::commit"] == "expanded_commit"
    assert "utility::spack::when" not in app_inst.variables


def _populate_mock_bootstrapped_spack(ws, version="v1.2.2"):
    """Populate a mock bootstrapped spack tree with both essential files and build bloat."""
    import llnl.util.filesystem as fs

    version_dir = os.path.join(ws.shared_dir, "bootstrapped_utilities", "spack", version)
    source_dir = os.path.join(version_dir, "source")

    kept_rel_paths = [
        os.path.join("source", "bin", "spack"),
        os.path.join("source", "share", "spack", "setup-env.sh"),
        os.path.join(
            "source", "var", "spack", "repos", "builtin", "packages", "opt", "package.py"
        ),
        os.path.join(".spack", "config.yaml"),
    ]
    excluded_rel_paths = [
        os.path.join("source", "opt", "spack", "linux-x86_64", "gcc", "zlib", "libz.so"),
        os.path.join("source", "var", "spack", "stage", "spack-stage-zlib", "build.out"),
        os.path.join("source", "var", "spack", "cache", "_source-cache", "zlib.tar.gz"),
        os.path.join(".spack", "bootstrap", "store", "clingo.so"),
        os.path.join(".spack", "cache", "indices", "index.json"),
    ]

    for rel in kept_rel_paths + excluded_rel_paths:
        full_path = os.path.join(version_dir, rel)
        fs.mkdirp(os.path.dirname(full_path))
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(f"mock content for {rel}\n")

    return version_dir, source_dir, kept_rel_paths, excluded_rel_paths


def test_utility_archive_exclude_directive_and_info():
    from ramble.language.shared_language import variant
    from ramble.language.utility_language import archive_exclude

    UtilityBase = ramble.repository.get_base_class("utility-base")

    class CustomExcludedUtil(UtilityBase):
        name = "custom_excluded_util"

        variant("clean_cache", default=False, description="Exclude cache dir")
        archive_exclude("build")
        archive_exclude("cache/*", when=["+clean_cache"])

    util = CustomExcludedUtil("/mock/path")
    assert frozenset() in util.archive_excludes
    assert util.archive_excludes[frozenset()]["build"] == "build"
    assert frozenset(["+clean_cache"]) in util.archive_excludes
    assert util.archive_excludes[frozenset(["+clean_cache"])]["cache/*"] == "cache/*"

    info = RambleCommand("info")
    out = info("--type", "utilities", "spack")
    assert "archive_excludes:" in out
    for expected in [
        "opt",
        "var/spack/stage",
        "var/spack/cache",
        "../.spack/bootstrap",
        "../.spack/cache",
    ]:
        assert expected in out


def test_workspace_archive_omits_utilities_by_default_and_excludes_bloat(
    make_workspace_from_config, mock_applications
):
    import llnl.util.filesystem as fs

    test_config = """
ramble:
  utilities:
    spack:
      version: v1.2.2
"""
    ws, ws_name = make_workspace_from_config(test_config, activate=True)
    workspace = RambleCommand("workspace")
    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-v",
        "n_ranks=1",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        global_args=["-w", ws_name],
    )
    ws._re_read()

    workspace("setup", "--dry-run", global_args=["-w", ws_name])

    shared_marker = os.path.join(ws.shared_dir, "custom_shared.txt")
    fs.mkdirp(ws.shared_dir)
    with open(shared_marker, "w", encoding="utf-8") as f:
        f.write("shared data\n")

    _, _, kept_rel_paths, excluded_rel_paths = _populate_mock_bootstrapped_spack(ws)

    # Default archive omits shared/bootstrapped_utilities while keeping other shared files
    workspace("archive", "--prefix", "default_archive")
    default_archive_dir = ws.latest_archive_path
    assert "default_archive-archive-" in os.path.basename(default_archive_dir)
    assert os.path.isfile(os.path.join(default_archive_dir, "shared", "custom_shared.txt"))
    assert not os.path.exists(
        os.path.join(default_archive_dir, "shared", "bootstrapped_utilities")
    )

    # --include-utilities copies bootstrapped utilities while skipping archive_exclude paths
    workspace(
        "archive",
        "--include-utilities",
        "--prefix",
        "with_utilities",
    )
    with_utils_archive_dir = ws.latest_archive_path
    assert "with_utilities-archive-" in os.path.basename(with_utils_archive_dir)
    archived_spack_ver_dir = os.path.join(
        with_utils_archive_dir, "shared", "bootstrapped_utilities", "spack", "v1.2.2"
    )
    assert os.path.isfile(os.path.join(with_utils_archive_dir, "shared", "custom_shared.txt"))
    for rel in kept_rel_paths:
        assert os.path.isfile(os.path.join(archived_spack_ver_dir, rel))
    for rel in excluded_rel_paths:
        assert not os.path.exists(os.path.join(archived_spack_ver_dir, rel))
    assert not os.path.exists(os.path.join(archived_spack_ver_dir, "source", "opt"))


def test_deployment_push_omits_utilities_by_default_and_excludes_bloat(
    make_workspace_from_config, mock_applications
):
    from ramble.util import json_util

    test_config = """
ramble:
  utilities:
    spack:
      version: v1.2.2
"""
    ws, ws_name = make_workspace_from_config(test_config, activate=True)
    workspace = RambleCommand("workspace")
    deployment = RambleCommand("deployment")
    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-v",
        "n_ranks=1",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        global_args=["-w", ws_name],
    )
    ws._re_read()

    _, _, kept_rel_paths, excluded_rel_paths = _populate_mock_bootstrapped_spack(ws)

    # Default deployment omits shared/bootstrapped_utilities
    deployment("push", "-d", "default_deploy", global_args=["-w", ws_name])
    default_deploy_dir = os.path.join(ws.deployments_dir, "default_deploy")
    assert not os.path.exists(os.path.join(default_deploy_dir, "shared", "bootstrapped_utilities"))
    with open(os.path.join(default_deploy_dir, "index.json"), encoding="utf-8") as f:
        default_index = json_util.load(f)["deployment_files"]
    assert not any("bootstrapped_utilities" in entry for entry in default_index)

    # --include-utilities copies bootstrapped utilities while skipping archive_exclude paths
    deployment(
        "push",
        "-d",
        "with_utils_deploy",
        "--include-utilities",
        global_args=["-w", ws_name],
    )
    utils_deploy_dir = os.path.join(ws.deployments_dir, "with_utils_deploy")
    deployed_spack_ver_dir = os.path.join(
        utils_deploy_dir, "shared", "bootstrapped_utilities", "spack", "v1.2.2"
    )
    with open(os.path.join(utils_deploy_dir, "index.json"), encoding="utf-8") as f:
        utils_index = set(json_util.load(f)["deployment_files"])

    for rel in kept_rel_paths:
        assert os.path.isfile(os.path.join(deployed_spack_ver_dir, rel))
        expected_index_entry = os.path.join(
            "shared", "bootstrapped_utilities", "spack", "v1.2.2", rel
        )
        assert expected_index_entry in utils_index

    for rel in excluded_rel_paths:
        assert not os.path.exists(os.path.join(deployed_spack_ver_dir, rel))
        unexpected_index_entry = os.path.join(
            "shared", "bootstrapped_utilities", "spack", "v1.2.2", rel
        )
        assert unexpected_index_entry not in utils_index


def test_utility_archive_exclude_when_and_variable_expansion(
    make_workspace_from_config, mock_applications, monkeypatch
):
    import llnl.util.filesystem as fs

    ws, ws_name = make_workspace_from_config(activate=True)
    workspace = RambleCommand("workspace")
    workspace(
        "manage",
        "experiments",
        "basic",
        "--wf",
        "test_wl",
        "-v",
        "n_ranks=1",
        "-v",
        "n_nodes=1",
        "-v",
        "processes_per_node=1",
        global_args=["-w", ws_name],
    )
    ws._re_read()

    # Populate spack on disk WITHOUT referencing spack in ramble.yaml (tests repo fallback),
    # plus custom variable-expanded and conditional excludes.
    version_dir, source_dir, kept_rel_paths, _ = _populate_mock_bootstrapped_spack(ws)
    extra_var_excluded = os.path.join(source_dir, "generated_bloat", "artifact.bin")
    extra_glob_excluded = os.path.join(source_dir, "logs", "debug.tmp")
    conditional_kept = os.path.join(source_dir, "conditional_dir", "keep.txt")
    for path in [extra_var_excluded, extra_glob_excluded, conditional_kept]:
        fs.mkdirp(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write("data\n")

    SpackClass = type(ramble.repository.get("spack", ramble.repository.ObjectTypes.utilities))
    patched_excludes = {
        frozenset(): {
            "opt": "opt",
            "{utility::spack::path}/generated_bloat": "{utility::spack::path}/generated_bloat",
            "*.tmp": "*.tmp",
        },
        frozenset(["+non_existent_variant"]): {
            "conditional_dir": "conditional_dir",
        },
    }
    monkeypatch.setattr(SpackClass, "archive_excludes", patched_excludes)

    workspace("setup", "--dry-run", global_args=["-w", ws_name])
    workspace("archive", "--include-utilities", global_args=["-w", ws_name])

    archived_spack_ver_dir = os.path.join(
        ws.latest_archive_path, "shared", "bootstrapped_utilities", "spack", "v1.2.2"
    )
    for rel in kept_rel_paths:
        assert os.path.isfile(os.path.join(archived_spack_ver_dir, rel))
    assert os.path.isfile(
        os.path.join(archived_spack_ver_dir, "source", "conditional_dir", "keep.txt")
    )
    assert not os.path.exists(os.path.join(archived_spack_ver_dir, "source", "opt"))
    assert not os.path.exists(os.path.join(archived_spack_ver_dir, "source", "generated_bloat"))
    assert not os.path.exists(os.path.join(archived_spack_ver_dir, "source", "logs", "debug.tmp"))
