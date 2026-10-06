.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

Configuring experiments
------------------------

For this tutorial, you are going to focus on creating experiments from the
``water_bare`` and ``water_gmx50`` workloads. The default configuration will
contain experiments for each value of the ``type`` variable, and a single value
for the ``size`` variable.

You will use a Ramble workspace to manage these experiments.

Create and Activate a Workspace
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Before you can configure your GROMACS experiments, you'll need to set up a
workspace. You can call this workspace ``basic_gromacs``.

.. code-block:: console

    $ ramble workspace create basic_gromacs

This will create a workspace for you in:

.. code-block:: console

    $ $RAMBLE_ROOT/var/ramble/workspaces/basic_gromacs

Now you can activate the workspace and view its default configuration.

.. code-block:: console

    $ ramble workspace activate basic_gromacs
    $ ramble workspace info

You can use the ``ramble workspace info`` command after editing configuration
files to see how ramble would use the changes you made.

Configure the Workspace
~~~~~~~~~~~~~~~~~~~~~~~

Within the workspace directory, ramble creates a directory named ``configs``.
This directory contains generated configuration and template files. Each of
these files can be edited to configure the workspace, and examples will be
provided below.

The available files are:

 * ``ramble.yaml`` This file describes all aspects of the workspace. This includes the software stack, the experiments, and all variables.
 * ``execute_experiment.tpl`` This file is a template shell script that will be rendered to execute each of the experiments that ramble generates.

You can edit these files directly or with the command ``ramble workspace edit``.

To begin, you should edit the ``ramble.yaml`` file to set up the configuration
for your experiments. For this tutorial, replace the default yaml text with the
contents of ``$RAMBLE_ROOT/examples/vector_matrix_gromacs_config.yaml``:

**NOTE**: This workspace utilizes the ``spack`` package
manager. As a result, it requires either that you
manually installed ``spack`` and it is available in
your path, or it will bootstrap a spack installation
for you in the workspace's ``shared/`` directory.
Modifications to the ``package_manager`` variant will
change this behavior.

.. literalinclude:: /../../../examples/vector_matrix_gromacs_config.yaml
   :language: YAML

Note that specifying compilers that Spack doesn't have installed may take a while.
To see available compilers, use ``spack compilers`` or see `Spack documentation
<https://spack.readthedocs.io/en/latest/getting_started.html#spack-compilers>`_
for more information.

The second file you should edit is the ``execute_experiment.tpl`` template file.
This file contains a template script that will be rendered into an execution
script for each generated experiment. You can feel free to edit it as you need
to for your given system, but for this tutorial the default value will work.
