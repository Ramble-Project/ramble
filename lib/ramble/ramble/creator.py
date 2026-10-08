# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

import llnl.util.filesystem as fs

import ramble.paths
import ramble.repository
import ramble.util.naming as nm


def get_template(object_type):
    """Load the python template for a given ObjectType from templates directory."""
    type_def = ramble.repository.type_definitions.get(object_type, {})
    tpl_name = type_def.get("file_name", "").replace("base_", "") + ".tpl"
    tpl_dir = os.path.join(ramble.paths.share_path, "templates")

    for name in (tpl_name, "generic.py.tpl"):
        tpl_path = os.path.join(tpl_dir, name)
        if os.path.exists(tpl_path):
            with open(tpl_path, encoding="utf-8") as f:
                return f.read()

    # Fail-safe fallback if the template file is missing
    return """# Copyright 2022-2026 The Ramble Authors
class {class_name}:
    name = "{name}"
"""


def get_target_repo(repo_name_or_path, object_type):
    """Finds the target repository based on name or path."""
    repo_path = ramble.repository.paths[object_type]

    if not repo_name_or_path or repo_name_or_path == "builtin":
        # Fallback to builtin or first registered
        for r in repo_path.repos:
            if r.namespace == "builtin":
                return r
        if repo_path.repos:
            return repo_path.repos[0]
        # If no repos registered, load builtin manually
        return ramble.repository.Repo(ramble.paths.builtin_path, object_type)

    # Check if it is an existing directory
    if os.path.isdir(repo_name_or_path):
        canon_path = os.path.realpath(repo_name_or_path)
        for r in repo_path.repos:
            if os.path.realpath(r.root) == canon_path:
                return r
        return ramble.repository.Repo(canon_path, object_type)

    # Try matching by namespace name
    for r in repo_path.repos:
        if r.namespace == repo_name_or_path:
            return r

    raise ValueError(f"No repository found with name or path: '{repo_name_or_path}'")


def create_object(
    object_type, name, repo_name_or_path=None, base_class=None, maintainers=None, tags=None
):
    """Generates directory and template stub for a new object definition."""
    nm.validate_module_name(name)

    # Retrieve/validate repository
    repo = get_target_repo(repo_name_or_path, object_type)

    # Resolve sub-directories
    type_def = ramble.repository.type_definitions[object_type]
    obj_dir = os.path.join(repo.objects_path, name)
    file_path = os.path.join(obj_dir, type_def["file_name"])

    if os.path.exists(obj_dir):
        raise FileExistsError(f"Object directory already exists: '{obj_dir}'")

    # Determine Class Name
    class_name = nm.mod_to_class(name)

    # Choose template & default base class
    template = get_template(object_type)
    default_base = type_def.get("default_base", "object")
    resolved_base = base_class or default_base
    kit_name = type_def.get("kit_name") or "appkit"

    # Format metadata variables
    m_args = ", ".join(repr(m) for m in (maintainers or []))
    t_args = ", ".join(repr(t) for t in (tags or []))

    # Write stub contents
    fs.mkdirp(obj_dir)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(
            template.format(
                class_name=class_name,
                base_class=resolved_base,
                name=name,
                maintainers=m_args,
                tags=t_args,
                kit_name=kit_name,
            )
        )

    return file_path, repo.namespace
