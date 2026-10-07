.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _configuring_a_scaling_study_tutorial:

==============================
6) Configuring a Scaling Study
==============================

In this tutorial, you will learn how to create a workspace containing a scaling
study for `WRF <https://www.mmm.ucar.edu/models/wrf>`_, a free and open-source
application for atmospheric research and operational forecasting applications.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

**NOTE:** In this tutorial, you will encounter expected errors when copying and
pasting the commands. This is to help show situations you might run into when
trying to use Ramble on your own, and illustrate how you might fix them.

Create a Workspace
------------------

To begin with, you need a workspace to configure the scaling study. This can be
created with the following command:

.. code-block:: console

    $ ramble workspace create scaling_wrf


Activate the Workspace
----------------------

Several of Ramble's commands require an activated workspace to function
properly. Activate the newly created workspace using the following command:
(NOTE: you only need to run this if you do not currently have the workspace
active).

.. code-block:: console

    $ ramble workspace activate scaling_wrf

Decide on a Workload
--------------------

Before you can setup this workspace, you'll need to configure the experiments
you want to execute. To begin with, select a workload from the output of:

.. code-block:: console

    $ ramble info --attrs workloads wrf

For the purposes of this tutorial, the ``CONUS_12km`` workload is recommended
because it is less computationally expensive than any of the other workloads.

**NOTE**: To get more detailed information about the workload definitions, you
can use ``ramble info --attrs workloads -v wrf``.

Configure Experiment Definitions
--------------------------------

Now that you have selected a workload to use, edit the workspace configuration
file. The workspace's root location can be seen under the ``Location`` output of:

.. code-block:: console

    $ ramble workspace info

Additionally, the files can be edited directly with:

.. code-block:: console

    $ ramble workspace edit

Within this file, configure the ``applications`` dictionary to describe the
experiments you want to execute. The contents might look like the following:

.. code-block:: YAML

    ramble:
      applications:
        wrf@4.2:
          workloads:
            CONUS_12km:
              experiments:


The next step in configuring the experiment definitions is to decide on an
experiment name template. For the purposes of this tutorial, we'll assume we
only want to change the ``n_nodes`` variable definition in our scaling study,
and as a result the experiment name template will only include this template
parameter. However, you are free to add additional parameters based on the
experiments you would like to perform. We will also assume ``n_nodes`` will
take the values of ``1`` and ``2``, however you should edit this for the system
you are attempting to run these experiments on. The contents of the
configuration file might look like the following now:

.. code-block:: YAML

    ramble:
      applications:
        wrf@4.2:
          workloads:
            CONUS_12km:
              experiments:
                scaling_{n_nodes}:
                  variables:
                    n_nodes: [1, 2]

At this point, you can attempt to view the experiments defined by this
configuration file. To do this, use the following command:

.. code-block:: console

    $ ramble workspace info

The output should tell you some required variable definitions are missing, as
the configuration does not include some system level definitions. The output
might look like the following:

.. code-block:: console

    ==> Error: Invalid number of required variables defined.
    Two or more of the following are required to be defined.
      - n_ranks
      - processes_per_node
      - n_nodes
    Experiment wrf@4.2.CONUS_12km.scaling_1 only has:
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
        wrf@4.2:
          workloads:
            CONUS_12km:
              experiments:
                scaling_{n_nodes}:
                  variables:
                    n_nodes: [1, 2]

**NOTE** The value of the ``n_ranks`` variable is escaped using single quotes.
This is because YAML interprets the ``{`` character as beginning a dictionary,
so we need to escape it to convert it to a string.

Applying the Default Software Configuration
-------------------------------------------

At this point, you have fully described the experiments you would like to
perform, but have not defined the software stack that should be used for these
experiments.

To see this, when running:

.. code-block:: console

    $ ramble workspace info

You should see the following warning

.. code-block:: console

    ==> Warning: Software environment 'wrf@4.2' was auto-constructed for package manager 'spack' and contains no packages. If this was not intended, please define the environment or packages in your configuration.

This warning is printed as a result of the workspace not having any software
packages or environments defined. Every Ramble application definition file
should contain a suggested starting place for the experiment's software stack.
To apply this to your workspace, use:


.. code-block:: console

    $ ramble workspace concretize

This will fill out the ``software`` dictionary within your workspace configuration
file. After executing this command, your workspace configuration file might
look like the following:


.. literalinclude:: ../../../../examples/tutorial_6_config.yaml
   :language: YAML

At this point, you have fully described experiments that can be executed.
However, your system might not have the correct compiler (and building a
compiler could be costly). The ``gcc14`` package definition can be updated to
refer to a compiler you already have on your system. These can be viewed using
the ``spack compiler list`` command. Edit the ``gcc14`` package definition as
you see fit, and make sure the ``gcc14`` references under ``intel-mpi`` and
``wrfv4`` are updated appropriately as well.

.. include:: shared/wrf_execute.rst

Ramble also supports uploading the analyzed data to online databases, using
``ramble workspace analyze --upload``. We will not cover this functionality in
detail here, but it is very useful for production experiments.

Cleaning the Workspace
----------------------

After you are finished with the content of this tutorial, make sure you
deactivate your workspace using:

.. code-block:: console

    $ ramble workspace deactivate

If you no longer need the workspace materials, remove the entire workspace
with:

.. code-block:: console

    $ ramble workspace remove scaling_wrf
