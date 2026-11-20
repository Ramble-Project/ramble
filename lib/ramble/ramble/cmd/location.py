# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Implement ``ramble location`` (and the path-resolution backend for ``ramble cd``).

Resolution flow:

1. ``location()`` (or ``ramble.cmd.cd.cd()``) calls ``run_location()``, which
   redirects incidental logging/warnings to ``stderr`` so ``stdout`` contains
   only resolved directory paths (one per line).
2. ``_resolve_locations()`` handles explicit static-path flags (``-r``, ``-m``,
   ``--user-config``, ``--builtin-repo``, ``--repos-dir``), then retrieves the
   active workspace context via ``_get_workspace_context()`` and delegates to
   ``_resolve_within_workspace_context()``.
3. ``_resolve_within_workspace_context()`` dispatches across:

   - Explicit repository mode (``--repo``).
   - Explicit experiment mode (``-e``, ``-s``, ``--input-dir``, ``-i``,
     ``--where``/``--exclude-where``, ``--filter-tags``, ``--fg``/``--efg``,
     or ``--first-failed``), which filters the workspace's ``ExperimentSet``
     via ``_build_and_filter_experiments()``, optionally matches a positional
     target via ``_match_in_experiment_set()``, and maps matches to run,
     software-env, or input directories via ``_extract_experiment_set_paths()``.
   - Default no-target mode (active workspace root, or ``$RAMBLE_ROOT``).
   - Lazy first-match-wins positional resolution (supporting ``<target>/<subpath>``):
     active workspace subdir -> active workspace experiment/workload/app ->
     named/directory workspace -> Ramble path keyword -> repository namespace.

4. All candidate lists pass through ``_finalize_candidates()`` to enforce
   ``--existing``, apply ``--first``/``--limit-one``, and emit ambiguity
   warnings when ``ramble cd`` implicitly picks the first of multiple matches.
