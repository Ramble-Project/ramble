# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import copy
import enum
import io

import ramble.error
import ramble.util.ramble_yaml as ryaml


class _SampleEnum(enum.Enum):
    ALPHA = "alpha"
    BETA = 2


def test_ryaml_wrapper_types():
    assert isinstance(ryaml.ryaml_type("hello"), ryaml.ryaml_str)
    assert isinstance(ryaml.ryaml_type(42), ryaml.ryaml_int)
    assert isinstance(ryaml.ryaml_type({"a": 1}), ryaml.ryaml_dict)
    assert isinstance(ryaml.ryaml_type([1, 2]), ryaml.ryaml_list)

    # Already wrapped objects are returned unchanged
    s = ryaml.ryaml_str("wrapped")
    assert ryaml.ryaml_type(s) is s

    # Booleans and floats are passed through without wrapping as ryaml_int
    assert ryaml.ryaml_type(True) is True
    assert ryaml.ryaml_type(3.14) == 3.14

    b_custom = ryaml.ryaml_bool(True, string_val="yes")
    assert str(b_custom) == "yes"
    assert repr(b_custom) == "yes"

    b_true = ryaml.ryaml_bool(True)
    b_false = ryaml.ryaml_bool(False)
    assert str(b_true) == "True"
    assert str(b_false) == "False"


def test_load_and_override_keys(capsys):
    raw = ryaml.load("a: 1\n")
    assert raw == {"a": 1}

    cfg_str = io.StringIO(
        "ramble:\n" "  override_key::\n" "    x: 1\n" '  "quoted:": 2\n' "  pkg@1.0:: 3\n"
    )
    cfg_str.name = "test_cfg.yaml"
    data = ryaml.load_config(cfg_str)

    assert ryaml.marked(data)
    override_k, quoted_k, spec_k = list(data["ramble"].keys())

    assert override_k == "override_key" and override_k.override is True
    assert quoted_k == "quoted:" and quoted_k.override is False
    assert spec_k == "pkg@1.0:" and spec_k.override is False

    # Exercise list-to-tuple hashable key conversion and duplicate detection
    from ruamel.yaml.nodes import MappingNode, ScalarNode

    loader = ryaml.OrderedLineLoader(io.StringIO())
    loader.construct_object = lambda node, deep=False: ["a", "b"]

    class _MockMark:
        name = "list_keys.yaml"
        line = 0
        column = 0

    class _MockMap(dict):
        def _yaml_set_kv_line_col(self, *args, **kwargs):
            pass

        def __setitem__(self, key, value):
            pass

    k1 = ScalarNode(tag="tag:yaml.org,2002:str", value="k1")
    k2 = ScalarNode(tag="tag:yaml.org,2002:str", value="k2")
    k1.start_mark = _MockMark()
    k2.start_mark = _MockMark()
    map_node = MappingNode(tag="tag:yaml.org,2002:map", value=[(k1, k1), (k2, k2)])
    map_node.start_mark = _MockMark()

    # ConstructorError is expected from super().construct_mapping on raw list keys,
    # after our duplicate-key check converts ["a", "b"] -> ("a", "b") and warns.
    try:
        loader.construct_mapping(map_node, _MockMap())
    except Exception:
        pass
    assert "Duplicate key \"('a', 'b')\" detected" in capsys.readouterr().err


def test_dump_and_dump_config():
    shared = [1, 2]
    payload = ryaml.ryaml_dict(
        [
            ("flag_cap_true", ryaml.ryaml_bool(True, string_val="True")),
            ("flag_ryaml_true", ryaml.ryaml_bool(True)),
            ("flag_plain_true", True),
            ("flag_plain_false", False),
            ("none_val", None),
            ("multiline", ryaml.ryaml_str("line1\nline2")),
            ("enum_str", _SampleEnum.ALPHA),
            ("enum_int", _SampleEnum.BETA),
            ("first_ref", shared),
            ("second_ref", shared),
        ]
    )
    override_key = ryaml.ryaml_str("section")
    override_key.override = True
    payload[override_key] = ryaml.ryaml_dict([("a", ryaml.ryaml_int(7))])

    safe_out = ryaml.dump(payload)
    assert "flag_cap_true: True" in safe_out
    assert "flag_ryaml_true: true" in safe_out
    assert "flag_plain_true: true" in safe_out
    assert "flag_plain_false: false" in safe_out
    assert "enum_str: alpha" in safe_out
    assert "enum_int: 2" in safe_out
    # Aliases must never be emitted
    assert "&id" not in safe_out
    assert "*id" not in safe_out

    cfg_out = ryaml.dump_config(payload, default_flow_style=False)
    assert "flag_cap_true: True" in cfg_out
    assert "flag_ryaml_true: true" in cfg_out
    assert "flag_plain_true: true" in cfg_out
    assert "none_val: null" in cfg_out
    assert "multiline: |-\n  line1\n  line2" in cfg_out
    assert "'section:':\n  a: 7" in cfg_out


def test_dump_annotated_blame():
    stream_in = io.StringIO('ramble:\n  empty: ""\n  nothing: null\n  val: hello\n')
    stream_in.name = "/tmp/user@host}dir/ramble.yaml"
    data = ryaml.load_config(stream_in)

    # Insert an unmarked top-level key to exercise the `saved is None` annotation branch
    combined = ryaml.ryaml_dict([("unmarked", 1), ("loaded", data)])

    # Return string when stream=None
    annotated_str = ryaml.dump_config(combined, blame=True, default_flow_style=False)
    assert "---" in annotated_str
    assert "/tmp/user@host}dir/ramble.yaml" in annotated_str
    assert "nothing: null" in annotated_str
    assert "val: hello" in annotated_str

    # Write directly to stream when stream is provided
    out_stream = io.StringIO()
    ret = ryaml.dump_annotated(data, stream=out_stream, default_flow_style=False)
    assert ret is None
    assert "val: hello" in out_stream.getvalue()


def test_commented_map_deepcopy_preserves_custom_attrs():
    src = "ramble:  # header\n  variables:\n    foo: bar  # inline\n"
    parsed = ryaml.load_config(src)
    parsed._custom_attr = {"tag": "preserved"}

    copied = copy.deepcopy(parsed)
    assert copied._custom_attr == {"tag": "preserved"}
    assert copied._custom_attr is not parsed._custom_attr
    assert ryaml.dump_config(copied, default_flow_style=False) == src


def test_ramble_yaml_error():
    err = ryaml.RambleYAMLError("Failed to parse YAML", ValueError("bad token"))
    assert isinstance(err, ramble.error.RambleError)
    assert "Failed to parse YAML" in str(err)
    assert "bad token" in str(err)
