.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _variable_expansion_and_indirection_and_stack_parameterization_tutorial:

=======================================================================
8) Variable Expansion, Indirection, and Software Stack Parameterization
=======================================================================

In this tutorial, you will learn how to use variable expansion, indirection,
and software stack parameterization when generating experiments. For this
tutorial, we will use
`WRF <https://www.mmm.ucar.edu/models/wrf>`_, a free and open-source
application for atmospheric research and operational forecasting applications.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

**NOTE:** In this tutorial, you will encounter expected errors when copying and
pasting the commands. This is to help show situations you might run into when
trying to use Ramble on your own, and illustrate how you might fix them.

Create a Workspace
------------------

To begin with, you need a workspace to configure the experiments. This can be
created with the following command:

.. code-block:: console

    $ ramble workspace create var_expansion_and_indirection


Activate the Workspace
----------------------

Several of Ramble's commands require an activated workspace to function
properly. Activate the newly created workspace using the following command:
(NOTE: you only need to run this if you do not currently have the workspace
active).

.. code-block:: console

    $ ramble workspace activate var_expansion_and_indirection

Configure Experiment Definitions
--------------------------------

To being with, you need to configure the workspace. The workspace's root
location can be seen under the ``Location`` output of:

.. code-block:: console

    $ ramble workspace info

Additionally, the files can be edited directly with:

.. code-block:: console

    $ ramble workspace edit

Within the ``ramble.yaml`` file, write the following contents, which are the
final configuration from the previous tutorial.


.. literalinclude:: ../../../../examples/tutorial_8_base_config.yaml
   :language: YAML

The above configuration will execute 4 experiments, comprising a basic scaling
study on three different sets of nodes across two different platforms.

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
compiler used for WRF.

**NOTE**: This package can also be defined using the following command, however
you will need parameterize which MPI implementation is used manually, as follows.

.. code-block::

    $ ramble workspace manage software --pkg openmpi --spec openmpi@5.0.8

We also need to generate additional software environments, however we will
parameterize the generation of these using a new variable definition. Since the
``mpi_name`` variable will be needed for both experiment generation and
environments, you'll put it under the workspace variables.

.. code-block:: YAML

    ramble:
      variables:
        mpi_name: ['intel-mpi', 'openmpi']

.. code-block:: YAML

    environments:
      wrf@4.2:
        packages:
        - '{mpi_name}'
        - wrfv4-{application::wrf::version}

This will create two software environments. One named ``wrf@4.2-intel-mpi`` and
another named ``wrf@4.2-openmpi``.

**NOTE** The reference to ``{mpi_name}`` within the environment package list is
escaped using single quotes. This is to prevent YAML from parsing this as a
dictionary.

The result might look like the following:

.. literalinclude:: ../../../../examples/tutorial_8_mpi_config.yaml
   :language: YAML

At this point, executing:

.. code-block:: console

    $ ramble workspace info

Should result in the following error:

.. code-block:: console

    ==> Warning: Two experiments are defined with the name wrf@4.2.CONUS_12km.scaling_1_platform1
    ==> Warning:   -> Collision Origin: Within the same YAML experiment block: 'scaling_{n_nodes}_{platform}' (Matrix/Vector Expansion)
    ==> Warning: Variables unique to previously defined experiment:
    ==> Warning:   - experiment_index
    ==> Warning: Variable differences between experiment definitions:
    ==> Warning:   - mpi_name: {'previous': 'intel-mpi', 'new': 'openmpi'}
    ==> Error: Experiment wrf@4.2.CONUS_12km.scaling_1_platform1 is not unique.

As you have implicitly defined 8 experiments (2 from ``n_nodes``, times 2 from
``platform_config``, times another 2 from ``mpi_name``), but you haven't
updated the experiment name template. To resolve this, add ``{mpi_name}`` into
the experiment name template, and the software environment name. Additionally,
you may explicitly add ``mpi_name`` into the matrix.

The experiments are still not completely defined. Running:

.. code-block:: console

    $ ramble workspace info

Should result in the following warning:

.. code-block:: console

    ==> Warning: Software environment 'wrf@4.2' was auto-constructed for package manager 'spack' and contains no packages. If this was not intended, please define the environment or packages in your configuration.

The default software environment every application uses is named the same as the
application (in this case, both would be named ``wrf@4.2``). Now that you've
changed the name of the environment, you need to connect each experiment to the
proper environment.

To control the software environment used within an experiment, Ramble allows
you to use the ``env_name`` variable definition. Because ``mpi_name`` is a list
variable, you might want ``env_name`` to be a list that is zipped with
``mpi_name`` to make sure they are iterated over together. However, you may
also utilize variable indirection / expansion to fix this issue. For the
purposes of this tutorial, we will use indirection instead of explicit zips. In
the experiment variables, add:

.. code-block:: YAML

    variables:
      env_name: 'wrf@4.2-{mpi_name}'

The resulting configuration file might look like the following:

.. literalinclude:: ../../../../examples/tutorial_8_mpi_matrix_config.yaml
   :language: YAML

Variable Expansion and Indirection
----------------------------------

At this stage, you have defined a workspace that will execute 8 experiments.
It is important to point out that different MPI implementations have different
command line flags for controlling their behavior. The existing ``mpi_command``
should work fine with both Intel MPI, and OpenMPI but to illustrate how
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

In Ramble, every variable can be defines as a combination of other variables. For example:

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

.. literalinclude:: ../../../../examples/tutorial_8_expansion_indirection_config.yaml
   :language: YAML


**NOTE** The arguments for the various MPI implementations may not run on your
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
arguments within the relevant experiments.

.. include:: shared/wrf_execute.rst

Clean the Workspace
-------------------

Once you are finished with the tutorial content, make sure you deactivate your workspace:

.. code-block:: console

    $ ramble workspace deactivate

Additionally, you can remove the workspace and all of its content with:

.. code-block:: console

    $ ramble workspace remove var_expansion_and_indirection
