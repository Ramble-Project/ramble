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


# For a FOM, the direction that is 'better' e.g., faster is better
class BetterDirection(Enum):
    HIGHER = 1
    LOWER = 2
    INDETERMINATE = 3  # requires interpretation or FOM type not defined
    INAPPLICABLE = 4  # non-numerical or no direction is 'better', like strings or categories

    @classmethod
    def from_str(cls, string):
        try:
            return cls[string.upper()]
        except KeyError:
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

    TIME = 1
    THROUGHPUT = 2
    MEASURE = 3
    CATEGORY = 4
    INFO = 5
    UNDEFINED = 6

    def better_direction(self):
        return _FOM_TYPE_DIRECTIONS[self]

    def copy(self):
        return copy.deepcopy(self)

    @classmethod
    def from_str(cls, string):
        try:
            return cls[string.upper()]
        except KeyError:
            return None

    def to_dict(self):
        """Converts the FomType enum member to a dictionary representation."""
        return _FOM_TYPE_DICTS[self]


class SummaryFoms(str, Enum):
    SUMMARY = "Experiment Summary"
    N_TOTAL = "n_total_repeats"
    N_SUCCESS = "n_success_repeats"


_FOM_TYPE_DIRECTIONS = {
    FomType.TIME: BetterDirection.LOWER,
    FomType.THROUGHPUT: BetterDirection.HIGHER,
    FomType.MEASURE: BetterDirection.INDETERMINATE,
    FomType.CATEGORY: BetterDirection.INAPPLICABLE,
    FomType.INFO: BetterDirection.INAPPLICABLE,
    FomType.UNDEFINED: BetterDirection.INDETERMINATE,
}

_FOM_TYPE_DICTS = {
    member: {"name": member.name, "better_direction": _FOM_TYPE_DIRECTIONS[member].name}
    for member in FomType
}


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
