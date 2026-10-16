.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _running_an_experiment_tutorial:

======================================
Creating a Single Experiment Workspace
======================================

In this tutorial, you will set up and run a benchmark simulation using a real
scientific application. This tutorial supports multiple applications (such as
WRF, GROMACS, and HPL); you can select your preferred application below.

.. raw:: html

   <div class="tn-app-switcher" data-recipe="single_experiment"></div>

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content,
however this tutorial is fully stand-alone as far as steps you need to perform.

Application Information
-----------------------

.. container:: tn-app-variant tn-app-wrf

   This tutorial uses the `Weather Research and Forecasting (WRF) <https://www.mmm.ucar.edu/models/wrf>`_
   model, a next-generation mesoscale numerical weather prediction system.
   We will begin with the ``CONUS_12km`` workload, as it represents a standard
   continental United States forecast benchmark.

   Using a previously installed ``ramble``, the following command can be used to
   get information about this workload:

   .. literalinclude:: ../_generated/snippets/single_experiment_wrf_info_workload_cmd.sh
      :language: console

   Under the workload marked by ``Workload: CONUS_12km``, you should see output similar to:

   .. literalinclude:: ../_generated/snippets/single_experiment_wrf_info_workload.out
      :language: console

   To determine a suggested software configuration, you can use:

   .. literalinclude:: ../_generated/snippets/single_experiment_wrf_info_software_cmd.sh
      :language: console

   With this command, you should see output similar to the following:

   .. literalinclude:: ../_generated/snippets/single_experiment_wrf_info_software.out
      :language: console

.. container:: tn-app-variant tn-app-gromacs

   This tutorial uses the `GROMACS <https://www.gromacs.org/>`_
   application definition, a free and open-source application for molecular dynamics.
   We will begin with the ``water_bare`` workload, as it is able to execute in a short amount of time.

   Using a previously installed ``ramble``, the following command can be used to
   get information about this workload:

   .. literalinclude:: ../_generated/snippets/single_experiment_gromacs_info_workload_cmd.sh
      :language: console

   Under the workload marked by ``Workload: water_bare``, you should see output similar to:

   .. literalinclude:: ../_generated/snippets/single_experiment_gromacs_info_workload.out
      :language: console

   Here we see that this workload has a ``type`` variable (with possible values
   of ``pme`` and ``rf``) and a ``size`` variable with a variety of available sizes.

   To determine a suggested software configuration, you can use:

   .. literalinclude:: ../_generated/snippets/single_experiment_gromacs_info_software_cmd.sh
      :language: console

   With this command, you should see output similar to the following:

   .. literalinclude:: ../_generated/snippets/single_experiment_gromacs_info_software.out
      :language: console

.. container:: tn-app-variant tn-app-hpl

   This tutorial uses the `High-Performance Linpack (HPL) <https://www.netlib.org/benchmark/hpl/>`_
   benchmark, a widely used benchmark measuring floating-point compute performance.
   We will begin with the ``calculator`` workload, which automatically determines problem
   dimensions and grid parameters based on system memory and node count.

   Using a previously installed ``ramble``, the following command can be used to
   get information about this workload:

   .. literalinclude:: ../_generated/snippets/single_experiment_hpl_info_workload_cmd.sh
      :language: console

   Under the workload marked by ``Workload: calculator``, you should see output similar to:

   .. literalinclude:: ../_generated/snippets/single_experiment_hpl_info_workload.out
      :language: console

   To determine a suggested software configuration, you can use:

   .. literalinclude:: ../_generated/snippets/single_experiment_hpl_info_software_cmd.sh
      :language: console

   With this command, you should see output similar to the following:

   .. literalinclude:: ../_generated/snippets/single_experiment_hpl_info_software.out
      :language: console

This output does not represent the only possible configuration that works for
this application, it only presents a good starting point. When using Ramble,
these can be modified freely.

Configuring Experiments
-----------------------

You will use a Ramble workspace to manage these experiments.

