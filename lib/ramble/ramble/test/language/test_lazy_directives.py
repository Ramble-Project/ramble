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
from ramble.language.language_base import _UNSET, DirectiveError, DirectiveMeta


@pytest.fixture(autouse=True)
def isolate_directive_registry():
    """Snapshot and restore DirectiveMeta global registries around each test."""
    import ramble.language.application_language  # noqa: F401
    import ramble.language.modifier_language  # noqa: F401
    import ramble.language.package_manager_language  # noqa: F401
    import ramble.language.platform_language  # noqa: F401
    import ramble.language.shared_language  # noqa: F401
    import ramble.language.system_language  # noqa: F401
    import ramble.language.utility_language  # noqa: F401
    import ramble.language.workflow_manager_language  # noqa: F401

    saved_dict_names = set(DirectiveMeta._directive_dict_names)
    saved_init_values = dict(DirectiveMeta._directive_init_values)
    saved_to_dicts = dict(DirectiveMeta._directive_to_dicts)
    saved_dict_to_dirs = {k: list(v) for k, v in DirectiveMeta._dict_to_directives.items()}
    saved_functions = dict(DirectiveMeta._directive_functions)
    saved_classes = dict(DirectiveMeta._directive_classes)
    saved_types = dict(DirectiveMeta._directive_types)
    saved_type_scoped = {k: set(v) for k, v in DirectiveMeta._type_scoped_dicts.items()}
    saved_shared = set(DirectiveMeta._shared_dict_names)
    saved_descriptor_cache = dict(DirectiveMeta._descriptor_cache)

    yield

    DirectiveMeta._directive_dict_names.clear()
    DirectiveMeta._directive_dict_names.update(saved_dict_names)
    DirectiveMeta._directive_init_values.clear()
    DirectiveMeta._directive_init_values.update(saved_init_values)
    DirectiveMeta._directive_to_dicts.clear()
    DirectiveMeta._directive_to_dicts.update(saved_to_dicts)
    DirectiveMeta._dict_to_directives.clear()
    for k, v in saved_dict_to_dirs.items():
        DirectiveMeta._dict_to_directives[k] = v
    DirectiveMeta._directive_functions.clear()
    DirectiveMeta._directive_functions.update(saved_functions)
    DirectiveMeta._directive_classes.clear()
    DirectiveMeta._directive_classes.update(saved_classes)
    DirectiveMeta._directive_types.clear()
    DirectiveMeta._directive_types.update(saved_types)
    DirectiveMeta._type_scoped_dicts.clear()
    for k, v in saved_type_scoped.items():
        DirectiveMeta._type_scoped_dicts[k] = v
    DirectiveMeta._shared_dict_names.clear()
    DirectiveMeta._shared_dict_names.update(saved_shared)
    DirectiveMeta._descriptor_cache.clear()
    DirectiveMeta._descriptor_cache.update(saved_descriptor_cache)
    DirectiveMeta._execution_plan_cache.clear()


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


def test_class_level_attribute_preservation():
    """Verify that class-level attributes matching directive names are preserved."""

    class ClassAttrApp(metaclass=ramble.language.application_language.ApplicationMeta):
        name = "class_attr_app"
        __module__ = "ramble.app"
        maintainers = ["alice", "bob"]
        tags = ["tag_custom"]

    assert ClassAttrApp.maintainers == ["alice", "bob"]
    assert ClassAttrApp.tags == ["tag_custom"]


def test_instance_preferred_version_preservation_on_clone(mutable_mock_apps_repo):
    """Verify that setting preferred_version on an instance is preserved across clone."""
    import spack.version

    app = mutable_mock_apps_repo.get("basic")
    app.set_variables_and_variants({"workload_name": "test_wl"}, {}, None, None)

    class CustomVer:
        version = spack.version.Version("99.99")

    app.preferred_version = CustomVer()
    assert str(app.preferred_version.version) == "99.99"

    clone = app.clone()
    assert clone.preferred_version is not None
    assert str(clone.preferred_version.version) == "99.99"


