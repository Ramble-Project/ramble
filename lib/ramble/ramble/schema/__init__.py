# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
"""This module contains jsonschema files for all of Ramble's YAML formats."""

import sys

import llnl.util.lang
import llnl.util.tty

# jsonschema is imported lazily as it is heavy to import
# and increases the start-up time


def _make_validator():
    import jsonschema

    def _deprecated_properties(validator, deprecated, instance, schema):
        if not (validator.is_type(instance, "object") or validator.is_type(instance, "array")):
            return

        # Get a list of the deprecated properties, return if there is none
        deprecated_properties = [x for x in instance if x in deprecated["properties"]]
        if not deprecated_properties:
            return

        # Retrieve the template message
        msg_str_or_func = deprecated["message"]
        if isinstance(msg_str_or_func, str):
            msg = msg_str_or_func.format(properties=deprecated_properties)
        else:
            msg = msg_str_or_func(instance, deprecated_properties)

        is_error = deprecated["error"]
        if not is_error:
            llnl.util.tty.warn(msg)
        else:
            import jsonschema

            yield jsonschema.ValidationError(msg)

    import spack.util.spack_yaml as syaml

    # Ramble's YAML loader represents `true`/`false` as `syaml_bool`, which derives from
    # `int` rather than `bool`, so jsonschema's stock `isinstance(instance, bool)` check
    # rejects it. Redefine the "boolean" type check to accept it, otherwise every boolean
    # in every Ramble config file fails validation.
    type_checker = jsonschema.Draft4Validator.TYPE_CHECKER.redefine(
        "boolean", lambda checker, instance: isinstance(instance, (bool, syaml.syaml_bool))
    )

    ValidatorClass = jsonschema.validators.extend(
        jsonschema.Draft4Validator,
        {"deprecatedProperties": _deprecated_properties},
        type_checker=type_checker,
    )

    return ValidatorClass


Validator = llnl.util.lang.Singleton(_make_validator)


def __getattr__(name: str):
    import importlib

    try:
        return importlib.import_module(f"ramble.schema.{name}")
    except (ImportError, ModuleNotFoundError) as err:
        if getattr(err, "name", None) == f"ramble.schema.{name}":
            raise AttributeError(f"module 'ramble.schema' has no attribute '{name}'") from err
        raise


if sys.version_info < (3, 7):  # pragma: no cover
    import types

    class _SchemaModule(types.ModuleType):
        def __getattr__(self, name: str):
            return __getattr__(name)

    sys.modules[__name__].__class__ = _SchemaModule
