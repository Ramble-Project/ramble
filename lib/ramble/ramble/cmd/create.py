# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import signal

import ramble.creator
import ramble.repository
import ramble.spec
import ramble.util.naming as nm
from ramble.main import POSIX_SIGNAL_EXIT_OFFSET
from ramble.util.logger import logger

description = "create a new application, modifier, or other object definition"
section = "config"
level = "long"

# Mapping of CLI choices to repository ObjectTypes
type_mapping = {
    "application": ramble.repository.ObjectTypes.applications,
    "modifier": ramble.repository.ObjectTypes.modifiers,
    "package-manager": ramble.repository.ObjectTypes.package_managers,
    "workflow-manager": ramble.repository.ObjectTypes.workflow_managers,
    "system": ramble.repository.ObjectTypes.systems,
    "platform": ramble.repository.ObjectTypes.platforms,
}


def setup_parser(subparser):
    """Setup parser options for create command."""

    subparser.add_argument(
        "object_type",
        nargs="?",
        help=(
            "the type of object definition to create or a namespaced spec "
            "(e.g., application, or builtin.app.foo)"
        ),
    )
    subparser.add_argument(
        "name",
        nargs="?",
        help="the name of the new definition (e.g., my-app)",
    )
    subparser.add_argument(
        "-r",
        "--repo",
        action="store",
        dest="repo",
        help="repository name (namespace) or path where the definition should be created",
    )
    subparser.add_argument(
        "-b",
        "--base",
        action="store",
        dest="base",
        help="base class to inherit from (e.g., ExecutableApplication, BasicModifier)",
    )
    subparser.add_argument(
        "-m",
        "--maintainers",
        action="store",
        dest="maintainers",
        help="comma-separated list of maintainers (GitHub usernames)",
    )
    subparser.add_argument(
        "-t",
        "--tags",
        action="store",
        dest="tags",
        help="comma-separated list of tags to categorize this definition",
    )
    subparser.add_argument(
        "-i",
        "--interactive",
        action="store_true",
        dest="interactive",
        help="force interactive creation wizard",
    )


def prompt_for_choice(question, choices):
    """Prompts the user to select an option by number."""
    print(f"\n{question}")
    for idx, item in enumerate(choices, 1):
        print(f"  {idx}) {item}")

    while True:
        try:
            selection = input("Enter choice (number): ").strip()
            if not selection:
                continue
            val = int(selection)
            if 1 <= val <= len(choices):
                return choices[val - 1]
        except ValueError:
            pass
        print(f"Invalid selection. Please enter a number between 1 and {len(choices)}.")


def discover_base_classes(obj_type):
    """Discovers and filters matching base classes dynamically."""
    try:
        all_bases = ramble.repository.all_object_names(ramble.repository.ObjectTypes.base_classes)
    except ramble.repository.NoRepoConfiguredError:
        all_bases = []

    # Define keyword filters to group base classes by object type
    filters = {
        ramble.repository.ObjectTypes.applications: ["app"],
        ramble.repository.ObjectTypes.modifiers: ["mod"],
        ramble.repository.ObjectTypes.package_managers: ["package", "pkg"],
        ramble.repository.ObjectTypes.workflow_managers: ["workflow", "wm"],
        ramble.repository.ObjectTypes.systems: ["system"],
        ramble.repository.ObjectTypes.platforms: ["platform"],
    }

    keywords = filters.get(obj_type, [])
    matched_bases = [
        nm.mod_to_class(base) for base in all_bases if any(kw in base for kw in keywords)
    ]

    # Fallback to generic classes if no matches found
    if not matched_bases:
        matched_bases = ["object"]

    return matched_bases


