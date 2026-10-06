# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from typing import Dict
from unittest.mock import MagicMock, patch

import pytest

import ramble.config
import ramble.pipeline
import ramble.workspace
from ramble.main import RambleCommand
from ramble.pkg_man.builtin import spack_lightweight
from ramble.test.mock_spack_runner import MockSpackRunner
from ramble.uploader import (
    BigQueryUploader,
    ConfigError,
    SQLiteUploader,
    _prepare_data,
    format_data,
    upload_results,
)

pytestmark = pytest.mark.usefixtures("mutable_config", "mutable_mock_workspace_path")

_empty_results: Dict[str, list] = {"experiments": []}

workspace = RambleCommand("workspace")


@pytest.mark.parametrize(
    "upload_uri,upload_type,results,expected_err_msg",
    [
        (None, None, _empty_results, "No upload type"),
        (None, "UnknownUploader", _empty_results, "Upload type UnknownUploader is not valid"),
        (None, "BigQuery", _empty_results, "No upload URI"),
        ("fake-zeppelin", "PrintOnly", [], "Does not contain valid data to upload"),
    ],
)
def test_upload_results_errs(upload_uri, upload_type, results, expected_err_msg):
    with ramble.config.override("config:upload", {"uri": upload_uri, "type": upload_type}):
        with pytest.raises(ConfigError, match=expected_err_msg):
            upload_results(results)


@pytest.mark.maybeslow
def test_data_preparation(request, mock_applications):
    ws_name = request.node.name
    global_args = ["-w", ws_name]

    app_name = "zlib"
    wl_name = "ensure_installed"

    with ramble.workspace.create(ws_name) as ws:
        workspace(
            "manage",
            "experiments",
            app_name,
            "--wf",
            wl_name,
            "-V",
            "package_manager=spack",
            "-v",
            "n_ranks=1",
            "-v",
            "n_nodes=1",
            "-v",
            "processes_per_node=1",
            "--default-variable-value",
            "1",
            global_args=global_args,
        )

        with patch.object(spack_lightweight, "SpackRunner", return_value=MockSpackRunner()):
            workspace("concretize", global_args=global_args)
            workspace("setup", global_args=global_args)

            filters = ramble.filters.Filters()
            ap = ramble.pipeline.AnalyzePipeline(ws, filters)
            ap._prepare()
            ap._execute()

            formatted_data = ramble.uploader.format_data(ws.results)
            uri = "not_used_in_test"
            (
                exp_table_id,
                exps_to_insert,
                fom_table_id,
                foms_to_insert,
                metadata_table_id,
                metadata_to_insert,
                software_table_id,
                software_to_insert,
            ) = ramble.uploader._prepare_data(formatted_data, uri)

            assert len(software_to_insert) == 1
            software = software_to_insert[0]
            assert software["name"] == "zlib"
            assert software["version"] == "1.2.11"
            assert software["compiler"] == "gcc"
            assert software["compiler_version"] == "9.3.0"
            assert software["target"] == "x86_64"
            assert software["variants"] == "none"
            assert software["experiment_name"] == "zlib.ensure_installed.generated"


@patch("google.cloud.bigquery.Client")
def test_create_tables_dataset_exists(mock_bigquery_client):
    # Arrange
    mock_client = MagicMock()
    mock_bigquery_client.return_value = mock_client

    # Configure mock for client.query().result().total_rows and list(results)[0].value
    mock_row = MagicMock()
    mock_row.value = "1.0"  # Example schema version

    mock_results_iterable = [mock_row]  # This is the data that the iterator will yield

    mock_results = MagicMock()
    mock_results.total_rows = 1
    # Make mock_results.__iter__ return a fresh iterator each time it's called
    mock_results.__iter__.side_effect = lambda: iter(mock_results_iterable)

    mock_query_job = MagicMock()
    mock_query_job.result.return_value = mock_results
    mock_client.query.return_value = mock_query_job

    uploader = BigQueryUploader()
    uri = "my-project.my_dataset"
    uploader.upload_metadata = MagicMock()

    # Act
    uploader.create_tables(uri)

    # Assert
    mock_client.get_dataset.assert_called_with(uri)
    mock_client.create_dataset.assert_not_called()
    assert mock_client.get_table.call_count == len(uploader.schema)
    mock_client.create_table.assert_not_called()
    uploader.upload_metadata.assert_not_called()


