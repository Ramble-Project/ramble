# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.error
import ramble.workspace
from ramble.main import RambleCommand

pytestmark = pytest.mark.usefixtures("mutable_mock_workspace_path")


workspace = RambleCommand("workspace")


def test_manage_variable_multiple_equals(workspace_name, tmpdir):
    ws = ramble.workspace.create(workspace_name)

    global_args = ["-w", workspace_name]

    # Highest precedence, experiment scope
    workspace(
        "manage",
        "experiments",
        "gromacs",
        "--wf",
        "water_bare",
        "-v",
        "n_nodes=1",
        "-v",
        "n_ranks=1",
        "-v",
        "test_var=foo=bar",
        "-v",
        "test_list_var=[ val1 = val2, val3=val4]",
        "-v",
        "test_other_var = test1=test2=test3",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )

    tests = [
        "test_var: foo=bar",
        "test_list_var:",
        "- val1 = val2",
        "- val3=val4",
        "test_other_var: test1=test2=test3",
    ]

    results = [False for _ in tests]

    with open(ws.config_file_path, encoding="utf-8") as f:
        for line in f:
            for idx, test_str in enumerate(tests):
                if test_str in line:
                    results[idx] = True

    assert all(results)


def test_manage_experiments_no_overwrite_wm_vars(workspace_name):
    ws = ramble.workspace.create(workspace_name)
    global_args = ["-w", workspace_name]
    workspace(
        "manage",
        "experiments",
        "gromacs",
        "--wf",
        "water_bare",
        "-V",
        "workflow_manager=user-managed",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )
    with open(ws.config_file_path, encoding="utf-8") as f:
        content = f.read()
        assert "processes_per_node:" in content
        assert "batch_submit" not in content
        assert "mpi_command" not in content


def _namespace_vars_absent(section):
    return "variables" not in section


def test_manage_variables_scopes_lists_and_removal(workspace_name):
    ws = ramble.workspace.create(workspace_name)
    ws.write()
    global_args = ["-w", workspace_name]

    # Seed an experiment so application, workload, and experiment scopes exist
    workspace(
        "manage",
        "experiments",
        "gromacs",
        "--wf",
        "water_bare",
        "-e",
        "exp1",
        "--default-variable-value",
        "1",
        global_args=global_args,
    )

    # Add to workspace scope (default when -s is omitted), including list & '=' values
    add_ws = workspace(
        "manage",
        "variables",
        "--add",
        "-v",
        "omp=4",
        "-v",
        "ranks=[1, 2]",
        "-v",
        "expr=a=b",
        global_args=global_args,
    )
    assert "Added 3 variables to workspace." in add_ws

    # Add to application, workload, and experiment scopes
    add_app = workspace(
        "manage",
        "variables",
        "--add",
        "-s",
        "gromacs",
        "-v",
        "app_var=app_val",
        global_args=global_args,
    )
    assert "Added 1 variable to workspace." in add_app

    workspace(
        "manage",
        "variables",
        "--add",
        "-s",
        "gromacs:water_bare",
        "-v",
        "wl_var=wl_val",
        global_args=global_args,
    )
    workspace(
        "manage",
        "variables",
        "--add",
        "-s",
        "gromacs:water_bare:exp1",
        "-v",
        "exp_var=exp_val",
        global_args=global_args,
    )

    list_out = workspace("manage", "variables", "--list", global_args=global_args)
    assert "Variable scope: workspace" in list_out
    assert "omp = 4" in list_out
    assert "ranks = ['1', '2']" in list_out
    assert "expr = a=b" in list_out
    assert "Variable scope: gromacs" in list_out
    assert "app_var = app_val" in list_out
    assert "Variable scope: gromacs:water_bare" in list_out
    assert "wl_var = wl_val" in list_out
    assert "Variable scope: gromacs:water_bare:exp1" in list_out
    assert "exp_var = exp_val" in list_out
    assert "Additional variables may come from other config scopes" in list_out

    # Remove by glob across scopes
    rem_glob = workspace(
        "manage",
        "variables",
        "--remove",
        "-s",
        "gromacs*",
        "-v",
        "*_var",
        global_args=global_args,
    )
    assert "Removed 3 variables from workspace." in rem_glob

    # Remove by index (0 = omp)
    rem_idx = workspace(
        "manage",
        "variables",
        "--remove",
        "-i",
        "0",
        global_args=global_args,
    )
    assert "Removed 1 variable from workspace." in rem_idx

    # Remove remaining workspace variables with default pattern ('*') & verify cleanup
    rem_rest = workspace(
        "manage",
        "variables",
        "--remove",
        "-s",
        "workspace",
        global_args=global_args,
    )
    assert "Removed " in rem_rest
    assert "from workspace." in rem_rest

    ramble.workspace.activate(ws)
    ws._re_read()
    assert _namespace_vars_absent(ws._get_scope_section("workspace"))
    remaining_names = {name for _, name, _ in ws.index_variables()}
    assert remaining_names.isdisjoint({"omp", "ranks", "expr", "app_var", "wl_var", "exp_var"})


