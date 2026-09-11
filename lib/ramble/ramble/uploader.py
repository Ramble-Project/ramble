# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import json
import math
import os
import sys
from enum import Enum
from typing import Any, Dict, List

import jsonschema

import ramble.config
import ramble.util.version
from ramble.config import ConfigError
from ramble.schema.db import db_schema_version
from ramble.schema.experiment import experiment_schema, experiment_schema_version
from ramble.schema.experiments_metadata import (
    experiments_metadata_schema,
    experiments_metadata_schema_version,
)
from ramble.schema.fom import fom_schema, fom_schema_version
from ramble.schema.metadata import metadata_schema, metadata_schema_version
from ramble.schema.software_db import software_db_schema, software_db_schema_version
from ramble.util.logger import logger

default_node_type_val = "Not Specified"

uploader_types = Enum("uploader_types", ["BigQuery", "PrintOnly", "SQLite"])


def get_utc_timestamp() -> str:
    """Returns the current UTC datetime formatted as an ISO 8601 string without timezone offset."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()


def validate_data(data, schema):
    """Validate data against a JSON schema."""
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.exceptions.ValidationError as err:
        logger.error(f"Schema validation error: {err}")
        raise


class Uploader:
    schema: List[Dict[str, Any]] = [
        {
            "table": "experiments",
            "schema": experiment_schema,
            "version": experiment_schema_version,
            "metadata_key": "experiment_schema_version",
        },
        {
            "table": "foms",
            "schema": fom_schema,
            "version": fom_schema_version,
            "metadata_key": "fom_schema_version",
        },
        {
            "table": "metadata",
            "schema": metadata_schema,
            "version": metadata_schema_version,
            "metadata_key": "metadata_schema_version",
        },
        {
            "table": "experiments_metadata",
            "schema": experiments_metadata_schema,
            "version": experiments_metadata_schema_version,
            "metadata_key": "experiments_metadata_schema_version",
        },
        {
            "table": "software",
            "schema": software_db_schema,
            "version": software_db_schema_version,
            "metadata_key": "software_db_schema_version",
        },
    ]

    # TODO: should the class store the base uri?
    def perform_upload(self, uri, data):
        # TODO: move content checking to __init__ ?
        if not uri:
            raise ValueError(f"{self.__class__} requires {uri} argument.")
        if not data:
            raise ValueError(f"{self.__class__} requires %{data} argument.")

    def chunked_upload(self, table_id, data, uri=None):
        """Abstract method for chunked uploads. Must be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement chunked_upload()")

    def insert_data(self, uri: str, results) -> None:
        (
            exp_table_id,
            exps_to_insert,
            fom_table_id,
            foms_to_insert,
            metadata_table_id,
            metadata_to_insert,
            software_table_id,
            software_to_insert,
        ) = _prepare_data(results, uri)

        logger.debug("Experiments to insert:")
        logger.debug(exps_to_insert)

        logger.msg("Upload experiments...")
        errors1 = self.chunked_upload(exp_table_id, exps_to_insert, uri=uri)

        if not errors1:
            logger.msg("Upload FOMs...")
            errors2 = self.chunked_upload(fom_table_id, foms_to_insert, uri=uri)
        else:
            errors2 = None

        if not errors2 and not errors1:
            logger.msg("Upload Experiment Metadata...")
            errors3 = self.chunked_upload(metadata_table_id, metadata_to_insert, uri=uri)
        else:
            errors3 = None

        if not errors3 and not errors2 and not errors1:
            logger.msg("Upload Software...")
            errors4 = self.chunked_upload(software_table_id, software_to_insert, uri=uri)
        else:
            errors4 = None

        for errors, name in zip(
            (errors1, errors2, errors3, errors4),
            ("exp", "fom", "experiment_metadata", "software"),
        ):
            if errors is not None and not errors:
                logger.msg(f"New rows have been added in {name}")
            elif errors:
                logger.die(f"Encountered errors while inserting rows: {errors}")


class ExperimentList(list):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.metadata = {}


