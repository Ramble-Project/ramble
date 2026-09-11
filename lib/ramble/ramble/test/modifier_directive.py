# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import ramble.repository
import ramble.workspace
from ramble.main import RambleCommand

workspace = RambleCommand("workspace")


def test_modifier_directive_injection(
    mutable_mock_workspace_path, mutable_applications, mock_modifiers, workspace_name, tmp_path
):
    app_repo_dir = tmp_path / "app_repo"
    app_repo_dir.mkdir()
    (app_repo_dir / "repo.yaml").write_text("repo:\n  namespace: extra_app_repo\n")

    app_dir = app_repo_dir / "applications" / "modifier-directive-app"
    app_dir.mkdir(parents=True)
    with open(str(app_dir / "application.py"), "w", encoding="utf-8") as f:
        f.write("""# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.appkit import *
class ModifierDirectiveApp(ExecutableApplication):
    name = "modifier-directive-app"

    executable('run', 'echo "hello"', use_mpi=False)
    workload('test', executable='run')

    # Inject a mock modifier
    modifier('directive-test-mod', mode='standard', on_executable=['run'], extra_kwarg='hello')

    # Conditionally inject a non-existent modifier (should not be injected)
    modifier('bad-modifier', when='@+some_fake_variant')

    # Conditionally inject another modifier when inject_modifiers_from_directives is false
    modifier('bad-modifier-2', when='~inject_modifiers_from_directives')
""")

    app_repo = ramble.repository.Repo(
        str(app_repo_dir), object_type=ramble.repository.ObjectTypes.applications
    )
    mutable_applications.put_first(app_repo)

    # Write out the mock modifiers
    mod_repo_dir = tmp_path / "mod_repo"
    mod_repo_dir.mkdir()
    (mod_repo_dir / "repo.yaml").write_text("repo:\n  namespace: extra_mod_repo\n")

    mod_dir1 = mod_repo_dir / "modifiers" / "directive-test-mod"
    mod_dir1.mkdir(parents=True)
    modifier_path = mod_dir1 / "modifier.py"
    with open(str(modifier_path), "w", encoding="utf-8") as f:
        f.write("""# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.modkit import *
class DirectiveTestMod(BasicModifier):
    name = "directive-test-mod"
    mode('standard', description='Standard mode')
""")

    mod_repo = ramble.repository.Repo(
        str(mod_repo_dir), object_type=ramble.repository.ObjectTypes.modifiers
    )
    mock_modifiers.put_first(mod_repo)

    mod_dir2 = mod_repo_dir / "modifiers" / "bad-modifier"
    mod_dir2.mkdir(parents=True)
    with open(str(mod_dir2 / "modifier.py"), "w", encoding="utf-8") as f:
        f.write("""# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.modkit import *
class BadModifier(BasicModifier):
    name = "bad-modifier"
    mode('standard', description='Standard mode')
""")

    mod_dir3 = mod_repo_dir / "modifiers" / "bad-modifier-2"
    mod_dir3.mkdir(parents=True)
    with open(str(mod_dir3 / "modifier.py"), "w", encoding="utf-8") as f:
        f.write("""# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.modkit import *
class BadModifier2(BasicModifier):
    name = "bad-modifier-2"
    mode('standard', description='Standard mode')
""")

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        config_path = os.path.join(ws.config_dir, ramble.workspace.CONFIG_FILE_NAME)

        # Test 1: With inject_modifiers_from_directives enabled (default)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("""
ramble:
  variables:
    mpi_command: 'mpirun'
    batch_submit: 'batch_submit'
    processes_per_node: '1'
    n_ranks: '1'
  applications:
    modifier-directive-app:
      workloads:
        test:
          experiments:
            exp1:
              variables:
                env_name: 'test'
""")

        ws._re_read()
        experiment_set = ws.build_experiment_set()
        # Find the experiment
        exp_name = "modifier-directive-app.test.exp1"
        app_inst = experiment_set.get_experiment(exp_name)
        assert app_inst is not None

        # We expect directive-test-mod to be in the modifiers
        modifier_names = [m.name for m in app_inst._modifier_instances]
        assert "directive-test-mod" in modifier_names
        assert "bad-modifier" not in modifier_names
        assert "bad-modifier-2" not in modifier_names

        with ramble.workspace.create(workspace_name + "_2") as ws2:
            ws2.write()
            config_path2 = os.path.join(ws2.config_dir, ramble.workspace.CONFIG_FILE_NAME)

            # Test 2: With inject_modifiers_from_directives disabled via variants
            with open(config_path2, "w", encoding="utf-8") as f:
                f.write("""
