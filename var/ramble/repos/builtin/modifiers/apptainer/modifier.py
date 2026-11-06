# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import re

import llnl.util.filesystem as fs

from ramble.base_mod.builtin.container_base import ContainerBase
from ramble.modkit import *
from ramble.util import json_util
from ramble.util.hashing import hash_json, hash_string

from spack.util.path import canonicalize_path


class Apptainer(ContainerBase):
    """Apptainer is a container platform. It allows you to create and run
    containers that package up pieces of software in a way that is portable and
    reproducible. You can build a container using Apptainer on your laptop, and
    then run it on many of the largest HPC clusters in the world, local
    university or company clusters, a single server, in the cloud, or on a
    workstation down the hall. Your container is a single file, and you don’t
    have to worry about how to install all the software you need on each
    different operating system.

    Building from a definition file: if ``container_uri`` ends in ``.def``, the
    ``pull_container`` setup phase runs
    ``apptainer build {container_path} {container_uri}`` on the host running
    ``ramble workspace setup``, but only when ``{container_path}`` does not
    exist yet. Otherwise the image is fetched with ``apptainer pull``.

    Experiment hash: each experiment's inventory includes the SIF ID of
    ``{container_path}``. Because pipeline ``_prepare()`` computes initial
    experiment hashes before setup phases run, ``_pull_container`` refreshes
    the experiment inventories once ``{container_path}`` is built or pulled
    (before ``make_experiments`` renders ``{experiment_hash}``). If the SIF
    file is manually rebuilt or replaced outside Ramble later, re-run
    ``ramble -D $WS workspace setup`` (or pass ``--overwrite-inventories``) to
    update the recorded hash."""

    container_extension = "sif"
    _runtime = "apptainer"
    name = "apptainer"

    tags("container")

    maintainers("douglasjacobsen")

    required_variable(
        "container_name",
        description="The variable controls the name of the resulting container file. "
        "It will be of the format {container_name}.{container_extension}.",
    )

    modifier_variable(
        "container_dir",
        default="{workload_input_dir}",
        description="Directory where the container sqsh will be stored",
        modes=["standard"],
    )

    modifier_variable(
        "container_path",
        default="{container_dir}/{container_name}." + container_extension,
        description="Full path to the container sqsh file",
        modes=["standard"],
    )

    modifier_variable(
        "apptainer_run_args",
        default="--bind {container_mounts}",
        description="Arguments to pass into `apptainer run` while executing the experiments",
        modes=["standard"],
    )

    variable_modification(
        "mpi_command",
        "apptainer run {apptainer_run_args} {container_path}",
        method="append",
        modes=["standard"],
    )

    register_phase(
        "pull_container",
        pipeline="setup",
        run_after=["get_inputs"],
        run_before=["make_experiments"],
    )

    def _pull_container(self, workspace, app_inst=None):
        """Import the container uri as an apptainer sif file

        Extract the container uri and path from the experiment, and import
        (using apptainer) into the target container_dir.
        """

        self._build_runner(
            runtime=self._runtime, app_inst=app_inst, dry_run=workspace.dry_run
        )

        uri = self.expander.expand_var_name("container_uri")

        container_dir = canonicalize_path(
            self.expander.expand_var_name("container_dir")
        )
        container_path = canonicalize_path(
            self.expander.expand_var_name("container_path")
        )

        if uri.endswith(".def"):
            pull_args = ["build", container_path, canonicalize_path(uri)]
        else:
            pull_args = ["pull", container_path, uri]

        if not os.path.exists(container_path):
            if not workspace.dry_run:
                fs.mkdirp(container_dir)
            self.apptainer_runner.execute(
                self.apptainer_runner.command, pull_args
            )
            if (
                app_inst
                and not workspace.dry_run
                and os.path.isfile(container_path)
            ):
                for (
                    _,
                    exp_inst,
                    _,
                ) in app_inst.experiment_set.all_experiments():
                    for mod_inst in exp_inst._modifier_instances:
                        if mod_inst.name == self.name:
                            for obj_conf in exp_inst.hash_inventory.get(
                                "object_configuration", []
                            ):
                                if (
                                    obj_conf.get("name") == self.name
                                    and obj_conf.get("type") == "modifiers"
                                ):
                                    obj_conf["artifacts"] = (
                                        mod_inst.artifact_inventory(
                                            workspace, exp_inst
                                        )
                                    )
                            exp_inst.experiment_hash = hash_json(
                                exp_inst.hash_inventory
                            )
                            exp_inst.variables[
                                exp_inst.keywords.experiment_hash
                            ] = exp_inst.experiment_hash
                            if os.path.exists(exp_inst.inventory_file):
                                with open(
                                    exp_inst.inventory_file,
                                    "w+",
                                    encoding="utf-8",
                                ) as f:
                                    json_util.dump(exp_inst.hash_inventory, f)
        else:
            logger.msg(f"Container is already pulled at {container_path}")

    def artifact_inventory(self, workspace, app_inst=None):
        """Return hash of container uri and sqsh file if they exist

        Args:
            workspace (Workspace): Reference to workspace
            app_inst (ApplicationBase): Reference to application instance

        Returns:
            (dict): Artifact inventory for container attributes
        """

        self._build_runner(
            runtime=self._runtime, app_inst=app_inst, dry_run=workspace.dry_run
        )

        id_regex = re.compile(r"\s*ID:\s*(?P<id>\S+)")
        container_name = self.expander.expand_var_name("container_name")
        container_uri = self.expander.expand_var_name("container_uri")
        container_path = canonicalize_path(
            self.expander.expand_var_name("container_path")
        )
        header_args = ["sif", "header", container_path]

        inventory = []

        inventory.append(
            {
                "container_uri": container_uri,
                "digest": hash_string(container_uri),
            }
        )

        container_id = None

        if os.path.isfile(container_path):
            header = self.apptainer_runner.execute(
                self.apptainer_runner.command, header_args, return_output=True
            )

            search_match = id_regex.search(header)

            if search_match:
                container_id = search_match.group("id")

        if container_id:
            inventory.append(
                {"container_name": container_name, "digest": container_id}
            )
        else:
            inventory.append(
                {"container_name": container_name, "digest": None}
            )

        return inventory
