# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import pytest

import llnl.util.filesystem as fs

import ramble.paths
import ramble.workspace
from ramble.error import RambleCommandError
from ramble.main import RambleCommand
from ramble.util import json_util

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
    "mutable_mock_apps_repo",
    "workspace_deactivate",
)

location = RambleCommand("location")
workspace = RambleCommand("workspace")


def _basic_config(apps_yaml: str, extra: str = "") -> str:
    return (
        "ramble:\n"
        "  variables:\n"
        "    mpi_command: 'mpirun -n {n_ranks}'\n"
        "    batch_submit: '{execute_experiment}'\n"
        f"{extra}"
        "  applications:\n"
        f"{apps_yaml}"
    )


def test_location_default_no_workspace():
    assert location().strip() == os.path.abspath(ramble.paths.prefix)


def test_location_default_active_workspace_and_global_flags(make_workspace_from_config):
    ws, ws_name = make_workspace_from_config(
        _basic_config("""    basic:
      workloads:
        test_wl:
          experiments:
            exp_1:
              variables:
                n_ranks: '1'
                n_nodes: '1'
"""),
        activate=True,
    )
    ws_root = os.path.abspath(ws.root)
    cfg_dir = os.path.abspath(ws.config_dir)
    exp1_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl", "exp_1"))
    ramble_root = os.path.abspath(ramble.paths.prefix)

    assert location().strip() == ws_root
    with pytest.raises(
        RambleCommandError, match="do not define a package-manager software environment"
    ):
        location("-s")

    assert location(global_args=["-W"]).strip() == ramble_root

    # Subcommand -W / --no-workspace mirrors top-level -W and preserves active_workspace
    ramble.workspace.activate(ws)
    assert location("-W").strip() == ramble_root
    assert location("--no-workspace").strip() == ramble_root
    assert ramble.workspace.active_workspace() is ws

    ramble.workspace.deactivate()
    assert location(global_args=["-w", ws_name]).strip() == ws_root
    assert location("configs", global_args=["-D", ws.root]).strip() == cfg_dir

    # Subcommand -w / --workspace and -D / --workspace-dir mirror top-level flags
    ramble.workspace.deactivate()
    for args, expected in [
        (["-w", ws_name], ws_root),
        ([f"--workspace={ws_name}"], ws_root),
        ([f"-w{ws_name}"], ws_root),
        (["-w", ws_name, "configs"], cfg_dir),
        ([f"--workspace={ws_name}", "configs"], cfg_dir),
        (["-w", ws_name, "exp_1"], exp1_dir),
        (["-w", ws_name, "-e", "exp_1"], exp1_dir),
        (["-D", ws.root], ws_root),
        ([f"--workspace-dir={ws.root}", "configs"], cfg_dir),
        (["-D", ws.root, "-e", "exp_1"], exp1_dir),
    ]:
        assert location(*args).strip() == expected
    assert ramble.workspace.active_workspace() is None

    with pytest.raises(RambleCommandError, match="both before and after"):
        location("-w", ws_name, global_args=["-w", ws_name])

    # Errors inside _scoped_workspace_context propagate cleanly without generator RuntimeError
    with pytest.raises(RambleCommandError, match="Unknown filter group 'no_such_group'"):
        location("-w", ws_name, "--fg", "no_such_group")


