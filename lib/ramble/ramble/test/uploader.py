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
        (
            None,
            "UnknownUploader",
            _empty_results,
            "'UnknownUploader' is not one of",
        ),
        (None, "BigQuery", _empty_results, "No upload URI"),
        ("fake-zeppelin", "PrintOnly", [], "Does not contain valid data to upload"),
    ],
)
def test_upload_results_errs(upload_uri, upload_type, results, expected_err_msg):
    upload_cfg = {}
    if upload_uri is not None:
        upload_cfg["uri"] = upload_uri
    if upload_type is not None:
        upload_cfg["type"] = upload_type
    with pytest.raises(ConfigError, match=expected_err_msg):
        with ramble.config.override("config:upload", upload_cfg):
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

    uploader = BigQueryUploader()
    mock_rows = []
    for table_def in uploader.schema:
        mock_row = MagicMock()
        mock_row.key = table_def["metadata_key"]
        mock_row.value = "1.0"  # Example schema version
        mock_rows.append(mock_row)

    mock_results = MagicMock()
    mock_results.total_rows = len(mock_rows)
    mock_results.__iter__.side_effect = lambda: iter(mock_rows)

    mock_query_job = MagicMock()
    mock_query_job.result.return_value = mock_results
    mock_client.query.return_value = mock_query_job

    uri = "my-project.my_dataset"
    uploader.upload_metadata = MagicMock()

    # Act
    uploader.create_tables(uri)

    # Assert
    mock_client.get_dataset.assert_called_with(uri)
    mock_client.create_dataset.assert_not_called()
    expected_query = f"SELECT key, value FROM `{uri}.metadata` ORDER BY timestamp ASC"
    mock_client.query.assert_called_once_with(expected_query)
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
        "fom_type": "TIME",
        "better_direction": "LOWER",
        "context": "test",
        "experiment_id": 1,
        "experiment_name": "test_exp",
    }

    schema = fom_schema[fom_schema_version]

    with pytest.raises(jsonschema.exceptions.ValidationError):
        validate_data(bad_fom, schema)


def test_fom_type_and_better_direction_upload(tmpdir):
    """Test that fom_type and better_direction are extracted, validated, and uploaded."""
    import sqlite3

    from ramble.util.foms import FomType

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
                "CONTEXTS": [
                    {
                        "name": "null",
                        "foms": [
                            {
                                "name": "runtime",
                                "value": "1.23",
                                "units": "s",
                                "origin": "app1",
                                "origin_type": "application",
                                "fom_type": FomType.TIME.to_dict(),
                            },
                            {
                                "name": "bw",
                                "value": "456.7",
                                "units": "GB/s",
                                "origin": "app1",
                                "origin_type": "application",
                                "fom_type": {
                                    "name": "THROUGHPUT",
                                    "better_direction": "HIGHER",
                                },
                            },
                            {
                                "name": "legacy_fom",
                                "value": "42",
                                "units": "",
                                "origin": "app1",
                                "origin_type": "application",
                            },
                        ],
                    }
                ],
                "SOFTWARE": {},
            }
        ],
        "workspace_hash": "hash123",
    }

    uri = str(tmpdir / "test_fom_type_upload.db")
    uploader = SQLiteUploader()
    upload_config = {"uri": uri, "type": "SQLite", "push_failed": False}

    with ramble.config.override("config:upload", upload_config):
        formatted_data = format_data(results)
        _, _, _, foms_to_insert, _, _, _, _ = _prepare_data(formatted_data, uri)

        assert len(foms_to_insert) == 3
        foms_by_name = {f["name"]: f for f in foms_to_insert}

        assert foms_by_name["runtime"]["fom_type"] == "TIME"
        assert foms_by_name["runtime"]["better_direction"] == "LOWER"

        assert foms_by_name["bw"]["fom_type"] == "THROUGHPUT"
        assert foms_by_name["bw"]["better_direction"] == "HIGHER"

        assert foms_by_name["legacy_fom"]["fom_type"] == "UNDEFINED"
        assert foms_by_name["legacy_fom"]["better_direction"] == "INDETERMINATE"

        uploader.create_tables(uri)
        uploader.perform_upload(uri, formatted_data)

        conn = sqlite3.connect(uri)
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name, fom_type, better_direction FROM foms ORDER BY name")
            rows = cursor.fetchall()
            assert rows == [
                ("bw", "THROUGHPUT", "HIGHER"),
                ("legacy_fom", "UNDEFINED", "INDETERMINATE"),
                ("runtime", "TIME", "LOWER"),
            ]
        finally:
            conn.close()


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


