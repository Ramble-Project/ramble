# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.config
import ramble.repository
import ramble.schema.merged
import ramble.schema.repo_schema


def test_repo_schema_generator():
    props = ramble.schema.repo_schema.make_repo_properties("my_custom_repos")
    assert "my_custom_repos" in props
    assert props["my_custom_repos"]["type"] == "array"

    schema = ramble.schema.repo_schema.make_repo_schema("my_custom_repos")
    assert schema["type"] == "object"
    assert schema["properties"] == props
    assert schema["title"] == "Ramble my custom repository configuration file schema"


def test_repo_sections_match_object_types():
    repo_sections_from_types = {
        obj_info["config_section"] for obj_info in ramble.repository.type_definitions.values()
    }
    repo_sections_from_schema = set(ramble.schema.repo_schema.REPO_SECTIONS)
    assert repo_sections_from_types == repo_sections_from_schema


def test_merged_properties_contain_all_repo_sections():
    for section in ramble.schema.repo_schema.REPO_SECTIONS:
        assert section in ramble.schema.merged.properties
        assert section in ramble.config.section_schemas


@pytest.mark.parametrize("section_name", ramble.schema.repo_schema.REPO_SECTIONS)
def test_individual_repo_schema_modules(section_name):
    import importlib

    mod = importlib.import_module(f"ramble.schema.{section_name}")
    assert hasattr(mod, "properties")
    assert hasattr(mod, "schema")
    assert section_name in mod.properties
    assert mod.schema["properties"] == mod.properties


def test_schema_attribute_error():
    with pytest.raises(AttributeError, match="has no attribute 'nonexistent'"):
        _ = ramble.schema.nonexistent
