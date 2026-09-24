# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import functools

import ramble.language.shared_language

"""This package contains directives that can be used within a system.

Directives are functions that can be called inside a system
definition to modify then system, for example:

    .. code-block:: python

      class MySystem(System):
          default_platform('c2')

In the above example, 'default_platform' is a ramble directive
"""

SystemMeta = ramble.language.shared_language.SharedMeta
system_directive = functools.partial(SystemMeta.directive, language_type="system")


@system_directive(dicts="system_default_workflow_manager", init_value=None)
def default_workflow_manager(name, **kwargs):
    """Sets the default workflow manager for this system

    Args:
      name (str): The name of the default workflow manager
    """

    def _execute_default_workflow_manager(obj):
        obj.system_default_workflow_manager = name

    return _execute_default_workflow_manager


@system_directive(dicts="system_default_package_manager", init_value=None)
def default_package_manager(name, **kwargs):
    """Sets the default package manager for this system

    Args:
      name (str): The name of the default package manager
    """

    def _execute_default_package_manager(obj):
        obj.system_default_package_manager = name

    return _execute_default_package_manager


@system_directive(dicts="system_default_platform", init_value=None)
def default_platform(name, **kwargs):
    """Sets the default platform for this system

    Args:
      name (str): The name of the default platform
    """

    def _execute_default_platform(obj):
        obj.system_default_platform = name

    return _execute_default_platform


@system_directive(dicts="system_available_platforms", init_value=[])
def available_platforms(platforms, **kwargs):
    """Sets the available platforms for this system

    Args:
      platforms (list): List of available platforms
    """

    def _execute_available_platforms(obj):
        platform_set = set(getattr(obj, "system_available_platforms", []))

        if isinstance(platforms, list):
            for platform in platforms:
                platform_set.add(platform)
        else:
            platform_set.add(platforms)
        obj.system_available_platforms = sorted(platform_set)

    return _execute_available_platforms


@system_directive(dicts="platform_variable_maps", init_value={})
def platform_variable_map(variable_name, var_map, **kwargs):
    """Defines a mapping of platform to variable values

    Args:
      variable_name (str): The name of the variable
      var_map (dict): Mapping of platform name to variable value
    """

    def _execute_platform_variable_map(obj):
        if variable_name not in obj.platform_variable_maps:
            obj.platform_variable_maps[variable_name] = {}
        obj.platform_variable_maps[variable_name].update(var_map)

    return _execute_platform_variable_map


@system_directive(dicts="variable_defaults", init_value={})
def variable_defaults(variable_definitions, when=None, **kwargs):
    """Defines default values for variables

    Args:
      variable_definitions (dict): Mapping of variable name to value
      when (list | None): List of when conditions to apply to directive
    """

    def _execute_variable_defaults(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, str(variable_definitions), "variable_defaults"
        )
        when_key = frozenset(when_list)
        if when_key not in obj.variable_defaults:
            obj.variable_defaults[when_key] = {}
        obj.variable_defaults[when_key].update(variable_definitions)

    return _execute_variable_defaults


@system_directive(dicts="class_families", init_value={})
def system_family(*names: str, **kwargs):
    """Add a new family to this system

    Args:
        name (str): Name of family to apply to this system
    """
    return ramble.language.shared_language.class_family(*names, **kwargs)
