# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Define the backwards-reading analysis strategy"""

import os

import ramble.util.lock as lk
from ramble.analysis.base import AnalysisStrategyBase
from ramble.util.foms import NULL_CONTEXT as _NULL_CONTEXT
from ramble.util.logger import logger


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

            if is_first_block and buffer.endswith(b"\n"):
                buffer = buffer[:-1]
            is_first_block = False

            nl_idx = buffer.find(b"\n")
            if nl_idx == -1:
                continue

            complete = buffer[nl_idx + 1 :]
            buffer = buffer[:nl_idx]

            for line in reversed(complete.decode("utf-8", errors="replace").split("\n")):
                yield line + "\n"

        if file_size > 0:
            yield buffer.decode("utf-8", errors="replace") + "\n"


class BackwardsAnalysisStrategy(AnalysisStrategyBase):
    """Optimized analysis strategy that reads logs backwards and stops early."""

    def __call__(self, workspace):
        app = self.app_inst

        prepared = self._prepare_analysis(workspace)
        if prepared is None:
            return
        criteria_list, files, f_defs, inmem_defs = prepared

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
        fom_values, context_metadata, null_key = self._init_fom_containers()

        # Iterate over files. We already know they exist
        with lk.ReadTransaction(exp_lock):
            null_foms = f_defs.get(_NULL_CONTEXT, {}).get("foms", {})
            for file, file_conf in files.items():

                logger.debug(f"Reading log file backwards: {file}")

                if not os.path.exists(file):
                    logger.debug(f"Skipping analysis of non-existent file: {file}")
                    continue

                per_file_crit_objs = [
                    criteria_list.find_criteria(c) for c in file_conf["success_criteria"]
                ]

                foms_to_find = [
                    (fom, null_foms[fom], null_foms[fom].get("pre_filter", ""))
                    for fom in file_conf["contexts"].get(_NULL_CONTEXT, [])
                ]

                for line in _read_file_backwards(file):
                    if per_file_crit_objs:
                        per_file_crit_objs = self._update_per_file_criteria(
                            line, per_file_crit_objs
                        )

                    if foms_to_find:
                        matched_foms = None
                        for fom, fom_conf, pre_filter in foms_to_find:
                            if pre_filter in line and self._extract_fom_from_line(
                                line, fom, fom_conf, null_key, fom_values
                            ):
                                if matched_foms is None:
                                    matched_foms = {fom}
                                else:
                                    matched_foms.add(fom)
                        if matched_foms is not None:
                            foms_to_find = [
                                entry for entry in foms_to_find if entry[0] not in matched_foms
                            ]

                    # Stop reading if everything is found
                    if not foms_to_find and not per_file_crit_objs:
                        logger.debug("Found all FOMs and success criteria, stopping early.")
                        break

        self._finalize_analysis(
            workspace, criteria_list, f_defs, inmem_defs, fom_values, context_metadata
        )
