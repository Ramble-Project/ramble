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

.. tutorial-header:: zips_matrices

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

.. tutorial-workspace-create:: zips

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

.. tutorial-app-template::
   :wrf: extra_var=
   :gromacs: extra_var=
   :hpl: extra_var=memory_per_node: 8

   .. code-block:: YAML

       applications:
         {app}:
           workloads:
             {workload}:
               experiments:
                 scaling_{n_nodes}:
                   variables:
                     n_nodes: [1, 2]
                     {extra_var}

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

.. tutorial-app-template::

   .. code-block:: console

       ==> Warning: Two experiments are defined with the name {app}.{workload}.scaling_1
       ==> Warning: Variable differences between experiment definitions:
       ==> Warning:   - processes_per_node: {'previous': 16, 'new': 18}
       ==> Warning:   - platform: {'previous': 'platform1', 'new': 'platform2'}
       ==> Error: Experiment {app}.{workload}.scaling_1 is not unique.

Making Experiment Names Unique
------------------------------

To ensure every generated experiment has a unique name, incorporate ``{platform}``
into the experiment name template: ``scaling_{n_nodes}_{platform}``.

Complete Workspace Setup Commands
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The full set of commands to construct this workspace:

.. tutorial-snippet:: zips_matrices commands.sh

Final Workspace Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The resulting ``configs/ramble.yaml`` file contains the following:

.. tutorial-snippet:: zips_matrices ramble.yaml

Inspecting Generated Experiments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

With the unique naming template and matrix defined, ``ramble workspace info``
successfully expands all 6 experiments:

.. tutorial-app-template::

   .. code-block:: console

       $ ramble workspace info
       Workspace: zips_{app}

       Experiments:
         Application: {app}
           Workload: {workload}
             Experiment 1: {app}.{workload}.scaling_1_platform1
             Experiment 2: {app}.{workload}.scaling_2_platform1
             Experiment 3: {app}.{workload}.scaling_1_platform2
             Experiment 4: {app}.{workload}.scaling_2_platform2
             Experiment 5: {app}.{workload}.scaling_1_platform3
             Experiment 6: {app}.{workload}.scaling_2_platform3

Executing Experiments
---------------------

.. tutorial-execute:: zips
   :dry-run-cmds: ls -la $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/{app}/{workload}/; cat $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/{app}/{workload}/scaling_1_platform1/execute_experiment
   :include-foms:

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


Cleaning the Workspace
----------------------

.. tutorial-workspace-cleanup:: zips