def get_user():
    config_user = ramble.config.get("config:user")
    if config_user:
        return config_user
    else:
        import getpass

        return getpass.getuser()


class Experiment:
    """
    Class representation of experiment data
    """

    def __init__(self, name, workspace_hash, data, timestamp):
        self.name = name
        self.id = None  # This is essentially the hash
        self.foms = []
        self.software = []
        self.data = data
        self.application_name = data["application_name"]
        self.workspace_name = data["RAMBLE_VARIABLES"]["workspace_name"]
        self.workspace_hash = workspace_hash
        self.workload_name = data["workload_name"]
        self.bulk_hash = None  # proxy for workspace or "uploaded with"
        self.n_nodes = int(data["n_nodes"])
        self.processes_per_node = int(data["processes_per_node"])
        self.n_ranks = int(data["n_ranks"])
        self.n_threads = int(data["n_threads"])
        self.node_type = default_node_type_val
        self.status = data["RAMBLE_STATUS"]
        self.user = get_user()

        # FIXME: this is no longer strictly needed since it is just a concat of known properties
        exps_hash = "{workspace_name}::{application}::{workload}::{date}".format(
            workspace_name=self.workspace_name,
            application=self.application_name,
            workload=self.workload_name,
            date=timestamp,
        )

        self.bulk_hash = exps_hash

        self.timestamp = str(timestamp)

        self.id = None
        self.generate_hash()

    def generate_hash(self):
        # Avoid regenerating a hash when possible
        # (The hash of an object must never change during its lifetime..)
        if self.id is None:
            #  TODO: this might be better as a hash of something we intuitively
            # expect to be uniqie, like:
            # "{RAMBLE_STATUS}-{application_name}-{experiment_name}-{time}-etc"
            # If we don't want this, we can go back to this class just being a dict
            self.id = hash(self)
        return self.id

    def get_hash(self):
        return self.generate_hash()

    def to_json(self):

        # deep copy so the assignment below doesn't affect the foms array
        import copy

        j = copy.deepcopy(self.__dict__)
        data_copy = copy.deepcopy(self.data)

        # These two fields will be deprecated in an upcoming release.
        # For now we avoid setting them to a reduced set of information to
        # maintain backwards database compatibiilty but also avoiding
        # large un-needed uploads
        data_copy["CONTEXTS"] = []

        del j["foms"]
        del j["software"]
        j["data"] = json.dumps(data_copy, default=vars)
        return j


def determine_node_type(experiment, contexts):
    """
    Extract node type from available FOMS.

    First prio is machine specific data, such as GCP meta data
    Second prio is more general data like CPU type
    """
    node_type = default_node_type_val
    for context in contexts:
        for fom in context.get("foms", []):
            if "machine-type" in fom["name"]:
                experiment.node_type = fom["value"]
                return
            elif "Model name" in fom["name"] and node_type == default_node_type_val:
                node_type = fom["value"]

    experiment.node_type = node_type


def upload_results(results):
    uploader_type = ramble.config.get("config:upload:type")
    if uploader_type is None:
        raise ConfigError("No upload type (config:upload:type) in config.")
    if not hasattr(uploader_types, uploader_type):
        raise ConfigError(f"Upload type {uploader_type} is not valid.")
    uploader_type = getattr(uploader_types, uploader_type)

    uri = ramble.config.get("config:upload:uri")
    if not uri:
        raise ConfigError("No upload URI (config:upload:uri) in config.")

    try:
        formatted_data = format_data(results)
    except (KeyError, TypeError) as e:
        raise ConfigError("Error parsing file: Does not contain valid data to upload.") from e
    if not formatted_data:
        logger.warn("No data to upload")
        return

    logger.all_msg(f"Uploading results to {uri} with {uploader_type} uploader")
    uploader: Uploader
    if uploader_type == uploader_types.BigQuery:
        uploader = BigQueryUploader()
    elif uploader_type == uploader_types.SQLite:
        uploader = SQLiteUploader()
    else:
        uploader = PrintOnlyUploader()
    uploader.perform_upload(uri, formatted_data)


