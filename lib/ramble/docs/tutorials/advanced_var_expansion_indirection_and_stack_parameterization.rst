.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _variable_expansion_and_indirection_and_stack_parameterization_tutorial:

======================================================================
Variable Expansion, Indirection, and Software Stack Parameterization
======================================================================

.. raw:: html

   <div class="tn-app-switcher" data-recipe="var_expansion"></div>

In this tutorial, you will learn how to use variable expansion, indirection,
and software stack parameterization when generating experiments.

.. container:: tn-app-variant tn-app-wrf

   For this tutorial path, we will use `WRF <https://www.mmm.ucar.edu/models/wrf>`_,
   a free and open-source atmospheric research model.

.. container:: tn-app-variant tn-app-gromacs

   For this tutorial path, we will use `GROMACS <https://www.gromacs.org/>`_,
   a versatile package for molecular dynamics simulations.

.. container:: tn-app-variant tn-app-hpl

   For this tutorial path, we will use `HPL <https://netlib.org/benchmark/hpl/>`_,
   a benchmark for High-Performance Computing that measures floating point execution rate.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

.. note::
   In this tutorial, you will encounter expected errors when copying and
   pasting the commands. This is to help show situations you might run into when
   trying to use Ramble on your own, and illustrate how you might fix them.

Create a Workspace
------------------

.. container:: tn-workspace-create

   To begin with, you need a workspace to configure the experiments. This can be
   created with the following command:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace create var_expansion_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace create var_expansion_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace create var_expansion_hpl

   .. rubric:: Activate the Workspace

   Several of Ramble's commands require an activated workspace to function
   properly. Activate the newly created workspace using the following command:

   .. note::

      You only need to run this if you do not currently have the workspace
      active.

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace activate var_expansion_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace activate var_expansion_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace activate var_expansion_hpl

Configure Experiment Definitions
--------------------------------

To begin with, you need to configure the workspace. The workspace's root
location can be seen under the ``Location`` output of:

.. code-block:: console

    $ ramble workspace info

Additionally, the configuration file can be edited directly with:

.. code-block:: console

    $ ramble workspace edit

Within the ``ramble.yaml`` file, write the following contents, which represent
the baseline scaling configuration from the previous tutorial.

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/var_expansion_wrf_base.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/var_expansion_gromacs_base.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/var_expansion_hpl_base.yaml
      :language: YAML

The above configuration will execute 4 experiments, comprising a basic scaling
study on two different sets of nodes across two different platforms.

You will expand this definition to perform the same sweep over multiple MPI
implementations. Over the course of this tutorial, you will learn how to use
variable expansion and indirection to construct more complex experiments.

Define Additional MPI and Parameterize Software Environments
------------------------------------------------------------

To begin with, you will parameterize the software stack definitions to generate
experiments using both IntelMPI and OpenMPI. For this section, you can focus on
the ``software`` portion of the ``ramble.yaml`` configuration file. For more
information on how this section is constructed, see the :ref:`Software config
section<software-config>` documentation.

To start with, you will create an OpenMPI package definition. This might look
like the following:

.. code-block:: YAML

    packages:
      openmpi:
        pkg_spec: openmpi@5.0.8

In the definition of the Intel MPI package above, you'll see we originally
specified a ``compiler`` attribute (with the value of ``gcc14``). This can be
explicitly selected if you like, however when using Spack, Ramble generates
Spack environments with ``unify: true``
(See `Spack's environment documentation <https://spack.readthedocs.io/en/latest/environments.html#spec-concretization>`_
for more details). As a result, OpenMPI should be compiled with the same
compiler used for the application.

.. note::
   This package can also be defined using the following command:

   .. code-block:: console

       $ ramble workspace manage software --pkg openmpi --spec openmpi@5.0.8

   However you will need to parameterize which MPI implementation is used
   manually, as follows.

We also need to generate additional software environments, however we will
parameterize the generation of these using a new variable definition. Since the
``mpi_name`` variable will be needed for both experiment generation and
environments, you'll put it under the workspace variables:

.. code-block:: YAML

    ramble:
      variables:
        mpi_name: ['intel-mpi', 'openmpi']

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: YAML

       environments:
         wrf@4.2-{mpi_name}:
           packages:
           - '{mpi_name}'
           - wrfv4-{application::wrf::version}

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: YAML

       environments:
         gromacs-{mpi_name}:
           packages:
           - '{mpi_name}'
           - gromacs

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: YAML

       environments:
         hpl-{mpi_name}:
           packages:
           - '{mpi_name}'
           - hpl

.. container:: tn-app-variant tn-app-wrf

   This will create two software environments: one named ``wrf@4.2-intel-mpi`` and
   another named ``wrf@4.2-openmpi``.

.. container:: tn-app-variant tn-app-gromacs

   This will create two software environments: one named ``gromacs-intel-mpi`` and
   another named ``gromacs-openmpi``.

.. container:: tn-app-variant tn-app-hpl

   This will create two software environments: one named ``hpl-intel-mpi`` and
   another named ``hpl-openmpi``.

.. note::
   The reference to ``{mpi_name}`` within the environment package list is
   escaped using single quotes. This is to prevent YAML from parsing this as a
   dictionary.

The result might look like the following:

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/var_expansion_wrf_mpi.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/var_expansion_gromacs_mpi.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/var_expansion_hpl_mpi.yaml
      :language: YAML

At this point, executing:

.. code-block:: console

    $ ramble workspace info

Should result in the following error:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       ==> Warning: Two experiments are defined with the name wrf@4.2.CONUS_12km.scaling_1_platform1
       ==> Warning:   -> Collision Origin: Within the same YAML experiment block: 'scaling_{n_nodes}_{platform}' (Matrix/Vector Expansion)
       ==> Warning: Variables unique to previously defined experiment:
       ==> Warning:   - experiment_index
       ==> Warning: Variable differences between experiment definitions:
       ==> Warning:   - mpi_name: {'previous': 'intel-mpi', 'new': 'openmpi'}
       ==> Error: Experiment wrf@4.2.CONUS_12km.scaling_1_platform1 is not unique.

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       ==> Warning: Two experiments are defined with the name gromacs.water_bare.scaling_1_platform1
       ==> Warning:   -> Collision Origin: Within the same YAML experiment block: 'scaling_{n_nodes}_{platform}' (Matrix/Vector Expansion)
       ==> Warning: Variables unique to previously defined experiment:
       ==> Warning:   - experiment_index
       ==> Warning: Variable differences between experiment definitions:
       ==> Warning:   - mpi_name: {'previous': 'intel-mpi', 'new': 'openmpi'}
       ==> Error: Experiment gromacs.water_bare.scaling_1_platform1 is not unique.

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       ==> Warning: Two experiments are defined with the name hpl.calculator.scaling_1_platform1
       ==> Warning:   -> Collision Origin: Within the same YAML experiment block: 'scaling_{n_nodes}_{platform}' (Matrix/Vector Expansion)
       ==> Warning: Variables unique to previously defined experiment:
       ==> Warning:   - experiment_index
       ==> Warning: Variable differences between experiment definitions:
       ==> Warning:   - mpi_name: {'previous': 'intel-mpi', 'new': 'openmpi'}
       ==> Error: Experiment hpl.calculator.scaling_1_platform1 is not unique.

As you have implicitly defined 8 experiments (2 from ``n_nodes``, times 2 from
``platform_config``, times another 2 from ``mpi_name``), but you haven't
updated the experiment name template. To resolve this, add ``{mpi_name}`` into
the experiment name template: ``scaling_{n_nodes}_{platform}_{mpi_name}``.
Additionally, you may explicitly add ``mpi_name`` into the matrix.

The experiments are still not completely defined. Running:

.. code-block:: console

    $ ramble workspace info

