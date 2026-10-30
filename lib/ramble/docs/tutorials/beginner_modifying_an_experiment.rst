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

.. tutorial-header:: modify_experiment

In this tutorial, you will learn how to modify an existing workspace
configuration that contains experiments.


.. note::
  This tutorial builds off of concepts introduced in previous tutorials. It uses the workspace configured in :ref:`Creating a Single Experiment Workspace <running_an_experiment_tutorial>`.

Activate the Workspace
----------------------

.. tutorial-workspace-create:: basic
   :activate-only:

Experiment Descriptions
-----------------------

Now that your workspace is active, execute the following command to see what
experiments the workspace currently contains:

.. code-block:: console

    $ ramble workspace info

This command provides a summary view of the workspace. Its output might look like:

.. tutorial-snippet:: modify_experiment workspace_info.out

To get detailed information about where variable definitions come from, you can use:

.. code-block:: console

    $ ramble workspace info --expansions

The output of this command displays variables defined at the workspace scope
and at the experiment scope. Note that workspace-level variables can be defined
using ``ramble config add variables:<name>:<value>`` while your workspace is active,
or by editing the ``variables:`` section of ``configs/ramble.yaml`` directly:

.. tutorial-snippet:: modify_experiment workspace_info_expansions_initial.out

Using Workload Variables
------------------------

Application definitions can expose variables that control the execution and
parameters of experiments. These are called **workload variables**. You can view
available workload variables with the ``ramble info`` command:

.. tutorial-app-template::

   .. literalinclude:: /_generated/snippets/modify_experiment_{app}_info_workload_cmd.sh
      :language: console

   This will show variables supported by the ``{workload}`` workload:

   .. literalinclude:: /_generated/snippets/modify_experiment_{app}_info_workload.out
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

.. tutorial-app-template::
   :wrf: desc=For WRF, let's modify the workload ``num_tiles`` variable from ``1`` to ``2`` to adjust the domain decomposition (and enable the ``wrf_tiles`` variant via ``-V wrf_tiles=true``):
   :gromacs: desc=For GROMACS, let's modify the workload ``size`` variable from ``0003`` to ``0006``:
   :hpl: desc=For HPL, let's modify the workload ``percent_mem`` variable from ``85`` to ``80``:

   {desc}

   .. literalinclude:: /_generated/snippets/modify_experiment_{app}_commands.sh
      :language: console

   Alternatively, editing ``configs/ramble.yaml`` directly results in:

   .. literalinclude:: /_generated/snippets/modify_experiment_{app}_ramble.yaml
      :language: YAML

After saving your changes, verify that the modified variables are reflected in the expansions output:

.. code-block:: console

    $ ramble workspace info --expansions

.. tutorial-snippet:: modify_experiment workspace_info_expansions_modified.out

Executing Experiments
---------------------

.. tutorial-execute:: basic
   :dry-run-cmds: ls -la $RAMBLE_ROOT/var/ramble/workspaces/basic_{app}/experiments/{app}/{workload}/; cat $RAMBLE_ROOT/var/ramble/workspaces/basic_{app}/experiments/{app}/{workload}/serial_{workload}/execute_experiment; cat $RAMBLE_ROOT/var/ramble/workspaces/basic_{app}/experiments/{app}/{workload}/distributed_{workload}/execute_experiment
   :include-foms:

.. container:: tn-full-run-only

   You can compare this new ``results`` file with your results from the
   :ref:`previous tutorial <running_an_experiment_tutorial>` to see the impact of
   your modifications on performance figures of merit.


Cleaning the Workspace
----------------------

.. tutorial-workspace-cleanup:: basic