Create and Activate a Workspace
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. container:: tn-workspace-create

   Before you can configure experiments, you'll need to set up a workspace:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace create basic_wrf

      This will create a workspace for you in:

      .. code-block:: console

          $ $RAMBLE_ROOT/var/ramble/workspaces/basic_wrf

      Now you can activate the workspace and view its default configuration:

      .. code-block:: console

          $ ramble workspace activate basic_wrf

      Alternatively, workspace creation and activation can be combined in one command
      with the activate flag (``-a``):

      .. code-block:: console

          $ ramble workspace create basic_wrf -a

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace create basic_gromacs

      This will create a workspace for you in:

      .. code-block:: console

          $ $RAMBLE_ROOT/var/ramble/workspaces/basic_gromacs

      Now you can activate the workspace and view its default configuration:

      .. code-block:: console

          $ ramble workspace activate basic_gromacs

      Alternatively, workspace creation and activation can be combined in one command
      with the activate flag (``-a``):

      .. code-block:: console

          $ ramble workspace create basic_gromacs -a

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace create basic_hpl

      This will create a workspace for you in:

      .. code-block:: console

          $ $RAMBLE_ROOT/var/ramble/workspaces/basic_hpl

      Now you can activate the workspace and view its default configuration:

      .. code-block:: console

          $ ramble workspace activate basic_hpl

      Alternatively, workspace creation and activation can be combined in one command
      with the activate flag (``-a``):

      .. code-block:: console

          $ ramble workspace create basic_hpl -a

Configure the Workspace
~~~~~~~~~~~~~~~~~~~~~~~

Within the workspace directory, Ramble creates a directory named ``configs``.
This directory contains configuration and template files:

* ``ramble.yaml``: Describes all aspects of the workspace, including software, experiments, and variables.
* ``execute_experiment.tpl``: A template shell script rendered to execute each experiment.

You can configure this experiment using the ``ramble workspace manage`` and ``ramble workspace concretize`` commands:

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/single_experiment_wrf_commands.sh
      :language: console

   Alternatively, you can edit the ``configs/ramble.yaml`` file directly to match the following configuration:

   .. literalinclude:: ../_generated/snippets/single_experiment_wrf_ramble.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/single_experiment_gromacs_commands.sh
      :language: console

   Alternatively, you can edit the ``configs/ramble.yaml`` file directly to match the following configuration:

   .. literalinclude:: ../_generated/snippets/single_experiment_gromacs_ramble.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/single_experiment_hpl_commands.sh
      :language: console

   Alternatively, you can edit the ``configs/ramble.yaml`` file directly to match the following configuration:

   .. literalinclude:: ../_generated/snippets/single_experiment_hpl_ramble.yaml
      :language: YAML

.. note::
   This workspace utilizes the ``spack`` package manager. As a result, it
   requires ``spack``. If ``spack`` is not installed and available in your
   ``PATH``, it will be bootstrapped for you. To see compilers already
   available to Spack, use ``spack compilers``.

The second file in the ``configs`` directory is the ``execute_experiment.tpl``
template file. It will be rendered into an execution script for each generated
experiment; for this tutorial, the default value will work.

Setting Up the Experiments
--------------------------

