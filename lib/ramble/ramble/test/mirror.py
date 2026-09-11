# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import hashlib
import os
import sys
from typing import FrozenSet

import pytest

from llnl.util.filesystem import resolve_link_target_relative_to_the_link

import ramble.caches
import ramble.filters
import ramble.mirror
import ramble.pipeline
import ramble.repository
import ramble.workspace

import spack.util.executable

pytestmark = [
    pytest.mark.skipif(sys.platform == "win32", reason="does not run on windows"),
    pytest.mark.usefixtures(
        "tmpdir",
        "tmpdir_factory",
        "mutable_config",
        "mutable_mock_workspace_path",
        "mutable_mock_apps_repo",
    ),
]

_FS: FrozenSet[str] = frozenset()


class MockFetcher:
    """Mock fetcher object which implements the necessary functionality for
    testing MirrorCache
    """

    @staticmethod
    def archive(dst):
        with open(dst, "w", encoding="utf-8"):
            pass


@pytest.mark.regression("14067")
def test_mirror_cache_symlinks(tmpdir):
    """Confirm that the cosmetic symlink created in the mirror cache (which may
    be relative) targets the storage path correctly.
    """
    cosmetic_path = "zlib/zlib-1.2.11.tar.gz"
    global_path = "_uboyt-cache/archive/c3/c3e5.tar.gz"
    cache = ramble.caches.MirrorCache(str(tmpdir))
    reference = ramble.mirror.MirrorReference(cosmetic_path, global_path)

    cache.store(MockFetcher(), reference.storage_path)
    cache.symlink(reference)

    link_target = resolve_link_target_relative_to_the_link(
        os.path.join(cache.root, reference.cosmetic_path)
    )
    assert os.path.exists(link_target)
    assert os.path.normpath(link_target) == os.path.join(cache.root, reference.storage_path)


def test_mirror_str_and_repr():
    m = ramble.mirror.Mirror("http://fetch.com", "http://push.com", name="my_mirror")
    assert str(m) == '[Mirror "my_mirror" (fetch: http://fetch.com, push: http://push.com)]'
    assert (
        repr(m)
        == "Mirror(fetch_url='http://fetch.com', push_url='http://push.com', name='my_mirror')"
    )


# Create an archive for the test input, with the correct file name
def create_archive(archive_dir, app_cls):
    tar = spack.util.executable.which("tar", required=True)

    for inputs_dict in app_cls.inputs.values():
        for input_name, conf in inputs_dict.items():
            expand = conf.get("expand", True)
            url = conf["url"]
            if expand:
                archive_dir.ensure(input_name, dir=True)
                archive_name = os.path.basename(url)
                test_file_path = str(archive_dir.join(input_name, "input-file"))
                with open(test_file_path, "w+", encoding="utf-8") as f:
                    f.write("Input File\n")

                with archive_dir.as_cwd():
                    tar("-czf", archive_name, input_name)
                    with open(archive_name, "rb") as f:
                        conf["sha256"] = hashlib.sha256(f.read()).hexdigest()
            else:
                filename = os.path.basename(url)
                with open(filename, "w+", encoding="utf-8") as f:
                    f.write("Input file\n")

                with open(filename, "rb") as f:
                    conf["sha256"] = hashlib.sha256(f.read()).hexdigest()


def check_mirror(mirror_path, app_name, app_inst):
    app_inst._inputs_and_fetchers()

    for input_name, conf in app_inst._input_fetchers.items():
        test_name = f"{input_name}"
        fetcher = conf["fetcher"]
        if fetcher.extension:
            test_name = f"{test_name}.{fetcher.extension}"
        assert os.path.exists(os.path.join(mirror_path, "inputs", app_name, test_name))


@pytest.mark.parametrize("app_name", ["input-test"])
def test_mirror_create(tmpdir, mutable_mock_workspace_path, app_name, tmpdir_factory):

    test_config = f"""
ramble:
  variables:
    mpi_command: 'mpirun -n {{n_ranks}}'
    batch_submit: '{{execute_experiment}}'
  applications:
    {app_name}:
      workloads:
        test:
          experiments:
            unit-test:
              variables:
                n_ranks: '1'
                n_nodes: '1'
                processes_per_node: '1'
  software:
    packages: {{}}
    environments: {{}}
"""

    archive_dir = tmpdir_factory.mktemp("mock-archives-dir")
    mirror_dir = tmpdir_factory.mktemp(f"mock-{app_name}-mirror")

    pipeline_type = ramble.pipeline.pipelines.mirror

    mirror_pipeline_cls = ramble.pipeline.pipeline_class(pipeline_type)
    filters = ramble.filters.Filters()

    with archive_dir.as_cwd():
        app_type = ramble.repository.ObjectTypes.applications
        app_cls = ramble.repository.paths[app_type].get_obj_class(app_name)
        create_archive(archive_dir, app_cls)

        # Create workspace
        ws_name = f"workspace-mirror-{app_name}"

        with ramble.workspace.create(ws_name) as workspace:
            workspace.write()
            config_path = os.path.join(workspace.config_dir, ramble.workspace.CONFIG_FILE_NAME)
            with open(config_path, "w+", encoding="utf-8") as f:
                f.write(test_config)
            workspace._re_read()
            mirror_pipeline = mirror_pipeline_cls(workspace, filters, mirror_path=str(mirror_dir))
            mirror_pipeline.run()

        app_inst = app_cls("test")
        app_inst.set_variables_and_variants({"workload_name": "test"}, {}, None, None)
        check_mirror(str(mirror_dir), app_name, app_inst)