def test_manage_variables_overwrite_and_dry_run(workspace_name):
    ws = ramble.workspace.create(workspace_name)
    ws.write()
    global_args = ["-w", workspace_name]

    workspace("manage", "variables", "--add", "-v", "omp=4", global_args=global_args)

    # Conflict without --overwrite fails
    with pytest.raises((ramble.error.RambleCommandError, ramble.error.RambleError)):
        workspace("manage", "variables", "--add", "-v", "omp=8", global_args=global_args)

    # Overwrite updates value
    workspace(
        "manage",
        "variables",
        "--add",
        "-o",
        "-v",
        "omp=8",
        global_args=global_args,
    )

    # --dry-run prints config without persisting changes
    dry_add = workspace(
        "manage",
        "variables",
        "--add",
        "--dry-run",
        "-v",
        "dryvar=1",
        global_args=global_args,
    )
    assert "dryvar: '1'" in dry_add

    dry_rem = workspace(
        "manage",
        "variables",
        "--remove",
        "--dry-run",
        "-s",
        "workspace",
        "-v",
        "omp",
        global_args=global_args,
    )
    assert "Removed 1 variable from workspace." in dry_rem

    ramble.workspace.activate(ws)
    ws._re_read()
    vars_after = ws.index_variables()
    assert ("workspace", "omp", "8") in vars_after
    assert all(name != "dryvar" for _, name, _ in vars_after)


def test_manage_variables_validation_errors(workspace_name):
    ws = ramble.workspace.create(workspace_name)
    ws.write()
    global_args = ["-w", workspace_name]

    invalid_invocations = [
        ("manage", "variables", "--add"),
        ("manage", "variables", "--add", "-v", "justaname"),
        ("manage", "variables", "--add", "-v", "application_name=x"),
        ("manage", "variables", "--add", "-s", "nosuchapp", "-v", "a=1"),
        ("manage", "variables", "--remove"),
        ("manage", "variables", "--remove", "-i", "0", "-s", "workspace"),
        ("manage", "variables", "--remove", "-i", "0", "-v", "a"),
        ("manage", "variables", "--remove", "-i", "99"),
    ]
    for cmd_args in invalid_invocations:
        with pytest.raises((ramble.error.RambleCommandError, ramble.error.RambleError)):
            workspace(*cmd_args, global_args=global_args)


_TEST_MODIFIERS = ["lscpu", "ethtool"]


def _workspace_with_two_modifiers(workspace_name):
    """Create a workspace containing two workspace-scoped modifiers.

    Uses ``workspace manage modifiers`` rather than raw YAML so the setup
    exercises the same path a user would take.
    """
    ws = ramble.workspace.create(workspace_name)
    ws.write()
    global_args = ["-w", workspace_name]

    for mod_name in _TEST_MODIFIERS:
        workspace(
            "manage",
            "modifiers",
            "--add",
            "--name",
            mod_name,
            "--scope",
            "workspace",
            global_args=global_args,
        )

    ws._re_read()
    assert [mod[1]["name"] for mod in ws.index_modifiers()] == _TEST_MODIFIERS
    return ws


