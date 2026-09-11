# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import contextlib
import copy
import datetime
import fnmatch
import os
import re
import shutil
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set

from ruamel import yaml

import llnl.util.filesystem as fs
from llnl.util import tty
from llnl.util.tty import log

import ramble.config
import ramble.context
import ramble.error
import ramble.experiment_result
import ramble.experiment_set
import ramble.keywords
import ramble.repository
import ramble.results_table
import ramble.schema.applications
import ramble.schema.merged
import ramble.schema.workspace
import ramble.software_environments
import ramble.spec
import ramble.util.hashing
import ramble.util.install_cache
import ramble.util.lock as lk
import ramble.util.path
import ramble.util.version
from ramble.mirror import MirrorStats
from ramble.namespace import namespace
from ramble.util import json_util
from ramble.util.conversions import list_str_to_list, strip_quotes
from ramble.util.logger import logger
from ramble.util.path import substitute_path_variables

import spack.util.spack_yaml as syaml
import spack.util.url as url_util
import spack.util.web as web_util

# Workspace-related constants

#: Environment variable used to indicate the active workspace
RAMBLE_WORKSPACE_VAR = "RAMBLE_WORKSPACE"

#: Subdirectory where workspace configs are stored
WORKSPACE_CONFIG_PATH = "configs"

#: Name of subdirectory within workspace where tables are stored
WORKSPACE_TABLES_PATH = "tables"

#: Name of subdirectory within workspace where results are stored
WORKSPACE_RESULTS_PATH = "results"

#: Name of subdirectory within workspaces where logs are stored
WORKSPACE_LOG_PATH = "logs"

#: Name of subdirectory within workspaces where experiments are stored
WORKSPACE_EXPERIMENT_PATH = "experiments"

#: Name of subdirectory within workspaces where input files are stored
WORKSPACE_INPUT_PATH = "inputs"

#: Name of subdirectory within workspaces where software environment
#: are stored
WORKSPACE_SOFTWARE_PATH = "software"

#: Name of the subdirectory where workspace archives are stored
WORKSPACE_ARCHIVE_PATH = "archive"

#: Name of the subdirectory where shared files are stored
WORKSPACE_SHARED_PATH = "shared"

#: Name of the subdirectory where shared license files are stored
WORKSPACE_SHARED_LICENSE_PATH = "licenses"

#: Name of the subdirectory where deployments are stored
WORKSPACE_DEPLOYMENTS_PATH = "deployments"

#: regex for validating workspace names
VALID_WORKSPACE_NAME_RE = re.compile(r"^\w[\w-]*$")
_DEF_REGEX = re.compile(r"\s*=\s*")

# File that includes licensing information for sourcing
LICENSE_INC_NAME = "license.inc"

#: Extension for template files
# Only files that end with this extension are considered valid templates by Ramble
TEMPLATE_EXTENSION = ".tpl"

#: Directory name for auxiliary software files
AUXILIARY_SOFTWARE_DIR_NAME = "auxiliary_software_files"

CONFIG_SECTION = namespace.workspace
CONFIG_FILE_NAME = "ramble.yaml"
LICENSES_FILE_NAME = "licenses.yaml"

METADATA_FILE_NAME = "workspace_metadata.yaml"

WORKSPACE_ALL_EXPERIMENTS_FILE = "all_experiments"

WORKSPACE_EXECUTION_TEMPLATE = "execute_experiment" + TEMPLATE_EXTENSION

#: Name of lockfile within a workspace
LOCKFILE_NAME = "ramble.lock"

#: Config schema for application files
applications_schema = ramble.schema.applications.schema

#: Config file information for workspaces.
#: Keys are filenames, values are dictionaries describing the config files.
config_schema = ramble.schema.workspace.schema

#: Currently activated workspace
_active_workspace: Optional["Workspace"] = None


def valid_workspace_name(name):
    return VALID_WORKSPACE_NAME_RE.match(name)


def validate_workspace_name(name):
    if not valid_workspace_name(name):
        logger.debug(f"Validation failed for {name}")
        raise ValueError(
            (
                "'%s': names must start with a letter, and only contain "
                "letters, numbers, _, and -."
            )
            % name
        )
    return name


def activate(ws):
    """Activate a workspace.

    To activate a workspace, we add its configuration scope to the
    existing Ramble configuration, and we set active to the current
    workspace.

    Arguments:
        ws (Workspace): the workspace to activate
    """
    global _active_workspace

    # Fail early to avoid ending in an invalid state
    if not isinstance(ws, Workspace):
        raise TypeError(f"`ws` should be of type {Workspace.__name__}")

    # Check if we need to reinitialize the store due to pushing the configuration
    # below.
    prepare_config_scope(ws)

    logger.debug(f"Using workspace '{ws.root}'")

    # Do this last, because setting up the config must succeed first.
    _active_workspace = ws


def deactivate():
    """Undo any configuration settings modified by ``activate()``."""
    global _active_workspace

    if not _active_workspace:
        return

    logger.debug(f"Deactivated workspace '{_active_workspace.root}'")

    try:
        deactivate_config_scope(_active_workspace)
    finally:
        _active_workspace = None


def prepare_config_scope(workspace):
    """Add workspace's scope to the global configuration search path."""
    for scope in workspace.config_scopes():
        ramble.config.config.push_scope(scope)


def deactivate_config_scope(workspace):
    """Remove any scopes from workspace from the global config path."""
    for scope in workspace.config_scopes():
        ramble.config.config.remove_scope(scope.name)


def all_workspace_names(parent_dir=None):
    """List the names of workspaces that currently exist."""
    if parent_dir:
        wspaths = get_workspace_path()
        canonical_parent = ramble.util.path.canonicalize_path(parent_dir)
        if canonical_parent not in wspaths:
            raise RambleWorkspaceError(
                f"Directory '{parent_dir}' is not in configured workspace_dirs"
            )
        wspaths = [canonical_parent]
    else:
        wspaths = get_workspace_path()

    names = set()
    for wspath in wspaths:
        if not os.path.exists(wspath):
            continue

        candidates = os.listdir(wspath)
        for candidate in candidates:
            cand_root = os.path.join(wspath, candidate)
            if valid_workspace_name(candidate) and is_workspace_dir(cand_root):
                names.add(candidate)
    return sorted(names)


def active_workspace():
    """Returns the active workspace when there is any"""
    return _active_workspace


def get_workspace_path():
    """Returns current directory of ramble-managed workspaces"""
    path_in_config = ramble.config.get("config:workspace_dirs")
    if not path_in_config:
        # command above should have worked, so if it doesn't, error out:
        logger.die("No config:workspace_dirs setting found in configuration!")

    if isinstance(path_in_config, str):
        paths = [path_in_config]
    else:
        paths = path_in_config

    return [ramble.util.path.canonicalize_path(str(p)) for p in paths]


def _root(name, parent_dir=None):
    """Non-validating version of root(), to be used internally."""
    if parent_dir:
        wspaths = get_workspace_path()
        canonical_parent = ramble.util.path.canonicalize_path(parent_dir)
        if canonical_parent not in wspaths:
            raise RambleWorkspaceError(
                f"Directory '{parent_dir}' is not in configured workspace_dirs"
            )
        wspaths = [canonical_parent]
    else:
        wspaths = get_workspace_path()

    for wspath in wspaths:
        cand_root = os.path.join(wspath, name)
        if is_workspace_dir(cand_root):
            return cand_root
    return os.path.join(wspaths[0], name)


def root(name, parent_dir=None):
    """Get the root directory for a workspace by name."""
    validate_workspace_name(name)
    return _root(name, parent_dir=parent_dir)


def exists(name, parent_dir=None):
    """Whether a workspace with this name exists or not."""
    if not valid_workspace_name(name):
        return False
    return os.path.isdir(root(name, parent_dir=parent_dir))


def active(name):
    """True if the named workspace is active."""
    return _active_workspace and name == _active_workspace.name


def get_filepath(path, file_name):
    if is_workspace_dir(path):
        return os.path.join(path, WORKSPACE_CONFIG_PATH, file_name)
    return None


def config_file(path):
    """Returns the path to a workspace's ramble.yaml"""
    return get_filepath(path, CONFIG_FILE_NAME)


def licenses_file(path):
    """Returns the path to a workspace's licenses.yaml"""
    return get_filepath(path, LICENSES_FILE_NAME)


def all_config_files(path):
    """Returns path to all yaml files in workspace config directory"""

    config_path = os.path.join(path, WORKSPACE_CONFIG_PATH)
    config_files = [
        os.path.join(config_path, f) for f in os.listdir(config_path) if f.endswith(".yaml")
    ]

    return config_files


def template_path(ws_path, requested_template_name):
    """Returns the path to a workspace's template file"""
    config_path = os.path.join(ws_path, WORKSPACE_CONFIG_PATH)
    template_file = requested_template_name + TEMPLATE_EXTENSION
    template_path = os.path.join(config_path, template_file)
    return template_path


def all_template_paths(path):
    """Returns (abs) path to available template files in the workspace"""
    templates: List[str] = []

    config_path = os.path.join(path, WORKSPACE_CONFIG_PATH)
    for root, _, files in os.walk(config_path):
        templates.extend(os.path.join(root, f) for f in files if f.endswith(TEMPLATE_EXTENSION))

    return templates


def is_workspace_dir(path):
    """Whether a directory contains a ramble workspace."""
    ret_val = os.path.isdir(path)
    if ret_val:
        ret_val = ret_val and os.path.exists(
            os.path.join(path, WORKSPACE_CONFIG_PATH, CONFIG_FILE_NAME)
        )
    return ret_val


def create(name, read_default_template=True, parent_dir=None):
    """Create a named workspace in Ramble"""
    validate_workspace_name(name)
    if exists(name, parent_dir=parent_dir):
        raise RambleWorkspaceError(f"'{name}': workspace already exists")

    ws_root = root(name, parent_dir=parent_dir)

    return Workspace(ws_root, read_default_template=read_default_template)


def config_dict(yaml_data):
    """Get the configuration scope section out of a ramble.yaml"""
    try:
        key = ramble.config.first_existing(yaml_data, ramble.schema.workspace.keys)
        return yaml_data[key]
    except KeyError:
        raise RambleActiveWorkspaceError(
            "ramble.yaml needs to contain at least one of the "
            f"required keys {ramble.schema.workspace.keys}"
        ) from None


def get_workspace(args, cmd_name, required=False):
    """Used by commands to get the active workspace.

    This first checks for a ``workspace`` argument, then looks at the
    ``active`` workspace.  We check args first because Ramble's
    subcommand arguments are parsed *after* the ``-s`` and ``-D``
    arguments to ``ramble``.  So there may be a ``workspace``
    argument that is *not* the active workspace, and we give it
    precedence.

    This is used by a number of commands for determining whether there is
    an active workspace.

    If a workspace is not found *and* is required, print an error
    message that says the calling command *needs* an active
    workspace.

    Arguments:
        args (ramble.namespace): argparse namespace with command arguments
        cmd_name (str): name of calling command
        required (bool): if ``True``, raise an exception when no workspace
                         is found; if ``False``, just return ``None``

    Returns:
        ramble.workspace.Workspace | None: Workspace instance if there is an arg or active
        workspace, ``None`` if no workspace is found and ``required`` is ``False``
    """

    logger.debug("In get_workspace()")

    workspace = getattr(args, namespace.workspace, None)
    if workspace:
        if exists(workspace):
            return read(workspace)
        elif is_workspace_dir(workspace):
            return Workspace(workspace)
        else:
            raise RambleWorkspaceError(f"no workspace in {workspace}")

    # try the active workspace. This is set by find_workspace (above)
    if _active_workspace:
        return _active_workspace
    # elif not required:
    else:
        logger.die(
            f"`ramble {cmd_name}` requires a workspace",
            "activate a workspace first:",
            "    ramble workspace activate WRKSPC",
            "or use:",
            f"    ramble -w WRKSPC {cmd_name} ...",
        )


