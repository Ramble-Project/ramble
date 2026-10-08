# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.pkgmankit import *


class {class_name}({base_class}):
    """Starter template for {name} package manager.

    TODO: Add description of the package manager and its purpose.
    """

    name = "{name}"
    maintainers({maintainers})
    tags({tags})

    def package_name_from_spec(self, spec: str) -> str:
        return spec

    def get_package_list(self, workspace):
        return []

    def environment_load_commands(self):
        return []

    def environment_unload_commands(self):
        return []