Should result in the following warning:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       ==> Warning: Software environment 'wrf@4.2' was auto-constructed for package manager 'spack' and contains no packages. If this was not intended, please define the environment or packages in your configuration.

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       ==> Warning: Software environment 'gromacs' was auto-constructed for package manager 'spack' and contains no packages. If this was not intended, please define the environment or packages in your configuration.

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       ==> Warning: Software environment 'hpl' was auto-constructed for package manager 'spack' and contains no packages. If this was not intended, please define the environment or packages in your configuration.

The default software environment every application uses is named the same as the
application. Now that you've changed the name of the environment, you need to
connect each experiment to the proper environment.

To control the software environment used within an experiment, Ramble allows
you to use the ``env_name`` variable definition. Because ``mpi_name`` is a list
variable, you might want ``env_name`` to be a list that is zipped with
``mpi_name`` to make sure they are iterated over together. However, you may
also utilize variable indirection / expansion to fix this issue. For the
purposes of this tutorial, we will use indirection instead of explicit zips. In
the experiment variables, add:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: YAML

       variables:
         env_name: 'wrf@4.2-{mpi_name}'

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: YAML

       variables:
         env_name: 'gromacs-{mpi_name}'

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: YAML

       variables:
         env_name: 'hpl-{mpi_name}'

The resulting configuration file might look like the following:

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/var_expansion_wrf_mpi_matrix.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/var_expansion_gromacs_mpi_matrix.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/var_expansion_hpl_mpi_matrix.yaml
      :language: YAML

Variable Expansion and Indirection
----------------------------------

At this stage, you have defined a workspace that will execute 8 experiments.
It is important to point out that different MPI implementations have different
command line flags for controlling their behavior. The existing ``mpi_command``
should work fine with both Intel MPI and OpenMPI, but to illustrate how
variable expansion and indirection can be used you will now add a flag to
control the number of MPI ranks per compute node.

For Intel MPI this is:

.. code-block:: console

    -ppn {processes_per_node}

While in OpenMPI this is:

.. code-block:: console

    --map-by ppr:{processes_per_node}:node

One way to define this is to define ``mpi_command`` as a list variable, with
the appropriate MPI command line arguments. Then you can define an explicit zip
that combines ``mpi_command`` and ``mpi_name``. However, for the purposes of
this tutorial you will instead use variable expansion and indirection to lookup
variable definitions.

.. note::
   These differences in ``mpi_command`` can also be parameterized through
   ``platform`` and ``system`` classes instead of explicitly within a
   workspace. Here they are performed within the workspace to show how
   indireciton works.

In Ramble, every variable can be defined as a combination of other variables. For example:

.. code-block:: YAML

    variables:
      processes_per_node: 4
      n_nodes: 2
      n_ranks: '{processes_per_node}*{n_nodes}'

Would result in ``n_ranks`` having a value of 8, as each of the variable
references are expanded and then the math is evaluated.

Additionally, variable references are allowed to be nested to parameterize
which variables you want to use. For example:

.. code-block:: YAML

    variables:
      openmpi_args: '--np {n_ranks} --map-by ppr:{processes_per_node}:node -x OMP_NUM_THREADS'
      intel-mpi_args: '-n {n_ranks} -ppn {processes_per_node}'
      mpi_command: 'mpirun {{mpi_name}_args}'

Allows the ``mpi_command`` definition to change based on the definition of
``mpi_name``. This is called variable indirection. If we employ variable
indirection to help parameterize the MPI arguments as shown above, the
resulting configuration might look like the following:

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/var_expansion_wrf_expansion_indirection.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/var_expansion_gromacs_expansion_indirection.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/var_expansion_hpl_expansion_indirection.yaml
      :language: YAML

.. note::
   The arguments for the various MPI implementations may not run on your
   system if you require additional arguments. To be able to execute these on your
   system, make sure you modify these appropriately.

At this point, you have described the 8 experiments you want to run.

Dry Run Setup
-------------

Before executing the experiments, you can perform:

.. code-block:: console

    $ ramble workspace setup --dry-run

