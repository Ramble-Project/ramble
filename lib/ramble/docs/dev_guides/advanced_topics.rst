.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _definition-dev-guide-adv-topics:

=========================================
Advanced Topics for Definition Developers
=========================================

Some application or modifier definition files have more complex requirements
than those met with the directives that are covered in the object specific
developer guides. This developers guide will teach you several more advanced
concepts to help write more specialized definition files.

The functionality described in this guide is briefly described within the
:ref:`package manager developer guide<package-manager-dev-guide>`, but will be
covered in more detail here. This functionality is shared by all of the object
types supported in Ramble.

.. _ramble-pipelines-and-phases:

-------------------------------
Experiment Pipelines and Phases
-------------------------------

Architecture Overview
=====================

Ramble organizes workspaces into a modular **Pipeline** and **Phase Graph** architecture.

Pipelines
---------

Ramble has a concept of a ``pipeline`` which represents full actions that can
be taken on a workspace. Each ``pipeline`` has a corresponding workspace
command and targets a specific stage of the experiment lifecycle. The most 
common pipelines are:

   * :ref:`ramble workspace setup <ramble-workspace-setup>`
     → :py:class:`~ramble.pipeline.SetupPipeline`
   * :ref:`ramble on <ramble-on>`
     → :py:class:`~ramble.pipeline.ExecutePipeline`
   * :ref:`ramble workspace analyze <ramble-workspace-analyze>`
     → :py:class:`~ramble.pipeline.AnalyzePipeline`
   * :ref:`ramble workspace archive <ramble-workspace-archive>`
     → :py:class:`~ramble.pipeline.ArchivePipeline`

There are more pipelines that Ramble can use to perform complex actions
on a workspace, which can be seen in the :ref:`Additional Pipelines
<additional-pipelines>` section below.

Phase Graphs
------------

Pipelines are built out of phases. In Ramble, a ``phase`` represents a specific
step along the path of completing the action defined by the ``pipeline``.
Examples of phases include ``get_inputs`` (for downloading input files needed
by a workload) and ``software_install`` (for performing software installation
using a package manager).

For each pipeline, Ramble builds a directed acyclic graph
(:py:class:`ramble.graphs.PhaseGraph`) containing all phases registered for that pipeline.

   * **Constraint Declaration**: Phase dependency constraints are declared within object class
     definitions using ``run_before=['phase_name']`` or ``run_after=['phase_name']``.
   * **Order Resolution**: When a pipeline initializes, :py:class:`ramble.graphs.PhaseGraph`
     resolves phase dependencies using a topological sort. If cyclical dependencies exist,
     Ramble raises a :py:class:`~ramble.error.RambleError`.

Phase Registration
==================

