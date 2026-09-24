.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. getting_started:

===============
Getting Started
===============

----------------
What is Ramble?
----------------

Ramble stands for Reproducible And Measurable Benchmarks in a Layered Environment.

Ramble is a multi-platform experimentation framework to increase exploration
productivity and improve reproducibility. Ramble is capable of driving software
installation, acquiring input files, configuring experiments, and extracting results.
It works on Linux, macOS, and many supercomputers.

Ramble can be used to configure a variety of experiments for applications. These
can include anything from:

* Scientific parameter sweeps
* Performance focused scalaing studies
* Compiler flag sweeps

--------------------
System Requirements
--------------------

Ramble requires Python 3.6.8 or greater. Some applications also require
`Spack <https://spack.io/about/#install-spack>`_, which is used for managing
binaries and their dependencies.

Ramble's Python dependencies are listed within the top level requirements.txt
file.

For Ramble developers, pytest and flake8 are required for linting and performing
unit tests.

-------------
Installation
-------------

There are two ways to install Ramble. The first, and recommended, approach is to
clone its `github repository <https://github.com/Ramble-Project/ramble>`_.
This can be done with:

.. code-block:: console

    $ git clone -c feature.manyFiles=true https://github.com/Ramble-Project/ramble.git

By default, this will checkout the ``develop`` branch, which is the most
up-to-date version of Ramble. Several tags, as well as the ``main`` branch
(which contains the latest tag) can provide a more stable exeperience.

The second approach is to download one of the releases from
`Ramble's releases page <https://github.com/Ramble-Project/ramble/releases>`_

Once Ramble is available on your system, its python dependencies can be
installed using the ``requirements.txt`` file included in the root of Ramble's
source directory.

To install this, you can use:

.. code-block:: console

    $ pip install -r requirements.txt

However, the exact command will depend on your environment.

^^^^^^^^^^^^^^
Shell Support
^^^^^^^^^^^^^^

Once you have cloned Ramble, we recommend sourcing the appropriate script for your shell:

.. code-block:: console

   # For bash/zsh/sh
   $ . ramble/share/ramble/setup-env.sh

   # For tcsh/csh
   $ source ramble/share/ramble/setup-env.csh

   # For fish
   $ . ramble/share/ramble/setup-env.fish

That's it! You're ready to use Ramble.

Sourcing these files will put the ``ramble`` command in your ``PATH``.

If you do not want to use Ramble's shell support, you can always just run the
``ramble`` command directly from ``ramble/bin/ramble``.

When the ``ramble`` command is executed, it searches for an appropriate Python
interpreter to use, which can be explicitly overridden by setting the
``RAMBLE_PYTHON`` environment variable. When sourcing the appropriate shell
setup script, ``RAMBLE_PYTHON`` will be set to the interpreter found at
sourcing time, ensuring future invocations of the ``ramble`` command will
continue to use the same consistent python version regardless of changes in the
environment.

-------------
Command Help
-------------

To get information on the available commands, you can execute:

.. code-block:: console

    $ ramble help --all


For help with sub-commands, the ``-h`` flag can be used:

.. code-block:: console

   $ ramble <subcommand> -h

^^^^^^^^^^^^^^^^
Debugging Ramble
^^^^^^^^^^^^^^^^

When an issue occurs while running Ramble, it can be useful to get additionally
debugging information. To enable the debugging mode in Ramble, you can use the
`-d` global option, as follows:

.. code-block:: console

    $ ramble -d <subcommand>
    or;
    $ ramble --debug <subcommand>

---------------------
Defined Applications
---------------------

In order to get information about the available applications defined within
``ramble``, you can use the command:

.. code-block:: console

   $ ramble list

This command uses filtering to search the defined applications, e.g.:

.. code-block:: console

   $ ramble list hpl

will list ``hpl``, ``intel-hpl``, and other versions of ``hpl``.

Available applications can be filtered using tags, e.g.:

.. code-block:: console

    $ ramble list -t weather

will list ``wrf``, ``ufs-weather-model``, and other applications tagged with
``weather``. The available tags can be seen with:

.. code-block:: console

    $ ramble attributes --tags --all

---------------------
Application Workloads
---------------------

To get detailed information about an application, you can use the command:

.. code-block:: console

    $ ramble info <application>

For example:

.. code-block:: console

    $ ramble info hpl

Will show that ``hpl`` has two workloads

* ``standard``
* ``calculator``

that experiments can be generated from. The ``ramble info`` command can also be
used to see what variables each workload has, and potentially some suggested
values for variables with a limited set of allowed values.

.. _ramble-workspaces:

------------------
Ramble Workspaces
------------------

To configure experiments, you need to use a Ramble workspace. A workspace is a
self contained directory that contains configuration files, template files, and
eventually will contain spack environments, input files, and experiment
execution directories.

Workspaces fall into one of two categories:

Named Workspaces (created with ``ramble workspace create <name>``) are located
in ``$ramble/var/workspaces/<workspace_name>``. These workspaces can be managed
with other ramble commands directly (e.g. ``ramble workspace remove <name>``).

Anonymous Workspaces (created with ``ramble workspace create -d <path>``) are
located in the provided path, and need to be managed independently of ramble
commands.

A workspace can be selected when executing ``ramble`` through the use of the
``-w`` and ``-D`` flags.

^^^^^^^^^^^^^^^^^^^^
Creating Workspaces
^^^^^^^^^^^^^^^^^^^^

To create a new Ramble workspace, you can use:

.. code-block:: console

    $ ramble workspace create [<name>] [-d <path>]

Once a workspace is created, you can activate the workspace. This allows some
subsequent commands to work without explicitly passing in a workspace. This
is done through:

.. code-block:: console

    $ ramble workspace activate [<name>/<path>]

With an activated workspace, you can get information about the workspace with:

.. code-block:: console

    $ ramble workspace info

^^^^^^^^^^^^^^^^^^^^^^^^
Configuring A Workspace
^^^^^^^^^^^^^^^^^^^^^^^^

Within the created workspace, a ``configs`` directory is created to house the
configuration files.

A newly created workspace will contain:

.. code-block:: console

   - configs
     | - ramble.yaml
     | - execute_experiment.tpl

The ``ramble.yaml`` file contains the configuration of the workspace. Any file
placed in this ``configs`` directory with the extension ``.tpl`` will generate
a "rendered" version within every experiment directory.

These files can be edited with your favorite editor, or though the command:

.. code-block:: console

    $ ramble workspace edit

Flags exist to control whether you want to edit a template file, or the
configuration file.

Ramble automatically defines variables for each template file found in the
``configs`` directory. The variable name is the template's path relative to
the ``configs`` directory, without the ``.tpl`` extension. Its value contains the path to the rendered file
within every experiment directory.

For example, a template named ``configs/execute_experiment.tpl`` will define
a variable ``{execute_experiment}`` that expands to the path of the generated
file within the experiment directory (more explicitly,
``{experiment_run_dir}/execute_experiment``).

^^^^^^^^^^^^^^^^^^^^^^^^^
Concretizing A Workspace
^^^^^^^^^^^^^^^^^^^^^^^^^

After configuring a workspace with applications, workloads, and experiments,
Ramble can be used to inject default software configurations for the requested
experiments. To do this, you can use the:

.. code-block:: console

    $ ramble workspace concretize

This will fill out the ``spack`` dictionary within the ``ramble.yaml`` file
with defaults. The defaults can be configured however you want before
installing the actual software.

^^^^^^^^^^^^^^^^^^^^^^^
Setting Up A Workspace
^^^^^^^^^^^^^^^^^^^^^^^

Once a workspace is concretized, it can be set up. This process is executed through:

.. code-block:: console

    $ ramble workspace setup

The setup action will:
 - Install required / requested software
 - Download required input files
 - Create and configure experiment directories
 - Create the ``all_experiments`` script

^^^^^^^^^^^^^^^^^^^^^^
Executing Experiments
^^^^^^^^^^^^^^^^^^^^^^

After the workspace is set up, its experiments can be executed. The two methods
to run the experiments are:

.. code-block:: console

    $ ramble on
   or;
    $ ./all_experiments

^^^^^^^^^^^^^^^^^^^^^^
Analyzing Experiments
^^^^^^^^^^^^^^^^^^^^^^

Once the experiments within a workspace are complete, the experiments can be
analyzed. This is done through:

.. code-block:: console

    $ ramble workspace analyze

This creates a ``results`` file in the root of the workspace that contains
extracted figures of merit.

^^^^^^^^^^^^^^^^^^^^^^
Archiving A Workspace
^^^^^^^^^^^^^^^^^^^^^^

Ramble can create an archive of a workspace. This is a self contained copy of various important aspects of the workspace, including:
 - All files in the ``configs`` directory
 - Rendered templates in the experiments directories
 - Files that would have figures of merit extracted
 - Auxiliary files that an application lists for archival
 - All generated spack.yaml files

You can archive a workspace with:

.. code-block:: console

    $ ramble workspace archive

And you can create a tar-ball with:

.. code-block:: console

    $ ramble workspace archive -t