def test_location_developer_and_user_paths(tmpdir, monkeypatch):
    user_cfg = str(tmpdir.mkdir("user_ramble"))
    monkeypatch.setattr(ramble.paths, "user_config_path", user_cfg)

    expected_root = os.path.abspath(ramble.paths.prefix)
    expected_mod = os.path.abspath(ramble.paths.module_path)
    expected_builtin = os.path.abspath(ramble.paths.builtin_path)
    expected_repos = os.path.abspath(ramble.paths.repos_path)
    expected_user = os.path.abspath(user_cfg)

    for args, expected in [
        (["-r"], expected_root),
        (["--ramble-root"], expected_root),
        (["root"], expected_root),
        (["-m"], expected_mod),
        (["--module-dir"], expected_mod),
        (["module"], expected_mod),
        (["lib"], expected_mod),
        (["--builtin-repo"], expected_builtin),
        (["builtin"], expected_builtin),
        (["--repos-dir"], expected_repos),
        (["repos"], expected_repos),
        (["repos/builtin.mock"], os.path.abspath(ramble.paths.mock_builtin_path)),
        (["--user-config"], expected_user),
        (["user-config"], expected_user),
    ]:
        assert location(*args).strip() == expected

    # Uncreated user config path resolves via `ramble location`, unless `--existing` is passed
    uncreated_user = os.path.abspath(str(tmpdir.join("uncreated_user_ramble")))
    monkeypatch.setattr(ramble.paths, "user_config_path", uncreated_user)
    assert location("--user-config").strip() == uncreated_user
    assert location("user-config").strip() == uncreated_user

    with pytest.raises(RambleCommandError, match="does not exist"):
        location("--existing", "--user-config")

    # Static path flags also accept a relative <subpath>
    for args, expected in [
        (["-r", "share/ramble"], os.path.abspath(ramble.paths.share_path)),
        (["-m", "test/cmd/"], os.path.abspath(os.path.join(ramble.paths.test_path, "cmd"))),
        (
            ["--builtin-repo", "applications"],
            os.path.abspath(os.path.join(ramble.paths.builtin_path, "applications")),
        ),
        (["--repos-dir", "builtin.mock"], os.path.abspath(ramble.paths.mock_builtin_path)),
        (["--user-config", "configs"], os.path.join(uncreated_user, "configs")),
    ]:
        assert location(*args).strip() == expected

    with pytest.raises(RambleCommandError, match="must be a relative path"):
        location("-r", "/abs/subpath")

    with pytest.raises(RambleCommandError, match="Cannot combine experiment filter flags"):
        location("-r", "--where", "True")


def test_location_workspace_subdirs_and_fast_path(make_workspace_from_config, monkeypatch):
    ws, _ = make_workspace_from_config(
        _basic_config("""    basic:
      workloads:
        test_wl:
          experiments:
            scale_{n_nodes}:
              variables:
                n_ranks: '1'
                n_nodes: ['1', '2']
"""),
        activate=True,
    )

    # Resolving workspace subdirs or unrelated keywords should not build the ExperimentSet
    def _unexpected_build(*args, **kwargs):
        raise AssertionError("build_experiment_set should not be called for fast-path targets")

    monkeypatch.setattr(ws, "build_experiment_set", _unexpected_build)

    for target, expected_dir in [
        ("configs", ws.config_dir),
        ("configs/", ws.config_dir),
        ("experiments", ws.experiment_dir),
        ("inputs", ws.input_dir),
        ("logs", ws.log_dir),
        ("software", ws.software_dir),
        ("shared", ws.shared_dir),
        ("results", ws.results_dir),
        ("tables", ws.tables_dir),
        ("archive", ws.archive_dir),
        ("archives", ws.archive_dir),
        ("deployments", ws.deployments_dir),
        ("root", ramble.paths.prefix),
    ]:
        assert location(target).strip() == os.path.abspath(expected_dir)

    with pytest.raises(RambleCommandError, match="does not exist"):
        location("--existing", "results")

    fs.mkdirp(ws.results_dir)
    assert location("--existing", "results").strip() == os.path.abspath(ws.results_dir)


def test_location_broken_workspace_config_fallback(
    make_workspace_from_config, monkeypatch, capsys
):
    import ramble.main

    ws, _ = make_workspace_from_config("ramble:\n  applications: {}\n", activate=False)

    # Simulate a broken ramble.yaml when RAMBLE_WORKSPACE is set in the shell
    with open(ws.config_file_path, "w", encoding="utf-8") as f:
        f.write("ramble:\n  invalid_yaml: [unclosed\n")

    monkeypatch.setenv(ramble.workspace.RAMBLE_WORKSPACE_VAR, ws.root)
    capsys.readouterr()

    for argv, expected in [
        (["location"], ws.root),
        (["location", "-w"], ws.root),
        (["location", "configs"], ws.config_dir),
    ]:
        assert ramble.main._main(argv) == 0
        assert capsys.readouterr().out.strip() == os.path.abspath(expected)

    with pytest.raises(SystemExit):
        ramble.main._main(["location", "-e", "exp_1"])
    assert "configuration contains errors" in capsys.readouterr().err


