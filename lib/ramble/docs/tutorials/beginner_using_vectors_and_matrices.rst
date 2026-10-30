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

.. tutorial-header:: vectors_matrices

In this tutorial, you will learn how to utilize vectors and matrices in Ramble
workspaces. Ramble's vector and matrix variable logic is defined in more detail in
:ref:`ramble-vector-logic` and :ref:`ramble-matrix-logic`.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

.. note::
   In this tutorial, you will encounter expected errors when copying and
   pasting the commands. This is to help show situations you might run into when
   trying to use Ramble on your own, and illustrate how you might fix them.

Create and Activate a Workspace
-------------------------------

.. tutorial-workspace-create:: vectors
   :separate-activate:

   Before configuring experiments with vectors and matrices, set up a new workspace:

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

.. tutorial-app-template::
   :wrf: extra_note=, with ``-V wrf_tiles=true`` enabled;flags1=-V wrf_tiles=true -v n_ranks=1 -v n_threads=1 -v num_tiles=1;flags2=-V wrf_tiles=true -v n_ranks=1 -v n_threads=1 -v num_tiles=2
   :gromacs: extra_note=;flags1=-v n_ranks=1 -v n_threads=1 -v size=0003 -v type=pme;flags2=-v n_ranks=1 -v n_threads=1 -v size=0003 -v type=rf
   :hpl: extra_note=;flags1=-v n_ranks=1 -v n_threads=1 -v memory_per_node=8 -v PFACTs=0;flags2=-v n_ranks=1 -v n_threads=1 -v memory_per_node=8 -v PFACTs=1

   For {app_upper}, we configure two workloads (``{workload}`` and ``{workload2}``), each with two
   experiments exploring different values of the ``{vec_dim}`` parameter (``{vec_e1}`` and ``{vec_e2}``{extra_note}):

   .. code-block:: console

       $ ramble workspace manage experiments {app} --workload-filter {workload} -e {vec_e1} -V package_manager=spack {flags1}
       $ ramble workspace manage experiments {app} --workload-filter {workload} -e {vec_e2} -V package_manager=spack {flags2}
       $ ramble workspace manage experiments {app} --workload-filter {workload2} -e {vec_e1} -V package_manager=spack {flags1}
       $ ramble workspace manage experiments {app} --workload-filter {workload2} -e {vec_e2} -V package_manager=spack {flags2}
       $ ramble workspace concretize

Experiment Descriptions
-----------------------

Now that your workspace is active and configured, execute the following command to see what
experiments the workspace currently contains:

.. code-block:: console

    $ ramble workspace info

This command provides a summary view of the workspace:

.. tutorial-app-template::

   .. code-block:: console

       Experiments:
         Application: {app}
           Workload: {workload}
             Experiment 1: {app}.{workload}.{vec_e1}
             Experiment 2: {app}.{workload}.{vec_e2}
         Application: {app}
           Workload: {workload2}
             Experiment 3: {app}.{workload2}.{vec_e1}
             Experiment 4: {app}.{workload2}.{vec_e2}

To get detailed information about where variable definitions come from, you can use:

.. code-block:: console

    $ ramble workspace info --expansions

The experiments section of this command displays variables defined at the workspace scope
and at the experiment scope:

.. tutorial-app-template::
   :wrf: extra_exp=
   :gromacs: extra_exp=size = 0003 ==> 0003
   :hpl: extra_exp=memory_per_node = 8 ==> 8

   .. code-block:: console

       Experiments:
         Application: {app}
           Workload: {workload}
             Experiment 1: {app}.{workload}.{vec_e1}
               Variables from Workspace:
                 processes_per_node = 16 ==> 16
                 mpi_command = mpirun -n {n_ranks} -ppn {processes_per_node} ==> mpirun -n 1 -ppn 16
                 batch_submit = {execute_experiment} ==> {execute_experiment}
               Variables from Experiment:
                 n_ranks = 1 ==> 1
                 n_threads = 1 ==> 1
                 {extra_exp}
                 {vec_dim} = {vec_v1} ==> {vec_v1}
             Experiment 2: {app}.{workload}.{vec_e2}
               Variables from Workspace:
                 processes_per_node = 16 ==> 16
                 mpi_command = mpirun -n {n_ranks} -ppn {processes_per_node} ==> mpirun -n 1 -ppn 16
                 batch_submit = {execute_experiment} ==> {execute_experiment}
               Variables from Experiment:
                 n_ranks = 1 ==> 1
                 n_threads = 1 ==> 1
                 {extra_exp}
                 {vec_dim} = {vec_v2} ==> {vec_v2}

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

.. tutorial-app-template::

   For {app_upper}, collapse the ``{vec_dim}`` values into a list (``{vec_list}``) within each workload:

   .. code-block:: YAML

       {vec_e1}:
         variables:
           n_ranks: '1'
           n_threads: '1'
           {vec_extra_var}
           {vec_dim}: {vec_list}

After updating your configuration, save and exit your ``ramble.yaml`` file, and execute:

.. code-block:: console

    $ ramble workspace info

Notice the error printed to the screen:

.. tutorial-app-template::
   :wrf: err_wl=CONUS_12km
   :gromacs: err_wl=water_gmx50
   :hpl: err_wl=calculator

   .. code-block:: console

       ==> Warning: Two experiments are defined with the name {app}.{err_wl}.{vec_e1}
       ==> Warning: Variables unique to previously defined experiment:
       ==> Warning:   - experiment_index
       ==> Warning: Variable differences between experiment definitions:
       ==> Warning:   - {vec_dim}: {'previous': '{vec_v1}', 'new': '{vec_v2}'}
       ==> Error: Experiment {app}.{err_wl}.{vec_e1} is not unique.

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

