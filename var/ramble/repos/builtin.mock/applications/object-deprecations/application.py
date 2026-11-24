# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.appkit import *


class ObjectDeprecations(ExecutableApplication):
    """Test application for declarative deprecations."""

    name = "object-deprecations"

    version("1.0")
    version("2.0", preferred=True)

    executable("echo", "echo", use_mpi=False)
    workload("current_wl", executable="echo")
    workload("legacy_wl", executable="echo")

    variant(
        "legacy_mode",
        default=False,
        values=[True, False],
        description="Trigger variant deprecation",
    )
    variant(
        "future_dep",
        default=False,
        values=[True, False],
        description="Trigger future deprecation",
    )
    variant(
        "expired_dep",
        default=False,
        values=[True, False],
        description="Trigger expired deprecation",
    )
    variant(
        "no_version_dep",
        default=False,
        values=[True, False],
        description="Trigger versionless deprecation",
    )
    variant(
        "bad_when",
        default=False,
        values=[True, False],
        description="Trigger bad when expression",
    )

    with when("@:1.0"):
        deprecate(
            deprecated_in="0.7.0",
            removed_in="99.0.0",
            replacement="object-deprecations@2.0",
        )

    with when("workload_name=legacy_wl"):
        deprecate(
            deprecated_in="0.7.0",
            removed_in="99.0.0",
            replacement="current_wl",
            msg="Migrate {workload_name} to current_wl.",
        )

    with when("+legacy_mode"):
        deprecate(
            deprecated_in="0.7.0",
            removed_in="99.0.0",
            msg="Use the default mode instead.",
        )

    with when("+future_dep"):
        deprecate(
            deprecated_in="99.0.0",
            removed_in="100.0.0",
            replacement="future-replacement",
        )

    with when("+expired_dep"):
        deprecate(
            deprecated_in="0.5.0",
            removed_in="0.6.0",
            replacement="new-feature",
        )

    with when("+no_version_dep"):
        deprecate(replacement="unversioned-replacement")

    with when("+bad_when"):
        deprecate(deprecated_in="0.7.0", when="1 is 1")