def test_location_named_and_dir_workspaces(tmpdir):
    workspace("create", "ws_alpha")
    workspace("create", "ws_beta")

    alpha_root = os.path.abspath(ramble.workspace.root("ws_alpha"))
    beta_root = os.path.abspath(ramble.workspace.root("ws_beta"))

    assert location("ws_alpha").strip() == alpha_root
    assert location("ws_alpha/").strip() == alpha_root
    assert location("-w", "ws_beta").strip() == beta_root
    assert location("--workspace=ws_beta").strip() == beta_root
    assert location("ws_beta", "-w").strip() == beta_root

    with pytest.raises(RambleCommandError, match="No workspace is currently active"):
        location("-w")

    ramble.workspace.activate(ramble.workspace.read("ws_alpha"))
    assert location("-w").strip() == alpha_root
    assert location("ws_beta").strip() == beta_root

    dir_ws_path = str(tmpdir.join("dir_ws"))
    workspace("create", "-d", dir_ws_path)
    assert location("-w", dir_ws_path).strip() == os.path.abspath(dir_ws_path)
    assert location("-D", dir_ws_path).strip() == os.path.abspath(dir_ws_path)
    assert location("-D", f"{dir_ws_path}/configs").strip() == os.path.abspath(
        os.path.join(dir_ws_path, "configs")
    )

    with pytest.raises(RambleCommandError, match="No workspace in 'ws_alpha'"):
        location("-D", "ws_alpha")
    with pytest.raises(RambleCommandError, match="No such workspace: 'no_such_ws'"):
        location("-w", "no_such_ws")
    with pytest.raises(
        RambleCommandError, match="Cannot combine bare --workspace with experiment filter flags"
    ):
        location("-w", "--where", "True")


