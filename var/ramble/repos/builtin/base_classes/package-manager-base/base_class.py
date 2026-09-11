# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
"""Define base classes for package manager definitions"""

import abc
import os
import tempfile
from typing import List

import ramble.definitions.families
import ramble.repository
from ramble.language.language_base import DirectiveMeta
from ramble.language.shared_language import register_phase
from ramble.software_environments import (
    RambleSoftwareEnvironmentError,
    TemplatePackage,
)
from ramble.util.logger import logger
from ramble.util.naming import NS_SEPARATOR

ObjectMixin = ramble.repository.get_base_class("object-mixin")


class PackageManagerBase(ObjectMixin, metaclass=DirectiveMeta):
    origin_type = "package_manager"
    _builtin_name = NS_SEPARATOR.join(
        ("package_manager_builtin", "{obj_name}", "{name}")
    )
    _language_types = ["package_manager", "shared"]
    _language_classes = _language_types
    pipelines = [
        "analyze",
        "archive",
        "mirror",
        "setup",
        "pushdeployment",
        "pushtocache",
        "execute",
        "logs",
    ]

    _spec_groups = [
        ("compilers", "Compilers"),
        ("software_specs", "Software Specs"),
    ]

    _spec_prefix = ""

    package_manager_class = "PackageManagerBase"
    requires_software_environment = True

    def __init__(self, file_path):
        super().__init__()

        self.object_variants = ramble.variants.VariantSet()
        for var_args in self.class_variants.values():
            self.object_variants.default_variant(**var_args)

        if getattr(self, "families", None) is None:
            self.families = ramble.definitions.families.Families(
                self.origin_type, list(self.class_families)
            )

        self._file_path = file_path

        self.app_inst = None
        self.keywords = None

        self._allow_unprefixed_specs = True

        self.object_variants.default_variant(
            self.origin_type,
            default=self.name,
            description="Name of package manager for an experiment",
        )

        for family in self.families:
            self.object_variants.multi_value_variant(
                self.families.family_type,
                value=family,
            )

        self.output_prefix = self.name

    @property
    def runner(self):
        # Turn `runner` into a property for delayed init
        return None

    @property
    def allow_unprefixed_specs(self):
        return self._allow_unprefixed_specs

    def package_manager_dir(self, workspace):
        """Get the path to the package manager's software environment directory

        Args:
            workspace (ramble.workspace.Workspace): Reference to workspace that
                owns a software directory

        Returns:
            (str) Path to package manager directory within workspace's software directory

        """
        return os.path.join(workspace.software_dir, self.name)

    @property
    def environment_required(self):
        app_inst = self.app_inst
        if not hasattr(app_inst, "software_specs"):
            return False

        return any(
            self.app_inst.expander.satisfies(
                info.when, variant_set=self.experiment_variants()
            )
            for definitions in app_inst.software_specs.values()
            for info in definitions
        )

    def get_spec_str(self, pkg, all_pkgs, compiler):
        """Return a spec string for the given pkg

        Can be overridden by individual package managers to provide a more
        specific package spec string. Default is to just return the detected
        package spec.

        Args:
            pkg (ramble.software_environments.RenderedPackage): Reference to a rendered package
            all_pkgs (dict): All related packages
            compiler (bool): True if this pkg is used as a compiler
        """
        return pkg.spec

    @property
    def spec_prefix(self):
        """Return this package manager's spec prefix

        Returns:
            (str): Prefix for this package manager's specs
        """
        prefix = self._spec_prefix or self.name
        return prefix.replace("-", "_")

    def set_application(self, app_inst):
        """Add an internal reference to the application instance this package
        manager instance is attached to.

        Args:
            app_inst: The experiment this package manager will act on.
        """
        self.app_inst = app_inst
        self.keywords = app_inst.keywords
        self.clear_variant_cache()

    def build_used_variables(self):
        """Build a set of all used variables

        By expanding all necessary portions of this experiment (required /
        reserved keywords, templates, commands, etc...), determine which
        variables are used throughout the experiment definition.

        Variables can have list definitions. These are iterated over to ensure
        variables referenced by any of them are tracked properly.

        Returns:
            (set): All variable names used by this experiment.
        """
        workspace = self.app_inst.workspace
        app_context = self.app_inst.expander.expand_var_name(
            self.keywords.env_name
        )

        software_environments = workspace.software_environments
        if software_environments is not None:
            software_env = software_environments.render_environment(
                app_context, self.app_inst.expander, self, require=False
            )
            if software_env is not None:
                software_environments.define_compiler_packages(
                    software_env, self.app_inst.expander
                )

            for _, contents in workspace.all_auxiliary_software_files():
                self.app_inst.expander.expand_var(contents)

        return self.app_inst.expander._used_variables

    def populate_inventory(self, workspace, force_compute=False) -> bool:
        """Stub class method for populating an experiment inventory.
        Specific package managers should implement this to convey inventory
        information to the workspace / experiment.

        Args:
            workspace (ramble.workspace.Workspace): Reference to the workspace that is currently
                                   being acted on.
            force_compute (bool): Whether to force computation of hashes or not
            require_exist (bool): Whether to require environment hashes exist or not.
        """

    def define_missing_packages(self, workspace):
        """Injection of missing packages that are auto-injected by objects

        This method will iterate over the objects in an experiment, and
        inject any missing packages that are defined as `inject_if_missing`
        from their software_spec directives.

        Args:
            workspace (Workspace): The workspace that contains the software environments
        """

        require_env = self.environment_required
        software_envs = workspace.software_environments

        if not software_envs:
            return

        # Inject any missing, but injected compilers
        for _, obj in self.app_inst.objects():
            for comps in obj.compilers.values():
                for comp in comps:
                    if (
                        comp.inject_if_missing
                        and comp.name not in software_envs._package_templates
                        and self.satisfy_when(
                            comp.when,
                            variant_set=obj.experiment_variants(),
                        )
                    ):
                        comp_template = TemplatePackage(
                            comp.name, comp.to_dict()
                        )
                        software_envs._package_templates[comp.name] = (
                            comp_template
                        )

        app_context = self.app_inst.expander.expand_var_name(
            self.keywords.env_name
        )
        try:
            software_env = software_envs.render_environment(
                app_context, self.app_inst.expander, self, require=require_env
            )

            # If there is no environment required or defined, skip defining
            # packages.
            if not require_env and software_env is None:
                return

            env_packages = set()
            for pkg_spec in software_envs.package_specs_for_environment(
                software_env
            ):
                if pkg_spec:
                    pkg_name = self.package_name_from_spec(pkg_spec)
                    if pkg_name:
                        env_packages.add(pkg_name)

            for _, obj in self.app_inst.objects():
                required_compilers = set()
                # Inject any specs that need to be injected.
                for specs in obj.software_specs.values():
                    for spec in specs:
                        pkg_name = None
                        if spec.pkg_spec:
                            pkg_name = self.package_name_from_spec(
                                spec.pkg_spec
                            )

                        if (
                            spec.inject_if_missing
                            and pkg_name
                            and pkg_name not in env_packages
                            and self.app_inst.expander.satisfies(
                                spec.when,
                                variant_set=obj.experiment_variants(),
                            )
                        ):
                            env_packages.add(pkg_name)
                            new_spec = spec.copy()
                            software_envs.add_spec_to_environment(
                                software_env,
                                new_spec,
                                self.app_inst.expander,
                                self,
                            )

                            if new_spec.compiler is not None:
                                required_compilers.add(new_spec.compiler)

                # Inject any dependent compilers
                pm_name = self.spec_prefix
                compilers_to_define = required_compilers.copy()
                for compiler in required_compilers:
                    rendered_compiler = self.app_inst.expander.expand_var(
                        compiler
                    )
                    if (
                        compiler in software_envs._package_templates
                        or rendered_compiler
                        in software_envs._rendered_packages[pm_name]
                    ):
                        compilers_to_define.remove(compiler)

                for compiler in compilers_to_define:
                    rendered_compiler = self.app_inst.expander.expand_var(
                        compiler
                    )

                    compiler_name = None
                    if compiler in obj.compilers:
                        compiler_name = compiler
                    elif rendered_compiler in obj.compilers:
                        compiler_name = rendered_compiler

                    if compiler_name is None:
                        logger.die(
                            f"When injecting packages from {obj.origin_type} "
                            f"{obj.name}, compiler {compiler} (rendered to "
                            f"{rendered_compiler}) is not defined."
                        )

                    for compiler_spec in obj.compilers[compiler_name]:
                        if self.app_inst.expander.satisfies(
                            compiler_spec.when,
                            variant_set=obj.experiment_variants(),
                        ):
                            compiler_template = TemplatePackage(
                                compiler_name, compiler_spec.to_dict()
                            )

                            software_envs._package_templates[compiler_name] = (
                                compiler_template
                            )
                            rendered_compiler = (
                                compiler_template.render_package(
                                    self.app_inst.expander, self
                                )
                            )
        except RambleSoftwareEnvironmentError:
            pass

    def merge_software_file(self, existing_file: str, new_file: str):
        """Stub to for package managers to implement merging of software files

        Args:
            existing_file: Path to existing file to merge into
            new_file: Path to new file to merge
        """
        logger.warn(
            f"When trying to merge into {existing_file} "
            f"merge_software_file is not implemented in {self.origin_type} {self.name}"
        )

    def render_object_auxiliary_software_files(
        self, workspace, app_inst=None, stage_path=None
    ):
        """Render auxiliary software files from system objects

        Uses package manager implemented `merge_software_file` method to handle conflicts.
        """
        if app_inst is None:
            return

        env_path = stage_path if stage_path else app_inst.expander.env_path

        for obj_type, obj in app_inst.objects():
            include_modifier = None
            if obj_type == ramble.repository.ObjectTypes.modifiers:
                include_modifier = obj

            obj_variants = self.experiment_variants(
                include_modifier=include_modifier, allow_caching=False
            )

            aux_files = getattr(obj, "auxiliary_software_files", {})
            for when_set, files_info in aux_files.items():
                if app_inst.expander.satisfies(
                    when_set, variant_set=obj_variants
                ):
                    for name, file_info in files_info.items():
                        src_path = app_inst.expander.expand_var(
                            file_info["src_path"]
                        )
                        dest_path = app_inst.expander.expand_var(
                            file_info["dest_path"]
                        )
                        file_info["consumed"] = True

                        if not os.path.isabs(src_path):
                            # Find source file relative to the system object
                            object_paths = [
                                e[1]
                                for e in ramble.repository.list_object_files(
                                    obj, obj_type
                                )
                            ]
                            for obj_path in object_paths:
                                test_path = os.path.join(
                                    os.path.dirname(obj_path), src_path
                                )
                                if os.path.isfile(test_path):
                                    src_path = test_path
                                    break

                        logger.msg(
                            f"Rendering auxiliary software file {name} to {dest_path}"
                        )
                        content = workspace.read_file_content(src_path)
                        rendered = app_inst.expander.expand_var(content)

                        if not os.path.isabs(dest_path):
                            dest_path = os.path.join(env_path, dest_path)

                        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                        # Python 3.12 and newer can pass `delete=False` for debugging
                        with tempfile.TemporaryDirectory() as tmpdir:
                            dest_name = os.path.basename(dest_path)
                            temp_path = os.path.join(str(tmpdir), dest_name)
                            with open(temp_path, "w+", encoding="utf-8") as f:
                                f.write(rendered)
                            self.merge_software_file(dest_path, temp_path)

        # Write auxiliary software files into created spack env.
        for name, contents in workspace.all_auxiliary_software_files():
            aux_file_path = app_inst.expander.expand_var(
                os.path.join(
                    env_path,
                    f"{name}",
                )
            )

            rendered = app_inst.expander.expand_var(contents)
            with tempfile.TemporaryDirectory() as tmpdir:
                dest_name = os.path.basename(aux_file_path)
                temp_path = os.path.join(str(tmpdir), dest_name)
                with open(temp_path, "w+", encoding="utf-8") as f:
                    f.write(rendered)
                self.merge_software_file(aux_file_path, str(temp_path))

    register_phase(
        "check_auxiliary_software_files",
        pipeline="setup",
        run_after=["make_experiments"],
    )

    def _check_auxiliary_software_files(self, workspace, app_inst=None):
        """Ensure all registered auxiliary software files are consumed.

        Prints warnings on any auxiliary software file that was not consumed to
        help users / developers know if a package manager handled files
        correctly.
        """
        if app_inst is None:
            return

        for obj_type, obj in app_inst.objects():
            include_modifier = None
            if obj_type == ramble.repository.ObjectTypes.modifiers:
                include_modifier = obj

            obj_variants = self.experiment_variants(
                include_modifier=include_modifier,
                allow_caching=False,
                app_inst=app_inst,
            )

            aux_files = getattr(obj, "auxiliary_software_files", {})
            for when_set, files_info in aux_files.items():
                if app_inst.expander.satisfies(
                    when_set, variant_set=obj_variants
                ):
                    for name, file_info in files_info.items():
                        if not file_info["consumed"]:
                            logger.warn(
                                f"Package manager {self.name} did not consume auxiliary software file\n"
                                f"{name} from {obj.origin_type} {obj.name}"
                            )

    register_phase(
        "add_software_to_results",
        pipeline="analyze",
        run_after=["analyze_experiments"],
        run_before=["append_results_to_workspace"],
    )

    def _add_software_to_results(self, workspace, app_inst=None):
        """Stub class method for injecting software information into results

        Args:
            workspace (ramble.workspace.Workspace): Reference to the workspace
                that is currently being acted on.
            app_inst: Reference to the application instance that owns the results.

        """
        if app_inst.result is None:
            return
        prov_cache = workspace.pkg_prov_cache
        env_name = self.app_inst.expander.expand_var_name(
            self.keywords.env_name
        )
        if env_name in prov_cache[self.name]:
            # No copy done as this shouldn't be modified once written
            pkg_list = prov_cache[self.name][env_name]
        else:
            pkg_list = self.get_package_list(workspace)
            prov_cache[self.name][env_name] = pkg_list
        self.app_inst.result.software[self.output_prefix] = pkg_list

    # Methods that need to be defined by every derived package manager
    @abc.abstractmethod
    def get_package_list(self, workspace):
        """Method used by add_software_to_results phase to get software provenance info"""

    @abc.abstractmethod
    def package_name_from_spec(self, spec: str) -> str:
        """Stub method for extracting a package name
        from a spec object"""

    @abc.abstractmethod
    def environment_load_commands(self) -> List[str]:
        """Stub method for acquiring the commands to load
        an experiment's execution environment"""

    @abc.abstractmethod
    def environment_unload_commands(self) -> List[str]:
        """Stub method for acquiring the commands to unload an
        experiment's execution environment"""

    def _extract_specs(
        self, attr_name="software_specs", app_inst=None, prefixed=False
    ):
        specs = {}
        for obj_type, obj in app_inst.objects():
            include_modifier = None
            if obj_type == ramble.repository.ObjectTypes.modifiers:
                include_modifier = obj
            spec_variants = self.experiment_variants(
                include_modifier=include_modifier, allow_caching=False
            )

            software_dict = getattr(obj, attr_name, {})
            for name, definitions in software_dict.items():
                for info in definitions:
                    if app_inst.expander.satisfies(
                        info.when, variant_set=spec_variants
                    ):
                        if name not in specs:
                            specs[name] = []

                        new_info = info.copy()
                        if prefixed:
                            new_info.prefix = self._spec_prefix

                        specs[name].append(new_info)
        return specs

    def get_experiment_specs(self, app_inst=None, prefixed=False):
        if app_inst is None:
            return {}
        return self._extract_specs(
            attr_name="software_specs", app_inst=app_inst, prefixed=prefixed
        )

    def get_experiment_compilers(self, app_inst=None, prefixed=False):
        if app_inst is None:
            return {}
        return self._extract_specs(
            attr_name="compilers", app_inst=app_inst, prefixed=prefixed
        )
