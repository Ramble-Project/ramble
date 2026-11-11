# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import argparse
import contextlib
import fnmatch
import operator
import os
import re
import sys
from typing import Any, Callable, Dict, Iterable, Iterator, List, NamedTuple, Optional, Tuple

from llnl.util.lang import dedupe

import ramble.cmd
import ramble.config
import ramble.filters
import ramble.keywords
import ramble.paths
import ramble.repository
import ramble.util.path
import ramble.workspace
from ramble.cmd.common import arguments
from ramble.expander import Expander
from ramble.experiment_result import ExperimentStatus
from ramble.namespace import namespace
from ramble.util.logger import logger

description = "print out locations of ramble directories, workspaces, and experiments"
section = "workspaces"
level = "short"

_INNER_BRACE_RE = re.compile(r"\{[^{}]*\}")
_GLOB_CHARS = frozenset("*?[")


class _SelectionOpts(NamedTuple):
    limit_one: bool
    existing: bool
    warn_implicit_first: bool = False


def setup_parser(subparser):
    ws_modes = subparser.add_mutually_exclusive_group()
    ws_modes.add_argument(
        "-w",
        "--workspace",
        nargs="?",
        const=True,
        default=None,
        dest="sub_workspace",
        metavar="WRKSPC",
        help="workspace name or path (or active workspace root when given with no value)",
    )
    ws_modes.add_argument(
        "-D",
        "--workspace-dir",
        action="store",
        default=None,
        dest="sub_workspace_dir",
        metavar="DIR",
        help="run with or locate a workspace directory (ignore named workspaces)",
    )
    ws_modes.add_argument(
        "-W",
        "--no-workspace",
        action="store_true",
        default=False,
        dest="sub_no_workspace",
        help="run without any workspaces activated",
    )

    modes = subparser.add_mutually_exclusive_group()
    modes.add_argument(
        "-e",
        "--experiment",
        action="store_true",
        dest="as_experiment",
        default=False,
        help="treat target as an experiment, workload, or application filter",
    )
    modes.add_argument(
        "-s",
        "--software-env",
        action="store_true",
        dest="software_env",
        default=False,
        help="locate the software environment directory for the matched experiment or workload",
    )
    modes.add_argument(
        "--input-dir",
        action="store_true",
        dest="input_dir",
        default=False,
        help="locate the input directory for the matched workload, experiment, or application",
    )
    modes.add_argument(
        "-r",
        "--ramble-root",
        action="store_const",
        dest="static_path_attr",
        const="prefix",
        default=None,
        help="ramble installation root directory ($RAMBLE_ROOT)",
    )
    modes.add_argument(
        "-m",
        "--module-dir",
        action="store_const",
        dest="static_path_attr",
        const="module_path",
        help="ramble's python module directory ($RAMBLE_ROOT/lib/ramble/ramble)",
    )
    modes.add_argument(
        "--user-config",
        action="store_const",
        dest="static_path_attr",
        const="user_config_path",
        help="user configuration directory (~/.ramble)",
    )
    modes.add_argument(
        "--builtin-repo",
        action="store_const",
        dest="static_path_attr",
        const="builtin_path",
        help="built-in object repository ($RAMBLE_ROOT/var/ramble/repos/builtin)",
    )
    modes.add_argument(
        "--repo",
        nargs="?",
        const=True,
        default=None,
        dest="sub_repo",
        metavar="REPO",
        help="object repository namespace or path (or all configured repos when given no value)",
    )
    modes.add_argument(
        "--repos-dir",
        action="store_const",
        dest="static_path_attr",
        const="repos_path",
        help="built-in repositories parent directory ($RAMBLE_ROOT/var/ramble/repos)",
    )

    subparser.add_argument(
        "-i",
        "--index",
        type=int,
        dest="index",
        default=None,
        metavar="N",
        help="select the primary experiment with the given 1-indexed experiment_index",
    )
    subparser.add_argument(
        "--first",
        "--limit-one",
        action="store_true",
        dest="limit_one",
        default=False,
        help="if multiple locations match, only return the first match",
    )
    subparser.add_argument(
        "--existing",
        action="store_true",
        dest="existing",
        default=False,
        help="only return directory paths that currently exist on disk",
    )
    subparser.add_argument(
        "--first-failed",
        action="store_true",
        dest="first_failed",
        default=False,
        help="select the first non-successful experiment in the active workspace",
    )
    # Single-argument options (unlike common arguments' nargs='+') so [target] is preserved
    subparser.add_argument(
        "--where",
        action="append",
        dest="where",
        default=None,
        metavar="EXPR",
        help="inclusive filter on experiments where the provided logical statement is True",
    )
    subparser.add_argument(
        "--exclude-where",
        action="append",
        dest="exclude_where",
        default=None,
        metavar="EXPR",
        help="exclusive filter on experiments where the provided logical statement is True",
    )
    subparser.add_argument(
        "--filter-tags",
        action="append",
        dest="filter_tags",
        default=None,
        metavar="TAG",
        help="filter experiments to only those that include the provided tag",
    )

    arguments.add_common_arguments(
        subparser,
        ["filter_group", "exclude_filter_group"],
    )

    subparser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="workspace subdirectory, experiment/workload/application name or glob, "
        "workspace name, repository namespace, or ramble path keyword "
        "(root, module, lib, user-config, builtin, repos)",
    )


