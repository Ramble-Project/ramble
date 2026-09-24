# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

# Need this because of ramble.util.string
import fnmatch
import functools
import io
import itertools
import re
import string

import ramble.error

__all__ = [
    "mod_to_class",
    "valid_module_name",
    "validate_module_name",
    "possible_ramble_module_names",
    "simplify_name",
    "match_pattern",
    "NamespaceTrie",
    "NS_SEPARATOR",
]

NS_SEPARATOR = "::"

# Valid module names can contain '-' but can't start with it.
_VALID_MODULE_RE = re.compile(r"^\w[\w-]*$")
_DASH_UNDERSCORE_RE = re.compile(r"[-_]+")
_NUM_PREFIX_RE = re.compile(r"^num(\d)")
_UNDERSCORE_SPLIT_RE = re.compile(r"(_)")
_LUA_PREFIX_RE = re.compile(r"^(lua)([^-])")
_BPP_PREFIX_RE = re.compile(r"^(bpp)([^-])")


@functools.lru_cache(maxsize=512)
def mod_to_class(mod_name):
    """Convert a name from module style to class name style.  Ramble mostly
    follows `PEP-8 <http://legacy.python.org/dev/peps/pep-0008/>`_:

       * Module and package names use lowercase_with_underscores.
       * Class names use the CapWords convention.

    Regular source code follows these conventions.  Ramble is a bit
    more liberal with its Application names:

       * They can contain '-' as well as '_', but cannot start with '-'.
       * They can start with numbers, e.g. "3proxy".

    This function converts from the module convention to the class
    convention by removing _ and - and converting surrounding
    lowercase text to CapWords.  If mod_name starts with a number,
    the class name returned will be prepended with '_' to make a
    valid Python identifier.
    """
    validate_module_name(mod_name)

    class_name = _DASH_UNDERSCORE_RE.sub("-", mod_name)
    class_name = string.capwords(class_name, "-")
    class_name = class_name.replace("-", "")

    # If a class starts with a number, prefix it with Number_ to make it
    # a valid Python class name.
    if class_name and class_name[0].isdigit():
        class_name = f"_{class_name}"

    return class_name


def possible_ramble_module_names(python_mod_name):
    """Given a Python module name, return a list of all possible ramble module
    names that could correspond to it."""
    mod_name = _NUM_PREFIX_RE.sub(r"\1", python_mod_name)

    parts = _UNDERSCORE_SPLIT_RE.split(mod_name)
    options = [["_", "-"]] * mod_name.count("_")

    results = []
    for subs in itertools.product(*options):
        s = list(parts)
        s[1::2] = subs
        results.append("".join(s))

    return results


@functools.lru_cache(maxsize=1024)
def simplify_name(name):
    """Simplify package name to only lowercase, digits, and dashes.

    Simplifies a name which may include uppercase letters, periods,
    underscores, and pluses. In general, we want our package names to
    only contain lowercase letters, digits, and dashes.

    Args:
        name (str): The original name of the package

    Returns:
        str: The new name of the package
    """
    # Convert CamelCase to Dashed-Names
    # e.g. ImageMagick -> Image-Magick
    # e.g. SuiteSparse -> Suite-Sparse
    # name = re.sub('([a-z])([A-Z])', r'\1-\2', name)

    # Rename Intel downloads
    # e.g. l_daal, l_ipp, l_mkl -> daal, ipp, mkl
    if name.startswith("l_"):
        name = name[2:]

    # Convert UPPERCASE to lowercase
    # e.g. SAMRAI -> samrai
    name = name.lower()

    # Replace '_' and '.' with '-'
    # e.g. backports.ssl_match_hostname -> backports-ssl-match-hostname
    name = name.replace("_", "-")
    name = name.replace(".", "-")

    # Replace "++" with "pp" and "+" with "-plus"
    # e.g. gtk+   -> gtk-plus
    # e.g. voro++ -> voropp
    name = name.replace("++", "pp")
    name = name.replace("+", "-plus")

    # Simplify Lua package names
    # We don't want "lua" to occur multiple times in the name
    name = _LUA_PREFIX_RE.sub(r"\1-\2", name)

    # Simplify Bio++ package names
    name = _BPP_PREFIX_RE.sub(r"\1-\2", name)

    return name


