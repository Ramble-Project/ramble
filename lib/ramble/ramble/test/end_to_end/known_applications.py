# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from unittest.mock import patch

import deprecation
import pytest

import ramble.error
import ramble.filters
import ramble.pipeline
import ramble.repository
import ramble.workspace
from ramble.main import RambleCommand
from ramble.pkg_man.builtin import spack_lightweight
from ramble.test.mock_spack_runner import MockSpackRunner

# everything here uses the mock_workspace_path
pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

workspace = RambleCommand("workspace")
config = RambleCommand("config")


@pytest.mark.long
@deprecation.fail_if_not_removed
@pytest.mark.filterwarnings("ignore:invalid escape sequence:DeprecationWarning")
def test_known_applications(application, package_manager, mock_file_auto_create, workspace_name):
    setup_type = ramble.pipeline.pipelines.setup
    analyze_type = ramble.pipeline.pipelines.analyze
    archive_type = ramble.pipeline.pipelines.archive
    setup_cls = ramble.pipeline.pipeline_class(setup_type)
    analyze_cls = ramble.pipeline.pipeline_class(analyze_type)
    archive_cls = ramble.pipeline.pipeline_class(archive_type)
    filters = ramble.filters.Filters()

    ws_name = workspace_name

    with patch.object(spack_lightweight, "SpackRunner", return_value=MockSpackRunner()):
        with ramble.workspace.create(ws_name) as ws:
            ws.write()
            args = [
                application,
                "-v",
                "n_nodes=1",
                "-v",
                "n_ranks=1",
                "-w",
                "test_workload",
                "--default-variable-value",
                "1",
            ]
            if package_manager == "user-managed":
                app_inst = ramble.repository.get(application)
                for pkg in app_inst.required_packages:
                    args.append("-v")
                    args.append(f"{pkg}_path='/not/real/path'")

            else:
                args.append("-V")
                args.append(f"package_manager={package_manager}")

            workspace("manage", "experiments", *args, global_args=["-w", ws_name])

            try:
                ws._re_read()
                ws.concretize()
                ws._re_read()

                if package_manager != "user-managed":
                    with open(ws.config_file_path, encoding="utf-8") as f:
                        data = f.read()
                        assert package_manager in data

                ws.dry_run = True
                setup_pipeline = setup_cls(ws, filters)
                setup_pipeline.run()
                analyze_pipeline = analyze_cls(ws, filters)
                analyze_pipeline.run()
                archive_pipeline = archive_cls(ws, filters, create_tar=True)
                archive_pipeline.run()
            except ramble.error.ObjectValidationError:
                # TODO: should figure out a better approach to configure the variables correctly.
                pytest.skip(
                    reason=(
                        "Validation failure is skipped, as that "
                        "usually indicates variables are not "
                        "set properly."
                    )
                )


@pytest.mark.long
@deprecation.fail_if_not_removed
@pytest.mark.filterwarnings("ignore:invalid escape sequence:DeprecationWarning")
def test_known_workflow_managers(
    workflow_manager, mock_file_auto_create, mutable_config, workspace_name
):
    setup_type = ramble.pipeline.pipelines.setup
    analyze_type = ramble.pipeline.pipelines.analyze
    archive_type = ramble.pipeline.pipelines.archive
    setup_cls = ramble.pipeline.pipeline_class(setup_type)
    analyze_cls = ramble.pipeline.pipeline_class(analyze_type)
    archive_cls = ramble.pipeline.pipeline_class(archive_type)
    filters = ramble.filters.Filters()

    with patch.object(spack_lightweight, "SpackRunner", return_value=MockSpackRunner()):
        with ramble.workspace.create(workspace_name) as ws:
            ws.write()
            args = [
                "gromacs",
                "-v",
                "n_nodes=1",
                "-v",
                "n_ranks=1",
                "-w",
                "test_workload",
                "--default-variable-value",
                "1",
            ]
            # Handle `user-managed` package manager
            app_inst = ramble.repository.get("gromacs")
            for pkg in app_inst.required_packages:
                args.append("-v")
                args.append(f"{pkg}_path='/not/real/path'")

            args.append("-V")
            args.append(f"workflow_manager={workflow_manager}")

            workspace("manage", "experiments", *args, global_args=["-w", workspace_name])

            # Handle workflow manager. Remove variables defined in the workflow to
            # ensure we catch invalid configurations.
            if workflow_manager != "None":
                ws._re_read()
                wm_inst = ramble.repository.get(
                    workflow_manager,
                    object_type=ramble.repository.ObjectTypes.workflow_managers,
                )
                for var in wm_inst.object_variables[frozenset()]:
                    config("remove", f"variables:{var.name}", global_args=["-w", workspace_name])

                for var_name in wm_inst.templates:
                    config("remove", f"variables:{var_name}", global_args=["-w", workspace_name])

            ws._re_read()
            ws.concretize()
            ws._re_read()

            with open(ws.config_file_path, encoding="utf-8") as f:
                data = f.read()
                assert workflow_manager in data

            ws.dry_run = True
            setup_pipeline = setup_cls(ws, filters)
            setup_pipeline.run()
            analyze_pipeline = analyze_cls(ws, filters)
            analyze_pipeline.run()
            archive_pipeline = archive_cls(ws, filters, create_tar=True)
            archive_pipeline.run()
