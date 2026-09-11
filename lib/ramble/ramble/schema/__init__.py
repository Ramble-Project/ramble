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

    ValidatorClass = jsonschema.validators.extend(
        jsonschema.Draft4Validator, {"deprecatedProperties": _deprecated_properties}
    )

    import spack.util.spack_yaml as syaml

    # Add syaml_bool to the accepted boolean types for validation
    boolean_types = ValidatorClass.DEFAULT_TYPES.get("boolean", bool)
    if not isinstance(boolean_types, tuple):
        boolean_types = (boolean_types,)
    ValidatorClass.DEFAULT_TYPES["boolean"] = boolean_types + (syaml.syaml_bool,)

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