def test_family_directive_single_execution():
    """Verify that family directives do not execute multiple times."""
    import ramble.language.workflow_manager_language

    class TestWM(metaclass=ramble.language.workflow_manager_language.WorkflowManagerMeta):
        name = "test_wm"
        __module__ = "ramble.wm"
        ramble.language.workflow_manager_language.workflow_manager_family("fam_test")

    exec_count = 0
    wrapped_list = []
    for d_name, d_fn in TestWM._directives_to_be_executed:

        def make_wrapper(target_fn):
            def _wrapped(cls):
                nonlocal exec_count
                exec_count += 1
                return target_fn(cls)

            return _wrapped

        wrapped_list.append((d_name, make_wrapper(d_fn)))

    TestWM._directives_to_be_executed = wrapped_list
    assert "fam_test" in TestWM.class_families
    assert exec_count == 1


def test_language_types_descriptor_scoping(mutable_mock_apps_repo, mutable_mock_mods_repo):
    """Verify descriptors are scoped to declared language types."""
    app = mutable_mock_apps_repo.get("basic")
    assert hasattr(app, "workloads")
    assert not hasattr(app, "modes")

    mod = mutable_mock_mods_repo.get("spack-mod")
    assert hasattr(mod, "modes")
    assert not hasattr(mod, "workloads")


def test_eager_directive_execution_without_dicts():
    """Verify that directives declared with dicts=() execute eagerly at class definition."""
    executed = []

    @DirectiveMeta.directive(dicts=())
    def custom_eager_directive(val):
        def _exec(cls):
            executed.append(val)

        return _exec

    class EagerApp(metaclass=DirectiveMeta):
        name = "eager_app"
        __module__ = "ramble.app"
        custom_eager_directive("eager_ran")

    assert executed == ["eager_ran"]


def test_clone_nested_directive_isolation(mutable_mock_apps_repo):
    """Verify that modifying nested directive dictionaries on a clone
    does not mutate the original.
    """
    app = mutable_mock_apps_repo.get("basic")
    app.set_variables_and_variants({"workload_name": "test_wl"}, {}, None, None)
    _ = app.inputs
    _ = app.executables

    clone = app.clone()
    # Mutate clone's inputs
    clone.inputs[frozenset()]["input"]["url"] = "file:///tmp/mutated.log"
    assert app.inputs[frozenset()]["input"]["url"] != "file:///tmp/mutated.log"

    # Mutate clone's executables
    clone.executables[frozenset()]["foo"].template = ["mutated_cmd"]
    assert app.executables[frozenset()]["foo"].template != ["mutated_cmd"]


def test_same_name_subclass_preferred_version_override():
    """Verify that a subclass sharing the same class name as its base
    can override the preferred version.
    """

    class SharedNameApp(ExecutableApplication):
        name = "shared_name_app"
        __module__ = "ramble.app.base"
        ramble.language.shared_language.version("1.0", preferred=True)

    # Subclass with identical class name in a different namespace
    class SubclassSharedNameApp(SharedNameApp):
        name = "subclass_shared_name_app"
        __module__ = "ramble.app.derived"
        ramble.language.shared_language.version("2.0", preferred=True)

    # Rename class attribute __name__ to mimic same class name
    SubclassSharedNameApp.__name__ = "SharedNameApp"

    assert str(SharedNameApp.preferred_version.version) == "1.0"
    assert str(SubclassSharedNameApp.preferred_version.version) == "2.0"


def test_utility_and_modifier_descriptor_scoping(mutable_mock_apps_repo, mutable_mock_mods_repo):
    """Verify that utility and modifier directives do not leak descriptors onto applications."""
    import ramble.language.utility_language  # noqa: F401

    app = mutable_mock_apps_repo.get("basic")
    assert not hasattr(app, "provided_executables")
    assert not hasattr(app, "env_sources")
    assert not hasattr(app, "env_var_modifications")
    assert not hasattr(app, "modifier_conflicts")

    mod = mutable_mock_mods_repo.get("spack-mod")
    assert not hasattr(mod, "provided_executables")
    assert not hasattr(mod, "env_sources")
    assert not hasattr(mod, "license_names")
    assert not hasattr(mod, "cleanups")


