# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Defines paths that are part of Ramble's directory structure.

Do not import other ``ramble`` modules here. This module is used
throughout Ramble and should bring in a minimal number of external
dependencies.
"""

import os

from llnl.util.filesystem import ancestor

#: This file lives in $prefix/lib/ramble/ramble/__file__
prefix: str = ancestor(__file__, 4)

#: synonym for prefix
ramble_root: str = prefix

#: bin directory in the ramble prefix
bin_path: str = os.path.join(prefix, "bin")

#: The ramble script itself
ramble_script: str = os.path.join(bin_path, "ramble")

# ramble directory hierarchy
lib_path: str = os.path.join(prefix, "lib", "ramble")
module_path: str = os.path.join(lib_path, "ramble")
command_path: str = os.path.join(module_path, "cmd")
test_path: str = os.path.join(module_path, "test")
var_path: str = os.path.join(prefix, "var", "ramble")
share_path: str = os.path.join(prefix, "share", "ramble")
repos_path: str = os.path.join(var_path, "repos")

# Paths to built-in Ramble repositories.
builtin_path: str = os.path.join(repos_path, "builtin")
mock_builtin_path: str = os.path.join(repos_path, "builtin.mock")

#: User configuration location
user_config_path: str = os.path.expanduser("~/.ramble")

etc_path: str = os.path.join(prefix, "etc")
system_etc_path: str = "/etc"

#: Default cache location for downloaded archives
default_fetch_cache_path: str = os.path.join(var_path, "cache")
