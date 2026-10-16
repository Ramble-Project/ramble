.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _internals_tutorial:

=========
Internals
=========

.. raw:: html

   <div class="tn-app-switcher" data-recipe="using_internals"></div>

In this tutorial, you will learn how to use ``internals`` within experiments to
define custom executables and control their execution order.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

Create a Workspace
------------------

.. container:: tn-workspace-create

   To begin with, you need a workspace to configure the experiments. This can be
   created with the following command:

   .. container:: tn-app-variant tn-app-container tn-app-wrf

      .. code-block:: console

          $ ramble workspace create internals_wrf

   .. container:: tn-app-variant tn-app-container tn-app-gromacs

      .. code-block:: console

          $ ramble workspace create internals_gromacs

   .. container:: tn-app-variant tn-app-container tn-app-hpl

      .. code-block:: console

          $ ramble workspace create internals_hpl

   .. rubric:: Activate the Workspace

   Several of Ramble's commands require an activated workspace to function
   properly. Activate the newly created workspace using the following command:

   .. note::

      You only need to run this if you do not currently have the workspace
      active.

   .. container:: tn-app-variant tn-app-container tn-app-wrf

      .. code-block:: console

          $ ramble workspace activate internals_wrf

   .. container:: tn-app-variant tn-app-container tn-app-gromacs

      .. code-block:: console

          $ ramble workspace activate internals_gromacs

   .. container:: tn-app-variant tn-app-container tn-app-hpl

      .. code-block:: console

          $ ramble workspace activate internals_hpl

Configure Experiment Definitions
--------------------------------

To begin with, you need to configure the workspace. Within the ``ramble.yaml``
file, write the following contents, which represents the scaling study
configuration from previous tutorials:

.. container:: tn-app-variant tn-app-container tn-app-wrf

   .. literalinclude:: ../_generated/snippets/using_internals_wrf_base.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-container tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/using_internals_gromacs_base.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-container tn-app-hpl

   .. literalinclude:: ../_generated/snippets/using_internals_hpl_base.yaml
      :language: YAML

Experiment Internals
--------------------

In Ramble, the concept of ``internals`` allows a user to override some aspects
of a workload within the workspace configuration file. More information about
``internals`` can be seen at :ref:`workspace_internals`.

The ``internals`` block within a workspace configuration file can be used to
define custom executables, and control the order of executables within an
experiment.

In this tutorial, you will define new executables for tracking the start and
end timestamp of each experiment, and properly inject these into the experiment
order.

Define New Executables
~~~~~~~~~~~~~~~~~~~~~~

The definition of a new executable lives within an ``internals`` block. Below
is an example of defining a new executable called ``start_time`` which is time
in seconds since the Unix epoch (1970-01-01 00:00 UTC):

.. code-block:: YAML

    internals:
      custom_executables:
        start_time:
          template:
          - 'date +%s'
          use_mpi: false
          redirect: '{experiment_run_dir}/start_time'

Within this ``start_time`` definition, the ``template`` attribute takes a list
of strings which will be injected as part of this executable. The ``use_mpi``
attribute tells Ramble whether to apply the ``mpi_command`` variable
definition as a prefix to every entry of the ``template`` attribute. The
``redirect`` attribute defines the file each portion of ``template`` should be
redirected into.

Not shown above is the ``output_capture`` attribute, which defines the operator
used for capturing the output from the portions of ``template`` (the default is
``&>``).

By default, this would define the actual command to be:

.. code-block:: console

    date +%s &> {experiment_run_dir}/start_time

Edit your workspace configuration file using:

.. code-block:: console

    $ ramble workspace edit

Within this file, use the example above to define two new executables
``start_time`` and ``end_time``. Make sure you change the value of ``redirect``
in the ``end_time`` executable definition. The resulting file should look like
the following:

.. container:: tn-app-variant tn-app-container tn-app-wrf

   .. literalinclude:: ../_generated/snippets/using_internals_wrf_new_exec.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-container tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/using_internals_gromacs_new_exec.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-container tn-app-hpl

   .. literalinclude:: ../_generated/snippets/using_internals_hpl_new_exec.yaml
      :language: YAML

Defining Executable Order
~~~~~~~~~~~~~~~~~~~~~~~~~

At this point, ``start_time`` and ``end_time`` are defined as new executables,
however they are not added to your experiments. To verify this, execute:

.. code-block:: console

    $ ramble workspace setup --dry-run

and examine the ``execute_experiment`` scripts in your experiment directories.
``date +%s`` should not be present in any of these. To fix this issue, we need
to modify the order of the executables for the workload your experiments are
using.

Currently, when controlling the order of executables, the entire order of
executables must be defined. To see the current list of executables for your
experiments, execute:

.. container:: tn-app-variant tn-app-container tn-app-wrf

   .. code-block:: console

       $ ramble info --attrs workloads -v -p "CONUS_12km" wrf

   This prints the information for the ``CONUS_12km`` workload in the WRF application definition.
   The ``Executables:`` definition lists the order of executables used for this workload:

   .. code-block:: console

       Executables: ['stage-files', 'stage-namelist', 'cleanup', 'define_nproc_y', 'define_nproc_x', 'fix_12km_start_hour', 'fix_12km_restart', 'execute', 'copy-logs', 'post-exec-clean']

.. container:: tn-app-variant tn-app-container tn-app-gromacs

   .. code-block:: console

       $ ramble info --attrs workloads -v -p "water_bare" gromacs

   This prints the information for the ``water_bare`` workload in the GROMACS application definition.
   The ``Executables:`` definition lists the order of executables used for this workload:

   .. code-block:: console

       Executables: ['print-binary-info', 'pre-process', 'execute-gen']

.. container:: tn-app-variant tn-app-container tn-app-hpl

   .. code-block:: console

       $ ramble info --attrs workloads -v -p "calculator" hpl

   This prints the information for the ``calculator`` workload in the HPL application definition.
   The ``Executables:`` definition lists the order of executables used for this workload:

   .. code-block:: console

       Executables: ['execute']

Some executables are provided through the ``builtin`` functionality. These are
executable commands that are injected by default from the object definitions.
To be able to see these, you can execute:

.. container:: tn-app-variant tn-app-container tn-app-wrf

   .. code-block:: console

       $ ramble info --attrs builtins -v wrf

   This command should print something like the following:

   .. code-block:: console

       ############
       # builtins #
       ############
       builtin::pre_cleanup:
           name: pre_cleanup
           required: True
           injection_method: prepend
           depends_on: []
           dependents: []
           when: []

       builtin::post_cleanup:
           name: post_cleanup
           required: True
           injection_method: append
           depends_on: []
           dependents: []
           when: []

       builtin::env_vars:
           name: env_vars
           required: True
           injection_method: prepend
           depends_on: []
           dependents: []
           when: []

.. container:: tn-app-variant tn-app-container tn-app-gromacs

   .. code-block:: console

       $ ramble info --attrs builtins -v gromacs

   This command should print something like the following:

   .. code-block:: console

       ############
       # builtins #
       ############
       builtin::pre_cleanup:
           name: pre_cleanup
           required: True
           injection_method: prepend
           depends_on: []
           dependents: []
           when: []

       builtin::post_cleanup:
           name: post_cleanup
           required: True
           injection_method: append
           depends_on: []
           dependents: []
           when: []

       builtin::env_vars:
           name: env_vars
           required: True
           injection_method: prepend
           depends_on: []
           dependents: []
           when: []

.. container:: tn-app-variant tn-app-container tn-app-hpl

   .. code-block:: console

       $ ramble info --attrs builtins -v hpl

   This command should print something like the following:

   .. code-block:: console

       ############
       # builtins #
       ############
       builtin::pre_cleanup:
           name: pre_cleanup
           required: True
           injection_method: prepend
           depends_on: []
           dependents: []
           when: []

       builtin::post_cleanup:
           name: post_cleanup
           required: True
           injection_method: append
           depends_on: []
           dependents: []
           when: []

       builtin::env_vars:
           name: env_vars
           required: True
           injection_method: prepend
           depends_on: []
           dependents: []
           when: []

Now, edit the workspace configuration file with:

.. code-block:: console

    $ ramble workspace edit

And define the order of the executables for your experiments to include
``start_time`` and ``end_time`` in the correct locations. To do this, add an
``executables`` attribute to the ``internals`` dictionary. The contents of
``executables`` are a list of executable names provided in the order you
want them to be executed.

For the purposes of this tutorial, add ``start_time`` directly before the main
execution command and ``end_time`` directly after it. The resulting configuration
file should look like the following:

.. container:: tn-app-variant tn-app-container tn-app-wrf

   .. literalinclude:: ../_generated/snippets/using_internals_wrf_exec_order.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-container tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/using_internals_gromacs_exec_order.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-container tn-app-hpl

   .. literalinclude:: ../_generated/snippets/using_internals_hpl_exec_order.yaml
      :language: YAML

.. note::
   Omitting any executables from the ``executables`` list will
   prevent it from being used in the generated experiments.

Execute Experiments
~~~~~~~~~~~~~~~~~~~

.. container:: tn-full-run-only

   .. note::
      This workspace uses the ``spack`` package manager to build the software stack
      and MPI implementation. ``spack`` can either be installed in your ``PATH``, or
      Ramble will automatically bootstrap it for you.

   .. note::
      When not running in dry-run mode, ``ramble workspace setup`` can take a long
      time if the software stack is not already installed on your system, and
      ``ramble on`` will execute the scaling study workloads across multiple node
      counts, which may also take a while. To skip software installation and
      execution, you can enable **Dry-Run Mode** in the configuration card at the
      top of this page to use ``ramble workspace setup --dry-run`` instead.

   Now set up and execute the experiments:

   .. code-block:: console

       $ ramble workspace setup
       $ ramble on

   Examining the experiment run directories, you should see ``start_time`` and
   ``end_time`` files which contain the output of our custom executables.

