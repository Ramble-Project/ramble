# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import functools
from typing import Optional

import ramble.language.shared_language

WorkflowManagerMeta = ramble.language.shared_language.SharedMeta
workflow_manager_directive = functools.partial(
    WorkflowManagerMeta.directive, language_type="workflow_manager"
)


@workflow_manager_directive(dicts="object_variables", init_value={})
def workflow_manager_variable(
    name: str,
    default,
    description: str,
    values: Optional[list] = None,
    expandable: bool = True,
    track_used: bool = False,
    when=None,
    **kwargs,
):
    """Define a variable for this wm
    Args:
        name: Name of variable
        default: Default value if the variable is not defined
        description: Description of the variable
        values: Optional list of suggested values for this variable
        expandable (bool): True if the variable should be expanded, False if not.
        track_used (bool): True if the variable should be tracked as used,
                           False if not. Can help with allowing lists without vectorizing
        when (list | None): List of when conditions to apply to directive

    """

    def _define_wm_variable(wm):
        ramble.language.shared_language.variable(
            name,
            default,
            description=description,
            values=values,
            expandable=expandable,
            track_used=track_used,
            when=when,
            error_context="workflow_manager_variable",
            **kwargs,
        )(wm)

    return _define_wm_variable


@workflow_manager_directive(dicts="class_families", init_value={})
def workflow_manager_family(*names: str, **kwargs):
    """Add a new family to this workflow manager

    Args:
        name (str): Name of family to apply to this workflow manager
    """
    return ramble.language.shared_language.class_family(*names, **kwargs)
