# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import ramble.paths

HELPER_SCRIPT_NAME = "_ramble_cleaner.py"


def get_cleaner_source_path():
    """Returns the source path to the cleaner script in Ramble's share directory"""
    return os.path.join(ramble.paths.share_path, "scripts", HELPER_SCRIPT_NAME)


def get_cleaner_exec_path():
    """Returns the path to the cleaner script to use in a workspace"""
    return f"{{workspace_shared}}/utilities/{HELPER_SCRIPT_NAME}"


def get_cleaner_script():
    """Returns the content of the standalone cleaner script"""
    with open(get_cleaner_source_path(), encoding="utf-8") as f:
        return f.read()