And examine the contents of the rendered ``execute_experiment`` scripts in some
experiment directories. Looking at these, you should see the correct MPI
arguments within the relevant experiments: Intel MPI experiments will contain
``-n ... -ppn ...``, while OpenMPI experiments will contain
``--np ... --map-by ppr:...:node -x OMP_NUM_THREADS``.

Execute Experiments
-------------------

.. container:: tn-full-run-only

   .. note::
      This workspace uses the ``spack`` package manager to build the software stack
      and MPI implementations. ``spack`` can either be installed in your ``PATH``, or
      Ramble will automatically bootstrap it for you.

   .. note::
      When not running in dry-run mode, both setup and execution can take a very
      long time:

      * Because the software stack is parameterized across two MPI libraries
        (``intel-mpi`` and ``openmpi``), ``ramble workspace setup`` will concretize
        and build **two separate software environments** from source if they are not
        already installed on your system.
      * ``ramble on`` executes all 8 scaling experiments across both MPI stacks and
        node counts.

      To skip software installation and execution, you can enable **Dry-Run Mode**
      at the top of this tutorial or validate the workspace configuration using
      ``ramble workspace setup --dry-run`` instead.

   Now that you have made the appropriate modifications, set up, execute, and
   analyze the new experiments using:

   .. code-block:: console

       $ ramble workspace setup
       $ ramble on
       $ ramble workspace analyze

   This creates a ``results`` file in the root of the workspace that contains
   extracted figures of merit:

.. container:: tn-dry-run-only

   With **Dry-Run Mode** enabled, set up the parameterized workspace using
   ``--dry-run``:

   .. code-block:: console

       $ ramble workspace setup --dry-run

   Because we are running in dry-run mode, we do **not** execute ``ramble on`` or
   ``ramble workspace analyze``. Instead, explore the generated ``software/`` and
   ``experiments/`` directories in the workspace to verify how Ramble expanded the
   parameterized software stacks and indirect variable references in each
   ``execute_experiment`` script:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/var_expansion_wrf/software/
          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/var_expansion_wrf/experiments/wrf/CONUS_12km/

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/var_expansion_gromacs/software/
          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/var_expansion_gromacs/experiments/gromacs/water_bare/

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/var_expansion_hpl/software/
          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/var_expansion_hpl/experiments/hpl/calculator/

   **Example Output (Full Run):**

   In a full run where ``ramble on`` and ``ramble workspace analyze`` are executed,
   Ramble creates a ``results.latest.txt`` file in the root of the workspace
   containing the following extracted figures of merit:

.. container:: tn-app-variant tn-app-wrf

   * **Average Timestep Time**: Time (in seconds) on average each timestep takes
   * **Cumulative Timestep Time**: Time (in seconds) spent executing all timesteps
   * **Minimum Timestep Time**: Minimum time (in seconds) spent on any one timestep
   * **Maximum Timestep Time**: Maximum time (in seconds) spent on any one timestep
   * **Number of timesteps**: Count of total timesteps performed
   * **Avg. Max Ratio Time**: Ratio of Average Timestep Time and Maximum Timestep Time

.. container:: tn-app-variant tn-app-gromacs

   * **Core Time**: CPU time (in seconds) spent on benchmark calculations
   * **Wall Time**: Elapsed real time (in seconds) spent on benchmark calculations
   * **Nanosecs per day**: Simulation speed achieved
   * **Hours per nanosec**: Hours required to calculate 1 nanosecond of simulation

.. container:: tn-app-variant tn-app-hpl

   * **Time**: Time (in seconds) spent executing the benchmark calculation
   * **GFlops**: Performance in GFLOP/s achieved


Clean the Workspace
-------------------

.. container:: tn-workspace-cleanup

   Once you are finished with the tutorial content, make sure you deactivate your workspace:

   .. code-block:: console

       $ ramble workspace deactivate

   Additionally, you can remove the workspace and all of its content with:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace remove var_expansion_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace remove var_expansion_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace remove var_expansion_hpl
