# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Define base classes for analysis strategies"""

import ramble.success_criteria
from ramble.experiment_result import ExperimentStatus
from ramble.language.application_language import ApplicationMeta
from ramble.success_criteria import SuccessCriteriaResult
from ramble.util.foms import NULL_CONTEXT as _NULL_CONTEXT
from ramble.util.foms import get_context_display_name
from ramble.util.logger import logger


class AnalysisStrategyBase(metaclass=ApplicationMeta):

    def __init__(self, app_inst):
        self.app_inst = app_inst

    def __call__(self, workspace):
        raise NotImplementedError

    def _prepare_analysis(self, workspace):
        """Perform pre-analysis checks and return (criteria_list, files, f_defs, inmem_defs),
        or None if analysis should be skipped or was satisfied from cache.
        """
        app = self.app_inst

        if app.get_status() == ExperimentStatus.UNKNOWN and not workspace.dry_run:
            logger.warn(f"Experiment has status {app.get_status()}. Skipping analysis..\n")
            app.result.finalize(workspace)
            return None

        # Exit early if read from cache works.
        if app.result.read_cache(workspace, app):
            app.result.finalize(workspace)
            return None

        criteria_list = app.success_list
        if not criteria_list:
            criteria_list = ramble.success_criteria.ScopedCriteriaList()
        criteria_list.reset()

        files, f_defs, inmem_defs = app.analysis_dicts(criteria_list)
        return criteria_list, files, f_defs, inmem_defs

    def _init_fom_containers(self):
        fom_values = {}
        context_metadata = {}
        null_key = (_NULL_CONTEXT, _NULL_CONTEXT, frozenset())
        context_metadata[null_key] = {
            "name": _NULL_CONTEXT,
            "def_name": _NULL_CONTEXT,
            "vars": {},
        }
        return fom_values, context_metadata, null_key

    def _update_per_file_criteria(self, line, per_file_crit_objs):
        if not per_file_crit_objs:
            return per_file_crit_objs

        app = self.app_inst
        matched = False
        for crit_obj in per_file_crit_objs:
            if crit_obj.passed(line, app):
                crit_obj.mark_found()
                matched = True
            elif crit_obj.anti_matched(line):
                crit_obj.mark_anti_found()
                matched = True

        if not matched:
            return per_file_crit_objs

        return [
            crit_obj
            for crit_obj in per_file_crit_objs
            if not crit_obj.found and not crit_obj.anti_found
        ]

    def _extract_fom_from_line(self, line, fom, fom_conf, fom_context, fom_values):
        """Attempt to match and extract a FOM from a log line.

        Returns True if a valid (non-None) FOM value was matched and recorded.
        """
        if fom_conf.get("pre_filter", "") not in line:
            return False

        fom_match = fom_conf["regex"].match(line)
        if not fom_match or fom_conf["group"] not in fom_conf["regex"].groupindex:
            return False

        fom_val = fom_match.group(fom_conf["group"])
        if fom_val is None:
            return False

        app = self.app_inst
        fom_vars = fom_match.groupdict()
        if fom_conf["fom_name_expanded"] is not None:
            fom_name = fom_conf["fom_name_expanded"]
        else:
            fom_name = app.expander.expand_var(fom, extra_vars=fom_vars)

        logger.debug(f" --- Matched fom {fom_name}")

        if fom_conf["units_expanded"] is not None:
            fom_unit = fom_conf["units"]
        else:
            fom_unit = app.expander.expand_var(
                fom_conf["units"],
                extra_vars=fom_vars,
            )

        if fom_context not in fom_values:
            fom_values[fom_context] = {}
        elif fom_name in fom_values[fom_context]:
            prev_val = fom_values[fom_context][fom_name]["value"]
            logger.debug(
                f" --- Overwriting FOM '{fom_name}' in context '{fom_context[0]}' "
                f"({prev_val} -> {fom_val})"
            )
        fom_values[fom_context][fom_name] = {
            "value": fom_val,
            "units": fom_unit,
            "origin": fom_conf["origin"],
            "origin_type": fom_conf["origin_type"],
            "fom_type": fom_conf["fom_type"],
        }
        return True

    def _finalize_analysis(
        self, workspace, criteria_list, f_defs, inmem_defs, fom_values, context_metadata
    ):
        app = self.app_inst
        app.extract_inmem_foms(inmem_defs, fom_values, context_metadata)

        # Test all non-file based success criteria
        for criteria_obj, _ in criteria_list.all_criteria():
            if criteria_obj.file is None:
                if criteria_obj.passed(app_inst=app, fom_values=fom_values):
                    criteria_obj.mark_found()

        # If an app has no FOMs defined, don't fail it for that
        success = (not f_defs and not inmem_defs) or any(
            value.get("origin_type") == "application"
            for fom in fom_values.values()
            for value in fom.values()
        )
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
                app.result.success_criteria[criteria_name] = SuccessCriteriaResult.PASSED
            else:
                app.result.success_criteria[criteria_name] = SuccessCriteriaResult.FAILED

        for context_key, fom_map in fom_values.items():
            metadata = context_metadata[context_key]
            context_map = {
                "name": metadata["name"],
                "foms": [],
                "display_name": get_context_display_name(metadata["name"]),
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
