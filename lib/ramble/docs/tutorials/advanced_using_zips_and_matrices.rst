.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _zips_and_matrices_tutorial:

========================
Using Zips and Matrices
========================

.. raw:: html

   <div class="tn-app-switcher" data-recipe="zips_matrices"></div>

In this tutorial, you will learn how to generate structured sets of experiments
using zips and matrices. You will explore how to group correlated variables together
using zips to avoid combinatorial explosion, and how to combine zips with matrices
to explore multi-dimensional parameter spaces.

This tutorial builds on concepts introduced in previous tutorials. Please make
sure you review :ref:`vector_and_matrix_tutorial` and :ref:`configuring_a_scaling_study_tutorial`
before starting.

.. contents:: Table of Contents
   :depth: 2
   :local:

.. note::

   In this tutorial, you will encounter expected validation errors when walking
   through intermediate steps. This illustrates common configuration pitfalls
   and how Ramble guides you to resolve them.

Creating the Workspace
----------------------

.. container:: tn-workspace-create

   First, create and activate a new workspace for this tutorial:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace create zips_wrf
          $ ramble workspace activate zips_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace create zips_gromacs
          $ ramble workspace activate zips_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace create zips_hpl
          $ ramble workspace activate zips_hpl

Configure the workspace-level variables:

.. code-block:: console

    $ ramble config add 'variables:n_ranks:"{processes_per_node}*{n_nodes}"'
    $ ramble config add "variables:mpi_command:mpirun -n {n_ranks}"
    $ ramble config add 'variables:batch_submit:"{execute_experiment}"'

Constructing a Platforms Zip
----------------------------

Zips are explicit groupings of vector variables that are stepped through in lockstep.
A zip is defined by a list of variable names, where each variable is a list/vector
of identical length.

For example, imagine you want to test multiple hardware platform configurations
where each platform has a distinct core count or process density:

.. code-block:: YAML

    variables:
      platform: ['platform1', 'platform2', 'platform3']
      processes_per_node: ['16', '18', '20']
    zips:
      platform_config:
      - platform
      - processes_per_node

With this definition, ``platform_config`` represents a list of length 3:

* Index 0: ``(platform1, 16)``
* Index 1: ``(platform2, 18)``
* Index 2: ``(platform3, 20)``

This allows grouping correlated variables together into a single logical entity.

You can add these definitions to your workspace configuration using ``ramble config add``:

.. code-block:: console

    $ ramble config add 'variables:platform:[platform1, platform2, platform3]'
    $ ramble config add 'variables:processes_per_node:[16, 18, 20]'
    $ ramble config add 'zips:platform_config:[platform, processes_per_node]'

.. note::
   These zips can alternatively be constructed by providing ``platform`` and
   ``system`` object definitions. Here they are simply used as a concrete
   example of something you would want to group together.

Unconsumed Zips and Vectors
---------------------------

Now suppose you define an experiment that scales across node counts:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: YAML

       applications:
         wrf:
           workloads:
             CONUS_12km:
               experiments:
                 scaling_{n_nodes}:
                   variables:
                     n_nodes: [1, 2]

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: YAML

       applications:
         gromacs:
           workloads:
             water_bare:
               experiments:
                 scaling_{n_nodes}:
                   variables:
                     n_nodes: [1, 2]

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: YAML

       applications:
         hpl:
           workloads:
             calculator:
               experiments:
                 scaling_{n_nodes}:
                   variables:
                     n_nodes: [1, 2]
                     memory_per_node: 8

At this stage, ``platform_config`` has length 3 and ``n_nodes`` has length 2.
Because neither is consumed by a matrix, Ramble attempts to zip all unconsumed
vectors together. Running:

.. code-block:: console

    $ ramble workspace info

Produces a length mismatch error:

.. code-block:: console

    ==> Error: Length mismatch in vector variables in experiment scaling_{n_nodes}
        Variable n_nodes has length 2
        Variable platform has length 3
        Variable processes_per_node has length 3

Defining an Experiment Matrix
-----------------------------

To resolve the length mismatch and test both node counts on all three platforms,
define an experiment matrix. A matrix computes the Cartesian product of its entries.

