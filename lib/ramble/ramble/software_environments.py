# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import copy
from collections import defaultdict
from typing import DefaultDict, Dict, List, Set

import ramble.config
import ramble.error
import ramble.util.colors as color
from ramble.expander import Expander
from ramble.namespace import namespace
from ramble.util.logger import logger
from ramble.util.spec_utils import SoftwareSpec

SUB_INDENT = 2


def _get_spec(
    pkg_info: dict, spec_name: str, prefix: str, allow_unprefixed=True, default=None
) -> str:
    if allow_unprefixed:
        return pkg_info.get(f"{prefix}_{spec_name}", pkg_info.get(spec_name, default))
    else:
        return pkg_info.get(f"{prefix}_{spec_name}", default)


def _is_dict_empty(rendered: defaultdict):
    if not rendered:
        return True
    for k in rendered:
        if rendered[k]:
            return False
    return True


class SoftwarePackage:
    """Class to represent a single software package"""

    def __init__(
        self,
        name: str,
        pkg_info: dict,
    ):
        """Software package constructor

        Args:
            name (str): Name of package
            pkg_info (dict): Package info containing specs for supported package managers
        """

        self.name = name
        self.pkg_info = pkg_info
        self._package_type = "Base"
        self._used = False
        self.injected = False

    def mark_used(self):
        """Mark this package a used"""
        self._used = True

    @property
    def is_used(self):
        """Return if this package is used or not

        Returns:
            bool: Whether package is used or not
        """
        return self._used

    def spec_str(self, all_packages=None, compiler=False):
        """Return a spec string for this software package

        Args:
            all_packages (dict | None): Dictionary of all package definitions.
                                 Used to look up compiler packages.
            compiler (bool): True of this package is used as a compiler for
                                another package. False if this is just a primary package.
                                Toggles returning compiler_spec vs. spec in case they are
                                different.

        Returns:
            str: String representation of the spec for this package definition
        """

        return ""

    def info(
        self, indent: int = 0, verbosity: int = 0, color_level: int = 0, only_used: bool = True
    ):
        """String representation of package information

        Args:
            indent (int): Number of spaces to indent lines with
            verbosity (int): Verbosity level
            color_level (int): Nested level for coloring
            only_used (bool): Whether to only track used info (True) or all info (False)

        Returns:
            str: String representation of this package
        """

        # Don't print if it is unused and we are only interested in used packages
        if only_used and not self.is_used:
            return ""

        indentation = " " * indent
        color_func = color.level_func(color_level)

        injected_str = "" if not self.injected else " (injected by ramble)"

        out_str = color_func(
            f"{indentation}{self._package_type} package: {self.name} {injected_str}\n"
        )
        return out_str

    def __str__(self):
        """String representation of software package

        Returns:
            str: String representation of this software package
        """

        return self.info()

    def __eq__(self, other):
        """Equvialence test for two package definitions

        Args:
            other (SoftwarePackage): Package to compare with self.

        Returns:
            bool: ``True`` if packages are the same, ``False`` otherwise
        """

        return (
            self.name == other.name
            and self.spec == other.spec
            and self.compiler == other.compiler
            and self.compiler_spec == other.compiler_spec
        )


