# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


from ramble.toolkit import *


class Spack(UtilityBase):
    """Spack package manager external utility: https://spack.io"""

    bootstrappable(True)

    variable(
        name="path",
        default="system",
        description="Path to Spack",
        scoped=True,
    )

    name = "spack"

    maintainers("douglasjacobsen")

    # For testing we only require version
    variable(
        "spack_url",
        default="https://github.com/spack/spack.git",
        description="Git repository for Spack",
    )
    variable(
        "spack_version",
        default="v1.2.2",
        description="Version of spack to fetch",
    )

    fetch_mapping("spack_url", "git", fallback_for=["git", "url"])
    fetch_mapping(
        "spack_version", "commit", fallback_for=["commit", "branch", "tag"]
    )

    provides_executable(
        "spack",
        version_cmd="spack --version",
        version_regex=r"(\d+.\d+.\d+).*",
    )

    env_source("{utility::spack::path}/share/spack/setup-env.sh")
    env_set("SPACK_USER_CONFIG_PATH", "{utility::spack::path}/../.spack")

    # Future proofing: tools can define their own setup phases!
    def install(self, workspace):
        # E.g., make, configure, etc.
        logger.debug(f"Executing install phase for {self.name}")
