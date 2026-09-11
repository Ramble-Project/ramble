# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""This package contains the underlying implementation for the language
directives, which are to allow functions to be invoked at class level
"""

import abc
import collections
import copy
import functools
import inspect
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Type, Union

import llnl.util.lang

import ramble.language.language_helpers
from ramble.error import DirectiveError
from ramble.util import directives
from ramble.util.logger import logger

__all__ = ["DirectiveMeta", "DirectiveDictDescriptor", "DirectiveError"]


def _impossible_when_warning(directive_name, obj_type, obj_name, message, args, kwargs):
    arg_lines = ["Directive Arguments:"] + [f" - {arg}" for arg in args] if args else []
    kwarg_lines = (
        ["Directive Keyword Arguments:"] + [f"  {k} = {v}" for k, v in kwargs.items()]
        if kwargs
        else []
    )

    parts = [
        f'Directive "{directive_name}"'
        f'{f" in {obj_type} {obj_name}" if obj_name and obj_type else ""} '
        "has an impossible when condition:",
        message,
        *arg_lines,
        *kwarg_lines,
    ]

    logger.warn("\n".join(parts))


#: These are variant names used by ramble internally; applications can't use
#: them
reserved_names: List[str] = []

namespaces = [
    "ramble.app",
    "ramble.mod",
    "ramble.pkg_man",
    "ramble.package_manager",
    "ramble.wm",
    "ramble.workflow_manager",
    "ramble.sys",
    "ramble.system",
    "ramble.plat",
    "ramble.platform",
    "ramble.base_cls",
    "ramble.modifier",
    "ramble.ext_dep",
    "ramble.utility",
]

_UNSET = object()


class DirectiveDictDescriptor:
    """A descriptor that lazily executes directives on first access."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.private_name = f"_{name}"

    def _evaluate_class(self, cls: type) -> Any:
        """Lazily evaluate directives on the class if not already done."""
        val = cls.__dict__.get(self.private_name, _UNSET)
        if val is not _UNSET:
            return val

        dicts_to_init, directives_to_run = DirectiveMeta._get_execution_plan(self.name)
        for dictionary in dicts_to_init:
            if cls.__dict__.get(f"_{dictionary}", _UNSET) is _UNSET:
                init_val = DirectiveMeta._directive_init_values.get(dictionary, {})
                setattr(cls, f"_{dictionary}", copy.deepcopy(init_val))

        directives_list = getattr(cls, "_directives_to_be_executed", [])
        DirectiveMeta._executing_directives_depth += 1
        try:
            for directive_name, directive in directives_list:
                if directive_name in directives_to_run:
                    DirectiveMeta._current_directive = directive
                    try:
                        directive(cls)
                    finally:
                        DirectiveMeta._current_directive = None
        finally:
            DirectiveMeta._executing_directives_depth -= 1

        res = cls.__dict__.get(self.private_name, _UNSET)
        return res if res is not _UNSET else None

    def __get__(self, obj: Any, objtype: Optional[type] = None) -> Any:
        if obj is None:
            if objtype is None:
                return self
            return self._evaluate_class(objtype)

        target_cls = objtype if objtype is not None else type(obj)
        cls_val = self._evaluate_class(target_cls)
        inst_val = copy.deepcopy(cls_val) if cls_val is not None else None
        obj.__dict__[self.name] = inst_val
        return inst_val