def test_remove_directives_nested_dict():
    """Verify that directives nested inside dictionaries or sets are removed from queue."""

    @DirectiveMeta.directive(dicts=())
    def outer_directive(**kwargs):
        def _exec(cls):
            pass

        return _exec

    @DirectiveMeta.directive(dicts=())
    def inner_directive():
        def _exec(cls):
            pass

        return _exec

    class NestedDirectiveApp(metaclass=DirectiveMeta):
        name = "nested_dir_app"
        __module__ = "ramble.app"
        outer_directive(mapping={"k": inner_directive()})

    # inner_directive was passed inside a dict value, so it should have been removed
    # from the execution queue, leaving only outer_directive
    assert len(NestedDirectiveApp._directives_to_be_executed) == 1
    assert NestedDirectiveApp._directives_to_be_executed[0][0] == "outer_directive"


def test_directive_auto_registration_type_scoping():
    """Verify that new directives dynamically defined with non-shared language_type
    are automatically added to _type_scoped_dicts without manual table editing.
    """

    @DirectiveMeta.directive(dicts="auto_app_dict", language_type="application")
    def auto_app_directive():
        def _exec(cls):
            pass

        return _exec

    @DirectiveMeta.directive(dicts="auto_mod_dict", language_type="modifier")
    def auto_mod_directive():
        def _exec(cls):
            pass

        return _exec

    assert "auto_app_dict" in DirectiveMeta._type_scoped_dicts["application"]
    assert "auto_mod_dict" in DirectiveMeta._type_scoped_dicts["modifier"]

    class AutoApp(metaclass=DirectiveMeta):
        name = "auto_app"
        __module__ = "ramble.app"
        _language_types = ["application", "shared"]

    class AutoMod(metaclass=DirectiveMeta):
        name = "auto_mod"
        __module__ = "ramble.mod"
        _language_types = ["modifier", "shared"]

    # AutoApp should have auto_app_dict, but not auto_mod_dict
    assert hasattr(AutoApp, "auto_app_dict")
    assert not hasattr(AutoApp, "auto_mod_dict")

    # AutoMod should have auto_mod_dict, but not auto_app_dict
    assert hasattr(AutoMod, "auto_mod_dict")
    assert not hasattr(AutoMod, "auto_app_dict")


def test_class_body_scratch_variable_collision():
    """Verify that a class body local variable with a colliding name but incompatible type
    does not clobber the directive dictionary initial value.
    """

    class ScratchVarApp(metaclass=ramble.language.application_language.ApplicationMeta):
        name = "scratch_var_app"
        __module__ = "ramble.app"
        # 'workloads' is defined as a list in class body (e.g. loop accumulator),
        # which collides with the 'workloads' directive dictionary (dict).
        workloads = ["w1", "w2"]
        for w in workloads:
            ramble.language.application_language.workload(w, executables=["exe"])

    assert isinstance(ScratchVarApp.workloads, dict)
    assert "w1" in ScratchVarApp.workloads[frozenset()]
    assert "w2" in ScratchVarApp.workloads[frozenset()]


def test_variable_and_workload_variable_multi_dict_dependencies():
    """Verify that accessing validators or object_environment_variables first
    triggers execution of variable and workload_variable directives.
    """

    class VarDepsApp(metaclass=ramble.language.application_language.ApplicationMeta):
        name = "var_deps_app"
        __module__ = "ramble.app"
        ramble.language.application_language.workload("test_wl", executables=["exe"])
        ramble.language.shared_language.variable(
            "strict_var",
            default="opt1",
            description="Strict var",
            values=["opt1", "opt2"],
            strict=True,
            environment_variable_name="STRICT_ENV_VAR",
        )
        ramble.language.application_language.workload_variable(
            "wl_strict_var",
            default="v1",
            description="Workload strict var",
            values=["v1", "v2"],
            strict=True,
            workload="test_wl",
        )

    # Access validators and object_environment_variables FIRST before object_variables
    validators = VarDepsApp.validators
    env_vars = VarDepsApp.object_environment_variables

    assert len(validators) == 2
    assert len(env_vars) > 0