class RenderedPackage(SoftwarePackage):
    """Class representing an already rendered software package"""

    def __init__(
        self,
        name: str,
        pkg_info: dict,
        package_manager,
        spec: str,
        compiler: str = "",
        compiler_spec: str = "",
    ):
        """Software package constructor

        Args:
            name (str): Name of package
            pkg_info (dict): Package info containing specs for supported package managers
            package_manager: package manager tied to this package
            spec (str): Package spec (used to install / load package)
            compiler (optional str): Name of package definition to use as compiler
                                     for this package
            compiler_spec (optional str): Spec string to use when this package
                                          is used as a compiler
        """
        super().__init__(name, pkg_info)
        self.name = name
        self.package_manager = package_manager
        self.spec = spec
        self.compiler = compiler
        self.compiler_spec = compiler_spec
        self._package_type = "Rendered"

    def spec_str(self, all_packages=None, compiler=False):
        """Return a spec string for this software package

        Args:
            all_packages (dict): Dictionary of all package definitions.
                                 Used to look up compiler packages.
            compiler (bool): True of this package is used as a compiler for
                                another package. False if this is just a primary package.
                                Toggles returning compiler_spec vs. spec in case they are
                                different.

        Returns:
            str: String representation of the spec for this package definition
        """
        if not all_packages:
            all_packages = defaultdict(dict)
        out_str = self.package_manager.get_spec_str(self, all_packages, compiler)

        return out_str

    def info(
        self, indent: int = 0, verbosity: int = 0, color_level: int = 0, only_used: bool = True
    ):
        """String representation of package information

        Args:
            indent (int): Number of spaces to indent lines with
            verbosity (int): Verbosity level
            color_level (int): Nested level for coloring
            only_used (bool): Whether to only track used info (True) or all info (False)

        Returns:
            str: String representation of this package
        """

        # Don't print if it is unused and we are only interested in used packages
        if only_used and not self.is_used:
            return ""

        indentation = " " * (indent + SUB_INDENT)
        out_str = super().info(indent, verbosity, color_level, only_used)
        out_str += f"{indentation}Spec: {self.spec}\n"
        if self.compiler:
            out_str += f"{indentation}Compiler: {self.compiler}\n"
        if self.compiler_spec:
            out_str += f"{indentation}Compiler Spec: {self.compiler_spec}\n"
        return out_str

    def __eq__(self, other):
        return self.package_manager.name == other.package_manager.name and super().__eq__(other)


class TemplatePackage(SoftwarePackage):
    """Class representing a template software package"""

    _rendered_packages: DefaultDict[str, Dict[str, RenderedPackage]]

    def __init__(
        self,
        name: str,
        pkg_info: dict,
    ):
        """Template package constructor

        Args:
            name (str): Name of package
            pkg_info (dict): Package info containing specs for supported package managers
        """
        # package_manager is only associated with a software package at render time
        super().__init__(name, pkg_info)
        self._rendered_packages = defaultdict(dict)
        self._package_type = "Template"

    @property
    def is_used(self):
        """Determine if template package is used

        Iterate over all packages in this template, and determine if any are
        used.

        Returns:
            bool: Whether this template contains any used packages or not
        """
        for pkgs in self._rendered_packages.values():
            for pkg in pkgs.values():
                if pkg.is_used:
                    return True
        return False

    def info(
        self, indent: int = 0, verbosity: int = 0, color_level: int = 0, only_used: bool = True
    ):
        """String representation of package information

        Args:
            indent (int): Number of spaces to indent lines with
            verbosity (int): Verbosity level
            color_level (int): Nested level for coloring
            only_used (bool): Whether to only track used info (True) or all info (False)

        Returns:
            str: String representation of this package
        """

        # Don't print if it is unused and we are only interested in used packages
        if only_used and not self.is_used:
            return ""

        out_str = ""
        pkg_man_indent = indent + SUB_INDENT
        indentation = " " * pkg_man_indent
        color_func = color.level_func(color_level + 1)
        for pkg_man, pkgs in self._rendered_packages.items():
            if pkgs:
                out_str += color_func(f"{indentation}{pkg_man} packages:\n")

            for pkg in pkgs.values():
                out_str += pkg.info(
                    indent=pkg_man_indent + SUB_INDENT,
                    verbosity=verbosity,
                    color_level=color_level + 2,
                    only_used=only_used,
                )

        if out_str == "" and not only_used:
            indentation = " " * (indent + SUB_INDENT)
            out_str = f"{indentation}No rendered packages\n"

        # If there are any rendered packages, prepend the header
        if out_str != "" or not only_used:
            out_str = super().info(indent, verbosity, color_level, only_used=only_used) + out_str
        return out_str

    def render_package(self, expander: Expander, package_manager):
        """Render a SoftwarePackage from this TemplatePackage

        Args:
            expander (ramble.expander.Expander): Expander to use to render a
                package from this template

        Returns:
            ramble.software_environments.SoftwarePackage: Rendered SoftwarePackage
        """
        name = expander.expand_var(self.name, merge_used_stage=False)
        pm_name = package_manager.name
        pkg_info = self.pkg_info
        pm_prefix = package_manager.spec_prefix
        pm_allow_unprefixed = package_manager.allow_unprefixed_specs

        raw_spec = _get_spec(pkg_info, "pkg_spec", pm_prefix, pm_allow_unprefixed)
        raw_compiler = _get_spec(pkg_info, "compiler", pm_prefix, pm_allow_unprefixed)
        raw_compiler_spec = _get_spec(pkg_info, "compiler_spec", pm_prefix, pm_allow_unprefixed)
        spec = (
            expander.expand_var(raw_spec, merge_used_stage=False) if raw_spec is not None else None
        )
        if not spec:
            if pm_allow_unprefixed:
                raise RambleSoftwareEnvironmentError(f"Package {name} is missing a valid spec")
            else:
                return None
        compiler = (
            expander.expand_var(raw_compiler, merge_used_stage=False)
            if raw_compiler is not None
            else None
        )
        compiler_spec = (
            expander.expand_var(raw_compiler_spec, merge_used_stage=False)
            if raw_compiler_spec is not None
            else None
        )

        new_pkg = RenderedPackage(name, pkg_info, package_manager, spec, compiler, compiler_spec)
        if new_pkg.name in self._rendered_packages[pm_name]:
            if new_pkg != self._rendered_packages[pm_name][name]:
                new_info = new_pkg.info(only_used=False, color_level=-1).replace("@", "")
                old_info = (
                    self._rendered_packages[pm_name][name]
                    .info(only_used=False, color_level=-1)
                    .replace("@", "")
                )
                raise RambleSoftwareEnvironmentError(
                    f"Package {new_pkg.name} defined multiple times with "
                    "inconsistent definitions.\n"
                    "New definition is:\n"
                    f"{new_info}\n"
                    "Old definition is:\n"
                    f"{old_info}\n"
                )
            return self._rendered_packages[pm_name][name]
        else:
            return new_pkg

    def add_rendered_package(self, new_package: RenderedPackage, all_packages: dict, pm_name: str):
        """Add a rendered package to this template's list of rendered packages

        Args:
            new_package (SoftwarePackage): New package definition to add
            all_packages (dict): Dictionary of all package definitions
            pm_name (str): The name of the package manager used for the package
        """

        if new_package.name not in self._rendered_packages[pm_name]:
            self._rendered_packages[pm_name][new_package.name] = new_package
            all_packages[pm_name][new_package.name] = new_package