def test_location_experiments_workloads_applications_and_filters(make_workspace_from_config):
    ws, _ = make_workspace_from_config(
        _basic_config("""    basic:
      workloads:
        test_wl:
          experiments:
            scale_1:
              tags:
              - small
              variables:
                n_ranks: '1'
                n_nodes: '1'
            scale_2:
              tags:
              - large
              variables:
                n_ranks: '2'
                n_nodes: '2'
        test_wl2:
          experiments:
            single_run:
              variables:
                n_ranks: '1'
                n_nodes: '1'
"""),
        activate=True,
    )

    exp1_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl", "scale_1"))
    exp2_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl", "scale_2"))
    exp3_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl2", "single_run"))
    wl1_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl"))
    wl2_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl2"))
    app_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic"))

    # Before setup, `location` prints computed paths while `--existing` hints at `workspace setup`
    assert location("scale_1").strip() == exp1_dir
    assert location("*scale*").strip().splitlines() == [exp1_dir, exp2_dir]

    with pytest.raises(RambleCommandError, match="ramble workspace setup"):
        location("--existing", "scale_1")
    with pytest.raises(RambleCommandError, match="ramble workspace setup"):
        location("--existing", "*scale*")

    # Partial setup: `--existing` filters to materialized directories before `--first`
    fs.mkdirp(exp2_dir)
    assert location("*scale*").strip().splitlines() == [exp1_dir, exp2_dir]
    assert location("--existing", "*scale*").strip() == exp2_dir
    assert location("--existing", "--first", "*scale*").strip() == exp2_dir

    workspace("setup", "--dry-run")

    for args, expected in [
        (["basic.test_wl.scale_1"], exp1_dir),
        (["scale_1"], exp1_dir),
        (["-e", "scale_2"], exp2_dir),
        (["basic.test_wl"], wl1_dir),
        (["test_wl2"], wl2_dir),
        (["basic"], app_dir),
        (["*single*"], exp3_dir),
        (["*basic*"], app_dir),
        (["*scale*", "--first"], exp1_dir),
        (["-i", "1"], exp1_dir),
        (["-i", "2"], exp2_dir),
        (["-i", "3"], exp3_dir),
        (["--where", "{n_nodes} == 2"], exp2_dir),
        (["--where", "{n_nodes} == 1", "scale_1"], exp1_dir),
        (["scale_1", "--where", "{n_nodes} == 1"], exp1_dir),
        (["--exclude-where", "{n_nodes} == 1"], exp2_dir),
        (["--filter-tags", "large"], exp2_dir),
        (["--filter-tags", "small", "*scale*"], exp1_dir),
    ]:
        assert location(*args).strip() == expected

    assert location("test_wl*").strip().splitlines() == [wl1_dir, wl2_dir]
    assert location("*scale*").strip().splitlines() == [exp1_dir, exp2_dir]
    assert location("--where", "{n_nodes} == 1").strip().splitlines() == [exp1_dir, exp3_dir]

    with pytest.raises(RambleCommandError, match="No experiment with index '99'"):
        location("-i", "99")

    # Filter groups (--fg / --efg)
    workspace(
        "manage",
        "filter-groups",
        "--scope",
        "workspace",
        "add",
        "-n",
        "two-nodes",
        "--where",
        "{n_nodes} == 2",
    )
    assert location("--fg", "two-nodes").strip() == exp2_dir
    assert location("--efg", "two-nodes").strip().splitlines() == [exp1_dir, exp3_dir]
    assert location("--efg", "two-nodes", "--first").strip() == exp1_dir

    # --first-failed skips SUCCESS experiments
    with open(os.path.join(exp1_dir, "ramble_status.json"), "w", encoding="utf-8") as f:
        json_util.dump({"experiment_status": "SUCCESS"}, f)
    with open(os.path.join(exp2_dir, "ramble_status.json"), "w", encoding="utf-8") as f:
        json_util.dump({"experiment_status": "FAILED"}, f)
    assert location("--first-failed").strip() == exp2_dir


def test_location_software_env_and_input_dirs(make_workspace_from_config):
    ws, _ = make_workspace_from_config(
        _basic_config(
            """    zlib:
      workloads:
        ensure_installed:
          experiments:
            run_1:
              variables:
                n_ranks: '1'
                n_nodes: '1'
            run_2:
              variables:
                n_ranks: '2'
                n_nodes: '1'
""",
            extra=(
                "  variants:\n"
                "    package_manager: spack\n"
                "  software:\n"
                "    packages:\n"
                "      zlib:\n"
                "        pkg_spec: zlib\n"
                "    environments:\n"
                "      zlib:\n"
                "        packages:\n"
                "        - zlib\n"
            ),
        ),
        activate=True,
    )

    sw_env_dir = os.path.abspath(os.path.join(ws.software_dir, "spack", "zlib"))
    app_in_dir = os.path.abspath(os.path.join(ws.input_dir, "zlib"))
    wl_in_dir = os.path.abspath(os.path.join(ws.input_dir, "zlib", "ensure_installed"))

    assert location("-s").strip() == sw_env_dir
    assert location("--input-dir").strip() == wl_in_dir

    with pytest.raises(RambleCommandError, match="ramble workspace setup"):
        location("--existing", "-s")

    fs.mkdirp(sw_env_dir)
    fs.mkdirp(wl_in_dir)

    for args, expected in [
        (["--existing", "-s"], sw_env_dir),
        (["--existing", "--input-dir"], wl_in_dir),
        (["--software-env", "zlib"], sw_env_dir),
        (["--software-env", "run_2"], sw_env_dir),
        (["--input-dir", "ensure_installed"], wl_in_dir),
        (["--input-dir", "run_1"], wl_in_dir),
        (["--input-dir", "zlib"], app_in_dir),
    ]:
        assert location(*args).strip() == expected