def format_data(data_in):
    """
    Goal: convert results to a more searchable and decomposed format for insertion
    into data store (etc)

    Input:

    .. code-block:: text

        { experiment_name:
            { "CONTEXTS": {
                "context_name": "FOM_name { unit: "value", "value":value" }
            ...}
            }
        }

    Output: The general idea is the decompose the results into a more "database"
    like format, where the runs and FOMs are in a different table.
    """
    logger.debug("Format Data in")
    logger.debug(data_in)
    results = ExperimentList()

    if "metadata" in data_in:
        results.metadata = data_in["metadata"]

    # TODO: what is the nice way to deal with the distinction between
    # numberic/float and string FOM values

    current_dateTime = get_utc_timestamp()

    for exp in data_in["experiments"]:

        upload_failed = ramble.config.get("config:upload:push_failed")

        if exp["RAMBLE_STATUS"] == "SUCCESS" or upload_failed:
            e = Experiment(exp["name"], data_in["workspace_hash"], exp, current_dateTime)
            results.append(e)
            # experiment_id = exp.hash()
            # 'experiment_id': experiment_id,
            for context in exp["CONTEXTS"]:
                for fom in context["foms"]:
                    # TODO: check on value to make sure it's a number
                    e.foms.append(
                        {
                            "name": fom["name"],
                            "value": fom["value"],
                            "unit": fom["units"],
                            "origin": fom["origin"],
                            "origin_type": fom["origin_type"],
                            "context": context["name"],
                        }
                    )

            if "SOFTWARE" in exp:
                for software_list in exp["SOFTWARE"].values():
                    for software in software_list:
                        e.software.append(
                            {
                                "name": software["name"],
                                "version": software["version"],
                                "compiler": software["compiler"],
                                "compiler_version": software["compiler_version"],
                                "target": software["target"],
                                "variants": software["variants"],
                            }
                        )
            determine_node_type(e, exp["CONTEXTS"])

    return results


def _prepare_data(results, uri):
    # It is expected that the user will create these tables outside of this
    # tooling
    exp_table_id = f"{uri}.experiments"
    fom_table_id = f"{uri}.foms"
    metadata_table_id = f"{uri}.experiments_metadata"
    software_table_id = f"{uri}.software"

    exps_to_insert = []
    foms_to_insert = []
    metadata_to_insert = []
    software_to_insert = []

    for experiment in results:
        json_experiment = experiment.to_json()
        exps_to_insert.append(json_experiment)

        for fom in experiment.foms:
            fom_data = fom.copy()
            fom_data["experiment_id"] = experiment.get_hash()
            fom_data["experiment_name"] = experiment.name
            foms_to_insert.append(fom_data)

        for software in experiment.software:
            software_data = software.copy()
            software_data["experiment_id"] = experiment.get_hash()
            software_data["experiment_name"] = experiment.name
            software_to_insert.append(software_data)

    current_metadata = []
    if hasattr(results, "metadata"):
        current_metadata = results.metadata

    # Handle dictionary and list format of metadata
    if isinstance(current_metadata, dict):
        # Flatten dictionary to a list of dicts
        aux_metadata = []
        for key, value in current_metadata.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    # Check if we should use dot notation or just the sub_key
                    # For now, just using the sub_key as it's cleaner for the 'metadata' case
                    aux_metadata.append({"key": sub_key, "value": sub_value})
            else:
                aux_metadata.append({"key": key, "value": value})
        current_metadata = aux_metadata

    for result in results:
        for metadatum in current_metadata:
            md_item = metadatum.copy()
            # Stringify all values
            for k, v in md_item.items():
                md_item[k] = str(v)

            md_item["experiment_id"] = result.get_hash()
            if hasattr(result, "timestamp"):
                md_item["timestamp"] = result.timestamp
            metadata_to_insert.append(md_item)

    return (
        exp_table_id,
        exps_to_insert,
        fom_table_id,
        foms_to_insert,
        metadata_table_id,
        metadata_to_insert,
        software_table_id,
        software_to_insert,
    )


