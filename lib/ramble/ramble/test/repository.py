# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import sys

import pytest

import ramble.repository


@pytest.fixture(params=["applications", "", "foo"])
def extra_repo(tmpdir_factory, request):
    repo_namespace = "extra_test_repo"
    repo_dir = tmpdir_factory.mktemp(repo_namespace)
    repo_dir.ensure(request.param, dir=True)

    with open(str(repo_dir.join("repo.yaml")), "w", encoding="utf-8") as f:
        f.write("""
repo:
  namespace: extra_test_repo
""")
        if request.param != "applications":
            f.write(f"  subdirectory: '{request.param}'")
    return (
        ramble.repository.Repo(
            str(repo_dir), object_type=ramble.repository.ObjectTypes.applications
        ),
        request.param,
    )


def test_repo_getapp(mutable_mock_apps_repo):
    mutable_mock_apps_repo.get("basic")
    mutable_mock_apps_repo.get("builtin.mock.basic")


def test_repo_multi_getapp(mutable_mock_apps_repo, extra_repo):
    mutable_mock_apps_repo.put_first(extra_repo[0])
    mutable_mock_apps_repo.get("basic")
    mutable_mock_apps_repo.get("builtin.mock.basic")


def test_repo_multi_getappclass(mutable_mock_apps_repo, extra_repo):
    mutable_mock_apps_repo.put_first(extra_repo[0])
    mutable_mock_apps_repo.get_obj_class("basic")
    mutable_mock_apps_repo.get_obj_class("builtin.mock.basic")


def test_repo_app_with_unknown_namespace(mutable_mock_apps_repo):
    with pytest.raises(ramble.repository.UnknownNamespaceError):
        mutable_mock_apps_repo.get("unknown.a")


def test_repo_unknown_app(mutable_mock_apps_repo):
    with pytest.raises(ramble.repository.UnknownObjectError):
        mutable_mock_apps_repo.get("builtin.mock.nonexistentapplication")


@pytest.mark.parametrize(
    "obj_name,obj_type,expected",
    [
        (
            "openfoam-org",
            ramble.repository.ObjectTypes.applications,
            [
                ("applications", "openfoam-org/application.py", "builtin"),
                ("base_applications", "openfoam/base_application.py", "builtin"),
            ],
        ),
        (
            "lscpu",
            ramble.repository.ObjectTypes.modifiers,
            [
                ("modifiers", "lscpu/modifier.py", "builtin"),
            ],
        ),
        (
            "spack",
            ramble.repository.ObjectTypes.package_managers,
            [
                ("package_managers", "spack/package_manager.py", "builtin"),
                ("package_managers", "spack-lightweight/package_manager.py", "builtin"),
            ],
        ),
    ],
)
def test_list_object_files(
    obj_name,
    obj_type,
    expected,
    mutable_apps_repo_path,
    mutable_mods_repo_path,
    mutable_pkg_mans_repo_path,
):
    if obj_type == ramble.repository.ObjectTypes.applications:
        repo = mutable_apps_repo_path
    elif obj_type == ramble.repository.ObjectTypes.modifiers:
        repo = mutable_mods_repo_path
    else:
        repo = mutable_pkg_mans_repo_path
    obj_inst = repo.get(obj_name)
    actual = ramble.repository.list_object_files(obj_inst, obj_type)
    assert len(expected) == len(actual)
    for i in range(len(expected)):
        assert len(expected[i]) == len(actual[i])
        assert expected[i][0] == actual[i][0]
        assert actual[i][1].endswith(expected[i][1])
        assert expected[i][2] == actual[i][2]


@pytest.mark.parametrize("bad_ns", ["foo!bar", "foo-bar", "123foo"])
def test_invalid_namespace(tmpdir, bad_ns):
    with pytest.raises(ramble.repository.InvalidNamespaceError):
        ramble.repository.create_repo(str(tmpdir.join("bad_repo")), namespace=bad_ns)