class SoftwareEnvironment:
    """Class representing a single software environment"""

    def __init__(self, name: str):
        """SoftwareEnvironment constructor

        Args:
            name (str): Name of the environment
            package_manager: Package manager associated with the environment
        """

        self.name = name
        self._packages: List[SoftwarePackage] = []
        self._environment_type = "Base"
        self._used = False
        self.auto_constructed = False

    @property
    def is_used(self):
        """Determine if environment is used or not

        Returns:
            bool: Whether environment is used or not
        """
        return self._used

    def mark_used(self):
        """Mark this environment (and all of its packages) as used"""
        self._used = True
        for pkg in self._packages:
            pkg.mark_used()

    def info(
        self, indent: int = 0, verbosity: int = 0, color_level: int = 0, only_used: bool = True
    ):
        """Software environment information

        Args:
            indent (int): Number of spaces to inject as indentation
            verbosity (int): Verbosity level
            color_level (int): Nested level for coloring
            only_used (bool): Whether to only track used info (True) or all info (False)

        Returns:
            str: information of this environment
        """

        # Don't print if it is unused and we are only interested in used packages
        if only_used and not self.is_used:
            return ""

        indentation = " " * indent
        color_func = color.level_func(color_level)
        out_str = color_func(f"{indentation}{self._environment_type} environment: {self.name}\n")

        if self._packages:
            indentation = " " * (indent + SUB_INDENT)
            out_str += f"{indentation}Packages:\n"

        for pkg in self._packages:
            if verbosity >= 1:
                out_str += f"{indentation}- {pkg.name} = {pkg.spec_str()}\n"
            else:
                out_str += f"{indentation}- {pkg.name}\n"
        return out_str

    def __str__(self):
        """String representation of this environment

        Returns:
            str: Representation of this environment
        """
        return self.info(indent=0)

    def add_package(self, package: "SoftwarePackage"):
        """Add a package definition to this environment

        Args:
            package (SoftwarePackage): Package object
        """
        self._packages.append(package)

    def __eq__(self, other):
        """Equivalence test for environments

        Args:
            other (SoftwareEnvironment): Environment to compare with self

        Returns:
            bool: ``True`` if environments are equivalent, ``False`` otherwise
        """
        if not self.name == other.name:
            return False

        self_pkgs = {}
        other_pkgs = {}

        for self_pkg in self._packages:
            if not self_pkg.injected:
                self_pkgs[self_pkg.name] = self_pkg

        for other_pkg in other._packages:
            if not other_pkg.injected:
                other_pkgs[other_pkg.name] = other_pkg

        if self_pkgs != other_pkgs:
            return False

        return True


