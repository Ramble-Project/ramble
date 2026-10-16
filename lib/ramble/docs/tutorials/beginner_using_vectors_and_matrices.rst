.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _vector_and_matrix_tutorial:

==========================
Using Vectors and Matrices
==========================

In this tutorial, you will learn how to utilize vectors and matrices in Ramble
workspaces. Ramble's vector and matrix variable logic is defined in more detail in
:ref:`ramble-vector-logic` and :ref:`ramble-matrix-logic`.

This tutorial supports multiple applications (such as WRF, GROMACS, and HPL); you can
select your preferred application below.

.. raw:: html

   <div class="tn-app-switcher" data-recipe="vectors_matrices"></div>

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

.. note::
   In this tutorial, you will encounter expected errors when copying and
   pasting the commands. This is to help show situations you might run into when
   trying to use Ramble on your own, and illustrate how you might fix them.

Create and Activate a Workspace
-------------------------------

.. container:: tn-workspace-create

   Before configuring experiments with vectors and matrices, set up a new workspace:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace create vectors_wrf
          $ ramble workspace activate vectors_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace create vectors_gromacs
          $ ramble workspace activate vectors_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace create vectors_hpl
          $ ramble workspace activate vectors_hpl

Configure Initial Experiments
-----------------------------

To understand why vectors and matrices are useful, we first start with a configuration
that defines several similar experiments explicitly.

Define system-level variables (such as ``processes_per_node``, ``mpi_command``, and ``batch_submit``)
at the workspace level:

.. code-block:: console

    $ ramble config add variables:processes_per_node:16
    $ ramble config add 'variables:mpi_command:mpirun -n {n_ranks} -ppn {processes_per_node}'
    $ ramble config add 'variables:batch_submit:"{execute_experiment}"'

Next, configure the initial experiments:

.. container:: tn-app-variant tn-app-wrf

   For WRF, we configure two workloads (``CONUS_12km`` and ``CONUS_2p5km``), each with two
   experiments exploring different values of the ``num_tiles`` parameter (``tile_1`` and ``tile_2``, with ``-V wrf_tiles=true`` enabled):

   .. code-block:: console

       $ ramble workspace manage experiments wrf --workload-filter CONUS_12km -e tile_1 -V package_manager=spack -V wrf_tiles=true -v n_ranks=1 -v n_threads=1 -v num_tiles=1
       $ ramble workspace manage experiments wrf --workload-filter CONUS_12km -e tile_2 -V package_manager=spack -V wrf_tiles=true -v n_ranks=1 -v n_threads=1 -v num_tiles=2
       $ ramble workspace manage experiments wrf --workload-filter CONUS_2p5km -e tile_1 -V package_manager=spack -V wrf_tiles=true -v n_ranks=1 -v n_threads=1 -v num_tiles=1
       $ ramble workspace manage experiments wrf --workload-filter CONUS_2p5km -e tile_2 -V package_manager=spack -V wrf_tiles=true -v n_ranks=1 -v n_threads=1 -v num_tiles=2
       $ ramble workspace concretize

.. container:: tn-app-variant tn-app-gromacs

   For GROMACS, we configure two workloads (``water_bare`` and ``water_gmx50``), each with two
   experiments exploring different values of the ``type`` parameter (``pme_single_rank`` and ``rf_single_rank``):

   .. code-block:: console

       $ ramble workspace manage experiments gromacs --workload-filter water_bare -e pme_single_rank -V package_manager=spack -v n_ranks=1 -v n_threads=1 -v size=0003 -v type=pme
       $ ramble workspace manage experiments gromacs --workload-filter water_bare -e rf_single_rank -V package_manager=spack -v n_ranks=1 -v n_threads=1 -v size=0003 -v type=rf
       $ ramble workspace manage experiments gromacs --workload-filter water_gmx50 -e pme_single_rank -V package_manager=spack -v n_ranks=1 -v n_threads=1 -v size=0003 -v type=pme
       $ ramble workspace manage experiments gromacs --workload-filter water_gmx50 -e rf_single_rank -V package_manager=spack -v n_ranks=1 -v n_threads=1 -v size=0003 -v type=rf
       $ ramble workspace concretize

