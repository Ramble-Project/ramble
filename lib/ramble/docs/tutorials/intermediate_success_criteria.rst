.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _success-criteria_tutorial:

================
Success Criteria
================

.. raw:: html

   <div class="tn-app-switcher" data-recipe="success_criteria"></div>

In this tutorial, you will learn how to use success criteria to validate experiments.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

Create a Workspace
------------------

.. container:: tn-workspace-create

   To begin with, you need a workspace to configure the experiments. This can be
   created with the following command:

   .. container:: tn-app-variant tn-app-container tn-app-wrf

      .. code-block:: console

          $ ramble workspace create success_wrf

   .. container:: tn-app-variant tn-app-container tn-app-gromacs

      .. code-block:: console

          $ ramble workspace create success_gromacs

   .. container:: tn-app-variant tn-app-container tn-app-hpl

      .. code-block:: console

          $ ramble workspace create success_hpl


   .. rubric:: Activate the Workspace

   Several of Ramble's commands require an activated workspace to function
   properly. Activate the newly created workspace using the following command:

   .. note::
      You only need to run this if you do not currently have the workspace active.

   .. container:: tn-app-variant tn-app-container tn-app-wrf

      .. code-block:: console

          $ ramble workspace activate success_wrf

   .. container:: tn-app-variant tn-app-container tn-app-gromacs

      .. code-block:: console

          $ ramble workspace activate success_gromacs

   .. container:: tn-app-variant tn-app-container tn-app-hpl

      .. code-block:: console

          $ ramble workspace activate success_hpl

Configure Experiment Definitions
--------------------------------

To begin with, you need to configure the workspace. Within the ``ramble.yaml``
file, write the following contents, which represents the scaling study
configuration from previous tutorials:

.. container:: tn-app-variant tn-app-container tn-app-wrf

   .. literalinclude:: ../_generated/snippets/success_criteria_wrf_base.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-container tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/success_criteria_gromacs_base.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-container tn-app-hpl

   .. literalinclude:: ../_generated/snippets/success_criteria_hpl_base.yaml
      :language: YAML

Success Criteria
----------------

Ramble provides you with the ability to define success criteria within an
application's ``application.py`` file, or within the ``success_criteria``
configuration scope (which can also be defined in a workspace's ``ramble.yaml``
configuration file). There are three supported types of success criteria,
including:

 #. Regular Expression String Matching
 #. Figure of Merit Logic Based
 #. Arbitrary Python Based

This tutorial will focus on the first two of these, as the third can only be
defined within the ``application.py`` file.

For more in-depth documentation about success criteria, see
:ref:`success-criteria`.

Regular Expression String Matching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most common success criteria is regular expression based string
matching. These can be defined within either the ``application.py`` or the
``success_criteria`` configuration scope. Several ``application.py`` files
already define this type of success criteria in order to make it easier for
users to be sure their experiments completed successfully.

.. container:: tn-app-variant tn-app-container tn-app-wrf

   When WRF runs, it outputs the time each timestep takes. To begin with, you will
   define a new success criteria within your workspace configuration file that
   validates some timing data is present in the output of an experiment. In the
   experiment output, the timing data is prefixed with the string
   ``Timing for main``.

   This success criteria might look like the following:

   .. code-block:: YAML

       success_criteria:
       - name: 'timing-present'
         mode: 'string'
         match: 'Timing for main.*'
         file: '{experiment_run_dir}/rsl.out.base'

   Edit your workspace configuration file with:

   .. code-block:: console

       $ ramble workspace edit

   And add the example block within the ``wrf@4.2`` application block. The resulting
   configuration file might look like the following:

   .. literalinclude:: ../_generated/snippets/success_criteria_wrf_regex_criteria.yaml
      :language: YAML

   Placing the success criteria definition here applies it to all of the
   experiments defined within the ``wrf@4.2`` application.

.. container:: tn-app-variant tn-app-container tn-app-gromacs

   When GROMACS runs, it writes detailed simulation logs to ``md.log``. To begin with,
   you will define a new success criteria within your workspace configuration file that
   validates the simulation completed successfully by matching the completion string
   in the log file.

   This success criteria might look like the following:

   .. code-block:: YAML

       success_criteria:
       - name: 'mdrun-finished'
         mode: 'string'
         match: 'Finished mdrun.*'
         file: '{experiment_run_dir}/md.log'

   Edit your workspace configuration file with:

   .. code-block:: console

       $ ramble workspace edit

   And add the example block within the ``gromacs@2025.3`` application block. The resulting
   configuration file might look like the following:

   .. literalinclude:: ../_generated/snippets/success_criteria_gromacs_regex_criteria.yaml
      :language: YAML

   Placing the success criteria definition here applies it to all of the
   experiments defined within the ``gromacs@2025.3`` application.