def valid_module_name(mod_name):
    """Return whether mod_name is valid for use in Ramble."""
    return bool(_VALID_MODULE_RE.match(mod_name))


def validate_module_name(mod_name):
    """Raise an exception if mod_name is not valid."""
    if not valid_module_name(mod_name):
        raise InvalidModuleNameError(mod_name)


class InvalidModuleNameError(ramble.error.RambleError):
    """Raised when we encounter a bad module name."""

    def __init__(self, name):
        super().__init__("Invalid module name: " + name)
        self.name = name


class NamespaceTrie:

    class Element:

        def __init__(self, value):
            self.value = value

    def __init__(self, separator="."):
        self._subspaces = {}
        self._value = None
        self._sep = separator

    def __setitem__(self, namespace, value):
        first, _, rest = namespace.partition(self._sep)

        if not first:
            self._value = NamespaceTrie.Element(value)
            return

        if first not in self._subspaces:
            self._subspaces[first] = NamespaceTrie()

        self._subspaces[first][rest] = value

    def _get_helper(self, namespace, full_name):
        first, _, rest = namespace.partition(self._sep)
        if not first:
            if not self._value:
                raise KeyError(f"Can't find namespace '{full_name}' in trie")
            return self._value.value
        elif first not in self._subspaces:
            raise KeyError(f"Can't find namespace '{full_name}' in trie")
        else:
            return self._subspaces[first]._get_helper(rest, full_name)

    def __getitem__(self, namespace):
        return self._get_helper(namespace, namespace)

    def is_prefix(self, namespace):
        """True if the namespace has a value, or if it's the prefix of one that
        does."""
        first, _, rest = namespace.partition(self._sep)
        if not first:
            return True
        elif first not in self._subspaces:
            return False
        else:
            return self._subspaces[first].is_prefix(rest)

    def is_leaf(self, namespace):
        """True if this namespace has no children in the trie."""
        first, _, rest = namespace.partition(self._sep)
        if not first:
            return not self._subspaces
        elif first not in self._subspaces:
            return False
        else:
            return self._subspaces[first].is_leaf(rest)

    def has_value(self, namespace):
        """True if there is a value set for the given namespace."""
        first, _, rest = namespace.partition(self._sep)
        if not first:
            return self._value is not None
        elif first not in self._subspaces:
            return False
        else:
            return self._subspaces[first].has_value(rest)

    def __contains__(self, namespace):
        """Returns whether a value has been set for the namespace."""
        return self.has_value(namespace)

    def _str_helper(self, stream, level=0):
        indent = level * "    "
        for name in sorted(self._subspaces):
            stream.write(indent + name + "\n")
            if self._value:
                stream.write(indent + "  " + repr(self._value.value))
            stream.write(self._subspaces[name]._str_helper(stream, level + 1))

    def __str__(self):
        stream = io.StringIO()
        self._str_helper(stream)
        return stream.getvalue()


def match_pattern(pattern, string):
    """Match a string against a pattern (regex or glob)

    Args:
        pattern (str): pattern to match against
        string (str): string to match

    Returns:
        (tuple): (bool: matched, dict: captured groups)
    """
    if pattern is None:
        return True, {}

    # If the pattern contains characters that strongly suggest a regex,
    # try regex matching first.
    # Common regex-only characters: (, ), [, ], ^, $, |
    # Note: * and ? are common to both. . is also common but more regex-y.
    is_regex = any(c in pattern for c in "()[]^$|") or "(?P<" in pattern

    if is_regex:
        try:
            regex = re.compile(pattern)
            match = regex.fullmatch(string)
            if match:
                return True, match.groupdict()
            return False, {}
        except re.error:
            pass

    # Try globbing
    if fnmatch.fnmatch(string, pattern):
        return True, {}

    # Final attempt: try as regex even if it didn't look like one
    if not is_regex:
        try:
            regex = re.compile(pattern)
            match = regex.fullmatch(string)
            if match:
                return True, match.groupdict()
        except re.error:
            pass

    return False, {}
