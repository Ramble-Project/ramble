# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Utilities for evaluating, formatting, and emitting object deprecation warnings."""

import contextlib
import warnings
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

import ramble
from ramble.util.logger import logger

_warned_context_stack: List[Set[Any]] = []


@contextlib.contextmanager
def deprecation_warning_context() -> Iterator[Set[Any]]:
    """Context manager scoping deprecation warning deduplication to a single command."""
    warned_set: Set[Any] = set()
    _warned_context_stack.append(warned_set)
    try:
        yield warned_set
    finally:
        _warned_context_stack.pop()


def get_active_warned_set(fallback_owner: Any = None) -> Optional[Set[Any]]:
    """Return the active set used to deduplicate deprecation warnings.

    Prefers the command-level context set when executing inside
    :func:`deprecation_warning_context`, falling back to a
    ``_warned_deprecations`` attribute on ``fallback_owner`` (such as an
    ``ExperimentSet``) when called outside a CLI command.
    """
    if _warned_context_stack:
        return _warned_context_stack[-1]

    if fallback_owner is not None:
        warned = getattr(fallback_owner, "_warned_deprecations", None)
        if warned is None:
            warned = set()
            fallback_owner._warned_deprecations = warned
        return warned

    return None


def evaluate_deprecation_status(
    deprecated_in: Optional[str],
    removed_in: Optional[str],
    current_version: Optional[str] = None,
) -> Tuple[bool, bool]:
    """Evaluate whether a deprecation is active or past its removal version.

    Args:
        deprecated_in: Version string when deprecation begins, or ``None`` for
            immediate deprecation.
        removed_in: Version string when the deprecated object/feature should be
            removed, or ``None`` if no removal version is scheduled.
        current_version: Version string to evaluate against. Defaults to
            ``ramble.ramble_version``.

    Returns:
        Tuple[bool, bool]: ``(is_deprecated, is_unsupported)``.
    """
    from packaging.version import Version

    ver_str = str(ramble.ramble_version) if current_version is None else str(current_version)
    cur_ver = Version(ver_str)

    if removed_in is not None and cur_ver >= Version(removed_in):
        return False, True

    if deprecated_in is not None:
        if cur_ver >= Version(deprecated_in):
            return True, False
        return False, False

    return True, False


def format_deprecation_message(
    obj_name: str,
    obj_type: str,
    deprecation_entry: Dict[str, Any],
    expanded_msg: Optional[str] = None,
) -> str:
    """Format a user-facing deprecation warning message."""
    obj_type_str = obj_type.replace("_", " ") if obj_type else "object"
    when_list = deprecation_entry.get("when") or []
    deprecated_in = deprecation_entry.get("deprecated_in")
    removed_in = deprecation_entry.get("removed_in")
    replacement = deprecation_entry.get("replacement")
    msg = expanded_msg if expanded_msg is not None else deprecation_entry.get("message")

    subject = f"The '{obj_name}' {obj_type_str}"
    if when_list:
        subject += f" (when {', '.join(when_list)})"

    if deprecated_in and removed_in:
        text = (
            f"{subject} is deprecated as of v{deprecated_in} "
            f"and will be removed in v{removed_in}."
        )
    elif deprecated_in:
        text = f"{subject} is deprecated as of v{deprecated_in}."
    else:
        text = f"{subject} is deprecated."

    if replacement:
        text += f" Please use '{replacement}' instead."

    if msg:
        text += f" {msg}"

    return text


def format_deprecation_summary(deprecation_entry: Dict[str, Any]) -> str:
    """Format a concise one-line summary for ``ramble info`` non-verbose output."""
    deprecated_in = deprecation_entry.get("deprecated_in")
    removed_in = deprecation_entry.get("removed_in")
    replacement = deprecation_entry.get("replacement")
    msg = deprecation_entry.get("message")
    when_list = deprecation_entry.get("when") or []

    parts = [f"deprecated in {deprecated_in}" if deprecated_in else "deprecated"]
    if removed_in:
        parts.append(f"removed in {removed_in}")

    summary = ", ".join(parts)
    if replacement:
        summary += f" (replacement: {replacement})"
    if msg:
        summary += f" - {msg}"
    if when_list:
        summary = f"when {', '.join(when_list)}: {summary}"

    return summary


def emit_deprecation_warning(
    obj_name: str,
    obj_type: str,
    deprecation_entry: Dict[str, Any],
    expanded_msg: Optional[str] = None,
    warn_user: bool = True,
    warned_set: Optional[Set[Any]] = None,
    current_version: Optional[str] = None,
) -> bool:
    """Emit Python and user-facing warnings for an active deprecation entry.

    Emits a ``deprecation.DeprecatedWarning`` (or
    ``deprecation.UnsupportedWarning`` once ``removed_in`` is reached)
    via :func:`warnings.warn` so ``@deprecation.fail_if_not_removed`` catches
    expired deprecations, and logs a user-facing warning via ``logger.warn``
    when ``warn_user`` is True. Deduplicates emissions per unique deprecation
    using ``warned_set`` when supplied.

    Returns:
        bool: True if the deprecation is active/unsupported at the current
        version, False otherwise.
    """
    deprecated_in = deprecation_entry.get("deprecated_in")
    removed_in = deprecation_entry.get("removed_in")
    replacement = deprecation_entry.get("replacement")
    raw_msg = deprecation_entry.get("message")
    msg = expanded_msg if expanded_msg is not None else raw_msg
    when_list = deprecation_entry.get("when") or []

    is_deprecated, is_unsupported = evaluate_deprecation_status(
        deprecated_in=deprecated_in,
        removed_in=removed_in,
        current_version=current_version,
    )
    if not (is_deprecated or is_unsupported):
        return False

    dedup_key = (
        obj_type,
        obj_name,
        frozenset(when_list),
        deprecated_in,
        removed_in,
        replacement,
        raw_msg,
    )

    py_key = ("py", dedup_key)
    if warned_set is None or py_key not in warned_set:
        import deprecation

        if warned_set is not None:
            warned_set.add(py_key)

        obj_type_str = obj_type.replace("_", " ") if obj_type else "object"
        target_desc = f"{obj_type_str} '{obj_name}'"
        if when_list:
            target_desc += f" (when {', '.join(when_list)})"

        details_parts = []
        if replacement:
            details_parts.append(f"Please use '{replacement}' instead.")
        if msg:
            details_parts.append(msg)
        details = " ".join(details_parts)

        warning_cls = (
            deprecation.UnsupportedWarning if is_unsupported else deprecation.DeprecatedWarning
        )
        the_warning = warning_cls(target_desc, deprecated_in, removed_in, details)
        warnings.warn(the_warning, stacklevel=3)

    if warn_user:
        user_key = ("user", dedup_key)
        if warned_set is None or user_key not in warned_set:
            if warned_set is not None:
                warned_set.add(user_key)
            user_msg = format_deprecation_message(
                obj_name=obj_name,
                obj_type=obj_type,
                deprecation_entry=deprecation_entry,
                expanded_msg=expanded_msg,
            )
            logger.warn(user_msg)

    return True