def _cmd_name(args) -> str:
    return "cd" if getattr(args, "command", None) == "cd" else "location"


def _ramble_keywords() -> Dict[str, str]:
    return {
        "root": ramble.paths.prefix,
        "module": ramble.paths.module_path,
        "lib": ramble.paths.module_path,
        "user-config": ramble.paths.user_config_path,
        "builtin": ramble.paths.builtin_path,
        "repos": ramble.paths.repos_path,
    }


def _workspace_subdirs(ws_root: str) -> Dict[str, str]:
    subdirs = {
        os.path.basename(p): p
        for p in ramble.workspace.Workspace.get_workspace_paths(ws_root).values()
        if p != ws_root
    }
    subdirs["archives"] = subdirs["archive"]
    return subdirs


def _has_experiment_selection_flags(args) -> bool:
    return bool(
        args.index is not None
        or args.where
        or args.exclude_where
        or args.filter_tags
        or args.filter_group
        or args.exclude_filter_group
        or args.first_failed
    )


def _has_experiment_mode(args) -> bool:
    return bool(
        args.as_experiment
        or args.software_env
        or args.input_dir
        or _has_experiment_selection_flags(args)
    )


def _get_workspace_context(
    args,
) -> Tuple[Optional[ramble.workspace.Workspace], Optional[str], Optional[str]]:
    ws = ramble.workspace.active_workspace()
    if ws is not None:
        return ws, ws.root, ws.name

    if not getattr(args, "no_workspace", False):
        try:
            ws_root = ramble.cmd.find_workspace_path(args)
        except ramble.workspace.RambleWorkspaceError:
            ws_root = None
        if ws_root:
            canonical_root = ramble.util.path.canonicalize_path(ws_root)
            return None, canonical_root, os.path.basename(canonical_root)

    return None, None, None


def _normalize_target(raw_target: Optional[str]) -> Optional[str]:
    if raw_target is None or raw_target == "/":
        return raw_target
    return raw_target.rstrip("/") or raw_target


def _split_head_and_subpath(norm_target: str) -> Tuple[str, Optional[str]]:
    if (
        "/" in norm_target
        and not os.path.isabs(norm_target)
        and not norm_target.startswith(("./", "../"))
        and norm_target not in (".", "..")
    ):
        head, raw_sub = norm_target.split("/", 1)
        return head, (raw_sub.lstrip("/") or None)
    return norm_target, None


def _join_subpath(base_path: str, subpath: Optional[str]) -> str:
    return os.path.abspath(os.path.join(base_path, subpath) if subpath else base_path)


def _walk_ancestor_dir(stripped: str, predicate: Callable[[str], bool]) -> Optional[str]:
    if "/" not in stripped:
        return None
    cur = os.path.dirname(stripped)
    while cur and cur not in (".", "..", "/"):
        if predicate(cur):
            return os.path.abspath(os.path.join(cur, os.path.relpath(stripped, cur)))
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    return None


def _resolve_workspace_target(target: str, allow_named: bool = True) -> Optional[str]:
    stripped = target.rstrip("/") or target
    if allow_named and ramble.workspace.exists(stripped):
        return ramble.workspace.root(stripped)
    if ramble.workspace.is_workspace_dir(stripped):
        return os.path.abspath(stripped)
    if (
        allow_named
        and "/" in stripped
        and not os.path.isabs(stripped)
        and not stripped.startswith(("./", "../"))
    ):
        head, raw_sub = stripped.split("/", 1)
        if ramble.workspace.exists(head):
            return _join_subpath(ramble.workspace.root(head), raw_sub.lstrip("/") or None)
    return _walk_ancestor_dir(stripped, ramble.workspace.is_workspace_dir)


