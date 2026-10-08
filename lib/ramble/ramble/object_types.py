# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from enum import Enum
from typing import Any, Dict

ObjectTypes = Enum(
    "ObjectTypes",
    [
        "applications",
        "modifiers",
        "package_managers",
        "workflow_managers",
        "systems",
        "platforms",
        "base_classes",
        "base_applications",
        "base_modifiers",
        "base_package_managers",
        "base_workflow_managers",
        "base_systems",
        "base_platforms",
        "utilities",
        "base_utilities",
    ],
)

OBJECT_NAMES = [obj.name for obj in ObjectTypes]

default_type = ObjectTypes.applications

unified_config = "repo.yaml"

type_definitions: Dict[ObjectTypes, Dict[str, Any]] = {
    ObjectTypes.applications: {
        "file_name": "application.py",
        "dir_name": "applications",
        "abbrev": "app",
        "kit_name": "appkit",
        "default_base": "ExecutableApplication",
        "config_section": "repos",
        "accepted_configs": ["application_repo.yaml", unified_config],
        "singular": "application",
    },
    ObjectTypes.modifiers: {
        "file_name": "modifier.py",
        "dir_name": "modifiers",
        "abbrev": "mod",
        "kit_name": "modkit",
        "default_base": "BasicModifier",
        "config_section": "modifier_repos",
        "accepted_configs": ["modifier_repo.yaml", unified_config],
        "singular": "modifier",
    },
    ObjectTypes.package_managers: {
        "file_name": "package_manager.py",
        "dir_name": "package_managers",
        "abbrev": "pkg_man",
        "kit_name": "pkgmankit",
        "default_base": "PackageManagerBase",
        "config_section": "package_manager_repos",
        "accepted_configs": ["package_manager_repo.yaml", unified_config],
        "singular": "package manager",
        "aliases": ["pkg", "package"],
    },
    ObjectTypes.workflow_managers: {
        "file_name": "workflow_manager.py",
        "dir_name": "workflow_managers",
        "abbrev": "wm",
        "kit_name": "wmkit",
        "default_base": "WorkflowManagerBase",
        "config_section": "workflow_manager_repos",
        "accepted_configs": ["workflow_manager_repo.yaml", unified_config],
        "singular": "workflow manager",
        "aliases": ["workflow"],
    },
    ObjectTypes.systems: {
        "file_name": "system.py",
        "dir_name": "systems",
        "abbrev": "sys",
        "kit_name": "syskit",
        "default_base": "SystemBase",
        "config_section": "system_repos",
        "accepted_configs": ["system_repo.yaml", unified_config],
        "singular": "system",
    },
    ObjectTypes.platforms: {
        "file_name": "platform.py",
        "dir_name": "platforms",
        "abbrev": "plat",
        "kit_name": "platkit",
        "default_base": "PlatformBase",
        "config_section": "platform_repos",
        "accepted_configs": ["platform_repo.yaml", unified_config],
        "singular": "platform",
    },
    ObjectTypes.base_classes: {
        "file_name": "base_class.py",
        "dir_name": "base_classes",
        "abbrev": "base_cls",
        "kit_name": None,
        "config_section": "base_class_repos",
        "accepted_configs": ["base_class_repo.yaml", unified_config],
        "singular": "base class",
        "aliases": ["base"],
    },
    ObjectTypes.base_applications: {
        "file_name": "base_application.py",
        "dir_name": "base_applications",
        "abbrev": "base_app",
        "kit_name": "appkit",
        "default_base": "ExecutableApplication",
        "config_section": "base_application_repos",
        "accepted_configs": ["base_application_repo.yaml", unified_config],
        "singular": "base application",
    },
    ObjectTypes.base_modifiers: {
        "file_name": "base_modifier.py",
        "dir_name": "base_modifiers",
        "abbrev": "base_mod",
        "kit_name": "modkit",
        "default_base": "BasicModifier",
        "config_section": "base_modifier_repos",
        "accepted_configs": ["base_modifier_repo.yaml", unified_config],
        "singular": "base modifier",
    },
    ObjectTypes.base_package_managers: {
        "file_name": "base_package_manager.py",
        "dir_name": "base_package_managers",
        "abbrev": "base_pkg_man",
        "kit_name": "pkgmankit",
        "default_base": "PackageManagerBase",
        "config_section": "base_package_manager_repos",
        "accepted_configs": ["base_package_manager_repo.yaml", unified_config],
        "singular": "base package manager",
        "aliases": ["base_pkg"],
    },
    ObjectTypes.base_workflow_managers: {
        "file_name": "base_workflow_manager.py",
        "dir_name": "base_workflow_managers",
        "abbrev": "base_wm",
        "kit_name": "wmkit",
        "default_base": "WorkflowManagerBase",
        "config_section": "base_workflow_manager_repos",
        "accepted_configs": ["base_workflow_manager_repo.yaml", unified_config],
        "singular": "base workflow manager",
        "aliases": ["base_workflow"],
    },
    ObjectTypes.base_systems: {
        "file_name": "base_system.py",
        "dir_name": "base_systems",
        "abbrev": "base_sys",
        "kit_name": "syskit",
        "default_base": "SystemBase",
        "config_section": "base_system_repos",
        "accepted_configs": ["base_system_repo.yaml", unified_config],
        "singular": "base system",
    },
    ObjectTypes.base_platforms: {
        "file_name": "base_platform.py",
        "dir_name": "base_platforms",
        "abbrev": "base_plat",
        "kit_name": "platkit",
        "default_base": "PlatformBase",
        "config_section": "base_platform_repos",
        "accepted_configs": ["base_platform_repo.yaml", unified_config],
        "singular": "base platform",
    },
    ObjectTypes.utilities: {
        "file_name": "utility.py",
        "dir_name": "utilities",
        "abbrev": "utility",
        "kit_name": "toolkit",
        "default_base": "UtilityBase",
        "config_section": "utility_repos",
        "accepted_configs": ["utility_repo.yaml", unified_config],
        "singular": "external dependency",
    },
    ObjectTypes.base_utilities: {
        "file_name": "base_utility.py",
        "dir_name": "base_utilities",
        "abbrev": "base_utility",
        "kit_name": "toolkit",
        "default_base": "UtilityBase",
        "config_section": "base_utility_repos",
        "accepted_configs": ["base_utility_repo.yaml", unified_config],
        "singular": "base external dependency",
    },
}
