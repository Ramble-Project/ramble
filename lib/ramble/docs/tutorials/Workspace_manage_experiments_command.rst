.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _workspace-manage-experiments-command-tutorial:

=========================================================
Using the ``ramble workspace manage experiments`` Command
=========================================================

Ramble workspaces are controlled through their configuration files. Each workspace has a
configuration file stored at ``$workspace/configs/ramble.yaml``. Definitions for the
Ramble experiments you want to perform come from this configuration file. While you can
write and edit these YAML files manually, Ramble provides a command-line interface
to generate and manage experiment definitions programmatically:
``ramble workspace manage experiments``.

This command is used throughout Ramble's developer tutorials to quickly bootstrap
experiments, construct parameter sweeps, and automate workspace generation without
hand-crafting YAML boilerplate.

In this tutorial, you will learn how to use ``ramble workspace manage experiments`` to:

* Generate baseline experiment configurations for applications and workloads.
* Filter workloads to include only the test cases you need.
* Inject and parameterize variables for scaling studies and sweeps.
* Define matrices to expand multi-variable combinations.
* Apply variants (such as specifying a package manager).
* Perform dry runs to preview generated configurations before saving.

--------------------
Creating a Workspace
--------------------

To start, create a new workspace using ``ramble workspace create``:

.. code-block:: console

   $ ramble workspace create -d manage-workspace

This creates an anonymous workspace (see note below) with the default ``ramble.yaml``
configuration:

.. code-block:: yaml

    # This is a ramble workspace config file.
    #
    # It describes the experiments, the software stack
    # and all variables required for ramble to configure
    # experiments.
    # As an example, experiments can be defined as follows.
    # applications:
    #   hostname: # Application name, as seen in `ramble list`
    #     variables:
    #       iterations: '5'
    #     workloads:
    #       serial: # Workload name, as seen in `ramble info <app>`
    #         variables:
    #           type: 'test'
    #         experiments:
    #           single_node: # Arbitrary experiment name
    #             variables:
    #               n_ranks: '{processes_per_node}'

    ramble:
    env_vars:
        set:
        OMP_NUM_THREADS: '{n_threads}'
    variants:
        system: user-managed
    variables:
        processes_per_node: 1
    applications: {}
    software: 
        packages: {}
        environments: {}

And there are no experiments listed in the output from ``ramble -D manage-workspace workspace info``.

.. note::
   Throughout this tutorial, we will use the ``-D manage-workspace`` flag to direct
   commands to our new anonymous workspace without needing to activate it explicitly.
   In these examples the ``manage-workspace`` directory is relative to our current working
   directory, but you may specify an absolute path to a workspace directory as well - e.g.,
   ``-D ${HOME}/manage-workspace``.

   For more information on named and anonymous workspaces, see the
   :ref:`Ramble workspace documentation<ramble-workspaces>`.

-------------------------------
Generating Default Experiments
-------------------------------

The simplest usage of ``ramble workspace manage experiments`` is to generate default
experiment definitions for an application.

Let's generate experiments for the ``hostname`` application:

.. code-block:: console

   $ ramble -D manage-workspace workspace manage experiments hostname --overwrite

Here, the ``--overwrite`` flag tells Ramble to replace any existing experiment
definitions for the ``hostname`` application in the workspace configuration file.

You can inspect the resulting workspace state using the ``workspace info`` command:

.. code-block:: console

   $ ramble -D manage-workspace workspace info

The ``hostname`` application has four defined workloads so the output should look
like the following:

.. code-block:: console

    Experiments:
        Application: hostname
            Workload: serial
            Experiment 1: hostname.serial.generated
        Application: hostname
            Workload: parallel
            Experiment 2: hostname.parallel.generated
        Application: hostname
            Workload: local
            Experiment 3: hostname.local.generated
        Application: hostname
            Workload: local_bg
            Experiment 4: hostname.local_bg.generated

Ramble generated an experiment for each of the workloads. The ``ramble.yaml``
configuration should also now look like:

.. code-block:: yaml

    # This is a ramble workspace config file.
    #
    # It describes the experiments, the software stack
    # and all variables required for ramble to configure
    # experiments.
    # As an example, experiments can be defined as follows.
    # applications:
    #   hostname: # Application name, as seen in `ramble list`
    #     variables:
    #       iterations: '5'
    #     workloads:
    #       serial: # Workload name, as seen in `ramble info <app>`
    #         variables:
    #           type: 'test'
    #         experiments:
    #           single_node: # Arbitrary experiment name
    #             variables:
    #               n_ranks: '{processes_per_node}'

    ramble:
    env_vars:
        set:
        OMP_NUM_THREADS: '{n_threads}'
    variants:
        system: user-managed
    variables:
        processes_per_node: 1
    applications:
        hostname:
        workloads:
            serial:
            experiments:
                generated:
                variables:
                    n_nodes: ''
                    n_ranks: ''
            parallel:
            experiments:
                generated:
                variables:
                    n_nodes: ''
                    n_ranks: ''
            local:
            experiments:
                generated:
                variables:
                    n_nodes: ''
                    n_ranks: ''
            local_bg:
            experiments:
                generated:
                variables:
                    n_nodes: ''
                    n_ranks: ''
    software:
        packages: {}
        environments: {}

You'll notice that the ``n_nodes`` and ``n_ranks`` variables have no values, this
will be covered next.

------------------------------------------
Filtering Workloads and Setting Variables
------------------------------------------

Often, an application contains multiple workloads, but you may only want to test a
specific one. You can use the ``--workload-filter`` (or ``--wf``) option to restrict
which workloads are generated.

Additionally, you can pass variable definitions using ``--variable-definition`` (or ``-v``)
in ``key=value`` format.

Let's generate a ``hostname`` experiment restricted to the ``local`` workload with
custom variables. But first, because ``workspace manage experiments`` does not
remove existing configuration, only adds new experiments or overwrite existing
experiments, let's remove the extra workloads. Use
``ramble -D manage-workspace workspace edit -c`` to make the configuration look like
the following:

.. code-block:: yaml

    # This is a ramble workspace config file.
    #
    # It describes the experiments, the software stack
    # and all variables required for ramble to configure
    # experiments.
    # As an example, experiments can be defined as follows.
    # applications:
    #   hostname: # Application name, as seen in `ramble list`
    #     variables:
    #       iterations: '5'
    #     workloads:
    #       serial: # Workload name, as seen in `ramble info <app>`
    #         variables:
    #           type: 'test'
    #         experiments:
    #           single_node: # Arbitrary experiment name
    #             variables:
    #               n_ranks: '{processes_per_node}'

    ramble:
    env_vars:
        set:
        OMP_NUM_THREADS: '{n_threads}'
    variants:
        system: user-managed
    variables:
        processes_per_node: 1
    applications:
        hostname:
        workloads:
            local:
            experiments:
                generated:
                variables:
                    n_ranks: ''
                    n_nodes: ''
    software:
        packages: {}
        environments: {}

All the workloads except the ``local`` workload have now been removed. Now let's
update the ``local`` workload to define the desired variable values.

.. code-block:: console

   $ ramble -D manage-workspace workspace manage experiments hostname \
        --wf local \
        -v n_ranks=1 \
        -v n_nodes=1 \
        --overwrite

Inspecting ``manage-workspace/configs/ramble.yaml`` shows the updated configuration:

.. code-block:: yaml

   ramble:
     applications:
       hostname:
         workloads:
           local:
             experiments:
               generated:
                 variables:
                   n_nodes: '1'
                   n_ranks: '1'

.. note::
    If you are setting all the required variables to the same value, you can
    instead use ``--default-variable-value <value>`` instead of specifying each
    individual variable. So the above could have been replaced with:

    .. code-block:: console

        $ ramble -D manage-workspace workspace manage experiments hostname \
                --wf local \
                --default-variable-value 1 \
                --overwrite

---------------------------------------------------
Configuring Parameter Sweeps (Vectors and Matrices)
---------------------------------------------------

To set up scaling studies or multi-dimensional parameter sweeps, you can pass vector
lists into variable definitions and define a matrix with ``--matrix`` (or ``-m``).

When expanding a matrix into multiple experiments, each experiment requires a unique name.
You can specify a template for experiment names using ``--experiment-name`` (or ``-e``),
interpolating variable values like ``'{size}-{n_nodes}nodes'``.