def test_check_schema_upgrade():
    from ramble.uploader import check_schema_upgrade, check_schema_upgrade_chain

    base_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["name", "value"],
    }

    # Safe upgrade: adding nullable columns
    safe_new_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "string"},
            "note": {"type": "string"},
            "fom_type": {"type": "string"},
            "better_direction": {"type": "string"},
        },
        "required": ["name", "value"],
    }
    added = check_schema_upgrade(base_schema, safe_new_schema, "foms")
    assert added == ["fom_type", "better_direction"]

    # Unsafe: removed column
    removed_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "string"},
        },
        "required": ["name", "value"],
    }
    with pytest.raises(ValueError, match="columns removed"):
        check_schema_upgrade(base_schema, removed_schema, "foms")

    # Unsafe: changed type
    type_changed_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "number"},
            "note": {"type": "string"},
        },
        "required": ["name", "value"],
    }
    with pytest.raises(ValueError, match="changed type/format"):
        check_schema_upgrade(base_schema, type_changed_schema, "foms")

    # Unsafe: existing optional column became required
    tightened_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "string"},
            "note": {"type": "string"},
        },
        "required": ["name", "value", "note"],
    }
    with pytest.raises(ValueError, match="existing columns became required"):
        check_schema_upgrade(base_schema, tightened_schema, "foms")

    # Unsafe: newly added column is required
    required_added_schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "string"},
            "note": {"type": "string"},
            "fom_type": {"type": "string"},
        },
        "required": ["name", "value", "fom_type"],
    }
    with pytest.raises(ValueError, match="newly added columns cannot be required"):
        check_schema_upgrade(base_schema, required_added_schema, "foms")

    # Chain validation: catches intermediate breaking change
    # (0.1 -> 0.2 adds 'temp', 0.2 -> 0.3 drops 'temp')
    v0_2_with_temp = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "value": {"type": "string"},
            "note": {"type": "string"},
            "temp": {"type": "string"},
        },
        "required": ["name", "value"],
    }
    broken_chain = {
        0.1: base_schema,
        0.2: v0_2_with_temp,
        0.3: safe_new_schema,
    }
    with pytest.raises(ValueError, match="columns removed: \\['temp'\\]"):
        check_schema_upgrade_chain(broken_chain, 0.1, 0.3, "foms")

    # Chain validation: missing upstream version in chain
    with pytest.raises(ValueError, match="missing schema definition in upgrade chain"):
        check_schema_upgrade_chain({0.2: safe_new_schema}, 0.1, 0.2, "foms")

    # Verify all built-in table schemas in Uploader.schema form valid upgrade chains
    for table_def in ramble.uploader.Uploader.schema:
        versions = sorted(float(v) for v in table_def["schema"])
        check_schema_upgrade_chain(
            table_def["schema"],
            versions[0],
            float(table_def["version"]),
            table_def["table"],
        )


