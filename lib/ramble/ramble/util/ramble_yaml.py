# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Enhanced YAML parsing for Ramble.

- ``load()`` preserves YAML Marks on returned objects -- this allows
  us to access file and line information later.

- Our load methods use ``OrderedDict`` class instead of YAML's
  default unordered dict.
"""

import collections
import copy
import ctypes
import enum
import io
import re
from typing import Any, Dict, List, Optional

import ruamel.yaml as yaml
from ruamel.yaml.constructor import RoundTripConstructor, SafeConstructor
from ruamel.yaml.representer import RoundTripRepresenter

import llnl.util.tty as tty

import ramble.error
from ramble.util.colors import cescape, cextra, clen, colorize

# Only export load and dump
__all__ = ["load", "dump", "RambleYAMLError"]


# Make new classes so we can add custom attributes.
# Also, use OrderedDict instead of just dict.
class ryaml_dict(collections.OrderedDict):
    _start_mark: Any = None
    _end_mark: Any = None

    def __repr__(self) -> str:
        mappings = (f"{k!r}: {v!r}" for k, v in self.items())
        return "{%s}" % ", ".join(mappings)


class ryaml_list(list):
    _start_mark: Any = None
    _end_mark: Any = None
    __repr__ = list.__repr__


class ryaml_str(str):
    override: bool = False
    _start_mark: Any = None
    _end_mark: Any = None
    __repr__ = str.__repr__


class ryaml_int(int):
    _start_mark: Any = None
    _end_mark: Any = None
    __repr__ = int.__repr__


class ryaml_bool(int):
    string_val: Optional[str] = None
    _start_mark: Any = None
    _end_mark: Any = None

    def __new__(cls, val: Any, string_val: Optional[str] = None) -> "ryaml_bool":
        obj = super().__new__(cls, val)
        obj.string_val = string_val
        return obj

    def __repr__(self) -> str:
        return self.string_val if self.string_val else ("True" if self else "False")

    def __str__(self) -> str:
        return self.string_val if self.string_val else ("True" if self else "False")


#: mapping from ryaml type -> primitive type
ryaml_types = {
    ryaml_str: str,
    ryaml_int: int,
    ryaml_bool: bool,
    ryaml_dict: dict,
    ryaml_list: list,
}

markable_types = set(ryaml_types) | {
    yaml.comments.CommentedSeq,
    yaml.comments.CommentedMap,
}


def _commented_map_deepcopy(self: Any, memo: Any) -> Any:
    res = self.__class__()
    memo[id(self)] = res
    for k, v in self.items():
        res[copy.deepcopy(k, memo)] = copy.deepcopy(v, memo)
    if hasattr(self, yaml.comments.Comment.attrib):
        setattr(
            res,
            yaml.comments.Comment.attrib,
            copy.deepcopy(getattr(self, yaml.comments.Comment.attrib), memo),
        )
    if hasattr(self, "__dict__"):
        for attr, val in self.__dict__.items():
            setattr(res, attr, copy.deepcopy(val, memo))
    return res


yaml.comments.CommentedMap.__deepcopy__ = _commented_map_deepcopy


def ryaml_type(obj: Any) -> Any:
    """Get the corresponding ryaml wrapper type for a primitive type.

    Return:
        (object): ryaml-typed copy of object, or the obj if no wrapper
    """
    for ryaml_t, t in ryaml_types.items():
        if type(obj) is not bool and isinstance(obj, t):
            return ryaml_t(obj) if type(obj) is not ryaml_t else obj
    return obj


def markable(obj: Any) -> bool:
    """Whether an object can be marked."""
    return type(obj) in markable_types


def mark(obj: Any, node: Any) -> None:
    """Add start and end markers to an object."""
    if hasattr(node, "start_mark"):
        obj._start_mark = node.start_mark
    elif hasattr(node, "_start_mark"):
        obj._start_mark = node._start_mark
    if hasattr(node, "end_mark"):
        obj._end_mark = node.end_mark
    elif hasattr(node, "_end_mark"):
        obj._end_mark = node._end_mark


def marked(obj: Any) -> bool:
    """Whether an object has been marked by ramble_yaml."""
    return bool(
        (hasattr(obj, "_start_mark") and obj._start_mark)
        or (hasattr(obj, "_end_mark") and obj._end_mark)
    )


class _SafeOverwriteConstructor(SafeConstructor):
    """SafeConstructor that overwrites duplicate keys when allowed."""

    def check_mapping_key(
        self, node: Any, key_node: Any, mapping: Any, key: Any, value: Any
    ) -> bool:
        if key in mapping and self.allow_duplicate_keys:
            return True
        return super().check_mapping_key(node, key_node, mapping, key, value)


class OrderedLineLoader(RoundTripConstructor):
    """YAML constructor specifically intended for reading Ramble configuration
    files. It preserves order and line numbers. It also has special-purpose
    logic for handling dictionary keys that indicate a Ramble config
    override: namely any key that contains an "extra" ':' character.

    Mappings read in by this constructor behave like an ordered dict.
    Sequences, mappings, and strings also have new attributes,
    ``_start_mark`` and ``_end_mark``, that preserve YAML line
    information in the output data.
    """

    def check_mapping_key(
        self, node: Any, key_node: Any, mapping: Any, key: Any, value: Any
    ) -> bool:
        if key in mapping:
            filename = node.start_mark.name
            line = key_node.start_mark.line + 1
            tty.warn(
                f'Duplicate key "{key}" detected in {filename} at line {line}. '
                "This will overwrite the previous value."
            )
            return True
        return super().check_mapping_key(node, key_node, mapping, key, value)

    def construct_yaml_bool(self, node: Any) -> ryaml_bool:
        value = super().construct_yaml_bool(node)
        b = ryaml_bool(value, string_val=node.value)
        mark(b, node)
        return b

    def construct_yaml_str(self, node: Any) -> ryaml_str:
        value = super().construct_yaml_str(node)
        # There is no specific marker to indicate that we are parsing a key,
        # so this assumes we are talking about a config override key if
        # it ends with a ':' and does not contain a '@' (which can appear
        # in config values that refer to Spack specs)
        # and is not quoted (identified by a non-empty node.style)
        if value and value.endswith(":") and "@" not in value and not node.style:
            s = ryaml_str(value[:-1])
            s.override = True
        else:
            s = ryaml_str(value)
        mark(s, node)
        return s

    def construct_yaml_seq(self, node: Any) -> Any:
        gen = super().construct_yaml_seq(node)
        data = next(gen)
        if markable(data):
            mark(data, node)
        yield data
        list(gen)

    def construct_yaml_map(self, node: Any) -> Any:
        gen = super().construct_yaml_map(node)
        data = next(gen)
        if markable(data):
            mark(data, node)
        yield data
        list(gen)


# register above new constructors
OrderedLineLoader.add_constructor("tag:yaml.org,2002:bool", OrderedLineLoader.construct_yaml_bool)
OrderedLineLoader.add_constructor("tag:yaml.org,2002:map", OrderedLineLoader.construct_yaml_map)
OrderedLineLoader.add_constructor("tag:yaml.org,2002:seq", OrderedLineLoader.construct_yaml_seq)
OrderedLineLoader.add_constructor("tag:yaml.org,2002:str", OrderedLineLoader.construct_yaml_str)


class OrderedLineDumper(RoundTripRepresenter):
    """Representer that preserves ordering and formats ``ryaml_*`` objects.

    This representer preserves insertion ordering of ``ryaml_dict`` objects
    when they're written out. It also has some custom formatters
    for ``ryaml_*`` objects so that they are formatted like their
    regular Python equivalents, instead of ugly YAML pyobjects.
    """

    def ignore_aliases(self, _data: Any) -> bool:
        """Make the dumper NEVER print YAML aliases."""
        return True

    def represent_data(self, data: Any) -> Any:
        result = super().represent_data(data)
        if data is None:
            result.value = ryaml_str("null")
        return result

    def represent_bool(self, data: Any) -> Any:
        if hasattr(data, "string_val") and data.string_val:
            return self.represent_scalar("tag:yaml.org,2002:bool", data.string_val)
        return super().represent_bool(bool(data))

    def represent_str(self, data: Any) -> Any:
        if hasattr(data, "override") and data.override:
            data = data + ":"
        if len(data.splitlines()) > 1:
            return super().represent_scalar("tag:yaml.org,2002:str", data, style="|")
        return super().represent_str(data)


class SafeDumper(RoundTripRepresenter):
    def ignore_aliases(self, _data: Any) -> bool:
        """Make the dumper NEVER print YAML aliases."""
        return True

    def represent_bool(self, data: Any) -> Any:
        if hasattr(data, "string_val") and data.string_val:
            return self.represent_scalar("tag:yaml.org,2002:bool", data.string_val)
        return super().represent_bool(bool(data))


# Make our special objects look like normal YAML ones.
RoundTripRepresenter.add_representer(ryaml_dict, RoundTripRepresenter.represent_dict)
RoundTripRepresenter.add_representer(ryaml_list, RoundTripRepresenter.represent_list)
RoundTripRepresenter.add_representer(ryaml_int, RoundTripRepresenter.represent_int)
RoundTripRepresenter.add_representer(ryaml_bool, RoundTripRepresenter.represent_bool)
RoundTripRepresenter.add_representer(ryaml_str, RoundTripRepresenter.represent_str)
RoundTripRepresenter.add_multi_representer(
    enum.Enum, lambda dumper, data: dumper.represent_data(data.value)
)
OrderedLineDumper.add_representer(ryaml_bool, OrderedLineDumper.represent_bool)
OrderedLineDumper.add_representer(ryaml_str, OrderedLineDumper.represent_str)
SafeDumper.add_representer(ryaml_bool, SafeDumper.represent_bool)


#: Max integer helps avoid passing too large a value to cyaml.
maxint = 2 ** (ctypes.sizeof(ctypes.c_int) * 8 - 1) - 1


def _dump_yaml(
    data: Any,
    stream: Any = None,
    representer: Any = None,
    emitter: Any = None,
    default_flow_style: Optional[bool] = None,
    width: Optional[int] = None,
    **kwargs: Any,
) -> Any:
    y = yaml.YAML(typ="rt")
    if representer is not None:
        y.Representer = representer
    if emitter is not None:
        y.Emitter = emitter
    if default_flow_style is not None:
        y.default_flow_style = default_flow_style
    if width is not None:
        y.width = width
    for attr in (
        "explicit_start",
        "explicit_end",
        "line_break",
        "allow_unicode",
        "canonical",
        "default_style",
        "version",
        "tags",
        "encoding",
    ):
        if attr in kwargs:
            setattr(y, attr, kwargs.pop(attr))
    if "indent" in kwargs:
        indent_val = kwargs.pop("indent")
        if indent_val is not None:
            y.indent(mapping=indent_val, sequence=indent_val)
    if kwargs:
        raise TypeError(
            "Unexpected keyword arguments for YAML dump: %s" % ", ".join(sorted(kwargs))
        )

    if stream is None:
        buf = io.StringIO()
        y.dump(data, buf)
        return buf.getvalue()
    y.dump(data, stream)
    return None


def dump(
    obj: Any,
    default_flow_style: bool = False,
    stream: Any = None,
    Dumper: Any = SafeDumper,
) -> Any:
    return _dump_yaml(
        obj,
        stream=stream,
        representer=Dumper,
        default_flow_style=default_flow_style,
        width=maxint,
    )


#: Global for interactions between LineAnnotationEmitter and dump_annotated().
_annotations: List[str] = []


class LineAnnotationRepresenter(OrderedLineDumper):
    """Representer that passes ``ryaml_str`` values through with marks."""

    def represent_data(self, data: Any) -> Any:
        """Force ryaml_str to be passed through with marks."""
        result = super().represent_data(data)
        if data is None:
            result.value = ryaml_str("null")
        elif isinstance(result.value, str):
            result.value = ryaml_str(result.value)
        if markable(result.value):
            mark(result.value, data)
        return result


_BaseEmitter: Any = getattr(yaml.emitter, "RoundTripEmitter", yaml.emitter.Emitter)


class LineAnnotationEmitter(_BaseEmitter):
    """Emitter that generates per-line annotations.

    Annotations are stored in the ``_annotations`` global. After one
    dump pass, the strings in ``_annotations`` will correspond one-to-one
    with the lines output by the emitter.

    LineAnnotationEmitter records blame information after each line is
    generated. As each line is emitted, it saves file/line info for each
    object printed. At the end of each line, it creates an annotation
    based on the saved mark and stores it in ``_annotations``.

    For an example of how to use this, see ``dump_annotated()``, which
    writes to a ``StringIO`` then joins the lines from that with
    annotations.
    """

    saved: Any = None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        del _annotations[:]
        self.colors = "KgrbmcyGRBMCY"
        self.filename_colors: Dict[str, str] = {}

    def process_scalar(self) -> None:
        super().process_scalar()
        if marked(self.event.value):
            self.saved = self.event.value

    def write_line_break(self, data: Any = None) -> None:
        super().write_line_break(data)
        if self.saved is None:
            _annotations.append(colorize("@K{---}"))
            return

        # append annotations at the end of each line
        if self.saved:
            mark_obj = self.saved._start_mark

            color = self.filename_colors.get(mark_obj.name)
            if not color:
                ncolors = len(self.colors)
                color = self.colors[len(self.filename_colors) % ncolors]
                self.filename_colors[mark_obj.name] = color

            fmt = "@%s{%%s}" % color
            ann = fmt % cescape(str(mark_obj.name))
            if mark_obj.line is not None:
                ann += ":@c{%s}" % (mark_obj.line + 1)
            _annotations.append(colorize(ann))
        else:
            _annotations.append("")


def load_config(*args: Any, **kwargs: Any) -> Any:
    """Load but modify the loader instance so that it will add __line__
    attributes to the returned object and warn on duplicate keys."""
    kwargs["Loader"] = OrderedLineLoader
    return load(*args, **kwargs)


def load(
    stream: Any,
    Loader: Any = None,
    version: Any = None,
    preserve_quotes: Optional[bool] = None,
) -> Any:
    if Loader is None:
        y = yaml.YAML(typ="safe", pure=True)
        y.Constructor = _SafeOverwriteConstructor
    else:
        if issubclass(Loader, RoundTripConstructor):
            y = yaml.YAML(typ="rt")
        else:
            y = yaml.YAML(typ="safe", pure=True)
        y.Constructor = Loader
    y.allow_duplicate_keys = True
    if version is not None:
        y.version = version
    if preserve_quotes is not None:
        y.preserve_quotes = preserve_quotes
    return y.load(stream)


def dump_config(data: Any, stream: Any = None, **kwargs: Any) -> Any:
    blame = kwargs.pop("blame", False)

    if blame:
        return dump_annotated(data, stream=stream, **kwargs)
    else:
        dumper = kwargs.pop("Dumper", OrderedLineDumper)
        return _dump_yaml(data, stream=stream, representer=dumper, **kwargs)


def dump_annotated(data: Any, stream: Any = None, **kwargs: Any) -> Any:
    kwargs.pop("Dumper", None)

    buf = io.StringIO()
    _dump_yaml(
        data,
        stream=buf,
        representer=LineAnnotationRepresenter,
        emitter=LineAnnotationEmitter,
        **kwargs,
    )

    # write_line_break() is not called by YAML for empty lines, so we
    # skip empty lines here with \n+.
    lines = re.split(r"\n+", buf.getvalue().rstrip())

    return_val = False
    if stream is None:
        stream = io.StringIO()
        return_val = True

    # write out annotations and lines, accounting for color
    width = max(clen(a) for a in _annotations) if _annotations else 0
    formats = ["%%-%ds  %%s\n" % (width + cextra(a)) for a in _annotations]

    for f, a, line in zip(formats, _annotations, lines):
        stream.write(f % (a, line))

    if return_val:
        return stream.getvalue()
    return None


class RambleYAMLError(ramble.error.RambleError):
    """Raised when there are issues with YAML parsing."""

    def __init__(self, msg: str, yaml_error: Any) -> None:
        super().__init__(msg, str(yaml_error))
