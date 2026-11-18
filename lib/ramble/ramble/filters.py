# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import itertools
import re
from typing import List, Optional, Set

import ramble.config
from ramble.error import RambleError
from ramble.util.logger import logger

ALL_PHASES: List[str] = ["*"]

_VALID_CHARS_RE = re.compile(r"[a-zA-Z0-9_\s\(\)-]")
_TOKEN_RE = re.compile(r"([a-zA-Z0-9_-]+|\(|\))")
_VALID_NAME_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


class Filters:
    """Object containing filters for limiting various operations in Ramble"""

    def __init__(
        self,
        phase_filters: Optional[List[str]] = None,
        include_where_filters: Optional[List[List[str]]] = None,
        exclude_where_filters: Optional[List[List[str]]] = None,
        tags: Optional[List[List[str]]] = None,
    ) -> None:
        """Create a new filter instance"""

        self.phases: List[str] = ALL_PHASES if phase_filters is None else phase_filters
        self.include_where: Optional[List[str]] = None
        self.exclude_where: Optional[List[str]] = None
        self.tags: Set[str] = set()

        if include_where_filters:
            self.include_where = list(itertools.chain.from_iterable(include_where_filters))
        if exclude_where_filters:
            self.exclude_where = list(itertools.chain.from_iterable(exclude_where_filters))
        if tags:
            self.tags = set(itertools.chain.from_iterable(tags))

    @classmethod
    def from_args(cls, args, **kwargs) -> "Filters":
        """Construct a filter instance from CLI arguments."""
        where = resolve_and_apply_filter_groups(args, getattr(args, "where", None))
        filter_kwargs = {
            "phase_filters": getattr(args, "phases", None),
            "include_where_filters": where,
            "exclude_where_filters": getattr(args, "exclude_where", None),
            "tags": getattr(args, "filter_tags", None),
            **kwargs,
        }
        return cls(**filter_kwargs)


def translate_group_to_predicate(group_def: dict) -> str:
    """Translate a filter group definition into a predicate string"""
    if not group_def:
        return "True"

    where_parts = group_def.get("where", [])
    exclude_parts = group_def.get("exclude_where", [])

    if not where_parts and not exclude_parts:
        return "True"

    parts = []
    if where_parts:
        where_str = " and ".join(f"({w})" for w in where_parts)
        parts.append(f"({where_str})")

    if exclude_parts:
        exclude_str = " and ".join(f"not ({e})" for e in exclude_parts)
        parts.append(f"({exclude_str})")

    return " and ".join(parts)


def expand_filter_groups(expression: str, filter_groups_defs: Optional[dict]) -> str:
    """Expand logical expression of filter groups into a predicate string"""
    if not expression:
        return "True"

    if filter_groups_defs is None:
        filter_groups_defs = {}

    # Validate expression only contains allowed characters to prevent injection or silent failures
    invalid_chars = _VALID_CHARS_RE.sub("", expression)
    if invalid_chars:
        raise RambleError(
            f"Invalid characters {repr(invalid_chars)} in filter group expression '{expression}'"
        )

    tokens = _TOKEN_RE.findall(expression)

    expanded_tokens = []
    for token in tokens:
        low_token = token.lower()
        if low_token in ("and", "or", "not", "(", ")"):
            expanded_tokens.append(low_token)
        elif token in filter_groups_defs:
            group_def = filter_groups_defs[token]
            group_expr = translate_group_to_predicate(group_def)
            expanded_tokens.append(f"( {group_expr} )")
        else:
            raise RambleError(f"Unknown filter group '{token}' in expression '{expression}'")

    return " ".join(expanded_tokens)


def resolve_and_apply_filter_groups(args, include_where_filters):
    """Resolve filter groups from args/env and apply them to include_where_filters"""
    filter_group_expr = getattr(args, "filter_group", None)
    exclude_filter_group_expr = getattr(args, "exclude_filter_group", None)

    # If not specified on CLI, check environment
    if filter_group_expr is None and exclude_filter_group_expr is None:
        import os

        active_group = os.environ.get("RAMBLE_ACTIVE_FILTER_GROUP")
        if active_group:
            filter_group_expr = active_group

    if not filter_group_expr and not exclude_filter_group_expr:
        return include_where_filters

    filter_groups_defs = ramble.config.get("filter_groups")

    combined_expr = []
    if filter_group_expr:
        combined_expr.append(f"( {filter_group_expr} )")
    if exclude_filter_group_expr:
        combined_expr.append(f"not ( {exclude_filter_group_expr} )")

    final_expr = " and ".join(combined_expr)

    try:
        predicate_expr = expand_filter_groups(final_expr, filter_groups_defs)
        if include_where_filters is None:
            include_where_filters = []
        include_where_filters.append([predicate_expr])
    except RambleError as e:
        logger.die(str(e))

    return include_where_filters


def validate_filter_group_name(name: str):
    """Validate filter group name to prevent reserved keywords and invalid characters."""
    if name.lower() in ("and", "or", "not"):
        raise RambleError(f"Filter group name '{name}' is a reserved keyword.")

    if not _VALID_NAME_RE.match(name):
        raise RambleError(
            f"Filter group name '{name}' is invalid. "
            "It can only contain alphanumeric characters, underscores, and hyphens."
        )