def test_location_repeats_templates_and_chains(make_workspace_from_config):
    ws, _ = make_workspace_from_config(
        _basic_config("""    basic:
      workloads:
        test_wl:
          experiments:
            tpl_exp:
              template: true
              variables:
                n_ranks: '1'
                n_nodes: '1'
            primary_exp:
              variables:
                n_ranks: '1'
                n_nodes: '1'
              chained_experiments:
              - name: basic.test_wl.tpl_exp
                command: '{execute_experiment}'
            rep_exp:
              n_repeats: '2'
              variables:
                n_ranks: '1'
                n_nodes: '1'
"""),
        activate=True,
    )
    workspace("setup", "--dry-run")

    primary_dir = os.path.abspath(
        os.path.join(ws.experiment_dir, "basic", "test_wl", "primary_exp")
    )
    chained_dir = os.path.abspath(
        os.path.join(primary_dir, "chained_experiments", "chain.0.basic.test_wl.tpl_exp")
    )
    rep1_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl", "rep_exp.1"))
    rep2_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl", "rep_exp.2"))

    with pytest.raises(RambleCommandError, match="template experiment"):
        location("-i", "1")
    with pytest.raises(RambleCommandError, match="repeat base experiment"):
        location("-i", "3")

    assert location("-i", "2").strip() == primary_dir
    assert location("*chain*").strip() == chained_dir
    assert location("rep_exp").strip().splitlines() == [rep1_dir, rep2_dir]
    assert location("rep_exp", "--first").strip() == rep1_dir
    assert location("rep_exp.2").strip() == rep2_dir


def test_location_multi_app_workloads(make_workspace_from_config):
    ws, _ = make_workspace_from_config(
        _basic_config("""    basic:
      workloads:
        test_wl:
          experiments:
            exp_a:
              variables:
                n_ranks: '1'
                n_nodes: '1'
    tagged-1:
      workloads:
        test_wl:
          experiments:
            exp_b:
              variables:
                n_ranks: '1'
                n_nodes: '1'
"""),
        activate=True,
    )
    workspace("setup", "--dry-run")

    basic_wl_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl"))
    tagged_wl_dir = os.path.abspath(os.path.join(ws.experiment_dir, "tagged-1", "test_wl"))

    assert location("test_wl").strip().splitlines() == [basic_wl_dir, tagged_wl_dir]
    assert location("test_wl", "--first").strip() == basic_wl_dir
    assert location("tagged-1.test_wl").strip() == tagged_wl_dir


def test_location_priority_precedence_and_disambiguation(make_workspace_from_config):
    ws, _ = make_workspace_from_config(
        _basic_config("""    basic:
      workloads:
        test_wl:
          experiments:
            logs:
              variables:
                n_ranks: '1'
                n_nodes: '1'
            root:
              variables:
                n_ranks: '1'
                n_nodes: '1'
"""),
        activate=True,
    )
    workspace("setup", "--dry-run")

    # Workspace subdir 'logs' takes precedence over experiment 'logs'; -e selects the experiment
    assert location("logs").strip() == os.path.abspath(ws.log_dir)
    exp_logs_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl", "logs"))
    assert location("-e", "logs").strip() == exp_logs_dir

    # Experiment 'root' takes precedence over ramble keyword 'root'; -r selects ramble root
    exp_root_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl", "root"))
    assert location("root").strip() == exp_root_dir
    assert location("-r").strip() == os.path.abspath(ramble.paths.prefix)