.. container:: tn-app-variant tn-app-hpl

   For HPL, we configure two workloads (``calculator`` and ``standard``), each with two
   experiments exploring different values of the ``PFACTs`` parameter (``pfact_0`` and ``pfact_1``):

   .. code-block:: console

       $ ramble workspace manage experiments hpl --workload-filter calculator -e pfact_0 -V package_manager=spack -v n_ranks=1 -v n_threads=1 -v memory_per_node=8 -v PFACTs=0
       $ ramble workspace manage experiments hpl --workload-filter calculator -e pfact_1 -V package_manager=spack -v n_ranks=1 -v n_threads=1 -v memory_per_node=8 -v PFACTs=1
       $ ramble workspace manage experiments hpl --workload-filter standard -e pfact_0 -V package_manager=spack -v n_ranks=1 -v n_threads=1 -v memory_per_node=8 -v PFACTs=0
       $ ramble workspace manage experiments hpl --workload-filter standard -e pfact_1 -V package_manager=spack -v n_ranks=1 -v n_threads=1 -v memory_per_node=8 -v PFACTs=1
       $ ramble workspace concretize

Experiment Descriptions
-----------------------

Now that your workspace is active and configured, execute the following command to see what
experiments the workspace currently contains:

.. code-block:: console

    $ ramble workspace info

This command provides a summary view of the workspace:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       Experiments:
         Application: wrf
           Workload: CONUS_12km
             Experiment 1: wrf.CONUS_12km.tile_1
             Experiment 2: wrf.CONUS_12km.tile_2
         Application: wrf
           Workload: CONUS_2p5km
             Experiment 3: wrf.CONUS_2p5km.tile_1
             Experiment 4: wrf.CONUS_2p5km.tile_2

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       Experiments:
         Application: gromacs
           Workload: water_bare
             Experiment 1: gromacs.water_bare.pme_single_rank
             Experiment 2: gromacs.water_bare.rf_single_rank
         Application: gromacs
           Workload: water_gmx50
             Experiment 3: gromacs.water_gmx50.pme_single_rank
             Experiment 4: gromacs.water_gmx50.rf_single_rank

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       Experiments:
         Application: hpl
           Workload: calculator
             Experiment 1: hpl.calculator.pfact_0
             Experiment 2: hpl.calculator.pfact_1
         Application: hpl
           Workload: standard
             Experiment 3: hpl.standard.pfact_0
             Experiment 4: hpl.standard.pfact_1

To get detailed information about where variable definitions come from, you can use:

.. code-block:: console

    $ ramble workspace info --expansions

