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

.. tutorial-header:: internals

In this tutorial, you will learn how to use ``internals`` within experiments to
define custom executables and control their execution order.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

Create a Workspace
------------------

.. tutorial-workspace-create:: internals
   :separate-activate:

Configure Experiment Definitions
--------------------------------

To begin with, you need to configure the workspace. Within the ``ramble.yaml``
file, write the following contents, which represents the scaling study
configuration from previous tutorials:

.. tutorial-snippet:: internals base.yaml

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

.. tutorial-snippet:: internals new_exec.yaml

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

.. tutorial-app-template::
   :wrf: exec_list=['stage-files', 'stage-namelist', 'cleanup', 'define_nproc_y', 'define_nproc_x', 'fix_12km_start_hour', 'fix_12km_restart', 'execute', 'copy-logs', 'post-exec-clean']
   :gromacs: exec_list=['print-binary-info', 'pre-process', 'execute-gen']
   :hpl: exec_list=['execute']

   .. code-block:: console

       $ ramble info --attrs workloads -v -p "{workload}" {app}

   This prints the information for the ``{workload}`` workload in the {app_upper} application definition.
   The ``Executables:`` definition lists the order of executables used for this workload:

   .. code-block:: console

       Executables: {exec_list}

Some executables are provided through the ``builtin`` functionality. These are
executable commands that are injected by default from the object definitions.
To be able to see these, you can execute:

.. tutorial-app-template::

   .. code-block:: console

       $ ramble info --attrs builtins -v {app}

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

.. tutorial-snippet:: internals exec_order.yaml

.. note::
   Omitting any executables from the ``executables`` list will
   prevent it from being used in the generated experiments.

Execute Experiments
~~~~~~~~~~~~~~~~~~~

.. tutorial-execute:: internals
   :no-analyze:
   :dry-run-cmds: grep "date +%s" $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/{app}/{workload}/*/execute_experiment
   :results-text: Examining the experiment run directories, you should see ``start_time`` and ``end_time`` files which contain the Unix epoch timestamps produced by our custom executables.

Using Executable Injection
--------------------------

In addition to the full explicit method of injecting an executable shown above,
you can inject executables relative to existing executables in the experiment's
executable list. This is documented in the :ref:`internals config
section<internals-config>` and :ref:`workspace internals<workspace_internals>`
documentation sections.

As an example, the following YAML could replace the ``executables`` section of
your existing configuration:

.. tutorial-app-template::
   :wrf: rel_exec=execute
   :gromacs: rel_exec=execute-gen
   :hpl: rel_exec=execute

   .. code-block:: YAML

       executable_injection:
       - name: start_time
         order: before
         relative_to: {rel_exec}
       - name: end_time
         order: after
         relative_to: {rel_exec}

Go ahead and edit the workspace configuration file with:

.. code-block:: console

    $ ramble workspace edit

Replace the ``executables`` block with the ``executable_injection`` block
presented above. The resulting configuration file should look like the
following:

.. tutorial-snippet:: internals exec_injection.yaml

Execute Experiments
~~~~~~~~~~~~~~~~~~~

.. tutorial-execute:: internals
   :no-analyze:
   :package-manager: none
   :dry-run-cmds: grep "date +%s" $(ramble workspace info | grep "Location" | awk '{print $NF}')/experiments/{app}/{workload}/*/execute_experiment
   :results-text: Examining the experiment run directories, you should see ``start_time`` and ``end_time`` in the same places around the main executable as when you used the explicitly defined ``executables`` list.


Clean the Workspace
-------------------

.. tutorial-workspace-cleanup:: internals