.. container:: tn-app-variant tn-app-container tn-app-hpl

   When HPL runs, it outputs test validation results. To begin with, you will define
   a new success criteria within your workspace configuration file that validates
   the benchmark passed by matching the completion string ``PASSED`` in ``HPL.out``.

   This success criteria might look like the following:

   .. code-block:: YAML

       success_criteria:
       - name: 'passed'
         mode: 'string'
         match: '.*PASSED.*'
         file: '{experiment_run_dir}/HPL.out'

   Edit your workspace configuration file with:

   .. code-block:: console

       $ ramble workspace edit

   And add the example block within the ``hpl@2.3`` application block. The resulting
   configuration file might look like the following:

   .. literalinclude:: ../_generated/snippets/success_criteria_hpl_regex_criteria.yaml
      :language: YAML

   Placing the success criteria definition here applies it to all of the
   experiments defined within the ``hpl@2.3`` application.

Figure of Merit Logic Based
~~~~~~~~~~~~~~~~~~~~~~~~~~~

In addition to string matching, Ramble allows you to define figure of merit
based success criteria. These success criteria can be defined as equations that
include placeholders for figures of merit the application will generate.

.. container:: tn-app-variant tn-app-container tn-app-wrf

   In this portion of the tutorial, you will define a new success criteria that
   ensures the experiments all have at least 50 timesteps to be considered
   successful. The figure of merit definition for this might look like the following:

   .. code-block:: YAML

       success_criteria:
       - name: 'correct-timesteps'
         mode: 'fom_comparison'
         fom_name: 'Number of timesteps'
         formula: '{value} >= 50'

   Edit your workspace configuration using:

   .. code-block:: console

       $ ramble workspace edit

   And add the success criteria within the ``CONUS_12km`` workload definition. The
   resulting configuration file might look like the following:

   .. literalinclude:: ../_generated/snippets/success_criteria_wrf_fom_criteria.yaml
      :language: YAML

   This new success criteria will apply to all experiments within the
   ``CONUS_12km`` workload. This is because different workloads could have
   different numbers of timesteps.

   It is important to note that the ``formula`` attribute of the success criteria
   definition can refer to other variables. As an example, one of the figures of
   merit output by the ``wrf@4.2`` application definition is
   ``Average Timestep Time``. If you had a single node value for this figure of
   merit and expected this to scale linearly you could define a success criteria
   as follows:

   .. code-block:: YAML

       variables:
         single_node_value: '1.0'
       success_criteria:
       - name: 'valid-scaling'
         mode: 'fom_comparison'
         fom_name: 'Average Timestep Time'
         formula: '{value} <= {single_node_value} / {n_nodes}'

   You won't test this success criteria in this tutorial, as the
   ``single_node_value`` might not be correct for your system, but feel free to
   explore using this after you perform experiments.

.. container:: tn-app-variant tn-app-container tn-app-gromacs

   In this portion of the tutorial, you will define a new success criteria that
   ensures the experiments complete within an expected wallclock threshold
   (e.g., at most 300 seconds) to be considered successful. The figure of merit
   definition for this might look like the following:

   .. code-block:: YAML

       success_criteria:
       - name: 'max-walltime'
         mode: 'fom_comparison'
         fom_name: 'Wall Time'
         formula: '{value} <= 300'

   Edit your workspace configuration using:

   .. code-block:: console

       $ ramble workspace edit

   And add the success criteria within the ``water_bare`` workload definition. The
   resulting configuration file might look like the following:

   .. literalinclude:: ../_generated/snippets/success_criteria_gromacs_fom_criteria.yaml
      :language: YAML

   This new success criteria will apply to all experiments within the
   ``water_bare`` workload.

   It is important to note that the ``formula`` attribute of the success criteria
   definition can refer to other variables. As an example, one of the figures of
   merit output by the ``gromacs@2025.3`` application definition is
   ``Wall Time``. If you had a single node value for this figure of
   merit and expected this to scale linearly you could define a success criteria
   as follows:

   .. code-block:: YAML

       variables:
         single_node_value: '100.0'
       success_criteria:
       - name: 'valid-scaling'
         mode: 'fom_comparison'
         fom_name: 'Wall Time'
         formula: '{value} <= {single_node_value} / {n_nodes}'

   You won't test this success criteria in this tutorial, as the
   ``single_node_value`` might not be correct for your system, but feel free to
   explore using this after you perform experiments.

