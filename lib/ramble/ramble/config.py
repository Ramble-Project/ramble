# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
"""This module implements Ramble's configuration file handling.

This implements Ramble's configuration system, which handles merging
multiple scopes with different levels of precedence.

The scopes are:

  #. ``default``
  #. ``system``
  #. ``site``
  #. ``user``

Important functions in this module are:

* :py:func:`Configuration.get_config`
* :py:func:`Configuration.update_config`

``get_config`` reads in YAML data for a particular scope and returns
it. Callers can then modify the data and write it back with
``update_config``.

When read in, Ramble validates configurations with jsonschemas.  The
schemas are in submodules of :py:mod:`ramble.schema`.

"""

import collections
import contextlib
import copy
import functools
import itertools
import os
import re
import sys
from contextlib import contextmanager
from typing import Any, Dict, List

from ruamel import yaml
from ruamel.yaml.error import MarkedYAMLError

import llnl.util.lang
from llnl.util.filesystem import mkdirp, rename

import ramble.paths
import ramble.schema.applications
import ramble.schema.config
import ramble.schema.env_vars
import ramble.schema.filter_groups
import ramble.schema.formatted_executables
import ramble.schema.internals
import ramble.schema.licenses
import ramble.schema.mirrors
import ramble.schema.modifiers
import ramble.schema.repo_schema
import ramble.schema.software
import ramble.schema.success_criteria
import ramble.schema.tables
import ramble.schema.utilities
import ramble.schema.variables
import ramble.schema.variants
import ramble.schema.workspace
import ramble.schema.zips
from ramble.error import RambleError
from ramble.util import cpus
from ramble.util.logger import logger

import spack.compilers
import spack.platforms

# Hacked yaml for configuration files preserves line numbers.
import spack.util.spack_yaml as syaml

#: Dict from section names -> schema for that section
section_schemas: Dict[str, Dict[str, Any]] = {
    "formatted_executables": ramble.schema.formatted_executables.schema,
    "config": ramble.schema.config.schema,
    "env_vars": ramble.schema.env_vars.schema,
    "filter_groups": ramble.schema.filter_groups.schema,
    "internals": ramble.schema.internals.schema,
    "licenses": ramble.schema.licenses.schema,
    "mirrors": ramble.schema.mirrors.schema,
    "modifiers": ramble.schema.modifiers.schema,
    "software": ramble.schema.software.schema,
    "success_criteria": ramble.schema.success_criteria.schema,
    "tables": ramble.schema.tables.schema,
    "applications": ramble.schema.applications.schema,
    "variables": ramble.schema.variables.schema,
    "variants": ramble.schema.variants.schema,
    "zips": ramble.schema.zips.schema,
    "utilities": ramble.schema.utilities.schema,
    **ramble.schema.repo_schema.schemas,
}

# Same as above, but including keys for workspaces
# this allows us to unify config reading between configs and workspaces
all_schemas = copy.deepcopy(section_schemas)
all_schemas.update(dict.fromkeys(ramble.schema.workspace.keys, ramble.schema.workspace.schema))


class _RambleLineLoader(syaml.OrderedLineLoader):
    def construct_mapping(self, node, maptyp, deep=False):
        from builtins import set

        import llnl.util.tty as tty

        seen_keys = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=True)

            # Check if key is hashable; convert lists to tuples
            try:
                hash(key)
                is_hashable = True
            except TypeError:
                if isinstance(key, list):
                    try:
                        key = tuple(key)
                        hash(key)
                        is_hashable = True
                    except TypeError:
                        is_hashable = False
                else:
                    is_hashable = False

            if is_hashable:
                if key in seen_keys:
                    filename = node.start_mark.name
                    line = key_node.start_mark.line + 1
                    tty.warn(
                        f'Duplicate key "{key}" detected in {filename} at line {line}. '
                        "This will overwrite the previous value."
                    )
                seen_keys.add(key)

        super().construct_mapping(node, maptyp, deep=deep)


def load_config(*args, **kwargs):
    """Load YAML using Ramble's custom Loader that warns on duplicate keys."""
    kwargs["Loader"] = _RambleLineLoader
    return syaml.load(*args, **kwargs)


#: Builtin paths to configuration files in ramble
configuration_paths = (
    # Default configuration scope is the lowest-level scope. These are
    # versioned with ramble and can be overridden by systems, sites or users
    ("defaults", os.path.join(ramble.paths.etc_path, "ramble", "defaults")),
    # System configuration is per machine.
    # No system-level configs should be checked into ramble by default
    ("system", os.path.join(ramble.paths.system_etc_path, "ramble")),
    # Site configuration is per ramble instance, for sites or projects
    # No site-level configs should be checked into ramble by default.
    ("site", os.path.join(ramble.paths.etc_path, "ramble")),
    # User configuration can override both ramble defaults and site config
    ("user", ramble.paths.user_config_path),
)