def test_source_script_directive_list_init():
    """Verify that source_script initializes scripts_to_source as a list."""

    class ScriptApp(metaclass=ramble.language.application_language.ApplicationMeta):
        name = "script_app"
        __module__ = "ramble.app"
        ramble.language.shared_language.source_script("/path/to/my_script.sh")

    scripts = ScriptApp.scripts_to_source
    assert isinstance(scripts, list)
    assert len(scripts) == 1
    assert scripts[0]["path"] == "/path/to/my_script.sh"


def test_directive_init_values_not_clobbered():
    """Verify that registering a directive with explicit init_value=[] is not
    overwritten with {} by a subsequent directive with default init_value=_UNSET.
    """

    @DirectiveMeta.directive(dicts="custom_list_dict", init_value=[])
    def first_directive():
        def _exec(cls):
            cls.custom_list_dict.append("item1")

        return _exec

    @DirectiveMeta.directive(dicts=("other_dict", "custom_list_dict"))
    def second_directive():
        def _exec(cls):
            cls.custom_list_dict.append("item2")

        return _exec

    assert isinstance(DirectiveMeta._directive_init_values["custom_list_dict"], list)

    class ClobberTestApp(metaclass=DirectiveMeta):
        name = "clobber_test_app"
        __module__ = "ramble.app"
        first_directive()
        second_directive()

    assert ClobberTestApp.custom_list_dict == ["item1", "item2"]


def test_class_body_exception_prepare_isolation():
    """Verify that an exception raised halfway through a class body does not
    leak queued directives or active when contexts to subsequent classes.
    """
    with pytest.raises(RuntimeError, match="Intentional crash"):

        class CrashingApp(metaclass=ramble.language.application_language.ApplicationMeta):
            name = "crashing_app"
            __module__ = "ramble.app"
            ramble.language.application_language.workload("leaked_wl", executables=["exe"])
            with ramble.language.shared_language.when("package_manager=spack"):
                raise RuntimeError("Intentional crash")

    class CleanApp(metaclass=ramble.language.application_language.ApplicationMeta):
        name = "clean_app"
        __module__ = "ramble.app"

    assert len(CleanApp.workloads) == 0
    assert len(DirectiveMeta._when_constraints_from_context) == 0


def test_eager_directive_nested_execution_depth_guard():
    """Verify that an eager directive (dicts=()) calling another directive internally
    does not leak the nested directive into _directives_to_be_executed.
    """

    @DirectiveMeta.directive(dicts=())
    def eager_outer():
        def _exec(cls):
            ramble.language.shared_language.tags("eager_tag")(cls)

        return _exec

    class EagerNestedApp(metaclass=DirectiveMeta):
        name = "eager_nested_app"
        __module__ = "ramble.app"
        eager_outer()

    assert len(DirectiveMeta._directives_to_be_executed) == 0


def test_partial_evaluation_rollback_on_exception():
    """Verify that if a directive raises an exception during evaluation,
    initialized attributes are rolled back to _UNSET so subsequent accesses
    re-raise rather than returning a corrupted dictionary.
    """

    class BrokenApp(ExecutableApplication):
        name = "broken_app"
        __module__ = "ramble.app"
        ramble.language.shared_language.version("1.0", preferred=True)
        ramble.language.shared_language.version("2.0", preferred=True)

    with pytest.raises(DirectiveError, match="already has a preferred version"):
        _ = BrokenApp.known_versions

    assert BrokenApp.__dict__.get("_known_versions", _UNSET) is _UNSET

    # Second access should raise the same DirectiveError rather than returning partial state
    with pytest.raises(DirectiveError, match="already has a preferred version"):
        _ = BrokenApp.known_versions


def test_utility_base_lazy_initialization():
    """Verify UtilityBase instantiation does not eagerly evaluate its directive dictionaries."""
    UtilityBase = ramble.repository.get_base_class("utility-base")

    class LazyUtil(UtilityBase):
        name = "lazy_util"
        __module__ = "ramble.utility"

    util = LazyUtil("/mock/path")
    for attr in [
        "env_sources",
        "env_sets",
        "env_prepends",
        "env_appends",
        "fetch_mappings",
        "bootstrappable",
        "missing_error_messages",
        "provided_executables",
    ]:
        assert attr not in util.__dict__