class Workspace:
    """Class representing a working directory for workload
    experiments

    Each workspace must have a config directory, that contains 2
    files by default.

    - ramble.yaml
    - execute_experiment.tpl

    The ramble.yaml file is the overall configuration file for
    this workspace. It defines all experiments, variables, and
    the entire software stack.

    The execute_experiment.tpl file is a template script that
    constants the blueprints for running each experiment.
    There are several ramble language features that can be used
    within the script, to help it render properly for all
    experiments.

    Each file with the suffix of .tpl will be expanded into the
    experiment directory, with the .tpl suffix removed.

    Directories will be created for each experiment, when the
    relevant phase of the application is executed. The workspace
    provides a self contained execution environment where experiments
    can be performed.
    """

    inventory_file_name = "ramble_inventory.json"
    hash_file_name = "workspace_hash.sha256"
    _latest_archive: Optional[str] = None

    def __init__(self, root, dry_run=False, read_default_template=True):
        logger.debug(f"In workspace init. Root = {root}")
        self.root = ramble.util.path.canonicalize_path(root)
        self.txlock = lk.Lock(self._transaction_lock_path)
        self.dry_run = dry_run
        self.repeat_success_strict = True

        self.read_default_template = read_default_template
        self.configs = ramble.config.ConfigScope(namespace.workspace, self.config_dir)
        self._templates = {}
        self._auxiliary_software_files = {}
        self.software_mirror_path = None
        self.input_mirror_path = None
        self.mirror_existed = None
        self.software_mirror_stats = None
        self.input_mirror_stats = None
        self.input_mirror_cache = None
        self.software_mirror_cache = None
        self.software_environments = None
        self.metadata = syaml.syaml_dict()
        self.hash_inventory: Dict[str, List[Any]] = {namespace.experiment: [], "versions": []}
        version = ramble.util.version.get_version()
        self.hash_inventory["versions"].append(
            {
                "name": namespace.ramble,
                "version": version,
                "digest": ramble.util.hashing.hash_string(version),
            }
        )

        self.workspace_hash = None

        self.results_tables = ramble.results_table.ResultsTables()

        self.specs = []

        self.config_sections = {}

        self.install_cache = ramble.util.install_cache.SetCache()

        # A per-package_manager dict mapping package spec to its install prefix.
        # This can be re-used by all experiments of the workspace.
        self.pkg_path_cache: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # A simple dict mapping a file's src_path to its content.
        # This is currently used as a cache for reading per-object template contents.
        self._inmem_file_cache = {}

        # A workspace-level cache that's used by objects to cache command returns.
        self.object_command_cache = {}

        self.results = self.default_results()

        # A cache structured as {pkg_man: {env_name: pkg_list}}.
        # It's used to cache package provenance info from different package managers.
        self.pkg_prov_cache: Dict[str, Dict[str, Any]] = defaultdict(dict)

        # Key for each application config should be it's filepath
        # Format for an application config should be:
        #  {
        #     'filename': <filename>,
        #     'path': <filepath>,
        #     'raw_yaml': <raw_yaml>,
        #     'yaml': <yaml>
        #  }
        self.application_configs = {}

        self.experiments_script = None

        self._read()

        # Create a logger to redirect certain prints from screen to log file
        self.logger = log.log_output(echo=False, debug=tty.debug_level())

        self.deployment_name = self.name

        # Used by profiling phases
        self.profile_config = None

    def _re_read(self):
        """Reinitialize the workspace object if it has been written (this
        may not be true if the workspace was just created in this running
        instance of ramble)."""
        for section in self.config_sections.values():
            if not os.path.exists(section["filename"]):
                return

        was_active = _active_workspace == self
        if was_active:
            deactivate_config_scope(self)

        self.clear()
        self._read()

        if was_active:
            prepare_config_scope(self)

    def _read(self):
        # Create the workspace config section
        with lk.ReadTransaction(self.txlock):
            self.config_sections[namespace.workspace] = {
                "filename": self.config_file_path,
                "path": self.config_file_path,
                "schema": config_schema,
                "section_filename": self.config_file_path,
                "raw_yaml": None,
                "yaml": None,
            }

            keywords = ramble.keywords.keywords

            read_default = not os.path.exists(self.config_file_path)
            if read_default:
                self.read_config(CONFIG_SECTION, self._default_config_yaml())
            else:
                with open(self.config_file_path, encoding="utf-8") as f:
                    self.read_config(CONFIG_SECTION, f)

            read_default_script = self.read_default_template
            ext_len = len(TEMPLATE_EXTENSION)
            if os.path.exists(self.config_dir):
                for root, _, files in os.walk(self.config_dir):
                    rel_root = os.path.relpath(root, self.config_dir)
                    processed_root = "" if rel_root == "." else rel_root + os.sep
                    for filename in files:
                        if filename.endswith(TEMPLATE_EXTENSION):
                            read_default_script = False
                            template_name = processed_root + filename[0:-ext_len]
                            template_path = os.path.join(root, filename)
                            if keywords.is_reserved(template_name):
                                raise RambleInvalidTemplateNameError(
                                    f"Template file {filename} results in a "
                                    f"template name of {template_name}"
                                    + " which is reserved by ramble."
                                )

                            with open(template_path, encoding="utf-8") as f:
                                self.read_template(template_name, f.read())

                if os.path.exists(self.auxiliary_software_dir):
                    for filename in os.listdir(self.auxiliary_software_dir):
                        aux_file_path = os.path.join(self.auxiliary_software_dir, filename)
                        with open(aux_file_path, encoding="utf-8") as f:
                            self._read_auxiliary_software_file(filename, f.read())

            if read_default_script:
                template_name = WORKSPACE_EXECUTION_TEMPLATE[0:-ext_len]
                self.read_template(template_name, self._template_execute_script())

            self._read_metadata()
            if hasattr(self, "results") and self.results:
                self.results["metadata"] = self.metadata

    @classmethod
    def _template_execute_script(self):
        shell = ramble.config.get("config:shell")
        shell_path = os.path.join("/bin/", shell)
        script = f"#!{shell_path}\n" + """\
# This is a template execution script for
# running the execute pipeline.
#
# Variables surrounded by curly braces will be expanded
# when generating a specific execution script.
# Some example variables are:
#   - experiment_run_dir (Will be replaced with the experiment directory)
#   - command (Will be replaced with the command to run the experiment)
#   - log_dir (Will be replaced with the logs directory)
#   - experiment_name (Will be replaced with the name of the experiment)
#   - workload_run_dir (Will be replaced with the directory of the workload
#   - application_name (Will be replaced with the name of the application)
#   - n_nodes (Will be replaced with the required number of nodes)
#   Any experiment parameters will be available as variables as well.

{workflow_banner}

cd "{experiment_run_dir}"

{command}
"""

        return script

    @classmethod
    def _default_config_yaml(self):

        # Construct string for default variants
        variant_string = ""

        # Set default system to the user-managed one,
        # which provides defaults for required variables such as
        # batch_submit and mpi_command.
        all_variants = {"system": "user-managed"}
        for scope in ramble.config.scopes():
            if namespace.workspace not in scope:
                variant_dict = ramble.config.get(namespace.variants, scope=scope)
                if variant_dict:
                    all_variants.update(variant_dict)

        variant_defs = []
        for var, val in all_variants.items():
            variant_defs.append(f"    {var}: {val}")

        if variant_defs:
            merged_string = "\n".join(variant_defs)
            variant_string = f"""  {namespace.variants}:
{merged_string}"""

        return f"""\
# This is a ramble workspace config file.
#
# It describes the experiments, the software stack
# and all variables required for ramble to configure
# experiments.
# As an example, experiments can be defined as follows.
# applications:
#   hostname: # Application name, as seen in `ramble list`
#     variables:
#       iterations: '5'
#     workloads:
#       serial: # Workload name, as seen in `ramble info <app>`
#         variables:
#           type: 'test'
#         experiments:
#           single_node: # Arbitrary experiment name
#             variables:
#               n_ranks: '{{processes_per_node}}'

ramble:
  env_vars:
    set:
      OMP_NUM_THREADS: '{{n_threads}}'
{variant_string}
  {namespace.variables}:
    processes_per_node: 1
  {namespace.application}: {{}}
  {namespace.software}:
    {namespace.packages}: {{}}
    {namespace.environments}: {{}}
"""

    def read_config(self, section, f, raw_yaml=None):
        """Read configuration file"""
        config = self.config_sections[section]
        self._read_yaml(config, f, raw_yaml)
        self._check_deprecated(config["yaml"])

    def _read_metadata(self):
        """Read workspace metadata file

        If a metadata file exists in the workspace root, read it in, and
        populate this workspace's metadata object with its contents.
        """
        metadata_file_path = os.path.join(self.root, METADATA_FILE_NAME)

        if os.path.exists(metadata_file_path):
            with open(metadata_file_path, encoding="utf-8") as f:
                self.metadata = syaml.load(f)
        else:
            self.metadata = syaml.syaml_dict()
            self.metadata[namespace.metadata] = syaml.syaml_dict()

    def write_metadata(self):
        """Write out workspace metadata file

        Create, and populate the metadata file in the root of the workspace.
        This file can be used to house cross-pipeline information.
        """
        metadata_file_path = os.path.join(self.root, METADATA_FILE_NAME)

        with open(metadata_file_path, "w+", encoding="utf-8") as f:
            syaml.dump(self.metadata, stream=f)

    def _check_deprecated(self, config):
        """
        Trap and warn (or error) on deprecated configuration settings
        in the workspace config.
        """

        error_sections: List[str] = []
        deprecated_sections: List[str] = []

        if deprecated_sections:
            logger.warn("Your workspace configuration contains deprecated sections:")
            for section in deprecated_sections:
                logger.warn(f"     {section}")
            logger.warn("Please see the current workspace documentation and update")
            logger.warn("to ensure your workspace continues to function properly")

        if error_sections:
            logger.warn("Your workspace configuration contains invalid sections:")
            for section in deprecated_sections:
                logger.warn(f"     {section}")
            logger.die("Please update to the latest format.")

    def _read_yaml(self, config, f, raw_yaml=None):
        if raw_yaml:
            _, config["yaml"] = _read_yaml(f, config["schema"])
            config["raw_yaml"], _ = _read_yaml(raw_yaml, config["schema"])
        else:
            config["raw_yaml"], config["yaml"] = _read_yaml(f, config["schema"])

    def read_template(self, name, f):
        """Read a template file"""
        self._templates[name] = {
            "contents": f,
            "digest": ramble.util.hashing.hash_string(f),
        }

    def _read_auxiliary_software_file(self, name, f):
        """Read an auxiliary software file for generated software directories"""
        self._auxiliary_software_files[name] = f

    def write(self, software_dir=None, inputs_dir=None):
        """Write an in-memory workspace to its location on disk."""

        with lk.WriteTransaction(self.txlock, acquire=self._re_read):
            # Ensure required directory structure exists
            fs.mkdirp(self.path)
            fs.mkdirp(self.config_dir)
            fs.mkdirp(self.auxiliary_software_dir)
            fs.mkdirp(self.shared_dir)
            fs.mkdirp(self.shared_utilities_dir)
            fs.mkdirp(self.log_dir)
            fs.mkdirp(self.experiment_dir)

            if inputs_dir:
                os.symlink(os.path.abspath(inputs_dir), self.input_dir, target_is_directory=True)
            elif not os.path.exists(self.input_dir):
                fs.mkdirp(self.input_dir)

            if software_dir:
                os.symlink(
                    os.path.abspath(software_dir), self.software_dir, target_is_directory=True
                )
            elif not os.path.exists(self.software_dir):
                fs.mkdirp(self.software_dir)

            fs.mkdirp(self.shared_dir)
            fs.mkdirp(self.shared_license_dir)

            self.write_config(CONFIG_SECTION)

            self.write_templates()

            self.write_utilities()

            self.write_auxiliary_software_files()

            self.write_metadata()

    def write_config(self, section, force=False):
        """Update YAML config file for this workspace, based on
        changes and write it"""
        config = self.config_sections[section]

        changed = not yaml_equivalent(config["raw_yaml"], config["yaml"])
        written = os.path.exists(config["path"])
        if changed or not written or force:
            config["raw_yaml"] = copy.deepcopy(config["yaml"])
            with fs.write_tmp_and_move(config["path"]) as f:
                _write_yaml(config["yaml"], f, config["schema"])

    def write_templates(self):
        """Write all templates out to workspace"""

        for name, conf in self._templates.items():
            template_path = self.template_path(name)
            with open(template_path, "w+", encoding="utf-8") as f:
                f.write(conf["contents"])

    def write_utilities(self):
        """Write workspace utilities out to the shared directory"""
        import ramble.util.cleaner
        import ramble.util.file_editor

        if ramble.config.get("config:generate_file_editing_scripts", True):
            fs.mkdirp(self.shared_utilities_dir)

            # Copy file editor helper script to workspace shared utilities
            base_script_path = os.path.join(
                self.shared_utilities_dir, ramble.util.file_editor.HELPER_SCRIPT_NAME
            )
            shutil.copyfile(
                ramble.util.file_editor.get_file_editor_source_path(), base_script_path
            )

            # Copy cleaner helper script to workspace shared utilities
            cleaner_script_path = os.path.join(
                self.shared_utilities_dir, ramble.util.cleaner.HELPER_SCRIPT_NAME
            )
            shutil.copyfile(ramble.util.cleaner.get_cleaner_source_path(), cleaner_script_path)

    def write_auxiliary_software_files(self):
        """Write all auxiliary software files out to workspace"""

        for name, contents in self._auxiliary_software_files.items():
            aux_path = os.path.join(self.auxiliary_software_dir, name)
            with open(aux_path, "w+", encoding="utf-8") as f:
                f.write(contents)

    def update_metadata(self, key, value):
        """Set the metadata key value
        Args:
            key (str): Key of metadata to set
            value (Any): Value to set in the metadata object
        """
        self.metadata[namespace.metadata][key] = value

    def clear(self):
        self.config_sections = {}
        self.application_configs = {}
        self._previous_active = None  # previously active environment
        self.specs = []

    @property
    def all_experiments_path(self):
        return os.path.join(self.root, WORKSPACE_ALL_EXPERIMENTS_FILE)

    def build_experiment_set(self, die_on_validate_error=True, check_environments=True):
        """Create an experiment set representing this workspace"""

        if self.software_environments is None:
            self.software_environments = ramble.software_environments.SoftwareEnvironments(self)

        experiment_set = ramble.experiment_set.ExperimentSet(self)

        experiment_set.set_base_var("experiments_file", self.all_experiments_path)

        for workloads, application_context in self.all_applications():
            experiment_set.set_application_context(application_context)

            for experiments, workload_context in self.all_workloads(workloads):
                experiment_set.set_workload_context(workload_context)

                for _, experiment_context in self.all_experiments(experiments):
                    experiment_set.set_experiment_context(
                        experiment_context, die_on_validate_error=die_on_validate_error
                    )

        experiment_set.build_experiment_chains()

        if check_environments and self.software_environments is not None:
            self.software_environments.check_all_environments()

        return experiment_set

    def all_applications(self):
        """Iterator over applications

        Returns application, context
        where context contains the platform level variables that
        should be applied.
        """

        ws_dict = self._get_workspace_dict()
        logger.debug(f" With ws dict: {ws_dict}")

        # Iterate over applications in ramble.yaml first
        app_dict = copy.deepcopy(ramble.config.get(namespace.application))

        for application, contents in app_dict.items():
            app_name, _, maybe_version = application.partition("@")
            if maybe_version:
                contents[namespace.version] = maybe_version

            app_spec = ramble.spec.Spec(app_name)
            app_name = app_spec.fullname

            application_context = ramble.context.create_context_from_dict(app_name, contents)

            yield contents, application_context

        logger.debug("  Iterating over configs in directories...")
        # Iterate over applications defined in application directories
        # files after the ramble.yaml file is complete
        for app_conf in self.application_configs:
            config = self._get_application_dict_config(app_conf)
            if namespace.application not in config:
                logger.msg(f"No applications in config file {app_conf}")
            app_dict = config[namespace.application]
            for application, contents in app_dict.items():
                app_name, _, maybe_version = application.partition("@")
                if maybe_version:
                    contents[namespace.version] = maybe_version

                app_spec = ramble.spec.Spec(app_name)
                app_name = app_spec.fullname

                application_context = ramble.context.create_context_from_dict(app_name, contents)

                yield contents, application_context

    def all_workloads(self, application):
        """Iterator over workloads in an application dict

        Returns workload, context
        where context contains the application level variables that
        should be applied.
        """

        if namespace.workload not in application:
            logger.msg("No workloads in application")
            return

        workloads = application[namespace.workload]

        for workload, contents in workloads.items():
            workload_context = ramble.context.create_context_from_dict(workload, contents)

            yield contents, workload_context

    def all_experiments(self, workload):
        """Iterator over experiments in a workload dict

        Returns experiment, context
        Where context contains the workload level variables that
        should be applied.
        """

        if namespace.experiment not in workload:
            logger.msg("No experiments in workload")
            return

        experiments = workload[namespace.experiment]
        for experiment, contents in experiments.items():
            experiment_context = ramble.context.create_context_from_dict(experiment, contents)

            yield contents, experiment_context

    def print_config(self):
        workspace_dict = self._get_workspace_dict()
        print(f"\n{syaml.dump(workspace_dict)}")

    def manage_environments(
        self,
        env_name,
        env_packages="",
        external_path=None,
        remove=False,
        overwrite=False,
    ):
        """Manipulate software environments

        Create, change, remove, and augment software environment definitions.

        Args:
            env_name (str): Name of environment to manipulate
            env_packages (str): (Optional) Comma delimited list of packages to add into
                                this environment
            external_path (str): (Optional) Path to external environment definition
            remove (bool): Whether the named environment should be removed from the workspace
            overwrite (bool): Whether new definition should overwrite existing definitions
        """

        package_list = []
        if env_packages:
            package_list = env_packages.split(",")

        if package_list and external_path is not None:
            logger.die("Can only manage environments with one of package_list or external_path")

        software_dict = copy.deepcopy(ramble.config.get(namespace.software))

        if namespace.environments in software_dict:
            environments = software_dict[namespace.environments]
        else:
            environments = None

        # Ensure package dict is an syaml_dict, for formatting
        if not environments:
            software_dict[namespace.environments] = syaml.syaml_dict()
            environments = software_dict[namespace.environments]

        if remove:
            if env_name in environments:
                del environments[env_name]
        else:
            if env_name in environments:
                conflicting_type = (
                    namespace.external_env in environments[env_name]
                    and package_list
                    or namespace.packages in environments[env_name]
                    and external_path
                )

                if overwrite:
                    del environments[env_name]
                elif conflicting_type:
                    logger.die(
                        "Cannot convert between internal and "
                        "external environments without --overwrite"
                    )

            if env_name not in environments:
                environments[env_name] = syaml.syaml_dict()

            if package_list:
                environments[env_name][namespace.packages] = package_list.copy()

            elif external_path:
                environments[env_name][namespace.external_env] = external_path

        if not self.dry_run:
            ramble.config.config.update_config(
                namespace.software, software_dict, scope=self.ws_file_config_scope_name()
            )
        else:
            workspace_dict = self._get_workspace_dict()
            workspace_dict[namespace.software] = software_dict

    def manage_packages(
        self,
        pkg_name,
        pkg_spec="",
        compiler_pkg=None,
        compiler_spec=None,
        package_manager_prefix=None,
        remove=False,
        overwrite=False,
    ):
        """Manage workspace package definitions

        Create, remove, update, or augment package definitions.

        Args:
            pkg_name (str): Name of package to manipulate
            pkg_spec (str): Package spec for the package manager
            compiler_pkg (str): Name of the package to use as a compiler for this package
            compiler_spec (str): When this package is used as a compiler for
                                 another, the string to refer to this package.
            package_manager_prefix (str): A package manager specific prefix to
                                          apply to package attribute definitions
            remove (bool): Whether the named package should be removed from the workspace
            overwrite (bool): Whether colliding definitions should be overwritten
        """

        software_dict = copy.deepcopy(ramble.config.get(namespace.software))

        if namespace.packages in software_dict:
            packages = software_dict[namespace.packages]
        else:
            packages = None

        # Ensure package dict is an syaml_dict, for formatting
        if not packages:
            software_dict[namespace.packages] = syaml.syaml_dict()
            packages = software_dict[namespace.packages]

        if remove:
            if pkg_name in packages:
                del packages[pkg_name]
        else:
            if not pkg_spec:
                logger.die("Cannot define a package without a --pkg-spec attribute")

            pkg_def = syaml.syaml_dict()
            prefix = ""
            if package_manager_prefix:
                prefix = f"{package_manager_prefix}_"

            pkg_def[f"{prefix}{namespace.pkg_spec}"] = pkg_spec
            if compiler_pkg:
                pkg_def[f"{prefix}{namespace.compiler}"] = compiler_pkg

            if compiler_spec:
                pkg_def[f"{prefix}{namespace.compiler_spec}"] = compiler_spec

            if pkg_name in packages:
                for attr, val in packages[pkg_name].items():
                    if attr in pkg_def and pkg_def[attr] != val and not overwrite:
                        logger.warn(
                            f"Cannot overwrite existing value of {attr} without --overwrite"
                        )
                        del pkg_def[attr]
            else:
                packages[pkg_name] = syaml.syaml_dict()

            for attr, val in pkg_def.items():
                packages[pkg_name][attr] = val

        if not self.dry_run:
            ramble.config.config.update_config(
                namespace.software, software_dict, scope=self.ws_file_config_scope_name()
            )
        else:
            workspace_dict = self._get_workspace_dict()
            workspace_dict[namespace.software] = software_dict

    def squash_and_print_config(self, included_section=None, excluded_section=None):
        workspace_dict = self._get_workspace_dict()

        # Remove includes if they were defined before.
        if "include" in workspace_dict["ramble"]:
            del workspace_dict["ramble"]["include"]

        for section in ramble.config.section_schemas:
            keep = True

            if included_section:
                keep = False
                for pattern in included_section:
                    if fnmatch.fnmatch(section, pattern):
                        keep = True

            if excluded_section:
                for pattern in excluded_section:
                    if fnmatch.fnmatch(section, pattern):
                        keep = False

            if keep:
                section_dict = ramble.config.get(section)
                if section_dict:
                    workspace_dict["ramble"][section] = section_dict

        print(f"\n{syaml.dump(workspace_dict, Dumper=syaml.OrderedLineDumper)}")

    def add_experiments(
        self,
        application,
        workload_name_variable,
        workload_filters,
        include_default_variables,
        default_variable_value,
        variable_filters,
        variable_definitions,
        variant_definitions,
        experiment_name,
        package_manager=None,
        workflow_manager=None,
        zips=None,
        matrix=None,
        overwrite=False,
    ):
        """Add new experiments to this workspace

        Iterate over the workloads of the input application and define new
        experiments for each workload that matches any filter provided in
        workload_filters.

        Args:
            application (str): Name of application to define experiments for
            workload_name_variable (str): Name of variable to contain workload names,
                                          if the workload names should be collapsed
            workload_filters (list(str)): List of filters to downselect workloads with
            include_default_variables (bool): Whether to include default variables in the
                                              resulting config or not
            default_variable_value (str): Default value to set undefined variables to
            variable_filters (list(str)): List of filters to downselect variables with
            variable_definitions (list(str)): List of variable definitions to use
                                              within generated experiments
            variant_definitions (list(str)): List of variant definitions to use
                                             within generated experiments
            experiment_name (str): The name of the experiments to add
            package_manager (str): Name of package manager to use for the generated experiments
            workflow_manager (str): Name of workflow manager to use for the generated experiments
            zips (list(str) | None): List of strings representing zips to define, in the
                              format zipname=[var1,var2,var3]
            matrix (str): String representing a matrix to define within the
                          experiment in the format of var1,var2,var3.
            overwrite (bool): Whether to overwrite existing definitions that
                              collide with new definitions or not.
        """

        if zips is None:
            zips = []

        def yaml_add_comment_before_key(
            base, key, comment, column=None, clear=False, start_char="#"
        ):
            """
            Insert a comment before the provided key within the base commented
            object.

            Args:
                base: Typically a CommentedMap, but the object comments should
                      be added to
                key: Key in base object to inject the comment before.
                column (int): Column to start the comment at. If not specified,
                              will use previously defined comments to determine
                              indentation.
                clear (bool): Whether to clear previous comments or not
                start_char (str): Character to begin the comment with
            """
            key_comment = base.ca.items.setdefault(key, [None, [], None, None])

            if clear:
                key_comment[1] = []
            comment_list = key_comment[1]

            if comment:
                comment_start = f"{start_char} "
                if comment[-1] == "\n":
                    comment = comment[:-1]  # strip final newline if there
            else:
                comment_start = f"{start_char}"

            if column is None:
                if comment_list:
                    # if there already are other comments get the column from them
                    column = comment_list[-1].start_mark.column
                else:
                    column = 0

            start_mark = yaml.error.Mark(None, None, None, column, None, None)

            comment_list.append(
                yaml.tokens.CommentToken(comment_start + comment + "\n", start_mark, None)
            )

            return base

        def process_definitions(definitions, def_type="variable"):
            def_dict = {}
            for definition in definitions:
                m = _DEF_REGEX.search(definition)

                if m:
                    key = definition[0 : m.start()]
                    value = list_str_to_list(definition[m.end() :])
                    if isinstance(value, str):
                        value = strip_quotes(value)
                    def_dict[key] = value
                else:
                    logger.die(
                        f"Invalid {def_type} definition provided: {definition}. "
                        + "Accepted form is 'key=value'"
                    )
            return def_dict

        edited = False

        workspace_vars = ramble.config.get(namespace.variables)
        apps_dict = copy.deepcopy(ramble.config.get(namespace.application))

        app_inst = ramble.repository.get(application)

        exp_context = ramble.context.Context()
        exp_context.context_name = experiment_name

        app_inst.variables = {}
        app_inst.expander = ramble.expander.Expander({}, None)

        exp_context.variables = process_definitions(variable_definitions, def_type="variable")
        exp_context.variants = process_definitions(variant_definitions, def_type="variant")

        # TODO: Deprecate / remove in favor of explicit variant definitions
        if package_manager:
            exp_context.variants["package_manager"] = package_manager

        if workflow_manager:
            exp_context.variants["workflow_manager"] = workflow_manager

        if application not in apps_dict:
            apps_dict[application] = syaml.syaml_dict()
            apps_dict[application][namespace.workload] = syaml.syaml_dict()

        workloads_dict = apps_dict[application][namespace.workload]

        exp_context.zips = process_definitions(zips, def_type="zip")

        if matrix:
            exp_context.matrices.append(list(matrix.split(",")))

        # Unpack all workload names from `when` sets
        all_workload_names = set()
        for workloads in app_inst.workloads.values():
            for workload in workloads:
                all_workload_names.add(workload)

        workload_names = []
        for workload in all_workload_names:
            add_workload = False
            for wl_filter in workload_filters:
                if fnmatch.fnmatch(workload, wl_filter):
                    add_workload = True
                    break

            # Don't add this experiment if it already exists in the workspace
            if add_workload:
                if application in apps_dict:
                    subdict = apps_dict[application]
                    if namespace.workload in subdict:
                        subdict = subdict[namespace.workload]
                        if workload in subdict:
                            subdict = subdict[workload]
                            if namespace.experiment in subdict:
                                subdict = subdict[namespace.experiment]
                                if experiment_name in subdict:
                                    exp_name = f"{application}.{workload}.{experiment_name}"
                                    if not overwrite:
                                        logger.warn(
                                            f"Experiment {exp_name} is defined already. "
                                            + "To overwrite, use '--overwrite'"
                                        )
                                    add_workload = overwrite

            if add_workload:
                workload_names.append(workload)

        if not workload_names:
            logger.die(f"No workloads match filter '{wl_filter}' in application {application}")

        if workload_name_variable:
            exp_context.variables[workload_name_variable] = workload_names.copy()
            workload_names = [ramble.expander.Expander.expansion_str(workload_name_variable)]

        self.software_environments = ramble.software_environments.SoftwareEnvironments(self)
        is_dry_run = self.dry_run
        self.dry_run = True
        for workload_name in workload_names:
            edited = True
            missing_vars: Set[str] = set()
            exp_set = ramble.experiment_set.ExperimentSet(self)
            exp_list = exp_set.render_experiment_set(
                app_inst.name,
                workload_name,
                exp_context,
                warn_validation=False,
                die_on_validate_error=False,
            )

            for exp_inst in exp_list:
                missing_exp_vars = {
                    var
                    for var in exp_inst.keywords.all_required_keys()
                    if var not in exp_inst.variables
                }
                missing_exp_vars = missing_exp_vars | exp_inst.missing_mpi_variables
                missing_vars = missing_vars | missing_exp_vars

            if workload_name not in workloads_dict:
                workloads_dict[workload_name] = {namespace.experiment: {}}

            exps_dict = workloads_dict[workload_name][namespace.experiment]
            exps_dict[experiment_name] = syaml.syaml_dict()
            exp_dict = exps_dict[experiment_name]

            if exp_context.variants:
                exp_dict[namespace.variants] = syaml.syaml_dict()
                variants_dict = exp_dict[namespace.variants]
                for name, val in exp_context.variants.items():
                    variants_dict[name] = val

            if namespace.variables not in exp_dict:
                exp_dict[namespace.variables] = yaml.comments.CommentedMap()

            vars_dict = exp_dict[namespace.variables]

            # Ensure required variables are defined
            for key in sorted(missing_vars):
                if key not in workspace_vars and key not in exp_context.variables:
                    vars_dict[key] = default_variable_value

            # Only extract variable defaults if requested.
            # This is mutually exclusive with workload_name_variable
            if include_default_variables:
                workload = exp_inst.get_workloads()
                if workload.variables:
                    first_var = True
                    for var in workload.variables.values():
                        keep_var = False
                        for var_filter in variable_filters:
                            if fnmatch.fnmatch(var.name, var_filter):
                                keep_var = True
                                break

                        if keep_var:
                            vars_dict[var.name] = var.default

                            # Add blank line before all variables except
                            # the first
                            if first_var:
                                first_var = False
                            else:
                                yaml_add_comment_before_key(
                                    vars_dict, var.name, "", column=17, start_char=""
                                )
                            if var.description:
                                yaml_add_comment_before_key(
                                    vars_dict, var.name, var.description, column=17
                                )
                            if len(var.values) > 1 or var.values[0] is not None:
                                yaml_add_comment_before_key(
                                    vars_dict,
                                    var.name,
                                    f"Suggested values: {var.values}",
                                    column=17,
                                )

                if workload.environment_variables:
                    if namespace.env_var not in exps_dict[experiment_name]:
                        exp_dict[namespace.env_var] = syaml.syaml_dict()
                        exp_dict[namespace.env_var]["set"] = syaml.syaml_dict()

                    env_vars_dict = exp_dict[namespace.env_var]["set"]

                    for env_var in workload.environment_variables.values():
                        env_vars_dict[env_var.name] = env_var.value

            # Add any variables that are defined to the variables dict
            if exp_context.variables:
                vars_dict.update(exp_context.variables)

            if exp_context.zips:
                if namespace.zips not in exp_dict:
                    exp_dict[namespace.zips] = exp_context.zips.copy()

            if exp_context.matrices:
                if namespace.matrix not in exp_dict:
                    exp_dict[namespace.matrix] = exp_context.matrices.copy()[0]

        self.dry_run = is_dry_run
        if edited and not self.dry_run:
            ramble.config.config.update_config(
                namespace.application, apps_dict, scope=self.ws_file_config_scope_name()
            )
        elif edited:
            workspace_dict = self._get_workspace_dict()
            workspace_dict[namespace.ramble][namespace.application] = apps_dict

    def concretize(self, force=False, quiet=False):
        """Concretize software definitions for defined experiments

        Extract suggested software for experiments defined in a workspace, and
        ensure the software environments are defined properly.

        Args:
            force (bool): Whether to overwrite conflicting definitions of named packages or not
            quiet (bool): Whether to silently ignore conflicts or not


        """
        full_software_dict = copy.deepcopy(ramble.config.get(namespace.software))

        if (
            namespace.packages not in full_software_dict
            or not full_software_dict[namespace.packages]
        ):
            full_software_dict[namespace.packages] = syaml.syaml_dict()
        if (
            namespace.environments not in full_software_dict
            or not full_software_dict[namespace.environments]
        ):
            full_software_dict[namespace.environments] = syaml.syaml_dict()

        packages_dict = full_software_dict[namespace.packages]
        environments_dict = full_software_dict[namespace.environments]
        newly_created_packages = set()

        self.software_environments = ramble.software_environments.SoftwareEnvironments(self)

        experiment_set = self.build_experiment_set(
            die_on_validate_error=False, check_environments=False
        )

        force_prefix = False
        pkgman_prefixes = set()
        for _, app_inst, _ in experiment_set.all_experiments():
            app_inst.build_modifier_instances()
            app_inst.define_variables_for_template_path()
            if app_inst.package_manager is not None:
                pkgman_prefixes.add(app_inst.package_manager.spec_prefix)
                force_prefix = force_prefix or not app_inst.package_manager.allow_unprefixed_specs

        force_prefix = force_prefix or len(pkgman_prefixes) > 1

        for _, app_inst, _ in experiment_set.all_experiments():
            app_inst.build_modifier_instances()
            app_inst.define_variables_for_template_path()
            env_name_str = app_inst.expander.expansion_str(ramble.keywords.keywords.env_name)
            env_name = app_inst.expander.expand_var(env_name_str)

            if app_inst.package_manager is None:
                continue

            compiler_packages = app_inst.package_manager.get_experiment_compilers(
                app_inst=app_inst, prefixed=force_prefix
            )
            for comp, definitions in compiler_packages.items():
                for info in definitions:
                    if (
                        not quiet
                        and comp in packages_dict
                        and info.conflict_dict(packages_dict[comp])
                    ):
                        logger.debug(f"  Spec 1: {str(info)}")
                        logger.debug(f"  Spec 2: {str(packages_dict[comp])}")
                        raise RambleConflictingDefinitionError(
                            f"Compiler {comp} would be defined " "in multiple conflicting ways"
                        )

                    if comp not in packages_dict or (force and comp not in newly_created_packages):
                        newly_created_packages.add(comp)
                        packages_dict[comp] = syaml.syaml_dict()

                    compiler_packages[comp] = False
                    packages_dict[comp].update(info.to_dict(apply_prefix=force_prefix))
                    for conf in info.config_opts():
                        ramble.config.add(conf, scope=self.ws_file_config_scope_name())

            logger.debug(f"Trying to define packages for {env_name}")
            app_packages = []
            if env_name in environments_dict:
                if namespace.packages in environments_dict[env_name]:
                    app_packages = environments_dict[env_name][namespace.packages].copy()

            defined_pm_packages = set()
            for pkg in app_packages:
                if pkg in packages_dict and isinstance(packages_dict[pkg], dict):
                    pkg_spec = None
                    for key, val in packages_dict[pkg].items():
                        if key == "pkg_spec" or key.endswith("_pkg_spec"):
                            pkg_spec = val
                            break
                    if pkg_spec:
                        pm_package_name = app_inst.package_manager.package_name_from_spec(pkg_spec)
                        if pm_package_name:
                            defined_pm_packages.add(pm_package_name)

            software_packages = app_inst.package_manager.get_experiment_specs(
                app_inst=app_inst, prefixed=force_prefix
            )
            specs_to_process = [
                (spec_name, info)
                for spec_name, definitions in software_packages.items()
                for info in definitions
            ]

            # Sort specs: inject_if_missing=False first
            specs_to_process.sort(key=lambda x: x[1].inject_if_missing)

            for spec_name, info in specs_to_process:
                logger.debug(f"    Found spec: {spec_name}")
                pm_package_name = None
                if info.pkg_spec:
                    pm_package_name = app_inst.package_manager.package_name_from_spec(
                        info.pkg_spec
                    )

                if info.inject_if_missing:
                    if pm_package_name and pm_package_name in defined_pm_packages:
                        logger.debug(
                            f"    Skipping inject_if_missing spec {spec_name} "
                            f"because package {pm_package_name} is already defined."
                        )
                        continue

                if (
                    not quiet
                    and spec_name in packages_dict
                    and info.conflict_dict(packages_dict[spec_name])
                ):
                    logger.debug(f"  Spec 1: {str(info)}")
                    logger.debug(f"  Spec 2: {str(packages_dict[spec_name])}")
                    raise RambleConflictingDefinitionError(
                        f"Package {spec_name} would be defined in multiple " "conflicting ways"
                    )

                if spec_name not in packages_dict or (
                    force and spec_name not in newly_created_packages
                ):
                    packages_dict[spec_name] = syaml.syaml_dict()

                # Check for usage of compilers
                expanded_compiler = app_inst.expander.expand_var(info.compiler)
                if expanded_compiler in compiler_packages:
                    compiler_packages[expanded_compiler] = True

                packages_dict[spec_name].update(info.to_dict(apply_prefix=force_prefix))

                if spec_name not in app_packages:
                    app_packages.append(spec_name)

                if pm_package_name:
                    defined_pm_packages.add(pm_package_name)

            if app_packages:
                if env_name not in environments_dict:
                    environments_dict[env_name] = syaml.syaml_dict()

                environments_dict[env_name][namespace.packages] = app_packages.copy()

            # Ensure all compilers in this experiment are used.
            comp_list = []
            for name, used in compiler_packages.items():
                if not used:
                    comp_list.append(name)
            if comp_list:
                logger.warn(
                    "Unused compiler(s) found in experiment: "
                    + app_inst.expander.experiment_namespace
                )
                logger.warn(f"   {comp_list}")

        ramble.config.config.update_config(
            namespace.software, full_software_dict, scope=self.ws_file_config_scope_name()
        )

        self.software_environments = None

        return

    def default_results(self):
        res = {}

        if self.workspace_hash:
            res["workspace_hash"] = self.workspace_hash
        else:
            try:
                with open(os.path.join(self.root, self.hash_file_name), encoding="utf-8") as f:
                    res["workspace_hash"] = f.readline().rstrip()
            except OSError:
                res["workspace_hash"] = "Unknown.."

        res["workspace_name"] = self.name
        res["metadata"] = self.metadata
        res["ramble_version"] = ramble.util.version.get_version()
        res[namespace.experiment] = []

        return res

    def append_result(self, result):
        if not self.results:
            self.results = self.default_results()

        self.results[namespace.experiment].append(result)

    def insert_result(self, result, insert_before_exp):
        """Insert a result before a specified experiment"""

        def search_exp_index(results_list, exp_to_search):
            for i, exp in enumerate(results_list):
                if exp["name"] == exp_to_search:
                    return i
            return None

        if not self.results:
            self.results = self.default_results()

        insert_index = search_exp_index(self.results[namespace.experiment], insert_before_exp)

        tty.debug(f"Attempting to insert result before experiment {insert_before_exp}")
        if insert_index is not None:
            self.results[namespace.experiment].insert(insert_index, result)
        else:
            tty.debug(f"Could not find {insert_before_exp}, appending result to end instead.")
            self.results[namespace.experiment].append(result)

    def symlink_result(self, out_file, latest_file):
        """
        Create symlink of result file so that results.latest.txt always points
        to the most recent analysis. This clobbers the existing link
        """

        from ramble.util.file_util import create_symlink

        create_symlink(out_file, latest_file)

    def write_software_info(self, f, exp):
        f.write("  Software definitions:\n")
        for package_manager, packages in exp["SOFTWARE"].items():
            f.write(f"    {package_manager} packages:\n")
            if not packages:
                f.write("      None\n")
            else:
                # Dedupe entries that have the same version texts.
                # This can happen for instance if a package is built against different compilers.
                pkg_info_set = set()
                for pkg_info in packages:
                    text = pkg_info.to_version_text()
                    if text not in pkg_info_set:
                        f.write(f"      {text}\n")
                        pkg_info_set.add(text)

    def dump_tables(self, experiment_set, filters):
        tables_config = ramble.config.get("tables", [])

        if tables_config:
            for table_conf in tables_config:
                self.results_tables.add_table_template(table_conf)

        if self.results_tables.num_tables > 0:
            self.results_tables.build_tables(experiment_set, filters)

            fs.mkdirp(self.tables_dir)
            self.results_tables.output_tables(self.tables_dir, self.date_string())

    def _create_result_symlinks(self, out_file, latest_base, file_extension, symlinks_updated):
        latest_file = os.path.join(self.results_dir, latest_base + file_extension)
        symlinks_updated.append(latest_file)
        self.symlink_result(out_file, latest_file)

        # Allow one simlink to the latest result in the top level for backwards compat
        latest_file_parent = os.path.join(self.root, latest_base + file_extension)
        self.symlink_result(out_file, latest_file_parent)

    def dump_results(
        self, output_formats=None, print_results=False, summary_only=False, fom_origin_types=None
    ):
        """
        Write out result file in desired format

        This attempts to avoid the loss of previous results data by appending
        the datetime to the filename, but is willing to clobber the file
        results.latest.<extension>

        """

        if output_formats is None:
            output_formats = ["text"]

        if not self.results:
            self.results = {}

        results = _filter_results(
            self.results, summary_only=summary_only, fom_origin_types=fom_origin_types
        )
        fs.mkdirp(self.results_dir)

        results_written = []
        symlinks_updated: List[str] = []

        dt = self.date_string()
        inner_delim = "."
        filename_base = "results" + inner_delim + dt
        latest_base = "results" + inner_delim + "latest"

        software_key = ramble.experiment_result._OUTPUT_MAPPING[namespace.software]

        if "text" in output_formats:

            file_extension = ".txt"
            out_file = os.path.join(self.results_dir, filename_base + file_extension)

            results_written.append(out_file)

            with open(out_file, "w+", encoding="utf-8") as f:
                f.write(f"From Workspace: {self.name} (hash: {results['workspace_hash']})\n")
                if namespace.experiment in results:
                    for exp in results[namespace.experiment]:
                        f.write(f"Experiment {exp['name']} figures of merit:\n")
                        f.write(f"  Status = {exp['RAMBLE_STATUS']}\n")
                        if "TAGS" in exp:
                            f.write(f'  Tags = {exp["TAGS"]}\n')

                        if exp["N_REPEATS"] > 0:  # this is a base exp with summary of repeats
                            for context in exp["CONTEXTS"]:
                                f.write(f'  {context["display_name"]} figures of merit:\n')

                                fom_summary: Dict[str, List[Any]] = {}
                                for fom in context["foms"]:
                                    name = fom["name"]
                                    if name not in fom_summary:
                                        fom_summary[name] = []
                                    stat_name = fom["origin_type"]
                                    if not stat_name.startswith("summary::"):
                                        display_name = "value"
                                    else:
                                        display_name = stat_name
                                    value = fom["value"]
                                    units = fom["units"]
                                    output = f"{display_name} = {value} {units}\n"
                                    fom_summary[name].append(output)

                                for fom_name, fom_val_list in fom_summary.items():
                                    f.write(f"    {fom_name}:\n")
                                    for fom_val in fom_val_list:
                                        f.write(f"      {fom_val.strip()}\n")

                            if exp.get(software_key):
                                self.write_software_info(f, exp)

                        else:
                            for context in exp["CONTEXTS"]:
                                f.write(f'  {context["display_name"]} figures of merit:\n')
                                for fom in context["foms"]:
                                    name = fom["name"]
                                    if fom["origin_type"] == "modifier":
                                        delim = "::"
                                        mod = fom["origin"]
                                        name = f"{fom['origin_type']}{delim}{mod}{delim}{name}"

                                    output = f"{name} = {fom['value']} {fom['units']}"
                                    f.write(f"    {output.strip()}\n")

                            if exp.get(software_key):
                                self.write_software_info(f, exp)

                        if exp["VARIANTS"]:
                            f.write("  Experiment variants:\n")
                            for variant in exp["VARIANTS"]:
                                f.write(f"  - {variant}\n")

                        if exp["SUCCESS_CRITERIA"]:
                            f.write("  Success criteria summary:\n")
                            for name, result in exp["SUCCESS_CRITERIA"].items():
                                f.write(f"    {name} = {result}\n")
                else:
                    logger.msg("No results to write")

            self._create_result_symlinks(out_file, latest_base, file_extension, symlinks_updated)

        # Convert SoftwareInfo classes to dicts
        for exp in results[namespace.experiment]:
            for key, pkg_list in exp[software_key].items():
                exp[software_key][key] = [pkg.to_dict() for pkg in pkg_list]

        if "json" in output_formats:
            file_extension = ".json"
            out_file = os.path.join(self.results_dir, filename_base + file_extension)
            results_written.append(out_file)
            with open(out_file, "w+", encoding="utf-8") as f:
                json_util.dump(results, f)
            self._create_result_symlinks(out_file, latest_base, file_extension, symlinks_updated)

        if "yaml" in output_formats:
            file_extension = ".yaml"
            out_file = os.path.join(self.results_dir, filename_base + file_extension)
            results_written.append(out_file)

            from ruamel.yaml import RoundTripDumper

            class RambleSafeDumper(RoundTripDumper):
                def ignore_aliases(self, _data):
                    """Make the dumper NEVER print YAML aliases."""
                    return True

            def call_value(dumper, data):
                return dumper.represent_data(data.value)

            RambleSafeDumper.add_representer(ramble.experiment_result.ExperimentStatus, call_value)

            with open(out_file, "w+", encoding="utf-8") as f:
                syaml.dump(results, stream=f, Dumper=RambleSafeDumper)

            self._create_result_symlinks(out_file, latest_base, file_extension, symlinks_updated)

        if not results_written:
            logger.die("Results were not written.")

        logger.all_msg("Results are written to:")
        for out_file in results_written:
            logger.all_msg(f"  {out_file}")
        logger.all_msg("Symlinks updated:")
        for symlink_path in symlinks_updated:
            logger.all_msg(f"  {symlink_path}")

        if print_results:
            with open(results_written[0], encoding="utf-8") as f:
                # Use tty directly to avoid cluttering the analyze log
                tty.msg(f"Results from the analysis pipeline:\n{f.read()}")

        return filename_base

    def create_mirror(self, mirror_root):
        parsed_url = url_util.parse(mirror_root)
        self.mirror_path = url_util.local_file_path(parsed_url)
        self.mirror_existed = web_util.url_exists(self.mirror_path)
        self.input_mirror_path = os.path.join(self.mirror_path, WORKSPACE_INPUT_PATH)
        self.software_mirror_path = os.path.join(self.mirror_path, WORKSPACE_SOFTWARE_PATH)
        mirror_dirs = [self.mirror_path, self.input_mirror_path, self.software_mirror_path]
        for subdir in mirror_dirs:
            if not os.path.isdir(subdir):
                try:
                    fs.mkdirp(subdir)
                except OSError as e:
                    raise ramble.mirror.MirrorError(f"Cannot create directory '{subdir}':") from e

        self.software_mirror_stats = MirrorStats()
        self.input_mirror_stats = MirrorStats()
        self.input_mirror_cache = ramble.caches.MirrorCache(self.input_mirror_path)
        self.software_mirror_cache = ramble.caches.MirrorCache(self.software_mirror_path)

    def simplify_variables(self):
        """Simplify variable sections in workspace configuration file"""

        def _remove_scoped_variables(scope_name: str, used_variables: Set):
            """Remove unused variables from a specific workspace scope.

            Args:
                scope_name (str): Name of scope to remove definitions from.
                used_variables (set): Set of used definitions that should be kept.
            """

            changed = False

            # Delete unused variables from requested scope.
            to_remove = set()
            scope_section = self._get_scope_section(scope_name)

            if scope_section is None:
                return changed

            if namespace.variables in scope_section:
                for var in scope_section[namespace.variables]:
                    if var not in used_variables:
                        to_remove.add(var)
                for var in to_remove:
                    del scope_section[namespace.variables][var]
                    changed = True

                if not scope_section[namespace.variables]:
                    del scope_section[namespace.variables]

            return changed

        # Build software environments to determine which variables are used
        self.software_environments = ramble.software_environments.SoftwareEnvironments(self)
        experiment_set = self.build_experiment_set()

        workspace_used_variables: Set[str] = set()

        prev_app = None
        prev_wl = None
        prev_exp = None

        app_used_vars: Set[str] = set()
        wl_used_vars: Set[str] = set()
        exp_used_vars: Set[str] = set()
        changed = False

        for _, app_inst, _ in experiment_set.all_experiments():
            app_inst.build_used_variables()

            if app_inst.repeats.is_repeat_base or app_inst.repeats.repeat_index is None:
                # Either there are no repeats, or this is the base
                if prev_exp is not None:
                    changed = changed or _remove_scoped_variables(
                        f"{prev_app}:{prev_wl}:{prev_exp}", exp_used_vars
                    )

                prev_exp = app_inst.variables[app_inst.keywords.experiment_template_name]
                exp_used_vars = set()

            if prev_wl != app_inst.variables[app_inst.keywords.workload_template_name]:
                if prev_wl is not None:
                    changed = changed or _remove_scoped_variables(
                        f"{prev_app}:{prev_wl}", wl_used_vars
                    )

                prev_wl = app_inst.variables[app_inst.keywords.workload_template_name]
                wl_used_vars = set()

            if prev_app != app_inst.variables[app_inst.keywords.application_name]:
                if prev_app is not None:
                    changed = changed or _remove_scoped_variables(prev_app, app_used_vars)

                prev_app = app_inst.variables[app_inst.keywords.application_name]
                app_used_vars = set()

            workspace_used_variables = workspace_used_variables.union(
                app_inst.expander._used_variables
            )
            app_used_vars = app_used_vars.union(app_inst.expander._used_variables)
            wl_used_vars = wl_used_vars.union(app_inst.expander._used_variables)
            exp_used_vars = exp_used_vars.union(app_inst.expander._used_variables)

        if prev_exp is not None:
            changed = changed or _remove_scoped_variables(
                f"{prev_app}:{prev_wl}:{prev_exp}", exp_used_vars
            )

        if prev_wl is not None:
            changed = changed or _remove_scoped_variables(f"{prev_app}:{prev_wl}", wl_used_vars)

        if prev_app is not None:
            changed = changed or _remove_scoped_variables(prev_app, app_used_vars)

        changed = changed or _remove_scoped_variables("workspace", workspace_used_variables)

        if changed:
            self.write_config(CONFIG_SECTION)
        else:
            logger.all_msg("No variables were changed.")

    def simplify_software(self):
        # First drop unused experiment templates from app dict so environments aren't rendered
        app_dict = copy.deepcopy(
            ramble.config.get(namespace.application, scope=self.ws_file_config_scope_name())
        )

        # Build experiment sets to determine which templates never get used
        self.software_environments = ramble.software_environments.SoftwareEnvironments(self)
        experiment_set = self.build_experiment_set()
        logger.debug("Software environments:")
        logger.debug(str(self.software_environments))

        for _, app_inst in experiment_set.template_experiments():
            if app_inst.is_template and not app_inst.has_generated_experiments:
                app = app_inst.expander.application_name
                wl = app_inst.expander.workload_name
                exp = app_inst.expander.experiment_name

                try:
                    app_dict[app][namespace.workload][wl][namespace.experiment].pop(exp)
                    if not app_dict[app][namespace.workload][wl][namespace.experiment]:
                        app_dict[app][namespace.workload][wl].pop(namespace.experiment)
                    if not app_dict[app][namespace.workload][wl]:
                        app_dict[app][namespace.workload].pop(wl)
                    if not app_dict[app][namespace.workload]:
                        app_dict[app].pop(namespace.workload)
                    if not app_dict[app]:
                        app_dict.pop(app)
                except KeyError:
                    continue

        ramble.config.config.update_config(
            namespace.application, app_dict, scope=self.ws_file_config_scope_name()
        )

        # Regenerate environments without the unused templates to see which env never get rendered
        self.software_environments = ramble.software_environments.SoftwareEnvironments(self)
        software_environments = self.software_environments
        experiment_set = self.build_experiment_set()

        changed = False

        software_dict = None
        package_dict = None
        environments_dict = None

        software_dict = copy.deepcopy(
            ramble.config.get(namespace.software, scope=self.ws_file_config_scope_name())
        )

        if namespace.packages in software_dict:
            package_dict = software_dict[namespace.packages]
        if namespace.environments in software_dict:
            environments_dict = software_dict[namespace.environments]

        tty.debug("Removing configurations that do not spark joy.")
        if package_dict:
            for pkg in software_environments.unused_packages():
                if pkg.name in package_dict:
                    tty.debug(f"Removing {pkg.name} from software packages")
                    package_dict.pop(pkg.name)
                    changed = True
        if environments_dict:
            for env in software_environments.unused_environments():
                if env.name in environments_dict:
                    tty.debug(f"Removing {env.name} from software environments")
                    environments_dict.pop(env.name)
                    changed = True

        if changed:
            ramble.config.config.update_config(
                namespace.software, software_dict, scope=self.ws_file_config_scope_name()
            )
        else:
            logger.all_msg("No changes were made to software configuration sections.")

    @property
    def latest_archive_path(self):
        return os.path.join(self.archive_dir, self.latest_archive)

    @property
    def latest_archive(self):
        if hasattr(self, "_latest_archive") and self._latest_archive:
            return self._latest_archive

        if os.path.exists(self.archive_dir):
            archive_dirs = []

            for subdir in os.listdir(self.archive_dir):
                archive_path = os.path.join(self.archive_dir, subdir)
                if os.path.isdir(archive_path) and not os.path.islink(archive_path):
                    archive_dirs.append(archive_path)

            if archive_dirs:
                latest_path = max(archive_dirs, key=os.path.getmtime)
                self._latest_archive = os.path.basename(latest_path)
                return self._latest_archive

        return None

    def date_string(self):
        now = datetime.datetime.now()
        return now.strftime("%Y-%m-%d_%H.%M.%S")

    def read_file_content(self, file_path):
        """Read and cache the file content

        This should only be used on files that are not modified during the lifetime of the
        workspace command execution.
        """
        if file_path in self._inmem_file_cache:
            return self._inmem_file_cache[file_path]
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        self._inmem_file_cache[file_path] = content
        return content

    @property
    def internal(self):
        """Whether this workspace is managed by Ramble."""
        wspaths = get_workspace_path()
        return any(self.path.startswith(wspath) for wspath in wspaths)

    @property
    def name(self):
        """Human-readable representation of the workspace.

        The name of the workspace is the basename of its path
        """
        return os.path.basename(self.path)

    @property
    def path(self):
        """Location of the workspace"""
        return self.root

    @property
    def active(self):
        """True if this workspace is currently active."""
        return _active_workspace and self.path == _active_workspace.path

    @property
    def internal_subdir(self):
        """Subdirectory for housing ramble internals"""
        return os.path.join(self.root, ".ramble-workspace")

    @property
    def _transaction_lock_path(self):
        """The location of the lock file used to synchronize multiple
        processes updating the same workspace.
        """
        return os.path.join(self.internal_subdir, "transaction_lock")

    @property
    def experiment_dir(self):
        """Path to the experiment directory"""
        return os.path.join(self.root, WORKSPACE_EXPERIMENT_PATH)

    @property
    def input_dir(self):
        """Path to the input directory"""
        return os.path.join(self.root, WORKSPACE_INPUT_PATH)

    @property
    def software_dir(self):
        """Path to the software directory"""
        return os.path.join(self.root, WORKSPACE_SOFTWARE_PATH)

    @property
    def tables_dir(self):
        """Directory where workspace tables are stored"""
        return os.path.join(self.root, WORKSPACE_TABLES_PATH)

    @property
    def results_dir(self):
        """Directory where workspace results are stored"""
        return os.path.join(self.root, WORKSPACE_RESULTS_PATH)

    @property
    def log_dir(self):
        """Path to the logs directory"""
        return os.path.join(self.root, WORKSPACE_LOG_PATH)

    @property
    def config_dir(self):
        """Path to the configuration file directory"""
        return os.path.join(self.root, WORKSPACE_CONFIG_PATH)

    @property
    def auxiliary_software_dir(self):
        """Path to the auxiliary software files directory"""
        return os.path.join(self.config_dir, AUXILIARY_SOFTWARE_DIR_NAME)

    @property
    def shared_utilities_dir(self):
        """Path to the Ramble shared utilities directory"""
        return os.path.join(self.shared_dir, "utilities")

    @property
    def config_file_path(self):
        """Path to the configuration file directory"""
        return os.path.join(self.config_dir, CONFIG_FILE_NAME)

    @property
    def archive_dir(self):
        """Path to the archive directory"""
        return os.path.join(self.root, WORKSPACE_ARCHIVE_PATH)

    @property
    def shared_dir(self):
        """Path to the shared directory"""
        return os.path.join(self.root, WORKSPACE_SHARED_PATH)

    @property
    def deployments_dir(self):
        """Path to the deployments directory"""
        return os.path.join(self.root, WORKSPACE_DEPLOYMENTS_PATH)

    @property
    def named_deployment(self):
        """Path to the specific deployment directory"""
        return os.path.join(self.deployments_dir, self.deployment_name)

    @property
    def deployment_repos_dir(self):
        """Path to the specific deployment directory that contains all the repos"""
        return os.path.join(self.named_deployment, "object_repos")

    @property
    def shared_license_dir(self):
        """Path to the shared license directory"""
        return os.path.join(self.shared_dir, WORKSPACE_SHARED_LICENSE_PATH)

    def template_path(self, name):
        if name in self._templates:
            return os.path.join(self.config_dir, name + TEMPLATE_EXTENSION)
        return None

    def all_templates(self):
        """Iterator over each template in the workspace"""
        yield from sorted(self._templates.items())

    def all_auxiliary_software_files(self):
        """Iterator over each auxiliary software file"""
        yield from self._auxiliary_software_files.items()

    @classmethod
    def get_workspace_paths(cls, root):
        """Construct dictionary of path replacements for workspace"""
        workspace_path_replacements = {
            "workspace_root": root,
            namespace.workspace: root,
            "workspace_configs": os.path.join(root, WORKSPACE_CONFIG_PATH),
            "workspace_software": os.path.join(root, WORKSPACE_SOFTWARE_PATH),
            "workspace_tables": os.path.join(root, WORKSPACE_TABLES_PATH),
            "workspace_results": os.path.join(root, WORKSPACE_RESULTS_PATH),
            "workspace_logs": os.path.join(root, WORKSPACE_LOG_PATH),
            "workspace_inputs": os.path.join(root, WORKSPACE_INPUT_PATH),
            "workspace_experiments": os.path.join(root, WORKSPACE_EXPERIMENT_PATH),
            "workspace_shared": os.path.join(root, WORKSPACE_SHARED_PATH),
            "workspace_archives": os.path.join(root, WORKSPACE_ARCHIVE_PATH),
            "workspace_deployments": os.path.join(root, WORKSPACE_DEPLOYMENTS_PATH),
        }

        return workspace_path_replacements

    def workspace_paths(self):
        """Dictionary of path replacements for workspace"""
        if not hasattr(self, "_workspace_path_replacements"):
            self._workspace_path_replacements = self.get_workspace_paths(self.root)

        return self._workspace_path_replacements

    def _get_scope_section(self, scope):
        base_section = None
        if scope == "workspace":
            base_section = self.config_sections["workspace"]["yaml"][namespace.ramble]

        else:
            scope_parts = scope.split(":")

            if (
                namespace.application
                not in self.config_sections["workspace"]["yaml"][namespace.ramble]
            ):
                return None

            base_section = self.config_sections["workspace"]["yaml"][namespace.ramble][
                namespace.application
            ]

            if len(scope_parts) >= 1:  # Extract application section
                if scope_parts[0] not in base_section:
                    logger.die(f"No application matches requested scope {scope_parts[0]}")
                base_section = base_section[scope_parts[0]]

            if len(scope_parts) >= 2:  # Extract workload section
                if scope_parts[1] not in base_section[namespace.workload]:
                    logger.die(
                        f"No workload matches requested scope {scope_parts[1]} "
                        f"in application {scope_parts[0]}"
                    )
                base_section = base_section[namespace.workload][scope_parts[1]]

            if len(scope_parts) >= 3:  # Extract experiment section
                joined_scope_part = ":".join(scope_parts[2:])
                if joined_scope_part not in base_section[namespace.experiment]:
                    logger.die(
                        f"No experiment matches requested scope {joined_scope_part} "
                        f"in application{scope_parts[0]} and workload {scope_parts[1]}"
                    )

                base_section = base_section[namespace.experiment][joined_scope_part]
        if base_section is None:
            logger.die(f"No scope matches requested scope of {scope}")
        return base_section

    def index_modifiers(self):
        """Construct a list of all modifiers in this workspace, and their associated scope.

        Returns:
            list[tuple]: List of tuples, of the form (scope, modifier_definition)
        """
        base_section = self._get_scope_section("workspace")
        ws_mods = base_section.get(namespace.modifiers, [])

        # Add workspace modifiers
        mod_list = [("workspace", mod) for mod in ws_mods]

        # Define scoped modifiers
        for workloads, application_context in self.all_applications():
            app_context = f"{application_context.context_name}"
            mod_list.extend((f"{app_context}", mod) for mod in application_context.modifiers)

            for experiments, workload_context in self.all_workloads(workloads):
                wl_context = f"{app_context}:{workload_context.context_name}"
                mod_list.extend((f"{wl_context}", mod) for mod in workload_context.modifiers)

                for _, experiment_context in self.all_experiments(experiments):
                    exp_context = f"{wl_context}:{experiment_context.context_name}"
                    mod_list.extend(
                        (f"{exp_context}", mod) for mod in experiment_context.modifiers
                    )

        return mod_list

    def print_modifiers(self):
        """Print an indexed list of all modifiers in this workspace"""
        mod_list = self.index_modifiers()

        logger.all_msg(f"Workspace contains {len(mod_list)} modifiers.")
        logger.all_msg("Additional modifiers may come from scopes outside of wokrspace")
        logger.all_msg("To see a complete list of these, use:")
        logger.all_msg("   ramble config get modifiers\n\n")

        prev_scope = None
        for idx, conf in enumerate(mod_list):
            scope = conf[0]
            entry = conf[1]
            if scope != prev_scope:
                if prev_scope is not None:
                    logger.all_msg("")
                logger.all_msg(f"Modifier scope: {scope}")
                prev_scope = scope
            name = entry["name"]
            mode_str = ""
            if "mode" in entry and entry["mode"] is not None:
                mode_str = f" -- Mode: {entry['mode']}"

            out_str = f"Name: {name}{mode_str}"

            logger.all_msg(f"{idx}: {out_str}")

    def remove_modifier(
        self,
        remove_index: Optional[int] = None,
        scope_pattern: Optional[str] = None,
        name_pattern: Optional[str] = None,
        mode_pattern: Optional[str] = None,
        dry_run: bool = False,
    ):
        """Remove an arbitrary number of modifiers from this workspace based
        on some input arguments.

        Args:
            remove_index: Index of modifier to remove. Indices match ordering
                          from the output of print_modifiers
            scope_pattern: Pattern to select which scopes to remove modifiers from.
                           If the pattern matches multiple scopes, each will
                           have matching modifiers removed from them.
            name_pattern: Pattern to select which modifier names should be removed.
                          Modifiers with matching names that are in included
                          scopes will be removed. If the scope doesn't match,
                          but the name does, the modifier will not be removed.
            mode_pattern: Pattern to select which modes should be removed. Only
                          Modifiers which match the scope and name patterns will be
                          considered for removal, but this can be used to downselect further.
            dry_run: Whether to print the config instead of editing it, or to edit it directly.

        Returns:
            int: Number of modifiers removed
        """
        mod_list = self.index_modifiers()
        to_remove = []

        if remove_index is not None:
            if not isinstance(remove_index, int):
                logger.error(
                    "Cannot remove modifier index without an integer index. "
                    f"Given index was {remove_index}"
                )

            if remove_index < 0 or remove_index > len(mod_list):
                logger.error(
                    f"Modifier index {remove_index} is outside of the range of modifiers."
                    "Use `ramble worksapce manage modifiers --list` to see indices"
                )

            to_remove.append(mod_list[remove_index])

        if scope_pattern is not None:
            if name_pattern is None:
                name_pattern = "*"
            if mode_pattern is None:
                mode_pattern = "*"

            for mod_tup in mod_list:
                scope = mod_tup[0]
                mod_conf = mod_tup[1]
                if fnmatch.fnmatch(scope, scope_pattern):
                    if fnmatch.fnmatch(mod_conf["name"], name_pattern):
                        if "mode" in mod_conf and fnmatch.fnmatch(mod_conf["mode"], mode_pattern):
                            to_remove.append(mod_tup)
                        else:
                            to_remove.append(mod_tup)

        removed = 0

        for mod_tup in to_remove:
            base_section = self._get_scope_section(mod_tup[0])

            if base_section is not None:
                base_mods = base_section[namespace.modifiers]
                remove_index = -1
                for idx, ws_mod in enumerate(base_mods):
                    if ws_mod == mod_tup[1]:
                        remove_index = idx
                        break
                if remove_index != -1:
                    removed += 1
                    del base_mods[remove_index]

                if not base_section[namespace.modifiers]:
                    del base_section[namespace.modifiers]

                if not dry_run:
                    self.write_config(CONFIG_SECTION)

        return removed

    def add_modifier(
        self,
        name_pattern: str,
        scope: Optional[str] = None,
        mode: Optional[str] = None,
        on_executable: Optional[str] = None,
        dry_run: bool = False,
    ):
        """Add an arbitrary number of modifiers to this workspace within a single scope

        Args:
            scope: Scope to add modifiers within.
            name_pattern: Pattern to determine which modifiers should be added.
                          If multiple modifiers match, all will be added with
                          the additional arguments.
            mode: Mode to set within the new modifier definitions
            on_executable: A list string to set for the on_executable
                           attribute of the new modifier definitions.
            dry_run: Whether to print the config instead of editing it, or to edit it directly.

        Returns:
            int: Number of modifiers added to workspace
        """
        on_exec_list = None
        if on_executable is not None:
            on_exec_list = syaml.syaml_list()
            on_exec_list.extend(on_executable[1:-1].split(","))

        base_section = self._get_scope_section(scope)

        if namespace.modifiers not in base_section:
            base_section[namespace.modifiers] = syaml.syaml_list()

        mod_type = ramble.repository.ObjectTypes.modifiers
        mod_objects = ramble.repository.all_object_names(object_type=mod_type)
        if isinstance(name_pattern, str):
            spec_parts = name_pattern.partition("@")
        mod_names = [
            name
            for name in mod_objects
            if fnmatch.fnmatchcase(name.lower(), spec_parts[0].lower())
        ]

        if len(mod_names) < 1:
            logger.error(f"No modifiers found matching name pattern of {name_pattern}")

        added = 0
        for mod_name in mod_names:
            mod_def = syaml.syaml_dict()
            mod_def["name"] = mod_name
            if spec_parts[2]:
                mod_def["name"] += f"@{spec_parts[2]}"
            if mode is not None:
                mod_def["mode"] = mode
            if on_exec_list is not None:
                mod_def["on_executable"] = on_exec_list
            base_section[namespace.modifiers].append(mod_def)
            added += 1

        if not dry_run:
            self.write_config(CONFIG_SECTION)
        return added

    def add_include(self, new_include):
        """Add a new include to this workspace"""

        if (
            namespace.include
            not in self.config_sections[namespace.workspace]["yaml"][namespace.ramble]
        ):
            self.config_sections[namespace.workspace]["yaml"][namespace.ramble][
                namespace.include
            ] = []
        includes = self.config_sections[namespace.workspace]["yaml"][namespace.ramble][
            namespace.include
        ]
        includes.append(new_include)
        self.write_config(CONFIG_SECTION)

    def remove_include(self, index=None, pattern=None):
        """Remove one or more includes from this workspace.

        Args:
            index (int): (Optional) Numerical position of include to remove
            pattern (str): (Optional) String or pattern of include to remove.
                                Removes all matching includes.
        """

        if (
            namespace.include
            not in self.config_sections[namespace.workspace]["yaml"][namespace.ramble]
        ):
            return

        includes = self.config_sections[namespace.workspace]["yaml"][namespace.ramble][
            namespace.include
        ]
        changed = False

        if index is not None:
            if index < 0 or index >= len(includes):
                logger.die(
                    f"Requested index {index} " "is outside of the range of existing includes."
                )
            includes.pop(index)
            changed = True

        if pattern is not None:
            remove_indices = []
            for idx, include in enumerate(includes):
                if fnmatch.fnmatch(include, pattern):
                    remove_indices.append(idx)

            for remove_idx in reversed(remove_indices):
                if remove_idx >= 0 and remove_idx < len(includes):
                    includes.pop(remove_idx)
                    changed = True

        if changed:
            self.write_config(CONFIG_SECTION)

    def included_config_scopes(self):
        """List of included configuration scopes from the environment.

        Scopes are listed in the YAML file in order from highest to
        lowest precedence, so configuration from earlier scope will take
        precedence over later ones.

        This routine returns them in the order they should be pushed onto
        the internal scope stack (so, in reverse, from lowest to highest).
        """
        scopes = []

        # load config scopes added via 'include:', in reverse so that
        # highest-precedence scopes are last.
        includes = config_dict(self.config_sections[namespace.workspace]["yaml"]).get(
            "include", []
        )
        missing = []
        for full_config_path in reversed(includes):
            # Remove trailing slash
            config_path = full_config_path
            if full_config_path.endswith("/"):
                config_path = full_config_path[:-1]

            # allow paths to contain ramble config/environment variables, etc.
            config_path = substitute_path_variables(
                config_path, local_replacements=self.workspace_paths()
            )

            # treat relative paths as relative to the environment
            if not os.path.isabs(config_path):
                config_path = os.path.join(self.path, config_path)
                config_path = os.path.normpath(os.path.realpath(config_path))

            if os.path.isdir(config_path):
                # directories are treated as regular ConfigScopes
                config_name = f"workspace:{self.name}:{os.path.basename(config_path)}"
                scope = ramble.config.ConfigScope(config_name, config_path)
            elif os.path.exists(config_path):
                # files are assumed to be SingleFileScopes
                config_name = f"workspace:{self.name}:{config_path}"
                scope = ramble.config.SingleFileScope(
                    config_name, config_path, ramble.schema.merged.schema
                )
            else:
                missing.append(config_path)
                continue

            scopes.append(scope)

        if missing:
            msg = f"Detected {len(missing)} missing include path(s):"
            msg += "\n   {}".format("\n   ".join(missing))

            msg = f"{msg}\nPlease correct."

            logger.warn(msg)
            raise RambleActiveWorkspaceError(msg)

        return scopes

    def ws_file_config_scope_name(self):
        """Name of the config scope of this workspace's config file."""
        return f"{namespace.workspace}:{self.name}:{self.config_dir}"
        # return 'ws:%s' % self.name

    def ws_file_config_scope(self):
        """Get the configuration scope for the workspace's config file."""
        section = self.config_sections[namespace.workspace]
        config_name = self.ws_file_config_scope_name()
        return ramble.config.SingleFileScope(
            config_name,
            section["path"],
            ramble.schema.workspace.schema,
            [ramble.config.first_existing(section["raw_yaml"], ramble.schema.workspace.keys)],
        )

    def config_scopes(self):
        """A list of all configuration scopes for this workspace."""
        return self.included_config_scopes() + [self.ws_file_config_scope()] + [self.configs]

    def destroy(self):
        """Remove this workspace from Ramble entirely."""
        shutil.rmtree(self.path)

    def _get_workspace_dict(self):
        return (
            self.config_sections[namespace.workspace]["yaml"]
            if namespace.workspace in self.config_sections
            else None
        )

    def _get_application_dict_config(self, key):
        return self.application_configs[key]["yaml"] if key in self.application_configs else None

    def read_transaction(self):
        """Get a read lock context manager for use in a `with` block."""
        return lk.ReadTransaction(self.txlock, acquire=self._re_read)

    def write_transaction(self):
        """Get a write lock context manager for use in a `with` block."""
        return lk.WriteTransaction(self.txlock, acquire=self._re_read)

    def __enter__(self):
        self._previous_active = _active_workspace
        activate(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        deactivate()
        if self._previous_active:
            activate(self._previous_active)

    def check_cache(self, tupl):
        return self.install_cache.contains(tupl)

    def add_to_cache(self, tupl):
        self.install_cache.add(tupl)


def read(name):
    """Get a workspace with the supplied name."""
    validate_workspace_name(name)
    if not exists(name):
        raise RambleWorkspaceError(f"no such workspace '{name}'")
    return Workspace(root(name))


def yaml_equivalent(first, second):
    """Returns whether two ramble yaml items are equivalent, including overrides"""
    if isinstance(first, dict):
        return isinstance(second, dict) and _equiv_dict(first, second)
    elif isinstance(first, list):
        return isinstance(second, list) and _equiv_list(first, second)
    else:  # it's a string
        return isinstance(second, str) and first == second


def _equiv_list(first, second):
    """Returns whether two ramble yaml lists are equivalent, including overrides"""
    if len(first) != len(second):
        return False
    return all(yaml_equivalent(f, s) for f, s in zip(first, second))


def _equiv_dict(first, second):
    """Returns whether two ramble yaml dicts are equivalent, including overrides"""
    if len(first) != len(second):
        return False
    same_values = all(yaml_equivalent(fv, sv) for fv, sv in zip(first.values(), second.values()))
    same_keys_with_same_overrides = all(
        fk == sk and getattr(fk, "override", False) == getattr(sk, "override", False)
        for fk, sk in zip(first.keys(), second.keys())
    )
    return same_values and same_keys_with_same_overrides


def _read_yaml(str_or_file, schema):
    """Read YAML from a file for round-trip parsing."""
    data = ramble.config.load_config(str_or_file)
    filename = getattr(str_or_file, "name", None)
    default_data = ramble.config.validate(data, schema, filename)
    return (data, default_data)


def _write_yaml(data, str_or_file, schema):
    """Write YAML to a file preserving comments and dict order."""
    filename = getattr(str_or_file, "name", None)
    ramble.config.validate(data, schema, filename)
    syaml.dump_config(data, str_or_file, default_flow_style=False)


@contextlib.contextmanager
def no_active_workspace():
    """Deactivate the active workspace for the duration of the context. Has no
    effect when there is no active workspace."""
    ws = active_workspace()
    env_var = None
    if RAMBLE_WORKSPACE_VAR in os.environ:
        env_var = os.environ[RAMBLE_WORKSPACE_VAR]
        del os.environ[RAMBLE_WORKSPACE_VAR]

    try:
        deactivate()
        yield
    finally:
        if ws:
            if env_var is not None:
                os.environ[RAMBLE_WORKSPACE_VAR] = env_var
            activate(ws)


def _filter_results(results, summary_only, fom_origin_types=None):
    if (not summary_only and not fom_origin_types) or namespace.experiment not in results:
        return results
    results = copy.deepcopy(results)

    filtered_experiments = []
    for r in results[namespace.experiment]:
        if summary_only and r["N_REPEATS"] == 0:
            continue

        if fom_origin_types:
            filtered_contexts = []
            for context in r.get("CONTEXTS", []):
                filtered_foms = [
                    fom
                    for fom in context.get("foms", [])
                    if fom.get("origin_type") in fom_origin_types
                ]
                if filtered_foms:
                    context["foms"] = filtered_foms
                    filtered_contexts.append(context)
            r["CONTEXTS"] = filtered_contexts

        filtered_experiments.append(r)

    results[namespace.experiment] = filtered_experiments
    return results


class RambleWorkspaceError(ramble.error.RambleError):
    """Superclass for all errors to do with Ramble Workspaces"""


class RambleInvalidTemplateNameError(ramble.error.RambleError):
    """Error when an invalid template name is provided"""


class RambleConflictingDefinitionError(RambleWorkspaceError):
    """Error when conflicting software definitions are found"""


class RambleActiveWorkspaceError(RambleWorkspaceError):
    """Error when an invalid workspace is activated"""
