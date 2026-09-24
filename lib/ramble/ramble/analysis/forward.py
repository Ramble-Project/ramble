# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Define the forward-reading analysis strategy"""

import os
import string

import ramble.success_criteria
import ramble.util.lock as lk
from ramble.analysis.base import AnalysisStrategyBase
from ramble.experiment_result import ExperimentStatus
from ramble.util.logger import logger

_NULL_CONTEXT = "null"


def _get_context_display_name(context):
    return (
        f"default ({_NULL_CONTEXT}) context" if context == _NULL_CONTEXT else f"{context} context"
    )


class ForwardAnalysisStrategy(AnalysisStrategyBase):
    """Forward regex-based analysis/extraction strategy."""

    def __call__(self, workspace):
        app = self.app_inst

        if app.get_status() == ExperimentStatus.UNKNOWN and not workspace.dry_run:
            logger.warn(f"Experiment has status {app.get_status()}. Skipping analysis..\n")
            app.result.finalize(workspace)
            return

        def format_context(context_match, context_format):
            context_val = {}
            if isinstance(context_format, str):
                for group in string.Formatter().parse(context_format):
                    if group[1]:
                        context_val[group[1]] = context_match[group[1]]

            context_string = context_format.format(**context_val)
            return context_string

        # Exit early if read from cache works.
        if app.result.read_cache(workspace, app):
            app.result.finalize(workspace)
            return

        criteria_list = app.success_list
        if not criteria_list:
            criteria_list = ramble.success_criteria.ScopedCriteriaList()
        criteria_list.reset()

        files, f_defs, inmem_defs = app.analysis_dicts(criteria_list)

        exp_lock = app.experiment_lock

        fom_values = {}
        context_metadata = {}
        null_key = (_NULL_CONTEXT, _NULL_CONTEXT, frozenset())
        context_metadata[null_key] = {
            "name": _NULL_CONTEXT,
            "def_name": _NULL_CONTEXT,
            "vars": {},
        }

        # Iterate over files. We already know they exist
        with lk.ReadTransaction(exp_lock):
            for file, file_conf in files.items():

                # Start with no active contexts in a file.
                active_contexts = {}
                logger.debug(f"Reading log file: {file}")

                if not os.path.exists(file):
                    logger.debug(f"Skipping analysis of non-existent file: {file}")
                    continue

                per_file_crit_objs = [
                    criteria_list.find_criteria(c) for c in file_conf["success_criteria"]
                ]

                with open(file, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        new_per_file_crit_objs = []
                        for crit_obj in per_file_crit_objs:
                            if crit_obj.passed(line, app):
                                crit_obj.mark_found()
                            elif crit_obj.anti_matched(line):
                                crit_obj.mark_anti_found()
                            else:
                                new_per_file_crit_objs.append(crit_obj)
                        per_file_crit_objs = new_per_file_crit_objs

                        # Iterate over contexts and add matched contexts to active_contexts
                        for context, foms in file_conf["contexts"].items():
                            if context != _NULL_CONTEXT:
                                context_conf = f_defs[context]["definition"]
                                if context_conf.get("pre_filter", "") not in line:
                                    context_match = None
                                else:
                                    context_match = context_conf["regex"].match(line)

                                if context_match:
                                    context_name = format_context(
                                        context_match,
                                        context_conf["format"],
                                    )
                                    logger.debug(f"Line was: {line}")
                                    logger.debug(f" Context match {context} -- {context_name}")

                                    context_vars = context_match.groupdict()
                                    context_key = (
                                        context_name,
                                        context,
                                        frozenset(context_vars.items()),
                                    )

                                    active_contexts[context] = context_key

                                    if context_key not in fom_values:
                                        fom_values[context_key] = {}
                                        context_metadata[context_key] = {
                                            "name": context_name,
                                            "def_name": context,
                                            "vars": context_vars,
                                        }

                            for fom in foms:
                                fom_conf = f_defs[context]["foms"][fom]
                                if fom_conf.get("pre_filter", "") not in line:
                                    fom_match = None
                                else:
                                    fom_match = fom_conf["regex"].match(line)

                                if fom_match:
                                    fom_vars = fom_match.groupdict()
                                    if fom_conf["fom_name_expanded"] is not None:
                                        fom_name = fom_conf["fom_name_expanded"]
                                    else:
                                        fom_name = app.expander.expand_var(
                                            fom, extra_vars=fom_vars
                                        )

                                    if fom_conf["group"] in fom_conf["regex"].groupindex:
                                        logger.debug(f" --- Matched fom {fom_name}")
                                        fom_contexts = []
                                        # if a FOM has contexts, check if each is active
                                        if fom_conf["contexts"]:
                                            for _ in fom_conf["contexts"]:
                                                context_key = (
                                                    active_contexts[context]
                                                    if context in active_contexts
                                                    else null_key
                                                )
                                                fom_contexts.append(context_key)
                                        else:
                                            fom_contexts.append(null_key)

                                        for fom_context in fom_contexts:
                                            if fom_context not in fom_values:
                                                fom_values[fom_context] = {}
                                            fom_val = fom_match.group(fom_conf["group"])
                                            if fom_val is None:
                                                continue
                                            if fom_conf["units_expanded"] is not None:
                                                fom_unit = fom_conf["units"]
                                            else:
                                                fom_unit = app.expander.expand_var(
                                                    fom_conf["units"],
                                                    extra_vars=fom_vars,
                                                )
                                            fom_values[fom_context][fom_name] = {
                                                "value": fom_val,
                                                "units": fom_unit,
                                                "origin": fom_conf["origin"],
                                                "origin_type": fom_conf["origin_type"],
                                                "fom_type": fom_conf["fom_type"],
                                            }
        app.extract_inmem_foms(inmem_defs, fom_values, context_metadata)

        # Test all non-file based success criteria
        for criteria_obj, _ in criteria_list.all_criteria():
            if criteria_obj.file is None:
                if criteria_obj.passed(app_inst=app, fom_values=fom_values):
                    criteria_obj.mark_found()

        # If an app has no FOMs defined, don't fail it for that
        success = (not f_defs and not inmem_defs) or False
        for fom in fom_values.values():
            for value in fom.values():
                if "origin_type" in value and value["origin_type"] == "application":
                    success = True
        success = success and criteria_list.passed()

        if success:
            status = ExperimentStatus.SUCCESS
        else:
            preserved_terminal = {
                ExperimentStatus.CANCELLED,
                ExperimentStatus.TIMEOUT,
                ExperimentStatus.FAILED,
            }
            current_status = app.get_status()
            if current_status in preserved_terminal:
                status = current_status
            else:
                status = ExperimentStatus.FAILED

        # When workflow_manager is present, only use app_status when workflow is completed or
        # unresolved.
        if app.workflow_manager is not None:
            wm_status = app.workflow_manager.get_status(workspace)
            if not (
                wm_status is None
                or wm_status in [ExperimentStatus.COMPLETE, ExperimentStatus.UNRESOLVED]
            ):
                status = wm_status

        app.set_status(status)
        app.result.finalize(workspace)

        for criteria_obj, criteria_scope in criteria_list.all_criteria():
            if criteria_obj.owner is not None:
                criteria_name = f"{criteria_obj.owner.scoped_name}::{criteria_obj.name}"
            else:
                criteria_name = f"config::{criteria_scope}::{criteria_obj.name}"
            if criteria_obj.ok():
                app.result.success_criteria[criteria_name] = "PASSED"
            else:
                app.result.success_criteria[criteria_name] = "FAILED"

        for context_key, fom_map in fom_values.items():
            metadata = context_metadata[context_key]
            context_map = {
                "name": metadata["name"],
                "foms": [],
                "display_name": _get_context_display_name(metadata["name"]),
                "context_def_name": metadata["def_name"],
                "context_vars": metadata["vars"],
            }

            for fom_name, fom in fom_map.items():
                fom_copy = fom.copy()
                fom_copy["name"] = fom_name
                context_map["foms"].append(fom_copy)

            if metadata["name"] == _NULL_CONTEXT:
                app.result.contexts.insert(0, context_map)
            else:
                app.result.contexts.append(context_map)
