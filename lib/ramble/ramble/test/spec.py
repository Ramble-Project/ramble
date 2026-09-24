# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

from ramble.spec import Spec


class TestSpec:
    """Tests for the Spec class."""

    @pytest.mark.parametrize(
        "spec_str, expected_name, expected_namespace, expected_fullname",
        [
            ("my-app", "my-app", None, "my-app"),
            ("my-namespace.my-app", "my-app", "my-namespace", "my-namespace.my-app"),
            ("", "", None, ""),
            ("builtin.app.foo", "foo", "builtin", "builtin.app.foo"),
            ("builtin.application.foo", "foo", "builtin", "builtin.app.foo"),
            ("builtin.mod.bar", "bar", "builtin", "builtin.mod.bar"),
            ("builtin.sys.my_sys", "my_sys", "builtin", "builtin.sys.my_sys"),
            ("app.foo", "foo", None, "app.foo"),
            ("org.project.repo.app.foo", "foo", "org.project.repo", "org.project.repo.app.foo"),
            ("org.project.repo.foo", "foo", "org.project.repo", "org.project.repo.foo"),
            ("foo@1.0", "foo", None, "foo"),
            ("builtin.app.foo@1.0", "foo", "builtin", "builtin.app.foo"),
            ("MY-APP", "my-app", None, "my-app"),
            ("Builtin.App.Foo", "foo", "builtin", "builtin.app.foo"),
            ("APP.FOO", "foo", None, "app.foo"),
            ("BUILTIN.APPLICATION.FOO@1.0", "foo", "builtin", "builtin.app.foo"),
            ("Builtin.Foo", "foo", "builtin", "builtin.foo"),
        ],
    )
    def test_init_from_string(
        self, spec_str, expected_name, expected_namespace, expected_fullname
    ):
        s = Spec(spec_str)
        assert s.name == expected_name
        assert s.namespace == expected_namespace
        assert s.fullname == expected_fullname

    def test_init_empty_and_copy(self):
        # Test default constructor
        s_empty = Spec()
        assert s_empty.name is None
        assert s_empty.namespace is None
        assert s_empty.fullname == ""
        assert str(s_empty) == ""

        # Test init from another spec and copy method
        s1 = Spec("my-namespace.my-app")
        assert str(s1) == "my-app"
        s2 = Spec(s1)
        s3 = s1.copy()

        for s in [s2, s3]:
            assert s.name == "my-app"
            assert s.namespace == "my-namespace"
            assert s.fullname == "my-namespace.my-app"
            assert s is not s1
            assert s == s1
            assert hash(s) == hash(s1)

    def test_repr_and_equality(self):
        s1 = Spec("my-namespace.my-app")
        assert "name='my-app'" in repr(s1)
        assert "namespace='my-namespace'" in repr(s1)

        s2 = Spec("my-namespace.my-app")
        s3 = Spec("other-namespace.my-app")
        assert s1 == s2
        assert s1 != s3
        assert s1 != "my-namespace.my-app"
        assert len({s1, s2, s3}) == 2