@contextlib.contextmanager
def _scoped_workspace_context(mode: Optional[str], value: Optional[str]):
    """Temporarily override active workspace context for subcommand -w/-D/-W."""
    if mode is None:
        yield None
        return

    with ramble.workspace.no_active_workspace():
        if mode == "no_workspace" or value is None:
            yield (None, None, None)
            return

        stripped = value.rstrip("/") or value
        ws_args = argparse.Namespace(
            workspace=stripped if mode == "workspace" else None,
            workspace_dir=stripped if mode == "workspace_dir" else None,
        )
        try:
            raw_root = ramble.cmd.find_workspace_path(ws_args)
        except ramble.workspace.RambleWorkspaceError:
            raw_root = None

        if not raw_root:
            msg = (
                f"No such workspace: '{value}'"
                if mode == "workspace"
                else f"No workspace in '{value}'"
            )
            logger.die(msg)
            yield (None, None, None)
            return

        ws_root = ramble.util.path.canonicalize_path(raw_root)
        ws_name = (
            stripped
            if (mode == "workspace" and ramble.workspace.exists(stripped))
            else os.path.basename(ws_root)
        )
        try:
            ws_obj = ramble.cmd.find_workspace(ws_args)
        except Exception:
            ws_obj = None

        if ws_obj is not None:
            with ws_obj:
                yield (ws_obj, ws_obj.root, ws_obj.name)
        else:
            yield (None, ws_root, ws_name)


def _iter_registered_repos() -> List[Tuple[str, str]]:
    """Return (namespace, root_path) pairs for all configured repos in precedence order."""
    seen_roots = set()
    entries: List[Tuple[str, str]] = []
    obj_types = [ramble.repository.default_type] + [
        t for t in ramble.repository.ObjectTypes if t != ramble.repository.default_type
    ]
    for obj_type in obj_types:
        type_def = ramble.repository.type_definitions[obj_type]
        for raw_root in ramble.config.get(type_def["config_section"]) or []:
            canon_root = ramble.util.path.canonicalize_path(str(raw_root))
            if canon_root in seen_roots:
                continue
            try:
                repo = ramble.repository.Repo(raw_root, obj_type)
            except ramble.repository.RepoError:
                continue
            seen_roots.add(canon_root)
            entries.append((repo.namespace, os.path.abspath(repo.root)))
    return entries


def _is_repo_dir(path: str) -> bool:
    if not os.path.isdir(path):
        return False
    for obj_type in ramble.repository.ObjectTypes:
        try:
            ramble.repository.Repo(path, obj_type)
            return True
        except ramble.repository.RepoError:
            continue
    return False


def _resolve_repo_targets(target: str) -> List[str]:
    stripped = target.rstrip("/")
    if not stripped:
        return []

    if not (os.path.isabs(stripped) or stripped.startswith(("./", "../"))):
        head, subpath = _split_head_and_subpath(stripped)
        matches = [
            _join_subpath(root, subpath) for ns, root in _iter_registered_repos() if ns == head
        ]
        if matches:
            return matches

    if _is_repo_dir(stripped):
        return [os.path.abspath(stripped)]

    ancestor_hit = _walk_ancestor_dir(stripped, _is_repo_dir)
    return [ancestor_hit] if ancestor_hit else []


def _template_to_glob(key: str) -> str:
    prev = None
    cur = key
    while prev != cur:
        prev = cur
        cur = _INNER_BRACE_RE.sub("*", cur)
    return "*" if ("{" in cur or "}" in cur) else cur


def _iter_raw_config_names(app_dict: Dict[Any, Any]) -> Iterator[str]:
    for app_key, app_contents in app_dict.items():
        app_key_str = str(app_key)
        app_base, _, _ = app_key_str.partition("@")
        yield app_key_str
        yield app_base
        yield app_base.rsplit(".", 1)[-1]
        workloads = (
            app_contents.get(namespace.workload) if isinstance(app_contents, dict) else None
        )
        if not isinstance(workloads, dict):
            continue
        for wl_key, wl_contents in workloads.items():
            yield str(wl_key)
            experiments = (
                wl_contents.get(namespace.experiment) if isinstance(wl_contents, dict) else None
            )
            if isinstance(experiments, dict):
                for exp_key in experiments:
                    yield str(exp_key)


