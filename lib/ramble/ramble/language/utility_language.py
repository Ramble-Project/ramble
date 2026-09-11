# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import functools
from typing import Optional

import ramble.language.language_helpers
import ramble.language.shared_language

UtilityMeta = ramble.language.shared_language.SharedMeta
utility_directive = functools.partial(UtilityMeta.directive, language_type="utility")


@utility_directive("env_sources")
def env_source(script_path: str, when=None, **kwargs):
    def _execute_env_source(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, script_path, "env_source"
        )
        when_key = frozenset(when_list)
        if when_key not in obj.env_sources:
            obj.env_sources[when_key] = []
        obj.env_sources[when_key].append(
            {
                "script_path": script_path,
                "when": when_list,
            }
        )

    return _execute_env_source


@utility_directive("env_sets")
def env_set(var: str, value: str, when=None, **kwargs):
    def _execute_env_set(obj):
        when_list = ramble.language.language_helpers.build_when_list(when, obj, var, "env_set")
        when_key = frozenset(when_list)
        if when_key not in obj.env_sets:
            obj.env_sets[when_key] = []
        obj.env_sets[when_key].append(
            {
                "var": var,
                "value": value,
                "when": when_list,
            }
        )

    return _execute_env_set


@utility_directive("env_prepends")
def env_prepend(var: str, value: str, when=None, **kwargs):
    def _execute_env_prepend(obj):
        when_list = ramble.language.language_helpers.build_when_list(when, obj, var, "env_prepend")
        when_key = frozenset(when_list)
        if when_key not in obj.env_prepends:
            obj.env_prepends[when_key] = []
        obj.env_prepends[when_key].append(
            {
                "var": var,
                "value": value,
                "when": when_list,
            }
        )

    return _execute_env_prepend


@utility_directive("env_appends")
def env_append(var: str, value: str, when=None, **kwargs):
    def _execute_env_append(obj):
        when_list = ramble.language.language_helpers.build_when_list(when, obj, var, "env_append")
        when_key = frozenset(when_list)
        if when_key not in obj.env_appends:
            obj.env_appends[when_key] = []
        obj.env_appends[when_key].append(
            {
                "var": var,
                "value": value,
                "when": when_list,
            }
        )

    return _execute_env_append


@utility_directive("fetch_mappings")
def fetch_mapping(utility_var: str, fetch_var: str, fallback_for=None, when=None, **kwargs):
    def _execute_fetch_mapping(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, utility_var, "fetch_mapping"
        )
        when_key = frozenset(when_list)
        if when_key not in obj.fetch_mappings:
            obj.fetch_mappings[when_key] = []
        obj.fetch_mappings[when_key].append(
            {
                "utility_var": utility_var,
                "fetch_var": fetch_var,
                "fallback_for": fallback_for if fallback_for is not None else [],
                "when": when_list,
            }
        )

    return _execute_fetch_mapping


@utility_directive("bootstrappable")
def bootstrappable(is_bootstrappable: bool, when=None, **kwargs):
    def _execute_bootstrappable(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, str(is_bootstrappable), "bootstrappable"
        )
        when_key = frozenset(when_list)
        if when_key not in obj.bootstrappable:
            obj.bootstrappable[when_key] = []
        obj.bootstrappable[when_key].append(
            {
                "is_bootstrappable": is_bootstrappable,
                "when": when_list,
            }
        )

    return _execute_bootstrappable


@utility_directive("missing_error_messages")
def missing_error_message(message: str, when=None, **kwargs):
    def _execute_missing_error_message(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, message, "missing_error_message"
        )
        when_key = frozenset(when_list)
        if when_key not in obj.missing_error_messages:
            obj.missing_error_messages[when_key] = []
        obj.missing_error_messages[when_key].append(
            {
                "message": message,
                "when": when_list,
            }
        )

    return _execute_missing_error_message


@utility_directive("provided_executables")
def provides_executable(
    executable: str,
    version_cmd: "Optional[str]" = None,
    version_regex: "Optional[str]" = None,
    when=None,
    **kwargs,
):
    def _execute_provides_executable(obj):
        when_list = ramble.language.language_helpers.build_when_list(
            when, obj, executable, "provides_executable"
        )
        when_key = frozenset(when_list)
        if when_key not in obj.provided_executables:
            obj.provided_executables[when_key] = []
        obj.provided_executables[when_key].append(
            {
                "executable": executable,
                "version_cmd": version_cmd,
                "version_regex": version_regex,
                "when": when_list,
            }
        )

    return _execute_provides_executable