ramble:
  variables:
    mpi_command: 'mpirun'
    batch_submit: 'batch_submit'
    processes_per_node: '1'
    n_ranks: '1'
  variants:
    package_manager: spack
  applications:
    modifier-directive-app:
      variants:
        inject_modifiers_from_directives: False
      workloads:
        test:
          experiments:
            exp2:
              variables:
                env_name: 'test'
""")

            ws2._re_read()
            experiment_set = ws2.build_experiment_set()
            exp_name = "modifier-directive-app.test.exp2"
            app_inst = experiment_set.get_experiment(exp_name)
            assert app_inst is not None

            # We expect NO modifiers to be injected
            modifier_names = [m.name for m in app_inst._modifier_instances]
            assert "directive-test-mod" not in modifier_names
            assert "bad-modifier" not in modifier_names
            assert "bad-modifier-2" not in modifier_names


def test_modifier_directive_from_package_manager(
    mutable_mock_workspace_path,
    mutable_applications,
    mutable_package_managers,
    mock_modifiers,
    workspace_name,
    tmp_path,
):
    app_repo_dir = tmp_path / "app_repo"
    app_repo_dir.mkdir()
    (app_repo_dir / "repo.yaml").write_text("repo:\n  namespace: extra_app_repo\n")
    app_dir = app_repo_dir / "applications" / "pm-directive-app"
    app_dir.mkdir(parents=True)
    with open(str(app_dir / "application.py"), "w", encoding="utf-8") as f:
        f.write("""# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.appkit import *
class PmDirectiveApp(ExecutableApplication):
    name = "pm-directive-app"

    executable('run', 'echo "hello"', use_mpi=False)
    workload('test', executable='run')
""")

    app_repo = ramble.repository.Repo(
        str(app_repo_dir), object_type=ramble.repository.ObjectTypes.applications
    )
    mutable_applications.put_first(app_repo)

    # Write out a mock package manager
    pm_repo_dir = tmp_path / "pm_repo"
    pm_repo_dir.mkdir()
    (pm_repo_dir / "repo.yaml").write_text("repo:\n  namespace: extra_pm_repo\n")
    pm_dir = pm_repo_dir / "package_managers" / "directive-pm"
    pm_dir.mkdir(parents=True)
    with open(str(pm_dir / "package_manager.py"), "w", encoding="utf-8") as f:
        f.write("""# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.pkgmankit import *
class DirectivePm(PackageManagerBase):
    name = "directive-pm"
    modifier('directive-mod')

    def environment_load_commands(self, *args, **kwargs): pass
    def environment_unload_commands(self, *args, **kwargs): pass
    def get_package_list(self, *args, **kwargs): return []
    def package_name_from_spec(self, spec, *args, **kwargs): return spec
""")

    pm_repo = ramble.repository.Repo(
        str(pm_repo_dir), object_type=ramble.repository.ObjectTypes.package_managers
    )
    mutable_package_managers.put_first(pm_repo)

    # Write out the mock modifiers
    mod_repo_dir = tmp_path / "mod_repo"
    mod_repo_dir.mkdir()
    (mod_repo_dir / "repo.yaml").write_text("repo:\n  namespace: extra_mod_repo\n")
    mod_dir1 = mod_repo_dir / "modifiers" / "directive-mod"
    mod_dir1.mkdir(parents=True)
    with open(str(mod_dir1 / "modifier.py"), "w", encoding="utf-8") as f:
        f.write("""# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.modkit import *
class DirectiveMod(BasicModifier):
    name = "directive-mod"
    mode('standard', description='Standard mode')
""")

    mod_repo = ramble.repository.Repo(
        str(mod_repo_dir), object_type=ramble.repository.ObjectTypes.modifiers
    )
    mock_modifiers.put_first(mod_repo)

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()

        config_path = os.path.join(ws.config_dir, ramble.workspace.CONFIG_FILE_NAME)

        with open(config_path, "w", encoding="utf-8") as f:
            f.write("""