.. container:: tn-app-variant tn-app-container tn-app-hpl

   In this portion of the tutorial, you will define a new success criteria that
   ensures the experiments achieve an expected performance threshold (e.g., at
   least 1.0 GFLOP/s) to be considered successful. The figure of merit definition
   for this might look like the following:

   .. code-block:: YAML

       success_criteria:
       - name: 'min-gflops'
         mode: 'fom_comparison'
         fom_name: 'GFlops'
         formula: '{value} >= 1.0'

   Edit your workspace configuration using:

   .. code-block:: console

       $ ramble workspace edit

   And add the success criteria within the ``calculator`` workload definition. The
   resulting configuration file might look like the following:

   .. literalinclude:: ../_generated/snippets/success_criteria_hpl_fom_criteria.yaml
      :language: YAML

   This new success criteria will apply to all experiments within the
   ``calculator`` workload.

   It is important to note that the ``formula`` attribute of the success criteria
   definition can refer to other variables. As an example, one of the figures of
   merit output by the ``hpl@2.3`` application definition is
   ``GFlops``. If you had a single node value for this figure of
   merit and expected this to scale linearly you could define a success criteria
   as follows:

   .. code-block:: YAML

       variables:
         single_node_value: '10.0'
       success_criteria:
       - name: 'valid-scaling'
         mode: 'fom_comparison'
         fom_name: 'GFlops'
         formula: '{value} >= {single_node_value} * {n_nodes}'

   You won't test this success criteria in this tutorial, as the
   ``single_node_value`` might not be correct for your system, but feel free to
   explore using this after you perform experiments.

Execute Experiments
-------------------

.. container:: tn-full-run-only

   .. note::
      This workspace uses the ``spack`` package manager. ``spack`` can either be
      installed in your ``PATH``, or Ramble will automatically bootstrap it for you
      during ``ramble workspace setup``. See the `Spack Getting Started Guide
      <https://spack.readthedocs.io/en/latest/getting_started.html>`_ for more
      information on Spack.

   .. note::
      When not running in dry-run mode, ``ramble workspace setup`` may take a long
      time if the required software stack is not already installed on your system,
      and ``ramble on`` will execute the multi-node scaling study workloads, which
      can also take a while to complete. You can enable **Dry-Run Mode** at the top
      of this tutorial or pass ``--dry-run`` to ``ramble workspace setup`` to skip
      building software and running the experiments.

   To test the success criteria, execute the workspace experiments:

   .. code-block:: console

       $ ramble workspace setup
       $ ramble on
       $ ramble workspace analyze

   To ensure the success criteria are checked and the experiments pass them,
   ensure ``SUCCESS`` is printed for the status of each experiment.

   Running analyze in debug mode as:

   .. code-block:: console

       $ ramble -d workspace analyze

   will print significantly more output, but you should see where Ramble tests the
   configured success criteria in the output.

.. container:: tn-dry-run-only

   With **Dry-Run Mode** enabled, set up the workspace using ``--dry-run``:

   .. code-block:: console

       $ ramble workspace setup --dry-run

   Because we are running in dry-run mode, we do **not** execute ``ramble on`` or
   ``ramble workspace analyze``. Instead, explore the generated experiment directories
   under ``experiments/`` and inspect the rendered ``execute_experiment`` scripts:

   .. container:: tn-app-variant tn-app-container tn-app-wrf

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/success_wrf/experiments/wrf/CONUS_12km/

   .. container:: tn-app-variant tn-app-container tn-app-gromacs

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/success_gromacs/experiments/gromacs/water_bare/

   .. container:: tn-app-variant tn-app-container tn-app-hpl

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/success_hpl/experiments/hpl/calculator/

   **Example Output (Full Run):**

   In a full run where ``ramble on`` and ``ramble workspace analyze`` are executed,
   Ramble evaluates every configured success criterion (both application-defined and
   custom ``fom_comparison`` / ``string`` criteria) and prints ``SUCCESS`` (or ``FAILED``)
   for the status of each experiment in ``results.latest.txt``. Running
   ``ramble -d workspace analyze`` in a full run prints detailed debug messages showing
   each success criterion evaluation.


Clean the Workspace
-------------------

.. container:: tn-workspace-cleanup

   Once you are finished with the tutorial content, make sure you deactivate your workspace:

   .. code-block:: console

       $ ramble workspace deactivate

   Additionally, you can remove the workspace and all of its content with:

   .. container:: tn-app-variant tn-app-container tn-app-wrf

      .. code-block:: console

          $ ramble workspace remove success_wrf

   .. container:: tn-app-variant tn-app-container tn-app-gromacs

      .. code-block:: console

          $ ramble workspace remove success_gromacs

   .. container:: tn-app-variant tn-app-container tn-app-hpl

      .. code-block:: console

          $ ramble workspace remove success_hpl