.. tutorial-app-template::

   Change the experiment name from ``{vec_e1}`` to ``'{vec_etpl}'``:

   .. code-block:: YAML

       '{vec_etpl}':
         variables:
           n_ranks: '1'
           n_threads: '1'
           {vec_extra_var}
           {vec_dim}: {vec_list}

.. note::
   In YAML, experiment names starting with ``{`` must be wrapped in quotes
   so the parser does not treat them as inline mappings/dictionaries.

Now, verify the resulting experiments using:

.. code-block:: console

    $ ramble workspace info

Ramble now generates four unique experiments:

.. tutorial-app-template::

   .. code-block:: console

       Experiments:
         Application: {app}
           Workload: {workload}
             Experiment 1: {app}.{workload}.{vec_e1}
             Experiment 2: {app}.{workload}.{vec_e2}
           Workload: {workload2}
             Experiment 3: {app}.{workload2}.{vec_e1}
             Experiment 4: {app}.{workload2}.{vec_e2}

Vectorizing Workload Names
--------------------------

Next, we can simplify the configuration further by vectorizing across workloads.

Define a new variable named ``app_workload`` within one experiment, delete the second workload
definition entirely, and templatize the workload name using ``'{app_workload}'``:

.. tutorial-app-template::

   .. code-block:: YAML

       workloads:
         '{app_workload}':
           experiments:
             '{vec_etpl}':
               variables:
                 app_workload: ['{workload}', '{workload2}']
                 n_ranks: '1'
                 n_threads: '1'
                 {vec_extra_var}
                 {vec_dim}: {vec_list}

Save and exit, then run:

.. code-block:: console

    $ ramble workspace info

Notice that Ramble now reports only **two** experiments instead of the four we expected:

.. tutorial-app-template::

   .. code-block:: console

       Experiments:
         Application: {app}
           Workload: {app_workload}
             Experiment 1: {app}.{workload}.{vec_e1}
             Experiment 2: {app}.{workload2}.{vec_e2}

This happens because multiple unconstrained vector variables are **implicitly zipped** together.
Since both vectors have length 2, Ramble pairs element 1 with element 1, and element 2 with element 2:

.. tutorial-app-template::
   :wrf: p1=tile 1;p2=tile 2
   :gromacs: p1=pme;p2=rf
   :hpl: p1=pfact 0;p2=pfact 1

   .. code-block:: console

       [ ({workload}, {p1}), ({workload2}, {p2}) ]

To generate the full cross-product of workloads and parameters, we use variable **matrices**.

Variable Matrices
-----------------

When you want an explicit Cartesian product of parameter lists, define a ``matrix:`` block
within the experiment scope. Variables listed in a matrix are consumed by the matrix and
crossed with each other.

Update your experiment definition to include a ``matrix:`` block:

.. tutorial-app-template::

   .. code-block:: YAML

       workloads:
         '{app_workload}':
           experiments:
             '{vec_etpl}':
               variables:
                 app_workload: ['{workload}', '{workload2}']
                 n_ranks: '1'
                 n_threads: '1'
                 {vec_extra_var}
                 {vec_dim}: {vec_list}
               matrix:
               - app_workload
               - {vec_dim}

Save the file and execute:

.. code-block:: console

    $ ramble workspace info

Ramble now generates all four combinations:

.. tutorial-app-template::

   .. code-block:: console

       Experiments:
         Application: {app}
           Workload: {app_workload}
             Experiment 1: {app}.{workload}.{vec_e1}
             Experiment 2: {app}.{workload}.{vec_e2}
             Experiment 3: {app}.{workload2}.{vec_e1}
             Experiment 4: {app}.{workload2}.{vec_e2}

Defining a Scaling Study
------------------------

Finally, we can extend this experiment definition to perform a rank-based scaling study by
vectorizing ``n_ranks: ['1', '2']`` and adding ``n_ranks`` to the matrix definition.

You can configure this scaling matrix directly using the ``ramble workspace manage experiments`` command:

.. tutorial-snippet:: vectors_matrices commands.sh
   :alt-yaml: ramble.yaml
   :alt-text: The resulting ``configs/ramble.yaml`` will look like:

Check the final list of generated experiments:

.. code-block:: console

    $ ramble workspace info

Ramble will display all 8 generated experiments:

.. tutorial-app-template::

   .. code-block:: console

       Experiments:
         Application: {app}
           Workload: {app_workload}
             Experiment 1: {app}.{workload}.{vec_p1}_1ranks
             Experiment 2: {app}.{workload}.{vec_p1}_2ranks
             Experiment 3: {app}.{workload}.{vec_p2}_1ranks
             Experiment 4: {app}.{workload}.{vec_p2}_2ranks
             Experiment 5: {app}.{workload2}.{vec_p1}_1ranks
             Experiment 6: {app}.{workload2}.{vec_p1}_2ranks
             Experiment 7: {app}.{workload2}.{vec_p2}_1ranks
             Experiment 8: {app}.{workload2}.{vec_p2}_2ranks

Executing Experiments
---------------------

.. tutorial-execute:: vectors
   :wrf: exp=CONUS_12km_1ranks
   :gromacs: exp=pme_0.0005_1ranks
   :hpl: exp=pfact_0_1ranks
   :dry-run-cmds: ls -la $RAMBLE_ROOT/var/ramble/workspaces/vectors_{app}/experiments/{app}/; cat $RAMBLE_ROOT/var/ramble/workspaces/vectors_{app}/experiments/{app}/{workload}/{exp}/execute_experiment
   :include-foms:

Cleaning the Workspace
----------------------

.. tutorial-workspace-cleanup:: vectors