def test_sqlite_upgrade_db_safe_and_cli(tmpdir, monkeypatch, mock_results_with_metadata, capsys):
    import copy
    import sqlite3

    data_cmd = RambleCommand("data")
    uri = str(tmpdir / "test_upgrade.db")
    upload_config = {"uri": uri, "type": "SQLite", "push_failed": False}

    with ramble.config.override("config:upload", upload_config):
        # 1. Create initial v0.1 database
        v0_1_schema = copy.deepcopy(SQLiteUploader.schema)
        for table_def in v0_1_schema:
            if table_def["table"] == "foms":
                table_def["version"] = 0.1
        monkeypatch.setattr(SQLiteUploader, "schema", v0_1_schema)
        data_cmd("create-db")

        conn = sqlite3.connect(uri)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO foms (name, value, unit, origin, origin_type, context, "
            "experiment_id, experiment_name) VALUES ('runtime', '1.5', 's', 'app', "
            "'application', 'null', 1, 'exp1')"
        )
        conn.commit()
        conn.close()

        # 2. Simulate bumping fom schema through a chain: v0.1 -> v0.2 -> v0.3
        new_schema = copy.deepcopy(SQLiteUploader.schema)
        for table_def in new_schema:
            if table_def["table"] == "foms":
                v0_2 = copy.deepcopy(table_def["schema"][0.1])
                v0_2["properties"]["fom_type"] = {"type": "string"}
                table_def["schema"][0.2] = v0_2

                v0_3 = copy.deepcopy(v0_2)
                v0_3["properties"]["better_direction"] = {"type": "string"}
                table_def["schema"][0.3] = v0_3
                table_def["version"] = 0.3

        monkeypatch.setattr(SQLiteUploader, "schema", new_schema)

        # Attempting to upload before running upgrade-db is rejected cleanly
        formatted_data = format_data(mock_results_with_metadata)
        with pytest.raises(SystemExit):
            SQLiteUploader().perform_upload(uri, formatted_data)
        assert "ramble data upgrade-db" in capsys.readouterr().err

        # 3. Run `ramble data upgrade-db -n` (dry run) and then `ramble data upgrade-db`
        dry_col_out = data_cmd("upgrade-db", "-n")
        assert "[Dry Run] Would add column 'fom_type'" in dry_col_out
        data_cmd("upgrade-db")

        # Subsequent upload succeeds after upgrade-db
        SQLiteUploader().perform_upload(uri, formatted_data)

        conn = sqlite3.connect(uri)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(foms)")
            cols = {row[1]: row[2] for row in cursor.fetchall()}
            assert "fom_type" in cols
            assert "better_direction" in cols

            # Existing row is preserved with NULL for new columns
            cursor.execute("SELECT name, value, fom_type, better_direction FROM foms")
            rows = cursor.fetchall()
            assert rows == [("runtime", "1.5", None, None)]

            # Metadata version updated to 0.3 and db_schema_version updated
            cursor.execute("SELECT value FROM metadata WHERE key = 'fom_schema_version'")
            assert cursor.fetchone()[0] == "0.3"
            cursor.execute("SELECT value FROM metadata WHERE key = 'db_schema_version'")
            assert cursor.fetchone()[0].startswith("fom-0.3_")
        finally:
            conn.close()

        # 4. Re-running upgrade-db (and --dry-run) is a safe no-op
        out = data_cmd("upgrade-db")
        assert "already up to date" in out
        dry_noop_out = data_cmd("upgrade-db", "--dry-run")
        assert "already up to date" in dry_noop_out

        # 5. Dropping a table & its metadata key, then running upgrade-db recreates both
        conn = sqlite3.connect(uri)
        try:
            cursor = conn.cursor()
            cursor.execute("DROP TABLE software")
            cursor.execute("DELETE FROM metadata WHERE key = 'software_db_schema_version'")
            cursor.execute("UPDATE metadata SET value = '0.2' WHERE key = 'fom_schema_version'")
            conn.commit()
        finally:
            conn.close()

        # Verify --dry-run reports planned changes without modifying the DB
        dry_out = data_cmd("upgrade-db", "--dry-run")
        assert "[Dry Run] Would create missing table software" in dry_out
        assert "[Dry Run] Would update metadata" in dry_out

        data_cmd("upgrade-db")

        conn = sqlite3.connect(uri)
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT count(name) FROM sqlite_master WHERE type='table' AND name='software'"
            )
            assert cursor.fetchone()[0] == 1
            cursor.execute("SELECT value FROM metadata WHERE key = 'software_db_schema_version'")
            assert cursor.fetchone()[0] == "0.1"
        finally:
            conn.close()