.. container:: tn-dry-run-only

   Since **Dry-Run Mode** is enabled, set up the workspace using ``--dry-run``
   without executing ``ramble on``:

   .. code-block:: console

       $ ramble workspace setup --dry-run

   Instead of executing the experiments, explore the generated experiment directories
   and examine the rendered ``execute_experiment`` scripts to verify that ``date +%s``
   is now redirected into ``start_time`` before the main executable and ``end_time``
   after it:

   .. container:: tn-app-variant tn-app-container tn-app-wrf

      .. code-block:: console

          $ grep "date +%s" $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/wrf/CONUS_12km/*/execute_experiment

   .. container:: tn-app-variant tn-app-container tn-app-gromacs

      .. code-block:: console

          $ grep "date +%s" $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/gromacs/water_bare/*/execute_experiment

   .. container:: tn-app-variant tn-app-container tn-app-hpl

      .. code-block:: console

          $ grep "date +%s" $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/hpl/calculator/*/execute_experiment

   If you were to execute the experiments in a full run, each experiment run
   directory would contain ``start_time`` and ``end_time`` files with the Unix
   epoch timestamps produced by our custom executables.

Using Executable Injection
--------------------------

In addition to the full explicit method of injecting an executable shown above,
you can inject executables relative to existing executables in the experiment's
executable list. This is documented in the :ref:`internals config
section<internals-config>` and :ref:`workspace internals<workspace_internals>`
documentation sections.

As an example, the following YAML could replace the ``executables`` section of
your existing configuration:

.. container:: tn-app-variant tn-app-container tn-app-wrf

   .. code-block:: YAML

       executable_injection:
       - name: start_time
         order: before
         relative_to: execute
       - name: end_time
         order: after
         relative_to: execute

.. container:: tn-app-variant tn-app-container tn-app-gromacs

   .. code-block:: YAML

       executable_injection:
       - name: start_time
         order: before
         relative_to: execute-gen
       - name: end_time
         order: after
         relative_to: execute-gen

.. container:: tn-app-variant tn-app-container tn-app-hpl

   .. code-block:: YAML

       executable_injection:
       - name: start_time
         order: before
         relative_to: execute
       - name: end_time
         order: after
         relative_to: execute

Go ahead and edit the workspace configuration file with:

.. code-block:: console

    $ ramble workspace edit

Replace the ``executables`` block with the ``executable_injection`` block
presented above. The resulting configuration file should look like the
following:

.. container:: tn-app-variant tn-app-container tn-app-wrf

   .. literalinclude:: ../_generated/snippets/using_internals_wrf_exec_injection.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-container tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/using_internals_gromacs_exec_injection.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-container tn-app-hpl

   .. literalinclude:: ../_generated/snippets/using_internals_hpl_exec_injection.yaml
      :language: YAML

Execute Experiments
~~~~~~~~~~~~~~~~~~~

.. container:: tn-full-run-only

   .. note::
      When not running in dry-run mode, ``ramble on`` will re-execute the scaling
      study workloads across all configured node counts, which may take a while
      depending on the application workload.

   Now set up and execute the workspace experiments again:

   .. code-block:: console

       $ ramble workspace setup
       $ ramble on

   Examining the experiment run directories, you should see ``start_time`` and
   ``end_time`` in the same places as they were when you ran the explicitly
   defined order experiments.

.. container:: tn-dry-run-only

   Now set up the workspace experiments again using ``--dry-run``:

   .. code-block:: console

       $ ramble workspace setup --dry-run

   Inspect the generated ``execute_experiment`` scripts in the experiment run
   directories to verify that ``executable_injection`` placed ``start_time`` and
   ``end_time`` in the exact same positions around the main executable as the
   explicitly defined ``executables`` list.


Clean the Workspace
-------------------

.. container:: tn-workspace-cleanup

   Once you are finished with the tutorial content, make sure you deactivate your workspace:

   .. code-block:: console

       $ ramble workspace deactivate

   Additionally, you can remove the workspace and all of its content with:

   .. container:: tn-app-variant tn-app-container tn-app-wrf

      .. code-block:: console

          $ ramble workspace remove internals_wrf

   .. container:: tn-app-variant tn-app-container tn-app-gromacs

      .. code-block:: console

          $ ramble workspace remove internals_gromacs

   .. container:: tn-app-variant tn-app-container tn-app-hpl

      .. code-block:: console

          $ ramble workspace remove internals_hpl