class ExternalEnvironment(SoftwareEnvironment):
    """Class representing an externally defined software environment"""

    def __init__(self, name: str, name_or_path: str):
        """Constructor for external software environment"""
        super().__init__(name)
        self.external_env = name_or_path


class RenderedExternalEnvironment(ExternalEnvironment):
    """Class representing a rendered externally defined software environment"""

    def __init__(self, name: str, name_or_path: str, package_manager):
        """Constructor for external software environment"""
        super().__init__(name, name_or_path)
        self.package_manager = package_manager

    @property
    def package_manager_name(self):
        return self.package_manager.name


class RenderedEnvironment(SoftwareEnvironment):
    """Class representing an already rendered software environment"""

    def __init__(self, name: str, package_manager):
        """Constructor for rendered software environment"""
        super().__init__(name)
        self.package_manager = package_manager

    @property
    def package_manager_name(self):
        return self.package_manager.name

    def __eq__(self, other):
        return self.package_manager.name == other.package_manager.name and super().__eq__(other)


class TemplateEnvironment(SoftwareEnvironment):
    """Class representing a template software environment"""

    _package_names: Set[str]
    _rendered_environments: DefaultDict[str, Dict[str, "RenderedEnvironment"]]

    def __init__(self, name: str):
        """TemplateEnvironment constructor

        Args:
            name (str): Name of this environment
        """
        super().__init__(name)
        self._package_names = set()
        self._rendered_environments = defaultdict(dict)
        self._environment_type = "Template"

    @property
    def is_used(self):
        """Determine if TemplateEnvironment is used or not

        Returns:
            bool: Whether template environment is used or not
        """
        for envs in self._rendered_environments.values():
            for env in envs.values():
                if env.is_used:
                    return True
        return False

    def add_package_name(self, package: str = ""):
        self._package_names.add(package)

    def info(
        self, indent: int = 0, verbosity: int = 0, color_level: int = 0, only_used: bool = True
    ):
        """Software environment information

        Args:
            indent (int): Number of spaces to inject as indentation
            verbosity (int): Verbosity level
            color_level (int): Nested level for coloring
            only_used (bool): Whether to only track used info (True) or all info (False)

        Returns:
            str: information of this environment
        """

        # Don't print if it is unused and we are only interested in used packages
        if only_used and not self.is_used:
            return ""

        out_str = ""
        if self._rendered_environments:
            for envs in self._rendered_environments.values():
                for env in envs.values():
                    out_str += env.info(
                        indent + SUB_INDENT,
                        verbosity,
                        color_level=color_level + 1,
                        only_used=only_used,
                    )
        elif not only_used:
            indentation = " " * (indent + SUB_INDENT)
            out_str += f"{indentation}No rendered environments\n"

        # If there are rendered environments, prepend the header
        if out_str != "" or not only_used:
            out_str = (
                super().info(indent, verbosity, color_level=color_level, only_used=only_used)
                + out_str
            )

        return out_str

    def __str__(self):
        """String representation of this environment

        Returns:
            str: String representation of this environment (none of its rendered environments)
        """

        return super().info()

    def render_environment(
        self,
        expander: Expander,
        all_package_templates: dict,
        all_packages: dict,
        package_manager,
    ):
        """Render a SoftwareEnvironment from this TemplateEnvironment

        Args:
            expander (ramble.expander.Expander): Expander object to use when rendering
            all_packages (dict): All package definitions
            package_manager: Package manager the environment is rendered with

        Returns:
            RenderedEnvironment: Reference to the rendered SoftwareEnvironment
        """
        name = expander.expand_var(self.name)
        pm_name = package_manager.name

        new_env = RenderedEnvironment(name, package_manager)
        new_env.auto_constructed = self.auto_constructed

        # Stores a mapping from rendered package name to template.
        # This helps with more efficient env package matching and
        # allows only matched packages to be fully rendered.
        name_to_template = {}
        for pkg_template in all_package_templates.values():
            rendered_name = expander.expand_var(pkg_template.name, merge_used_stage=False)
            if rendered_name:
                name_to_template[rendered_name] = pkg_template

        for env_pkg_template in self._package_names:
            rendered_env_pkg_name = expander.expand_var(env_pkg_template)
            if not rendered_env_pkg_name:
                continue
            matching_template = name_to_template.get(rendered_env_pkg_name)
            if matching_template is None:
                raise RambleSoftwareEnvironmentError(
                    f"Environment template {self.name} references "
                    f"undefined package {env_pkg_template} rendered to {rendered_env_pkg_name}"
                )
            expander.flush_used_variable_stage()
            rendered_pkg = matching_template.render_package(expander, package_manager)
            if rendered_pkg is not None:
                if rendered_pkg.spec is not None:
                    expander.merge_used_variable_stage()
                    if rendered_pkg.name in all_packages[pm_name]:
                        if rendered_pkg != all_packages[pm_name][rendered_pkg.name]:
                            raise RambleSoftwareEnvironmentError(
                                f"Environment {name} defined multiple "
                                "times in inconsistent ways.\n"
                                f"Package with differences is {rendered_pkg.name}"
                            )
                        rendered_pkg = all_packages[pm_name][rendered_pkg.name]
                    else:
                        all_packages[pm_name][rendered_pkg.name] = rendered_pkg
                matching_template.add_rendered_package(rendered_pkg, all_packages, pm_name)
                new_env.add_package(rendered_pkg)

        return new_env

    def add_rendered_environment(
        self,
        environment: RenderedEnvironment,
        all_environments: dict,
        all_packages: dict,
        pm_name: str,
    ):
        """Add a rendered environment to this template

        Args:
            environment (RenderedEnvironment): Reference to rendered environment
            all_environments (dict): Dictionary containing all environments
            all_packages (dict): Dictionary containing all packages
            pm_name (str): Name of the associated package manager
        """
        if environment.name not in self._rendered_environments[pm_name]:
            self._rendered_environments[pm_name][environment.name] = environment
            all_environments[pm_name][environment.name] = environment
            for template_pkg, rendered_pkg in zip(self._packages, environment._packages):
                if isinstance(rendered_pkg, RenderedPackage) and isinstance(
                    template_pkg, TemplatePackage
                ):
                    template_pkg.add_rendered_package(rendered_pkg, all_packages, pm_name)


