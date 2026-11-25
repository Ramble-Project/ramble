# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

from ramble.util.foms import get_literal_from_regex


@pytest.mark.parametrize(
    "regex_str, expected",
    [
        (r"foo bar", "foo bar"),
        (r"Sleep for (?P<time>[0-9]+) seconds", "Sleep for"),
        (r".*?(?P<mins>[0-9]+):(?P<secs>[0-9]+)\.(?P<millisecs>[0-9]+) elapsed", ":"),
        (r"a|b", ""),
        (r"(ab|c)def", "def"),
        (r"def(a|b)c", "def"),
        (r"ab?c", "a"),
        (r"a*bc", "bc"),
        (r"a+b?c", "c"),
        (r"(optional)? required", "required"),
        (r"a(?:bc)?d", "a"),
        (r".*", ""),
        (r"^[0-9]+$", ""),
        (r"^\s*$", ""),
        (r"hello\sworld", "hello"),
        (r"(?i).*error.*", ""),
        (r"(?i)FATAL", ""),
        (r"(?i:foo)bar", "bar"),
        (r"(?m)^hello", "hello"),
        # Invalid regex
        (r"hello(w", ""),
    ],
)
def test_get_literal_from_regex_functionality(regex_str, expected):
    """Test functionality of get_literal_from_regex helper logic"""
    assert get_literal_from_regex(regex_str) == expected


def test_get_literal_from_regex_missing_sre_parse(monkeypatch):
    """Test fallback logic when sre_parse is unavailable."""
    import ramble.util.foms

    monkeypatch.setattr(ramble.util.foms, "sre_parse", None)

    assert get_literal_from_regex(r"Sleep for (?P<time>[0-9]+) seconds") == ""


def test_fom_type_from_value():
    from ramble.util.foms import BetterDirection, FomType

    # Enum instances
    assert FomType.from_value(FomType.CATEGORY) == FomType.CATEGORY
    assert FomType.from_value(FomType.TIME) == FomType.TIME

    # Serialized dicts
    assert (
        FomType.from_value({"name": "CATEGORY", "better_direction": "INAPPLICABLE"})
        == FomType.CATEGORY
    )
    assert FomType.from_value({"name": "time"}) == FomType.TIME

    # Strings
    assert FomType.from_value("category") == FomType.CATEGORY
    assert FomType.from_value("MEASURE") == FomType.MEASURE

    # Invalid / None
    assert FomType.from_value(None) is None
    assert FomType.from_value("invalid_type") is None
    assert FomType.from_value({}) is None
    assert FomType.from_value(123) is None

    # BetterDirection from_value
    assert BetterDirection.from_value(BetterDirection.HIGHER) == BetterDirection.HIGHER
    assert BetterDirection.from_value("higher") == BetterDirection.HIGHER
    assert BetterDirection.from_value("lower") == BetterDirection.LOWER
    assert BetterDirection.from_value(None) is None
    assert BetterDirection.from_value("invalid") is None

    # Title-based from_str
    assert FomType.from_str("categorical") == FomType.CATEGORY
    assert FomType.from_str("informational") == FomType.INFO
    assert FomType.from_str("throughput") == FomType.THROUGHPUT


def test_better_direction_strings():
    from ramble.util.foms import BetterDirection

    assert BetterDirection.HIGHER.as_str() == "higher is better"
    assert BetterDirection.HIGHER.suffix() == " (higher is better)"
    assert str(BetterDirection.HIGHER) == "higher is better"

    assert BetterDirection.LOWER.as_str() == "lower is better"
    assert BetterDirection.LOWER.suffix() == " (lower is better)"
    assert str(BetterDirection.LOWER) == "lower is better"

    assert BetterDirection.INDETERMINATE.as_str() == ""
    assert BetterDirection.INDETERMINATE.suffix() == ""
    assert str(BetterDirection.INDETERMINATE) == ""

    assert BetterDirection.INAPPLICABLE.as_str() == ""
    assert BetterDirection.INAPPLICABLE.suffix() == ""
    assert str(BetterDirection.INAPPLICABLE) == ""


def test_fom_type_strings_and_group_titles():
    from ramble.util.foms import BetterDirection, FomType

    # Titles
    assert FomType.TIME.title == "Time"
    assert FomType.THROUGHPUT.title == "Throughput"
    assert FomType.MEASURE.title == "Measure"
    assert FomType.CATEGORY.title == "Categorical"
    assert FomType.INFO.title == "Informational"
    assert FomType.UNDEFINED.title == "Undefined"

    # formatted_str and __str__
    assert str(FomType.TIME) == "Time (lower is better)"
    assert str(FomType.THROUGHPUT) == "Throughput (higher is better)"
    assert str(FomType.MEASURE) == "Measure"
    assert FomType.MEASURE.formatted_str(BetterDirection.HIGHER) == "Measure (higher is better)"
    assert str(FomType.CATEGORY) == "Categorical"
    assert str(FomType.INFO) == "Informational"
    assert str(FomType.UNDEFINED) == "Undefined"

    # group_title
    assert FomType.TIME.group_title() == "Time FOMs (lower is better)"
    assert FomType.THROUGHPUT.group_title() == "Throughput FOMs (higher is better)"
    assert FomType.MEASURE.group_title() == "Measure FOMs"
    assert FomType.MEASURE.group_title(BetterDirection.HIGHER) == "Measure FOMs (higher is better)"
    assert FomType.CATEGORY.group_title() == "Categorical FOMs"
    assert FomType.INFO.group_title() == "Informational FOMs"
    assert FomType.UNDEFINED.group_title() == "Undefined FOMs"
