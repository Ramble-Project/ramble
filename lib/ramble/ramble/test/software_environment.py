# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import pytest

import ramble.config
import ramble.expander
import ramble.software_environments
import ramble.workspace
from ramble.main import RambleCommand
from ramble.namespace import namespace

pytestmark = pytest.mark.usefixtures(
    "mutable_config",
    "mutable_mock_workspace_path",
    "mutable_mock_apps_repo",
)

workspace = RambleCommand("workspace")


def _get_package_manager(pm_name: str = "spack"):
    return ramble.repository.get(pm_name, ramble.repository.ObjectTypes.package_managers).copy()


def test_basic_software_environment(request, mutable_mock_workspace_path):
    ws_name = request.node.name
    workspace("create", ws_name)

    assert ws_name in workspace("list")

    with ramble.workspace.read(ws_name) as ws:
        software_dict = ramble.config.get(namespace.software)

        software_dict["packages"] = {}
        software_dict["packages"]["basic"] = {"pkg_spec": "basic@1.1"}
        software_dict["environments"] = {"basic": {"packages": ["basic"]}}

        software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        assert "basic" in software_environments._environment_templates
        assert "basic" in software_environments._package_templates

        variables = {}
        env_expander = ramble.expander.Expander(variables, None)

        rendered_env = software_environments.render_environment(
            "basic", env_expander, _get_package_manager()
        )
        assert rendered_env.name == "basic"
        pkg_found = False
        for pkg in rendered_env._packages:
            if pkg.name == "basic":
                pkg_found = True
        assert pkg_found


def test_software_environments_no_packages(request, mutable_mock_workspace_path):
    ws_name = request.node.name

    workspace("create", ws_name)

    assert ws_name in workspace("list")

    with ramble.workspace.read(ws_name) as ws:
        software_dict = ramble.config.get(namespace.software)

        software_dict["packages"] = {}
        software_dict["environments"] = {"basic-{env_test}": {"packages": [""]}}

        software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        assert "basic-{env_test}" in software_environments._environment_templates

        variables = {
            "env_test": "environment",
        }
        env_expander = ramble.expander.Expander(variables, None)

        rendered_env = software_environments.render_environment(
            "basic-environment", env_expander, _get_package_manager()
        )
        assert rendered_env.name == "basic-environment"


def test_software_environments_no_rendered_packages(request, mutable_mock_workspace_path):
    ws_name = request.node.name

    workspace("create", ws_name)

    assert ws_name in workspace("list")

    with ramble.workspace.read(ws_name) as ws:
        software_dict = ramble.config.get(namespace.software)

        software_dict["packages"] = {}
        software_dict["environments"] = {"basic-{env_test}": {"packages": ["{var_pkg_name}"]}}

        software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        assert "basic-{env_test}" in software_environments._environment_templates

        variables = {"env_test": "environment", "var_pkg_name": ""}
        env_expander = ramble.expander.Expander(variables, None)

        rendered_env = software_environments.render_environment(
            "basic-environment", env_expander, _get_package_manager()
        )
        assert rendered_env.name == "basic-environment"


def test_template_software_environments(request, mutable_mock_workspace_path):
    ws_name = request.node.name

    workspace("create", ws_name)

    assert ws_name in workspace("list")

    with ramble.workspace.read(ws_name) as ws:
        software_dict = ramble.config.get(namespace.software)

        software_dict["packages"] = {}
        software_dict["packages"]["basic-{pkg_test}"] = {"pkg_spec": "basic@1.1"}
        software_dict["environments"] = {"basic-{env_test}": {"packages": ["basic-{pkg_test}"]}}

        software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        assert "basic-{env_test}" in software_environments._environment_templates
        assert "basic-{pkg_test}" in software_environments._package_templates

        variables = {
            "env_test": "environment",
            "pkg_test": "package",
        }
        env_expander = ramble.expander.Expander(variables, None)

        rendered_env = software_environments.render_environment(
            "basic-environment", env_expander, _get_package_manager()
        )
        assert rendered_env.name == "basic-environment"
        pkg_found = False
        for pkg in rendered_env._packages:
            if pkg.name == "basic-package":
                pkg_found = True
        assert pkg_found


