# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


#: major, minor, patch version for Ramble, in a tuple
ramble_version_info = (0, 7, 0)

#: String containing Ramble version joined with .'s
ramble_version = ".".join(str(v) for v in ramble_version_info)

__all__ = ["ramble_version_info", "ramble_version"]