class SoftwareEnvironments:
    """Class representing a group of software environments"""

    def __init__(self, workspace):
        """SoftwareEnvironments constructor

        Args:
            workspace (ramble.workspace.Workspace): Reference to workspace
                owning the software descriptions
        """

        self._workspace = workspace
        self._software_dict = copy.deepcopy(ramble.config.get(namespace.software))
        self._environment_templates = {}
        self._external_env_templates = {}
        self._package_templates = {}
        self._rendered_packages = defaultdict(dict)
        self._rendered_environments = defaultdict(dict)

        self._define_templates()

    def info(
        self, indent: int = 0, verbosity: int = 0, color_level: int = 0, only_used: bool = True
    ):
        """Information for all packages and environments

        Args:
            indent (int): Number of spaces to indent lines with
            verbosity (int): Verbosity level
            color_level (int): Nested level for coloring
            only_used (bool): Whether to only track used info (True) or all info (False)

        Returns:
            str: Representation of all packages and environments
        """
        out_str = ""
        for pkg in self._package_templates.values():
            out_str += pkg.info(
                indent, verbosity=verbosity, color_level=color_level, only_used=only_used
            )
        for env in self._environment_templates.values():
            out_str += env.info(
                indent, verbosity=verbosity, color_level=color_level, only_used=only_used
            )
        return out_str

    def use_environment(self, package_manager, env_name):
        """Mark an environment as used.

        Given a package manager object and the name of a rendered environment,
        mark the environment as used. This allows the info method to only print
        information about used packages and environments.

        Args:
            package_manager: Reference to a package manager object
            env_name (str): Name of the rendered environment to mark as used
        """

        pm_name = package_manager.spec_prefix
        if pm_name in self._rendered_environments:
            if env_name in self._rendered_environments[pm_name]:
                self._rendered_environments[pm_name][env_name].mark_used()

    def unused_environments(self):
        """Iterator over environment templates that do not have any rendered environments

        Yields:
            (TemplateEnvironment) Each unused template environment in this group
        """
        for env in self._environment_templates.values():
            if _is_dict_empty(env._rendered_environments):
                yield env

    def unused_packages(self):
        """Iterator over package templates that do not have any rendered packages

        Yields:
            (TemplatePackage) Each unused template package in this group
        """
        for pkg in self._package_templates.values():
            if _is_dict_empty(pkg._rendered_packages):
                yield pkg

    def __str__(self):
        """String representation of all packages and environments in this object

        Returns:
            str: Representation of all packages and environments
        """
        return self.info(indent=0)

    def _define_templates(self):
        """Process software dictionary to generate templates"""

        if namespace.packages in self._software_dict:
            for pkg_template, pkg_info in self._software_dict[namespace.packages].items():
                new_pkg = TemplatePackage(pkg_template, pkg_info)
                self._package_templates[pkg_template] = new_pkg

        if namespace.environments in self._software_dict:
            for env_template, env_info in self._software_dict[namespace.environments].items():
                if env_info.get(namespace.external_env):
                    # External environments are stored in a separate template dict, such that it
                    # still goes through the rendering to concretize on the package_manager used.
                    new_env = ExternalEnvironment(env_template, env_info[namespace.external_env])
                    self._external_env_templates[env_template] = new_env
                else:
                    # Define a new template environment
                    new_env = TemplateEnvironment(env_template)
                    if namespace.packages in env_info:
                        for package in env_info[namespace.packages]:
                            new_env.add_package_name(package)
                    self._environment_templates[env_template] = new_env

    def define_compiler_packages(self, environment: RenderedEnvironment, expander: Expander):
        """Define packages for compilers in this environment

        If compilers referenced by (environment) are not defined, create
        definitions for them to properly create compiler specs.

        Args:
            environment (RenderedEnvironment): Environment to extract necessary
                compilers from
            expander (ramble.expander.Expander): Expander object to use when
                constructing compiler package names
        """
        pm_name = environment.package_manager_name
        for pkg in environment._packages:
            if isinstance(pkg, RenderedPackage) and pkg.compiler:
                cur_compiler = pkg.compiler
                # Re-render compiler package to ensure variables are marked as used.
                if cur_compiler in self._rendered_packages[pm_name]:
                    for template_def in self._package_templates.values():
                        if cur_compiler in template_def._rendered_packages[pm_name]:
                            expander.flush_used_variable_stage()
                            rendered_pkg = template_def.render_package(
                                expander, environment.package_manager
                            )
                            expander.merge_used_variable_stage()

                while cur_compiler and cur_compiler not in self._rendered_packages[pm_name]:
                    added = False
                    for template_name, template_def in self._package_templates.items():
                        expander.flush_used_variable_stage()
                        rendered_name = expander.expand_var(template_name, merge_used_stage=False)

                        if rendered_name == cur_compiler:
                            rendered_pkg = template_def.render_package(
                                expander, environment.package_manager
                            )
                            expander.merge_used_variable_stage()

                            if (
                                cur_compiler in self._rendered_packages[pm_name]
                                and rendered_pkg != self._rendered_packages[pm_name][cur_compiler]
                            ):
                                raise RambleSoftwareEnvironmentError(
                                    f"Package {rendered_pkg.name} defined "
                                    "multiple times in inconsistent ways"
                                )
                            added = True
                            template_def.add_rendered_package(
                                rendered_pkg, self._rendered_packages, pm_name
                            )
                            self._rendered_packages[pm_name][rendered_pkg.name] = rendered_pkg

                            if rendered_pkg.compiler:
                                cur_compiler = rendered_pkg.compiler

                    if not added:
                        raise RambleSoftwareEnvironmentError(
                            f"Compiler {pkg.compiler} used, but not "
                            f"defined in environment {environment.name} "
                            f"by package {pkg.name}"
                        )

    def compiler_specs_for_environment(self, environment: RenderedEnvironment):
        """Iterator over compiler specs for a given environment

        Assumes all compilers have been defined via
        self.define_compiler_packages()

        Args:
            environment (SoftwareEnvironment): Environment to extract compiler specs for

        Yields:
            (str) Package spec string for each compiler
            (str) Compiler spec string for each compiler
        """

        root_compilers = []
        pm_name = environment.package_manager_name
        for pkg in environment._packages:
            if isinstance(pkg, RenderedPackage) and pkg.compiler:
                if pkg.compiler not in self._rendered_packages[pm_name]:
                    raise RambleSoftwareEnvironmentError(
                        f"Compiler {pkg.compiler} used, but not "
                        f"defined in environment {environment.name} "
                        f"by package {pkg.name}"
                    )

                root_compilers.append(pkg.compiler)

        dep_compilers = []
        for comp in root_compilers:
            comp_pkg = self._rendered_packages[pm_name][comp]

            if isinstance(comp_pkg, RenderedPackage) and comp_pkg.compiler:
                cur_compiler = comp_pkg.compiler

                while cur_compiler and cur_compiler not in dep_compilers:
                    dep_compilers.append(cur_compiler)
                    if isinstance(comp_pkg, RenderedPackage) and comp_pkg.compiler:
                        cur_compiler = self._rendered_packages[pm_name][comp_pkg.compiler].name

        for comp in reversed(root_compilers + dep_compilers):
            comp_pkg = self._rendered_packages[pm_name][comp]
            yield comp_pkg.spec_str(
                all_packages=self._rendered_packages, compiler=False
            ), comp_pkg.spec_str(all_packages=self._rendered_packages, compiler=True)

    def package_specs_for_environment(self, environment: SoftwareEnvironment):
        """Iterator over package specs for a given environment

        Assumes all compilers have been defined via
        self.define_compiler_packages()

        Args:
            environment (SoftwareEnvironment): Environment to extract package specs for

        Yields:
            (str) Spec string for each package
        """

        for pkg in environment._packages:
            yield pkg.spec_str(all_packages=self._rendered_packages, compiler=False)

    def add_spec_to_environment(
        self,
        environment: SoftwareEnvironment,
        spec: SoftwareSpec,
        expander: Expander,
        package_manager,
    ):
        """Add a spec to a given environment

        Creates a new template / rendered package (if needed) from the input spec,
        and adds to the template and rendered environment as a package in the environment.

        Args:
            environment (SoftwareEnvironment): Rendered environment to add package to
            spec (ramble.util.spec_utils.SoftwareSpec): Software spec to add to environment
            expander (ramble.expander.Expander): Experiment's expander object,
                                                 to render package / environment with
            package_manager: Package manager from the experiment
        """

        pm_name = package_manager.spec_prefix

        if spec.name not in self._package_templates:
            template_package = TemplatePackage(spec.name, spec.to_dict())

            self._package_templates[spec.name] = template_package

        template_package = self._package_templates[spec.name]

        rendered_package = template_package.render_package(expander, package_manager)
        rendered_package.injected = True

        if rendered_package.name not in self._rendered_packages:
            template_package.add_rendered_package(
                rendered_package, self._rendered_packages, pm_name
            )

        environment.add_package(rendered_package)

    def _check_environment(self, environment):
        """Check an environment for common issues

        Args:
            environment (SoftwareEnvironment): Environment to check for issues in
        """

        pkg_names = set()

        for pkg in environment._packages:
            pkg_names.add(pkg.name)

        used_compilers = set()
        compiler_warnings = [
            (pkg.name, pkg.compiler)
            for pkg in environment._packages
            if isinstance(pkg, RenderedPackage) and pkg.compiler and pkg.compiler in pkg_names
        ]

        logger.debug(f" Used compilers: {used_compilers}")
        logger.debug(f" Compiler warnings: {compiler_warnings}")
        if compiler_warnings:
            logger.warn(
                f"Environment {environment.name} contains packages and their "
                "compilers in the package list. These include:"
            )
            for pkg_name, comp_name in compiler_warnings:
                logger.warn(f"    Package: {pkg_name}, Compiler: {comp_name}")
            logger.warn("This might cause problems when installing the packages.")

    def render_environment(self, env_name: str, expander: Expander, package_manager, require=True):
        """Render an environment needed by an experiment

        Args:
            env_name (str): Name of environment needed by the experiment
            expander (ramble.expander.Expander): Expander object from the experiment
            package_manager: Package manager the environment is rendered with

        Returns:
            ramble.software_environments.SoftwareEnvironment: Reference to software environment
            for the experiment
        """

        pm_name = package_manager.name
        # Invoke render with the null package_manager is a programming error
        if not pm_name:
            raise RambleSoftwareEnvironmentError(
                "`render_environment` expects a non-null package manager"
            )

        # Check for an external environment before checking templates that need to be rendered
        if env_name in self._external_env_templates:
            ext_env_tmpl = self._external_env_templates[env_name]
            ext_env_spec = expander.expand_var(ext_env_tmpl.external_env)
            rendered_ext_env = RenderedExternalEnvironment(env_name, ext_env_spec, package_manager)
            self._rendered_environments[pm_name][env_name] = rendered_ext_env
            return rendered_ext_env

        for template_name, template_def in self._environment_templates.items():
            expander.flush_used_variable_stage()
            rendered_name = expander.expand_var(template_name, merge_used_stage=False)
            if rendered_name == env_name:
                expander.merge_used_variable_stage()
                rendered_env = template_def.render_environment(
                    expander, self._package_templates, self._rendered_packages, package_manager
                )

                if rendered_env.name == env_name:
                    if env_name in self._rendered_environments[pm_name]:
                        if rendered_env != self._rendered_environments[pm_name][env_name]:
                            error_string = f"Old environment: {env_name}\n"
                            error_string += "  Packages:\n"
                            for pkg in self._rendered_environments[pm_name][env_name]._packages:
                                error_string += f"  - {pkg.name}\n"
                            error_string += f"New environment: {rendered_env.name}\n"
                            error_string += "  Packages:\n"
                            for pkg in rendered_env._packages:
                                error_string += f"  - {pkg.name}\n"

                            raise RambleSoftwareEnvironmentError(
                                f"Environment {env_name} defined multiple times "
                                "in inconsistent ways.\n" + error_string
                            )
                        rendered_env = self._rendered_environments[pm_name][env_name]

                    template_def.add_rendered_environment(
                        rendered_env, self._rendered_environments, self._rendered_packages, pm_name
                    )
                    self.define_compiler_packages(rendered_env, expander)
                    self._check_environment(rendered_env)
                    return rendered_env

        if require:
            new_env_tmpl = TemplateEnvironment(env_name)
            new_env_tmpl.auto_constructed = True
            self._environment_templates[env_name] = new_env_tmpl
            expander.flush_used_variable_stage()
            expander.merge_used_variable_stage()
            rendered_env = new_env_tmpl.render_environment(
                expander, self._package_templates, self._rendered_packages, package_manager
            )
            new_env_tmpl.add_rendered_environment(
                rendered_env, self._rendered_environments, self._rendered_packages, pm_name
            )
            self.define_compiler_packages(rendered_env, expander)
            self._check_environment(rendered_env)
            return rendered_env
        return None

    def check_all_environments(self):
        """Check all rendered environments for issues after they have been fully set up"""
        for pm_name, envs in self._rendered_environments.items():
            for env in envs.values():
                if getattr(env, "auto_constructed", False) and len(env._packages) == 0:
                    logger.warn(
                        f"Software environment '{env.name}' was auto-constructed "
                        f"for package manager '{pm_name}' and contains no packages. "
                        "If this was not intended, please define the environment "
                        "or packages in your configuration."
                    )


class RambleSoftwareEnvironmentError(ramble.error.RambleError):
    """Super class for all software environment errors"""
