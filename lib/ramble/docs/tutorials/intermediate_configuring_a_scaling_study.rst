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

.. tutorial-header:: scaling_study

In this tutorial, you will learn how to create a workspace containing a scaling
study.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

.. note::
   In this tutorial, you will encounter expected errors when copying and
   pasting the commands. This is to help show situations you might run into when
   trying to use Ramble on your own, and illustrate how you might fix them.

Create and Activate a Workspace
-------------------------------

.. tutorial-workspace-create:: scaling
   :separate-activate:

Decide on a Workload
--------------------

Before you can set up this workspace, you'll need to configure the experiments
you want to execute. To begin with, select a workload:

.. tutorial-app-template::
   :wrf: note_extra= because it is less computationally expensive than the ``CONUS_2p5km`` workload
   :gromacs: note_extra=
   :hpl: note_extra=

   .. code-block:: console

       $ ramble info --attrs workloads {app}

   For the purposes of this tutorial, the ``{workload}`` workload is recommended {note_extra}.

   .. note::
      To get more detailed information about the workload definitions, you
      can use ``ramble info --attrs workloads -v {app}``.

Configure Experiment Definitions
--------------------------------

Now that you have selected a workload to use, configure the experiments you want to execute.
You can configure your experiment definitions directly using ``ramble workspace manage experiments``:

.. tutorial-snippet:: scaling_study commands.sh
   :alt-yaml: applications.yaml

The experiment name template ``scaling_{n_nodes}`` allows parameterizing the experiment
across the values in ``n_nodes: [1, 2]``.

At this point, you can attempt to view the experiments defined by this
configuration file. To do this, use the following command:

.. code-block:: console

    $ ramble workspace info

The output should tell you some required variable definitions are missing, as
the configuration does not include some system level definitions. The output
might look like the following:

.. tutorial-app-template::

   .. code-block:: console

       ==> Error: Invalid number of required variables defined.
       Two or more of the following are required to be defined.
         - n_ranks
         - processes_per_node
         - n_nodes
       Experiment {app}.{workload}.scaling_1 only has:
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

.. tutorial-app-template::
   :wrf: extra_var=
   :gromacs: extra_var=
   :hpl: extra_var=memory_per_node: 8

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
           {app}:
             workloads:
               {workload}:
                 experiments:
                   scaling_{n_nodes}:
                     variables:
                       n_nodes: [1, 2]
                       {extra_var}

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

.. tutorial-snippet:: scaling_study ramble.yaml

At this point, you have fully described experiments that can be executed.
However, your system might not have the correct compiler (and building a
compiler could be costly). The ``gcc14`` package definition can be updated to
refer to a compiler you already have on your system. These can be viewed using
the ``spack compiler list`` command. Edit the ``gcc14`` package definition as
you see fit, and make sure the compiler references are updated appropriately as well.

Executing Experiments
---------------------

.. tutorial-execute:: scaling
   :include-foms:

Ramble also supports uploading the analyzed data to online databases, using
``ramble workspace analyze --upload``. We will not cover this functionality in
detail here, but it is very useful for production experiments.


Cleaning the Workspace
----------------------

.. tutorial-workspace-cleanup:: scaling
