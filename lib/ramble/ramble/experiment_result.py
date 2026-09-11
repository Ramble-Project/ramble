# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
from enum import Enum
from typing import Union

from ramble.namespace import namespace
from ramble.software_info import SoftwareInfo
from ramble.util import json_util
from ramble.util.file_util import get_newest_experiment_file
from ramble.util.format import when_order
from ramble.util.logger import logger


# Can use auto() once we're at >= python 3.11
class ExperimentStatus(str, Enum):
    UNKNOWN = "UNKNOWN"
    UNQUEUED = "UNQUEUED"
    UNRESOLVED = "UNRESOLVED"  # unresolved means the status is not fetched successfully
    SETUP = "SETUP"
    SUBMITTED = "SUBMITTED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMEOUT = "TIMEOUT"


_OUTPUT_MAPPING = {
    "name": "name",
    "status": "EXPERIMENT_STATUS",
    namespace.n_repeats: "N_REPEATS",
    "keys": "keys",
    "contexts": "CONTEXTS",
    "software": "SOFTWARE",
    namespace.variables: "RAMBLE_VARIABLES",
    "raw_variables": "RAMBLE_RAW_VARIABLES",
    namespace.tags: "TAGS",
    namespace.variants: "VARIANTS",
    "experiment_chain": "EXPERIMENT_CHAIN",
    "success_criteria": "SUCCESS_CRITERIA",
    "object_definitions": "OBJECT_DEFINITIONS",
}


# TODO: would be better to use dataclass after 3.6 support is dropped
class ExperimentResult:
    """Class containing results and related metadata of an experiment"""

    cache_file_name = "ramble_results_cache.json"

    def __init__(self, app_inst):
        """Build up the result from the given app instance"""
        self._app_inst = app_inst
        self.name = None
        self.status: Union[ExperimentStatus, str] = ExperimentStatus.UNKNOWN
        self.n_repeats = None
        self.experiment_chain = []
        self.tags = []
        self.contexts = []
        self.success_criteria = {}
        self.software = {}
        self.keys = {}
        self.raw_variables = {}
        self.variables = {}
        self.variants = []
        self.object_definitions = []

    def read_cache(self, workspace, app_inst) -> bool:
        experiment_dir = app_inst.expander.experiment_run_dir
        cache_file = os.path.join(experiment_dir, self.cache_file_name)

        logger.debug(f"Experiment results cache file is: {cache_file}")

        if not os.path.isfile(cache_file):
            logger.debug("No valid experiment results cache found. Will create one.")
            return False
        cache_timestamp = os.path.getmtime(cache_file)

        newest_file, file_timestamp = get_newest_experiment_file(experiment_dir)

        if file_timestamp is not None and cache_timestamp < file_timestamp:
            logger.all_msg("Invalidating experiment results cache: timestamp difference")
            return False

        with open(cache_file, encoding="utf-8") as f:
            cache_dict = json_util.load(f)

        if (
            "experiment_hash" not in cache_dict
            or app_inst.experiment_hash != cache_dict["experiment_hash"]
        ):
            logger.all_msg("Invalidating experiment results cache: experiment hash difference")
            return False

        self.from_dict(cache_dict)
        logger.all_msg("Reading experiment results from cache file")
        return True

    def write_cache(self, app_inst):
        experiment_dir = app_inst.expander.experiment_run_dir
        cache_file = os.path.join(experiment_dir, self.cache_file_name)

        out_dict = self.to_dict()
        out_dict["experiment_hash"] = app_inst.experiment_hash

        software_key = _OUTPUT_MAPPING["software"]
        software_packages = {}
        if software_key in out_dict:
            software_packages = out_dict[software_key].copy()

        out_dict[software_key] = {}
        for key, pkg_list in software_packages.items():
            out_dict[software_key][key] = [pkg.to_dict() for pkg in pkg_list]

        with open(cache_file, "w+", encoding="utf-8") as f:
            json_util.dump(out_dict, f)

    def finalize(self, workspace):
        app_inst = self._app_inst
        self.name = app_inst.expander.experiment_namespace

        self.status = app_inst.get_status()

        self.n_repeats = app_inst.repeats.n_repeats
        self.experiment_chain = app_inst.chain_order.copy()
        self.tags = list(app_inst.experiment_tags)

        # Most libs can handle this str enum, but convert it to help out
        if hasattr(self.status, "value"):
            self.status = self.status.value

        for key in app_inst.keywords.keys:
            if app_inst.keywords.is_key_level(key):
                self.keys[key] = app_inst.expander.expand_var_name(key)

        self.raw_variables = {}
        for var, val in app_inst.variables.items():
            self.raw_variables[var] = val
            if var not in app_inst.keywords.keys or not app_inst.keywords.is_key_level(var):
                self.variables[var] = app_inst.expander.expand_var(val)

        self.variants = sorted(
            app_inst.experiment_variants().as_set(for_output=True), key=when_order
        )

        self.object_definitions = app_inst.object_inventory()

    def from_dict(self, in_dict: dict):
        """Convert a dict back into a results object

        Args:
            in_dict (dict): Input dictionary of results from a cache
        """

        for lookup_key, output_key in _OUTPUT_MAPPING.items():
            if output_key in in_dict:
                setattr(self, lookup_key, in_dict[output_key])

        software_key = _OUTPUT_MAPPING["software"]
        if software_key in in_dict:
            self.software = {}
            for key, pkg_list in in_dict[software_key].items():
                self.software[key] = [SoftwareInfo(**pkg_conf) for pkg_conf in pkg_list]

    def to_dict(self):
        """Generate a dict for encoders (json, yaml) and uploaders.

        The generated dict preserves the existing serialized format
        so that previous result files work as expected.
        """
        import copy

        output = {}
        for lookup_key, output_val in _OUTPUT_MAPPING.items():
            if lookup_key == "keys":
                if self.keys:
                    output.update(self.keys)
            else:
                val = getattr(self, lookup_key, None)
                if isinstance(val, (dict, list)):
                    output[output_val] = copy.deepcopy(val)
                else:
                    output[output_val] = val

        return output