"""

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
_MAX_WARN_ALTERNATIVES = 5
_SETUP_HINT = " Has the workspace been set up? Try running 'ramble workspace setup' first."


class _SelectionOpts(NamedTuple):
    """Post-resolution filtering options shared between ``location`` and ``cd``."""

    limit_one: bool
    existing: bool
    warn_implicit_first: bool = False


class _StaticPathSpec(NamedTuple):
    """Metadata for a static Ramble directory flag and its positional keyword alias(es)."""

    flags: Tuple[str, ...]
    path_attr: str
    keywords: Tuple[str, ...]
    help_text: str


_STATIC_PATHS: Tuple[_StaticPathSpec, ...] = (
    _StaticPathSpec(
        flags=("-r", "--ramble-root"),
        path_attr="prefix",
        keywords=("root",),
        help_text="ramble installation root directory ($RAMBLE_ROOT)",
    ),
    _StaticPathSpec(
        flags=("-m", "--module-dir"),
        path_attr="module_path",
        keywords=("module", "lib"),
        help_text="ramble's python module directory ($RAMBLE_ROOT/lib/ramble/ramble)",
    ),
    _StaticPathSpec(
        flags=("--user-config",),
        path_attr="user_config_path",
        keywords=("user-config",),
        help_text="user configuration directory (~/.ramble)",
    ),
    _StaticPathSpec(
        flags=("--builtin-repo",),
        path_attr="builtin_path",
        keywords=("builtin",),
        help_text="built-in object repository ($RAMBLE_ROOT/var/ramble/repos/builtin)",
    ),
    _StaticPathSpec(
        flags=("--repos-dir",),
        path_attr="repos_path",
        keywords=("repos",),
        help_text="built-in repositories parent directory ($RAMBLE_ROOT/var/ramble/repos)",
    ),
)
_STATIC_PATH_FLAGS_DESC = (
    ", ".join(spec.flags[-1] for spec in _STATIC_PATHS[:-1])
    + f", or {_STATIC_PATHS[-1].flags[-1]}"
)


class _HierarchyLevel(NamedTuple):
    """One level (experiment, workload, or application) of an ExperimentSet."""

    kind: str
    input_kind: str

    @property
    def plural(self) -> str:
        return f"{self.kind}s"

    @property
    def run_dir_attr(self) -> str:
        return f"{self.kind}_run_dir"

    @property
    def input_dir_attr(self) -> str:
        return f"{self.input_kind}_input_dir"

    @property
    def input_ns_attr(self) -> str:
        return f"{self.input_kind}_namespace"

    @property
    def input_plural(self) -> str:
        return f"{self.input_kind} input directories"

    def identifiers(self, exp: str, app_inst: Any) -> Tuple[str, str, str]:
        """Return ``(full_ns, simplified_ns, short_name)`` for ``app_inst`` at this level."""
        expander = app_inst.expander
        full_ns = exp if self.kind == "experiment" else getattr(expander, f"{self.kind}_namespace")
        simp_ns = expander.expand_var_name(
            getattr(app_inst.keywords, f"simplified_{self.kind}_namespace")
        )
        short_name = getattr(expander, f"{self.kind}_name")
        return full_ns, simp_ns, short_name


_EXPERIMENT_LEVEL = _HierarchyLevel("experiment", "workload")
_WORKLOAD_LEVEL = _HierarchyLevel("workload", "workload")
_APPLICATION_LEVEL = _HierarchyLevel("application", "application")
_HIERARCHY_LEVELS: Tuple[_HierarchyLevel, ...] = (
    _EXPERIMENT_LEVEL,
    _WORKLOAD_LEVEL,
    _APPLICATION_LEVEL,
)


def setup_parser(subparser):
    """Configure CLI arguments for ``ramble location`` and ``ramble cd``."""
    subparser.add_argument(
        "-e",
        "--experiment",
        action="store_true",
        dest="as_experiment",
        default=False,
        help="treat target as an experiment, workload, or application (bypassing subdirs)",
    )

    modes = subparser.add_mutually_exclusive_group()
    modes.add_argument(
        "-s",
        "--software-env",
        action="store_true",
        dest="software_env",
        default=False,
        help=(
            "locate the software environment directory ({env_path}) "
            "for the matched experiment or workload"
        ),
    )
    modes.add_argument(
        "--input-dir",
        action="store_true",
        dest="input_dir",
        default=False,
        help="locate the input directory for the matched workload, experiment, or application",
    )
    for spec in _STATIC_PATHS:
        modes.add_argument(
            *spec.flags,
            action="store_const",
            dest="static_path_attr",
            const=spec.path_attr,
            default=None,
            help=spec.help_text,
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

    keyword_list = ", ".join(kw for spec in _STATIC_PATHS for kw in spec.keywords)
    subparser.add_argument(
        "target",
        nargs="?",
        default=None,
        help="workspace subdirectory, experiment/workload/application name, namespace, or glob, "
        f"workspace name, repository namespace, or ramble path keyword ({keyword_list})",
    )


# ---------------------------------------------------------------------------
# Option predicates, static lookups, and target path helpers
# ---------------------------------------------------------------------------


def _cmd_name(args) -> str:
    """Return the invoked subcommand name (``'cd'`` or ``'location'``) for messages."""
    return "cd" if getattr(args, "command", None) == "cd" else "location"


def _ramble_keywords() -> Dict[str, str]:
    """Return mapping of positional Ramble path keywords to installation directories."""
    return {
        kw: getattr(ramble.paths, spec.path_attr) for spec in _STATIC_PATHS for kw in spec.keywords
    }


def _workspace_subdirs(ws_root: str) -> Dict[str, str]:
    """Return mapping of standard workspace subdirectory names to paths under ``ws_root``."""
    subdirs = {
        os.path.basename(p): p
        for p in ramble.workspace.Workspace.get_workspace_paths(ws_root).values()
        if p != ws_root
    }
    subdirs["archives"] = subdirs["archive"]
    return subdirs


def _has_experiment_selection_flags(args) -> bool:
    """Return True if any flag that explicitly selects or filters experiments is set."""
    return bool(
        args.as_experiment
        or args.index is not None
        or args.where
        or args.exclude_where
        or args.filter_tags
        or args.filter_group
        or args.exclude_filter_group
        or args.first_failed
    )


def _has_experiment_mode(args) -> bool:
    """Return True if arguments require resolving against the active workspace's ExperimentSet."""
    return bool(args.software_env or args.input_dir or _has_experiment_selection_flags(args))


def _get_workspace_context(
    args,
) -> Tuple[Optional[ramble.workspace.Workspace], Optional[str], Optional[str]]:
    """Return ``(workspace_obj, workspace_root, workspace_name)`` for the current invocation.

    Falls back to ``find_workspace_path()`` when the workspace directory exists
    but failed to load (e.g., broken ``ramble.yaml``), returning ``ws=None``
    alongside its root so workspace-root and subdirectory navigation still work.
    """
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
    """Strip trailing slashes from a positional target while preserving ``'/'`` and ``None``."""
    if raw_target is None or raw_target == "/":
        return raw_target
    return raw_target.rstrip("/") or raw_target