def _may_match_in_workspace_config(target: str) -> bool:
    """Fast conservative check against raw workspace config before building ExperimentSet."""
    if not target or "." in target or any(c in _GLOB_CHARS for c in target):
        return True
    app_dict = ramble.config.get(namespace.application)
    if not isinstance(app_dict, dict) or not app_dict:
        return False
    return any(
        fnmatch.fnmatchcase(target, _template_to_glob(name))
        for name in _iter_raw_config_names(app_dict)
    )


def _build_and_filter_experiments(
    ws: ramble.workspace.Workspace, args
) -> Tuple[Any, List[Tuple[str, Any, int]]]:
    where_filter = [[v] if isinstance(v, str) else list(v) for v in (args.where or [])]
    where_filter = ramble.filters.resolve_and_apply_filter_groups(args, where_filter)
    exclude_filter = [[v] if isinstance(v, str) else list(v) for v in (args.exclude_where or [])]

    if args.first_failed:
        status_key = ramble.keywords.keywords.experiment_status
        exclude_filter.append([f"'{{{status_key}}}' == '{ExperimentStatus.SUCCESS.value}'"])

    tags = (
        [
            [t for t in v.split(",") if t] if isinstance(v, str) else list(v)
            for v in args.filter_tags
        ]
        if args.filter_tags
        else None
    )

    filters = ramble.filters.Filters(
        include_where_filters=where_filter,
        exclude_where_filters=exclude_filter,
        tags=tags,
    )

    experiment_set = ws.build_experiment_set(
        die_on_validate_error=False,
        check_environments=False,
    )

    filtered: List[Tuple[str, Any, int]] = []
    for exp, app_inst, idx in experiment_set.filtered_experiments(filters):
        if app_inst.is_template or app_inst.repeats.is_repeat_base:
            continue
        if args.index is not None and exp in experiment_set.chained_experiments:
            continue
        exp_idx_str = app_inst.expander.expand_var_name(app_inst.keywords.experiment_index)
        try:
            exp_idx = int(exp_idx_str)
        except (ValueError, TypeError):
            exp_idx = idx
        if args.index is not None and exp_idx != args.index:
            continue
        filtered.append((exp, app_inst, exp_idx))

    return experiment_set, filtered


def _die_missing_index(ws: ramble.workspace.Workspace, experiment_set, target_index: int) -> None:
    for exp, app_inst in experiment_set.experiments.items():
        exp_idx_str = app_inst.expander.expand_var_name(app_inst.keywords.experiment_index)
        try:
            exp_idx = int(exp_idx_str)
        except (ValueError, TypeError):
            continue
        if exp_idx == target_index:
            if app_inst.is_template:
                logger.die(
                    f"Experiment {target_index} ('{exp}') in workspace '{ws.name}' "
                    "is a template experiment and does not have a run directory."
                )
            if app_inst.repeats.is_repeat_base:
                logger.die(
                    f"Experiment {target_index} ('{exp}') in workspace '{ws.name}' "
                    "is a repeat base experiment and does not have a run directory. "
                    "Specify one of its repeat instances instead."
                )
    logger.die(f"No experiment with index '{target_index}' found in workspace '{ws.name}'.")


