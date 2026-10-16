.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _configuring_a_scaling_study_tutorial:

===========================
Configuring a Scaling Study
===========================

In this tutorial, you will learn how to create a workspace containing a scaling
study. This tutorial supports multiple applications (such as WRF, GROMACS, and HPL);
you can select your preferred application below.

.. raw:: html

   <div class="tn-app-switcher" data-recipe="scaling_study"></div>

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

.. note::
   In this tutorial, you will encounter expected errors when copying and
   pasting the commands. This is to help show situations you might run into when
   trying to use Ramble on your own, and illustrate how you might fix them.

Create and Activate a Workspace
-------------------------------

.. container:: tn-workspace-create

   To begin with, you need a workspace to configure the scaling study. This can be
   created with the following command:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace create scaling_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace create scaling_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace create scaling_hpl

   Several of Ramble's commands require an activated workspace to function
   properly. Activate the newly created workspace using the following command:

   .. note::
      You only need to run this if you do not currently have the workspace active.

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace activate scaling_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace activate scaling_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace activate scaling_hpl

Decide on a Workload
--------------------

Before you can set up this workspace, you'll need to configure the experiments
you want to execute. To begin with, select a workload:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       $ ramble info --attrs workloads wrf

   For the purposes of this tutorial, the ``CONUS_12km`` workload is recommended
   because it is less computationally expensive than the ``CONUS_2p5km`` workload.

   .. note::
      To get more detailed information about the workload definitions, you
      can use ``ramble info --attrs workloads -v wrf``.

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       $ ramble info --attrs workloads gromacs

   For the purposes of this tutorial, the ``water_bare`` workload is recommended.

   .. note::
      To get more detailed information about the workload definitions, you
      can use ``ramble info --attrs workloads -v gromacs``.

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       $ ramble info --attrs workloads hpl

   For the purposes of this tutorial, the ``calculator`` workload is recommended.

   .. note::
      To get more detailed information about the workload definitions, you
      can use ``ramble info --attrs workloads -v hpl``.

Configure Experiment Definitions
--------------------------------

Now that you have selected a workload to use, configure the experiments you want to execute.
You can configure your experiment definitions directly using ``ramble workspace manage experiments``:

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/scaling_study_wrf_commands.sh
      :language: console

   Alternatively, if you edit ``configs/ramble.yaml`` directly, your ``applications`` configuration will look like:

   .. literalinclude:: ../_generated/snippets/scaling_study_wrf_applications.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/scaling_study_gromacs_commands.sh
      :language: console

   Alternatively, if you edit ``configs/ramble.yaml`` directly, your ``applications`` configuration will look like:

   .. literalinclude:: ../_generated/snippets/scaling_study_gromacs_applications.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/scaling_study_hpl_commands.sh
      :language: console

   Alternatively, if you edit ``configs/ramble.yaml`` directly, your ``applications`` configuration will look like:

   .. literalinclude:: ../_generated/snippets/scaling_study_hpl_applications.yaml
      :language: YAML

The experiment name template ``scaling_{n_nodes}`` allows parameterizing the experiment
across the values in ``n_nodes: [1, 2]``.

At this point, you can attempt to view the experiments defined by this
configuration file. To do this, use the following command:

.. code-block:: console

    $ ramble workspace info

The output should tell you some required variable definitions are missing, as
the configuration does not include some system level definitions. The output
might look like the following:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       ==> Error: Invalid number of required variables defined.
       Two or more of the following are required to be defined.
         - n_ranks
         - processes_per_node
         - n_nodes
       Experiment wrf.CONUS_12km.scaling_1 only has:
         - n_nodes

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       ==> Error: Invalid number of required variables defined.
       Two or more of the following are required to be defined.
         - n_ranks
         - processes_per_node
         - n_nodes
       Experiment gromacs.water_bare.scaling_1 only has:
         - n_nodes

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       ==> Error: Invalid number of required variables defined.
       Two or more of the following are required to be defined.
         - n_ranks
         - processes_per_node
         - n_nodes
       Experiment hpl.calculator.scaling_1 only has:
         - n_nodes

To remedy this issue, you need to define some system level variables in the
following section.

Configuring System Details
--------------------------

Within Ramble configuration files, it is generally a good practice to keep your
system level details as close to the top level as possible within a
``ramble.yaml`` workspace configuration file.

Currently, your configuration file describes a scaling study, but does not
define additional important details such as how many MPI ranks you want in each
experiment (defined by the ``n_ranks`` variable), or how many MPI ranks should
execute on each node (defined by the ``processes_per_node`` variable). You
should add these details as workspace variables within your configuration file.
For the purposes of this tutorial, we will assume 16 MPI ranks per node and that
the number of MPI ranks total will be the number of MPI ranks per node
multiplied by the number of nodes.

Additionally, you need to define ``batch_submit`` and ``mpi_command``
variables. The ``batch_submit`` variable will take a command template that can
be used to actually execute the experiment. For use outside of a workload
manager (such as SLURM) the default value of ``{execute_experiment}`` is a good
starting place, however this will execute all experiments sequentially. The
``mpi_command`` variable will take the ``mpirun`` command and any MPI specific
variables you would like to use for your experiments. These vary based on the
MPI implementation you wish to use, but good default might be
``mpirun -n {n_ranks}``. If you would like to add ``hostfile`` and ``ppn``
flags, feel free to do so here.

