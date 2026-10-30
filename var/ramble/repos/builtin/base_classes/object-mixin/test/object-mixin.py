# Copyright 2022-2025 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
from unittest import mock

from ramble.repository import get_base_class

ObjectMixin = get_base_class("object-mixin")


class TestObject(ObjectMixin):
    """A test class for the ObjectMixin's workspace_cache decorator."""

    origin_type = "test-object-type"
    _name = "test-object"

    def __init__(self):
        self.call_count = 0

    @ObjectMixin.workspace_cache
    def cached_method(self, *args, **kwargs):
        self.call_count += 1
        return self.call_count


def test_workspace_cache():
    obj = TestObject()
    workspace = mock.Mock()
    workspace.object_command_cache = {}

    # First call
    result1 = obj.cached_method(1, 2, key="value", workspace=workspace)
    assert result1 == 1
    assert obj.call_count == 1

    # Second call with same arguments
    result2 = obj.cached_method(1, 2, key="value", workspace=workspace)
    assert result2 == 1
    assert obj.call_count == 1

    # Call with different args
    result3 = obj.cached_method(3, 4, key="value", workspace=workspace)
    assert result3 == 2
    assert obj.call_count == 2

    # Call with different kwargs
    result4 = obj.cached_method(1, 2, key="new_value", workspace=workspace)
    assert result4 == 3
    assert obj.call_count == 3

    # Verify cache contents
    assert len(workspace.object_command_cache) == 3

    # Without workspace= or obj.workspace, the method executes without caching
    result5 = obj.cached_method(1, 2)
    assert result5 == 4
    assert obj.call_count == 4

    # With obj.workspace set, caching works without passing workspace=
    obj.workspace = workspace
    assert obj.cached_method(1, 2, env={"PATH": "/bin"}) == 5
    assert obj.cached_method(1, 2, env={"PATH": "/bin"}) == 5
    assert obj.call_count == 5


def test_satisfy_when_without_expander():
    obj = TestObject()
    assert obj.satisfy_when("any_condition") is True
    obj.app_inst = None
    assert obj.satisfy_when("any_condition") is True