def _is_explicit_fs_path(path: str) -> bool:
    """Return True if ``path`` is absolute or starts with ``./`` or ``../``."""
    return os.path.isabs(path) or path.startswith(("./", "../"))


def _split_head_and_subpath(norm_target: str) -> Tuple[str, Optional[str]]:
    """Split a relative ``<head>/<subpath>`` target into its leading token and remainder.

    Absolute paths and explicit relative filesystem paths (``./``, ``../``) are
    returned unchanged with ``subpath=None``.
    """
    if (
        "/" in norm_target
        and not _is_explicit_fs_path(norm_target)
        and norm_target not in (".", "..")
    ):
        head, raw_sub = norm_target.split("/", 1)
        return head, (raw_sub.lstrip("/") or None)
    return norm_target, None


def _join_subpath(base_path: str, subpath: Optional[str]) -> str:
    """Join an optional relative ``subpath`` onto ``base_path`` and normalize with ``abspath``."""
    return os.path.abspath(os.path.join(base_path, subpath) if subpath else base_path)


def _walk_ancestor_dir(stripped: str, predicate: Callable[[str], bool]) -> Optional[str]:
    """Walk parent directories of ``stripped`` and return its absolute path if an ancestor matches.

    Used to resolve paths pointing inside an anonymous workspace directory or
    unregistered repository directory (e.g., ``/path/to/ws/configs``).
    """
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


# ---------------------------------------------------------------------------
# Workspace and repository lookup helpers
# ---------------------------------------------------------------------------


def _resolve_workspace_target(target: str) -> Optional[str]:
    """Resolve ``target`` as a named workspace, workspace directory, or subpath inside one."""
    stripped = target.rstrip("/") or target
    if ramble.workspace.exists(stripped):
        return ramble.workspace.root(stripped)
    if ramble.workspace.is_workspace_dir(stripped):
        return os.path.abspath(stripped)
    head, subpath = _split_head_and_subpath(stripped)
    if subpath is not None and ramble.workspace.exists(head):
        return _join_subpath(ramble.workspace.root(head), subpath)
    return _walk_ancestor_dir(stripped, ramble.workspace.is_workspace_dir)


def _iter_registered_repos() -> List[Tuple[str, str]]:
    """Return ``(namespace, root_path)`` pairs for all configured repos in precedence order."""
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
    """Return True if ``path`` is a valid Ramble repository for any ``ObjectTypes`` entry."""
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
    """Resolve ``target`` as a registered repo namespace, repo directory, or subpath inside one."""
    stripped = target.rstrip("/")
    if not stripped:
        return []

    if not _is_explicit_fs_path(stripped):
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


# ---------------------------------------------------------------------------
# Experiment-set fast-path check, filtering, and matching
# ---------------------------------------------------------------------------


def _template_to_glob(key: str) -> str:
    """Convert a templated config key (e.g., ``scale_{n_nodes}``) into an ``fnmatch`` glob."""
    prev = None
    cur = key
    while prev != cur:
        prev = cur
        cur = _INNER_BRACE_RE.sub("*", cur)
    return "*" if ("{" in cur or "}" in cur) else cur


def _iter_raw_config_names(app_dict: Dict[Any, Any]) -> Iterator[str]:
    """Yield raw application, workload, and experiment key names from the workspace config dict."""
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
    """Fast conservative check against raw workspace config before building ExperimentSet.

    Avoids the cost of instantiating an ``ExperimentSet`` when resolving
    non-experiment positional targets such as ``root`` or another workspace name.
    Dotted targets and globs always return True so full namespace matching runs.
    """
    if not target or "." in target or any(c in _GLOB_CHARS for c in target):
        return True
    app_dict = ramble.config.get(namespace.application)
    if not isinstance(app_dict, dict) or not app_dict:
        return False
    return any(
        fnmatch.fnmatchcase(target, _template_to_glob(name))
        for name in _iter_raw_config_names(app_dict)
    )


def _experiment_index(app_inst: Any) -> Optional[int]:
    """Return the integer ``experiment_index`` of ``app_inst``, or ``None`` if unparsable."""
    exp_idx_str = app_inst.expander.expand_var_name(app_inst.keywords.experiment_index)
    try:
        return int(exp_idx_str)
    except (ValueError, TypeError):
        return None


