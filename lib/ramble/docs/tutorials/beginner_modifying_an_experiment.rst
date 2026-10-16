.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _modifying_a_gromacs_experiment_tutorial:
.. _modifying_an_experiment_tutorial:

=======================
Modifying an Experiment
=======================

In this tutorial, you will learn how to modify an existing workspace
configuration that contains experiments. This tutorial supports multiple
applications (such as WRF, GROMACS, and HPL); you can select your preferred application below.

.. raw:: html

   <div class="tn-app-switcher" data-recipe="modify_experiment"></div>


.. note::
  This tutorial builds off of concepts introduced in previous tutorials. It uses the workspace configured in :ref:`Creating a Single Experiment Workspace <running_an_experiment_tutorial>`.

Activate the Workspace
----------------------

.. container:: tn-workspace-create

   Ensure your workspace is activated before continuing:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace activate basic_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace activate basic_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace activate basic_hpl

Experiment Descriptions
-----------------------

Now that your workspace is active, execute the following command to see what
experiments the workspace currently contains:

.. code-block:: console

    $ ramble workspace info

This command provides a summary view of the workspace. Its output might look like:

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/modify_experiment_wrf_workspace_info.out
      :language: console

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/modify_experiment_gromacs_workspace_info.out
      :language: console

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/modify_experiment_hpl_workspace_info.out
      :language: console

To get detailed information about where variable definitions come from, you can use:

.. code-block:: console

    $ ramble workspace info --expansions

The output of this command displays variables defined at the workspace scope
and at the experiment scope. Note that workspace-level variables can be defined
using ``ramble config add variables:<name>:<value>`` while your workspace is active,
or by editing the ``variables:`` section of ``configs/ramble.yaml`` directly:

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/modify_experiment_wrf_workspace_info_expansions_initial.out
      :language: console

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/modify_experiment_gromacs_workspace_info_expansions_initial.out
      :language: console

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/modify_experiment_hpl_workspace_info_expansions_initial.out
      :language: console

Using Workload Variables
------------------------

Application definitions can expose variables that control the execution and
parameters of experiments. These are called **workload variables**. You can view
available workload variables with the ``ramble info`` command:

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/modify_experiment_wrf_info_workload_cmd.sh
      :language: console

   This will show variables supported by the ``CONUS_12km`` workload:

   .. literalinclude:: ../_generated/snippets/modify_experiment_wrf_info_workload.out
      :language: console

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/modify_experiment_gromacs_info_workload_cmd.sh
      :language: console

   This will show variables supported by the ``water_bare`` workload:

   .. literalinclude:: ../_generated/snippets/modify_experiment_gromacs_info_workload.out
      :language: console

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/modify_experiment_hpl_info_workload_cmd.sh
      :language: console

   This will show variables supported by the ``calculator`` workload:

   .. literalinclude:: ../_generated/snippets/modify_experiment_hpl_info_workload.out
      :language: console

Within this output, the default value for workload variables can be seen. While
this is provided in the application definition, users are free to override
these values within their individual experiments.

   .. note::
      Within each workload, some variables provide ``Suggested Values`` indicating
      parameter values that are either expected to work, or the application is
      constrained to use. 

Editing Experiments
-------------------

You can edit experiments either by using ``ramble workspace manage experiments`` with the
``--overwrite`` flag, or by editing ``configs/ramble.yaml`` directly using your editor:

.. code-block:: console

    $ ramble workspace edit

.. container:: tn-app-variant tn-app-wrf

   For WRF, let's modify the workload ``num_tiles`` variable from ``1`` to ``2`` to adjust the domain decomposition (and enable the ``wrf_tiles`` variant via ``-V wrf_tiles=true``):

   .. literalinclude:: ../_generated/snippets/modify_experiment_wrf_commands.sh
      :language: console

   Alternatively, editing ``configs/ramble.yaml`` directly results in:

   .. literalinclude:: ../_generated/snippets/modify_experiment_wrf_ramble.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-gromacs

   For GROMACS, let's modify the workload ``size`` variable from ``0003`` to ``0006``:

   .. literalinclude:: ../_generated/snippets/modify_experiment_gromacs_commands.sh
      :language: console

   Alternatively, editing ``configs/ramble.yaml`` directly results in:

   .. literalinclude:: ../_generated/snippets/modify_experiment_gromacs_ramble.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-hpl

   For HPL, let's modify the workload ``percent_mem`` variable from ``85`` to ``80``:

   .. literalinclude:: ../_generated/snippets/modify_experiment_hpl_commands.sh
      :language: console

   Alternatively, editing ``configs/ramble.yaml`` directly results in:

   .. literalinclude:: ../_generated/snippets/modify_experiment_hpl_ramble.yaml
      :language: YAML

