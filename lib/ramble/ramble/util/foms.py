# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import copy
import functools
import re
from enum import Enum

NULL_CONTEXT = "null"


def get_context_display_name(context):
    return f"default ({NULL_CONTEXT}) context" if context == NULL_CONTEXT else f"{context} context"


# For a FOM, the direction that is 'better' e.g., faster is better
class BetterDirection(Enum):
    _description: str

    HIGHER = (1, "higher is better")
    LOWER = (2, "lower is better")
    INDETERMINATE = (3, "")  # requires interpretation or FOM type not defined
    INAPPLICABLE = (4, "")  # non-numerical or no direction is 'better', like strings or categories

    def __new__(cls, value, description):
        obj = object.__new__(cls)
        obj._value_ = value
        obj._description = description
        return obj

    @property
    def description(self) -> str:
        return self._description

    def as_str(self) -> str:
        """Returns the human-readable description (e.g., 'higher is better')."""
        return self.description

    def suffix(self) -> str:
        """Returns the direction suffix formatted in parentheses, or empty string."""
        return f" ({self.description})" if self.description else ""

    def __str__(self) -> str:
        return self.as_str()

    @classmethod
    def from_str(cls, string):
        try:
            return cls[string.upper()]
        except KeyError:
            return None

    @classmethod
    def from_value(cls, val):
        """Coerce a BetterDirection enum, string, int, or None to a BetterDirection."""
        if isinstance(val, cls):
            return val
        if isinstance(val, str):
            return cls.from_str(val)
        if isinstance(val, int):
            for member in cls:
                if member._value_ == val:
                    return member
        return None


class FomType(Enum):
    """Classification of a Figure of Merit (FOM).

    - ``TIME``: Duration or latency metric where lower values are better.
    - ``THROUGHPUT``: Rate or bandwidth metric where higher values are better.
    - ``MEASURE``: Quantitative measurement with no inherent 'better' direction
      (e.g., power draw, frequency, problem size, error). Eligible for summary
      statistics across repeats.
    - ``CATEGORY``: Qualitative or discrete classification drawn from a shared
      set of values across experiments (e.g., CPU vendor, machine type,
      compiler/library variant, pass/fail status). Useful for grouping,
      filtering, or splitting series; excluded from numeric repeat stats.
    - ``INFO``: High-cardinality, run-specific, or unstructured provenance
      metadata expected to be unique per run or resource (e.g., hostnames,
      job IDs, UUIDs, timestamps). Excluded from numeric repeat stats.
    - ``UNDEFINED``: Default when no FOM type is specified.
    """

    _title: str
    _default_better_direction: BetterDirection

    THROUGHPUT = (1, "Throughput", BetterDirection.HIGHER)
    TIME = (2, "Time", BetterDirection.LOWER)
    MEASURE = (3, "Measure", BetterDirection.INDETERMINATE)
    CATEGORY = (4, "Categorical", BetterDirection.INAPPLICABLE)
    INFO = (5, "Informational", BetterDirection.INAPPLICABLE)
    UNDEFINED = (6, "Undefined", BetterDirection.INDETERMINATE)

    def __new__(cls, value, title, default_better_direction):
        obj = object.__new__(cls)
        obj._value_ = value
        obj._title = title
        obj._default_better_direction = default_better_direction
        return obj

    @property
    def title(self) -> str:
        return self._title

    @property
    def default_better_direction(self) -> BetterDirection:
        return self._default_better_direction

    def better_direction(self):
        return self.default_better_direction

    def group_title(self, better_direction=None) -> str:
        """Returns the formatted group title for result index sections."""
        if better_direction is None:
            bd = self.better_direction()
        else:
            bd = BetterDirection.from_value(better_direction)
        suffix = bd.suffix() if bd else ""
        return f"{self.title} FOMs{suffix}"

    def formatted_str(self, better_direction=None) -> str:
        """Returns the display string for this FOM type with direction suffix."""
        if better_direction is None:
            bd = self.better_direction()
        else:
            bd = BetterDirection.from_value(better_direction)
        suffix = bd.suffix() if bd else ""
        return f"{self.title}{suffix}"

    def __str__(self) -> str:
        return self.formatted_str()

    def copy(self):
        return copy.deepcopy(self)

    @classmethod
    def from_str(cls, string):
        try:
            return cls[string.upper()]
        except KeyError:
            for member in cls:
                if string.upper() == member.title.upper():
                    return member
            return None

    @classmethod
    def from_value(cls, val):
        """Coerce a FomType enum member, serialized dictionary, string, int,
        or None to a FomType.
        """
        if isinstance(val, cls):
            return val
        if isinstance(val, dict) and "name" in val:
            return cls.from_str(str(val["name"]))
        if isinstance(val, str):
            return cls.from_str(val)
        if isinstance(val, int):
            for member in cls:
                if member._value_ == val:
                    return member
        return None

    def to_dict(self):
        """Converts the FomType enum member to a dictionary representation."""
        return {"name": self.name, "better_direction": self.default_better_direction.name}


class SummaryFoms(str, Enum):
    SUMMARY = "Experiment Summary"
    N_TOTAL = "n_total_repeats"
    N_SUCCESS = "n_success_repeats"


# Try to import the internal parser for the re module
try:
    # See https://github.com/python/cpython/issues/91308
    import re._parser as sre_parse
except ImportError:
    try:
        # This is for Python 3.10 or earlier
        import sre_parse
    except ImportError:
        sre_parse = None


@functools.lru_cache(maxsize=1024)
def _get_literal_from_regex_cached(regex_str: str) -> str:
    if not sre_parse:
        return ""

    try:
        tree = sre_parse.parse(regex_str)
    # re.error is renamed, but it's kept around for backward compatibility
    # See https://docs.python.org/3/library/re.html#exceptions
    except re.error:
        return ""

    if tree.state.flags & re.IGNORECASE:
        return ""

    current_literal = ""
    for node in tree:
        node_name = str(node[0])
        if node_name == "LITERAL":
            current_literal += chr(node[1])
        elif current_literal:
            break

    return current_literal.strip()


def get_literal_from_regex(regex_str: str) -> str:
    """
    Extracts a first-encountered required literal string from a regex pattern.

    This is used to create fast string pre-filters to avoid executing complex regex matching.
    This is not exhaustive, as it doesn't recurse into sub-patterns. It is only intended as a
    heuristic to short-circuit the matching process.
    """
    if not regex_str or not sre_parse:
        return ""

    return _get_literal_from_regex_cached(regex_str)