def test_multi_template_software_environments(request, mutable_mock_workspace_path):
    ws_name = request.node.name

    workspace("create", ws_name)

    assert ws_name in workspace("list")

    with ramble.workspace.read(ws_name) as ws:
        software_dict = ramble.config.get(namespace.software)

        software_dict["packages"] = {}
        software_dict["packages"]["basic1-{pkg_test}"] = {"pkg_spec": "basic@1.1"}
        software_dict["packages"]["basic2-{pkg_test}"] = {"pkg_spec": "basic@1.1"}
        software_dict["environments"] = {
            "all-basic-{env_test}": {"packages": ["basic1-{pkg_test}", "basic2-{pkg_test}"]},
            "basic1-{env_test}": {"packages": ["basic1-{pkg_test}"]},
            "basic2-{env_test}": {"packages": ["basic2-{pkg_test}"]},
        }

        software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        assert "all-basic-{env_test}" in software_environments._environment_templates
        assert "basic1-{env_test}" in software_environments._environment_templates
        assert "basic2-{env_test}" in software_environments._environment_templates
        assert "basic1-{pkg_test}" in software_environments._package_templates
        assert "basic2-{pkg_test}" in software_environments._package_templates

        variables = {
            "env_test": "environment",
            "pkg_test": "package",
        }
        env_expander = ramble.expander.Expander(variables, None)

        env_tests = {
            "all-basic-environment": ["basic1-package", "basic2-package"],
            "basic1-environment": ["basic1-package"],
            "basic2-environment": ["basic2-package"],
        }

        for env_name, env_packages in env_tests.items():
            rendered_env = software_environments.render_environment(
                env_name, env_expander, _get_package_manager()
            )
            assert rendered_env.name == env_name

            assert len(rendered_env._packages) == len(env_packages)
            for pkg_name in env_packages:
                pkg_found = False
                for pkg in rendered_env._packages:
                    if pkg.name == pkg_name:
                        pkg_found = True
                assert pkg_found


def test_undefined_package_errors(request, mutable_mock_workspace_path):
    ws_name = request.node.name

    workspace("create", ws_name)

    assert ws_name in workspace("list")

    with ramble.workspace.read(ws_name) as ws:
        software_dict = ramble.config.get(namespace.software)

        software_dict["packages"] = {}
        software_dict["packages"]["basic-{pkg_test}"] = {"pkg_spec": "basic@{pkg_ver}"}
        software_dict["environments"] = {
            "all-basic-{env_test}": {"packages": ["foo-basic-{pkg_test}"]}
        }

        software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        variables = {"env_test": "environment"}

        env_expander = ramble.expander.Expander(variables, None)

        with pytest.raises(ramble.software_environments.RambleSoftwareEnvironmentError) as pkg_err:
            software_environments.render_environment(
                "all-basic-environment", env_expander, _get_package_manager()
            )

        err_str = (
            "Environment template all-basic-{env_test} references undefined "
            + "package foo-basic-{pkg_test}"
        )
        assert err_str in str(pkg_err)