def test_sqlite_upgrade_db_errors(tmpdir, capsys):
    import copy
    import sqlite3

    uri = str(tmpdir / "does_not_exist.db")
    uploader = SQLiteUploader()

    # Non-existent DB fails
    with pytest.raises(SystemExit):
        uploader.upgrade_tables(uri)
    assert "does not exist" in capsys.readouterr().err

    # Create DB and test downgrade & unsafe schema rejection
    uri = str(tmpdir / "test_upgrade_errors.db")
    uploader.create_tables(uri)

    conn = sqlite3.connect(uri)
    cursor = conn.cursor()
    cursor.execute("UPDATE metadata SET value='not-a-float' WHERE key='fom_schema_version'")
    conn.commit()
    conn.close()

    with pytest.raises(SystemExit):
        uploader.upgrade_tables(uri)
    assert "Invalid upstream schema version 'not-a-float'" in capsys.readouterr().err

    conn = sqlite3.connect(uri)
    cursor = conn.cursor()
    cursor.execute("UPDATE metadata SET value='99.0' WHERE key='fom_schema_version'")
    conn.commit()
    conn.close()

    with pytest.raises(SystemExit):
        uploader.upgrade_tables(uri)
    assert "Cannot downgrade table 'foms'" in capsys.readouterr().err

    # Reset version to 0.1 and test broken upgrade chain (missing 0.1 in schema dict)
    conn = sqlite3.connect(uri)
    cursor = conn.cursor()
    cursor.execute("UPDATE metadata SET value='0.1' WHERE key='fom_schema_version'")
    conn.commit()
    conn.close()

    broken_chain_schema = copy.deepcopy(SQLiteUploader.schema)
    for table_def in broken_chain_schema:
        if table_def["table"] == "foms":
            table_def["schema"] = {0.2: table_def["schema"][0.1]}
            table_def["version"] = 0.2
    uploader.schema = broken_chain_schema

    with pytest.raises(SystemExit):
        uploader.upgrade_tables(uri)
    assert "missing schema definition in upgrade chain" in capsys.readouterr().err

    # Reset metadata version to match current schema version to test live DB checks directly
    cur_fom_ver = next(t["version"] for t in SQLiteUploader.schema if t["table"] == "foms")
    conn = sqlite3.connect(uri)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE metadata SET value=? WHERE key='fom_schema_version'",
        (str(cur_fom_ver),),
    )
    conn.commit()
    conn.close()

    # Test unsafe live column removal
    bad_schema = copy.deepcopy(SQLiteUploader.schema)
    for table_def in bad_schema:
        if table_def["table"] == "foms":
            cur_ver = table_def["version"]
            del table_def["schema"][cur_ver]["properties"]["unit"]
    uploader.schema = bad_schema

    with pytest.raises(SystemExit):
        uploader.upgrade_tables(uri)
    assert "columns removed: ['unit']" in capsys.readouterr().err

    # Test unsafe live column type change
    type_mismatch_schema = copy.deepcopy(SQLiteUploader.schema)
    for table_def in type_mismatch_schema:
        if table_def["table"] == "foms":
            cur_ver = table_def["version"]
            table_def["schema"][cur_ver]["properties"]["unit"]["type"] = "number"
    uploader.schema = type_mismatch_schema

    with pytest.raises(SystemExit):
        uploader.upgrade_tables(uri)
    assert "column 'unit' has type 'TEXT' in DB but 'REAL'" in capsys.readouterr().err

    # Test unsafe newly added required column against live DB
    req_added_schema = copy.deepcopy(SQLiteUploader.schema)
    for table_def in req_added_schema:
        if table_def["table"] == "foms":
            cur_ver = table_def["version"]
            table_def["schema"][cur_ver]["properties"]["new_req"] = {"type": "string"}
            table_def["schema"][cur_ver]["required"].append("new_req")
    uploader.schema = req_added_schema

    with pytest.raises(SystemExit):
        uploader.upgrade_tables(uri)
    assert "newly added columns cannot be required: ['new_req']" in capsys.readouterr().err

    # Test empty uninitialized DB file fails upgrade-db
    empty_uri = str(tmpdir.ensure("empty_uninitialized.db"))
    uploader.schema = SQLiteUploader.schema
    with pytest.raises(SystemExit):
        uploader.upgrade_tables(empty_uri)
    assert "has not been initialized" in capsys.readouterr().err


