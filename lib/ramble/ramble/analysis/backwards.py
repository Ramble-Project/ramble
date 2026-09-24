# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Define the backwards-reading analysis strategy"""

import os

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


def _read_file_backwards(file_path, block_size=4096):
    """Yield lines from a file backwards, matching the forward reader."""
    with open(file_path, "rb") as f:
        f.seek(0, os.SEEK_END)
        file_size = f.tell()
        position = file_size
        buffer = b""
        is_first_block = True

        while position > 0:
            grab_size = min(block_size, position)
            position -= grab_size
            f.seek(position)
            chunk = f.read(grab_size)
            buffer = chunk + buffer

            lines = buffer.split(b"\n")
            if is_first_block and lines and lines[-1] == b"":
                lines.pop()
            is_first_block = False
            buffer = lines[0]

            for line in reversed(lines[1:]):
                yield line.decode("utf-8", errors="replace") + "\n"

        if file_size > 0:
            yield buffer.decode("utf-8", errors="replace") + "\n"


class BackwardsAnalysisStrategy(AnalysisStrategyBase):
    """Optimized analysis strategy that reads logs backwards and stops early."""

    def __call__(self, workspace):
        app = self.app_inst

        if app.get_status() == ExperimentStatus.UNKNOWN and not workspace.dry_run:
            logger.warn(f"Experiment has status {app.get_status()}. Skipping analysis..\n")
            app.result.finalize(workspace)
            return

        # Exit early if read from cache works.
        if app.result.read_cache(workspace, app):
            app.result.finalize(workspace)
            return

        criteria_list = app.success_list
        if not criteria_list:
            criteria_list = ramble.success_criteria.ScopedCriteriaList()
        criteria_list.reset()

        files, f_defs, inmem_defs = app.analysis_dicts(criteria_list)

        # Validate that only the null context is used
        for file_conf in files.values():
            for context in file_conf["contexts"]:
                if context != _NULL_CONTEXT:
                    if getattr(app, "analysis_strategy", None) is None:
                        logger.debug(
                            "Falling back to forward-reading strategy due to non-null context."
                        )
                        import ramble.analysis as ra

                        forward_strategy = ra.get_strategy("forward", app)
                        return forward_strategy(workspace)
                    else:
                        raise ValueError(
                            f"BackwardsAnalysisStrategy cannot be used because "
                            f"context '{context}' is not the null context. "
                            "This strategy only supports the null context."
                        )

        # Validate that only static FOMs and static units are used
        for context_dict in f_defs.values():
            for fom_name, fom_conf in context_dict.get("foms", {}).items():
                if (
                    fom_conf.get("fom_name_expanded") is None
                    or fom_conf.get("units_expanded") is None
                ):
                    if getattr(app, "analysis_strategy", None) is None:
                        logger.debug(
                            "Falling back to forward-reading strategy due to dynamic "
                            "FOM name or units."
                        )
                        import ramble.analysis as ra

                        forward_strategy = ra.get_strategy("forward", app)
                        return forward_strategy(workspace)
                    else:
                        raise ValueError(
                            f"BackwardsAnalysisStrategy cannot be used because "
                            f"FOM '{fom_name}' has dynamic name or units. "
                            "This strategy only supports static FOMs."
                        )

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

                logger.debug(f"Reading log file backwards: {file}")

                if not os.path.exists(file):
                    logger.debug(f"Skipping analysis of non-existent file: {file}")
                    continue

                per_file_crit_objs = [
                    criteria_list.find_criteria(c) for c in file_conf["success_criteria"]
                ]

                foms_to_find = set(file_conf["contexts"].get(_NULL_CONTEXT, []))

                for line in _read_file_backwards(file):
                    new_per_file_crit_objs = []
                    for crit_obj in per_file_crit_objs:
                        if crit_obj.passed(line, app):
                            crit_obj.mark_found()
                        elif crit_obj.anti_matched(line):
                            crit_obj.mark_anti_found()
                        else:
                            new_per_file_crit_objs.append(crit_obj)
                    per_file_crit_objs = new_per_file_crit_objs

                    for fom in list(foms_to_find):
                        fom_conf = f_defs[_NULL_CONTEXT]["foms"][fom]
                        if fom_conf.get("pre_filter", "") not in line:
                            fom_match = None
                        else:
                            fom_match = fom_conf["regex"].match(line)

                        if fom_match:
                            fom_vars = fom_match.groupdict()
                            if fom_conf["fom_name_expanded"] is not None:
                                fom_name = fom_conf["fom_name_expanded"]
                            else:
                                fom_name = app.expander.expand_var(fom, extra_vars=fom_vars)

                            if fom_conf["group"] in fom_conf["regex"].groupindex:
                                fom_val = fom_match.group(fom_conf["group"])
                                if fom_val is not None:
                                    if fom_conf["units_expanded"] is not None:
                                        fom_unit = fom_conf["units"]
                                    else:
                                        fom_unit = app.expander.expand_var(
                                            fom_conf["units"],
                                            extra_vars=fom_vars,
                                        )

                                    if null_key not in fom_values:
                                        fom_values[null_key] = {}
                                    fom_values[null_key][fom_name] = {
                                        "value": fom_val,
                                        "units": fom_unit,
                                        "origin": fom_conf["origin"],
                                        "origin_type": fom_conf["origin_type"],
                                        "fom_type": fom_conf["fom_type"],
                                    }
                                    foms_to_find.remove(fom)

                    # Stop reading if everything is found
                    if not foms_to_find and not per_file_crit_objs:
                        logger.debug("Found all FOMs and success criteria, stopping early.")
                        break

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
