# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import ramble.language.shared_language
from ramble.language.language_base import DirectiveMeta


class MockObject(metaclass=DirectiveMeta):
    name = "mock_obj"
    __module__ = "ramble.app"
    required_utilities: dict = {}

    ramble.language.shared_language.requires_utility(
        name="my_ext_dep",
        git="https://github.com/my/ext_dep.git",
        commit="v1.0",
        when="mock_when=True",
    )

    ramble.language.shared_language.requires_utility(
        name="my_ext_dep_allow",
        git="https://github.com/my/ext_dep.git",
        commit="v1.0",
        when="mock_when=True",
        allow_external=True,
    )

    ramble.language.shared_language.requires_utility(
        name="my_ext_dep_no_allow",
        git="https://github.com/my/ext_dep.git",
        commit="v1.0",
        when="mock_when=True",
        allow_external=False,
    )

    ramble.language.shared_language.requires_utility(
        name="my_ext_dep_allow_str",
        git="https://github.com/my/ext_dep.git",
        commit="v1.0",
        when="mock_when=True",
        allow_external="True",
    )

    ramble.language.shared_language.requires_utility(
        name="my_ext_dep_no_allow_str",
        git="https://github.com/my/ext_dep.git",
        commit="v1.0",
        when="mock_when=True",
        allow_external="False",
    )


def test_requires_utility_directive_parsing():
    obj = MockObject()
    when_list = ["mock_when=True"]
    when_key = frozenset(when_list)
    assert hasattr(obj, "required_utilities")
    assert when_key in obj.required_utilities

    ext_dep = obj.required_utilities[when_key]["my_ext_dep"]
    assert ext_dep["git"] == "https://github.com/my/ext_dep.git"
    assert ext_dep["commit"] == "v1.0"
    assert ext_dep["when"] == when_list
    assert ext_dep["allow_external"] is True  # Default is True

    ext_dep_allow = obj.required_utilities[when_key]["my_ext_dep_allow"]
    assert ext_dep_allow["allow_external"] is True

    ext_dep_no_allow = obj.required_utilities[when_key]["my_ext_dep_no_allow"]
    assert ext_dep_no_allow["allow_external"] is False

    ext_dep_allow_str = obj.required_utilities[when_key]["my_ext_dep_allow_str"]
    assert ext_dep_allow_str["allow_external"] is True

    ext_dep_no_allow_str = obj.required_utilities[when_key]["my_ext_dep_no_allow_str"]
    assert ext_dep_no_allow_str["allow_external"] is False
