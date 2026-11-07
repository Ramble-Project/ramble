# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import re

import llnl.util.tty.color
from llnl.util.tty.color import (
    ColorParseError,
    cescape,
    cextra,
    clen,
    get_color_when,
    set_color_when,
)

__all__ = [
    "ColorParseError",
    "cescape",
    "cextra",
    "clen",
    "get_color_when",
    "set_color_when",
    "auto_escape",
    "colorize",
    "cprint",
    "escape_str",
    "level_func",
    "config_title",
    "section_title",
    "nested_1",
    "nested_2",
    "nested_3",
    "nested_4",
    "title_color",
]

config_color = "@*Y"
header_color = "@*b"
level1_color = "@*g"
level2_color = "@*r"
level3_color = "@*c"
level4_color = "@*m"
plain_format = "@."

_valid_color_re = re.compile(
    r"("
    r"@@|"
    r"@\.|"
    r"@[*_]?[krgybmcwKRGYBMCW]?\{(?:[^}]|}})*\}|"
    r"@[*_][krgybmcwKRGYBMCW]?|"
    r"@[krgybmcwKRGYBMCW]"
    r")"
)


def auto_escape(s):
    """Escapes `@` characters that are not part of valid color formats."""
    s = str(s)
    parts = _valid_color_re.split(s)

    new_parts = []
    for i, part in enumerate(parts):
        if i % 2 == 0:
            new_parts.append(part.replace("@", "@@"))
        else:
            # Heuristic: If it looks like a version separator (preceded by alnum or -_)
            # and is not a braced color code or special escape, escape it.
            if part in ["@@", "@."]:
                new_parts.append(part)
            elif "{" in part:
                new_parts.append(part)
            elif (
                i > 0 and parts[i - 1] and (parts[i - 1][-1].isalnum() or parts[i - 1][-1] in "-_")
            ):
                new_parts.append(part.replace("@", "@@"))
            else:
                new_parts.append(part)

    return "".join(new_parts)


def colorize(string, **kwargs):
    """Wrapper for llnl.util.tty.color.colorize that automatically escapes `@`"""
    string = auto_escape(string)
    return llnl.util.tty.color.colorize(string, **kwargs)


def cprint(string, **kwargs):
    """
    Wrapper for llnl.util.tty.color.cprint that automatically escapes `@`
    characters in the string if they do not match valid color codes.
    """
    string = auto_escape(string)
    llnl.util.tty.color.cprint(string, **kwargs)


def escape_str(s):
    return cescape(str(s))


def level_func(level):
    if level < 0:
        return str
    elif level == 0:
        return section_title
    elif level == 1:
        return nested_1
    elif level == 2:
        return nested_2
    elif level == 3:
        return nested_3
    elif level >= 4:
        return nested_4


def config_title(s):
    return config_color + escape_str(s) + plain_format


def section_title(s):
    return header_color + escape_str(s) + plain_format


def nested_1(s):
    return level1_color + escape_str(s) + plain_format


def nested_2(s):
    return level2_color + escape_str(s) + plain_format


def nested_3(s):
    return level3_color + escape_str(s) + plain_format


def nested_4(s):
    return level4_color + escape_str(s) + plain_format


def title_color(title: str, n_indent: int = 0):
    """Set the appropriate color for titles based on indentation"""
    if n_indent == 0:
        out_str = section_title(f"{title}")
    elif n_indent == 4:
        out_str = nested_1(f"{title}")
    elif n_indent == 8:
        out_str = nested_2(f"{title}")
    elif n_indent == 12:
        out_str = nested_3(f"{title}")
    else:
        out_str = nested_4(f"{title}")

    return out_str