ramble:
  variables:
    mpi_command: 'mpirun'
    batch_submit: 'batch_submit'
    processes_per_node: '1'
    n_ranks: '1'
  variants:
    package_manager: directive-pm
  applications:
    pm-directive-app:
      workloads:
        test:
          experiments:
            exp1:
              variables:
                env_name: 'test'
""")

        ws._re_read()
        experiment_set = ws.build_experiment_set()
        # Find the experiment
        exp_name = "pm-directive-app.test.exp1"
        app_inst = experiment_set.get_experiment(exp_name)
        assert app_inst is not None

        # We expect directive-mod to be in the modifiers
        # because the package manager injected it
        modifier_names = [m.name for m in app_inst._modifier_instances]
        assert "directive-mod" in modifier_names


def test_modifier_directive_edge_cases(
    mutable_mock_workspace_path, mutable_applications, mock_modifiers, workspace_name, tmp_path
):
    # Test KeyError and str values for inject_modifiers_from_directives
    app_repo_dir = tmp_path / "app_repo"
    app_repo_dir.mkdir()
    (app_repo_dir / "repo.yaml").write_text("repo:\n  namespace: extra_app_repo\n")
    app_dir = app_repo_dir / "applications" / "edge-case-app"
    app_dir.mkdir(parents=True)
    with open(str(app_dir / "application.py"), "w", encoding="utf-8") as f:
        f.write("""from ramble.appkit import *
class EdgeCaseApp(ExecutableApplication):
    name = "edge-case-app"
    executable('run', 'echo "hello"', use_mpi=False)
    workload('test', executable='run')
    modifier('directive-test-mod')
""")

    app_repo = ramble.repository.Repo(
        str(app_repo_dir), object_type=ramble.repository.ObjectTypes.applications
    )
    mutable_applications.put_first(app_repo)

    mod_repo_dir = tmp_path / "mod_repo"
    mod_repo_dir.mkdir()
    (mod_repo_dir / "repo.yaml").write_text("repo:\n  namespace: extra_mod_repo\n")
    mod_dir1 = mod_repo_dir / "modifiers" / "directive-test-mod"
    mod_dir1.mkdir(parents=True)
    with open(str(mod_dir1 / "modifier.py"), "w", encoding="utf-8") as f:
        f.write("""from ramble.modkit import *
class DirectiveTestMod(BasicModifier):
    name = "directive-test-mod"
    mode('standard', description='Standard mode')
""")
    mod_repo = ramble.repository.Repo(
        str(mod_repo_dir), object_type=ramble.repository.ObjectTypes.modifiers
    )
    mock_modifiers.put_first(mod_repo)

    with ramble.workspace.create(workspace_name) as ws:
        ws.write()
        config_path = os.path.join(ws.config_dir, ramble.workspace.CONFIG_FILE_NAME)
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("""
ramble:
  variables:
    mpi_command: 'mpirun'
    batch_submit: 'batch_submit'
    processes_per_node: '1'
    n_ranks: '1'
  applications:
    edge-case-app:
      variants:
        inject_modifiers_from_directives: 'False'
      workloads:
        test:
          experiments:
            exp1:
              variables:
                env_name: 'test'
            exp2:
              variants:
                inject_modifiers_from_directives: 'True'
""")
        ws._re_read()
        experiment_set = ws.build_experiment_set()

        # Test string 'False'
        exp1 = experiment_set.get_experiment("edge-case-app.test.exp1")
        assert "directive-test-mod" not in [m.name for m in exp1._modifier_instances]

        # Test string 'True'
        exp2 = experiment_set.get_experiment("edge-case-app.test.exp2")
        assert "directive-test-mod" in [m.name for m in exp2._modifier_instances]

        # Test KeyError
        # Force KeyError by mocking value()
        import unittest.mock

        exp3 = experiment_set.get_experiment("edge-case-app.test.exp2")
        original_value = exp3.experiment_variants(allow_caching=False).__class__.value

        def mock_value(self, name):
            if name == "inject_modifiers_from_directives":
                raise KeyError("Mock KeyError")
            return original_value(self, name)  # pragma: no cover

        with unittest.mock.patch.object(
            exp3.experiment_variants(allow_caching=False).__class__, "value", mock_value
        ):
            exp3.build_modifier_instances()
            assert "directive-test-mod" in [m.name for m in exp3._modifier_instances]
