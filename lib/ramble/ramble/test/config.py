# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.config


# A crude assertion to check there's no conflicting value.
# It supports only list and dict as containers, instead of
# the more general abstract types.
def _assert_no_conflict_recurse(a, b):
    if a is None or b is None:
        return
    if isinstance(a, dict):
        for k, v in a.items():
            _assert_no_conflict_recurse(v, b.get(k))
    elif isinstance(a, list):
        for i, v in enumerate(a):
            _assert_no_conflict_recurse(v, b[i])
    else:
        assert a == b


def test_default_configs_no_conflict(default_config):
    """Ensure the hard-coded config_defaults do not conflict with etc/defaults/config.yaml"""
    defaults_in_mem = ramble.config.config_defaults["config"]
    assert defaults_in_mem
    for k, v in defaults_in_mem.items():
        in_file_def = ramble.config.get(f"config:{k}")
        _assert_no_conflict_recurse(v, in_file_def)


@pytest.mark.parametrize(
    "config,expected_error",
    [
        (":config:wrong_leading", "Illegal leading"),
        ("config::second::override", "Meaningless second override"),
    ],
)
def test_process_config_path_error(config, expected_error):
    with pytest.raises(ramble.config.ConfigError, match=expected_error):
        ramble.config.process_config_path(config)


def test_duplicate_key_warning(capsys):
    yaml_content = """
ramble:
  config:
    upload:
      type: BigQuery
      uri: some.uri
  config:
    n_repeats: 2
"""
    data = ramble.config.load_config(yaml_content)
    captured = capsys.readouterr()
    assert 'Duplicate key "config" detected' in captured.err
    assert data["ramble"]["config"]["n_repeats"] == 2


def test_unhashable_yaml_keys_coverage():
    import io

    from ruamel.yaml.nodes import MappingNode

    import ramble.config

    loader = ramble.config._RambleLineLoader(io.StringIO())

    # Mock construct_object to return custom keys dynamically with caching
    mock_keys = []

    def mock_construct_object(node, deep=False):
        if node not in loader.constructed_objects:
            loader.constructed_objects[node] = mock_keys.pop(0)
        return loader.constructed_objects[node]

    loader.construct_object = mock_construct_object

    class MockMap(dict):
        def _yaml_set_kv_line_col(self, *args, **kwargs):
            pass

        def __setitem__(self, key, value):
            pass

    from ruamel.yaml.nodes import ScalarNode

    # Mock node having a start_mark for constructor warnings
    class MockMark:
        name = "test"
        line = 0
        column = 0

    dummy = ScalarNode(tag="tag:yaml.org,2002:str", value="dummy")
    dummy.start_mark = MockMark()
    node = MappingNode(tag="tag:yaml.org,2002:map", value=[(dummy, dummy)])
    node.start_mark = MockMark()

    # 1. Key is a list containing unhashable dicts
    # (exercising the inner nested try-except TypeError block)
    mock_keys.append([{"a": 1}])
    loader.construct_mapping(node, MockMap())

    # 2. Key is a mapping (exercising the outer else block)
    dummy2 = ScalarNode(tag="tag:yaml.org,2002:str", value="dummy2")
    dummy2.start_mark = MockMark()
    node2 = MappingNode(tag="tag:yaml.org,2002:map", value=[(dummy2, dummy2)])
    node2.start_mark = MockMark()

    mock_keys.append({"a": 1})
    import ruamel.yaml.constructor

    with pytest.raises(ruamel.yaml.constructor.ConstructorError, match="found unhashable key"):
        loader.construct_mapping(node2, MockMap())


def test_syaml_bool_validates_as_json_boolean():
    """Booleans from Ramble YAML must satisfy a schema's ``"type": "boolean"``.

    Ramble's YAML loader represents ``true``/``false`` as ``syaml_bool``, which
    derives from ``int`` rather than ``bool``, so stock jsonschema rejects it.
    ``ramble.schema`` compensates by redefining the "boolean" type check. This
    test pins that behavior down: without the redefinition every boolean in
    every Ramble config file fails validation.
    """
    import io

    import jsonschema

    import ramble.schema
    import ramble.schema.internals

    import spack.util.spack_yaml as syaml

    schema = ramble.schema.internals.schema
    data = syaml.load_config(io.StringIO("""
internals:
  custom_executables:
    test_exec:
      template:
        - 'echo hello'
      use_mpi: true
      force: false
"""))

    value = data["internals"]["custom_executables"]["test_exec"]["use_mpi"]
    assert isinstance(value, syaml.syaml_bool)
    # The reason this test exists: syaml_bool is not a bool.
    assert not isinstance(value, bool)

    # Control: an unpatched validator rejects it, so the check below has teeth.
    assert list(jsonschema.Draft4Validator(schema).iter_errors(data))

    assert not list(ramble.schema.Validator(schema).iter_errors(data))


def test_non_boolean_still_rejected():
    """Accepting syaml_bool must not weaken boolean type checking generally."""
    import io

    import ramble.schema
    import ramble.schema.internals

    import spack.util.spack_yaml as syaml

    data = syaml.load_config(io.StringIO("""
internals:
  custom_executables:
    test_exec:
      use_mpi: definitely_not_a_boolean
"""))

    validator = ramble.schema.Validator(ramble.schema.internals.schema)
    errors = [e.message for e in validator.iter_errors(data)]
    assert any("is not of type 'boolean'" in e for e in errors), errors
