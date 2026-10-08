# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.wmkit import *


class {class_name}({base_class}):
    """Starter template for {name} workflow manager.

    TODO: Add description of the workflow manager and its purpose.
    """

    name = "{name}"
    maintainers({maintainers})
    tags({tags})

    def get_status(self, workspace):
        """Return status of a given job"""
        return None
