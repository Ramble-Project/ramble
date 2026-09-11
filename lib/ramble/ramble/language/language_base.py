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
import copy
import functools
import inspect
from collections.abc import Sequence  # novm
from typing import Any, Callable, Dict, List, Set

import llnl.util.lang

import ramble.language.language_helpers
from ramble.error import DirectiveError
from ramble.util import directives
from ramble.util.logger import logger

__all__ = ["DirectiveMeta", "DirectiveError"]


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


def _push_to_context(when_condition: str) -> None:
    DirectiveMeta._when_constraints_from_context.append(when_condition)

    impossible, message = ramble.language.language_helpers.is_when_impossible(
        DirectiveMeta._when_constraints_from_context
    )
    if impossible:
        logger.warn(f"Entering an impossible 'when' context: {message}")


def _pop_from_context() -> str:
    return DirectiveMeta._when_constraints_from_context.pop()


def _push_default_args(default_args: Dict[str, Any]) -> None:
    DirectiveMeta._default_args.append(default_args)


def _pop_default_args() -> dict:
    return DirectiveMeta._default_args.pop()


class DirectiveMeta(abc.ABCMeta):
    """Flushes the directives that were temporarily stored in the staging
    area into the package.
    """

    # Set of all known directives
    _directive_names: Set[str] = set()
    _directive_init_values: Dict[str, Any] = {}
    _directives_to_be_executed: List[Callable[..., Any]] = []
    _directive_functions: Dict[str, Callable[..., Any]] = {}
    _directive_classes: Dict[str, type] = {}
    _when_constraints_from_context: List[str] = []
    _default_args: List[dict] = []

    push_to_context = _push_to_context
    pop_from_context = _pop_from_context
    push_default_args = _push_default_args
    pop_default_args = _pop_default_args

    def __new__(cls, name, bases, attr_dict):
        # Initialize the attribute containing the list of directives
        # to be executed. Here we go reversed because we want to execute
        # commands:
        # 1. in the order they were defined
        # 2. following the MRO
        attr_dict["_directives_to_be_executed"] = []
        for base in reversed(bases):
            directive_from_base = getattr(base, "_directives_to_be_executed", None)
            if directive_from_base is not None:
                attr_dict["_directives_to_be_executed"].extend(directive_from_base)

        # De-duplicates directives from base classes
        attr_dict["_directives_to_be_executed"] = list(
            llnl.util.lang.dedupe(attr_dict["_directives_to_be_executed"])
        )

        # Move things to be executed from module scope (where they
        # are collected first) to class scope
        if DirectiveMeta._directives_to_be_executed:
            attr_dict["_directives_to_be_executed"].extend(
                DirectiveMeta._directives_to_be_executed
            )
            DirectiveMeta._directives_to_be_executed = []

        return super().__new__(cls, name, bases, attr_dict)

    def __init__(cls, name, bases, attr_dict):
        # The instance is being initialized: if it is a package we must ensure
        # that the directives are called to set it up.

        valid_module = False
        for namespace in namespaces:
            if namespace in cls.__module__:
                valid_module = True

        if valid_module:
            # Ensure the presence of the dictionaries associated
            # with the directives
            # We use type(cls) to get the metaclass, and iterate its MRO to
            # collect all init values and directive attributes.
            all_init_values: Dict[str, Any] = {}
            all_directive_names: Set[str] = set()
            all_directive_functions: Dict[str, Any] = {}
            all_directive_classes: Dict[str, Any] = {}

            for base_meta in reversed(inspect.getmro(type(cls))):
                if hasattr(base_meta, "_directive_init_values"):
                    all_init_values.update(base_meta._directive_init_values)
                if hasattr(base_meta, "_directive_names"):
                    all_directive_names |= base_meta._directive_names
                if hasattr(base_meta, "_directive_functions"):
                    all_directive_functions.update(base_meta._directive_functions)
                if hasattr(base_meta, "_directive_classes"):
                    all_directive_classes.update(base_meta._directive_classes)

            for d, t in all_init_values.items():
                setattr(cls, d, copy.deepcopy(t))

            if hasattr(DirectiveMeta, "_directive_functions"):
                all_directive_functions.update(DirectiveMeta._directive_functions)
            if hasattr(DirectiveMeta, "_directive_classes"):
                all_directive_classes.update(DirectiveMeta._directive_classes)
            if hasattr(DirectiveMeta, "_directive_names"):
                all_directive_names |= DirectiveMeta._directive_names

            directive_attrs = {
                "_directive_functions": all_directive_functions,
                "_directive_classes": all_directive_classes,
                "_directive_names": all_directive_names,
            }

            for attr, val in directive_attrs.items():
                setattr(cls, attr, val)

            # Lazily execute directives
            for directive in cls._directives_to_be_executed:
                directive(cls)

            # Ignore any directives executed *within* top-level
            # directives by clearing out the queue they're appended to
            DirectiveMeta._directives_to_be_executed = []

            directives.define_directive_methods_on_class(cls)

        super().__init__(name, bases, attr_dict)

    @classmethod
    def directive(cls, dicts=None, init_value=None):
        """Decorator for Ramble directives.

        Ramble directives allow you to modify an object while it is being
        defined, e.g. to add version or dependency information.  Directives are
        one of the key pieces of Ramble's object "language", which is
        embedded in python.

        Here's an example directive:

        .. code-block:: python

            @directive(dicts='workloads')
            workload('workload_name', ...):
                ...

        This directive allows you write:

        .. code-block:: python

            class Foo(ApplicationBase):
                workload(...)

        The ``@directive`` decorator handles a couple things for you:

          1. Adds the class scope (app) as an initial parameter when
             called, like a class method would.  This allows you to modify
             a package from within a directive, while the package is still
             being defined.

          2. It automatically adds a dictionary called "workloads" to the
             package so that you can refer to app.workloads.

        The ``(dicts='workloads')`` part ensures that ALL applications in
        Ramble will have a ``workloads`` attribute after they're constructed,
        and that if no directive actually modified it, it will just be an empty
        dict.

        The ``(init_value={})`` part allows objects in Ramble to define what the
        type of the attribute defined by the `dicts` argument will be. This
        allows ``(dicts="variables", init_value=[])`` which makes the attribute
        a list instead of a dict, which is the default.

        This is just a modular way to add storage attributes to the Application
        class, and it's how Ramble gets information from the applications to
        the core.

        """
        if isinstance(dicts, str):
            dicts = (dicts,)

        if not isinstance(dicts, Sequence):
            message = "dicts arg must be list, tuple, or string. Found {0}"
            raise TypeError(message.format(type(dicts)))

        if init_value is None:
            init_value = {}

        # Add the dictionary names if not already there
        dicts_set = set(dicts)
        cls._directive_names |= dicts_set
        for attr_name in dicts_set:
            cls._directive_init_values[attr_name] = init_value

        # This decorator just returns the directive functions
        def _decorator(decorated_function):
            @functools.wraps(decorated_function)
            def _wrapper(*args, **_kwargs):
                # First merge default args with kwargs
                kwargs = {}
                for default_args in DirectiveMeta._default_args:
                    kwargs.update(default_args)
                kwargs.update(_kwargs)

                # Inject when arguments from the context
                if DirectiveMeta._when_constraints_from_context:
                    # Check that directives not yet supporting the when= argument
                    # are not used inside the context manager
                    sig = inspect.signature(decorated_function)
                    if "when" not in sig.parameters:
                        msg = (
                            'directive "{0}" cannot be used within a "when"'
                            ' context since it does not support a "when=" '
                            "argument"
                        )
                        msg = msg.format(decorated_function.__name__)
                        raise DirectiveError(msg)

                    when_constraints = DirectiveMeta._when_constraints_from_context.copy()

                    if kwargs.get("when"):
                        when_arg = kwargs["when"]

                        # Validate kwarg `when` conditions are correctly formatted
                        when_list = ramble.language.language_helpers.build_when_list(
                            when_arg, "DirectiveMeta", args[0], decorated_function.__name__
                        )

                        when_constraints.extend(when_list)

                    kwargs["when"] = when_constraints.copy()

                if "when" in kwargs:
                    impossible, message = ramble.language.language_helpers.is_when_impossible(
                        kwargs["when"]
                    )
                    if impossible:

                        def _warn_impossible(obj):
                            obj_type = obj.origin_type if hasattr(obj, "origin_type") else ""
                            obj_name = obj.name if hasattr(obj, "name") else ""
                            _impossible_when_warning(
                                decorated_function.__name__,
                                obj_type,
                                obj_name,
                                message,
                                args,
                                kwargs,
                            )

                        DirectiveMeta._directives_to_be_executed.append(_warn_impossible)
                        return _warn_impossible

                # If any of the arguments are executors returned by a
                # directive passed as an argument, don't execute them
                # lazily. Instead, let the called directive handle them.
                # This allows nested directive calls in applications.  The
                # caller can return the directive if it should be queued.
                def remove_directives(arg):
                    directives = DirectiveMeta._directives_to_be_executed
                    if isinstance(arg, (list, tuple)):
                        # Descend into args that are lists or tuples
                        for a in arg:
                            remove_directives(a)
                    else:
                        # Remove directives args from the exec queue
                        remove = next((d for d in directives if d is arg), None)
                        if remove is not None:
                            directives.remove(remove)

                # Nasty, but it's the best way I can think of to avoid
                # side effects if directive results are passed as args
                remove_directives(args)
                remove_directives(list(kwargs.values()))

                # A directive returns either something that is callable on a
                # package or a sequence of them
                result = decorated_function(*args, **kwargs)

                # ...so if it is not a sequence make it so
                values = result
                if not isinstance(values, Sequence):
                    values = (values,)

                DirectiveMeta._directives_to_be_executed.extend(values)

                # wrapped function returns same result as original so
                # that we can nest directives
                return result

            cls._directive_classes[decorated_function.__name__] = cls
            cls._directive_functions[decorated_function.__name__] = decorated_function

            return _wrapper

        return _decorator