def _repeat_base_identifiers(
    exp: str, app_inst: Any
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    repeat_idx = getattr(app_inst.repeats, "repeat_index", 0)
    if not repeat_idx:
        return None, None, None
    suffix = f".{repeat_idx}"
    simplified_exp_ns = app_inst.expander.expand_var_name(
        app_inst.keywords.simplified_experiment_namespace
    )
    exp_name = app_inst.expander.experiment_name
    return (
        exp[: -len(suffix)] if exp.endswith(suffix) else None,
        simplified_exp_ns[: -len(suffix)] if simplified_exp_ns.endswith(suffix) else None,
        exp_name[: -len(suffix)] if exp_name.endswith(suffix) else None,
    )


def _match_in_experiment_set(
    ws: ramble.workspace.Workspace, args, target: str
) -> Tuple[Optional[str], List[Tuple[str, Any, int]]]:
    _, filtered = _build_and_filter_experiments(ws, args)
    if not filtered:
        return None, []

    exact_ns, exact_name, repeat_ns, repeat_name = [], [], [], []
    wl_ns_matches, wl_name_matches, app_matches = [], [], []
    for exp, app_inst, exp_idx in filtered:
        exp_simp = app_inst.expander.expand_var_name(
            app_inst.keywords.simplified_experiment_namespace
        )
        if target in (exp, exp_simp):
            exact_ns.append((exp, app_inst, exp_idx))
        elif target == app_inst.expander.experiment_name:
            exact_name.append((exp, app_inst, exp_idx))
        else:
            base_exp, base_simp, base_name = _repeat_base_identifiers(exp, app_inst)
            if target in (base_exp, base_simp):
                repeat_ns.append((exp, app_inst, exp_idx))
            elif base_name and target == base_name:
                repeat_name.append((exp, app_inst, exp_idx))

        wl_ns = app_inst.expander.workload_namespace
        wl_simp = app_inst.expander.expand_var_name(
            app_inst.keywords.simplified_workload_namespace
        )
        if target in (wl_ns, wl_simp):
            wl_ns_matches.append((wl_ns, app_inst, exp_idx))
        elif target == app_inst.expander.workload_name:
            wl_name_matches.append((wl_ns, app_inst, exp_idx))

        app_ns = app_inst.expander.application_namespace
        app_simp = app_inst.expander.expand_var_name(
            app_inst.keywords.simplified_application_namespace
        )
        if target in (app_ns, app_simp, app_inst.expander.application_name):
            app_matches.append((app_ns, app_inst, exp_idx))

    for kind, group in (
        ("experiment", exact_ns or exact_name or repeat_ns or repeat_name),
        ("workload", wl_ns_matches or wl_name_matches),
        ("application", app_matches),
    ):
        if group:
            return kind, group

    if any(c in _GLOB_CHARS for c in target):
        has_dot = "." in target
        exp_globs: List[Tuple[str, Any, int]] = []
        wl_globs: List[Tuple[str, Any, int]] = []
        app_globs: List[Tuple[str, Any, int]] = []
        for exp, app_inst, exp_idx in filtered:
            exp_expander = app_inst.expander
            kw = app_inst.keywords
            for group, item_ns, full_ns, simp_var, short_name in (
                (
                    exp_globs,
                    exp,
                    exp,
                    kw.simplified_experiment_namespace,
                    exp_expander.experiment_name,
                ),
                (
                    wl_globs,
                    exp_expander.workload_namespace,
                    exp_expander.workload_namespace,
                    kw.simplified_workload_namespace,
                    exp_expander.workload_name,
                ),
                (
                    app_globs,
                    exp_expander.application_namespace,
                    exp_expander.application_namespace,
                    kw.simplified_application_namespace,
                    exp_expander.application_name,
                ),
            ):
                names = (
                    (full_ns, exp_expander.expand_var_name(simp_var), short_name)
                    if has_dot
                    else (short_name,)
                )
                if any(fnmatch.fnmatchcase(c, target) for c in names):
                    group.append((item_ns, app_inst, exp_idx))

        for kind, group in (
            ("experiment_glob", exp_globs),
            ("workload", wl_globs),
            ("application", app_globs),
        ):
            if group:
                return kind, group

    return None, []


def _die_missing_path(path: str, needs_setup_hint: bool) -> None:
    if needs_setup_hint:
        logger.die(
            f"Target directory '{path}' does not exist. Has the workspace "
            "been set up? Try running 'ramble workspace setup' first."
        )
    else:
        logger.die(f"Target directory '{path}' does not exist.")


def _finalize_candidates(
    candidates: List[Tuple[str, str, bool]],
    opts: _SelectionOpts,
    noun_plural: Optional[str] = None,
    ws_name: Optional[str] = None,
) -> List[str]:
    if opts.existing:
        existing_candidates = [c for c in candidates if os.path.isdir(c[1])]
        if not existing_candidates:
            if len(candidates) == 1:
                _die_missing_path(candidates[0][1], candidates[0][2])
            else:
                hint = (
                    " Has the workspace been set up? Try running 'ramble workspace setup' first."
                    if any(c[2] for c in candidates)
                    else ""
                )
                logger.die(
                    f"None of the {len(candidates)} matched target directories exist "
                    f"(first: '{candidates[0][1]}' does not exist).{hint}"
                )
            return []
        candidates = existing_candidates

    if opts.limit_one:
        if opts.warn_implicit_first and len(candidates) > 1 and noun_plural and ws_name:
            logger.warn(
                f"Matched {len(candidates)} {noun_plural} in workspace '{ws_name}'; "
                f"navigating to first match '{candidates[0][0]}'."
            )
        candidates = candidates[:1]

    return [path for _, path, _ in candidates]


def _finalize_one(path: str, opts: _SelectionOpts) -> List[str]:
    abs_path = os.path.abspath(path)
    return _finalize_candidates([(abs_path, abs_path, False)], opts)


def _dedupe_pairs(pairs: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    return list(dedupe(pairs, key=operator.itemgetter(1)))


def _extract_experiment_set_paths(
    ws: ramble.workspace.Workspace,
    args,
    opts: _SelectionOpts,
    match_kind: str,
    matches: List[Tuple[str, Any, int]],
    subpath: Optional[str] = None,
) -> List[str]:
    if args.software_env:
        unexpanded_env = Expander.expansion_str(ramble.keywords.keywords.env_path)
        env_pairs = (
            (
                app_inst.expander.expand_var_name(app_inst.keywords.env_name) or label,
                app_inst.expander.env_path,
            )
            for label, app_inst, _ in matches
            if app_inst.package_manager is not None
            and getattr(app_inst.package_manager, "requires_software_environment", True)
            and app_inst.expander.env_path
            and app_inst.expander.env_path != unexpanded_env
        )
        unique_items = _dedupe_pairs(env_pairs)
        if not unique_items:
            logger.die(
                f"Matched experiment(s) in workspace '{ws.name}' do not define "
                "a package-manager software environment."
            )
        noun = "software environments"
    elif args.input_dir:
        is_app = match_kind == "application"
        unique_items = _dedupe_pairs(
            (
                (
                    app_inst.expander.application_namespace
                    if is_app
                    else app_inst.expander.workload_namespace
                ),
                (
                    app_inst.expander.application_input_dir
                    if is_app
                    else app_inst.expander.workload_input_dir
                ),
            )
            for _, app_inst, _ in matches
        )
        noun = "application input directories" if is_app else "workload input directories"
    elif match_kind in ("experiment", "experiment_glob", "filtered"):
        unique_items = _dedupe_pairs(
            (exp_ns, app_inst.expander.experiment_run_dir) for exp_ns, app_inst, _ in matches
        )
        noun = "experiments"
    elif match_kind == "workload":
        unique_items = _dedupe_pairs(
            (wl_ns, app_inst.expander.workload_run_dir) for wl_ns, app_inst, _ in matches
        )
        noun = "workloads"
    elif match_kind == "application":
        unique_items = _dedupe_pairs(
            (app_ns, app_inst.expander.application_run_dir) for app_ns, app_inst, _ in matches
        )
        noun = "applications"
    else:
        logger.die(f"Unexpected match kind: {match_kind}")
        return []

    candidates = [
        (label, _join_subpath(base_dir, subpath), not os.path.isdir(base_dir))
        for label, base_dir in unique_items
    ]
    return _finalize_candidates(candidates, opts, noun_plural=noun, ws_name=ws.name)


def _resolve_within_workspace_context(
    args,
    opts: _SelectionOpts,
    ws: Optional[ramble.workspace.Workspace],
    ws_root: Optional[str],
    ws_name: Optional[str],
) -> List[str]:
    # Explicit repository mode (--repo [REPO])
    sub_repo = getattr(args, "sub_repo", None)
    if sub_repo is not None:
        if _has_experiment_selection_flags(args):
            logger.die("Cannot combine --repo with experiment filter flags.")
        repo_query: Optional[str] = args.target if sub_repo is True else sub_repo
        repo_subpath: Optional[str] = None if sub_repo is True else _normalize_target(args.target)
        if repo_subpath and os.path.isabs(repo_subpath):
            logger.die("Subpath used with --repo must be a relative path.")
        if repo_query is None:
            repos = _iter_registered_repos()
            if not repos:
                logger.die("No object repositories are configured.")
                return []
            return _finalize_candidates([(ns, root, False) for ns, root in repos], opts)
        repo_paths = _resolve_repo_targets(repo_query)
        if not repo_paths:
            logger.die(f"No such repository: '{repo_query}'")
            return []
        return _finalize_candidates(
            [(p, _join_subpath(p, repo_subpath), False) for p in repo_paths], opts
        )

    norm_target = _normalize_target(args.target)

    # Explicit experiment / software-env / input-dir mode or experiment filter flags
    if _has_experiment_mode(args):
        if ws is None:
            if ws_root is not None:
                logger.die(
                    f"Cannot resolve experiment paths in workspace '{ws_name}' "
                    "because its configuration contains errors."
                )
            ws = ramble.cmd.require_active_workspace(_cmd_name(args))

        if norm_target is None:
            experiment_set, filtered = _build_and_filter_experiments(ws, args)
            if not filtered:
                if args.index is not None:
                    _die_missing_index(ws, experiment_set, args.index)
                logger.die(f"No matching experiments found in workspace '{ws.name}'.")
            return _extract_experiment_set_paths(ws, args, opts, "filtered", filtered)

        head, subpath = _split_head_and_subpath(norm_target)
        match_kind, matches = _match_in_experiment_set(ws, args, head)
        if match_kind is None:
            logger.die(
                f"No experiment, workload, or application matching '{head}' "
                f"found in workspace '{ws.name}'."
            )
            return []
        return _extract_experiment_set_paths(ws, args, opts, match_kind, matches, subpath=subpath)

    # Default behavior with no target and no flags
    if args.target is None or norm_target is None:
        return _finalize_one(ws_root if ws_root is not None else ramble.paths.prefix, opts)

    # Lazy first-match-wins positional resolution (supporting <target>/<subpath>):
    #   1. Active workspace subdirectory
    #   2. Active workspace experiment, workload, or application
    #   3. Named workspace or workspace directory
    #   4. Ramble path keyword
    #   5. Registered object repository namespace
    head, subpath = _split_head_and_subpath(norm_target)
    is_explicit_fs_path = os.path.isabs(norm_target) or norm_target.startswith(("./", "../"))

    if ws_root is not None and not is_explicit_fs_path:
        subdir_match = _workspace_subdirs(ws_root).get(head)
        if subdir_match is not None:
            return _finalize_one(_join_subpath(subdir_match, subpath), opts)

    if (
        ws is not None
        and not is_explicit_fs_path
        and head not in (".", "..")
        and _may_match_in_workspace_config(head)
    ):
        exp_match_kind, exp_matches = _match_in_experiment_set(ws, args, head)
        if exp_match_kind is not None:
            return _extract_experiment_set_paths(
                ws, args, opts, exp_match_kind, exp_matches, subpath=subpath
            )

    ws_match = _resolve_workspace_target(args.target)
    if ws_match is not None:
        return _finalize_one(ws_match, opts)

    if not is_explicit_fs_path:
        kw_match = _ramble_keywords().get(head)
        if kw_match is not None:
            return _finalize_one(_join_subpath(kw_match, subpath), opts)

    if not is_explicit_fs_path and head not in (".", ".."):
        repo_matches = _resolve_repo_targets(args.target)
        if repo_matches:
            return _finalize_candidates([(p, p, False) for p in repo_matches], opts)

    if ws_name is not None:
        logger.die(
            f"Cannot resolve target '{args.target}' as a subdirectory, experiment, workload, "
            f"or application in active workspace '{ws_name}', nor as a workspace name, "
            "repository namespace, or ramble path keyword."
        )
    else:
        logger.die(
            f"Cannot resolve target '{args.target}' as a workspace name, repository namespace, "
            "or ramble path keyword (no workspace is currently active)."
        )
    return []


def _resolve_locations(args, opts: _SelectionOpts) -> List[str]:
    """Resolve one or more target directory paths from parsed CLI arguments."""
    sub_ws = getattr(args, "sub_workspace", None)
    sub_ws_dir = getattr(args, "sub_workspace_dir", None)
    sub_no_ws = bool(getattr(args, "sub_no_workspace", False))
    sub_repo = getattr(args, "sub_repo", None)

    has_top_ws_flag = bool(
        getattr(args, "workspace", None)
        or getattr(args, "workspace_dir", None)
        or getattr(args, "no_workspace", False)
    )
    if has_top_ws_flag and (isinstance(sub_ws, str) or sub_ws_dir is not None or sub_no_ws):
        logger.die(
            "Cannot specify workspace flags (-w/--workspace, -D/--workspace-dir, "
            "-W/--no-workspace) both before and after the subcommand."
        )

    # 1. Explicit developer / user path flags
    static_attr = getattr(args, "static_path_attr", None)
    if static_attr:
        if sub_ws is not None or sub_ws_dir is not None:
            logger.die(
                "Cannot combine -w/--workspace or -D/--workspace-dir with "
                "--ramble-root, --module-dir, --user-config, --builtin-repo, or --repos-dir."
            )
        if _has_experiment_selection_flags(args):
            logger.die(
                "Cannot combine experiment filter flags with "
                "--ramble-root, --module-dir, --user-config, --builtin-repo, or --repos-dir."
            )
        subpath = _normalize_target(args.target)
        if subpath and os.path.isabs(subpath):
            logger.die(
                "Subpath used with --ramble-root, --module-dir, --user-config, "
                "--builtin-repo, or --repos-dir must be a relative path."
            )
        return _finalize_one(_join_subpath(getattr(ramble.paths, static_attr), subpath), opts)

    # 2. Direct workspace target resolution (`-w`, `target -w`, `-w WRKSPC`, or `-D DIR` alone)
    has_inner_query = bool(
        args.target is not None or _has_experiment_mode(args) or sub_repo is not None
    )
    if sub_ws is True or (
        not has_inner_query and (isinstance(sub_ws, str) or sub_ws_dir is not None)
    ):
        if sub_ws is True:
            if sub_repo is not None:
                logger.die("Cannot combine -w/--workspace with --repo.")
            if _has_experiment_mode(args):
                logger.die(
                    "Cannot combine bare --workspace with experiment filter flags "
                    "(pass '-w WRKSPC ...' to query a workspace)."
                )
        if sub_ws_dir is not None:
            ws_path = _resolve_workspace_target(sub_ws_dir, allow_named=False)
            if ws_path is None:
                logger.die(f"No workspace in '{sub_ws_dir}'")
                return []
            return _finalize_one(ws_path, opts)

        ws_query: Optional[str] = sub_ws if isinstance(sub_ws, str) else args.target
        if ws_query is None:
            _, ws_root, _ = _get_workspace_context(args)
            if ws_root is None:
                logger.die(
                    "No workspace is currently active. "
                    "Specify a workspace name or activate a workspace first."
                )
                return []
            return _finalize_one(ws_root, opts)

        ws_path = _resolve_workspace_target(ws_query, allow_named=True)
        if ws_path is None:
            logger.die(f"No such workspace: '{ws_query}'")
            return []
        return _finalize_one(ws_path, opts)

    # 3. Scoped workspace context (`-W`, `-w WRKSPC <query>`, `-D DIR <query>`, or default)
    override_mode: Optional[str] = None
    override_val: Optional[str] = None
    if sub_no_ws:
        override_mode = "no_workspace"
    elif isinstance(sub_ws, str):
        override_mode, override_val = "workspace", sub_ws
    elif sub_ws_dir is not None:
        override_mode, override_val = "workspace_dir", sub_ws_dir

    with _scoped_workspace_context(override_mode, override_val) as scoped_ctx:
        ws, ws_root, ws_name = (
            scoped_ctx if scoped_ctx is not None else _get_workspace_context(args)
        )
        return _resolve_within_workspace_context(args, opts, ws, ws_root, ws_name)


def run_location(
    args,
    limit_one: Optional[bool] = None,
    existing: Optional[bool] = None,
    warn_implicit_first: bool = False,
) -> int:
    opts = _SelectionOpts(
        limit_one=bool(args.limit_one or args.first_failed) if limit_one is None else limit_one,
        existing=bool(getattr(args, "existing", False)) if existing is None else existing,
        warn_implicit_first=warn_implicit_first,
    )
    with contextlib.redirect_stdout(sys.stderr):
        try:
            resolved_paths = _resolve_locations(args, opts=opts)
        except BaseException:
            logger.file_warnings.clear()
            logger.global_warnings.clear()
            raise

        # Flush aggregated warnings (-A) inside redirect_stdout(sys.stderr) because
        # logger.all_warnings() prints summary headers via tty.info() to stdout.
        if logger._aggregated_warnings and not ramble.config.get("config:suppress_warnings"):
            logger.all_warnings()
            logger.file_warnings.clear()
            logger.global_warnings.clear()

    for resolved_path in resolved_paths:
        print(resolved_path)
    return 0


def location(parser, args):
    return run_location(args)
