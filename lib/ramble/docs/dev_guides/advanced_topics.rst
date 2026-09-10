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
than those met with the directives that are covered the object specific
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
:ref:`common pipelines <standard-pipelines>` are:

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
pipelines. Additionally, Applications, Modifiers, and Package Managers can all define and
register their own phases to build more complex pipelines for specific use cases.

   * :doc:`Applications <../application_list>` define core command generation, input downloading,
     license inclusion, and analysis hooks.
   * :doc:`Package Managers <../package_managers>` (e.g., Spack, Pip) inject software environment
     creation and installation phases.
   * :doc:`Modifiers <../modifier_list>` (e.g., containers, profilers) inject pre-exec and post-exec
     hooks.
   * :doc:`Workflow Managers <../workflow_managers>` (e.g., Slurm, PBS, Google Batch) define batch
     submission logic and job execution wrappers.
   * :doc:`Systems <../systems>` and :doc:`Platforms <../platforms>` contribute hardware-specific
     variables, CPU architecture parameters, and compiler configurations expanded during pipeline
     setup.

Each phase is defined in two parts. The first part is to define
a class method on a object definition. Phase names need to begin with an
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

The diagram below illustrates a :py:class:`~ramble.pipeline.SetupPipeline` example of how
classes register specific phases via ``register_phase()`` into the pipeline's
:py:class:`~ramble.graphs.PhaseGraph` as phases:

.. graphviz::

    digraph setup_phase_registration {
        newrank=true;
        fontsize=12;
        rankdir=TB;
        nodesep=0.8;
        ranksep=0.4;
        compound=true;

        node [shape=box, style="filled,rounded", fontsize=11, margin="0.2,0.12"];
        edge [fontsize=10, color="#0056b3", penwidth=1.5];

        // Classes
        subgraph cluster_classes {
            label=<<b>Classes</b>>;
            labelloc=t;
            labeljust=c;
            style="filled,dashed";
            fillcolor="#f8f9fa";
            color="#cbd5e1";
            fontsize=12;
            margin=20;

            mod [
                label="Modifier\n(e.g., Profilers)",
                fillcolor="#eef6ff",
                color="#0056b3",
                width=2.5
            ];
            pm  [
                label="Package Manager\n(e.g., Spack)",
                fillcolor="#eef6ff",
                color="#0056b3",
                width=2.5
            ];
            app [
                label="Application Definition\n(e.g., Gromacs)",
                fillcolor="#eef6ff",
                color="#0056b3",
                width=2.5
            ];

            mod -> pm -> app [style=invis];
        }

        // PhaseGraph Execution Order
        subgraph cluster_phases {
            label=<<b>SetupPipeline PhaseGraph</b>>;
            labelloc=t;
            labeljust=c;
            style="filled,dashed";
            fillcolor="#f8f9fa";
            color="#cbd5e1";
            fontsize=12;
            margin=20;

            p1 [
                label="Phase 1: bootstrap_utilities",
                fillcolor="#e6f4ea",
                color="#28a745",
                width=2.5
            ];
            p2 [
                label="Phase 2: software_create_env",
                fillcolor="#e6f4ea",
                color="#28a745",
                width=2.5
            ];
            p3 [
                label="Phase 3: get_inputs",
                fillcolor="#e6f4ea",
                color="#28a745",
                width=2.5
            ];
            p4 [
                label="Phase 4: license_includes",
                fillcolor="#e6f4ea",
                color="#28a745",
                width=2.5
            ];
            p5 [
                label="Phase 5: make_experiments",
                fillcolor="#e6f4ea",
                color="#28a745",
                width=2.5
            ];

            p1 -> p2 -> p3 -> p4 -> p5 [color="#28a745", penwidth=2.0, weight=10];
        }

        // Horizontal rank alignment between Classes and Phases
        { rank=same; mod; p1; }
        { rank=same; pm; p2; }
        { rank=same; app; p3; }

        // Classes --> Phases
        mod -> p1 [
            label=<<i>register_phase('bootstrap_utilities')</i>>,
            color="#0056b3"
        ];
        pm  -> p2 [
            label=<<i>register_phase('software_create_env')</i>>,
            color="#0056b3"
        ];
        app -> p3 [
            label=<<i>register_phase('get_inputs')</i>>,
            color="#0056b3"
        ];
        app:se -> p4:w [
            label=<<i>register_phase('license_includes')</i>>,
            color="#0056b3"
        ];
        app:s -> p5:w [
            label=<<i>register_phase('make_experiments')</i>>,
            color="#0056b3"
        ];
    }

.. _standard-pipelines:

Standard Pipelines
==================

Setup Pipeline
--------------

* **CLI Command**: :ref:`ramble workspace setup <ramble-workspace-setup>`
* **Class**: :py:class:`ramble.pipeline.SetupPipeline`

The setup pipeline prepares everything required to execute experiments:

.. graphviz::

    digraph setup_pipeline {
        fontsize=12;
        rankdir=TB;
        nodesep=0.3;
        ranksep=0.4;

        node [
            shape=box,
            style="filled,rounded",
            fontsize=11,
            margin="0.25,0.12",
            fillcolor="#d4edda",
            color="#28a745",
            width=3.5
        ];
        edge [fontsize=10, color="#28a745", penwidth=1.3];

        s1 [label="bootstrap_utilities\n(Fetch tool dependencies)"];
        s2 [label="software_create_env / software_install\n(Concretize & install via Package Manager)"];
        s3 [label="get_inputs\n(Download workload datasets)"];
        s4 [label="license_includes\n(Inject license variables)"];
        s5 [label="make_experiments\n(Render execute_experiment scripts)"];

        s1 -> s2 -> s3 -> s4 -> s5;
    }