Let's add experiments for the ``gromacs`` application, filtering for the ``water_bare`` workload,
sweeping over node counts and domain sizes:

.. code-block:: console

   $ ramble -D manage-workspace workspace manage experiments gromacs \
        --wf water_bare \
        -v "n_nodes=[1, 2, 4]" \
        -v "size=[1536, 3072]" \
        -m n_nodes,size \
        -e '{size}-{n_nodes}nodes' \
        -V package_manager=spack

Let's break down the options used in this command:

* ``--wf water_bare``: Restricts experiment generation to the ``water_bare`` workload.
* ``-v "n_nodes=[1, 2, 4]"`: Sets ``n_nodes`` as a vector of node counts.
* ``-v "size=[1536, 3072]"`: Sets ``size`` as a vector of problem sizes.
* ``-m n_nodes,size``: Defines a matrix across ``n_nodes`` and ``size``.
* ``-e '{size}-{n_nodes}nodes'``: Formats experiment names dynamically based on variable values.
* ``-V package_manager=spack``: Adds a variant definition setting the package manager to Spack.

Now check the workspace info again:

.. code-block:: console

   $ ramble -D manage-workspace workspace info

Output:

.. code-block:: console

    Experiments:
    Application: hostname
        Workload: local
        Experiment 1: hostname.local.generated
    Application: gromacs
        Workload: water_bare
        Experiment 2: gromacs.water_bare.1536-1nodes
        Experiment 3: gromacs.water_bare.3072-1nodes
        Experiment 4: gromacs.water_bare.1536-2nodes
        Experiment 5: gromacs.water_bare.3072-2nodes
        Experiment 6: gromacs.water_bare.1536-4nodes
        Experiment 7: gromacs.water_bare.3072-4nodes

Ramble automatically generated 6 distinct experiments representing the cross-product
of 3 node counts and 2 problem sizes.

-------------------------
Defining Success Criteria
-------------------------

You can define custom experiment :ref:`success criteria <success-criteria>` using the ``-s`` (or ``--success-criteria``) flag.
Criteria are specified in comma-separated key=value format (e.g. ``name=CRITERIA,mode=TYPE,...``):

.. code-block:: console

   $ ramble -D manage-workspace workspace manage experiments hostname \
        --wf local \
        -s name=check_output,mode=string,match="Host.*" \
        --overwrite

If either the ``key`` or ``value`` contains a comma, equals sign, or space, you must quote the key/value.

---------------------------------------
Previewing Configurations with Dry Runs
---------------------------------------

Before modifying your workspace configuration, you can perform a dry run using ``--dry-run``
(or ``--print``). This is especially helpful when scripting or testing complex matrix
combinations. This prints the resulting YAML configuration to stdout without saving changes
to disk:

.. code-block:: console

   $ ramble -D manage-workspace workspace manage experiments hostname \
        --wf local \
        -v n_ranks=4 \
        --overwrite \
        --dry-run

A few things to note:

1. If the experiment already exists, ``--overwrite`` must be used or you will get an error
like:

.. code-block:: console

    ==> Warning: Experiment hostname.local.generated is defined already. To overwrite, use '--overwrite'
    ==> Error: No workloads match filter 'local' in application hostname

2. You'll notice from the dry run output that ``n_nodes`` was reset to no value. That's
because no value was provided so it reverted back to the default.

-------------------
Where to Learn More
-------------------

The ``ramble workspace manage experiments`` command offers additional options and customization
details. To explore further, consult the following resources:

* **Command Line Help**: Run ``ramble workspace manage experiments --help`` for a full summary of flags and arguments.
* **Developer Guides**: See the :ref:`application-dev-guide` and developer tutorials (e.g. :ref:`basic_application_tutorial`) to see how ``manage experiments`` is used when creating and testing new object definitions.

----------------------
Conclusion and Cleanup
----------------------

In this tutorial, you learned how to use ``ramble workspace manage experiments`` to programmatically
create baseline experiments, filter workloads, set variables, construct matrix sweeps, set variants,
and dry-run experiment configurations.

To clean up the tutorial workspace, run:

.. code-block:: console

   $ rm -rf manage-workspace