.. container:: tn-full-run-only

   Now that the workspace is configured correctly, you can set up the experiments
   in the active workspace using:

   .. code-block:: console

       $ ramble workspace setup

   This command will create experiment directories, download and expand input files,
   and install the required software stack.

   .. note::
      When not running in dry-run mode, ``ramble workspace setup`` may take a
      significant amount of time if the required software stack (such as the
      compiler, MPI library, or application package) is not already installed on
      your system and needs to be built from source, or when downloading larger
      input datasets (such as WRF's ``CONUS_12km`` input files).

      If you would like to quickly inspect what will be configured without
      downloading inputs or building software, enable **Dry-Run Mode** at the
      top of this tutorial or pass the ``--dry-run`` flag:

      .. code-block:: console

          $ ramble workspace setup --dry-run

.. container:: tn-dry-run-only

   With **Dry-Run Mode** enabled, set up the experiments in the active workspace
   using the ``--dry-run`` flag:

   .. code-block:: console

       $ ramble workspace setup --dry-run

   This command validates the workspace configuration, creates the experiment
   directories, and renders the execution scripts and software environment configs
   without downloading input files or building the software stack.

For each setup run, logs are created under:

.. code-block:: console

    $ $workspace_root/logs

While setup is running (or after it completes), you can inspect the experiment setup log:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       $ $RAMBLE_ROOT/var/ramble/workspaces/basic_wrf/logs/setup.latest/wrf.CONUS_12km.single_rank.out

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       $ $RAMBLE_ROOT/var/ramble/workspaces/basic_gromacs/logs/setup.latest/gromacs.water_bare.single_rank.out

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       $ $RAMBLE_ROOT/var/ramble/workspaces/basic_hpl/logs/setup.latest/hpl.calculator.single_rank.out

Executing Experiments
---------------------

.. container:: tn-full-run-only

   After the workspace is set up, its experiments can be executed. The two methods
   to run the experiments are:

   .. code-block:: console

       $ ramble on
      or;
       $ ./all_experiments

   .. note::
      Running ``ramble on`` executes the actual benchmark simulation on a single
      rank. Depending on the application workload (especially larger simulations
      like WRF ``CONUS_12km``) and your system's hardware, this step may take
      several minutes or longer to finish.

.. container:: tn-dry-run-only

   Because the workspace was set up with ``--dry-run``, we do **not** execute
   ``ramble on``. Instead, explore the generated experiment directory and inspect
   the rendered ``execute_experiment`` script to see how Ramble configured the
   execution environment and command line:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/basic_wrf/experiments/wrf/CONUS_12km/single_rank
          $ cat $RAMBLE_ROOT/var/ramble/workspaces/basic_wrf/experiments/wrf/CONUS_12km/single_rank/execute_experiment

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/basic_gromacs/experiments/gromacs/water_bare/single_rank
          $ cat $RAMBLE_ROOT/var/ramble/workspaces/basic_gromacs/experiments/gromacs/water_bare/single_rank/execute_experiment

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/basic_hpl/experiments/hpl/calculator/single_rank
          $ cat $RAMBLE_ROOT/var/ramble/workspaces/basic_hpl/experiments/hpl/calculator/single_rank/execute_experiment

Analyzing Experiments
---------------------

.. container:: tn-full-run-only

   Once the experiments within a workspace are complete, the experiments can be
   analyzed:

   .. code-block:: console

       $ ramble workspace analyze

   This creates a ``results`` file in the root of the workspace that contains
   extracted figures of merit. If the experiments were successful, this file will
   show the following results:

.. container:: tn-dry-run-only

   Because experiments are not executed in dry-run mode, ``ramble workspace analyze``
   is skipped.

   **Example Output (Full Run):**

   In a full run where ``ramble on`` and ``ramble workspace analyze`` are executed,
   Ramble creates a ``results.latest.txt`` file in the root of the workspace
   containing the following extracted figures of merit:

.. container:: tn-app-variant tn-app-wrf

   * Average Timestep Time: Time (in seconds) on average each timestep takes
   * Cumulative Timestep Time: Time (in seconds) spent executing all timesteps
   * Minimum Timestep Time: Minimum time (in seconds) spent on any one timestep
   * Maximum Timestep Time: Maximum time (in seconds) spent on any one timestep
   * Number of timesteps: Count of total timesteps performed
   * Avg. Max Ratio Time: Ratio of Average Timestep Time and Maximum Timestep Time

.. container:: tn-app-variant tn-app-gromacs

   * Core Time: CPU time (in seconds) spent on the benchmark calculations
   * Wall Time: Elapsed real time (in seconds) spent on the benchmark calculations
   * Percent Core Time: Core Time / Wall Time
   * Nanosecs per day: Nanoseconds of simulation per day at the speed achieved
   * Hours per nanosec: Hours required to calculate 1 nanosecond of simulation at
     the speed achieved

.. container:: tn-app-variant tn-app-hpl

   * Time: Linpack problem execution time (in seconds)
   * GFlops: Rate of execution (in GFLOP/s)


Workspace Directory Structure
-----------------------------

After analyzing the workspace, you can examine its structure:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       $ ls $RAMBLE_ROOT/var/ramble/workspaces/basic_wrf

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       $ ls $RAMBLE_ROOT/var/ramble/workspaces/basic_gromacs

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       $ ls $RAMBLE_ROOT/var/ramble/workspaces/basic_hpl

Within this directory, you should see the following directories:

* ``configs`` - Contains all configuration files for the workspace
* ``experiments`` - Contains experiment execution directories
* ``inputs`` - Contains input files needed for the experiments
* ``logs`` - Contains log files from any Ramble command acting on the workspace
* ``shared`` - Contains auxiliary files such as environment variable scripts
* ``software`` - Contains software environments for the experiments

Cleanup the Workspace
---------------------

.. container:: tn-workspace-cleanup

   Once you are finished with the tutorial content, ensure you have deactivated
   the workspace:

   .. code-block:: console

       $ ramble workspace deactivate

   Additionally, you can remove the workspace using:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace remove basic_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace remove basic_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace remove basic_hpl