def test_invalid_packages_error(request, mutable_mock_workspace_path):
    ws_name = request.node.name

    workspace("create", ws_name)

    assert ws_name in workspace("list")

    with ramble.workspace.read(ws_name) as ws:
        software_dict = ramble.config.get(namespace.software)

        software_dict["packages"] = {}
        software_dict["packages"]["basic-{pkg_test}"] = {"pkg_spec": "basic@{pkg_ver}"}
        software_dict["environments"] = {
            "all-basic-{env_test}": {"packages": ["basic-{pkg_test}"]}
        }

        software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        assert "all-basic-{env_test}" in software_environments._environment_templates
        assert "basic-{pkg_test}" in software_environments._package_templates

        variables = {
            "env_test": "environment",
            "pkg_test": "package",
            "pkg_ver": "1.1",
        }
        env_expander = ramble.expander.Expander(variables, None)

        _ = software_environments.render_environment(
            "all-basic-environment", env_expander, _get_package_manager()
        )

        with pytest.raises(ramble.software_environments.RambleSoftwareEnvironmentError) as pkg_err:
            variables = {
                "env_test": "environment",
                "pkg_test": "package",
                "pkg_ver": "1.4",
            }
            env_expander = ramble.expander.Expander(variables, None)

            software_environments.render_environment(
                "all-basic-environment", env_expander, _get_package_manager()
            )
        assert "Package basic-package defined multiple times" in str(pkg_err)


def test_invalid_environment_error(request, mutable_mock_workspace_path):
    ws_name = request.node.name

    workspace("create", ws_name)

    assert ws_name in workspace("list")

    with ramble.workspace.read(ws_name) as ws:
        software_dict = ramble.config.get(namespace.software)

        software_dict["packages"] = {}
        software_dict["packages"]["basic1-{pkg_test}"] = {"pkg_spec": "basic@1.1"}
        software_dict["packages"]["basic2-{pkg_test}"] = {"pkg_spec": "basic@1.1"}
        software_dict["environments"] = {
            "all-basic-{env_test}": {"packages": ["basic1-{pkg_test}", "basic2-{pkg_test}"]}
        }

        software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        assert "all-basic-{env_test}" in software_environments._environment_templates
        assert "basic1-{pkg_test}" in software_environments._package_templates
        assert "basic2-{pkg_test}" in software_environments._package_templates

        variables = {
            "env_test": "environment",
            "pkg_test": "package",
        }
        env_expander = ramble.expander.Expander(variables, None)

        _ = software_environments.render_environment(
            "all-basic-environment", env_expander, _get_package_manager()
        )

        variables = {"env_test": "environment", "pkg_test": "other-package"}

        env_expander = ramble.expander.Expander(variables, None)

        with pytest.raises(ramble.software_environments.RambleSoftwareEnvironmentError) as env_err:
            software_environments.render_environment(
                "all-basic-environment", env_expander, _get_package_manager()
            )

        assert "Environment all-basic-environment defined multiple times" in str(env_err)


def test_undefined_compiler_errors(request, mutable_mock_workspace_path):
    ws_name = request.node.name

    workspace("create", ws_name)

    assert ws_name in workspace("list")

    with ramble.workspace.read(ws_name) as ws:
        software_dict = ramble.config.get(namespace.software)

        software_dict["packages"] = {}
        software_dict["packages"]["basic"] = {"pkg_spec": "basic@1.1", "compiler": "foo_comp"}
        software_dict["environments"] = {"basic": {"packages": ["basic"]}}

        software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        assert "basic" in software_environments._environment_templates
        assert "basic" in software_environments._package_templates

        variables = {}
        env_expander = ramble.expander.Expander(variables, None)

        with pytest.raises(
            ramble.software_environments.RambleSoftwareEnvironmentError,
            match="Compiler foo_comp used, but not defined",
        ):
            software_environments.render_environment("basic", env_expander, _get_package_manager())


def test_compiler_in_environment_warns(request, mutable_mock_workspace_path, capsys):
    ws_name = request.node.name

    workspace("create", ws_name)

    assert ws_name in workspace("list")

    with ramble.workspace.read(ws_name) as ws:
        software_dict = ramble.config.get(namespace.software)

        software_dict["packages"] = {}
        software_dict["packages"]["test_comp"] = {"pkg_spec": "comp@2.1"}
        software_dict["packages"]["basic"] = {"pkg_spec": "basic@1.1", "compiler": "test_comp"}
        software_dict["environments"] = {"basic": {"packages": ["basic", "test_comp"]}}

        software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        assert "basic" in software_environments._environment_templates
        assert "basic" in software_environments._package_templates

        variables = {}
        env_expander = ramble.expander.Expander(variables, None)

        _ = software_environments.render_environment("basic", env_expander, _get_package_manager())
        captured = capsys.readouterr()

        assert "Environment basic contains packages and their compilers" in captured.err
        assert "Package: basic, Compiler: test_comp" in captured.err


