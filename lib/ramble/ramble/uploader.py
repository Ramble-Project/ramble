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
from enum import Enum, auto

import jsonschema

import ramble.config
import ramble.util.version
from ramble.config import ConfigError
from ramble.experiment_result import ExperimentStatus, ResultKeys
from ramble.keywords import keywords
from ramble.schema.db import db_schema_version
from ramble.schema.experiment import experiment_schema, experiment_schema_version
from ramble.schema.experiments_metadata import (
    experiments_metadata_schema,
    experiments_metadata_schema_version,
)
from ramble.schema.fom import fom_schema, fom_schema_version
from ramble.schema.metadata import metadata_schema, metadata_schema_version
from ramble.schema.software_db import software_db_schema, software_db_schema_version
from ramble.util.foms import BetterDirection, FomType
from ramble.util.logger import logger

default_node_type_val = "Not Specified"


class uploader_types(Enum):
    BigQuery = auto()
    PrintOnly = auto()
    SQLite = auto()


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


def check_schema_upgrade(old_schema: dict, new_schema: dict, table_name: str = "") -> list:
    """Validate whether upgrading from old_schema to new_schema is safe (non-destructive).

    A schema upgrade is safe if:
    1. No existing properties are removed.
    2. No existing property changes its type or format.
    3. No existing optional property becomes required.
    4. All newly added properties are nullable (not in 'required').

    Returns:
        list[str]: List of newly added property names.

    Raises:
        ValueError: If the schema upgrade is unsafe.
    """
    old_props = old_schema.get("properties", {})
    new_props = new_schema.get("properties", {})
    old_req = set(old_schema.get("required", []))
    new_req = set(new_schema.get("required", []))

    removed_cols = set(old_props.keys()) - set(new_props.keys())
    if removed_cols:
        raise ValueError(
            f"Unsafe schema upgrade for table '{table_name}': "
            f"columns removed: {sorted(removed_cols)}"
        )

    for col, old_col_props in old_props.items():
        new_col_props = new_props[col]
        if old_col_props.get("type") != new_col_props.get("type") or old_col_props.get(
            "format"
        ) != new_col_props.get("format"):
            raise ValueError(
                f"Unsafe schema upgrade for table '{table_name}': "
                f"column '{col}' changed type/format from {old_col_props} to {new_col_props}"
            )

    newly_required_existing = (new_req - old_req) & set(old_props.keys())
    if newly_required_existing:
        raise ValueError(
            f"Unsafe schema upgrade for table '{table_name}': "
            f"existing columns became required: {sorted(newly_required_existing)}"
        )

    added_cols = [col for col in new_props if col not in old_props]
    required_added_cols = [col for col in added_cols if col in new_req]
    if required_added_cols:
        raise ValueError(
            f"Unsafe schema upgrade for table '{table_name}': "
            f"newly added columns cannot be required: {sorted(required_added_cols)}"
        )

    return added_cols


def check_schema_upgrade_chain(
    schema_dict: dict, upstream_version: float, target_version: float, table_name: str = ""
) -> None:
    """Validate every consecutive version step from upstream_version to target_version."""
    versions = sorted(v for v in schema_dict if upstream_version <= float(v) <= target_version)
    if (
        not versions
        or float(versions[0]) != float(upstream_version)
        or float(versions[-1]) != float(target_version)
    ):
        raise ValueError(
            f"Unsafe schema upgrade for table '{table_name}': missing schema definition "
            f"in upgrade chain from '{upstream_version}' to '{target_version}'"
        )
    for v_old, v_new in zip(versions, versions[1:]):
        check_schema_upgrade(schema_dict[v_old], schema_dict[v_new], table_name)