def _get_metadata_to_insert():
    now_timestamp = get_utc_timestamp()
    return [
        {
            "key": "db_schema_version",
            "value": db_schema_version,
            "timestamp": now_timestamp,
        },
        {
            "key": "experiment_schema_version",
            "value": str(experiment_schema_version),
            "timestamp": now_timestamp,
        },
        {
            "key": "fom_schema_version",
            "value": str(fom_schema_version),
            "timestamp": now_timestamp,
        },
        {
            "key": "metadata_schema_version",
            "value": str(metadata_schema_version),
            "timestamp": now_timestamp,
        },
        {
            "key": "software_db_schema_version",
            "value": str(software_db_schema_version),
            "timestamp": now_timestamp,
        },
        {
            "key": "ramble_version",
            "value": ramble.util.version.get_version(),
            "timestamp": now_timestamp,
        },
        {
            "key": "user",
            "value": get_user(),
            "timestamp": now_timestamp,
        },
    ]


class BigQueryUploader(Uploader):
    """Class to handle upload of FOMs to BigQuery"""

    """
    Attempt to chunk the upload into acceptable size chunks, per BigQuery requirements
    """

    def _schema_to_bigquery(self, schema):
        from google.cloud import bigquery

        type_map = {
            "string": "STRING",
            "number": "FLOAT",
            "integer": "INTEGER",
            "boolean": "BOOLEAN",
            "array": "RECORD",
            "object": "RECORD",
        }

        bq_schema = []
        for name, props in schema.get("properties", {}).items():
            if props.get("format") == "date-time":
                bq_type = "DATETIME"
            else:
                bq_type = type_map[props["type"]]
            mode = "NULLABLE"
            if name in schema.get("required", []):
                mode = "REQUIRED"

            fields = []
            if "items" in props:
                fields = self._schema_to_bigquery(props["items"])

            bq_schema.append(bigquery.SchemaField(name, bq_type, mode=mode, fields=fields))

        return bq_schema

    def create_tables(self, uri):
        from google.cloud import bigquery
        from google.cloud.exceptions import NotFound

        client = bigquery.Client()

        try:
            client.get_dataset(uri)
        except NotFound:
            logger.info(f"Dataset {uri} is not found, creating it.")
            client.create_dataset(uri)

        # Check schema version
        for table_def in self.schema:
            try:
                query = (
                    f"SELECT value FROM `{uri}.metadata` WHERE key = "
                    f"'{table_def['table']}_schema_version'"
                )
                query_job = client.query(query)
                results = query_job.result()
                if results.total_rows > 0:
                    upstream_version = next(iter(results)).value
                    if upstream_version != str(table_def["version"]):
                        logger.warn(
                            f"Upstream DB schema version for table {table_def['table']} "
                            f"('{upstream_version}') does not match current version "
                            f"('{table_def['version']}')"
                        )
            except NotFound:
                pass  # metadata table doesn't exist, so we don't need to check the version

        tables_created = False
        for table_def in self.schema:
            table_id = f"{uri}.{table_def['table']}"
            try:
                client.get_table(table_id)
                logger.info(f"Table {table_id} already exists.")
            except NotFound:
                logger.info(f"Creating table {table_id}")
                bq_schema = self._schema_to_bigquery(table_def["schema"][table_def["version"]])
                table = bigquery.Table(table_id, schema=bq_schema)
                table = client.create_table(table)
                logger.info(f"Created table {table.project}.{table.dataset_id}.{table.table_id}")
                tables_created = True

        if tables_created:
            self.upload_metadata(uri)

    def upload_metadata(self, uri):
        logger.info("Uploading metadata at table creation time")
        metadata_table_id = f"{uri}.metadata"
        metadata_to_insert = _get_metadata_to_insert()
        self.chunked_upload(metadata_table_id, metadata_to_insert, uri=uri)

    def chunked_upload(self, table_id, data, uri=None):
        from google.cloud import bigquery

        client = bigquery.Client()
        error = []
        approx_max_request = 1000000.0  # 1MB

        data_len = len(data)
        approx_request_size = sys.getsizeof(json.dumps(data))
        approx_num_batches = math.ceil(approx_request_size / approx_max_request)
        rows_per_batch = math.floor(data_len / approx_num_batches)
        if rows_per_batch <= 1:
            rows_per_batch = 1

        logger.debug(f"Size: {sys.getsizeof(json.dumps(data))}B")
        logger.debug(f"Length in rows: {data_len}")
        logger.debug(f"Num Batches: {approx_num_batches}")
        logger.debug(f"Rows per Batch: {rows_per_batch}")

        for i in range(0, data_len, rows_per_batch):
            end = i + rows_per_batch
            if end > data_len:
                end = data_len
            logger.debug(f"Uploading rows {i} to {end}")
            table_name = table_id.split(".")[-1]
            table_def = next((t for t in self.schema if t["table"] == table_name), None)
            if table_def and table_def["schema"].get(table_def["version"]):
                schema_for_validation = table_def["schema"][table_def["version"]]
                for row in data[i:end]:
                    validate_data(row, schema_for_validation)
            else:
                logger.warn(
                    f"Could not find a valid schema for table '{table_name}'. "
                    f"Skipping validation for this chunk."
                )

            error = client.insert_rows_json(table_id, data[i:end])
            if error:
                logger.warn("Issue  during uploader insert")
                logger.warn(error)
                return error
        return error

    def perform_upload(self, uri, results):
        super().perform_upload(uri, results)

        # import spack.util.spack_json as sjson
        # json_str = sjson.dump(results)

        self.insert_data(uri, results)

    # def get_max_current_id(uri, table):
    # TODO: Generating an id based on the max in use id is dangerous, and
    # technically gives a race condition in parallel, and should be done in
    # a more graceful and scalable way..  like hashing the experiment? or
    # generating a known unique id for it
    # query = "SELECT MAX(id) FROM `{uri}.{table}` LIMIT 1".format(uri=uri, table=table)
    # query_job = client.query(query)
    # results = query_job.result()  # Waits for job to complete.
    # return results[0]