#: Hard-coded default values for some key configuration options.
#: This ensures that Ramble will still work even if config.yaml in
#: the defaults scope is removed.
config_defaults = {
    "config": {
        "debug": False,
        "disable_passthrough": False,
        "disable_progress_bar": False,
        "connect_timeout": 10,
        "n_repeats": "0",
        "repeat_success_strict": True,
        "verify_ssl": True,
        "checksum": True,
        "dirty": False,
        "build_jobs": min(16, cpus.cpus_available()),
        "build_stage": "$tempdir/ramble-stage",
        "concretizer": "clingo",
        "license_dir": spack.paths.default_license_dir,
        "shell": "bash",
        "spack": {"install": {"flags": "--fresh"}, "concretize": {"flags": "--fresh"}},
        "pip": {"install": {"flags": []}},
        "input_cache": "$ramble/var/ramble/cache",
        "workspace_dirs": ["$ramble/var/ramble/workspaces"],
        "upload": {"push_failed": True},
        "upload_threads": cpus.cpus_available(),
        "report_dirs": "~/.ramble/reports",
        "enable_strict_versions": True,
    }
}


class ScopesMetavar:
    def __str__(self):
        import ramble.workspace

        if ramble.workspace.active_workspace():
            return "{defaults,system,site,user,workspace}"
        return "{defaults,system,site,user}"

    def __repr__(self):
        return self.__str__()


class ScopesChoices:
    def __init__(self, include_workspace=True):
        self.include_workspace = include_workspace

    def __contains__(self, item):
        import ramble.workspace

        all_scopes = [s for s in scopes() if not s.startswith("workspace:")]
        if self.include_workspace and ramble.workspace.active_workspace():
            all_scopes.append("workspace")
        return item in all_scopes

    def __iter__(self):
        import ramble.workspace

        all_scopes = [s for s in scopes() if not s.startswith("workspace:")]
        if self.include_workspace and ramble.workspace.active_workspace():
            all_scopes.append("workspace")
        return iter(all_scopes)


def scopes_choices(include_workspace=True):
    return ScopesChoices(include_workspace)


#: metavar to use for commands that accept scopes
#: this is shorter and more readable than listing all choices
scopes_metavar = ScopesMetavar()

#: Base name for the (internal) overrides scope.
overrides_base_name = "overrides-"


def first_existing(dictionary, keys):
    """Get the value of the first key in keys that is in the dictionary."""
    for k in keys:
        if k in dictionary:
            return k
    raise KeyError(f"None of {keys} is in dict!")


class ConfigScope:
    """This class represents a configuration scope.

    A scope is one directory containing named configuration files.
    Each file is a config "section" (e.g., mirrors, compilers, etc).
    """

    def __init__(self, name, path):
        self.name = name  # scope name.
        self.path = path  # path to directory containing configs.
        self.sections = syaml.syaml_dict()  # sections read from config files.

    @property
    def is_platform_dependent(self):
        return os.sep in self.name

    def get_section_filename(self, section):
        _validate_section_name(section)
        return os.path.join(self.path, f"{section}.yaml")

    def get_section(self, section):
        if section not in self.sections:
            path = self.get_section_filename(section)
            schema = section_schemas[section]
            data = read_config_file(path, schema)
            self.sections[section] = data
        return self.sections[section]

    def _write_section(self, section):
        filename = self.get_section_filename(section)
        data = self.get_section(section)

        # validate handles copying data to avoid adding defaults at write time
        validate(data, section_schemas[section])

        try:
            mkdirp(self.path)
            with open(filename, "w", encoding="utf-8") as f:
                syaml.dump_config(data, stream=f, default_flow_style=False)
        except (yaml.YAMLError, OSError) as e:
            raise ConfigFileError("Error writing to config file") from e

    def clear(self):
        """Empty cached config information."""
        self.sections = syaml.syaml_dict()

    def __repr__(self):
        return f"<ConfigScope: {self.name}: {self.path}>"