Adding the matrix:

.. code-block:: YAML

    matrix:
    - platform_config
    - n_nodes

This tells Ramble to cross each element of ``platform_config`` with each element
of ``n_nodes``, producing 3 * 2 = 6 experiments.

However, if the experiment name template remains ``scaling_{n_nodes}``, running:

.. code-block:: console

    $ ramble workspace info

Will produce a collision error because the experiment name is not unique across
platforms:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       ==> Warning: Two experiments are defined with the name wrf.CONUS_12km.scaling_1
       ==> Warning: Variable differences between experiment definitions:
       ==> Warning:   - processes_per_node: {'previous': 16, 'new': 18}
       ==> Warning:   - platform: {'previous': 'platform1', 'new': 'platform2'}
       ==> Error: Experiment wrf.CONUS_12km.scaling_1 is not unique.

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       ==> Warning: Two experiments are defined with the name gromacs.water_bare.scaling_1
       ==> Warning: Variable differences between experiment definitions:
       ==> Warning:   - processes_per_node: {'previous': 16, 'new': 18}
       ==> Warning:   - platform: {'previous': 'platform1', 'new': 'platform2'}
       ==> Error: Experiment gromacs.water_bare.scaling_1 is not unique.

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       ==> Warning: Two experiments are defined with the name hpl.calculator.scaling_1
       ==> Warning: Variable differences between experiment definitions:
       ==> Warning:   - processes_per_node: {'previous': 16, 'new': 18}
       ==> Warning:   - platform: {'previous': 'platform1', 'new': 'platform2'}
       ==> Error: Experiment hpl.calculator.scaling_1 is not unique.

Making Experiment Names Unique
------------------------------

To ensure every generated experiment has a unique name, incorporate ``{platform}``
into the experiment name template: ``scaling_{n_nodes}_{platform}``.

Complete Workspace Setup Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The full set of commands to construct this workspace:

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/zips_matrices_wrf_commands.sh
      :language: console

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/zips_matrices_gromacs_commands.sh
      :language: console

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/zips_matrices_hpl_commands.sh
      :language: console

Final Workspace Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The resulting ``configs/ramble.yaml`` file contains the following:

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/zips_matrices_wrf_ramble.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/zips_matrices_gromacs_ramble.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/zips_matrices_hpl_ramble.yaml
      :language: YAML

Inspecting Generated Experiments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With the unique naming template and matrix defined, ``ramble workspace info``
successfully expands all 6 experiments:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       $ ramble workspace info
       Workspace: zips_wrf

       Experiments:
         Application: wrf
           Workload: CONUS_12km
             Experiment 1: wrf.CONUS_12km.scaling_1_platform1
             Experiment 2: wrf.CONUS_12km.scaling_2_platform1
             Experiment 3: wrf.CONUS_12km.scaling_1_platform2
             Experiment 4: wrf.CONUS_12km.scaling_2_platform2
             Experiment 5: wrf.CONUS_12km.scaling_1_platform3
             Experiment 6: wrf.CONUS_12km.scaling_2_platform3

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       $ ramble workspace info
       Workspace: zips_gromacs

       Experiments:
         Application: gromacs
           Workload: water_bare
             Experiment 1: gromacs.water_bare.scaling_1_platform1
             Experiment 2: gromacs.water_bare.scaling_2_platform1
             Experiment 3: gromacs.water_bare.scaling_1_platform2
             Experiment 4: gromacs.water_bare.scaling_2_platform2
             Experiment 5: gromacs.water_bare.scaling_1_platform3
             Experiment 6: gromacs.water_bare.scaling_2_platform3

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       $ ramble workspace info
       Workspace: zips_hpl

       Experiments:
         Application: hpl
           Workload: calculator
             Experiment 1: hpl.calculator.scaling_1_platform1
             Experiment 2: hpl.calculator.scaling_2_platform1
             Experiment 3: hpl.calculator.scaling_1_platform2
             Experiment 4: hpl.calculator.scaling_2_platform2
             Experiment 5: hpl.calculator.scaling_1_platform3
             Experiment 6: hpl.calculator.scaling_2_platform3

Executing Experiments
---------------------