The experiments section of this command displays variables defined at the workspace scope
and at the experiment scope:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       Experiments:
         Application: wrf
           Workload: CONUS_12km
             Experiment 1: wrf.CONUS_12km.tile_1
               Variables from Workspace:
                 processes_per_node = 16 ==> 16
                 mpi_command = mpirun -n {n_ranks} -ppn {processes_per_node} ==> mpirun -n 1 -ppn 16
                 batch_submit = {execute_experiment} ==> {execute_experiment}
               Variables from Experiment:
                 n_ranks = 1 ==> 1
                 n_threads = 1 ==> 1
                 num_tiles = 1 ==> 1
             Experiment 2: wrf.CONUS_12km.tile_2
               Variables from Workspace:
                 processes_per_node = 16 ==> 16
                 mpi_command = mpirun -n {n_ranks} -ppn {processes_per_node} ==> mpirun -n 1 -ppn 16
                 batch_submit = {execute_experiment} ==> {execute_experiment}
               Variables from Experiment:
                 n_ranks = 1 ==> 1
                 n_threads = 1 ==> 1
                 num_tiles = 2 ==> 2

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       Experiments:
         Application: gromacs
           Workload: water_bare
             Experiment 1: gromacs.water_bare.pme_single_rank
               Variables from Workspace:
                 processes_per_node = 16 ==> 16
                 mpi_command = mpirun -n {n_ranks} -ppn {processes_per_node} ==> mpirun -n 1 -ppn 16
                 batch_submit = {execute_experiment} ==> {execute_experiment}
               Variables from Experiment:
                 n_ranks = 1 ==> 1
                 n_threads = 1 ==> 1
                 size = 0003 ==> 0003
                 type = pme ==> pme
             Experiment 2: gromacs.water_bare.rf_single_rank
               Variables from Workspace:
                 processes_per_node = 16 ==> 16
                 mpi_command = mpirun -n {n_ranks} -ppn {processes_per_node} ==> mpirun -n 1 -ppn 16
                 batch_submit = {execute_experiment} ==> {execute_experiment}
               Variables from Experiment:
                 n_ranks = 1 ==> 1
                 n_threads = 1 ==> 1
                 size = 0003 ==> 0003
                 type = rf ==> rf

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       Experiments:
         Application: hpl
           Workload: calculator
             Experiment 1: hpl.calculator.pfact_0
               Variables from Workspace:
                 processes_per_node = 16 ==> 16
                 mpi_command = mpirun -n {n_ranks} -ppn {processes_per_node} ==> mpirun -n 1 -ppn 16
                 batch_submit = {execute_experiment} ==> {execute_experiment}
               Variables from Experiment:
                 n_ranks = 1 ==> 1
                 n_threads = 1 ==> 1
                 memory_per_node = 8 ==> 8
                 PFACTs = 0 ==> 0
             Experiment 2: hpl.calculator.pfact_1
               Variables from Workspace:
                 processes_per_node = 16 ==> 16
                 mpi_command = mpirun -n {n_ranks} -ppn {processes_per_node} ==> mpirun -n 1 -ppn 16
                 batch_submit = {execute_experiment} ==> {execute_experiment}
               Variables from Experiment:
                 n_ranks = 1 ==> 1
                 n_threads = 1 ==> 1
                 memory_per_node = 8 ==> 8
                 PFACTs = 1 ==> 1

When examining the ``ramble.yaml`` file, notice how repetitive it is. Defining each
experiment explicitly works, but becomes verbose and tedious when configuring many similar experiments.
Next, we will collapse the experiments using vectors and matrices.

Editing Experiments
-------------------

To edit your workspace configuration file directly, use:

.. code-block:: console

    $ ramble workspace edit

Using Vector Variables
----------------------

Vector (or list) variables in Ramble are variables whose value is a list of
other values in the ``ramble.yaml`` workspace configuration file. Vectors allow
exploring ranges of parameters or scaling studies within a single experiment definition.

Currently, your workspace has 4 experiments defined across two workloads.
Collapse the experiment definitions using vectors:

.. container:: tn-app-variant tn-app-wrf

   For WRF, collapse the ``num_tiles`` values into a list (``['1', '2']``) within each workload:

   .. code-block:: YAML

       tile_1:
         variables:
           n_ranks: '1'
           n_threads: '1'
           num_tiles: ['1', '2']

.. container:: tn-app-variant tn-app-gromacs

   For GROMACS, collapse the ``type`` values into a list (``['pme', 'rf']``) within each workload:

   .. code-block:: YAML

       pme_single_rank:
         variables:
           n_ranks: '1'
           n_threads: '1'
           size: '0003'
           type: ['pme', 'rf']

.. container:: tn-app-variant tn-app-hpl

   For HPL, collapse the ``PFACTs`` values into a list (``['0', '1']``) within each workload:

   .. code-block:: YAML

       pfact_0:
         variables:
           n_ranks: '1'
           n_threads: '1'
           memory_per_node: '8'
           PFACTs: ['0', '1']

After updating your configuration, save and exit your ``ramble.yaml`` file, and execute:

.. code-block:: console

    $ ramble workspace info

Notice the error printed to the screen:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       ==> Warning: Two experiments are defined with the name wrf.CONUS_12km.tile_1
       ==> Warning: Variables unique to previously defined experiment:
       ==> Warning:   - experiment_index
       ==> Warning: Variable differences between experiment definitions:
       ==> Warning:   - num_tiles: {'previous': '1', 'new': '2'}
       ==> Error: Experiment wrf.CONUS_12km.tile_1 is not unique.

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       ==> Warning: Two experiments are defined with the name gromacs.water_gmx50.pme_single_rank
       ==> Warning: Variables unique to previously defined experiment:
       ==> Warning:   - experiment_index
       ==> Warning: Variable differences between experiment definitions:
       ==> Warning:   - type: {'previous': 'pme', 'new': 'rf'}
       ==> Error: Experiment gromacs.water_gmx50.pme_single_rank is not unique.

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       ==> Warning: Two experiments are defined with the name hpl.calculator.pfact_0
       ==> Warning: Variables unique to previously defined experiment:
       ==> Warning:   - experiment_index
       ==> Warning: Variable differences between experiment definitions:
       ==> Warning:   - PFACTs: {'previous': '0', 'new': '1'}
       ==> Error: Experiment hpl.calculator.pfact_0 is not unique.

Within Ramble, each experiment is required to have a unique namespace:

.. code-block:: console

    <application name>.<workload name>.<rendered experiment name>

Changing the application or workload automatically creates a unique namespace, but
changing vector variables within an experiment does not automatically generate a unique name.
Both experiments end up with the same rendered experiment name.

Templatized Experiment Names
----------------------------

In order to generate unique experiment namespaces while using vector variable
definitions, Ramble allows experiment names to be templatized using variable names
as expansion placeholders.

Modify the experiment name to include the vector variable:

.. container:: tn-app-variant tn-app-wrf

   Change the experiment name from ``tile_1`` to ``'tile_{num_tiles}'``:

   .. code-block:: YAML

       'tile_{num_tiles}':
         variables:
           n_ranks: '1'
           n_threads: '1'
           num_tiles: ['1', '2']

.. container:: tn-app-variant tn-app-gromacs

   Change the experiment name from ``pme_single_rank`` to ``'{type}_single_rank'``:

   .. code-block:: YAML

       '{type}_single_rank':
         variables:
           n_ranks: '1'
           n_threads: '1'
           size: '0003'
           type: ['pme', 'rf']

.. container:: tn-app-variant tn-app-hpl

   Change the experiment name from ``pfact_0`` to ``'pfact_{PFACTs}'``:

   .. code-block:: YAML

       'pfact_{PFACTs}':
         variables:
           n_ranks: '1'
           n_threads: '1'
           memory_per_node: '8'
           PFACTs: ['0', '1']