@pytest.mark.parametrize(
    "remove_index",
    [
        # Equal to len(mod_list). Regression test for an off-by-one in the
        # bounds check that let this through and raised a bare IndexError.
        2,
        3,
        99,
        -1,
    ],
)
def test_remove_modifier_out_of_range_index_errors(workspace_name, remove_index):
    """Out-of-range indices raise a RambleWorkspaceError, not an IndexError."""
    ws = _workspace_with_two_modifiers(workspace_name)

    with pytest.raises(ramble.workspace.RambleWorkspaceError, match="outside of the range"):
        ws.remove_modifier(remove_index=remove_index)

    # A rejected removal must not modify the workspace.
    assert len(ws.index_modifiers()) == 2


def test_remove_modifier_out_of_range_index_messages(workspace_name):
    """Out-of-range error messages format singular vs plural ranges correctly."""
    ws = ramble.workspace.create(workspace_name)
    ws.write()
    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "modifiers",
        "--add",
        "--name",
        "lscpu",
        "--scope",
        "workspace",
        global_args=global_args,
    )
    ws._re_read()

    with pytest.raises(ramble.workspace.RambleWorkspaceError, match=r"Valid index is 0\."):
        ws.remove_modifier(remove_index=1)

    workspace(
        "manage",
        "modifiers",
        "--add",
        "--name",
        "ethtool",
        "--scope",
        "workspace",
        global_args=global_args,
    )
    ws._re_read()

    with pytest.raises(ramble.workspace.RambleWorkspaceError, match=r"Valid indices are 0-1\."):
        ws.remove_modifier(remove_index=2)


def test_remove_modifier_index_on_empty_workspace_errors(workspace_name):
    """Removing by index with no modifiers defined gives a clear error."""
    ws = ramble.workspace.create(workspace_name)

    assert ws.index_modifiers() == []

    with pytest.raises(ramble.workspace.RambleWorkspaceError, match="contains no modifiers"):
        ws.remove_modifier(remove_index=0)


@pytest.mark.parametrize("remove_index", ["1", 1.0, True, object()])
def test_remove_modifier_non_integer_index_errors(workspace_name, remove_index):
    """Non-integer indices are rejected rather than silently indexing the list.

    ``True`` is included deliberately: ``bool`` is a subclass of ``int``, so an
    unguarded check would index the list with it.
    """
    ws = _workspace_with_two_modifiers(workspace_name)

    with pytest.raises(ramble.workspace.RambleWorkspaceError, match="integer index"):
        ws.remove_modifier(remove_index=remove_index)

    assert len(ws.index_modifiers()) == 2


@pytest.mark.parametrize(
    "remove_index,expected_remaining",
    [(0, "ethtool"), (1, "lscpu")],
)
def test_remove_modifier_valid_index_removes_expected(
    workspace_name, remove_index, expected_remaining
):
    """Valid indices, including the last one, remove the correct modifier."""
    ws = _workspace_with_two_modifiers(workspace_name)

    removed = ws.remove_modifier(remove_index=remove_index)

    assert removed == 1
    remaining = ws.index_modifiers()
    assert len(remaining) == 1
    assert remaining[0][1]["name"] == expected_remaining


def test_add_modifier_without_scope_uses_workspace_scope(workspace_name):
    """``--scope`` is optional when adding, and defaults to the workspace scope."""
    ws = ramble.workspace.create(workspace_name)
    ws.write()

    workspace(
        "manage",
        "modifiers",
        "--add",
        "--name",
        "lscpu",
        global_args=["-w", workspace_name],
    )

    ws._re_read()
    assert ws.index_modifiers() == [("workspace", {"name": "lscpu"})]


