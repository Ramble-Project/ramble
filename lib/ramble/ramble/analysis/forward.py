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

import ramble.util.lock as lk
from ramble.analysis.base import AnalysisStrategyBase
from ramble.util.foms import NULL_CONTEXT as _NULL_CONTEXT
from ramble.util.logger import logger


class ForwardAnalysisStrategy(AnalysisStrategyBase):
    """Forward regex-based analysis/extraction strategy."""

    def __call__(self, workspace):
        app = self.app_inst

        prepared = self._prepare_analysis(workspace)
        if prepared is None:
            return
        criteria_list, files, f_defs, inmem_defs = prepared

        exp_lock = app.experiment_lock
        fom_values, context_metadata, null_key = self._init_fom_containers()

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

                context_entries = []
                for context, foms in file_conf["contexts"].items():
                    context_def = (
                        f_defs[context]["definition"] if context != _NULL_CONTEXT else None
                    )
                    context_pre_filter = (
                        context_def.get("pre_filter", "") if context_def is not None else ""
                    )
                    format_fields = (
                        tuple(
                            field_name
                            for _, field_name, _, _ in string.Formatter().parse(
                                context_def["format"]
                            )
                            if field_name
                        )
                        if context_def is not None and isinstance(context_def.get("format"), str)
                        else ()
                    )
                    context_foms = f_defs[context]["foms"]
                    fom_entries = [
                        (
                            fom,
                            context_foms[fom],
                            context_foms[fom].get("pre_filter", ""),
                            bool(context_foms[fom]["contexts"]),
                        )
                        for fom in foms
                    ]
                    context_entries.append(
                        (context, context_def, context_pre_filter, format_fields, fom_entries)
                    )

                with open(file, encoding="utf-8", errors="replace") as f:
                    for line in f:
                        if per_file_crit_objs:
                            per_file_crit_objs = self._update_per_file_criteria(
                                line, per_file_crit_objs
                            )

                        # Iterate over contexts and add matched contexts to active_contexts
                        for (
                            context,
                            context_conf,
                            context_pre_filter,
                            format_fields,
                            fom_entries,
                        ) in context_entries:
                            if context_conf is not None and context_pre_filter in line:
                                context_match = context_conf["regex"].match(line)

                                if context_match:
                                    context_vars = {k: context_match[k] for k in format_fields}
                                    context_name = (
                                        context_conf["format"].format(**context_vars)
                                        if isinstance(context_conf.get("format"), str)
                                        else str(context_conf.get("format"))
                                    )
                                    logger.debug(f"Line was: {line}")
                                    logger.debug(f" Context match {context} -- {context_name}")

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
                                    else:
                                        logger.debug(
                                            f"Context '{context_name}' (from '{context}') "
                                            "matched multiple times; earlier FOM values in this "
                                            "context may be overwritten."
                                        )

                            for fom, fom_conf, pre_filter, has_contexts in fom_entries:
                                if pre_filter not in line:
                                    continue
                                fom_context = (
                                    active_contexts.get(context, null_key)
                                    if has_contexts
                                    else null_key
                                )
                                self._extract_fom_from_line(
                                    line, fom, fom_conf, fom_context, fom_values
                                )

        self._finalize_analysis(
            workspace, criteria_list, f_defs, inmem_defs, fom_values, context_metadata
        )