def run_interactive_wizard():
    """Runs the step-by-step interactive wizard."""
    print("\n" + "=" * 40)
    print(" Ramble Object Creation Wizard ")
    print("=" * 40)

    # Select Object Type
    type_choices = list(type_mapping.keys())
    chosen_type_str = prompt_for_choice(
        "Select the type of object you want to create:", type_choices
    )
    obj_type = type_mapping[chosen_type_str]

    # Enter Name
    while True:
        name = input("\nEnter a name for the new definition: ").strip()
        if not name:
            continue
        try:
            nm.validate_module_name(name)
            break
        except Exception as e:
            print(
                f"Invalid name: {e}.\n"
                "Names must be valid python identifiers (lowercase, digits, and dashes)."
            )

    # Select Repository
    repo_path = ramble.repository.paths[obj_type]
    repo_options = []
    repo_map = {}
    for r in repo_path.repos:
        display_str = f"{r.namespace} ({r.root})"
        repo_options.append(display_str)
        repo_map[display_str] = r.namespace

    if len(repo_options) > 1:
        repo_selection_display = prompt_for_choice(
            "Select the repository to add it to:", repo_options
        )
        repo_selection = repo_map[repo_selection_display]
    elif repo_options:
        repo_selection = repo_path.repos[0].namespace
        print(f"\nDefaulting to repository: '{repo_selection}' ({repo_path.repos[0].root})")
    else:
        repo_selection = "builtin"
        print(f"\nDefaulting to repository: '{repo_selection}'")

    # Dynamic Base Class selection
    base_options = discover_base_classes(obj_type)
    if len(base_options) > 1:
        base_class = prompt_for_choice("Select the base class / template:", base_options)
    else:
        base_class = base_options[0]
        print(f"\nDefaulting to base class: '{base_class}'")

    maintainers_raw = input(
        "\nEnter maintainer GitHub usernames (comma-separated, optional): "
    ).strip()
    maintainers = [m.strip() for m in maintainers_raw.split(",")] if maintainers_raw else []

    tags_raw = input("\nEnter tags for categorization (comma-separated, optional): ").strip()
    tags = [t.strip() for t in tags_raw.split(",")] if tags_raw else []

    return obj_type, name, repo_selection, base_class, maintainers, tags


def create(parser, args):
    """Main command runner logic."""

    obj_type = None
    name = None
    repo = args.repo
    base = args.base
    maintainers = [m.strip() for m in args.maintainers.split(",")] if args.maintainers else []
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []

    if args.object_type:
        spec = ramble.spec.Spec(args.object_type)
        if spec.object_type and spec.name:
            obj_type = spec.object_type
            name = spec.name
            if spec.namespace:
                repo = spec.namespace
        else:
            type_map = ramble.repository.get_object_type_map()
            if args.object_type in type_map:
                obj_type = type_map[args.object_type]
                name = args.name

    # Check if interactive wizard is requested or needed
    if args.interactive or not obj_type or not name:
        import sys

        if not sys.stdin.isatty():
            if args.object_type and not name and obj_type:
                logger.die(f"Missing name for {args.object_type}.")
            logger.die(
                "Interactive wizard cannot be run in a non-interactive terminal. "
                "Please provide 'object_type' and 'name' arguments."
            )
        try:
            obj_type, name, repo, base, maintainers, tags = run_interactive_wizard()
        except KeyboardInterrupt:
            print("\n\n[ABORTED] Object creation cancelled.")
            return POSIX_SIGNAL_EXIT_OFFSET + signal.SIGINT.value

    try:
        file_path, repo_namespace = ramble.creator.create_object(
            object_type=obj_type,
            name=name,
            repo_name_or_path=repo,
            base_class=base,
            maintainers=maintainers,
            tags=tags,
        )

        logger.msg("\n" + "=" * 45)
        logger.msg(f"[SUCCESS] Created '{name}' in repo '{repo_namespace}'!")
        logger.msg("=" * 45)
        logger.msg(f"Generated Stub File: {file_path}\n")
        logger.msg("Next Steps:")
        logger.msg(f"  1. Open and edit '{file_path}' to define your custom configurations.")
        logger.msg("  2. Verify the definition is loaded successfully:")
        logger.msg(f"     $ ramble list --type {obj_type.name}")
        logger.msg("=" * 45)

    except FileExistsError as e:
        logger.die(f"Failed to create object: {e}")
    except Exception as e:
        logger.die(f"Error during creation: {e}")
