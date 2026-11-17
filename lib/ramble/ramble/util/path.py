# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Utilities for managing paths in ramble.

TODO: this is really part of ramble.config. Consolidate it.
"""

import getpass
import os
import re
import sys
import tempfile
import urllib.parse
from functools import wraps
from typing import Any, Callable, List, Optional

import ramble.paths

is_windows = sys.platform == "win32"

__all__ = [
    "substitute_config_variables",
    "substitute_path_variables",
    "canonicalize_path",
    "Path",
    "format_os_path",
    "convert_to_posix_path",
    "convert_to_windows_path",
    "convert_to_platform_path",
    "is_path_url",
    "path_to_os_path",
    "system_path_filter",
]

_PATH_VAR_RE = re.compile(r"(\$\w+\b|\$\{\w+\})")

# Substitutions to perform
replacements = {
    "ramble": ramble.paths.prefix,
    "user": getpass.getuser(),
    "tempdir": tempfile.gettempdir(),
}


def substitute_config_variables(path, local_replacements=None):
    """Substitute placeholders into paths.

    Ramble allows paths in configs to have some placeholders, as follows:

    - $ramble    The ramble instance's prefix
    - $user      The current user's username
    - $tempdir   Default temporary directory returned by tempfile.gettempdir()

    If a workspace is active, workspace path variables (such as $workspace_root,
    $workspace_configs, etc.) are also substituted.

    These are substituted case-insensitively into the path, and users can
    use either ``$var`` or ``${var}`` syntax for the variables.

    """

    if "$" not in path:
        return path

    if local_replacements is None:
        local_replacements = {}

    import ramble.workspace

    ws = ramble.workspace.active_workspace()
    ws_replacements = ws.workspace_paths() if ws else {}

    # Look up replacements for re.sub in the replacements dict.
    def repl(match):
        m = match.group(0).strip("${}")
        lower_key = m.lower()
        return replacements.get(
            lower_key,
            local_replacements.get(
                lower_key,
                ws_replacements.get(lower_key, match.group(0)),
            ),
        )

    # Replace $var or ${var}.
    return _PATH_VAR_RE.sub(repl, path)


def substitute_path_variables(path, local_replacements=None):
    """Substitute config vars, expand environment vars, expand user home."""
    if local_replacements is None:
        local_replacements = {}
    path = substitute_config_variables(path, local_replacements)
    path = os.path.expandvars(path)
    path = os.path.expanduser(path)
    return path


def canonicalize_path(path):
    """Same as substitute_path_variables, but also take absolute path."""
    path = substitute_path_variables(path)
    path = os.path.abspath(path)

    return path


def normalize_path_or_url(path):
    """Convert a scheme-less path to absolute local path
    Also, remove trailing slashes from the input path

    Args:
        path (str): Input path

    Returns:
        str: Absolute local path or cleaned remote url
    """
    if not path:
        return path

    parsed = urllib.parse.urlparse(path)
    if not parsed.scheme:
        return os.path.abspath(path)
    return path.rstrip("/")


class Path:
    """Describes the filepath separator types in an enum style with a helper
    attribute exposing the path type of the current platform.
    """

    unix = 0
    windows = 1
    platform_path = windows if is_windows else unix


def format_os_path(path: str, mode: int = Path.unix) -> str:
    """Format path to use consistent, platform-specific separators."""
    if not path:
        return path
    if mode == Path.windows:
        return path.replace("/", "\\")
    return path.replace("\\", "/")


def convert_to_posix_path(path: str) -> str:
    return format_os_path(path, mode=Path.unix)


def convert_to_windows_path(path: str) -> str:
    return format_os_path(path, mode=Path.windows)


def convert_to_platform_path(path: str) -> str:
    return format_os_path(path, mode=Path.platform_path)


def is_path_url(path: str) -> bool:
    if "\\" in path:
        return False
    url_tuple = urllib.parse.urlparse(path)
    return bool(url_tuple.scheme) and len(url_tuple.scheme) > 1


def path_to_os_path(*pths: Any) -> List[Any]:
    """Takes an arbitrary number of positional parameters, converts each
    argument of type string to use a normalized filepath separator, and
    returns a list of all values.
    """
    ret_pths: List[Any] = []
    for pth in pths:
        if type(pth) is str and not is_path_url(pth):
            pth = convert_to_platform_path(pth)
        ret_pths.append(pth)
    return ret_pths


def system_path_filter(
    _func: Optional[Callable[..., Any]] = None, arg_slice: Optional[slice] = None
) -> Callable[..., Any]:
    """Filters function arguments to account for platform path separators."""

    def holder_func(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def path_filter_caller(*args: Any, **kwargs: Any) -> Any:
            arg_list = list(args)
            if arg_slice:
                arg_list[arg_slice] = path_to_os_path(*arg_list[arg_slice])
            else:
                arg_list = path_to_os_path(*arg_list)
            return func(*arg_list, **kwargs)

        return path_filter_caller

    if _func:
        return holder_func(_func)
    return holder_func