.. note::
   In YAML, experiment names starting with ``{`` must be wrapped in quotes
   so the parser does not treat them as inline mappings/dictionaries.

Now, verify the resulting experiments using:

.. code-block:: console

    $ ramble workspace info

Ramble now generates four unique experiments:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       Experiments:
         Application: wrf
           Workload: CONUS_12km
             Experiment 1: wrf.CONUS_12km.tile_1
             Experiment 2: wrf.CONUS_12km.tile_2
           Workload: CONUS_2p5km
             Experiment 3: wrf.CONUS_2p5km.tile_1
             Experiment 4: wrf.CONUS_2p5km.tile_2

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       Experiments:
         Application: gromacs
           Workload: water_bare
             Experiment 1: gromacs.water_bare.pme_single_rank
             Experiment 2: gromacs.water_bare.rf_single_rank
           Workload: water_gmx50
             Experiment 3: gromacs.water_gmx50.pme_single_rank
             Experiment 4: gromacs.water_gmx50.rf_single_rank

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       Experiments:
         Application: hpl
           Workload: calculator
             Experiment 1: hpl.calculator.pfact_0
             Experiment 2: hpl.calculator.pfact_1
           Workload: standard
             Experiment 3: hpl.standard.pfact_0
             Experiment 4: hpl.standard.pfact_1

Vectorizing Workload Names
--------------------------

Next, we can simplify the configuration further by vectorizing across workloads.

Define a new variable named ``app_workload`` within one experiment, delete the second workload
definition entirely, and templatize the workload name using ``'{app_workload}'``:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: YAML

       workloads:
         '{app_workload}':
           experiments:
             'tile_{num_tiles}':
               variables:
                 app_workload: ['CONUS_12km', 'CONUS_2p5km']
                 n_ranks: '1'
                 n_threads: '1'
                 num_tiles: ['1', '2']

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: YAML

       workloads:
         '{app_workload}':
           experiments:
             '{type}_single_rank':
               variables:
                 app_workload: ['water_bare', 'water_gmx50']
                 n_ranks: '1'
                 n_threads: '1'
                 size: '0003'
                 type: ['pme', 'rf']

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: YAML

       workloads:
         '{app_workload}':
           experiments:
             'pfact_{PFACTs}':
               variables:
                 app_workload: ['calculator', 'standard']
                 n_ranks: '1'
                 n_threads: '1'
                 memory_per_node: '8'
                 PFACTs: ['0', '1']

Save and exit, then run:

.. code-block:: console

    $ ramble workspace info

Notice that Ramble now reports only **two** experiments instead of the four we expected:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       Experiments:
         Application: wrf
           Workload: {app_workload}
             Experiment 1: wrf.CONUS_12km.tile_1
             Experiment 2: wrf.CONUS_2p5km.tile_2

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       Experiments:
         Application: gromacs
           Workload: {app_workload}
             Experiment 1: gromacs.water_bare.pme_single_rank
             Experiment 2: gromacs.water_gmx50.rf_single_rank

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       Experiments:
         Application: hpl
           Workload: {app_workload}
             Experiment 1: hpl.calculator.pfact_0
             Experiment 2: hpl.standard.pfact_1

This happens because multiple unconstrained vector variables are **implicitly zipped** together.
Since both vectors have length 2, Ramble pairs element 1 with element 1, and element 2 with element 2:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       [ (CONUS_12km, tile 1), (CONUS_2p5km, tile 2) ]

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       [ (water_bare, pme), (water_gmx50, rf) ]

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       [ (calculator, pfact 0), (standard, pfact 1) ]

To generate the full cross-product of workloads and parameters, we use variable **matrices**.

Variable Matrices
-----------------

When you want an explicit Cartesian product of parameter lists, define a ``matrix:`` block
within the experiment scope. Variables listed in a matrix are consumed by the matrix and
crossed with each other.

Update your experiment definition to include a ``matrix:`` block:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: YAML

       workloads:
         '{app_workload}':
           experiments:
             'tile_{num_tiles}':
               variables:
                 app_workload: ['CONUS_12km', 'CONUS_2p5km']
                 n_ranks: '1'
                 n_threads: '1'
                 num_tiles: ['1', '2']
               matrix:
               - app_workload
               - num_tiles

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: YAML

       workloads:
         '{app_workload}':
           experiments:
             '{type}_single_rank':
               variables:
                 app_workload: ['water_bare', 'water_gmx50']
                 n_ranks: '1'
                 n_threads: '1'
                 size: '0003'
                 type: ['pme', 'rf']
               matrix:
               - app_workload
               - type

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: YAML

       workloads:
         '{app_workload}':
           experiments:
             'pfact_{PFACTs}':
               variables:
                 app_workload: ['calculator', 'standard']
                 n_ranks: '1'
                 n_threads: '1'
                 memory_per_node: '8'
                 PFACTs: ['0', '1']
               matrix:
               - app_workload
               - PFACTs

Save the file and execute:

.. code-block:: console

    $ ramble workspace info

Ramble now generates all four combinations:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       Experiments:
         Application: wrf
           Workload: {app_workload}
             Experiment 1: wrf.CONUS_12km.tile_1
             Experiment 2: wrf.CONUS_12km.tile_2
             Experiment 3: wrf.CONUS_2p5km.tile_1
             Experiment 4: wrf.CONUS_2p5km.tile_2

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       Experiments:
         Application: gromacs
           Workload: {app_workload}
             Experiment 1: gromacs.water_bare.pme_single_rank
             Experiment 2: gromacs.water_bare.rf_single_rank
             Experiment 3: gromacs.water_gmx50.pme_single_rank
             Experiment 4: gromacs.water_gmx50.rf_single_rank

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       Experiments:
         Application: hpl
           Workload: {app_workload}
             Experiment 1: hpl.calculator.pfact_0
             Experiment 2: hpl.calculator.pfact_1
             Experiment 3: hpl.standard.pfact_0
             Experiment 4: hpl.standard.pfact_1

Defining a Scaling Study
------------------------

Finally, we can extend this experiment definition to perform a rank-based scaling study by
vectorizing ``n_ranks: ['1', '2']`` and adding ``n_ranks`` to the matrix definition.

You can configure this scaling matrix directly using the ``ramble workspace manage experiments`` command:

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/vectors_matrices_wrf_commands.sh
      :language: console

   The resulting ``configs/ramble.yaml`` will look like:

   .. literalinclude:: ../_generated/snippets/vectors_matrices_wrf_ramble.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/vectors_matrices_gromacs_commands.sh
      :language: console

   The resulting ``configs/ramble.yaml`` will look like:

   .. literalinclude:: ../_generated/snippets/vectors_matrices_gromacs_ramble.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/vectors_matrices_hpl_commands.sh
      :language: console

   The resulting ``configs/ramble.yaml`` will look like:

   .. literalinclude:: ../_generated/snippets/vectors_matrices_hpl_ramble.yaml
      :language: YAML

Check the final list of generated experiments:

.. code-block:: console

    $ ramble workspace info

Ramble will display all 8 generated experiments:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       Experiments:
         Application: wrf
           Workload: {app_workload}
             Experiment 1: wrf.CONUS_12km.tile_1_1ranks
             Experiment 2: wrf.CONUS_12km.tile_1_2ranks
             Experiment 3: wrf.CONUS_12km.tile_2_1ranks
             Experiment 4: wrf.CONUS_12km.tile_2_2ranks
             Experiment 5: wrf.CONUS_2p5km.tile_1_1ranks
             Experiment 6: wrf.CONUS_2p5km.tile_1_2ranks
             Experiment 7: wrf.CONUS_2p5km.tile_2_1ranks
             Experiment 8: wrf.CONUS_2p5km.tile_2_2ranks

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       Experiments:
         Application: gromacs
           Workload: {app_workload}
             Experiment 1: gromacs.water_bare.pme_1ranks
             Experiment 2: gromacs.water_bare.pme_2ranks
             Experiment 3: gromacs.water_bare.rf_1ranks
             Experiment 4: gromacs.water_bare.rf_2ranks
             Experiment 5: gromacs.water_gmx50.pme_1ranks
             Experiment 6: gromacs.water_gmx50.pme_2ranks
             Experiment 7: gromacs.water_gmx50.rf_1ranks
             Experiment 8: gromacs.water_gmx50.rf_2ranks

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       Experiments:
         Application: hpl
           Workload: {app_workload}
             Experiment 1: hpl.calculator.pfact_0_1ranks
             Experiment 2: hpl.calculator.pfact_0_2ranks
             Experiment 3: hpl.calculator.pfact_1_1ranks
             Experiment 4: hpl.calculator.pfact_1_2ranks
             Experiment 5: hpl.standard.pfact_0_1ranks
             Experiment 6: hpl.standard.pfact_0_2ranks
             Experiment 7: hpl.standard.pfact_1_1ranks
             Experiment 8: hpl.standard.pfact_1_2ranks

Executing Experiments
---------------------

.. container:: tn-full-run-only

   .. note::
      By default, the experiments in this tutorial use `Spack <https://spack.io/>`_
      (configured via ``package_manager: spack``) to build and install the required
      software stack. ``spack`` can either be installed in your ``PATH``, or Ramble
      will automatically bootstrap it for you.

   .. note::
      When not running in dry-run mode, both setup and execution may take a
      substantial amount of time:

      * ``ramble workspace setup`` will build the software stack if it is not
        already installed on your system, and download input files for multiple
        workloads (including larger datasets such as WRF's ``CONUS_2p5km`` and
        GROMACS's ``water_gmx50``).
      * ``ramble on`` executes all 8 experiments in the matrix sequentially—including
        the larger workloads and multi-rank configurations—which can take a long
        time to complete.

      You can enable **Dry-Run Mode** at the top of this tutorial (or
      pass ``--dry-run`` to setup) to quickly generate and inspect the experiment
      directories without executing them.

   To fully set up, execute, and analyze the experiments, run:

   .. code-block:: console

       $ ramble workspace setup
       $ ramble on
       $ ramble workspace analyze

   Figures of merit will be written to the ``results`` file in the workspace directory:

.. container:: tn-dry-run-only

   With **Dry-Run Mode** enabled, perform a dry-run setup to generate the experiment
   directories across all vector and matrix combinations without building software or
   downloading inputs:

   .. code-block:: console

       $ ramble workspace setup --dry-run

   Because we are using dry-run mode, we do **not** run ``ramble on`` or
   ``ramble workspace analyze``. Instead, explore the generated experiment directories
   under the workspace's ``experiments/`` folder to see how Ramble expanded each matrix
   point into its own directory and ``execute_experiment`` script:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/vectors_wrf/experiments/wrf/
          $ cat $RAMBLE_ROOT/var/ramble/workspaces/vectors_wrf/experiments/wrf/CONUS_12km/CONUS_12km_1ranks/execute_experiment

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/vectors_gromacs/experiments/gromacs/
          $ cat $RAMBLE_ROOT/var/ramble/workspaces/vectors_gromacs/experiments/gromacs/water_bare/pme_0.0005_1ranks/execute_experiment

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/vectors_hpl/experiments/hpl/
          $ cat $RAMBLE_ROOT/var/ramble/workspaces/vectors_hpl/experiments/hpl/calculator/pfact_0_1ranks/execute_experiment

   **Example Output (Full Run):**

   In a full run where ``ramble on`` and ``ramble workspace analyze`` are executed,
   figures of merit are extracted for each experiment in the matrix and written to
   ``results.latest.txt`` in the workspace directory:

.. container:: tn-app-variant tn-app-wrf

   * Average Timestep Time: Time (in seconds) on average each timestep takes
   * Cumulative Timestep Time: Time (in seconds) spent executing all timesteps
   * Minimum Timestep Time: Minimum time (in seconds) spent on any one timestep
   * Maximum Timestep Time: Maximum time (in seconds) spent on any one timestep
   * Number of timesteps: Total count of timesteps performed

.. container:: tn-app-variant tn-app-gromacs

   * Core Time: CPU time (in seconds) spent on benchmark calculations
   * Wall Time: Elapsed real time (in seconds) spent on benchmark calculations
   * Nanosecs per day: Simulation speed achieved
   * Hours per nanosec: Hours required to calculate 1 nanosecond of simulation

.. container:: tn-app-variant tn-app-hpl

   * Time: Linpack problem execution time (in seconds)
   * GFlops: Rate of execution (in GFLOP/s)

Cleaning the Workspace
----------------------

.. container:: tn-workspace-cleanup

   Deactivate the workspace:

   .. code-block:: console

       $ ramble workspace deactivate

   To completely remove the workspace:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace remove vectors_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace remove vectors_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace remove vectors_hpl