@patch("google.cloud.bigquery.Client")
def test_bigquery_upgrade_tables(mock_bigquery_client, capsys, mock_results_with_metadata):
    import copy

    from google.cloud import bigquery
    from google.cloud.exceptions import NotFound

    mock_client = MagicMock()
    mock_bigquery_client.return_value = mock_client

    uploader = BigQueryUploader()
    mock_rows = []
    for t_def in uploader.schema:
        row = MagicMock()
        row.key = t_def["metadata_key"]
        row.value = "0.1"
        mock_rows.append(row)
    mock_results = MagicMock()
    mock_results.total_rows = len(mock_rows)
    mock_results.__iter__.side_effect = lambda: iter(mock_rows)
    mock_query_job = MagicMock()
    mock_query_job.result.return_value = mock_results
    mock_client.query.return_value = mock_query_job

    new_schema = copy.deepcopy(BigQueryUploader.schema)
    for table_def in new_schema:
        if table_def["table"] == "foms":
            v0_2 = copy.deepcopy(table_def["schema"][0.1])
            v0_2["properties"]["fom_type"] = {"type": "string"}
            v0_2["properties"]["better_direction"] = {"type": "string"}
            table_def["schema"][0.2] = v0_2
            table_def["version"] = 0.2
    uploader.schema = new_schema

    # Return live table matching v0.1 schema for each table, except 'software' which is missing
    def get_table_side_effect(table_id):
        t_name = table_id.split(".")[-1]
        if t_name == "software":
            raise NotFound("Table software not found")
        t_def = next(t for t in BigQueryUploader.schema if t["table"] == t_name)
        live_fields = uploader._schema_to_bigquery(t_def["schema"][0.1])
        mock_table = MagicMock()
        mock_table.schema = live_fields
        return mock_table

    mock_client.get_table.side_effect = get_table_side_effect

    uri = "my-project.my_dataset"

    # Before upgrade, perform_upload dies when upstream version (0.1) != target version (0.2)
    formatted_data = format_data(mock_results_with_metadata)
    with pytest.raises(SystemExit):
        uploader.perform_upload(uri, formatted_data)
    assert "ramble data upgrade-db" in capsys.readouterr().err

    # Dry run does not create or update tables
    uploader.upgrade_tables(uri, dry_run=True)
    mock_client.create_table.assert_not_called()
    mock_client.update_table.assert_not_called()

    uploader.upgrade_tables(uri)

    mock_client.create_table.assert_called_once()
    mock_client.update_table.assert_called_once()
    updated_table = mock_client.update_table.call_args[0][0]
    updated_field_names = [f.name for f in updated_table.schema]
    assert "fom_type" in updated_field_names
    assert "better_direction" in updated_field_names
    fom_type_field = next(f for f in updated_table.schema if f.name == "fom_type")
    assert fom_type_field == bigquery.SchemaField("fom_type", "STRING", mode="NULLABLE", fields=[])

    # Test update_metadata with client=None and upload_metadata
    uploader.update_metadata(uri)
    with patch.object(uploader, "chunked_upload") as mock_chunked:
        uploader.upload_metadata(uri)
        mock_chunked.assert_called_once()

    # Test no-op upgrade_tables when all tables & metadata versions are current
    current_rows = []
    for t_def in uploader.schema:
        row = MagicMock()
        row.key = t_def["metadata_key"]
        row.value = str(t_def["version"])
        current_rows.append(row)
    mock_results.__iter__.side_effect = lambda: iter(current_rows)

    def get_all_tables_current(table_id):
        t_name = table_id.split(".")[-1]
        t_def = next(t for t in uploader.schema if t["table"] == t_name)
        mock_table = MagicMock()
        mock_table.schema = uploader._schema_to_bigquery(t_def["schema"][t_def["version"]])
        return mock_table

    mock_client.get_table.side_effect = get_all_tables_current
    mock_client.create_table.reset_mock()
    mock_client.update_table.reset_mock()
    uploader.upgrade_tables(uri)
    uploader.upgrade_tables(uri, dry_run=True)
    mock_client.create_table.assert_not_called()
    mock_client.update_table.assert_not_called()

    # perform_upload succeeds when versions match
    with patch.object(uploader, "insert_data") as mock_insert:
        uploader.perform_upload(uri, formatted_data)
        mock_insert.assert_called_once_with(uri, formatted_data)

    # Test _get_upstream_table_versions when metadata table is NotFound
    mock_client.query.side_effect = NotFound("Table metadata not found")
    assert uploader._get_upstream_table_versions(mock_client, uri) is None
    with patch.object(uploader, "insert_data") as mock_insert:
        uploader.perform_upload(uri, formatted_data)
        mock_insert.assert_called_once_with(uri, formatted_data)
    mock_client.query.side_effect = None
    mock_client.query.return_value = mock_query_job

    # Test BigQuery uninitialized dataset rejection when all tables raise NotFound
    mock_client.get_table.side_effect = NotFound("Table not found")
    with pytest.raises(SystemExit):
        uploader.upgrade_tables(uri)
    assert "has not been initialized" in capsys.readouterr().err

    # Test BigQuery live NULLABLE -> REQUIRED rejection
    bad_bq_schema = copy.deepcopy(BigQueryUploader.schema)
    for table_def in bad_bq_schema:
        if table_def["table"] == "software":
            table_def["schema"][0.1]["required"].append("version")
    uploader.schema = bad_bq_schema

    def get_orig_tables_current(table_id):
        t_name = table_id.split(".")[-1]
        t_def = next(t for t in BigQueryUploader.schema if t["table"] == t_name)
        mock_table = MagicMock()
        mock_table.schema = uploader._schema_to_bigquery(t_def["schema"][t_def["version"]])
        return mock_table

    mock_client.get_table.side_effect = get_orig_tables_current
    with pytest.raises(SystemExit):
        uploader.upgrade_tables(uri)
    assert "existing column 'version' became required" in capsys.readouterr().err

    # Test dataset NotFound rejection
    mock_client.get_dataset.side_effect = NotFound("Dataset not found")
    with pytest.raises(SystemExit):
        uploader.upgrade_tables(uri)
    assert "does not exist" in capsys.readouterr().err