@pytest.mark.parametrize(
    "input_type,expected_enum",
    [
        ("applications", ramble.repository.ObjectTypes.applications),
        ("application", ramble.repository.ObjectTypes.applications),
        ("app", ramble.repository.ObjectTypes.applications),
        ("apps", ramble.repository.ObjectTypes.applications),
        ("modifiers", ramble.repository.ObjectTypes.modifiers),
        ("modifier", ramble.repository.ObjectTypes.modifiers),
        ("mod", ramble.repository.ObjectTypes.modifiers),
        ("package_managers", ramble.repository.ObjectTypes.package_managers),
        ("package_manager", ramble.repository.ObjectTypes.package_managers),
        ("package-manager", ramble.repository.ObjectTypes.package_managers),
        ("package manager", ramble.repository.ObjectTypes.package_managers),
        ("pkg_man", ramble.repository.ObjectTypes.package_managers),
        ("pkg", ramble.repository.ObjectTypes.package_managers),
        ("package", ramble.repository.ObjectTypes.package_managers),
        ("workflow_managers", ramble.repository.ObjectTypes.workflow_managers),
        ("workflow_manager", ramble.repository.ObjectTypes.workflow_managers),
        ("workflow-manager", ramble.repository.ObjectTypes.workflow_managers),
        ("workflow manager", ramble.repository.ObjectTypes.workflow_managers),
        ("wm", ramble.repository.ObjectTypes.workflow_managers),
        ("workflow", ramble.repository.ObjectTypes.workflow_managers),
        ("systems", ramble.repository.ObjectTypes.systems),
        ("system", ramble.repository.ObjectTypes.systems),
        ("sys", ramble.repository.ObjectTypes.systems),
        ("platforms", ramble.repository.ObjectTypes.platforms),
        ("platform", ramble.repository.ObjectTypes.platforms),
        ("plat", ramble.repository.ObjectTypes.platforms),
        ("base_classes", ramble.repository.ObjectTypes.base_classes),
        ("base_class", ramble.repository.ObjectTypes.base_classes),
        ("base-class", ramble.repository.ObjectTypes.base_classes),
        ("base class", ramble.repository.ObjectTypes.base_classes),
        ("base_cls", ramble.repository.ObjectTypes.base_classes),
        ("base", ramble.repository.ObjectTypes.base_classes),
        ("base_applications", ramble.repository.ObjectTypes.base_applications),
        ("base_application", ramble.repository.ObjectTypes.base_applications),
        ("base-application", ramble.repository.ObjectTypes.base_applications),
        ("base application", ramble.repository.ObjectTypes.base_applications),
        ("base_app", ramble.repository.ObjectTypes.base_applications),
        ("base_modifiers", ramble.repository.ObjectTypes.base_modifiers),
        ("base_modifier", ramble.repository.ObjectTypes.base_modifiers),
        ("base-modifier", ramble.repository.ObjectTypes.base_modifiers),
        ("base modifier", ramble.repository.ObjectTypes.base_modifiers),
        ("base_mod", ramble.repository.ObjectTypes.base_modifiers),
        ("base_package_managers", ramble.repository.ObjectTypes.base_package_managers),
        ("base_package_manager", ramble.repository.ObjectTypes.base_package_managers),
        ("base-package-manager", ramble.repository.ObjectTypes.base_package_managers),
        ("base package manager", ramble.repository.ObjectTypes.base_package_managers),
        ("base_pkg_man", ramble.repository.ObjectTypes.base_package_managers),
        ("base_pkg", ramble.repository.ObjectTypes.base_package_managers),
        ("base_workflow_managers", ramble.repository.ObjectTypes.base_workflow_managers),
        ("base_workflow_manager", ramble.repository.ObjectTypes.base_workflow_managers),
        ("base-workflow-manager", ramble.repository.ObjectTypes.base_workflow_managers),
        ("base workflow manager", ramble.repository.ObjectTypes.base_workflow_managers),
        ("base_wm", ramble.repository.ObjectTypes.base_workflow_managers),
        ("base_systems", ramble.repository.ObjectTypes.base_systems),
        ("base_system", ramble.repository.ObjectTypes.base_systems),
        ("base-system", ramble.repository.ObjectTypes.base_systems),
        ("base system", ramble.repository.ObjectTypes.base_systems),
        ("base_sys", ramble.repository.ObjectTypes.base_systems),
        ("base_platforms", ramble.repository.ObjectTypes.base_platforms),
        ("base_platform", ramble.repository.ObjectTypes.base_platforms),
        ("base-platform", ramble.repository.ObjectTypes.base_platforms),
        ("base platform", ramble.repository.ObjectTypes.base_platforms),
        ("base_plat", ramble.repository.ObjectTypes.base_platforms),
        ("utilities", ramble.repository.ObjectTypes.utilities),
        ("utility", ramble.repository.ObjectTypes.utilities),
        ("base_utilities", ramble.repository.ObjectTypes.base_utilities),
        ("base_utility", ramble.repository.ObjectTypes.base_utilities),
        ("base-utility", ramble.repository.ObjectTypes.base_utilities),
        ("base utility", ramble.repository.ObjectTypes.base_utilities),
    ],
)
def test_simplify_object_type(input_type, expected_enum):
    assert ramble.repository.simplify_object_type(input_type) == expected_enum
    assert ramble.repository.simplify_object_type(input_type.upper()) == expected_enum
    assert ramble.repository.get_object_type(input_type) == expected_enum