Phases can be defined in a variety of locations. Some base classes define phases for specific
pipelines. For example:

    * `ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_
      registers phases such as ``get_inputs``, ``license_includes``, and
      ``make_experiments`` in the ``setup`` pipeline, ``prepare_analysis`` and
      ``analyze_experiments`` in the ``analyze`` pipeline, and ``archive_experiments`` in the
      ``archive`` pipeline.
    * `PackageManagerBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/package-manager-base/base_class.py>`_
      registers ``check_auxiliary_software_files`` in the ``setup`` pipeline and
      ``add_software_to_results`` in the ``analyze`` pipeline.

Additionally, instances of the base classes (e.g., application, modifier, or package manager)
can define and register their own phases to build more complex pipelines for specific use
cases. Some examples include:

    * The `HpcgBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_applications/hpcg/base_application.py>`_
      base application registers ``calculate_values`` in the ``setup`` pipeline to compute
      grid dimensions from memory variables before experiment scripts are rendered.
    * The `Spack <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack/package_manager.py>`_
      package manager registers ``software_install`` and ``define_package_paths`` in the
      ``setup`` pipeline (extending the ``software_create_env`` and ``software_configure``
      phases inherited from
      `SpackLightweight <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack-lightweight/package_manager.py>`_).
    * Container modifiers such as
      `Docker <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/modifiers/docker/modifier.py>`_
      and
      `Apptainer <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/modifiers/apptainer/modifier.py>`_
      register phases like ``build_container``, ``pull_container``, and
      ``format_docker_mounts`` in the ``setup`` pipeline (alongside
      ``define_container_variables`` from
      `ContainerBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_modifiers/container-base/base_modifier.py>`_).

Each phase is defined in two parts. The first part is to define
a class method on an object definition. Phase names need to begin with an
underscore, and they have the following signature:

.. code-block::

  def _new_phase_name(self, workspace, app_inst=None)

In this signature, ``workspace`` is a reference to the workspace that has a
pipeline acting on it, and ``app_inst`` is a reference to the application
instance representing the experiment. The ``app_inst`` should be identical to
``self`` when ``self`` is an instance of an application definition.

Once the phase's method is complete, it can be registered into a pipeline as
follows:

.. code-block::

  register_phase("new_phase_name", pipeline="setup", run_before=["make_experiments"])

This example would register the phase defined by ``_new_phase_name`` into the
setup pipeline, and make sure it is executed before the ``make_experiments``
phase. Phase registration can also define a ``run_after`` list of phases to execute
before the newly registered phase. A phase can also be registered into multiple
pipelines, by calling the ``register_phase`` directive multiple times.

.. _standard-pipelines:

Example Experiment Pipelines
----------------------------

The following sections illustrate the pipeline phase graphs constructed
for a common experiment workflow of ``ramble workspace setup`` → ``ramble on`` →
``ramble workspace analyze`` using the
`Hpcg <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/applications/hpcg/application.py>`_
application and the
`Spack <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack/package_manager.py>`_
package manager. In this scenario, no phases are added
to the :py:class:`ramble.pipeline.ExecutePipeline` by any of the objects, so we'll only
be examining the :py:class:`ramble.pipeline.SetupPipeline` and
:py:class:`ramble.pipeline.AnalyzePipeline`.

Example: Setup Pipeline
************************

* **CLI Command**: :ref:`ramble workspace setup <ramble-workspace-setup>`
* **Class**: :py:class:`ramble.pipeline.SetupPipeline`

When :py:class:`~ramble.pipeline.SetupPipeline` initializes, Ramble constructs a
:py:class:`~ramble.graphs.PhaseGraph` by combining the ``setup`` phases registered across both
``Hpcg`` and ``Spack`` object inheritance hierarchies. `Hpcg <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_applications/hpcg/base_application.py>`_
inherits from `HpcgBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_applications/hpcg/base_application.py>`_
which, in turn, inherits from `ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_.
Likewise, `Spack <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack/package_manager.py>`_
inherits from `SpackLightweight <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack-lightweight/package_manager.py>`_
which inherits from `PackageManagerBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/package-manager-base/base_class.py>`_.
This results in the following phases being registered by the associated objects:

* **Application Hierarchy**:

  * `ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_
    registers:

    * ``bootstrap_utilities`` (``run_before=["get_inputs"]``)
    * ``get_inputs`` (unconstrained)
    * ``license_includes`` (unconstrained)
    * ``make_experiments`` (``run_after=["get_inputs"]``)
    * ``write_status`` (``run_after=["make_experiments"]``)

  * `HpcgBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_applications/hpcg/base_application.py>`_
    registers:
    
    * ``calculate_values`` (``run_before=["make_experiments"]``)

  * `Hpcg <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_applications/hpcg/base_application.py>`_
    doesn't register any additional phases.

* **Package Manager Hierarchy**:

  * `PackageManagerBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/package-manager-base/base_class.py>`_
    registers:
    
    * ``check_auxiliary_software_files`` (``run_after=["make_experiments"]``)

  * `SpackLightweight <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack-lightweight/package_manager.py>`_
    registers:

    * ``software_create_env`` (unconstrained)
    * ``software_install_requested_compilers``
      (``run_after=["software_create_env"]`` when ``+spack_install_compilers`` is enabled)
    * ``software_configure``
      (``run_after=["software_create_env", "software_install_requested_compilers"]``)
    * ``evaluate_requirements`` (``run_before=["make_experiments"]``)

  * `Spack <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack/package_manager.py>`_
    registers:

    * ``software_install`` (``run_after=["software_configure"]``,
      ``run_before=["evaluate_requirements"]``)
    * ``define_package_paths`` (``run_after=["software_install", "evaluate_requirements"]``,
      ``run_before=["make_experiments"]``)

The diagram below shows the resulting :py:class:`~ramble.graphs.PhaseGraph` directed acyclic graph
(DAG), where directed connecting lines express the ``run_before`` / ``run_after`` dependencies and
nodes are colored to indicate the object hierarchy that registered them (green for the application
hierarchy, blue for the package manager hierarchy):

.. graphviz::

    digraph hpcg_spack_setup_dag {
        fontsize=12;
        rankdir=TB;
        nodesep=0.35;
        ranksep=0.45;

        node [shape=box, style="filled,rounded", fontsize=10, margin="0.18,0.1"];
        edge [fontsize=9, color="#475569", penwidth=1.3];

        // ApplicationBase phases (green)
        bootstrap_utilities [
            label=<<b>bootstrap_utilities</b><br/><i>(ApplicationBase)</i>>,
            fillcolor="#e6f4ea",
            color="#28a745",
            penwidth=2.0,
            group="left_col"
        ];
        get_inputs [
            label=<<b>get_inputs</b><br/><i>(ApplicationBase)</i>>,
            fillcolor="#e6f4ea",
            color="#28a745",
            penwidth=2.0,
            group="left_col"
        ];
        license_includes [
            label=<<b>license_includes</b><br/><i>(ApplicationBase)</i>>,
            fillcolor="#e6f4ea",
            color="#28a745",
            penwidth=2.0,
            group="left_col"
        ];
        make_experiments [
            label=<<b>make_experiments</b><br/><i>(ApplicationBase)</i>>,
            fillcolor="#e6f4ea",
            color="#28a745",
            penwidth=2.0,
            group="mid_col"
        ];
        write_status [
            label=<<b>write_status</b><br/><i>(ApplicationBase)</i>>,
            fillcolor="#e6f4ea",
            color="#28a745",
            penwidth=2.0
        ];

        // HpcgBase base application phase (green)
        calculate_values [
            label=<<b>calculate_values</b><br/><i>(HpcgBase)</i>>,
            fillcolor="#e6f4ea",
            color="#28a745",
            penwidth=2.0,
            group="calc_col"
        ];

        // PackageManagerBase / SpackLightweight / Spack phases (blue)
        software_create_env [
            label=<<b>software_create_env</b><br/><i>(SpackLightweight)</i>>,
            fillcolor="#eef6ff",
            color="#0056b3",
            penwidth=2.0,
            group="right_col"
        ];
        software_install_requested_compilers [
            label=<<b>software_install_requested_compilers</b><br/><i>(SpackLightweight)</i>>,
            fillcolor="#eef6ff",
            penwidth=2.0,
            color="#0056b3"
        ];
        software_configure [
            label=<<b>software_configure</b><br/><i>(SpackLightweight)</i>>,
            fillcolor="#eef6ff",
            color="#0056b3",
            penwidth=2.0,
            group="right_col"
        ];
        software_install [
            label=<<b>software_install</b><br/><i>(Spack)</i>>,
            fillcolor="#eef6ff",
            color="#0056b3",
            penwidth=2.0,
            group="right_col"
        ];
        evaluate_requirements [
            label=<<b>evaluate_requirements</b><br/><i>(SpackLightweight)</i>>,
            fillcolor="#eef6ff",
            color="#0056b3",
            penwidth=2.0,
            group="mid_col"
        ];
        define_package_paths [
            label=<<b>define_package_paths</b><br/><i>(Spack)</i>>,
            fillcolor="#eef6ff",
            color="#0056b3",
            penwidth=2.0,
            group="right_col"
        ];
        check_auxiliary_software_files [
            label=<<b>check_auxiliary_software_files</b><br/><i>(PackageManagerBase)</i>>,
            fillcolor="#eef6ff",
            penwidth=2.0,
            color="#0056b3"
        ];

        // Invisible spacers to align license_includes vertically with bootstrap_utilities on the far left
        _pad1 [style=invis, shape=point, width=0, height=0, group="left_col"];
        _pad2 [style=invis, shape=point, width=0, height=0, group="left_col"];
        _pad3 [style=invis, shape=point, width=0, height=0, group="left_col"];
        _calc_pad [style=invis, shape=point, width=0, height=0, group="calc_col"];
        license_includes -> _pad1 -> _pad2 -> _pad3 -> bootstrap_utilities [style=invis, weight=10];
        _calc_pad -> calculate_values [style=invis, weight=10];

        { rank=same; license_includes; software_create_env; }
        license_includes -> software_create_env [style=invis];
        { rank=same; _pad1; software_install_requested_compilers; }
        _pad1 -> software_install_requested_compilers [style=invis];
        { rank=same; bootstrap_utilities; _calc_pad; evaluate_requirements; }
        bootstrap_utilities -> _calc_pad -> evaluate_requirements [style=invis];

        // Application dependency edges
        bootstrap_utilities -> get_inputs [weight=10];
        get_inputs -> make_experiments;
        calculate_values -> make_experiments;
        make_experiments -> write_status;

        // Package manager dependency edges
        software_create_env -> software_install_requested_compilers;
        software_create_env -> software_configure [weight=10];
        software_install_requested_compilers -> software_configure;
        software_configure -> software_install [weight=10];
        software_install -> evaluate_requirements;
        software_install -> define_package_paths [weight=10];
        evaluate_requirements -> define_package_paths;
        evaluate_requirements -> make_experiments [weight=10];
        define_package_paths -> make_experiments;
        make_experiments -> check_auxiliary_software_files;
    }

You'll notice that some phases don't have explicit constraints defined by
them at registration, but do have constraints applied indirectly on them
when other phases are registered - e.g.,  ``get_inputs`` has no explicit constraints
but ``bootstrap_utilities`` has a ``run_before=["get_inputs"]`` constraint and
``make_experiments`` has a ``run_after=["get_inputs"]`` constraint. Some phases, like
``license_includes``, have no constraints at all, and their execution order gets
resolved by the :py:class:`~ramble.graphs.PhaseGraph` topological sort. When
:py:class:`~ramble.graphs.PhaseGraph` topologically sorts this graph, the phases are
flattened into the following execution order:

#. ``bootstrap_utilities`` (`ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_)
#. ``license_includes`` (`ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_)
#. ``calculate_values`` (`HpcgBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_applications/hpcg/base_application.py>`_)
#. ``software_create_env`` (`SpackLightweight <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack-lightweight/package_manager.py>`_)
#. ``get_inputs`` (`ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_)
#. ``software_install_requested_compilers`` (`SpackLightweight <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack-lightweight/package_manager.py>`_)
#. ``software_configure`` (`SpackLightweight <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack-lightweight/package_manager.py>`_)
#. ``software_install`` (`Spack <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack/package_manager.py>`_)
#. ``evaluate_requirements`` (`SpackLightweight <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack-lightweight/package_manager.py>`_)
#. ``define_package_paths`` (`Spack <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack/package_manager.py>`_)
#. ``make_experiments`` (`ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_)
#. ``write_status`` (`ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_)
#. ``check_auxiliary_software_files`` (`PackageManagerBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/package-manager-base/base_class.py>`_)