@patch("google.cloud.bigquery.Client")
def test_create_tables_dataset_does_not_exist(mock_bigquery_client):
    # Arrange
    from google.cloud.exceptions import NotFound

    mock_client = MagicMock()
    mock_client.get_dataset.side_effect = NotFound("testing")

    # Configure mock for client.query().result().total_rows = 0
    mock_query_job = MagicMock()
    mock_results = MagicMock()
    mock_results.total_rows = 0
    mock_query_job.result.return_value = mock_results
    mock_client.query.return_value = mock_query_job

    mock_client.get_table.side_effect = NotFound("testing")  # Tables will be created
    mock_bigquery_client.return_value = mock_client
    uploader = BigQueryUploader()
    uploader.upload_metadata = MagicMock()
    uri = "my-project.my_dataset"

    # Act
    uploader.create_tables(uri)

    # Assert
    mock_client.get_dataset.assert_called_with(uri)
    mock_client.create_dataset.assert_called_with(uri)
    assert mock_client.create_table.call_count == len(uploader.schema)
    uploader.upload_metadata.assert_called_with(uri)


@pytest.fixture
def mock_results_with_metadata():
    results = {
        "experiments": [
            {
                "name": "exp1",
                "RAMBLE_STATUS": "SUCCESS",
                "RAMBLE_VARIABLES": {"workspace_name": "test_ws"},
                "application_name": "app1",
                "workload_name": "workload1",
                "n_nodes": 1,
                "processes_per_node": 1,
                "n_ranks": 1,
                "n_threads": 1,
                "CONTEXTS": [],
                "SOFTWARE": {},
            }
        ],
        "workspace_hash": "hash123",
        "metadata": {"metadata": {"key1": "value1", "key2": 123}},
    }
    return results


@pytest.mark.usefixtures("mutable_config")
def test_experiment_metadata_preparation(mock_results_with_metadata, mutable_config):
    uri = "test_dataset"

    # Mock Config to avoid errors and set up upload
    upload_config = {"uri": uri, "type": "PrintOnly", "push_failed": False}
    with ramble.config.override("config:upload", upload_config):
        formatted_data = format_data(mock_results_with_metadata)

        assert hasattr(formatted_data, "metadata")
        assert formatted_data.metadata == mock_results_with_metadata["metadata"]

        (
            exp_table_id,
            exps_to_insert,
            fom_table_id,
            foms_to_insert,
            metadata_table_id,
            metadata_to_insert,
            software_table_id,
            software_to_insert,
        ) = _prepare_data(formatted_data, uri)

        assert len(metadata_to_insert) == 2  # 2 metadata items * 1 experiment

        # Check actual values
        keys = {item["key"] for item in metadata_to_insert}
        assert "key1" in keys
        assert "key2" in keys

        for item in metadata_to_insert:
            if item["key"] == "key1":
                assert item["value"] == "value1"
            elif item["key"] == "key2":
                assert item["value"] == "123"  # Should be stringified

            assert "experiment_name" not in item
            assert "experiment_id" in item
            assert "timestamp" in item
            assert isinstance(item["timestamp"], str)


def test_sqlite_uploader_create_tables_and_upload(tmpdir, mock_results_with_metadata):
    import os
    import sqlite3

    uri = str(tmpdir / "test_ramble_upload.db")
    uploader = SQLiteUploader()
    upload_config = {"uri": uri, "type": "SQLite", "push_failed": False}

    with ramble.config.override("config:upload", upload_config):
        formatted_data = format_data(mock_results_with_metadata)

        # Test create tables
        uploader.create_tables(uri)
        assert os.path.exists(uri)

        conn = sqlite3.connect(uri)
        cursor = conn.cursor()

        # Verify tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = ["experiments", "foms", "metadata", "experiments_metadata", "software"]
        for table in expected_tables:
            assert table in tables

        # Verify metadata was uploaded upon table creation
        cursor.execute("SELECT key FROM metadata")
        metadata_keys = [row[0] for row in cursor.fetchall()]
        assert "db_schema_version" in metadata_keys
        assert "ramble_version" in metadata_keys

        # Test uploading results
        uploader.perform_upload(uri, formatted_data)

        # Verify experiments were inserted
        cursor.execute("SELECT * FROM experiments")
        rows = cursor.fetchall()
        assert len(rows) == 1

        # Verify experiments_metadata was inserted
        cursor.execute("SELECT * FROM experiments_metadata")
        rows = cursor.fetchall()
        assert len(rows) == 2  # mock_results_with_metadata has 2 keys

        conn.close()


def test_sqlite_uploader_perform_upload_no_db(tmpdir, mock_results_with_metadata, capsys):

    uri = str(tmpdir / "does_not_exist.db")
    uploader = SQLiteUploader()
    upload_config = {"uri": uri, "type": "SQLite", "push_failed": False}

    with ramble.config.override("config:upload", upload_config):
        formatted_data = format_data(mock_results_with_metadata)

        # Test uploading results to non-existent DB dies
        with pytest.raises(SystemExit):
            uploader.perform_upload(uri, formatted_data)

        captured = capsys.readouterr()
        assert "does not exist" in captured.err
        assert "ramble data create-db" in captured.err


