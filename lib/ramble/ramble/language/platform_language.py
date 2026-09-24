# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import functools

import ramble.language.shared_language

"""This package contains directives that can be used within a platform.

Directives are functions that can be called inside a platform
definition to modify then platform, for example:

    .. code-block:: python

      class MyPlatform(Platform):
          platform_family('x86_64')

In the above example, 'platform_family' is a ramble directive
"""

PlatformMeta = ramble.language.shared_language.SharedMeta
platform_directive = functools.partial(PlatformMeta.directive, language_type="platform")


@platform_directive(dicts="class_families", init_value={})
def platform_family(*names: str, **kwargs):
    """Add a new family to this platform

    Args:
        name (str): Name of family to apply to this platform
    """
    return ramble.language.shared_language.class_family(*names, **kwargs)