class DirectiveMeta(abc.ABCMeta):
    """Flushes the directives that were temporarily stored in the staging
    area into the package.
    """

    # Depth counter indicating whether directives are actively being executed
    _executing_directives_depth: int = 0

    # Registry mapping directive_name -> Tuple[dict_name, ...]
    _directive_to_dicts: Dict[str, Tuple[str, ...]] = {}
    _dict_to_directives: Dict[str, List[str]] = collections.defaultdict(list)
    # Cache of DirectiveDictDescriptor instances
    _descriptor_cache: Dict[str, DirectiveDictDescriptor] = {}
    # Set of all known directive dictionary names
    _directive_dict_names: Set[str] = set()
    # Map of dict_name -> initial value template
    _directive_init_values: Dict[str, Any] = {}
    # List of directives to be executed for the class being defined, preserving definition order
    _directives_to_be_executed: List[Tuple[str, Callable[..., Any]]] = []
    # Directive functions and classes
    _directive_functions: Dict[str, Callable[..., Any]] = {}
    _directive_classes: Dict[str, type] = {}
    _directive_types: Dict[str, str] = {}
    _when_constraints_from_context: List[str] = []
    _default_args: List[dict] = []
    _current_directive: Optional[Callable[..., Any]] = None

    @staticmethod
    def push_to_context(when_condition: str) -> None:
        """Push a when condition onto the context stack."""
        DirectiveMeta._when_constraints_from_context.append(when_condition)
        impossible, message = ramble.language.language_helpers.is_when_impossible(
            DirectiveMeta._when_constraints_from_context
        )
        if impossible:
            logger.warn(f"Entering an impossible 'when' context: {message}")

    @staticmethod
    def pop_from_context() -> str:
        """Pop the last when condition from the context stack."""
        return DirectiveMeta._when_constraints_from_context.pop()

    @staticmethod
    def push_default_args(default_args: Dict[str, Any]) -> None:
        """Push default arguments onto the stack."""
        DirectiveMeta._default_args.append(default_args)

    @staticmethod
    def pop_default_args() -> dict:
        """Pop default arguments from the stack."""
        return DirectiveMeta._default_args.pop()

    def __new__(
        cls: Type["DirectiveMeta"], name: str, bases: tuple, attr_dict: dict
    ) -> "DirectiveMeta":
        # Initialize the attribute containing the list of directives
        # to be executed following MRO order and class definition order.
        merged: List[Tuple[str, Callable[..., Any]]] = []
        sources = [getattr(b, "_directives_to_be_executed", None) or [] for b in reversed(bases)]
        for source in sources:
            merged.extend(source)

        for _, directive in DirectiveMeta._directives_to_be_executed:
            try:
                directive._defining_class = name  # type: ignore[attr-defined]
            except (AttributeError, TypeError):
                pass

        merged = list(llnl.util.lang.dedupe(merged))
        merged.extend(DirectiveMeta._directives_to_be_executed)

        attr_dict["_directives_to_be_executed"] = merged
        DirectiveMeta._directives_to_be_executed.clear()

        # Add descriptors for all known directive dictionaries
        for dict_name in DirectiveMeta._directive_dict_names:
            attr_dict[f"_{dict_name}"] = _UNSET
            attr_dict[dict_name] = DirectiveMeta._get_descriptor(dict_name)

        attr_dict["_directive_functions"] = dict(DirectiveMeta._directive_functions)
        attr_dict["_directive_classes"] = dict(DirectiveMeta._directive_classes)
        attr_dict["_directive_types"] = dict(DirectiveMeta._directive_types)
        attr_dict["_directive_dict_names"] = set(DirectiveMeta._directive_dict_names)

        return super().__new__(cls, name, bases, attr_dict)

    def __init__(cls: "DirectiveMeta", name: str, bases: tuple, attr_dict: dict) -> None:
        super().__init__(name, bases, attr_dict)
        directives.define_directive_methods_on_class(cls)

    def __setattr__(cls: "DirectiveMeta", name: str, value: Any) -> None:
        if name in DirectiveMeta._directive_dict_names:
            super().__setattr__(f"_{name}", value)
        else:
            super().__setattr__(name, value)

    @classmethod
    def register_directive(cls, name: str, dicts: Tuple[str, ...]) -> None:
        """Called by directive decorator to register relationships."""
        DirectiveMeta._directive_to_dicts[name] = dicts
        for d in dicts:
            if name not in DirectiveMeta._dict_to_directives[d]:
                DirectiveMeta._dict_to_directives[d].append(name)

    @staticmethod
    def _get_descriptor(name: str) -> DirectiveDictDescriptor:
        """Returns a singleton descriptor for the given dictionary name."""
        if name not in DirectiveMeta._descriptor_cache:
            DirectiveMeta._descriptor_cache[name] = DirectiveDictDescriptor(name)
        return DirectiveMeta._descriptor_cache[name]

    @property
    def preferred_version(cls: "DirectiveMeta") -> Optional[Any]:
        _ = getattr(cls, "known_versions", None)
        return getattr(cls, "_preferred_version", None)

    @preferred_version.setter
    def preferred_version(cls: "DirectiveMeta", value: Optional[Any]) -> None:
        cls._preferred_version = value

    @staticmethod
    def _get_execution_plan(target_dict: str) -> Tuple[List[str], List[str]]:
        """Calculates the closure of dicts and directives needed to populate target_dict."""
        dicts_involved = {target_dict}
        directives_involved: List[str] = []
        stack = [target_dict]

        while stack:
            current_dict = stack.pop()

            for directive_name in DirectiveMeta._dict_to_directives.get(current_dict, ()):
                if directive_name in directives_involved:
                    continue

                directives_involved.append(directive_name)

                for other_dict in DirectiveMeta._directive_to_dicts.get(directive_name, ()):
                    if other_dict not in dicts_involved:
                        dicts_involved.add(other_dict)
                        stack.append(other_dict)

        return sorted(dicts_involved), directives_involved

    @classmethod
    def directive(
        cls: Type["DirectiveMeta"],
        dicts: Union[Sequence[str], str, None] = None,
        init_value: Any = _UNSET,
        language_type: str = "shared",
    ) -> Callable[..., Any]:
        """Decorator for Ramble directives."""
        if dicts is None or dicts == ():
            dicts_tuple: Tuple[str, ...] = ()
        elif isinstance(dicts, str):
            dicts_tuple = (dicts,)
        elif isinstance(dicts, Sequence):
            dicts_tuple = tuple(dicts)
        else:
            message = f"dicts arg must be list, tuple, or string. Found {type(dicts)}"
            raise TypeError(message)

        if init_value is _UNSET:
            init_value = {}

        # Add the dictionary names if not already there
        for attr_name in dicts_tuple:
            DirectiveMeta._directive_dict_names.add(attr_name)
            DirectiveMeta._directive_init_values[attr_name] = init_value

        def _decorator(decorated_function: Callable[..., Any]) -> Callable[..., Any]:
            func_name = decorated_function.__name__
            DirectiveMeta.register_directive(func_name, dicts_tuple)
            DirectiveMeta._directive_classes[func_name] = cls
            DirectiveMeta._directive_types[func_name] = language_type
            DirectiveMeta._directive_functions[func_name] = decorated_function

            @functools.wraps(decorated_function)
            def _wrapper(*args: Any, **_kwargs: Any) -> Any:
                # First merge default args with kwargs
                if DirectiveMeta._default_args:
                    kwargs = {}
                    for default_args in DirectiveMeta._default_args:
                        kwargs.update(default_args)
                    kwargs.update(_kwargs)
                else:
                    kwargs = _kwargs

                # Inject when arguments from the context
                if DirectiveMeta._when_constraints_from_context:
                    sig = inspect.signature(decorated_function)
                    if "when" not in sig.parameters:
                        msg = (
                            f'directive "{decorated_function.__name__}" cannot be used '
                            'within a "when" context since it does not support a "when=" argument'
                        )
                        raise DirectiveError(msg)

                    when_constraints = list(DirectiveMeta._when_constraints_from_context)

                    if kwargs.get("when"):
                        when_arg = kwargs["when"]
                        directive_id = str(args[0]) if args else ""
                        when_list = ramble.language.language_helpers.build_when_list(
                            when_arg,
                            "DirectiveMeta",
                            directive_id,
                            decorated_function.__name__,
                        )
                        when_constraints.extend(when_list)

                    kwargs["when"] = when_constraints

                if "when" in kwargs:
                    impossible, message = ramble.language.language_helpers.is_when_impossible(
                        kwargs["when"]
                    )
                    if impossible:

                        def _warn_impossible(obj):
                            obj_type = getattr(obj, "origin_type", "")
                            obj_name = getattr(obj, "name", "")
                            _impossible_when_warning(
                                decorated_function.__name__,
                                obj_type,
                                obj_name,
                                message,
                                args,
                                kwargs,
                            )

                        DirectiveMeta._directives_to_be_executed.append(
                            (func_name, _warn_impossible)
                        )
                        return _warn_impossible

                # Handle nested directives passed as arguments
                def remove_directives(arg):
                    if isinstance(arg, (list, tuple)):
                        for a in arg:
                            remove_directives(a)
                    elif callable(arg):
                        DirectiveMeta._directives_to_be_executed = [
                            (n, fn)
                            for n, fn in DirectiveMeta._directives_to_be_executed
                            if fn != arg
                        ]

                remove_directives(args)
                remove_directives(list(kwargs.values()))

                result = decorated_function(*args, **kwargs)

                if result is not None and DirectiveMeta._executing_directives_depth == 0:
                    if isinstance(result, Sequence) and not isinstance(result, (str, bytes)):
                        for item in result:
                            DirectiveMeta._directives_to_be_executed.append((func_name, item))
                    else:
                        DirectiveMeta._directives_to_be_executed.append((func_name, result))

                return result

            return _wrapper

        return _decorator
