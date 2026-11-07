# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import ramble.repository

ModifierBase = ramble.repository.get_base_class("modifier-base")


class BasicModifier(ModifierBase):
    """Specialized class for basic modifiers.

    This class can be used to set up a modifier that can be composed into
    experiment definitions.
    """

    name = "basic-modifier"