def test_simplify_object_type_enum_passthrough():
    for obj_type in ramble.repository.ObjectTypes:
        assert ramble.repository.simplify_object_type(obj_type) == obj_type


@pytest.mark.parametrize("invalid_type", ["not_a_type", "foo_bar", "123", "", None])
def test_simplify_object_type_invalid(invalid_type):
    with pytest.raises(ramble.repository.UnknownObjectTypeError):
        ramble.repository.simplify_object_type(invalid_type)


def test_use_repositories_exception_cleanup(extra_repo):
    orig_path = ramble.repository.paths[ramble.repository.ObjectTypes.applications]
    orig_meta_path = list(sys.meta_path)
    with pytest.raises(RuntimeError):
        with ramble.repository.use_repositories(extra_repo[0].root):
            raise RuntimeError("test error inside context")
    assert ramble.repository.paths[ramble.repository.ObjectTypes.applications] is orig_path
    assert sys.meta_path == orig_meta_path


def test_namespace_import_and_attribute_access(mutable_mock_apps_repo):
    import ramble.app.builtin.mock.basic as mock_basic

    assert hasattr(mock_basic, "Basic")

    import ramble.app.builtin.mock as mock_ns

    assert hasattr(mock_ns, "basic")
    assert mock_ns.basic.Basic.name == "basic"

    import ramble.app as app_ns

    assert hasattr(app_ns.builtin.mock, "basic")
    assert app_ns.builtin.mock.basic.Basic.name == "basic"


def test_namespace_nonexistent_attribute(mutable_mock_apps_repo):
    import ramble.app.builtin.mock as mock_ns

    assert not hasattr(mock_ns, "nonexistent_object")
    assert getattr(mock_ns, "nonexistent_object", "default") == "default"
    with pytest.raises(AttributeError):
        _ = mock_ns.nonexistent_object

    import ramble.app as app_ns

    assert not hasattr(app_ns, "nonexistent_subnamespace")
    assert getattr(app_ns, "nonexistent_subnamespace", None) is None
    with pytest.raises(AttributeError):
        _ = app_ns.nonexistent_subnamespace


def test_failed_constructor_error_message():
    try:
        raise ValueError("test exception message")
    except ValueError:
        exc_info = sys.exc_info()

    # Without object_type
    err = ramble.repository.FailedConstructorError("my_obj", *exc_info)
    assert "Class constructor failed for 'my_obj'." in str(err)
    assert "ValueError: test exception message" in str(err)
    assert "None" not in str(err)
    assert "%s" not in str(err)

    # With string object_type
    err_str = ramble.repository.FailedConstructorError("my_obj", *exc_info, object_type="modifier")
    assert "Class constructor failed for modifier 'my_obj'." in str(err_str)

    # With ObjectTypes enum
    err_enum = ramble.repository.FailedConstructorError(
        "my_obj", *exc_info, object_type=ramble.repository.ObjectTypes.applications
    )
    assert "Class constructor failed for application 'my_obj'." in str(err_enum)


def test_repo_get_raises_failed_constructor_error(mutable_mock_apps_repo, monkeypatch):
    def failing_constructor(*args, **kwargs):
        raise TypeError("simulated constructor failure")

    repo = mutable_mock_apps_repo.repo_for_obj("basic")
    monkeypatch.setattr(repo, "get_obj_class", lambda name: failing_constructor)

    with pytest.raises(ramble.repository.FailedConstructorError) as exc_info:
        mutable_mock_apps_repo.get("basic")

    err_msg = str(exc_info.value)
    assert "Class constructor failed for application 'basic'." in err_msg
    assert "TypeError: simulated constructor failure" in err_msg
