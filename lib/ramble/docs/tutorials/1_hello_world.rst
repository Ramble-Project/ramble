.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _hello_world_tutorial:

=====================================================
1) Getting Started Running A "Hello World" Experiment
=====================================================

This tutorial will provide a basic introduction to navigating Ramble and running
experiments. In this tutorial, you will set up and run a basic experiment using
``hostname`` linux utility as your application.

Installation
============

To install Ramble, see the :doc:`../getting_started` guide.

**NOTE**: This tutorial does not require a package manager to be installed or configured.

Ramble Basics
=============

Before beginning, we will learn some basics about ``ramble`` and its available
commands.

Available Applications
----------------------

Once Ramble is installed, viewing the available application definitions is as
simple as executing:

.. code-block:: console

    $ ramble list

The ``ramble list`` command also takes a query string, which can be used to
filter available application definitions. For example:

.. code-block:: console

    $ ramble list h

might output the following:

.. rst-class:: hide-copy
.. code-block:: console

    ==> 10 applications
    hmmer  hostname  hpcc  hpcg  hpl  intel-hpl  intel-mpi-benchmarks  lulesh  osu-micro-benchmarks  ufs-weather-model

The ``ramble list`` command also accepts regular expressions. For example:

.. code-block:: console

    $ ramble list "h*"

might output the following:

.. rst-class:: hide-copy
.. code-block:: console

    ==> 5 applications
    hmmer  hostname  hpcc  hpcg  hpl

**NOTE**: The quotes around ``h*`` in the previous command avoid a potential
issue where your shell matches files that begin with the later ``h``, can
ramble prints no applications.

Additionally, applications can be filtered by their tags, e.g.

.. code-block:: console

    $ ramble list -t test-app
    ==> 1 applications
    hostname

The available tags (and their mappings to applications) can be listed using:

.. code-block:: console

    $ ramble attributes --all --tags

What's in an application?
^^^^^^^^^^^^^^^^^^^^^^^^^

Knowing what applications are available is only part of how you interact
with Ramble. Each application contains one or more workloads, all of which can
contain their own variables to control their behavior. The ``ramble info``
command can be used to get more information about a specific application
definition. As an example:

.. code-block:: console

    $ ramble info hostname

Will print the workloads and variables the ``hostname`` application definition contains.

Configuring experiments
------------------------

Create and Activate a Workspace
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Before you can configure your hostname experiments, you'll need to set up a
workspace. You can call this workspace ``hello_world``.

.. code-block:: console

    $ ramble workspace create hello_world

This will create a named workspace for you in:

.. code-block:: console

    $ $RAMBLE_ROOT/var/ramble/workspaces/hello_world

Now you can activate the workspace and view its default configuration.

.. code-block:: console

    $ ramble workspace activate hello_world
    $ ramble workspace info

You can use the ``ramble workspace info`` command after editing configuration
files to see how ramble would use the changes you made.

As an aside, if you had used:

.. code-block:: console

    $ ramble workspace create -d hello_world

Ramble would create an anonymous workspace for you in ``${PWD}/hello_world``
for more information on named and anonymous workspaces, see
:ref:`Ramble workspace documentation<ramble-workspaces>`.

For convenience, the workspace creation and activation can also be combined
in one command with the activate flag (``-a``):

.. code-block:: console

    $ ramble workspace create hello_world -a

Configure the Workspace
^^^^^^^^^^^^^^^^^^^^^^^^

Within the workspace directory, ramble creates a directory named ``configs``.
This directory contains generated configuration and template files. Each of
these files can be edited to configure the workspace, and examples will be
provided below.

The available files are:
* ``ramble.yaml`` This file describes all aspects of the workspace. This
includes the software stack, the experiments, and all variables.
* ``execute_experiment.tpl`` This file is a template shell script that will be
rendered to execute each of the experiments that ramble generates.

You can edit these files directly or with the command:

.. code-block:: console

    $ ramble workspace edit

To begin, you should edit the ``ramble.yaml`` file to set up the configuration
for your experiments. For this tutorial, replace the default yaml text with the
following contents:

.. literalinclude:: ../../../../examples/tutorial_1_config.yaml
   :language: YAML

Note that since the ``hostname`` application does not rely on a package manager, the software
dictionary has empty ``packages`` and ``environments`` dictionaries.

The second file you should edit is the ``execute_experiment.tpl`` template file.
This file contains a template script that will be rendered into an execution
script for each generated experiment. You can feel free to edit it as you need
to for your given system, but for this tutorial the default value will work.

As an alternative to directly editing the configuration files, Ramble provides
a set of commands (under the ``ramble workspace manage`` subcommand) that can
be used to manipulate the workspace configuration. To replicate the experiments
from this tutorial, you can run the following command (with a fresh workspace):

.. code-block:: console

     $ ramble workspace manage experiments hostname --wf local -v n_ranks=1 -e test

Setting Up the Experiments
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Now that the workspace is configured correctly, you can set up the experiments
in the active workspace using:

.. code-block:: console

    $ ramble workspace setup

This command will create experiment directories, download and expand input files,
and install the required software stack (and generate software environments for
each workload).

It can take a bit to run depending on if you need to build new software and how
long the input files take to download. If you'd like to see what will be installed,
you can do a dry run of the setup using:

.. code-block:: console

    $ ramble workspace setup --dry-run

For each setup run, a set of logs will be created at:

.. code-block:: console

    $ $RAMBLE_ROOT/var/ramble/workspaces/$workspace_root/logs

Each run will have its own primary log, along with a folder containing a log for each
experiment that is being configured.

Executing Experiments
^^^^^^^^^^^^^^^^^^^^^^

After the workspace is set up, its experiments can be executed. The two methods
to run the experiments are:

.. code-block:: console

    $ ramble on
   or;
    $ ./all_experiments

Analyzing Experiments
^^^^^^^^^^^^^^^^^^^^^^

Once the experiments within a workspace are complete, the experiments can be
analyzed. This is done through:

.. code-block:: console

    $ ramble workspace analyze

This creates a ``results`` file in the root of the workspace that contains
extracted figures of merit. If the experiments were successful, this file will
show the following results:

* possible hostname: hostname of machine the experiment was executed on

Cleanup the Workspace
^^^^^^^^^^^^^^^^^^^^^

After you are finished exploring the workspace and tutorial content, make sure
you deactivate the workspace using:

.. code-block:: console

    $ ramble workspace deactivate

Additionally, you can remove the workspace you used with:

.. code-block:: console

    $ ramble workspace remove hello_world
