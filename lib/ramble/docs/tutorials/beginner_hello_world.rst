.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _hello_world_tutorial:

=====================================================
Getting Started Running A 'Hello World' Experiment
=====================================================

**Learning Objectives**

By the end of this tutorial, you will understand how to:

* Create and activate a workspace
* Configure a workspace for the ``hostname`` application
* Set up, execute, and analyze a basic experiment

Introduction
============

This tutorial will walk you through setting up, executing, and analyzing your first simple
experiment using the ``hostname`` application.

.. note::
   This tutorial assumes you have followed the :doc:`Getting Started
   <../getting_started>` tutorial to set up your environment to have ``ramble`` in
   your ``PATH``. If you haven't already explored how to discover applications
   and inspect their workloads with ``ramble list`` and ``ramble info``, see the
   :ref:`Ramble Basics tutorial <ramble_basics_tutorial>`.

Configuring Experiments
=======================

Most user-driven work in Ramble is facilitated through a ``workspace``. You can
think of a workspace as a self-contained directory on the file system
containing configuration files, along with a directory format for performing
experiments, and storing input files and software environments.

In the following sub-sections you will configure your first workspace, execute
its experiments, and analyze the results.

Create and Activate a Workspace
-------------------------------

First, let's create a new workspace named ``hello_world``. Ramble can create and
manage ``named`` workspaces (stored in a central location) or ``anonymous``
workspaces (located at any path on your filesystem). By default, named workspaces
are stored at:

.. code-block:: console

    $ $RAMBLE_ROOT/var/ramble/workspaces

Let's create our ``hello_world`` workspace as a named workspace using the command:

.. code-block:: console

    $ ramble workspace create hello_world

Next, we need to ``activate`` the workspace, which sets environment variables
so subsequent Ramble commands automatically apply to it:

.. code-block:: console

    $ ramble workspace activate hello_world

To verify the workspace is active and inspect its current configuration, run:

.. code-block:: console

    $ ramble workspace info

which outputs:

.. literalinclude:: ../_generated/snippets/hello_world_hostname_workspace_info_initial.out
   :language: console

Configure the Workspace
-----------------------

A workspace's primary configuration file is ``ramble.yaml``, located inside the
workspace's ``configs`` directory. Let's inspect the default configuration file:

.. code-block:: console

   $ ramble workspace edit -c

Alternatively, you can refer to this configuration file using it's path:

.. code-block:: console

    $ cat $RAMBLE_ROOT/var/ramble/workspaces/hello_world/configs/ramble.yaml

This file starts with an empty skeleton:

.. code-block:: YAML

    # This is a ramble workspace config file.
    #
    # It describes the experiments, the software stack
    # and all variables required for ramble to configure
    # experiments.
    # As an example, experiments can be defined as follows:
    # applications:
    #   hostname:
    #     workloads:
    #       serial:
    #         experiments:
    #           single_node:
    #             variables:
    #               n_ranks: 1

    ramble:
      variables:
        mpi_command: ''
        batch_command: ''
      applications: {}
      software:
        packages: {}
        environments: {}

Let's configure the workspace to execute the ``local`` workload of the ``hostname``
application. You can edit the configuration directly using ``ramble workspace edit``,
or use the ``ramble workspace manage experiments`` CLI command to populate it for you:

.. literalinclude:: ../_generated/snippets/hello_world_hostname_commands.sh
   :language: console

If we view ``ramble.yaml`` again (or run ``ramble workspace edit``), we can see
how the experiment was added:

.. literalinclude:: ../_generated/snippets/hello_world_hostname_ramble.yaml
   :language: YAML

.. tip::
   The ``ramble workspace edit`` command opens the workspace's configuration files in
   the editor configured by your ``EDITOR`` environment variable.

Let's examine this configuration:

* Under ``applications:``, we added ``hostname:``, telling Ramble to use the ``hostname`` application definition (which can be found in the output of ``ramble list``).
* Under ``workloads:``, we selected the ``local`` workload (which can be seen in the output of ``ramble info hostname``).
* Under ``experiments:``, we created an experiment named ``test`` (which serves as a unique label for this experiment).
* Under ``variables:``, we defined ``n_ranks: 1`` to run a single process.

Save and exit the file if you opened it in an editor. Now, let's check our workspace
information again:

.. code-block:: console

    $ ramble workspace info

which outputs:

.. literalinclude:: ../_generated/snippets/hello_world_hostname_workspace_info.out
   :language: console

Setting Up the Experiments
--------------------------

Now that the workspace is configured, we can set up the experiments in the
active workspace:

.. code-block:: console

    $ ramble workspace setup

This command creates the experiment directory structure, downloads any required
input files, configures the software stack, and renders the execution scripts.
Because the ``hostname`` application does not require external inputs or Spack
software installations, setup completes very quickly:

.. literalinclude:: ../_generated/snippets/hello_world_hostname_setup.out
   :language: console

For each setup run, Ramble creates log files under ``$workspace_root/logs``.
You can inspect the setup log for our experiment at:

.. code-block:: console

    $ cat $RAMBLE_ROOT/var/ramble/workspaces/hello_world/logs/setup.latest/hostname.local.test.out

.. tip::
   If you ever want to preview what Ramble will configure and generate without
   downloading input files or installing software, you can pass the ``--dry-run``
   flag to ``ramble workspace setup``:

   .. code-block:: console

       $ ramble workspace setup --dry-run

Executing Experiments
---------------------

After setting up the workspace, we can execute its experiments using either of
the following methods:

.. code-block:: console

    $ ramble on
   or;
    $ $RAMBLE_ROOT/var/ramble/workspaces/hello_world/all_experiments

Executing with ``ramble on`` produces output similar to:

.. literalinclude:: ../_generated/snippets/hello_world_hostname_on.out
   :language: console

Each experiment creates an output log file in its experiment directory. You can view
the standard output of our ``test`` experiment at:

.. code-block:: console

    $ cat $RAMBLE_ROOT/var/ramble/workspaces/hello_world/experiments/hostname/local/test/test.out

which should contain the hostname of your machine.

Analyzing Experiments
---------------------

Once the experiments have finished running, we can analyze the results:

.. code-block:: console

    $ ramble workspace analyze

which outputs:

.. literalinclude:: ../_generated/snippets/hello_world_hostname_analyze.out
   :language: console

This generates a ``results.latest.txt`` file in the root of the workspace (as well as
inside the ``results/`` directory) containing the extracted figures of merit.
Let's view the results:

.. code-block:: console

    $ cat $RAMBLE_ROOT/var/ramble/workspaces/hello_world/results.latest.txt

.. literalinclude:: ../_generated/snippets/hello_world_hostname_results.txt
   :language: text

Here, the ``possible hostname`` figure of merit shows the hostname captured during
the experiment.

Clean Up the Workspace
----------------------

.. tutorial-workspace-cleanup:: hello_world
   :single:
