# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.language.application_language
import ramble.language.shared_language
from ramble.appkit import ExecutableApplication
from ramble.language.language_base import _UNSET, DirectiveError


def test_lazy_directive_evaluation():
    """Verify that directives are not evaluated until attributes are accessed."""

    class LazyTestApp(metaclass=ramble.language.application_language.ApplicationMeta):
        name = "lazy_test_app"
        __module__ = "ramble.app"

        ramble.language.shared_language.tags("tag1", "tag2")
        ramble.language.application_language.workload("test_wl", executables=["exe1"])

    assert LazyTestApp._workloads is _UNSET
    assert LazyTestApp._tags is _UNSET

    wl = LazyTestApp.workloads
    assert LazyTestApp._workloads is not _UNSET
    assert frozenset() in wl
    assert "test_wl" in wl[frozenset()]

    tags = LazyTestApp.tags
    assert LazyTestApp._tags is not _UNSET
    assert "tag1" in tags
    assert "tag2" in tags


def test_lazy_directive_inheritance_and_mro():
    """Verify inheritance and MRO order when directives are executed lazily."""

    class ParentApp(metaclass=ramble.language.application_language.ApplicationMeta):
        name = "parent_app"
        __module__ = "ramble.app"

        ramble.language.application_language.workload("parent_wl", executables=["p_exe"])
        ramble.language.shared_language.maintainers("parent_user")

    class ChildApp(ParentApp):
        name = "child_app"
        __module__ = "ramble.app"

        ramble.language.application_language.workload("child_wl", executables=["c_exe"])
        ramble.language.shared_language.maintainers("child_user")

    assert ChildApp._workloads is _UNSET
    assert ChildApp._maintainers is _UNSET

    child_wls = ChildApp.workloads
    assert frozenset() in child_wls
    assert "parent_wl" in child_wls[frozenset()]
    assert "child_wl" in child_wls[frozenset()]

    child_maintainers = ChildApp.maintainers
    assert "parent_user" in child_maintainers
    assert "child_user" in child_maintainers


def test_instance_attribute_isolation():
    """Verify copy-on-first-access isolates instance attributes from class descriptors."""

    class IsolatedApp(metaclass=ramble.language.application_language.ApplicationMeta):
        name = "isolated_app"
        __module__ = "ramble.app"

        ramble.language.application_language.workload("base_wl", executables=["base_exe"])

    inst = IsolatedApp()
    inst2 = IsolatedApp()

    assert "workloads" not in inst.__dict__
    assert "workloads" not in inst2.__dict__
    assert IsolatedApp._workloads is _UNSET

    inst_wl = inst.workloads
    assert "workloads" in inst.__dict__
    assert "workloads" not in inst2.__dict__
    assert "base_wl" in inst_wl[frozenset()]

    inst.workloads[frozenset()]["inst_wl"] = {"executables": ["inst_exe"]}

    assert "inst_wl" not in IsolatedApp.workloads[frozenset()]
    assert "base_wl" in IsolatedApp.workloads[frozenset()]
    assert "inst_wl" in inst.workloads[frozenset()]
    assert "inst_wl" not in inst2.workloads[frozenset()]


def test_graph_closure_multi_dict_execution():
    """Verify that accessing one dictionary triggers all co-dependent directives."""

    class MultiDictApp(metaclass=ramble.language.application_language.ApplicationMeta):
        name = "multi_dict_app"
        __module__ = "ramble.app"

        ramble.language.shared_language.edit_file(
            name="patch_cfg",
            file_path="config.txt",
            match="FOO",
            replace="BAR",
        )

    assert MultiDictApp._executables is _UNSET
    assert MultiDictApp._custom_edit_functions is _UNSET

    exes = MultiDictApp.executables
    assert frozenset() in exes
    assert "patch_cfg" in exes[frozenset()]
    assert MultiDictApp._custom_edit_functions is not _UNSET


def test_modifier_lazy_directives():
    """Verify lazy evaluation of modifier-specific directives."""
    import ramble.language.modifier_language

    class LazyMod(metaclass=ramble.language.modifier_language.ModifierMeta):
        name = "lazy_mod"
        __module__ = "ramble.mod"

        ramble.language.modifier_language.mode("opt", description="Optimized mode")
        ramble.language.modifier_language.default_mode("opt")
        ramble.language.modifier_language.modifier_variable(
            "threads", default="4", description="Thread count"
        )

    assert LazyMod._modes is _UNSET
    assert LazyMod._default_usage_mode is _UNSET
    assert LazyMod._object_variables is _UNSET

    modes = LazyMod.modes
    assert "opt" in modes
    assert LazyMod.default_usage_mode == "opt"

    vars_dict = LazyMod.object_variables
    assert frozenset() in vars_dict
    assert "threads" in [v.name for v in vars_dict[frozenset()]]


def test_system_lazy_directives():
    """Verify lazy evaluation of system-specific directives."""
    import ramble.language.system_language

    class LazySys(metaclass=ramble.language.system_language.SystemMeta):
        name = "lazy_sys"
        __module__ = "ramble.sys"

        ramble.language.system_language.default_platform("x86_64")
        ramble.language.system_language.available_platforms(["x86_64", "arm64"])
        ramble.language.system_language.variable_defaults({"n_ranks": "16"})

    assert LazySys._system_default_platform is _UNSET
    assert LazySys._system_available_platforms is _UNSET
    assert LazySys._variable_defaults is _UNSET

    assert LazySys.system_default_platform == "x86_64"
    assert "arm64" in LazySys.system_available_platforms
    assert frozenset() in LazySys.variable_defaults
    assert LazySys.variable_defaults[frozenset()]["n_ranks"] == "16"


def test_dynamic_instance_directive_execution():
    """Verify dynamic invocation of directive methods on instances."""

    class DynamicApp(metaclass=ramble.language.application_language.ApplicationMeta):
        name = "dynamic_app"
        __module__ = "ramble.app"
        _language_types = ["application", "shared"]
        _language_classes = _language_types

        ramble.language.application_language.workload("static_wl", executables=["static_exe"])

    inst = DynamicApp()

    inst.workload("dynamic_wl", executables=["dynamic_exe"])

    assert "dynamic_wl" in inst.workloads[frozenset()]
    assert "dynamic_wl" not in DynamicApp.workloads[frozenset()]


def test_application_clone_preserves_evaluated_directives(mutable_mock_apps_repo):
    """Verify application clone preserves evaluated and dynamically added directives."""
    app = mutable_mock_apps_repo.get("basic")
    app.set_variables_and_variants({"workload_name": "test_wl"}, {}, None, None)
    app.workload("dyn_wl", executables=["dyn_exe"])

    assert "dyn_wl" in app.workloads[frozenset()]

    clone = app.clone()

    assert "dyn_wl" in clone.workloads[frozenset()]
    assert "archive_patterns" not in clone.__dict__


def test_generic_object_copy_preserves_evaluated_directives(mutable_mock_mods_repo):
    """Verify generic Ramble object copy (e.g. modifier) preserves evaluated directives."""
    mod = mutable_mock_mods_repo.get("spack-mod")
    _ = mod.modes
    assert "modes" in mod.__dict__

    mod_copy = mod.copy()
    assert "modes" in mod_copy.__dict__
    assert mod_copy.modes == mod.modes
    assert "env_var_modifications" not in mod_copy.__dict__


def test_subclass_directive_evaluation_when_parent_already_evaluated():
    """Verify that evaluating parent directives first does not prevent subclass evaluation."""

    class ParentApp(metaclass=ramble.language.application_language.ApplicationMeta):
        name = "parent_eval_app"
        __module__ = "ramble.app"
        _language_types = ["application", "shared"]
        ramble.language.application_language.workload("parent_wl", executables=["p_exe"])

    class ChildApp(ParentApp):
        name = "child_eval_app"
        __module__ = "ramble.app"
        _language_types = ["application", "shared"]
        ramble.language.application_language.workload("child_wl", executables=["c_exe"])

    parent_wls = ParentApp.workloads
    assert "parent_wl" in parent_wls[frozenset()]
    assert "child_wl" not in parent_wls[frozenset()]

    child_wls = ChildApp.workloads
    assert "parent_wl" in child_wls[frozenset()]
    assert "child_wl" in child_wls[frozenset()]


def test_subclass_preferred_version_override():
    """Verify that a subclass can override the parent's preferred version."""

    class ParentVerApp(ExecutableApplication):
        name = "parent_ver_app"
        __module__ = "ramble.app"
        ramble.language.shared_language.version("1.0", preferred=True)

    class ChildVerApp(ParentVerApp):
        name = "child_ver_app"
        __module__ = "ramble.app"
        ramble.language.shared_language.version("2.0", preferred=True)

    assert str(ParentVerApp.preferred_version.version) == "1.0"
    assert str(ChildVerApp.preferred_version.version) == "2.0"

    with pytest.raises(DirectiveError, match="already has a preferred version"):

        class ConflictVerApp(ExecutableApplication):
            name = "conflict_ver_app"
            __module__ = "ramble.app"
            ramble.language.shared_language.version("1.0", preferred=True)
            ramble.language.shared_language.version("2.0", preferred=True)

        _ = ConflictVerApp.preferred_version