def test_add_modifier_unknown_name_errors(workspace_name):
    """An unmatched name pattern is a fatal error, not a warning plus a no-op."""
    ws = ramble.workspace.create(workspace_name)
    ws.write()

    with pytest.raises(ramble.workspace.RambleWorkspaceError, match="No modifiers found matching"):
        workspace(
            "manage",
            "modifiers",
            "--add",
            "--name",
            "definitely-no-such-modifier",
            "--scope",
            "workspace",
            global_args=["-w", workspace_name],
        )

    # A rejected add must leave the config completely untouched, including
    # not creating an empty `modifiers` list.
    ws._re_read()
    assert ws.index_modifiers() == []
    with open(ws.config_file_path, encoding="utf-8") as f:
        assert "modifiers" not in f.read()


def test_add_modifier_without_name_errors(workspace_name):
    """Adding without a name pattern is rejected at the CLI layer."""
    ws = ramble.workspace.create(workspace_name)
    ws.write()

    with pytest.raises(ramble.error.RambleCommandError, match="requires --name"):
        workspace(
            "manage",
            "modifiers",
            "--add",
            "--scope",
            "workspace",
            global_args=["-w", workspace_name],
        )

    ws._re_read()
    assert ws.index_modifiers() == []


@pytest.mark.parametrize("name_pattern", [None, "", 1, ["lscpu"]])
def test_add_modifier_invalid_name_pattern_errors(workspace_name, name_pattern):
    """The method guards its own preconditions, for callers bypassing the CLI."""
    ws = ramble.workspace.create(workspace_name)
    ws.write()

    with pytest.raises(ramble.workspace.RambleWorkspaceError, match="without a name pattern"):
        ws.add_modifier(name_pattern=name_pattern, scope="workspace")


@pytest.mark.parametrize(
    "pattern_args",
    [
        ["--scope", "workspace"],
        ["--name", "lscpu"],
        ["--mode", "standard"],
        ["--scope", "workspace", "--name", "lscpu"],
    ],
)
def test_remove_modifier_index_with_pattern_errors(workspace_name, pattern_args):
    """Index and pattern selection are alternatives, not a union.

    Combining them used to remove every pattern-matching modifier in addition
    to the indexed one.
    """
    ws = _workspace_with_two_modifiers(workspace_name)

    with pytest.raises(ramble.error.RambleCommandError, match="not both"):
        workspace(
            "manage",
            "modifiers",
            "--remove",
            "--mod-index",
            "0",
            *pattern_args,
            global_args=["-w", workspace_name],
        )

    ws._re_read()
    assert [mod[1]["name"] for mod in ws.index_modifiers()] == _TEST_MODIFIERS


def test_remove_modifier_index_with_pattern_api_errors(workspace_name):
    """The method rejects the combination for callers bypassing the CLI."""
    ws = _workspace_with_two_modifiers(workspace_name)

    with pytest.raises(ramble.workspace.RambleWorkspaceError, match="not both"):
        ws.remove_modifier(remove_index=0, scope_pattern="workspace")

    assert len(ws.index_modifiers()) == 2


def test_remove_modifier_mode_pattern_filters_correctly(workspace_name):
    """Removing by mode_pattern only removes modifiers whose mode matches."""
    ws = ramble.workspace.create(workspace_name)
    ws.write()
    global_args = ["-w", workspace_name]

    workspace(
        "manage",
        "modifiers",
        "--add",
        "--name",
        "lscpu",
        "--mode",
        "standard",
        "--scope",
        "workspace",
        global_args=global_args,
    )
    workspace(
        "manage",
        "modifiers",
        "--add",
        "--name",
        "ethtool",
        "--scope",
        "workspace",
        global_args=global_args,
    )
    ws._re_read()
    assert len(ws.index_modifiers()) == 2

    # Non-matching mode pattern should remove nothing
    removed = ws.remove_modifier(scope_pattern="workspace", mode_pattern="nonexistent")
    assert removed == 0
    assert len(ws.index_modifiers()) == 2

    # Matching mode pattern should only remove the modifier with mode="standard"
    removed = ws.remove_modifier(scope_pattern="workspace", mode_pattern="standard")
    assert removed == 1
    remaining = ws.index_modifiers()
    assert len(remaining) == 1
    assert remaining[0][1]["name"] == "ethtool"
