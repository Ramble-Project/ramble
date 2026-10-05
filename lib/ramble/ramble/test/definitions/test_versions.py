# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

from ramble.definitions.versions import ObjectVersion
from ramble.language import language_base


class TestObjectVersion:
    """Tests for the ObjectVersion class."""

    def test_init(self):
        """Test that the ObjectVersion constructor works correctly."""
        obj_ver = ObjectVersion(
            version_number="1.2.3",
            description="description",
            origin_type="origin_type",
            preferred=True,
        )
        assert str(obj_ver.version) == "1.2.3"
        assert obj_ver.description == "description"
        assert obj_ver.origin_type == "origin_type"
        assert obj_ver.preferred is True

    def test_init_invalid_version(self):
        """Test that the ObjectVersion constructor raises an error for invalid versions."""
        with pytest.raises(language_base.DirectiveError):
            ObjectVersion(version_number="invalid_version")

    def test_copy(self):
        """Test that the copy method works correctly."""
        obj_ver = ObjectVersion(
            version_number="1.2.3",
            description="description",
            origin_type="origin_type",
            preferred=True,
        )
        obj_ver_copy = obj_ver.copy()
        assert obj_ver is not obj_ver_copy
        assert obj_ver.version == obj_ver_copy.version
        assert obj_ver.description == obj_ver_copy.description
        assert obj_ver.origin_type == obj_ver_copy.origin_type
        assert obj_ver.preferred == obj_ver_copy.preferred

    def test_str(self):
        """Test that the __str__ method works correctly."""
        obj_ver = ObjectVersion(version_number="1.2.3")
        assert str(obj_ver) == "1.2.3"

    @pytest.mark.parametrize(
        "version,variant,expected",
        [
            ("1.2.3", "foo@1.2.3", True),
            ("1.2.3", "foo@1.2.4", False),
            ("1.2.3", "foo@:1.2.3", True),
            ("1.2.3", "foo@:1.2.2", False),
            ("1.2.3", "foo@1.2.3:", True),
            ("1.2.3", "foo@1.2.4:", False),
            ("1.2.3", "foo@1.2.2:1.2.4", True),
            ("1.2.3", "foo@1.2.4:1.2.5", False),
        ],
    )
    def test_satisfies(self, version, variant, expected):
        """Test that the satisfies method works correctly."""
        obj_ver = ObjectVersion(version_number=version)
        assert obj_ver.satisfies(variant) is expected