Example: Analyze Pipeline
**************************

* **CLI Command**: :ref:`ramble workspace analyze <ramble-workspace-analyze>`
* **Class**: :py:class:`ramble.pipeline.AnalyzePipeline`

The analyze pipeline evaluates completed experiments, extracts metrics, records software
provenance, and writes results using phases registered across the application and package
manager hierarchies. Fewer phases are registered in the
:py:class:`ramble.pipeline.AnalyzePipeline` by the `Hpcg` and `Spack` object hierarchies:

* **Application Hierarchy**:

  * `ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_
    registers:

    * ``prepare_analysis`` (unconstrained)
    * ``analyze_experiments`` (``run_after=["prepare_analysis"]``)
    * ``write_status`` (``run_after=["analyze_experiments"]``)
    * ``append_results_to_workspace`` (``run_after=["analyze_experiments"]``)
    * ``write_results_cache`` (``run_after=["write_status", "append_results_to_workspace"]``)

* **Package Manager Hierarchy**:

  * `PackageManagerBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/package-manager-base/base_class.py>`_
    registers:

    * ``add_software_to_results`` (``run_after=["analyze_experiments"]``,
      ``run_before=["append_results_to_workspace"]``)

The diagram below shows the resulting :py:class:`~ramble.graphs.PhaseGraph` DAG.

.. graphviz::

    digraph analyze_pipeline {
        fontsize=12;
        rankdir=TB;
        nodesep=0.35;
        ranksep=0.45;

        node [shape=box, style="filled,rounded", fontsize=10, margin="0.18,0.1"];
        edge [fontsize=9, color="#475569", penwidth=1.3];

        // ApplicationBase phases (green)
        prepare_analysis [
            label=<<b>prepare_analysis</b><br/><i>(ApplicationBase)</i>>,
            fillcolor="#e6f4ea",
            color="#28a745",
            penwidth=2.0,
            group="main_col"
        ];
        analyze_experiments [
            label=<<b>analyze_experiments</b><br/><i>(ApplicationBase)</i>>,
            fillcolor="#e6f4ea",
            color="#28a745",
            penwidth=2.0,
            group="main_col"
        ];
        write_status [
            label=<<b>write_status</b><br/><i>(ApplicationBase)</i>>,
            fillcolor="#e6f4ea",
            color="#28a745",
            penwidth=2.0
        ];
        append_results_to_workspace [
            label=<<b>append_results_to_workspace</b><br/><i>(ApplicationBase)</i>>,
            fillcolor="#e6f4ea",
            color="#28a745",
            penwidth=2.0,
            group="main_col"
        ];
        write_results_cache [
            label=<<b>write_results_cache</b><br/><i>(ApplicationBase)</i>>,
            fillcolor="#e6f4ea",
            color="#28a745",
            penwidth=2.0,
            group="main_col"
        ];

        // PackageManagerBase phase (blue)
        add_software_to_results [
            label=<<b>add_software_to_results</b><br/><i>(PackageManagerBase)</i>>,
            fillcolor="#eef6ff",
            color="#0056b3",
            penwidth=2.0
        ];

        prepare_analysis -> analyze_experiments [weight=10];
        analyze_experiments -> write_status;
        analyze_experiments -> append_results_to_workspace [weight=10];
        analyze_experiments -> add_software_to_results;
        add_software_to_results -> append_results_to_workspace;
        write_status -> write_results_cache;
        append_results_to_workspace -> write_results_cache [weight=10];
    }

When the :py:class:`~ramble.graphs.PhaseGraph` topologically sorts this graph, the phases are
flattened into the following execution order:

#. ``prepare_analysis`` (`ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_)
#. ``analyze_experiments`` (`ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_)
#. ``write_status`` (`ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_)
#. ``add_software_to_results`` (`PackageManagerBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/package-manager-base/base_class.py>`_)
#. ``append_results_to_workspace`` (`ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_)
#. ``write_results_cache`` (`ApplicationBase <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/base_classes/application-base/base_class.py>`_)

