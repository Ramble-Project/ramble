# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import shutil
import tempfile
import unittest
from unittest import mock

import llnl.util.filesystem as fs

import ramble.workspace
from ramble.filters import Filters
from ramble.pipeline import PushDeploymentPipeline


class TestPushDeploymentPipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.workspace = ramble.workspace.Workspace(self.test_dir)
        self.deployment_name = "test_deployment"
        self.deployment_path = os.path.join(
            self.workspace.root, "deployments", self.deployment_name
        )
        self.workspace.deployment = self.deployment_name

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_complete_copies_inventory_files(self):
        # Create dummy inventory files
        inventory_file = os.path.join(self.workspace.root, self.workspace.inventory_file_name)
        hash_file = os.path.join(self.workspace.root, self.workspace.hash_file_name)
        metadata_file = os.path.join(self.workspace.root, ramble.workspace.METADATA_FILE_NAME)

        with open(inventory_file, "w", encoding="utf-8") as f:
            f.write("inventory")
        with open(hash_file, "w", encoding="utf-8") as f:
            f.write("hash")
        with open(metadata_file, "w", encoding="utf-8") as f:
            f.write("metadata")

        pipeline = PushDeploymentPipeline(
            self.workspace,
            filters=Filters([]),
            deployment_name=self.deployment_name,
            create_tar=False,
        )
        pipeline._deployment_files = list
        pipeline._construct_experiment_hashes = lambda: False
        with mock.patch("ramble.expander.Expander.expand_var", return_value=self.deployment_name):
            pipeline._execute()
        pipeline._complete()

        # Check if the files were copied
        self.assertTrue(
            os.path.exists(os.path.join(self.deployment_path, self.workspace.inventory_file_name))
        )
        self.assertTrue(
            os.path.exists(os.path.join(self.deployment_path, self.workspace.hash_file_name))
        )
        self.assertTrue(
            os.path.exists(os.path.join(self.deployment_path, ramble.workspace.METADATA_FILE_NAME))
        )

    def test_copy_tree_relative_path(self):
        from ramble.pipeline import _copy_tree

        src_dir = os.path.join(self.test_dir, "src")
        os.makedirs(os.path.join(src_dir, "nested", "subdir"))
        file_path = os.path.join(src_dir, "nested", "subdir", "test.txt")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("hello")

        with fs.working_dir(self.test_dir):
            _copy_tree("src", "dest")
            self.assertTrue(os.path.isfile(os.path.join("dest", "nested", "subdir", "test.txt")))

    def test_deployment_files_yields_correct_paths(self):
        pipeline = PushDeploymentPipeline(
            self.workspace,
            filters=Filters([]),
            deployment_name=self.deployment_name,
            create_tar=False,
        )
        os.makedirs(os.path.join(self.deployment_path, "sub"))
        dummy_file = os.path.join(self.deployment_path, "sub", "file.txt")
        with open(dummy_file, "w", encoding="utf-8") as f:
            f.write("data")

        files = list(pipeline._deployment_files())
        self.assertEqual(files, [dummy_file])

    def test_complete_uploads_files_with_upload_url(self):
        remote_dir = os.path.join(self.test_dir, "remote_upload")
        upload_url = f"file://{remote_dir}"

        nested_rel = os.path.join(self.deployment_path.lstrip(os.sep), "sub", "file.txt")
        dummy_file = os.path.join(self.deployment_path, nested_rel)
        os.makedirs(os.path.dirname(dummy_file), exist_ok=True)
        with open(dummy_file, "w", encoding="utf-8") as f:
            f.write("data")

        pipeline = PushDeploymentPipeline(
            self.workspace,
            filters=Filters([]),
            deployment_name=self.deployment_name,
            create_tar=False,
            upload_url=upload_url,
        )
        pipeline._construct_experiment_hashes = lambda: False
        with mock.patch("ramble.expander.Expander.expand_var", return_value=self.deployment_name):
            pipeline._execute()
        with mock.patch("ramble.pipeline._upload_file") as mock_upload:
            pipeline._complete()

        expected_dest = os.path.join(upload_url + "/" + self.deployment_name, nested_rel)
        mock_upload.assert_any_call(dummy_file, expected_dest)