def test_location_target_subpaths(make_workspace_from_config, tmpdir):
    workspace("create", "ws_other")
    other_root = os.path.abspath(ramble.workspace.root("ws_other"))

    dir_ws = str(tmpdir.join("dir_ws_sub"))
    workspace("create", "-d", dir_ws)

    ws, _ = make_workspace_from_config(
        _basic_config("""    basic:
      workloads:
        test_wl:
          experiments:
            scale_1:
              variables:
                n_ranks: '1'
                n_nodes: '1'
"""),
        activate=True,
    )
    workspace("setup", "--dry-run")

    exp1_dir = os.path.abspath(os.path.join(ws.experiment_dir, "basic", "test_wl", "scale_1"))
    exp1_sub = os.path.join(exp1_dir, "sub_output")
    fs.mkdirp(exp1_sub)

    for args, expected in [
        (["shared/licenses"], os.path.abspath(ws.shared_license_dir)),
        (["shared/utilities/"], os.path.abspath(ws.shared_utilities_dir)),
        (["configs//auxiliary_software_files"], os.path.abspath(ws.auxiliary_software_dir)),
        (["basic/test_wl/scale_1"], exp1_dir),
        (["scale_1/sub_output"], exp1_sub),
        (["-e", "scale_1/sub_output"], exp1_sub),
        (["scale_1/no_such_subdir"], os.path.join(exp1_dir, "no_such_subdir")),
        (["ws_other/configs"], os.path.join(other_root, "configs")),
        (["-w", "ws_other/shared/licenses"], os.path.join(other_root, "shared", "licenses")),
        ([f"{dir_ws}/configs"], os.path.abspath(os.path.join(dir_ws, "configs"))),
    ]:
        assert location(*args).strip() == expected

    with pytest.raises(RambleCommandError) as exc_info:
        location("--existing", "scale_1/no_such_subdir")
    assert "does not exist" in str(exc_info.value)
    assert "ramble workspace setup" not in str(exc_info.value)

    # Keyword subpaths (even when cwd is inside a directory workspace)
    with fs.working_dir(dir_ws):
        assert location("root/share/ramble").strip() == os.path.abspath(ramble.paths.share_path)
        assert location("module/test/cmd").strip() == os.path.abspath(
            os.path.join(ramble.paths.test_path, "cmd")
        )
        assert location("builtin/applications").strip() == os.path.abspath(
            os.path.join(ramble.paths.builtin_path, "applications")
        )


def test_location_custom_repositories(tmpdir):
    repo_cmd = RambleCommand("repo")

    custom_repo_dir = os.path.abspath(str(tmpdir.join("my_custom_repo")))
    repo_cmd("create", custom_repo_dir, "my_lab")
    repo_cmd("add", custom_repo_dir)

    unregistered_repo_dir = os.path.abspath(str(tmpdir.join("unregistered_repo")))
    repo_cmd("create", unregistered_repo_dir, "unreg_ns")

    repo_lines = location("--repo").strip().splitlines()
    assert len(repo_lines) >= 2
    assert repo_lines[0] == custom_repo_dir

    custom_apps_dir = os.path.join(custom_repo_dir, "applications")
    for args, expected in [
        (["--repo", "--first"], custom_repo_dir),
        (["--repo", "my_lab"], custom_repo_dir),
        (["--repo=my_lab"], custom_repo_dir),
        (["my_lab", "--repo"], custom_repo_dir),
        (["--repo", "my_lab/applications"], custom_apps_dir),
        (["--repo", "my_lab", "applications"], custom_apps_dir),
        (["--repo", unregistered_repo_dir], unregistered_repo_dir),
        (
            ["--repo", f"{unregistered_repo_dir}/applications"],
            os.path.join(unregistered_repo_dir, "applications"),
        ),
        (["my_lab"], custom_repo_dir),
        (["--first", "my_lab"], custom_repo_dir),
        (["my_lab/applications"], custom_apps_dir),
    ]:
        assert location(*args).strip() == expected

    # Named workspace 'my_lab' takes precedence over repository 'my_lab'; --repo selects the repo
    workspace("create", "my_lab")
    assert location("my_lab").strip() == os.path.abspath(ramble.workspace.root("my_lab"))
    assert location("--repo", "my_lab").strip() == custom_repo_dir

    with pytest.raises(RambleCommandError, match="No such repository: 'no_such_repo_ns'"):
        location("--repo", "no_such_repo_ns")
    with pytest.raises(
        RambleCommandError, match="Cannot combine --repo with experiment filter flags"
    ):
        location("--repo", "my_lab", "--where", "True")