After saving your changes, verify that the modified variables are reflected in the expansions output:

.. code-block:: console

    $ ramble workspace info --expansions

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/modify_experiment_wrf_workspace_info_expansions_modified.out
      :language: console

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/modify_experiment_gromacs_workspace_info_expansions_modified.out
      :language: console

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/modify_experiment_hpl_workspace_info_expansions_modified.out
      :language: console

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

      * ``ramble workspace setup`` will build the required software stack from
        source if it is not already installed on your system, and download any
        new workload input archives.
      * ``ramble on`` executes the modified workload (such as the larger ``0006``
        problem size in GROMACS or modified tiling in WRF), which can take longer
        to run than the default configuration.

      You can optionally enable **Dry-Run Mode** at the top of this tutorial or pass the
      ``--dry-run`` flag to setup (``ramble workspace setup --dry-run``) to quickly
      generate and inspect the experiment directories without building software or
      running the experiments.

   Now that you have made the appropriate modifications, set up, execute, and
   analyze the updated experiments:

   .. code-block:: console

       $ ramble workspace setup
       $ ramble on
       $ ramble workspace analyze

   This creates or updates the ``results`` file in the root of the workspace.
   If the experiments were successful, this file will contain extracted figures of merit:

.. container:: tn-dry-run-only

   With **Dry-Run Mode** enabled, set up the modified experiments using ``--dry-run``:

   .. code-block:: console

       $ ramble workspace setup --dry-run

   Because we are running in dry-run mode, we do **not** execute ``ramble on`` or
   ``ramble workspace analyze``. Instead, explore the generated experiment directories
   and compare the rendered ``execute_experiment`` scripts between the ``serial_*`` and
   ``distributed_*`` experiments:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/basic_wrf/experiments/wrf/CONUS_12km/
          $ cat $RAMBLE_ROOT/var/ramble/workspaces/basic_wrf/experiments/wrf/CONUS_12km/serial_CONUS_12km/execute_experiment
          $ cat $RAMBLE_ROOT/var/ramble/workspaces/basic_wrf/experiments/wrf/CONUS_12km/distributed_CONUS_12km/execute_experiment

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/basic_gromacs/experiments/gromacs/water_bare/
          $ cat $RAMBLE_ROOT/var/ramble/workspaces/basic_gromacs/experiments/gromacs/water_bare/serial_water_bare/execute_experiment
          $ cat $RAMBLE_ROOT/var/ramble/workspaces/basic_gromacs/experiments/gromacs/water_bare/distributed_water_bare/execute_experiment

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/basic_hpl/experiments/hpl/calculator/
          $ cat $RAMBLE_ROOT/var/ramble/workspaces/basic_hpl/experiments/hpl/calculator/serial_calculator/execute_experiment
          $ cat $RAMBLE_ROOT/var/ramble/workspaces/basic_hpl/experiments/hpl/calculator/distributed_calculator/execute_experiment

   **Example Output (Full Run):**

   In a full run where ``ramble on`` and ``ramble workspace analyze`` are executed,
   Ramble extracts the following figures of merit into ``results.latest.txt`` for each
   experiment:

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

.. container:: tn-full-run-only

   You can compare this new ``results`` file with your results from the
   :ref:`previous tutorial <running_an_experiment_tutorial>` to see the impact of
   your modifications on performance figures of merit.


Cleaning the Workspace
----------------------

.. container:: tn-workspace-cleanup

   After you are finished with this tutorial, deactivate your workspace:

   .. code-block:: console

       $ ramble workspace deactivate

   If you no longer need the workspace materials, remove the entire workspace with:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace remove basic_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace remove basic_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace remove basic_hpl
