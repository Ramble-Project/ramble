# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""A utility for dynamically importing modules."""

import importlib
import types
from typing import Dict

from ramble.util.logger import logger

_modules: Dict[str, types.ModuleType] = {}


def import_module(module_name):
    """A utility for dynamically importing a module."""
    if module_name not in _modules:
        try:
            module = importlib.import_module(module_name)
            _modules[module_name] = module
        except ModuleNotFoundError:
            logger.die(
                f"`{module_name}` was not found. Ensure all the packages in "
                "`requirements.txt` are installed."
            )
    return _modules[module_name]


def import_pandas():
    """A utility for dynamically importing pandas."""
    return import_module("pandas")