class Uploader:
    schema = [
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

    def create_tables(self, uri):
        logger.warn(f"{self.__class__.__name__} does not support creating database tables.")

    def upgrade_tables(self, uri, dry_run=False):
        logger.warn(f"{self.__class__.__name__} does not support upgrading database tables.")

    def _warn_on_version_mismatch(self, upstream_versions) -> None:
        if not upstream_versions:
            return
        for table_def in self.schema:
            upstream_version = upstream_versions.get(table_def["metadata_key"])
            if upstream_version is not None and upstream_version != str(table_def["version"]):
                logger.warn(
                    f"Upstream DB schema version for table {table_def['table']} "
                    f"('{upstream_version}') does not match current version "
                    f"('{table_def['version']}'). "
                    "Run 'ramble data upgrade-db' to upgrade the database schema."
                )

    def _verify_schema_versions(self, upstream_versions) -> None:
        if upstream_versions is None:
            return
        for table_def in self.schema:
            upstream_version = upstream_versions.get(table_def["metadata_key"])
            if upstream_version != str(table_def["version"]):
                logger.die(
                    f"Database schema version for table '{table_def['table']}' "
                    f"('{upstream_version}') does not match current version "
                    f"('{table_def['version']}'). "
                    "Please upgrade the database by running: ramble data upgrade-db"
                )

    def _validate_version_upgrade(self, table_def: dict, upstream_version) -> None:
        table_name = table_def["table"]
        target_version = table_def["version"]
        if upstream_version is not None:
            try:
                upstream_ver_num = float(upstream_version)
            except (ValueError, TypeError):
                logger.die(
                    f"Invalid upstream schema version '{upstream_version}' "
                    f"for table '{table_name}'."
                )
            target_ver_num = float(target_version)
            if upstream_ver_num > target_ver_num:
                logger.die(
                    f"Cannot downgrade table '{table_name}' from upstream version "
                    f"'{upstream_version}' to '{target_version}'."
                )
            if upstream_ver_num < target_ver_num:
                try:
                    check_schema_upgrade_chain(
                        table_def["schema"],
                        upstream_ver_num,
                        target_ver_num,
                        table_name,
                    )
                except ValueError as e:
                    logger.die(str(e))

    def _validate_live_table_columns(
        self,
        table_name: str,
        live_cols: dict,
        target_cols: dict,
        required_cols: set,
        live_nullable_cols=None,
    ) -> list:
        removed_cols = set(live_cols.keys()) - set(target_cols.keys())
        if removed_cols:
            logger.die(
                f"Unsafe schema upgrade for table '{table_name}': "
                f"columns removed: {sorted(removed_cols)}"
            )

        for col, live_type in live_cols.items():
            if live_type != target_cols[col]:
                logger.die(
                    f"Unsafe schema upgrade for table '{table_name}': "
                    f"column '{col}' has type '{live_type}' in DB "
                    f"but '{target_cols[col]}' in target schema"
                )
            if (
                live_nullable_cols is not None
                and col in live_nullable_cols
                and col in required_cols
            ):
                logger.die(
                    f"Unsafe schema upgrade for table '{table_name}': "
                    f"existing column '{col}' became required"
                )

        missing_cols = [col for col in target_cols if col not in live_cols]
        required_missing = [col for col in missing_cols if col in required_cols]
        if required_missing:
            logger.die(
                f"Unsafe schema upgrade for table '{table_name}': "
                f"newly added columns cannot be required: {sorted(required_missing)}"
            )

        return missing_cols

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
        self.application_name = data[keywords.application_name]
        self.workspace_name = data[ResultKeys.VARIABLES][keywords.workspace_name]
        self.workspace_hash = workspace_hash
        self.workload_name = data[keywords.workload_name]
        self.bulk_hash = None  # proxy for workspace or "uploaded with"
        self.n_nodes = int(data[keywords.n_nodes])
        self.processes_per_node = int(data[keywords.processes_per_node])
        self.n_ranks = int(data[keywords.n_ranks])
        self.n_threads = int(data[keywords.n_threads])
        self.node_type = default_node_type_val
        self.status = data[keywords.RAMBLE_STATUS]
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
        data_copy[ResultKeys.CONTEXTS] = []

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


def get_uploader_and_uri():
    uploader_type_str = ramble.config.get("config:upload:type")
    if uploader_type_str is None:
        raise ConfigError("No upload type (config:upload:type) in config.")
    if not hasattr(uploader_types, uploader_type_str):
        raise ConfigError(f"Upload type {uploader_type_str} is not valid.")
    uploader_type = getattr(uploader_types, uploader_type_str)

    uri = ramble.config.get("config:upload:uri")
    if not uri:
        raise ConfigError("No upload URI (config:upload:uri) in config.")

    if uploader_type == uploader_types.BigQuery:
        uploader = BigQueryUploader()
    elif uploader_type == uploader_types.SQLite:
        uploader = SQLiteUploader()
    else:
        uploader = PrintOnlyUploader()

    return uploader, uri


def upload_results(results):
    uploader, uri = get_uploader_and_uri()

    try:
        formatted_data = format_data(results)
    except (KeyError, TypeError) as e:
        raise ConfigError("Error parsing file: Does not contain valid data to upload.") from e
    if not formatted_data:
        logger.warn("No data to upload")
        return

    logger.all_msg(f"Uploading results to {uri} with {type(uploader).__name__} uploader")
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

        if exp[keywords.RAMBLE_STATUS] == ExperimentStatus.SUCCESS or upload_failed:
            e = Experiment(exp[ResultKeys.NAME], data_in["workspace_hash"], exp, current_dateTime)
            results.append(e)
            # experiment_id = exp.hash()
            # 'experiment_id': experiment_id,
            for context in exp[ResultKeys.CONTEXTS]:
                for fom in context["foms"]:
                    raw_fom_type = fom.get("fom_type")
                    fom_type_obj = FomType.from_value(raw_fom_type) or FomType.UNDEFINED
                    if isinstance(raw_fom_type, dict) and "better_direction" in raw_fom_type:
                        better_direction_obj = (
                            BetterDirection.from_value(raw_fom_type["better_direction"])
                            or fom_type_obj.better_direction()
                        )
                    else:
                        better_direction_obj = fom_type_obj.better_direction()

                    # TODO: check on value to make sure it's a number
                    e.foms.append(
                        {
                            "name": fom["name"],
                            "value": fom["value"],
                            "unit": fom["units"],
                            "origin": fom["origin"],
                            "origin_type": fom["origin_type"],
                            "fom_type": fom_type_obj.name,
                            "better_direction": better_direction_obj.name,
                            "context": context["name"],
                        }
                    )

            if ResultKeys.SOFTWARE in exp:
                for software_list in exp[ResultKeys.SOFTWARE].values():
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
            determine_node_type(e, exp[ResultKeys.CONTEXTS])

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


def _get_db_schema_version(schema) -> str:
    versions = {t["table"]: t["version"] for t in schema}
    required_tables = ("foms", "experiments", "metadata", "experiments_metadata", "software")
    if all(t in versions for t in required_tables):
        return (
            f"fom-{versions['foms']}"
            f"_experiment-{versions['experiments']}"
            f"_metadata-{versions['metadata']}"
            f"_experiments-metadata-{versions['experiments_metadata']}"
            f"_software-{versions['software']}"
        )
    return db_schema_version


def _get_metadata_to_insert(schema=None):
    if schema is None:
        schema = Uploader.schema
    now_timestamp = get_utc_timestamp()
    return [
        {
            "key": "db_schema_version",
            "value": _get_db_schema_version(schema),
            "timestamp": now_timestamp,
        },
        *[
            {
                "key": table_def["metadata_key"],
                "value": str(table_def["version"]),
                "timestamp": now_timestamp,
            }
            for table_def in schema
        ],
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

    def _get_upstream_table_versions(self, client, uri):
        from google.cloud.exceptions import NotFound

        try:
            query = f"SELECT key, value FROM `{uri}.metadata` ORDER BY timestamp ASC"
            results = client.query(query).result()
            return {row.key: row.value for row in results}
        except NotFound:
            return None

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
        upstream_versions = self._get_upstream_table_versions(client, uri)
        self._warn_on_version_mismatch(upstream_versions)

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

        if tables_created and not upstream_versions:
            self.upload_metadata(uri)

    def upgrade_tables(self, uri, dry_run=False):
        from google.cloud import bigquery
        from google.cloud.exceptions import NotFound

        client = bigquery.Client()

        try:
            client.get_dataset(uri)
        except NotFound:
            logger.die(
                f"BigQuery dataset '{uri}' does not exist. "
                "Please create it first by running: ramble data create-db"
            )

        upstream_versions = self._get_upstream_table_versions(client, uri) or {}
        schema_updated = False
        tables_to_create = []
        tables_to_update = []

        # Phases 1 & 2: Validate version chains in memory and inspect live tables
        for table_def in self.schema:
            table_name = table_def["table"]
            table_id = f"{uri}.{table_name}"
            target_version = table_def["version"]
            target_schema = table_def["schema"][target_version]
            upstream_version = upstream_versions.get(table_def["metadata_key"])

            self._validate_version_upgrade(table_def, upstream_version)

            try:
                table = client.get_table(table_id)
                target_bq_fields = {f.name: f for f in self._schema_to_bigquery(target_schema)}
                live_bq_fields = {f.name: f for f in table.schema}

                missing_cols = self._validate_live_table_columns(
                    table_name,
                    {col: f.field_type for col, f in live_bq_fields.items()},
                    {col: f.field_type for col, f in target_bq_fields.items()},
                    {col for col, f in target_bq_fields.items() if f.mode == "REQUIRED"},
                    {col for col, f in live_bq_fields.items() if f.mode == "NULLABLE"},
                )

                relaxed_cols = [
                    col
                    for col, f in live_bq_fields.items()
                    if f.mode == "REQUIRED" and target_bq_fields[col].mode == "NULLABLE"
                ]

                if missing_cols or relaxed_cols:
                    updated_schema = [
                        target_bq_fields[f.name] if f.name in relaxed_cols else f
                        for f in table.schema
                    ] + [target_bq_fields[col] for col in missing_cols]
                    tables_to_update.append((table_id, table, missing_cols, updated_schema))

                if upstream_version != str(target_version):
                    schema_updated = True
            except NotFound:
                tables_to_create.append((table_id, self._schema_to_bigquery(target_schema)))

        if len(tables_to_create) == len(self.schema):
            logger.die(
                f"BigQuery dataset '{uri}' has not been initialized. "
                "Please create it first by running: ramble data create-db"
            )

        if dry_run:
            for table_id, _ in tables_to_create:
                logger.info(f"[Dry Run] Would create missing table {table_id}")
            for table_id, _, missing_cols, _ in tables_to_update:
                logger.info(
                    f"[Dry Run] Would update schema for table {table_id} "
                    f"(added columns: {missing_cols})"
                )
            if schema_updated or tables_to_create or tables_to_update:
                logger.info("[Dry Run] Would update metadata after schema upgrade")
            else:
                logger.info("Database schema is already up to date.")
            return

        # Phase 3: Apply changes after all tables pass validation
        for table_id, bq_schema in tables_to_create:
            logger.info(f"Creating missing table {table_id}")
            table = bigquery.Table(table_id, schema=bq_schema)
            client.create_table(table)
            schema_updated = True

        for table_id, table, missing_cols, updated_schema in tables_to_update:
            logger.info(f"Updating schema for table {table_id} (added columns: {missing_cols})")
            table.schema = updated_schema
            client.update_table(table, ["schema"])
            schema_updated = True

        if schema_updated:
            self.update_metadata(uri, client=client)
        else:
            logger.info("Database schema is already up to date.")

    def upload_metadata(self, uri):
        logger.info("Uploading metadata at table creation time")
        metadata_table_id = f"{uri}.metadata"
        metadata_to_insert = _get_metadata_to_insert(self.schema)
        self.chunked_upload(metadata_table_id, metadata_to_insert, uri=uri)

    def update_metadata(self, uri, client=None):
        from google.cloud import bigquery

        logger.info("Updating metadata after schema upgrade")
        if client is None:
            client = bigquery.Client()
        select_clauses = []
        query_params = []
        for idx, item in enumerate(_get_metadata_to_insert(self.schema)):
            select_clauses.append(
                f"SELECT @key_{idx} AS key, @val_{idx} AS value, "
                f"DATETIME(@ts_{idx}) AS timestamp"
            )
            query_params.extend(
                [
                    bigquery.ScalarQueryParameter(f"key_{idx}", "STRING", item["key"]),
                    bigquery.ScalarQueryParameter(f"val_{idx}", "STRING", item["value"]),
                    bigquery.ScalarQueryParameter(f"ts_{idx}", "STRING", item["timestamp"]),
                ]
            )
        source_sql = " UNION ALL ".join(select_clauses)
        query = (
            f"MERGE `{uri}.metadata` T "
            f"USING ({source_sql}) S "
            "ON T.key = S.key "
            "WHEN MATCHED THEN UPDATE SET value = S.value, timestamp = S.timestamp "
            "WHEN NOT MATCHED THEN INSERT (key, value, timestamp) "
            "VALUES (S.key, S.value, S.timestamp)"
        )
        job_config = bigquery.QueryJobConfig(query_parameters=query_params)
        client.query(query, job_config=job_config).result()

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
        from google.cloud import bigquery

        super().perform_upload(uri, results)

        client = bigquery.Client()
        upstream_versions = self._get_upstream_table_versions(client, uri)
        self._verify_schema_versions(upstream_versions)

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

    def _get_sqlite_columns(self, schema):
        type_map = {
            "string": "TEXT",
            "number": "REAL",
            "integer": "INTEGER",
            "boolean": "INTEGER",  # SQLite uses 0/1 for booleans
            "array": "TEXT",  # Store as JSON string
            "object": "TEXT",  # Store as JSON string
        }

        sqlite_cols = {}
        for name, props in schema.get("properties", {}).items():
            if props.get("format") == "date-time":
                sqlite_type = "DATETIME"
            else:
                sqlite_type = type_map[props["type"]]
            sqlite_cols[name] = sqlite_type

        return sqlite_cols

    def _schema_to_sqlite(self, schema):
        return ", ".join(
            f"{name} {sqlite_type}"
            for name, sqlite_type in self._get_sqlite_columns(schema).items()
        )

    def _get_upstream_table_versions(self, cursor):
        cursor.execute(
            "SELECT count(name) FROM sqlite_master WHERE type='table' AND name='metadata'"
        )
        if cursor.fetchone()[0] == 0:
            return None
        cursor.execute("SELECT key, value FROM metadata ORDER BY timestamp ASC")
        return {row[0]: row[1] for row in cursor.fetchall()}

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
            upstream_versions = self._get_upstream_table_versions(cursor)
            self._warn_on_version_mismatch(upstream_versions)

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

        if tables_created and not upstream_versions:
            self.upload_metadata(uri)

    def upgrade_tables(self, uri, dry_run=False):
        import sqlite3

        if not os.path.exists(uri):
            logger.die(
                f"SQLite database '{uri}' does not exist. "
                "Please create it first by running: ramble data create-db"
            )

        conn = sqlite3.connect(uri)
        try:
            cursor = conn.cursor()
            upstream_versions = self._get_upstream_table_versions(cursor) or {}

            schema_updated = False
            tables_to_create = []
            columns_to_add = []

            # Phases 1 & 2: Validate version chains in memory and inspect live tables
            for table_def in self.schema:
                table_name = table_def["table"]
                target_version = table_def["version"]
                target_schema = table_def["schema"][target_version]
                upstream_version = upstream_versions.get(table_def["metadata_key"])

                self._validate_version_upgrade(table_def, upstream_version)

                cursor.execute(
                    "SELECT count(name) FROM sqlite_master WHERE type='table' AND name=?",
                    (table_name,),
                )
                if cursor.fetchone()[0] == 0:
                    tables_to_create.append((table_name, self._schema_to_sqlite(target_schema)))
                else:
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    live_cols = {row[1]: row[2].upper() for row in cursor.fetchall()}
                    target_cols = self._get_sqlite_columns(target_schema)

                    missing_cols = self._validate_live_table_columns(
                        table_name,
                        live_cols,
                        target_cols,
                        set(target_schema.get("required", [])),
                    )

                    columns_to_add.extend(
                        (table_name, col, target_cols[col]) for col in missing_cols
                    )

                    if upstream_version != str(target_version):
                        schema_updated = True

            if len(tables_to_create) == len(self.schema):
                logger.die(
                    f"SQLite database '{uri}' has not been initialized. "
                    "Please create it first by running: ramble data create-db"
                )

            if dry_run:
                for table_name, _ in tables_to_create:
                    logger.info(f"[Dry Run] Would create missing table {table_name}")
                for table_name, col, col_type in columns_to_add:
                    logger.info(f"[Dry Run] Would add column '{col}' ({col_type}) to {table_name}")
                if schema_updated or tables_to_create or columns_to_add:
                    logger.info("[Dry Run] Would update metadata after schema upgrade")
                else:
                    logger.info("Database schema is already up to date.")
                return

            # Phase 3: Apply changes after all tables pass validation
            for table_name, sqlite_schema in tables_to_create:
                logger.info(f"Creating missing table {table_name}")
                cursor.execute(f"CREATE TABLE {table_name} ({sqlite_schema})")
                schema_updated = True

            for table_name, col, col_type in columns_to_add:
                logger.info(f"Adding column '{col}' ({col_type}) to {table_name}")
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col} {col_type}")
                schema_updated = True

            if schema_updated:
                logger.info("Updating metadata after schema upgrade")
                cursor.execute("SELECT key FROM metadata")
                existing_keys = {row[0] for row in cursor.fetchall()}
                for item in _get_metadata_to_insert(self.schema):
                    if item["key"] in existing_keys:
                        cursor.execute(
                            "UPDATE metadata SET value = ?, timestamp = ? WHERE key = ?",
                            (item["value"], item["timestamp"], item["key"]),
                        )
                    else:
                        cursor.execute(
                            "INSERT INTO metadata (key, value, timestamp) VALUES (?, ?, ?)",
                            (item["key"], item["value"], item["timestamp"]),
                        )
            else:
                logger.info("Database schema is already up to date.")

            conn.commit()
        finally:
            conn.close()

    def upload_metadata(self, uri):
        logger.info("Uploading metadata at table creation time")
        metadata_table_id = "metadata"
        metadata_to_insert = _get_metadata_to_insert(self.schema)
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
            sqlite_row = []
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
        import sqlite3

        if not os.path.exists(uri):
            logger.die(
                f"SQLite database '{uri}' does not exist. "
                "Please create it first by running: ramble data create-db"
            )

        super().perform_upload(uri, results)

        conn = sqlite3.connect(uri)
        try:
            cursor = conn.cursor()
            upstream_versions = self._get_upstream_table_versions(cursor)
            self._verify_schema_versions(upstream_versions)
        finally:
            conn.close()

        self.insert_data(uri, results)