class PrintOnlyUploader(Uploader):
    """An uploader that only prints out formatted data without actually uploading."""

    def perform_upload(self, uri, results):
        super().perform_upload(uri, results)
        (
            exp_table_id,
            exps_to_insert,
            fom_table_id,
            foms_to_insert,
            metadata_table_id,
            metadata_to_insert,
            software_table_id,
            software_to_insert,
        ) = _prepare_data(results, uri)
        logger.info("NOTE: The PrintOnly uploader only logs, but does not upload any data.")
        logger.info(f"{len(exps_to_insert)} experiment(s) would be uploaded to {exp_table_id}:")
        for exp in exps_to_insert:
            logger.info(f"  {exp}")
        logger.info(f"{len(foms_to_insert)} fom(s) would be uploaded to {fom_table_id}:")
        for fom in foms_to_insert:
            logger.info(f"  {fom}")
        logger.info(
            f"{len(metadata_to_insert)} experiment metadata item(s) "
            f"would be uploaded to {metadata_table_id}:"
        )
        for metadata_item in metadata_to_insert:
            logger.info(f"  {metadata_item}")
        logger.info(
            f"{len(software_to_insert)} "
            f"software package(s) would be uploaded to {software_table_id}:"
        )
        for software in software_to_insert:
            logger.info(f"  {software}")