def test_is_used_property(request, mutable_mock_workspace_path):
    ws_name = request.node.name
    workspace("create", ws_name)

    with ramble.workspace.read(ws_name) as ws:
        software_dict = ramble.config.get(namespace.software)
        software_dict["packages"] = {}
        software_dict["packages"]["basic"] = {"pkg_spec": "basic@1.1"}
        software_dict["environments"] = {"basic": {"packages": ["basic"]}}

        software_environments = ramble.software_environments.SoftwareEnvironments(ws)
        env_template = software_environments._environment_templates["basic"]
        pkg_template = software_environments._package_templates["basic"]

        # Verify initial state (not used)
        assert env_template.is_used is False
        assert pkg_template.is_used is False

        # Render environment
        variables = {}
        env_expander = ramble.expander.Expander(variables, None)
        rendered_env = software_environments.render_environment(
            "basic", env_expander, _get_package_manager()
        )
        rendered_pkg = rendered_env._packages[0]

        # Verify rendered packages/envs are initially not used
        assert rendered_env.is_used is False
        assert rendered_pkg.is_used is False

        # Mark environment as used and verify propagation
        software_environments.use_environment(_get_package_manager(), "basic")
        assert rendered_env.is_used is True
        assert rendered_pkg.is_used is True
        assert env_template.is_used is True
        assert pkg_template.is_used is True


def test_undefined_environment_auto_construction(request, mutable_mock_workspace_path):
    ws_name = request.node.name
    workspace("create", ws_name)

    with ramble.workspace.read(ws_name) as ws:
        software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        assert "completely-undefined-env" not in software_environments._environment_templates

        variables = {}
        env_expander = ramble.expander.Expander(variables, None)
        rendered_env = software_environments.render_environment(
            "completely-undefined-env", env_expander, _get_package_manager()
        )
        assert rendered_env.name == "completely-undefined-env"
        assert "completely-undefined-env" in software_environments._environment_templates
        assert len(rendered_env._packages) == 0


def test_check_all_environments_warning(request, mutable_mock_workspace_path, capsys):
    ws_name = request.node.name
    workspace("create", ws_name)

    with ramble.workspace.read(ws_name) as ws:
        software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        variables = {}
        env_expander = ramble.expander.Expander(variables, None)
        _ = software_environments.render_environment(
            "completely-undefined-env", env_expander, _get_package_manager()
        )

        software_environments.check_all_environments()
        captured = capsys.readouterr()
        assert (
            "Software environment 'completely-undefined-env' was auto-constructed" in captured.err
        )


def test_build_experiment_set_check_environments_flag(
    request, mutable_mock_workspace_path, capsys
):
    ws_name = request.node.name
    workspace("create", ws_name)

    with ramble.workspace.read(ws_name) as ws:
        ws.software_environments = ramble.software_environments.SoftwareEnvironments(ws)

        variables = {}
        env_expander = ramble.expander.Expander(variables, None)
        _ = ws.software_environments.render_environment(
            "completely-undefined-env", env_expander, _get_package_manager()
        )

        ws.build_experiment_set(check_environments=False)
        captured = capsys.readouterr()
        assert (
            "Software environment 'completely-undefined-env' was auto-constructed"
            not in captured.err
        )

        ws.build_experiment_set(check_environments=True)
        captured = capsys.readouterr()
        assert (
            "Software environment 'completely-undefined-env' was auto-constructed" in captured.err
        )
