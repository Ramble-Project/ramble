# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.toolkit import *


class Pdsh(UtilityBase):
    """pdsh utility"""

    bootstrappable(False)
    missing_error_message(
        "pdsh is required but was not found in your environment. Please install it to proceed."
    )

    provides_executable(
        "pdsh",
        version_cmd="pdsh -V",
        version_regex=r"pdsh-(\d+\.\d+).*",
    )

    name = "pdsh"

    maintainers("douglasjacobsen")