class SQLiteUploader(Uploader):
    """Class to handle upload of FOMs to a local SQLite database"""

    def _schema_to_sqlite(self, schema):
        type_map = {
            "string": "TEXT",
            "number": "REAL",
            "integer": "INTEGER",
            "boolean": "INTEGER",  # SQLite uses 0/1 for booleans
            "array": "TEXT",  # Store as JSON string
            "object": "TEXT",  # Store as JSON string
        }

        sqlite_schema = []
        for name, props in schema.get("properties", {}).items():
            if props.get("format") == "date-time":
                sqlite_type = "DATETIME"
            else:
                sqlite_type = type_map[props["type"]]
            sqlite_schema.append(f"{name} {sqlite_type}")

        return ", ".join(sqlite_schema)

    def create_tables(self, uri):
        import sqlite3

        # Verify URI is a valid path location, create directories if needed
        db_dir = os.path.dirname(uri)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)

        conn = sqlite3.connect(uri)
        try:
            cursor = conn.cursor()

            # Check schema version
            for table_def in self.schema:
                try:
                    # Check if metadata table exists first
                    cursor.execute(
                        "SELECT count(name) FROM sqlite_master WHERE "
                        "type='table' AND name='metadata'"
                    )
                    if cursor.fetchone()[0] == 1:
                        query = (
                            f"SELECT value FROM metadata WHERE key = "
                            f"'{table_def['metadata_key']}'"
                        )
                        cursor.execute(query)
                        result = cursor.fetchone()
                        if result:
                            upstream_version = result[0]
                            if upstream_version != str(table_def["version"]):
                                logger.warn(
                                    f"Upstream DB schema version for table {table_def['table']} "
                                    f"('{upstream_version}') does not match current version "
                                    f"('{table_def['version']}')"
                                )
                except sqlite3.Error as e:
                    logger.warn(f"Error checking schema version: {e}")

            tables_created = False
            for table_def in self.schema:
                table_name = table_def["table"]
                cursor.execute(
                    "SELECT count(name) FROM sqlite_master WHERE "
                    f"type='table' AND name='{table_name}'"
                )
                if cursor.fetchone()[0] == 1:
                    logger.info(f"Table {table_name} already exists.")
                else:
                    logger.info(f"Creating table {table_name}")
                    sqlite_schema = self._schema_to_sqlite(
                        table_def["schema"][table_def["version"]]
                    )
                    cursor.execute(f"CREATE TABLE {table_name} ({sqlite_schema})")
                    tables_created = True

            conn.commit()
        finally:
            conn.close()

        if tables_created:
            self.upload_metadata(uri)

    def upload_metadata(self, uri):
        logger.info("Uploading metadata at table creation time")
        metadata_table_id = "metadata"
        metadata_to_insert = _get_metadata_to_insert()
        self.chunked_upload(metadata_table_id, metadata_to_insert, uri)

    def chunked_upload(self, table_id, data, uri=None):
        import sqlite3

        if not data:
            return []

        error = []
        table_name = table_id.split(".")[-1]
        table_def = next((t for t in self.schema if t["table"] == table_name), None)

        if table_def and table_def["schema"].get(table_def["version"]):
            schema_for_validation = table_def["schema"][table_def["version"]]
            for row in data:
                validate_data(row, schema_for_validation)
        else:
            logger.warn(
                f"Could not find a valid schema for table '{table_name}'. "
                f"Skipping validation for this chunk."
            )

        # Prepare data for SQLite insertion (serialize dicts/lists to JSON strings)
        sqlite_data = []
        keys = list(data[0].keys())

        for row in data:
            sqlite_row: List[Any] = []
            for key in keys:
                val = row.get(key)
                if isinstance(val, (dict, list)):
                    sqlite_row.append(json.dumps(val))
                elif isinstance(val, bool):
                    sqlite_row.append(1 if val else 0)
                else:
                    sqlite_row.append(val)
            sqlite_data.append(tuple(sqlite_row))

        placeholders = ", ".join(["?"] * len(keys))
        columns = ", ".join(keys)
        insert_query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

        try:
            conn = sqlite3.connect(uri)
            try:
                cursor = conn.cursor()
                cursor.executemany(insert_query, sqlite_data)
                conn.commit()
            finally:
                conn.close()
        except sqlite3.Error as e:
            logger.warn(f"Issue during uploader insert: {e}")
            error.append(str(e))

        return error

    def perform_upload(self, uri, results):

        if not os.path.exists(uri):
            logger.die(
                f"SQLite database '{uri}' does not exist. "
                "Please create it first by running: ramble data create-db"
            )

        super().perform_upload(uri, results)
        self.insert_data(uri, results)
