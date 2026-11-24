# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.modkit import *


class DeprecatedMod(BasicModifier):
    """Mock modifier to test declarative deprecations."""

    name = "deprecated-mod"

    version("1.0")
    version("2.0", preferred=True)

    mode("standard", description="Standard mode")
    mode("legacy", description="Legacy mode")
    default_mode("standard")

    with when("deprecated-mod_mode=legacy"):
        deprecate(
            deprecated_in="0.7.0",
            removed_in="99.0.0",
            replacement="deprecated-mod_mode=standard",
        )

    with when("@:1.0"):
        deprecate(
            deprecated_in="0.7.0",
            removed_in="99.0.0",
            replacement="deprecated-mod@2.0",
        )