.. container:: tn-full-run-only

   .. note::
      This workspace uses the ``spack`` package manager to build the software stack
      and MPI implementation. ``spack`` can either be installed in your ``PATH``, or
      Ramble will automatically bootstrap it for you.

   .. note::
      When not running in dry-run mode, ``ramble workspace setup`` may take a long
      time if the required software stack is not already installed on your system,
      and ``ramble on`` will execute all 6 scaling experiments across the platform
      zips and node counts, which can take a substantial amount of time. To skip
      software installation and execution, you can enable **Dry-Run Mode** in the
      configuration card at the top of this page to use
      ``ramble workspace setup --dry-run`` instead.

   To set up, execute, and analyze the experiments:

   .. code-block:: console

       $ ramble workspace setup
       $ ramble on
       $ ramble workspace analyze

   .. rubric:: Filtering Experiments

   When running larger parameter sweeps, you can use the ``--where`` filter option
   to execute only a subset of the generated experiments:

   .. code-block:: console

       $ ramble workspace setup --where '{n_ranks} >= 20'
       $ ramble on --where '{n_ranks} >= 20'
       $ ramble workspace analyze --where '{n_ranks} >= 20'

   You can also export analysis results in structured JSON or YAML formats:

   .. code-block:: console

       $ ramble workspace analyze --formats yaml json

   .. rubric:: Extracted Figures of Merit

   The extracted figures of merit will be written to ``results.latest.txt``:

.. container:: tn-dry-run-only

   Since **Dry-Run Mode** is enabled, we will set up the workspace using ``--dry-run``
   so that Ramble generates all experiment directories and execution scripts without
   installing software or running ``ramble on``:

   .. code-block:: console

       $ ramble workspace setup --dry-run

   You can also combine ``--dry-run`` with the ``--where`` filter option to set up
   only a subset of the generated experiments:

   .. code-block:: console

       $ ramble workspace setup --dry-run --where '{n_ranks} >= 20'

   .. rubric:: Exploring the Experiment Directories

   Instead of executing the experiments with ``ramble on`` and analyzing them with
   ``ramble workspace analyze``, explore the generated experiment directories and
   rendered ``execute_experiment`` scripts to see how each zipped platform and node
   count combination was expanded:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ls -la $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/wrf/CONUS_12km/
          $ cat $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/wrf/CONUS_12km/scaling_1_platform1/execute_experiment

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ls -la $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/gromacs/water_bare/
          $ cat $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/gromacs/water_bare/scaling_1_platform1/execute_experiment

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ls -la $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/hpl/calculator/
          $ cat $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/hpl/calculator/scaling_1_platform1/execute_experiment

   .. rubric:: Example Analysis Output (Reference Only)

   In Dry-Run Mode, experiments are not executed or analyzed. If you were to execute
   and analyze these experiments in a full run, the following figures of merit would
   be extracted into ``results.latest.txt``:

.. container:: tn-app-variant tn-app-wrf

   * **Average Timestep Time**: Time (in seconds) on average each timestep takes
   * **Cumulative Timestep Time**: Time (in seconds) spent executing all timesteps
   * **Minimum Timestep Time**: Minimum time (in seconds) spent on any one timestep
   * **Maximum Timestep Time**: Maximum time (in seconds) spent on any one timestep
   * **Number of timesteps**: Count of total timesteps performed

.. container:: tn-app-variant tn-app-gromacs

   * **Core Time**: CPU time (in seconds) spent on benchmark calculations
   * **Wall Time**: Elapsed real time (in seconds) spent on benchmark calculations
   * **Nanosecs per day**: Simulation speed achieved
   * **Hours per nanosec**: Hours required to calculate 1 nanosecond of simulation

.. container:: tn-app-variant tn-app-hpl

   * **Time**: Time (in seconds) spent executing the benchmark calculation
   * **GFlops**: Performance in GFLOP/s achieved


Cleaning the Workspace
----------------------

.. container:: tn-workspace-cleanup

   Once you have completed this tutorial, deactivate and optionally remove the workspace:

   .. code-block:: console

       $ ramble workspace deactivate

   To delete the workspace:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace remove zips_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace remove zips_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace remove zips_hpl