Your configuration file might look like the following after adding this
information:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: YAML

       ramble:
         variants:
           package_manager: spack
         env_vars:
           set:
             OMP_NUM_THREADS: '{n_threads}'
         variables:
           processes_per_node: 16
           n_ranks: '{processes_per_node}*{n_nodes}'
           batch_submit: '{execute_experiment}'
           mpi_command: 'mpirun -n {n_ranks}'
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

       ramble:
         variants:
           package_manager: spack
         env_vars:
           set:
             OMP_NUM_THREADS: '{n_threads}'
         variables:
           processes_per_node: 16
           n_ranks: '{processes_per_node}*{n_nodes}'
           batch_submit: '{execute_experiment}'
           mpi_command: 'mpirun -n {n_ranks}'
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

       ramble:
         variants:
           package_manager: spack
         env_vars:
           set:
             OMP_NUM_THREADS: '{n_threads}'
         variables:
           processes_per_node: 16
           n_ranks: '{processes_per_node}*{n_nodes}'
           batch_submit: '{execute_experiment}'
           mpi_command: 'mpirun -n {n_ranks}'
         applications:
           hpl:
             workloads:
               calculator:
                 experiments:
                   scaling_{n_nodes}:
                     variables:
                       n_nodes: [1, 2]
                       memory_per_node: 8

.. note::
   The value of the ``n_ranks`` variable is escaped using single quotes.
   This is because YAML interprets the ``{`` character as beginning a dictionary,
   so we need to escape it to convert it to a string.

Applying the Default Software Configuration
-------------------------------------------

At this point, you have fully described the experiments you would like to
perform, but have not defined the software stack that should be used for these
experiments. Every Ramble application definition file should contain a
suggested starting place for the experiments. To apply this to your workspace, use:


.. code-block:: console

    $ ramble workspace concretize

This will fill out the ``software`` dictionary within your workspace configuration
file. After executing this command, your workspace configuration file might
look like the following:


.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/scaling_study_wrf_ramble.yaml
      :language: YAML


.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/scaling_study_gromacs_ramble.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/scaling_study_hpl_ramble.yaml
      :language: YAML

At this point, you have fully described experiments that can be executed.
However, your system might not have the correct compiler (and building a
compiler could be costly). The ``gcc14`` package definition can be updated to
refer to a compiler you already have on your system. These can be viewed using
the ``spack compiler list`` command. Edit the ``gcc14`` package definition as
you see fit, and make sure the compiler references are updated appropriately as well.

Executing Experiments
---------------------

.. container:: tn-full-run-only

   .. note::
      By default, the experiments in this tutorial use `Spack <https://spack.io/>`_
      (configured via ``package_manager: spack``) to build and install the required
      software stack. ``spack`` can either be installed in your ``PATH``, or Ramble
      will automatically bootstrap it for you.

   .. note::
      When not running in dry-run mode, both setup and execution can take a
      significant amount of time:

      * ``ramble workspace setup`` will build the required compiler, MPI library,
        and application from source if they are not already installed on your
        system, and download any required workload input files.
      * ``ramble on`` executes multiple scaling experiments across the configured
        node and rank sweep, which can take a long time depending on the workload
        and available compute resources.

      You can optionally enable **Dry-Run Mode** at the top of this tutorial or pass the
      ``--dry-run`` flag to setup (``ramble workspace setup --dry-run``) to quickly
      generate and inspect the experiment directories without building software or
      running the experiments.

   Now that you have configured your scaling study, set up, execute, and
   analyze the experiments using:

   .. code-block:: console

       $ ramble workspace setup
       $ ramble on
       $ ramble workspace analyze

   This creates a ``results.latest.txt`` file in the root of the workspace containing
   extracted figures of merit. If the experiments were successful, the results file
   will show the extracted metrics:

.. container:: tn-dry-run-only

   With **Dry-Run Mode** enabled, set up the scaling study experiments using
   ``--dry-run``:

   .. code-block:: console

       $ ramble workspace setup --dry-run

   In dry-run mode, we do **not** execute ``ramble on`` or ``ramble workspace analyze``.
   Instead, explore the generated scaling study directories under ``experiments/`` and
   inspect the rendered ``execute_experiment`` scripts across the different rank/thread
   configurations:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/scaling_wrf/experiments/wrf/CONUS_12km/

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/scaling_gromacs/experiments/gromacs/water_bare/

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/scaling_hpl/experiments/hpl/calculator/

   **Example Output (Full Run):**

   In a full run where ``ramble on`` and ``ramble workspace analyze`` are executed,
   Ramble creates a ``results.latest.txt`` file in the root of the workspace
   containing the following extracted metrics for each scaling point:

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
   * **GFlops**: Benchmark calculation throughput (in GFLOP/s)

Ramble also supports uploading the analyzed data to online databases, using
``ramble workspace analyze --upload``. We will not cover this functionality in
detail here, but it is very useful for production experiments.


Cleaning the Workspace
----------------------

.. container:: tn-workspace-cleanup

   After you are finished with the content of this tutorial, make sure you
   deactivate your workspace using:

   .. code-block:: console

       $ ramble workspace deactivate

   If you no longer need the workspace materials, remove the entire workspace
   with:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace remove scaling_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace remove scaling_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace remove scaling_hpl
