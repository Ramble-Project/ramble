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

_UNSET = object()


def _copy_directive_value(val: Any) -> Any:
    """Fast copy helper for directive values.

    Returns primitives and immutables directly, allocates new empty containers
    for empty collections, and deepcopies populated collections for isolation.
    """
    if val is None or isinstance(val, (int, float, str, bool, tuple, frozenset)):
        return val
    if not val:
        return type(val)()
    return copy.deepcopy(val)


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

        dicts_to_init, directives_to_run = DirectiveMeta.get_cached_execution_plan(self.name)
        class_values = getattr(cls, "_class_directive_values", {})
        initialized_dicts = []
        for dictionary in dicts_to_init:
            if cls.__dict__.get(f"_{dictionary}", _UNSET) is _UNSET:
                if dictionary in class_values:
                    init_val = class_values[dictionary]
                else:
                    init_val = DirectiveMeta._directive_init_values.get(dictionary, {})
                setattr(cls, f"_{dictionary}", _copy_directive_value(init_val))
                initialized_dicts.append(dictionary)

        directives_list = getattr(cls, "_directives_to_be_executed", [])
        DirectiveMeta._executing_directives_depth += 1
        try:
            for directive_name, directive in directives_list:
                if directive_name in directives_to_run:
                    directive(cls)
        except Exception:
            for dictionary in initialized_dicts:
                setattr(cls, f"_{dictionary}", _UNSET)
            raise
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
        inst_val = _copy_directive_value(cls_val)
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
    # Cache of execution plans: dict_name -> (dicts_to_init, set_of_directives_to_run)
    _execution_plan_cache: Dict[str, Tuple[List[str], Set[str]]] = {}
    # Set of all known directive dictionary names
    _directive_dict_names: Set[str] = set()
    # Map of dict_name -> initial value template
    _directive_init_values: Dict[str, Any] = {}
    # List of directives to be executed for the class being defined, preserving definition order
    _directives_to_be_executed: List[Tuple[str, Any]] = []
    # Directive functions and classes
    _directive_functions: Dict[str, Callable[..., Any]] = {}
    _directive_classes: Dict[str, type] = {}
    _directive_types: Dict[str, str] = {}
    # Workload-related dictionaries referenced by environment_variable in shared_language
    # that belong exclusively to applications
    _cross_boundary_app_dicts: Set[str] = {
        "workloads",
        "workload_groups",
        "workload_group_vars",
        "workload_group_env_vars",
    }
    # Dynamic mapping of object types to their exclusive directive dictionaries
    _type_scoped_dicts: Dict[str, Set[str]] = collections.defaultdict(set)
    # Set of dictionaries registered by shared directives
    _shared_dict_names: Set[str] = set()
    _when_constraints_from_context: List[str] = []
    _default_args: List[dict] = []

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

    @classmethod
    def __prepare__(metacls, *args: Any, **kwds: Any) -> Any:
        DirectiveMeta._directives_to_be_executed.clear()
        DirectiveMeta._when_constraints_from_context.clear()
        DirectiveMeta._default_args.clear()
        return super().__prepare__(*args, **kwds)

    def __new__(
        cls: Type["DirectiveMeta"], name: str, bases: tuple, attr_dict: dict
    ) -> "DirectiveMeta":
        # Initialize the attribute containing the list of directives
        # to be executed following MRO order and class definition order.
        merged: List[Tuple[str, Any]] = []
        sources = [getattr(b, "_directives_to_be_executed", None) or [] for b in reversed(bases)]
        for source in sources:
            merged.extend(source)

        defining_id = object()
        for _, directive in DirectiveMeta._directives_to_be_executed:
            try:
                directive._defining_class = defining_id
            except (AttributeError, TypeError):
                pass

        merged.extend(DirectiveMeta._directives_to_be_executed)
        DirectiveMeta._directives_to_be_executed.clear()

        # Deduplicate directives by callable identity to prevent double execution
        seen_fns = set()
        deduped: List[Tuple[str, Any]] = []
        for directive_name, fn in merged:
            if fn not in seen_fns:
                seen_fns.add(fn)
                deduped.append((directive_name, fn))
        merged = deduped

        attr_dict["_directives_to_be_executed"] = merged

        # Determine language types to scope descriptors
        lang_types = set(attr_dict.get("_language_types", [])) | set(
            attr_dict.get("_language_classes", [])
        )
        for base in bases:
            lang_types |= set(getattr(base, "_language_types", [])) | set(
                getattr(base, "_language_classes", [])
            )

        if lang_types:
            relevant_dicts = set()
            for d in DirectiveMeta._directive_dict_names:
                scoped_types = [
                    t for t, dicts in DirectiveMeta._type_scoped_dicts.items() if d in dicts
                ]
                if not scoped_types or any(t in lang_types for t in scoped_types):
                    relevant_dicts.add(d)
        else:
            relevant_dicts = set(DirectiveMeta._directive_dict_names)

        # Collect class-level attribute initial values
        class_directive_values = {}
        for base in bases:
            if hasattr(base, "_class_directive_values"):
                class_directive_values.update(base._class_directive_values)

        # Add descriptors for known directive dictionaries
        for dict_name in relevant_dicts:
            if dict_name in attr_dict and attr_dict[
                dict_name
            ] is not DirectiveMeta._get_descriptor(dict_name):
                val = attr_dict.pop(dict_name)
                default_init = DirectiveMeta._directive_init_values.get(dict_name, {})
                if default_init is None or isinstance(val, type(default_init)):
                    class_directive_values[dict_name] = val
            attr_dict.setdefault(f"_{dict_name}", _UNSET)
            attr_dict[dict_name] = DirectiveMeta._get_descriptor(dict_name)

        attr_dict["_class_directive_values"] = class_directive_values

        attr_dict["_directive_functions"] = dict(DirectiveMeta._directive_functions)
        attr_dict["_directive_classes"] = dict(DirectiveMeta._directive_classes)
        attr_dict["_directive_types"] = dict(DirectiveMeta._directive_types)
        attr_dict["_directive_dict_names"] = relevant_dicts

        return super().__new__(cls, name, bases, attr_dict)

    def __init__(cls: "DirectiveMeta", name: str, bases: tuple, attr_dict: dict) -> None:
        super().__init__(name, bases, attr_dict)
        directives.define_directive_methods_on_class(cls)

        # Execute eager directives (directives without target dictionaries)
        DirectiveMeta._executing_directives_depth += 1
        try:
            for directive_name, directive in getattr(cls, "_directives_to_be_executed", []):
                if not DirectiveMeta._directive_to_dicts.get(directive_name):
                    directive(cls)
        finally:
            DirectiveMeta._executing_directives_depth -= 1

    def __setattr__(cls: "DirectiveMeta", name: str, value: Any) -> None:
        if name in DirectiveMeta._directive_dict_names:
            super().__setattr__(f"_{name}", value)
        else:
            super().__setattr__(name, value)

    @classmethod
    def register_directive(cls, name: str, dicts: Tuple[str, ...]) -> None:
        """Called by directive decorator to register relationships."""
        DirectiveMeta._execution_plan_cache.clear()
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

    @staticmethod
    def get_cached_execution_plan(target_dict: str) -> Tuple[List[str], Set[str]]:
        """Returns cached execution plan with directives as a set for O(1) membership check."""
        if target_dict not in DirectiveMeta._execution_plan_cache:
            dicts_to_init, directives_to_run = DirectiveMeta._get_execution_plan(target_dict)
            DirectiveMeta._execution_plan_cache[target_dict] = (
                dicts_to_init,
                set(directives_to_run),
            )
        return DirectiveMeta._execution_plan_cache[target_dict]

    @property
    def preferred_version(cls: "DirectiveMeta") -> Optional[Any]:
        for ver in getattr(cls, "known_versions", {}).values():
            if getattr(ver, "preferred", False):
                return ver
        return None

    @preferred_version.setter
    def preferred_version(cls: "DirectiveMeta", value: Optional[Any]) -> None:
        if not hasattr(cls, "known_versions"):
            return
        for ver in cls.known_versions.values():
            if hasattr(ver, "preferred"):
                ver.preferred = False
        if value is not None:
            try:
                value.preferred = True
            except (AttributeError, TypeError):
                pass
            ver_key = (
                getattr(value, "version_number", None)
                or getattr(value, "version", None)
                or str(value)
            )
            cls.known_versions[ver_key] = value

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

        # Add the dictionary names and auto-register type scoping
        for attr_name in dicts_tuple:
            DirectiveMeta._directive_dict_names.add(attr_name)
            if init_value is not _UNSET:
                DirectiveMeta._directive_init_values[attr_name] = init_value
            elif attr_name not in DirectiveMeta._directive_init_values:
                DirectiveMeta._directive_init_values[attr_name] = {}

            if language_type == "shared":
                if attr_name not in DirectiveMeta._cross_boundary_app_dicts:
                    DirectiveMeta._shared_dict_names.add(attr_name)
                    for type_set in DirectiveMeta._type_scoped_dicts.values():
                        type_set.discard(attr_name)
                else:
                    DirectiveMeta._type_scoped_dicts["application"].add(attr_name)
            else:
                if attr_name not in DirectiveMeta._shared_dict_names:
                    DirectiveMeta._type_scoped_dicts[language_type].add(attr_name)

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
                    if isinstance(arg, (list, tuple, set)):
                        for a in arg:
                            remove_directives(a)
                    elif isinstance(arg, dict):
                        for a in arg.values():
                            remove_directives(a)
                    elif callable(arg):
                        DirectiveMeta._directives_to_be_executed = [
                            (n, fn)
                            for n, fn in DirectiveMeta._directives_to_be_executed
                            if fn is not arg
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