def test_sqlite_uploader_create_tables_with_existing(tmpdir, mock_results_with_metadata, capsys):
    import sqlite3

    import ramble.util.logger

    uri = str(tmpdir / "UNIT_TEST_DATABASE.db")
    uploader = SQLiteUploader()
    upload_config = {"uri": uri, "type": "SQLite", "push_failed": False}

    with ramble.config.override("config:upload", upload_config):
        # Create initially
        uploader.create_tables(uri)

        # Modify schema version dynamically to verify mismatch warning
        conn = sqlite3.connect(uri)
        cursor = conn.cursor()

        cursor.execute("UPDATE metadata SET value='999.0' WHERE key='fom_schema_version'")
        conn.commit()
        conn.close()

        # Call again to trigger existing table and schema mismatch logs
        uploader.create_tables(uri)
        captured = capsys.readouterr()

        assert "already exists" in captured.out + captured.err
        assert "does not match current version" in captured.out + captured.err


def test_sqlite_uploader_chunked_upload_errors(tmpdir, mock_results_with_metadata, capsys):
    uri = str(tmpdir / "test_ramble_upload_errors.db")
    uploader = SQLiteUploader()
    upload_config = {"uri": uri, "type": "SQLite", "push_failed": False}

    with ramble.config.override("config:upload", upload_config):
        uploader.create_tables(uri)

        formatted_data = format_data(mock_results_with_metadata)
        (
            exp_table_id,
            exps_to_insert,
            fom_table_id,
            foms_to_insert,
            metadata_table_id,
            metadata_to_insert,
            software_table_id,
            software_to_insert,
        ) = ramble.uploader._prepare_data(formatted_data, uri)

        # Trigger issue during upload insert by injecting bad data format that breaks SQLite schema
        bad_exps_to_insert = exps_to_insert.copy()

        # Test unknown schema missing
        uploader.schema = []
        uploader.chunked_upload(exp_table_id, bad_exps_to_insert, uri)
        captured = capsys.readouterr()
        assert "Could not find a valid schema" in captured.err


def test_fom_validation_fails_with_none():
    """Test that FOM validation fails when value is None"""
    import jsonschema

    from ramble.schema.fom import fom_schema, fom_schema_version
    from ramble.uploader import validate_data

    bad_fom = {
        "name": "test_fom",
        "value": None,  # This should be a string according to schema
        "unit": "s",
        "origin": "test",
        "origin_type": "test",
        "context": "test",
        "experiment_id": 1,
        "experiment_name": "test_exp",
    }

    schema = fom_schema[fom_schema_version]

    with pytest.raises(jsonschema.exceptions.ValidationError):
        validate_data(bad_fom, schema)


@pytest.mark.parametrize(
    "contexts,expected_node_type",
    [
        (
            [
                {
                    "foms": [
                        {"name": "machine-type", "value": "c2-standard-60"},
                        {
                            "name": "Model name",
                            "value": "Intel(R) Xeon(R) Gold 6268CL CPU @ 2.80GHz",
                        },
                    ]
                }
            ],
            "c2-standard-60",
        ),
        (
            [
                {
                    "foms": [
                        {
                            "name": "Model name",
                            "value": "Intel(R) Xeon(R) Gold 6268CL CPU @ 2.80GHz",
                        },
                        {"name": "machine-type", "value": "c2-standard-60"},
                    ]
                }
            ],
            "c2-standard-60",
        ),
        (
            [
                {"foms": [{"name": "machine-type", "value": "c2-standard-60"}]},
                {
                    "foms": [
                        {
                            "name": "Model name",
                            "value": "Intel(R) Xeon(R) Gold 6268CL CPU @ 2.80GHz",
                        }
                    ]
                },
            ],
            "c2-standard-60",
        ),
        (
            [
                {
                    "foms": [
                        {
                            "name": "Model name",
                            "value": "Intel(R) Xeon(R) Gold 6268CL CPU @ 2.80GHz",
                        }
                    ]
                }
            ],
            "Intel(R) Xeon(R) Gold 6268CL CPU @ 2.80GHz",
        ),
        (
            [{"foms": [{"name": "other_fom", "value": "123"}]}],
            ramble.uploader.default_node_type_val,
        ),
    ],
)
def test_determine_node_type(contexts, expected_node_type):
    """Test that determine_node_type prioritizes machine-type
    over Model name regardless of order.
    """
    import types

    from ramble.uploader import default_node_type_val, determine_node_type

    exp = types.SimpleNamespace(node_type=default_node_type_val)
    determine_node_type(exp, contexts)
    assert exp.node_type == expected_node_type
