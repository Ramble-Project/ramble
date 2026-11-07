# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import ramble.repository

base_class_type = ramble.repository.ObjectTypes.base_classes
ApplicationBase = ramble.repository.get_obj_class(
    "application-base", object_type=base_class_type
)


class ExecutableApplication(ApplicationBase):
    """Specialized class for applications that are pre-built binaries.

    This class can be used to set up an application that uses an executable
    which should already be on the platform.

    It currently only utilizes phases defined in the base class.
    """

    name = "executable-application"
