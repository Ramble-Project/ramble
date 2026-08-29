.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _workspace-config-command-tutorial:

=============================================
Using the ``ramble workspace config`` command
=============================================

Ramble contains many configuration sections, which can be defined in separate
files across several scopes that represent different precedence levels. For
more information on these, see the :ref:`configuration files
<configuration-files>` documentation.

All of these configuration files impact the resulting configuration within a
:ref:`workspace<workspace-config>`. It can be difficult to create a hermetic
definition of the experiments performed, given many configuration files across
a system can influence the resulting experiment definition. To help with the
process of constructing a unifed configuration representing experiment, Ramble
has the ``workspace config`` command.

In this tutorial, you will learn how to use the ``ramble workspace config``
command, to unify configuration files, and remove unnecessary portions of a
configuration file to make it easier for users to digest and share.

This tutorial builds off of concepts introduce in other tutorials, mostly
around configuring a workspace. Configuring experiments within a workspace will
not be covered in this tutorial, however we will use pre-configured workspaces
to illustrate the utility of the ``workspace config`` command.

------------------------
Create Complex Workspace
------------------------

To begin, we will construct a complex workspace to serve as an example of
something we want to share with other users. Before configuring the workspace,
it needs to be created using something like the following:

.. code-block:: console

   $ ramble workspace create -d includes-workspace

Within this workspace, lets create a separate file to represent the
applications configuration section. After this file is created, we'll include
it into the ramble configuration to show how workspace configuration files can
use indirection to simplify their contents. For the next step, edit the
``applications.yaml`` file in the root of the new workspace:

.. code-block:: console

  $ $EDITOR includes-workspace/applications.yaml

In this file, write the following contents:

.. code-block:: yaml

  applications:
    gromacs:
      variants:
        package_manager: spack
      workloads:
        water_bare:
          experiments:
            '{size}-{n_nodes}nodes':
              variables:
                n_nodes: [1, 2, 4]
                size: [1536, 3072]
                compiler_name: gcc14
                mpi_name: openmpi5
                gromacs_version: 2023.1
                test_variable: test_value
              matrix:
              - n_nodes
              - size

In addition, create a ``software.yaml`` file in the root of the workspace:

.. code-block:: console

  $ $EDITOR includes-workspace/software.yaml

In this file, write the following contents:

.. code-block:: yaml

  software:
    packages:
      gcc15:
        pkg_spec: gcc@15.1.0
      gcc14:
        pkg_spec: gcc@14.2.0
      gromacs:
        pkg_spec: gromacs@{gromacs_version}
        compiler: '{compiler_name}'
      openmpi5:
        pkg_spec: openmpi@5.0.8
      intel-mpi:
        pkg_spec: intel-oneapi-mpi@2021.17.2
      wrf:
        pkg_spec: wrf@4.3.3
        compiler: '{compiler_name}'
    environments:
      gromacs:
        packages:
        - gromacs
        - '{mpi_name}'
      wrf:
        packages:
        - wrf
        - '{mpi_name}'


------------------------
Including External Files
------------------------

Now that we have two configuration files, we will configure the workspace to
:ref:`include<workspace_including_external_files>` them. To achieve this, we
will use the ``ramble workspace manage includes`` command.

.. code-block:: console

  $ ramble -D includes-workspace workspace manage includes -a '$workspace_root/applications.yaml'
  $ ramble -D includes-workspace workspace manage includes -a '$workspace_root/software.yaml'

This step causes the ramble workspace to include these YAML files when
constructing its merged configuration file.

At this stage, you can explore the experiments defined in the workspace using:

.. code-block:: console

   $ ramble -D includes-workspace info

This command should output that workspace contains 6 experiments, representing
the three node counts crossed with the two sizes.

----------------------------------------
Squashing A Workspace Configuration File
----------------------------------------

Now, at this stage we have a workspace that is pieced together with external
configuration files. This can be fairly difficult to share with other users if
the configuration files are stored outside of the workspace, or if there are
additional configuration options defined in other configuration scopes.

For the next step, create a new workspace which will represent the squashed
configuration file.

.. code-block:: console

  $ ramble workspace create -d squash-workspace

This workspace does not contain any experiments or configuration at this stage.
At this point, overwrite the configuration of this workspace with a squashed
configuration file form the ``includes-workspace`` you constructed earlier.

.. code-block:: console

   $ ramble -D includes-workspace workspace config -p > squash-workspace/configs/ramble.yaml

At this stage, both workspaces should contain the same experiments. To verify,
you can examine the differences from the following commands:

.. code-block:: console

   $ ramble -D includes-workspace info
   $ ramble -D squash-workspace info

Additionally, the ``squash-workspace`` should not refer to any external files.
To verify this, explore the contents of the configuration file:

.. code-block:: console

   $ less squash-workspace/configs/ramble.yaml

This file should also contain far more information, such as every configuration
scope that was defined in ramble outside of the workspace with the exception of
any ``_repos`` configuration sections. These are omitted because they are not
valid to define within a workspace configuration file.

At this stage, you have learned how to squash a configuration file which can be
shared with other users to easily reproduce your experiments.

-----------------------------------------------------
Removing Unnecessary Portions of a Configuration File
-----------------------------------------------------

If you examined the external configuration files we wrote earlier in the
``include-workspace`` you might have noticed there are several portions that
are not used directly. This includes variables in the experiment definition,
along with software packages within the software definitions.

Commands are provided to help remove unneeded or unused portions of
configuration files, to simplify them before sharing with other people.

To simplify the configuration file, execute the following commands:

.. code-block:: console

  $ ramble -D squash-workspace workspace config --simplify-variables
  $ ramble -D squash-workspace workspace config --simplify-software

These two commands will prune any software definitions (packages or
environments) that are not used by an experiment, and additionally remove any
variables that are not used by experiments as well.

The result should be that packages (such as ``wrf``, ``gcc15``, and
``intel-mpi``) and environments (such as ``wrf``) are removed from the
software configuration section, while variables (such as ``test_variable``) are
removed from the variables dictionaries.

**NOTE**: Variable removal will happen across all of the scopes, even though in
this example we only illustrate removing variables form the experiment scope.

-----------------------
Conclusion And Cleanup
-----------------------

At the end of this tutorial, you should have learned how to construct a
workspace consisting of externally referenced configuration files. You then
learned how to squash the configuration file out of this workspace, and
simplify the software and variables contained within the resulting workspace.

At this stage, if you are finished using the workspaces, you can clean up your
workspaces using:

.. code-block:: console

   $ rm -rf include-workspace squash-workspace


The skills learned in this tutorial should help you construct more reproducible
artifacts for experiments, regardless of how you initially configured the
experiments.