Execute Pipeline
----------------

* **CLI Command**: :ref:`ramble on <ramble-on>`
* **Class**: :py:class:`ramble.pipeline.ExecutePipeline`

Unlike setup or analysis, base application definitions do not register built-in default execution
phases because experiment execution centers on evaluating the ``{batch_submit}`` executor command.
However, custom execution phases registered via ``register_phase(..., pipeline="execute")``
(e.g., by modifiers or specialized applications) are processed first by the
:py:class:`~ramble.graphs.PhaseGraph`:

.. graphviz::

    digraph execute_pipeline {
        fontsize=12;
        rankdir=TB;
        nodesep=0.3;
        ranksep=0.4;

        node [
            shape=box,
            style="filled,rounded",
            fontsize=11,
            margin="0.25,0.12",
            fillcolor="#cce5ff",
            color="#004085",
            width=3.5
        ];
        edge [fontsize=10, color="#004085", penwidth=1.3];

        e1 [label="Custom Registered Phases\n(Optional register_phase(..., pipeline='execute'))"];
        e2 [label="Expand Executor Command\n(Evaluate {batch_submit})"];
        e3 [label="Submit / Launch Experiments\n(Invoke sbatch, mpirun, or local shell)"];

        e1 -> e2 -> e3;
    }

* **Batch Scheduler Integration**: :doc:`Workflow Managers <../workflow_managers>` (e.g., Slurm, PBS,
  Google Batch) expand the ``{batch_submit}`` executor command to submit batch scripts to the
  workload manager or execute scripts locally.

Analyze Pipeline
----------------

* **CLI Command**: :ref:`ramble workspace analyze <ramble-workspace-analyze>`
* **Class**: :py:class:`ramble.pipeline.AnalyzePipeline`

The analyze pipeline evaluates completed experiments, extracts metrics, and writes results using
registered phases:

.. graphviz::

    digraph analyze_pipeline {
        fontsize=12;
        rankdir=TB;
        nodesep=0.3;
        ranksep=0.4;

        node [
            shape=box,
            style="filled,rounded",
            fontsize=11,
            margin="0.25,0.12",
            fillcolor="#ffe8cc",
            color="#d9480f",
            width=3.5
        ];
        edge [fontsize=10, color="#d9480f", penwidth=1.3];

        a1 [label="prepare_analysis\n(Pre-processing hook for output logs)"];
        a2 [label="analyze_experiments\n(Extract FOMs & evaluate success_criteria)"];
        a3 [label="write_status & append_results_to_workspace\n(Persist ramble_status.json & workspace results)"];
        a4 [label="write_results_cache\n(Dump results text/YAML/JSON & upload if requested)"];

        a1 -> a2 -> a3 -> a4;
    }

Archive Pipeline
----------------

* **CLI Command**: :ref:`ramble workspace archive <ramble-workspace-archive>`
* **Class**: :py:class:`ramble.pipeline.ArchivePipeline`

The archive pipeline preserves experiment artifacts using its registered phase followed by
optional archive creation:

.. graphviz::

    digraph archive_pipeline {
        fontsize=12;
        rankdir=TB;
        nodesep=0.3;
        ranksep=0.4;

        node [
            shape=box,
            style="filled,rounded",
            fontsize=11,
            margin="0.25,0.12",
            fillcolor="#eebefa",
            color="#862e9c",
            width=3.5
        ];
        edge [fontsize=10, color="#862e9c", penwidth=1.3];

        ar1 [label="archive_experiments\n(Registered Phase: collect logs, templates & FOM files)"];
        ar2 [label="create_tarball / upload_archive\n(Generate archive.latest.tar.gz & upload)"];

        ar1 -> ar2;
    }

Standard Pipeline Phases
-------------------------

The following table summarizes the standard built-in phases registered across Ramble's primary
pipelines:

.. list-table::
   :widths: 22 15 20 43
   :header-rows: 1

   * - Phase Name
     - Pipeline
     - Owner / Source
     - Description & Purpose
   * - ``bootstrap_utilities``
     - Setup
     - Application Base
     - Downloads or builds external tool dependencies required for script rendering and experiment
       processing.
   * - ``software_create_env``
     - Setup
     - Package Manager
     - Creates software environment definitions (e.g., Spack environments) and concretizes
       package specs.
   * - ``software_install``
     - Setup
     - Package Manager
     - Installs required software packages, compilers, and dependencies into the target software
       stack.
   * - ``get_inputs``
     - Setup
     - Application Base
     - Downloads, verifies checksums, and extracts workload input datasets into workspace
       directories.
   * - ``license_includes``
     - Setup
     - Application Base
     - Resolves license environment variables and paths for commercial or proprietary software.
   * - ``make_experiments``
     - Setup
     - Application Base
     - Expands variables, renders templates, creates ``execute_experiment`` scripts, and writes the
       ``all_experiments`` submission script.
   * - ``prepare_analysis``
     - Analyze
     - Application Base
     - Application-specific pre-processing hook executed prior to FOM extraction.
   * - ``analyze_experiments``
     - Analyze
     - Application Base
     - Parses log files using regular expressions defined by Figures of Merit (FOMs) and evaluates
       ``success_criteria``.
   * - ``calculate_statistics``
     - Analyze
     - Pipeline Engine
     - Computes summary statistics (mean, stddev, min, max) for repeated experiment runs.
   * - ``archive_experiments``
     - Archive
     - Application Base
     - Copies logs, rendered templates, FOM output files, and inventory metadata into the workspace
       archive directory.

.. _additional-pipelines:

Additional Pipelines
====================

Ramble provides several additional pipelines for specialized workflow operations:

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