.. _pipeline-exploration:

Exploring Experiment Pipelines
===============================

Several Ramble commands are useful for understanding what objects register phases in
what pipelines, how these phased registrations are applied to a given workspace, and
what the resulting ordered phase execution is for a given pipeline.

To explore and understand what phases a Ramble object registers, you can use the
:ref:`ramble info <ramble-info>` command:

.. code-block:: bash

    ramble info --attributes registered_phases hpcg
    ramble info --type base_classes application-base --attributes registered_phases
    ramble info --type package_managers --attributes registered_phases spack

To understand what phases are registered for a given workspace, you can use the
:ref:`ramble workspace info <ramble-workspace-info>` command:

.. code-block:: bash

    ramble workspace info --phases

And finally, to understand the phase graph order for a given workspace's pipeline, you can
use the ``--debug`` and ``-dry-run`` options together along with ``--disable-progress-bar``
and ``--disable-logger`` and ``grep`` for "Executing phase". The results are returned in
the topologically sorted order:

.. code-block:: bash

    ramble --debug --disable-progress-bar --disable-logger workspace setup --dry-run 2>&1 | grep "Executing phase"
    ramble --debug --disable-progress-bar --disable-logger workspace analyze --dry-run 2>&1 | grep "Executing phase"

.. _additional-pipelines:

Additional Pipelines
====================

In addition to :py:class:`ramble.pipeline.ExecutePipeline`,
:py:class:`ramble.pipeline.SetupPipeline`,
:py:class:`ramble.pipeline.AnalyzePipeline`, and 
:py:class:`ramble.pipeline.ArchivePipeline`, Ramble provides several additional pipelines:

* **Mirror Pipeline** (:py:class:`~ramble.pipeline.MirrorPipeline`):

  * **CLI Command**: :ref:`ramble workspace mirror <ramble-workspace-mirror>`
  * Downloads software tarballs and workload input files into a local workspace mirror for offline
    execution (see :doc:`../mirror_config`).

* **PushDeployment Pipeline** (:py:class:`~ramble.pipeline.PushDeploymentPipeline`):

  * **CLI Command**: :ref:`ramble deployment push <ramble-deployment-push>`
  * Packages workspace configurations, software definitions, and templates into a deployment
    bundle suitable for distribution (see :doc:`../workspace`).

* **PushToCache Pipeline** (:py:class:`~ramble.pipeline.PushToCachePipeline`):

  * **CLI Command**: :ref:`ramble workspace push-to-cache <ramble-workspace-push-to-cache>`
  * Pushes compiled software environments to a Spack build cache (see :doc:`../package_managers`).

* **Bootstrap Pipeline** (:py:class:`~ramble.pipeline.BootstrapPipeline`):

  * **CLI Command**: :ref:`ramble workspace bootstrap <ramble-workspace-bootstrap>`
  * Bootstraps external utilities required by the workspace (see :doc:`../utilities`).

* **Logs Pipeline** (:py:class:`~ramble.pipeline.LogsPipeline`):

  * **CLI Command**: :ref:`ramble workspace experiment-logs <ramble-workspace-experiment-logs>`
  * Inspects log files and archive patterns across workspace experiments (see :doc:`../workspace`).

Pipeline Reference Links
========================

* **Pipeline Engine**:

  * Base Class: :py:class:`ramble.pipeline.Pipeline`
  * Setup: :py:class:`ramble.pipeline.SetupPipeline`
  * Execute: :py:class:`ramble.pipeline.ExecutePipeline`
  * Analyze: :py:class:`ramble.pipeline.AnalyzePipeline`
  * Archive: :py:class:`ramble.pipeline.ArchivePipeline`
  * Mirror: :py:class:`ramble.pipeline.MirrorPipeline`
  * PushDeployment: :py:class:`ramble.pipeline.PushDeploymentPipeline`
  * PushToCache: :py:class:`ramble.pipeline.PushToCachePipeline`

* **Phase Graph Engine**:

  * Graph: :py:class:`ramble.graphs.PhaseGraph`
  * Node: :py:class:`ramble.util.graph.GraphNode`

* **Phase Directives**:

  * Directive: :py:func:`ramble.language.shared_language.register_phase`

.. _ramble-builtins:

--------
Builtins
--------

Another component of object definitions is a ``builtin``. These are intended to
be semi-static command blocks that should / could be injected into experiments
using this definition. Similar to phases, builtins are defined in two steps.

The first step in defining a ``builtin`` is to define a class method with the
following signature:

.. code-block::

  def new_builtin(self):
    cmds = []
    ... add strings to cmds ...
    return cmds

Once the class method is defined, the second step is to register the builtin
into the object definition. Builtin registration is accomplished using the
``register_builtin`` directive, as follows:

.. code-block::

  register_builtin("new_builtin", required=True/False, injection_method="prepend"/"append", depends_on=[...])

When registering a builtin, the ``required`` attribute controls whether the builtin
is required to be present in experiments generated using the object or not. The
``injection_method`` attribute controls if the commands defined by the builtin
should be at the beginning (``prepend``) or end (``append``) of the experiment.
The ``depends_on`` attribute can be used to define the ordering of multiple
builtins relative to each other. Fully qualified builtin names are passed in
here, and their named depend on which object they are defined in.