class SingleFileScope(ConfigScope):
    """This class represents a configuration scope in a single YAML file."""

    def __init__(self, name, path, schema, yaml_path=None):
        """Similar to ``ConfigScope`` but can be embedded in another schema.

        Arguments:
            schema (dict): jsonschema for the file to read
            yaml_path (list): path in the schema where config data can be
                found.
                If the schema accepts the following yaml data, the yaml_path
                would be ['outer', 'inner']

                .. code-block:: yaml

                   outer:
                     inner:
                       config:
                         install_tree: $ramble/opt/ramble
        """
        super().__init__(name, path)
        self._raw_data = None
        self.schema = schema
        self.yaml_path = yaml_path or []

    @property
    def is_platform_dependent(self):
        return False

    def get_section_filename(self, section):
        return self.path

    def get_section(self, section):
        # read raw data from the file, which looks like:
        # {
        #   'config': {
        #      ... data ...
        #   },
        #   'packages': {
        #      ... data ...
        #   },
        # }
        #
        # To preserve overrides up to the section level (e.g. to override
        # the "packages" section with the "::" syntax), data in self.sections
        # looks like this:
        # {
        #   'config': {
        #      'config': {
        #         ... data ...
        #       }
        #   },
        #   'packages': {
        #      'packages': {
        #         ... data ...
        #      }
        #   }
        # }

        # This bit ensures we have read the file and have
        # the raw data in memory
        if self._raw_data is None:
            self._raw_data = read_config_file(self.path, self.schema)
            if self._raw_data is None:
                return None

        # Here we know we have the raw data and ensure we
        # populate the sections dictionary, which may be
        # cleared by the clear() method
        if not self.sections:
            section_data = self._raw_data
            for key in self.yaml_path:
                if section_data is None:
                    return None
                section_data = section_data[key]

            for section_key, data in section_data.items():
                self.sections[section_key] = {section_key: data}

        return self.sections.get(section)

    def _write_section(self, section):
        data_to_write = self._raw_data

        # If there is no existing data, this section SingleFileScope has never
        # been written to disk. We need to construct the portion of the data
        # from the root of self._raw_data to the level at which the config
        # sections are defined. That requires creating keys for every entry in
        # self.yaml_path
        if not data_to_write:
            data_to_write = {}
            # reverse because we construct it from the inside out
            for key in reversed(self.yaml_path):
                data_to_write = {key: data_to_write}

        # data_update_pointer is a pointer to the part of data_to_write
        # that we are currently updating.
        # We start by traversing into the data to the point at which the
        # config sections are defined. This means popping the keys from
        # self.yaml_path
        data_update_pointer = data_to_write
        for key in self.yaml_path:
            data_update_pointer = data_update_pointer[key]

        # For each section, update the data at the level of our pointer
        # with the data from the section
        for key, data in self.sections.items():
            data_update_pointer[key] = data[key]

        validate(data_to_write, self.schema)
        try:
            parent = os.path.dirname(self.path)
            mkdirp(parent)

            tmp = os.path.join(parent, f".{os.path.basename(self.path)}.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                syaml.dump_config(data_to_write, stream=f, default_flow_style=False)
            rename(tmp, self.path)

        except (yaml.YAMLError, OSError) as e:
            raise ConfigFileError("Error writing to config file") from e

    def __repr__(self):
        return f"<SingleFileScope: {self.name}: {self.path}>"


class ImmutableConfigScope(ConfigScope):
    """A configuration scope that cannot be written to.

    This is used for ConfigScopes passed on the command line.
    """

    def _write_section(self, section):
        raise ConfigError(f"Cannot write to immutable scope {self}")

    def __repr__(self):
        return f"<ImmutableConfigScope: {self.name}: {self.path}>"


class InternalConfigScope(ConfigScope):
    """An internal configuration scope that is not persisted to a file.

    This is for Ramble internal use so that command-line options and
    config file settings are accessed the same way, and Ramble can easily
    override settings from files.
    """

    def __init__(self, name, data=None):
        super().__init__(name, None)
        self.sections = syaml.syaml_dict()

        if data:
            data = InternalConfigScope._process_dict_keyname_overrides(data)
            for section in data:
                dsec = data[section]
                validate({section: dsec}, section_schemas[section])
                self.sections[section] = _mark_internal(syaml.syaml_dict({section: dsec}), name)

    def get_section_filename(self, section):
        raise NotImplementedError("Cannot get filename for InternalConfigScope.")

    def get_section(self, section):
        """Just reads from an internal dictionary."""
        if section not in self.sections:
            self.sections[section] = None
        return self.sections[section]

    def _write_section(self, section):
        """This only validates, as the data is already in memory."""
        data = self.get_section(section)
        if data is not None:
            validate(data, section_schemas[section])
        self.sections[section] = _mark_internal(data, self.name)

    def __repr__(self):
        return f"<InternalConfigScope: {self.name}>"

    def clear(self):
        # no cache to clear here.
        pass

    @staticmethod
    def _process_dict_keyname_overrides(data):
        """Turn a trailing `:' in a key name into an override attribute."""
        result = {}
        for sk, sv in data.items():
            if sk.endswith(":"):
                key = syaml.syaml_str(sk[:-1])
                key.override = True
            else:
                key = sk

            if isinstance(sv, dict):
                result[key] = InternalConfigScope._process_dict_keyname_overrides(sv)
            else:
                result[key] = copy.copy(sv)

        return result


def _config_mutator(method):
    """Decorator to mark all the methods in the Configuration class
    that mutate the underlying configuration. Used to clear the
    memoization cache.
    """

    @functools.wraps(method)
    def _method(self, *args, **kwargs):
        if hasattr(self, "_get_config_cache"):
            self._get_config_cache.clear()
        return method(self, *args, **kwargs)

    return _method


class Configuration:
    """A full Ramble configuration, from a hierarchy of config files.

    This class makes it easy to add a new scope on top of an existing one.
    """

    def __init__(self, *scopes):
        """Initialize a configuration with an initial list of scopes.

        Args:
            scopes (list of ConfigScope): list of scopes to add to this
                Configuration, ordered from lowest to highest precedence

        """
        self.scopes = collections.OrderedDict()
        for scope in scopes:
            self.push_scope(scope)
        self.format_updates = collections.defaultdict(list)

    @_config_mutator
    def push_scope(self, scope):
        """Add a higher precedence scope to the Configuration."""
        cmd_line_scope = None
        if self.scopes:
            highest_precedence_scope = list(self.scopes.values())[-1]
            if highest_precedence_scope.name == "command_line":
                # If the command-line scope is present, it should always
                # be the scope of highest precedence
                cmd_line_scope = self.pop_scope()

        self.scopes[scope.name] = scope
        if cmd_line_scope:
            self.scopes["command_line"] = cmd_line_scope

    @_config_mutator
    def pop_scope(self):
        """Remove the highest precedence scope and return it."""
        _, scope = self.scopes.popitem(last=True)
        return scope

    @_config_mutator
    def remove_scope(self, scope_name):
        """Remove scope by name; has no effect when ``scope_name`` does not exist"""
        return self.scopes.pop(scope_name, None)

    @property
    def file_scopes(self):
        """List of writable scopes with an associated file."""
        return [
            s
            for s in self.scopes.values()
            if (type(s) is ConfigScope or type(s) is SingleFileScope)
        ]

    def highest_precedence_scope(self):
        """Non-internal scope with highest precedence."""
        return next(reversed(self.file_scopes), None)

    def highest_precedence_non_platform_scope(self):
        """Non-internal non-platform scope with highest precedence

        Platform-specific scopes are of the form scope/platform"""
        generator = reversed(self.file_scopes)
        highest = next(generator, None)
        while highest and highest.is_platform_dependent:
            highest = next(generator, None)
        return highest

    def matching_scopes(self, reg_expr):
        """
        List of all scopes whose names match the provided regular expression.

        For example, matching_scopes(r'^command') will return all scopes
        whose names begin with `command`.
        """
        return [s for s in self.scopes.values() if re.search(reg_expr, s.name)]

    def _validate_scope(self, scope):
        """Ensure that scope is valid in this configuration.

        This should be used by routines in ``config.py`` to validate
        scope name arguments, and to determine a default scope where no
        scope is specified.

        Raises:
            ValueError: if ``scope`` is not valid

        Returns:
            ramble.config.ConfigScope: A valid ConfigScope if ``scope`` is ``None`` or valid
        """
        if scope is None:
            # default to the scope with highest precedence.
            return self.highest_precedence_scope()

        elif scope in self.scopes:
            return self.scopes[scope]

        else:
            raise ValueError(
                f"Invalid config scope: '{scope}'.  Must be one of {self.scopes.keys()}"
            )

    def get_config_filename(self, scope, section):
        """For some scope and section, get the name of the configuration file."""
        scope = self._validate_scope(scope)
        return scope.get_section_filename(section)

    @_config_mutator
    def clear_caches(self):
        """Clears the caches for configuration files,

        This will cause files to be re-read upon the next request."""
        for scope in self.scopes.values():
            scope.clear()

    @_config_mutator
    def update_config(self, section, update_data, scope=None, force=False):
        """Update the configuration file for a particular scope.

        Overwrites contents of a section in a scope with update_data,
        then writes out the config file.

        update_data should have the top-level section name stripped off
        (it will be re-added).  Data itself can be a list, dict, or any
        other yaml-ish structure.

        Configuration scopes that are still written in an old schema
        format will fail to update unless ``force`` is True.

        Args:
            section (str): section of the configuration to be updated
            update_data (dict): data to be used for the update
            scope (str): scope to be updated
            force (str): force the update
        """
        if self.format_updates.get(section) and not force:
            msg = (
                'The "{0}" section of the configuration needs to be written'
                " to disk, but is currently using a deprecated format. "
                "Please update it using:\n\n"
                "\tramble config [--scope=<scope] update {0}\n\n"
                "Note that previous versions of Ramble will not be able to "
                "use the updated configuration."
            )
            msg = msg.format(section)
            raise RuntimeError(msg)

        _validate_section_name(section)  # validate section name
        scope = self._validate_scope(scope)  # get ConfigScope object

        # manually preserve comments
        need_comment_copy = section in scope.sections and scope.sections[section] is not None
        if need_comment_copy:
            comments = getattr(
                scope.sections[section][section], yaml.comments.Comment.attrib, None
            )

        # read only the requested section's data.
        scope.sections[section] = syaml.syaml_dict({section: update_data})
        if need_comment_copy and comments:
            setattr(scope.sections[section][section], yaml.comments.Comment.attrib, comments)

        scope._write_section(section)

    def get_config(self, section, scope=None):
        """Get configuration settings for a section.

        If ``scope`` is ``None`` or not provided, return the merged contents
        of all of ramble's configuration scopes.  If ``scope`` is provided,
        return only the configuration as specified in that scope.

        This off the top-level name from the YAML section.  That is, for a
        YAML config file that looks like this::

           config:
             install_tree: $ramble/opt/ramble
             module_roots:
               lmod:   $ramble/share/ramble/lmod

        ``get_config('config')`` will return::

           { 'install_tree': '$ramble/opt/ramble',
             'module_roots: {
                 'lmod': '$ramble/share/ramble/lmod'
             }
           }

        """
        if not hasattr(self, "_get_config_cache"):
            self._get_config_cache = {}

        key = (section, scope)
        if key not in self._get_config_cache:
            self._get_config_cache[key] = self._get_config_no_memo(section, scope)

        return self._get_config_cache[key]

    def _get_config_no_memo(self, section, scope):
        _validate_section_name(section)

        if scope is None:
            scopes = self.scopes.values()
        else:
            scopes = [self._validate_scope(scope)]

        merged_section = syaml.syaml_dict()
        for scope in scopes:
            # read potentially cached data from the scope.

            data = scope.get_section(section)

            # Skip empty configs
            if not data or not isinstance(data, dict):
                continue

            if section not in data:
                continue

            # We might be reading configuration files in an old format,
            # thus read data and update it in memory if need be.
            changed = _update_in_memory(data, section)
            if changed:
                self.format_updates[section].append(scope)

            merged_section = merge_yaml(merged_section, data)

        # no config files -- empty config.
        if section not in merged_section:
            return syaml.syaml_dict()

        # take the top key off before returning.
        ret = merged_section[section]
        if isinstance(ret, dict):
            ret = syaml.syaml_dict(ret)
        return ret

    def get(self, path, default=None, scope=None):
        """Get a config section or a single value from one.

        Accepts a path syntax that allows us to grab nested config map
        entries.  Getting the 'config' section would look like::

            ramble.config.get('config')

        and the ``dirty`` section in the ``config`` scope would be::

            ramble.config.get('config:dirty')

        We use ``:`` as the separator, like YAML objects.
        """
        # TODO: Currently only handles maps. Think about lists if needed.
        parts = process_config_path(path)
        section = parts.pop(0)

        value = self.get_config(section, scope=scope)

        while parts:
            key = parts.pop(0)
            # cannot use value.get(key, default) in case there is another part
            # and default is not a dict
            if key not in value:
                return default
            value = value[key]

        return value

    @_config_mutator
    def set(self, path, value, scope=None):
        """Convenience function for setting single values in config files.

        Accepts the path syntax described in ``get()``.
        """
        if ":" not in path:
            # handle bare section name as path
            self.update_config(path, value, scope=scope)
            return

        parts = process_config_path(path)
        section = parts.pop(0)

        section_data = self.get_config(section, scope=scope)

        data = section_data
        while len(parts) > 1:
            key = parts.pop(0)

            if _override(key):
                new = type(data[key])()
                del data[key]
            else:
                new = data[key]

            if isinstance(new, dict):
                # Make it an ordered dict
                new = syaml.syaml_dict(new)
                # reattach to parent object
                data[key] = new
            data = new

        if _override(parts[0]):
            data.pop(parts[0], None)

        # update new value
        data[parts[0]] = value

        self.update_config(section, section_data, scope=scope)

    def __iter__(self):
        """Iterate over scopes in this configuration."""
        yield from self.scopes.values()

    def print_section(self, section, blame=False):
        """Print a configuration to stdout."""
        try:
            data = syaml.syaml_dict()
            data[section] = self.get_config(section)
            syaml.dump_config(data, stream=sys.stdout, default_flow_style=False, blame=blame)
        except (yaml.YAMLError, OSError):
            raise ConfigError(f"Error reading configuration: {section}") from None


@contextmanager
def override(path_or_scope, value=None):
    """Simple way to override config settings within a context.

    Arguments:
        path_or_scope (ConfigScope | str): scope or single option to override
        value (object | None): value for the single option

    Temporarily push a scope on the current configuration, then remove it
    after the context completes. If a single option is provided, create
    an internal config scope for it and push/pop that scope.

    """
    if isinstance(path_or_scope, ConfigScope):
        overrides = path_or_scope
        config.push_scope(path_or_scope)
    else:
        base_name = overrides_base_name
        # Ensure the new override gets a unique scope name
        current_overrides = [s.name for s in config.matching_scopes(rf"^{base_name}")]
        num_overrides = len(current_overrides)
        while True:
            scope_name = f"{base_name}{num_overrides}"
            if scope_name in current_overrides:
                num_overrides += 1
            else:
                break

        overrides = InternalConfigScope(scope_name)
        config.push_scope(overrides)
        config.set(path_or_scope, value, scope=scope_name)

    try:
        yield config
    finally:
        scope = config.remove_scope(overrides.name)
        assert scope is overrides


#: configuration scopes added on the command line
#: set by ``ramble.main.main()``.
command_line_scopes: List[str] = []


def _add_platform_scope(cfg, scope_type, name, path):
    """Add a platform-specific subdirectory for the current platform."""
    platform = spack.platforms.host().name
    plat_name = os.path.join(name, platform)
    plat_path = os.path.join(path, platform)
    cfg.push_scope(scope_type(plat_name, plat_path))


def _add_command_line_scopes(cfg, command_line_scopes):
    """Add additional scopes from the --config-scope argument.

    Command line scopes are named after their position in the arg list.
    """
    for i, path in enumerate(command_line_scopes):
        # We ensure that these scopes exist and are readable, as they are
        # provided on the command line by the user.
        if not os.path.isdir(path):
            raise ConfigError(f"config scope is not a directory: '{path}'")
        elif not os.access(path, os.R_OK):
            raise ConfigError(f"config scope is not readable: '{path}'")

        # name based on order on the command line
        name = "cmd_scope_%d" % i
        cfg.push_scope(ImmutableConfigScope(name, path))
        _add_platform_scope(cfg, ImmutableConfigScope, name, path)


def _config():
    """Singleton Configuration instance.

    This constructs one instance associated with this module and returns
    it. It is bundled inside a function so that configuration can be
    initialized lazily.

    Return:
        (Configuration): object for accessing ramble configuration

    """
    cfg = Configuration()

    # first do the builtin, hardcoded defaults
    defaults = InternalConfigScope("_builtin", config_defaults)
    cfg.push_scope(defaults)

    # add each scope
    for name, path in configuration_paths:
        cfg.push_scope(ConfigScope(name, path))

        # Each scope can have per-platform overrides in subdirectories
        _add_platform_scope(cfg, ConfigScope, name, path)

    # add command-line scopes
    _add_command_line_scopes(cfg, command_line_scopes)

    # we make a special scope for ramble commands so that they can
    # override configuration options.
    cfg.push_scope(InternalConfigScope("command_line"))

    return cfg


#: This is the singleton configuration instance for ramble.
config = llnl.util.lang.Singleton(_config)


def add_from_file(filename, scope=None):
    """Add updates to a config from a filename"""
    # Get file as config dict
    data = read_config_file(filename)

    # update all sections from config dict
    # We have to iterate on keys to keep overrides from the file
    for section in data:
        if section in section_schemas:
            # Special handling for compiler scope difference
            # Has to be handled after we choose a section
            if scope is None:
                scope = default_modify_scope(section)

            value = data[section]
            existing = get(section, scope=scope)
            new = merge_yaml(existing, value, path=[section])

            # We cannot call config.set directly (set is a type)
            config.set(section, new, scope)


def add(fullpath, scope=None):
    """Add the given configuration to the specified config scope.
    Add accepts a path. If you want to add from a filename, use add_from_file"""

    components = process_config_path(fullpath)

    has_existing_value = True
    path = ""
    override = False
    for idx, name in enumerate(itertools.islice(components, len(components) - 1)):
        # First handle double colons in constructing path
        colon = "::" if override else ":" if path else ""
        path += colon + name
        if getattr(name, "override", False):
            override = True
        else:
            override = False

        # Test whether there is an existing value at this level
        existing = get(path, scope=scope)

        if existing is None:
            has_existing_value = False
            # We've nested further than existing config, so we need the
            # type information for validation to know how to handle bare
            # values appended to lists.
            existing = get_valid_type(path)

            # construct value from this point down
            value = load_config(components[-1])
            for component in reversed(components[idx + 1 : -1]):
                value = {component: value}
            break

    if has_existing_value:
        path, _, value = fullpath.rpartition(":")
        value = load_config(value)
        existing = get(path, scope=scope)

    # append values to lists
    if isinstance(existing, list) and not isinstance(value, list):
        value = [value]

    # merge value into existing
    new = merge_yaml(existing, value, path=process_config_path(path))
    config.set(path, new, scope)


def get(path, default=None, scope=None):
    """Module-level wrapper for ``Configuration.get()``."""
    return config.get(path, default, scope)


def set(path, value, scope=None):
    """Convenience function for setting single values in config files.

    Accepts the path syntax described in ``get()``.
    """
    return config.set(path, value, scope)


def scopes():
    """Convenience function to get list of configuration scopes."""
    return config.scopes


def resolve_scope(scope):
    """Resolve a scope name to its canonical name.

    If scope is 'workspace', resolve it to the active workspace's scope name.
    """
    if scope == "workspace":
        import ramble.workspace

        ws = ramble.workspace.active_workspace()
        if ws:
            return ws.ws_file_config_scope_name()
        else:
            raise ValueError("Workspace scope requires an active workspace")
    return scope


def _validate_section_name(section):
    """Exit if the section is not a valid section."""
    if section not in section_schemas:
        raise ConfigSectionError(
            "Invalid config section: '%s'. Options are: %s"
            % (section, " ".join(section_schemas.keys()))
        )


def validate(data, schema, filename=None):
    """Validate data read in from a Ramble YAML file.

    Arguments:
        data (dict | list): data read from a Ramble YAML file
        schema (dict | list): jsonschema to validate data

    This leverages the line information (start_mark, end_mark) stored
    on Ramble YAML structures.
    """
    import jsonschema

    # validate a copy to avoid adding defaults
    # This allows us to round-trip data without adding to it.
    test_data = copy.deepcopy(data)

    if isinstance(test_data, yaml.comments.CommentedMap):
        # HACK to fully copy ruamel CommentedMap that doesn't provide copy
        # method. Especially necessary for workspaces
        setattr(
            test_data,
            yaml.comments.Comment.attrib,
            getattr(data, yaml.comments.Comment.attrib, yaml.comments.Comment()),
        )

    try:
        ramble.schema.Validator(schema).validate(test_data)
    except jsonschema.ValidationError as e:
        if hasattr(e.instance, "lc"):
            line_number = e.instance.lc.line + 1
        else:
            line_number = None
        raise ConfigFormatError(e, data, filename, line_number) from e
    # return the validated data so that we can access the raw data
    # mostly relevant for workspaces
    return test_data


def read_config_file(filename, schema=None):
    """Read a YAML configuration file.

    User can provide a schema for validation. If no schema is provided,
    we will infer the schema from the top-level key."""
    # Dev: Inferring schema and allowing it to be provided directly allows us
    # to preserve flexibility in calling convention (don't need to provide
    # schema when it's not necessary) while allowing us to validate against a
    # known schema when the top-level key could be incorrect.

    # Ignore nonexisting files.
    if not os.path.exists(filename):
        return None

    elif not os.path.isfile(filename):
        raise ConfigFileError(f"Invalid configuration. {filename} exists but is not a file.")

    elif not os.access(filename, os.R_OK):
        raise ConfigFileError(f"Config file is not readable: {filename}")

    try:
        logger.debug(f"Reading config file {filename}")
        with open(filename, encoding="utf-8") as f:
            data = load_config(f)

        if data:
            if not schema:
                key = next(iter(data))
                schema = all_schemas[key]
            validate(data, schema)
        return data

    except StopIteration:
        raise ConfigFileError(
            f"Config file is empty or is not a valid YAML dict: {filename}"
        ) from None

    except MarkedYAMLError as e:
        raise ConfigFileError(f"Error parsing yaml{str(e.context_mark)}: {e.problem}") from e

    except OSError as e:
        raise ConfigFileError(f"Error reading configuration file {filename}") from e


def _override(string):
    """Test if a ramble YAML string is an override.

    See ``ramble_yaml`` for details.  Keys in Ramble YAML can end in `::`,
    and if they do, their values completely replace lower-precedence
    configs instead of merging into them.

    """
    return hasattr(string, "override") and string.override


def _mark_internal(data, name):
    """Add a simple name mark to raw YAML/JSON data.

    This is used by `ramble config blame` to show where config lines came from.
    """
    if isinstance(data, dict):
        d = syaml.syaml_dict(
            (_mark_internal(k, name), _mark_internal(v, name)) for k, v in data.items()
        )
    elif isinstance(data, list):
        d = syaml.syaml_list(_mark_internal(e, name) for e in data)
    else:
        d = syaml.syaml_type(data)

    if syaml.markable(d):
        d._start_mark = yaml.Mark(name, None, None, None, None, None)
        d._end_mark = yaml.Mark(name, None, None, None, None, None)

    return d


def get_valid_type(path):
    """Returns an instance of a type that will pass validation for path.

    The instance is created by calling the constructor with no arguments.
    If multiple types will satisfy validation for data at the configuration
    path given, the priority order is ``list``, ``dict``, ``str``, ``bool``,
    ``int``, ``float``.
    """
    types = {
        "array": list,
        "object": syaml.syaml_dict,
        "string": str,
        "boolean": bool,
        "integer": int,
        "number": float,
    }

    components = process_config_path(path)
    section = components[0]

    # Use None to construct the test data
    test_data = None
    for component in reversed(components):
        test_data = {component: test_data}

    try:
        validate(test_data, section_schemas[section])
    except (ConfigFormatError, AttributeError) as e:
        jsonschema_error = e.validation_error
        if jsonschema_error.validator == "type":
            return types[jsonschema_error.validator_value]()
        elif jsonschema_error.validator in ("anyOf", "oneOf"):
            for subschema in jsonschema_error.validator_value:
                schema_type = subschema.get("type")
                if schema_type is not None:
                    return types[schema_type]()
    else:
        return type(None)
    raise ConfigError(f"Cannot determine valid type for path '{path}'.")


def merge_yaml(dest, source, path=None):
    """Merges source into dest; entries in source take precedence over dest.

    This routine may modify dest and should be assigned to dest, in
    case dest was None to begin with, e.g.:

       dest = merge_yaml(dest, source)

    In the result, elements from lists from ``source`` will appear before
    elements of lists from ``dest``. Likewise, when iterating over keys
    or items in merged ``OrderedDict`` objects, keys from ``source`` will
    appear before keys from ``dest``.

    Config file authors can optionally end any attribute in a dict
    with `::` instead of `:`, and the key will override that of the
    parent instead of merging.
    """
    if path is None:
        path = []

    def they_are(t):
        return isinstance(dest, t) and isinstance(source, t)

    # If source is None, overwrite with source.
    if source is None:
        return None

    # Source list is prepended (for precedence)
    if they_are(list):
        # Make sure to copy ruamel comments
        dest[:] = source + [x for x in dest if x not in source]
        return dest

    # Source dict is merged into dest.
    elif they_are(dict):
        # save dest keys to reinsert later -- this ensures that  source items
        # come *before* dest in OrderedDicts
        dest_keys = [dk for dk in dest if dk not in source]

        for sk, sv in source.items():
            # always remove the dest items. Python dicts do not overwrite
            # keys on insert, so this ensures that source keys are copied
            # into dest along with mark provenance (i.e., file/line info).
            merge = sk in dest
            old_dest_value = dest.pop(sk, None)

            current_path = path + [sk]
            should_override = _override(sk)
            if not should_override:
                if len(current_path) == 2 and current_path[0] == "filter_groups":
                    should_override = True

            if merge and not should_override:
                dest[sk] = merge_yaml(old_dest_value, sv, current_path)
            else:
                # if sk ended with ::, or if it's new, completely override
                dest[sk] = copy.deepcopy(sv)

        # reinsert dest keys so they are last in the result
        for dk in dest_keys:
            dest[dk] = dest.pop(dk)

        return yaml.comments.CommentedMap(dest)

    # If we reach here source and dest are either different types or are
    # not both lists or dicts: replace with source.
    return copy.copy(source)


#
# Process a path argument to config.set() that may contain overrides ('::' or
# trailing ':')
#
def process_config_path(path):
    result = []
    if path.startswith(":"):
        raise ConfigError(f"Illegal leading `:' in path `{path}'", "")
    seen_override_in_path = False
    while path:
        front, sep, path = path.partition(":")
        if (sep and not path) or path.startswith(":"):
            if seen_override_in_path:
                raise ConfigError(
                    f"Meaningless second override indicator `::' in path `{path}'", ""
                )
            path = path.lstrip(":")
            front = syaml.syaml_str(front)
            front.override = True
            seen_override_in_path = True
        result.append(front)
    return result


#
# Settings for commands that modify configuration
#
def default_modify_scope(section="config"):
    """Return the config scope that commands should modify by default.

    Commands that modify configuration by default modify the *highest*
    priority scope.

    Arguments:
        section (bool): Section for which to get the default scope.
            If this is not 'experiments', a general (non-workspace) scope is
            used.
    """
    # TODO Ensure the correct scoping for different sections.
    if section == "experiments":
        return ramble.config.config.highest_precedence_scope().name
    else:
        return ramble.config.config.highest_precedence_non_platform_scope().name


def default_list_scope():
    """Return the config scope that is listed by default.

    Commands that list configuration list *all* scopes (merged) by default.
    """
    return


def _update_in_memory(data, section):
    """Update the format of the configuration data in memory.

    This function assumes the section is valid (i.e. validation
    is responsibility of the caller)

    Args:
        data (dict): configuration data
        section (str): section of the configuration to update

    Returns:
        bool: ``True`` if the data was changed, ``False`` otherwise
    """
    update_fn = ensure_latest_format_fn(section)
    changed = update_fn(data[section])
    return changed


def ensure_latest_format_fn(section):
    """Return a function that takes as input a dictionary read from
    a configuration file and update it to the latest format.

    The function returns True if there was any update, False otherwise.

    Args:
        section (str): section of the configuration e.g. "applications",
            "config", etc.
    """
    # The line below is based on the fact that every module we need
    # is already imported at the top level
    section_module = getattr(ramble.schema, section)
    update_fn = getattr(section_module, "update", lambda x: False)
    return update_fn


@contextlib.contextmanager
def use_configuration(*scopes_or_paths):
    """Use the configuration scopes passed as arguments within the
    context manager.

    Args:
        *scopes_or_paths: scope objects or paths to be used

    Returns:
        ramble.config.Configuration: Configuration object associated with the scopes
        passed as arguments
    """
    global config

    # Normalize input and construct a Configuration object
    configuration = _config_from(scopes_or_paths)
    config.clear_caches(), configuration.clear_caches()

    # Save and clear the current compiler cache
    saved_compiler_cache = spack.compilers._cache_config_file
    spack.compilers._cache_config_file = []

    saved_config, config = config, configuration

    import ramble.repository

    saved_instances = {}
    for obj_type, singleton in ramble.repository.paths.items():
        saved_instances[obj_type] = singleton._instance
        singleton._instance = None
    saved_meta_path = list(sys.meta_path)

    try:
        yield configuration
    finally:
        for obj_type, instance in saved_instances.items():
            ramble.repository.paths[obj_type]._instance = instance
        sys.meta_path = saved_meta_path

        # Restore previous config files
        spack.compilers._cache_config_file = saved_compiler_cache
        config = saved_config


@llnl.util.lang.memoized
def _config_from(scopes_or_paths):
    scopes = []
    for scope_or_path in scopes_or_paths:
        # If we have a config scope we are already done
        if isinstance(scope_or_path, ConfigScope):
            scopes.append(scope_or_path)
            continue

        # Otherwise we need to construct it
        path = os.path.normpath(scope_or_path)
        assert os.path.isdir(path), f'"{path}" must be a directory'
        name = os.path.basename(path)
        scopes.append(ConfigScope(name, path))

    configuration = Configuration(*scopes)
    return configuration


class ConfigError(RambleError):
    """Superclass for all ramble config related errors."""


class ConfigSectionError(ConfigError):
    """Error for referring to a bad config section name in a configuration."""


class ConfigFileError(ConfigError):
    """Issue reading or accessing a configuration file."""


class ConfigFormatError(ConfigError):
    """Raised when a configuration format does not match its schema."""

    def __init__(self, validation_error, data, filename=None, line=None):
        # ramble yaml has its own file/line marks -- try to find them
        # we prioritize these over the inputs
        self.validation_error = validation_error
        mark = self._get_mark(validation_error, data)
        if mark:
            filename = mark.name
            line = mark.line + 1

        self.filename = filename  # record this for ruamel.yaml

        # construct the location and retrieve the line that caused the error
        location = "<unknown file>"
        if filename:
            location = f"{filename}"
        if line is not None:
            location += f":{line}"
            with open(filename, encoding="utf-8") as file:
                lines = file.readlines()
                location += f"\n{lines[mark.line]}"

        message = f"{location}\n{validation_error}"
        super(ConfigError, self).__init__(message)

    def _get_mark(self, validation_error, data):
        """Get the file/line mark for a validation error from a Ramble YAML file."""

        def _get_mark_or_first_member_mark(obj):
            # mark of object itelf
            mark = getattr(obj, "_start_mark", None)
            if mark:
                return mark

            # mark of first member if it is a container
            if isinstance(obj, (list, dict)):
                first_member = next(iter(obj), None)
                if first_member:
                    mark = getattr(first_member, "_start_mark", None)
                    if mark:
                        return mark

        # Try various places, starting with instance and parent
        for obj in (validation_error.instance, validation_error.parent):
            mark = _get_mark_or_first_member_mark(obj)
            if mark:
                return mark

        def get_path(path, data):
            if path:
                return get_path(path[1:], data[path[0]])
            else:
                return data

        # Try really hard to get the parent (which sometimes is not
        # set) This digs it out of the validated structure if it's not
        # on the validation_error.
        path = validation_error.path
        if path:
            parent = get_path(list(path)[:-1], data)
            if path[-1] in parent:
                if isinstance(parent, dict):
                    keylist = list(parent.keys())
                elif isinstance(parent, list):
                    keylist = parent
                idx = keylist.index(path[-1])
                mark = getattr(keylist[idx], "_start_mark", None)
                if mark:
                    return mark

        # give up and return None if nothing worked
        return None