def _build_and_filter_experiments(
    ws: ramble.workspace.Workspace, args
) -> Tuple[Any, List[Tuple[str, Any]]]:
    """Build ``ws``'s ``ExperimentSet`` and apply CLI experiment filters.

    Applies ``--where``, ``--exclude-where``, ``--filter-tags``, ``--fg``/``--efg``,
    ``--first-failed``, and ``-i``/``--index``, excluding templates and repeat base
    entries (which do not own concrete run directories).

    Returns:
        Tuple of ``(experiment_set, filtered)`` where ``filtered`` is a list of
        ``(experiment_namespace, app_inst)`` tuples.
    """
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

    filtered: List[Tuple[str, Any]] = []
    for exp, app_inst, idx in experiment_set.filtered_experiments(filters):
        if app_inst.is_template or app_inst.repeats.is_repeat_base:
            continue
        if args.index is not None and exp in experiment_set.chained_experiments:
            continue
        parsed_idx = _experiment_index(app_inst)
        exp_idx = idx if parsed_idx is None else parsed_idx
        if args.index is not None and exp_idx != args.index:
            continue
        filtered.append((exp, app_inst))

    return experiment_set, filtered


def _die_missing_index(ws: ramble.workspace.Workspace, experiment_set, target_index: int) -> None:
    """Exit with an informative error when ``-i/--index`` matched no runnable experiment.

    Distinguishes template and repeat-base indices from nonexistent indices.
    """
    for exp, app_inst in experiment_set.experiments.items():
        if _experiment_index(app_inst) == target_index:
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
    full_ns: str, simp_ns: str, short_name: str, app_inst: Any
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Return ``(base_exp_ns, base_simplified_ns, base_exp_name)`` for a repeat instance.

    Strips the trailing ``.<repeat_index>`` suffix so targeting a repeat base name
    (e.g., ``rep_exp``) matches all of its repeat instances (``rep_exp.1``, ...).
    Returns ``(None, None, None)`` for non-repeat experiments.
    """
    repeat_idx = getattr(app_inst.repeats, "repeat_index", 0)
    if not repeat_idx:
        return None, None, None
    suffix = f".{repeat_idx}"
    return (
        full_ns[: -len(suffix)] if full_ns.endswith(suffix) else None,
        simp_ns[: -len(suffix)] if simp_ns.endswith(suffix) else None,
        short_name[: -len(suffix)] if short_name.endswith(suffix) else None,
    )


def _match_in_experiment_set(
    ws: ramble.workspace.Workspace, args, target: str
) -> Tuple[Optional[_HierarchyLevel], List[Tuple[str, Any]]]:
    """Match ``target`` against filtered experiments at experiment, workload, or application level.

    Applies CLI filters via ``_build_and_filter_experiments()`` first, then
    matches ``target`` across ``_HIERARCHY_LEVELS`` in precedence order:

    1. Exact match per level (experiment > workload > application), preferring
       full/simplified namespace > short name (> repeat-base namespace/name
       for experiments).
    2. Glob match (if ``target`` contains ``*``, ``?``, or ``[``) in the same
       level order. Dotted globs match against full/simplified namespaces and
       short names; dotless globs match only against short names so e.g.
       ``*hpcg*`` selects the application directory.

    Returns:
        Tuple of ``(level, matches)`` where ``level`` is the matched
        ``_HierarchyLevel`` (or ``None`` if nothing matched).
    """
    _, filtered = _build_and_filter_experiments(ws, args)
    if not filtered:
        return None, []

    for level in _HIERARCHY_LEVELS:
        ns_matches: List[Tuple[str, Any]] = []
        name_matches: List[Tuple[str, Any]] = []
        repeat_ns: List[Tuple[str, Any]] = []
        repeat_name: List[Tuple[str, Any]] = []
        for exp, app_inst in filtered:
            full_ns, simp_ns, short_name = level.identifiers(exp, app_inst)
            item = (full_ns, app_inst)
            if target in (full_ns, simp_ns):
                ns_matches.append(item)
            elif target == short_name:
                name_matches.append(item)
            elif level is _EXPERIMENT_LEVEL:
                base_exp, base_simp, base_name = _repeat_base_identifiers(
                    full_ns, simp_ns, short_name, app_inst
                )
                if target in (base_exp, base_simp):
                    repeat_ns.append(item)
                elif base_name and target == base_name:
                    repeat_name.append(item)
        group = ns_matches or name_matches or repeat_ns or repeat_name
        if group:
            return level, group

    if any(c in _GLOB_CHARS for c in target):
        has_dot = "." in target
        for level in _HIERARCHY_LEVELS:
            glob_matches: List[Tuple[str, Any]] = []
            for exp, app_inst in filtered:
                full_ns, simp_ns, short_name = level.identifiers(exp, app_inst)
                names = (full_ns, simp_ns, short_name) if has_dot else (short_name,)
                if any(fnmatch.fnmatchcase(c, target) for c in names):
                    glob_matches.append((full_ns, app_inst))
            if glob_matches:
                return level, glob_matches

    return None, []


# ---------------------------------------------------------------------------
# Candidate extraction and finalization
# ---------------------------------------------------------------------------


def _finalize_candidates(
    candidates: List[Tuple[str, str, bool]],
    opts: _SelectionOpts,
    noun_plural: Optional[str] = None,
    ws_name: Optional[str] = None,
) -> List[str]:
    """Filter, validate, and optionally truncate resolved ``(label, path, needs_setup)`` tuples.

    When ``opts.existing`` is set, filters to directories that exist on disk
    before applying ``opts.limit_one``. When ``opts.warn_implicit_first`` is set
    and multiple candidates remain, logs a warning naming the selected match and
    listing up to ``_MAX_WARN_ALTERNATIVES`` alternative labels.
    """
    if opts.existing:
        existing_candidates = [c for c in candidates if os.path.isdir(c[1])]
        if not existing_candidates:
            hint = _SETUP_HINT if any(c[2] for c in candidates) else ""
            if len(candidates) == 1:
                logger.die(f"Target directory '{candidates[0][1]}' does not exist.{hint}")
            else:
                logger.die(
                    f"None of the {len(candidates)} matched target directories exist "
                    f"(first: '{candidates[0][1]}' does not exist).{hint}"
                )
            return []
        candidates = existing_candidates

    if opts.limit_one:
        if opts.warn_implicit_first and len(candidates) > 1 and noun_plural and ws_name:
            others = [c[0] for c in candidates[1:]]
            shown = ", ".join(f"'{name}'" for name in others[:_MAX_WARN_ALTERNATIVES])
            remaining = len(others) - _MAX_WARN_ALTERNATIVES
            other_str = f"{shown} (+{remaining} more)" if remaining > 0 else shown
            logger.warn(
                f"Matched {len(candidates)} {noun_plural} in workspace '{ws_name}'; "
                f"navigating to first match '{candidates[0][0]}'. "
                f"Other matches: {other_str}."
            )
        candidates = candidates[:1]

    return [path for _, path, _ in candidates]


def _finalize_one(path: str, opts: _SelectionOpts) -> List[str]:
    """Finalize a single non-experiment directory path through ``_finalize_candidates()``."""
    abs_path = os.path.abspath(path)
    return _finalize_candidates([(abs_path, abs_path, False)], opts)


def _dedupe_pairs(pairs: Iterable[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Deduplicate ``(label, path)`` pairs while preserving first-seen order by ``path``."""
    return list(dedupe(pairs, key=operator.itemgetter(1)))


def _software_env_label(
    ws: ramble.workspace.Workspace, app_inst: Any, env_path: str, fallback: str
) -> str:
    """Format a human-readable label for a software environment (e.g., ``spack/my_env``)."""
    try:
        rel = os.path.relpath(os.path.abspath(env_path), os.path.abspath(ws.software_dir))
    except ValueError:
        rel = ""
    if rel and rel not in (".", "..") and not rel.startswith(".." + os.sep):
        return rel
    return app_inst.expander.expand_var_name(app_inst.keywords.env_name) or fallback


def _extract_experiment_set_paths(
    ws: ramble.workspace.Workspace,
    args,
    opts: _SelectionOpts,
    level: _HierarchyLevel,
    matches: List[Tuple[str, Any]],
    subpath: Optional[str] = None,
) -> List[str]:
    """Map matched ``ExperimentSet`` items to concrete directory paths and finalize them.

    Projects matches to:

    - ``{env_path}`` when ``-s/--software-env`` is set
    - ``{application_input_dir}`` or ``{workload_input_dir}`` when ``--input-dir`` is set
    - ``{experiment_run_dir}``, ``{workload_run_dir}``, or ``{application_run_dir}``
      corresponding to ``level`` otherwise
    """
    if args.software_env:
        unexpanded_env = Expander.expansion_str(ramble.keywords.keywords.env_path)
        env_pairs = (
            (
                _software_env_label(ws, app_inst, app_inst.expander.env_path, label),
                app_inst.expander.env_path,
            )
            for label, app_inst in matches
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
        unique_items = _dedupe_pairs(
            (
                getattr(app_inst.expander, level.input_ns_attr),
                getattr(app_inst.expander, level.input_dir_attr),
            )
            for _, app_inst in matches
        )
        noun = level.input_plural
    else:
        unique_items = _dedupe_pairs(
            (item_ns, getattr(app_inst.expander, level.run_dir_attr))
            for item_ns, app_inst in matches
        )
        noun = level.plural

    candidates = [
        (label, _join_subpath(base_dir, subpath), not os.path.isdir(base_dir))
        for label, base_dir in unique_items
    ]
    return _finalize_candidates(candidates, opts, noun_plural=noun, ws_name=ws.name)


# ---------------------------------------------------------------------------
# Main resolution flow and command entry points
# ---------------------------------------------------------------------------


def _resolve_repo_mode(args, opts: _SelectionOpts, sub_repo: Any) -> List[str]:
    """Resolve paths for explicit ``--repo [REPO] [SUBPATH]`` mode."""
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


def _resolve_within_workspace_context(
    args,
    opts: _SelectionOpts,
    ws: Optional[ramble.workspace.Workspace],
    ws_root: Optional[str],
    ws_name: Optional[str],
) -> List[str]:
    """Resolve target directory path(s) given the active workspace context.

    Handles ``--repo`` mode, explicit experiment mode (``-e``, ``-s``,
    ``--input-dir``, or filter flags), default no-target mode, and lazy
    first-match-wins positional resolution.
    """
    sub_repo = getattr(args, "sub_repo", None)
    if sub_repo is not None:
        return _resolve_repo_mode(args, opts, sub_repo)

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
            return _extract_experiment_set_paths(ws, args, opts, _EXPERIMENT_LEVEL, filtered)

        head, subpath = _split_head_and_subpath(norm_target)
        match_level, matches = _match_in_experiment_set(ws, args, head)
        if match_level is None:
            logger.die(
                f"No experiment, workload, or application matching '{head}' "
                f"found in workspace '{ws.name}'."
            )
            return []
        return _extract_experiment_set_paths(ws, args, opts, match_level, matches, subpath=subpath)

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
    is_explicit_fs_path = _is_explicit_fs_path(norm_target)

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
        exp_level, exp_matches = _match_in_experiment_set(ws, args, head)
        if exp_level is not None:
            return _extract_experiment_set_paths(
                ws, args, opts, exp_level, exp_matches, subpath=subpath
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
    static_attr = getattr(args, "static_path_attr", None)
    if static_attr:
        if _has_experiment_selection_flags(args):
            logger.die(f"Cannot combine experiment filter flags with {_STATIC_PATH_FLAGS_DESC}.")
        subpath = _normalize_target(args.target)
        if subpath and os.path.isabs(subpath):
            logger.die(f"Subpath used with {_STATIC_PATH_FLAGS_DESC} must be a relative path.")
        return _finalize_one(_join_subpath(getattr(ramble.paths, static_attr), subpath), opts)

    ws, ws_root, ws_name = _get_workspace_context(args)
    return _resolve_within_workspace_context(args, opts, ws, ws_root, ws_name)


def run_location(
    args,
    limit_one: Optional[bool] = None,
    existing: Optional[bool] = None,
    warn_implicit_first: bool = False,
) -> int:
    """Resolve and print target directory path(s) to stdout.

    Shared backend for both ``ramble location`` and ``ramble cd``. All
    diagnostic output and aggregated warnings are redirected to ``stderr`` so
    shell wrappers and scripts can safely capture ``stdout``.

    Args:
        args: Parsed CLI argument namespace.
        limit_one: Override ``args.limit_one`` / ``args.first_failed`` when set.
        existing: Override ``args.existing`` when set.
        warn_implicit_first: Emit a warning when ``limit_one`` truncates
            multiple matches (used by ``ramble cd`` when ``--first`` wasn't passed).
    """
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
    """Entry point for the ``ramble location`` subcommand."""
    return run_location(args)