def test_uploader_helpers_and_print_only_data_cmd(monkeypatch, capsys):
    from ramble.schema.db import db_schema_version
    from ramble.uploader import (
        BigQueryUploader,
        PrintOnlyUploader,
        _get_db_schema_version,
        _get_metadata_to_insert,
        get_uploader_and_uri,
    )

    # Fallback when not all required tables are in schema
    assert _get_db_schema_version([]) == db_schema_version
    metadata_items = _get_metadata_to_insert()
    assert any(item["key"] == "db_schema_version" for item in metadata_items)

    # get_uploader_and_uri for BigQuery and invalid uploader type
    with ramble.config.override("config:upload", {"uri": "proj.ds", "type": "BigQuery"}):
        uploader, uri = get_uploader_and_uri()
        assert isinstance(uploader, BigQueryUploader)
        assert uri == "proj.ds"
        upload_results({"experiments": []})

    monkeypatch.setattr(ramble.config, "get", lambda key: "InvalidType" if "type" in key else "u")
    with pytest.raises(ConfigError, match="is not valid"):
        get_uploader_and_uri()

    # PrintOnlyUploader warns on create_tables and upgrade_tables
    po_uploader = PrintOnlyUploader()
    po_uploader.create_tables("unused")
    po_uploader.upgrade_tables("unused")
    err = capsys.readouterr().err
    assert "does not support creating database tables" in err
    assert "does not support upgrading database tables" in err
