.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _eessi_package_manager_tutorial:

===============================
Using the EESSI Package Manager
===============================

In this tutorial, you will set up and run a benchmark simulation using
`GROMACS <https://www.gromacs.org/>`_, a free and open-source application
for molecular dynamics. The execution environment will be created and managed
using the
`European Environment for Scientific Software Installations (EESSI) package manager <https://www.eessi.io/docs/>`_.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content,
however this tutorial is fully stand-alone as far as steps you need to perform.

Application Information
-----------------------

As mentioned above, this tutorial uses the `GROMACS <https://www.gromacs.org/>`_
application definition. We will begin with the ``water_bare`` and ``water_gmx50``
workloads, as they are able to execute in a short amount of time.

Using a previously installed ``ramble``, the following command can be used to
get information about these workloads:

.. code-block:: console

    $ ramble info --attrs workloads -v -p "water*" gromacs

Under the workloads marked by ``Workload: water_bare`` and
``Workload: water_gmx50``, you should see something like the following output:

.. code-block:: console

    Workload: water_gmx50
        Executables: ['pre-process', 'execute-gen']
        Inputs: ['water_gmx50_bare']
        Tags: []
        Variables:
            Unconditional:
                size:
                    Description: Workload size
                    Default: 1536
                    Suggested Values: ['0000.65', '0000.96', '0001.5', '0003', '0006', '0012', '0024', '0048', '0096', '0192', '0384', '0768', '1536', '3072']
                type:
                    Description: Workload type.
                    Default: pme
                    Suggested Values: ['pme', 'rf']
                input_path:
                    Description: Input path for water GMX50
                    Default: {water_gmx50_bare}/{size}
    Workload: water_bare
        Executables: ['pre-process', 'execute-gen']
        Inputs: ['water_bare_hbonds']
        Tags: []
        Variables:
            Unconditional:
                size:
                    Description: Workload size
                    Default: 1536
                    Suggested Values: ['0000.65', '0000.96', '0001.5', '0003', '0006', '0012', '0024', '0048', '0096', '0192', '0384', '0768', '1536', '3072']
                type:
                    Description: Workload type.
                    Default: pme
                    Suggested Values: ['pme', 'rf']
                input_path:
                    Description: Input path for water bare hbonds
                    Default: {water_bare_hbonds}/{size}

Here we see that both of these workloads have a ``type`` variable (with
possible values of ``pme`` and ``rf``) and a ``size`` variable with a variety
of available sizes.

To determine a suggested software configuration, you can use:

.. code-block:: console

  $ ramble info --attrs software_specs,compilers -v gromacs

With this command, you should see output similar to the following:

.. code-block:: console

  ##################
  # software_specs #
  ##################
  intel-mpi:
      pkg_spec: intel-oneapi-mpi@2021.17.2

      When:
          package_manager_family=spack

  gromacs:
      pkg_spec: gromacs@2025.3
      compiler: gcc14

      When:
          package_manager_family=spack

  gromacs:
      pkg_spec: GROMACS/2024.1-foss-2023b

      When:
          package_manager_family=eessi
          application_version@2024.1

  #############
  # compilers #
  #############
  gcc14:
      pkg_spec: gcc@14.2.0

      When:
          package_manager_family=spack



Package Manager Information
---------------------------

When learning how to use a new package manager in Ramble, it can be useful to
inspect the information of the package manager definition. To do this, execute
the following command:

.. code-block:: console

  $ ramble info --type package_managers eessi
  or;
  $ ramble info builtin.pkg_man.eessi

This should print a summary of the ``eessi`` definition, as follows:

.. code-block:: console

  Package Manager: eessi

  Description:
      Package manager definition for EESSI
      
          This package manager uses the European Environment for Scientific Software
          Installations to stream binaries from an EESSI mirror.
      
          https://www.eessi.io/
      
      
          To control the target architecture used, add EESSI_SOFTWARE_SUBDIR_OVERRIDE
          to the workspace's environment variable definitions.
          

  maintainers:
      douglasjacobsen

  pipelines:
      analyze  archive  mirror  setup  pushdeployment  pushtocache  execute  logs

  builtins:
      package_manager_builtin::eessi::module_load  package_manager_builtin::eessi::module_list  package_manager_builtin::eessi::eessi_init

  object_variables:
      eessi_version:
      Description: Version of EESSI to use
      Default: 2023.06
      Suggested Values: [None]


  registered_phases:
      analyze:
          add_software_to_results

      setup:
          write_module_commands


Examining the ``object_variables`` section, you can see that ``eessi``
has a defined variable named ``eessi_version``. To get more information about
this portion of the package manager definition, you can execute the following:

.. code-block:: console

  $ ramble info --type package_managers --attrs object_variables -v eessi
  or;
  $ ramble info builtin.pkg_man.eessi --attrs object_variables -v

Which should print something like the following output:

.. code-block:: console

  ####################
  # object_variables #
  ####################
      eessi_version:
      Description: Version of EESSI to use
      Default: 2023.06
      Suggested Values: [None]

Here, we can see that the version of ``eessi`` can be controlled through the use
of the ``eessi_version`` variable definition. Defining this variable within an
experiment can allow you to parameterize the versions of EESSI used.

Configuring experiments
-----------------------

For this tutorial, you are going to focus on creating experiments from the
``water_bare`` and ``water_gmx50`` workloads. The default configuration will
contain experiments for each value of the ``type`` variable, and a single value
for the ``size`` variable.

You will use a Ramble workspace to manage these experiments.

Create and Activate a Workspace
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. tutorial-workspace-create:: eessi_gromacs
   :single:
   :separate-activate:

You can use the ``ramble workspace info`` command after editing configuration
files to see how ramble would use the changes you made.

.. code-block:: console

    $ ramble workspace info

Configure the Workspace
~~~~~~~~~~~~~~~~~~~~~~~

Edit the workspace's ``configs/ramble.yaml`` file (either directly or with
``ramble workspace edit``) to match the contents of
``$RAMBLE_ROOT/examples/gromacs_eessi_config.yaml``:

.. note::
   This workspace utilizes the ``eessi`` package manager. As a result, it
   requires ``eessi`` is installed following
   `EESSI installation instructions <https://www.eessi.io/docs/getting_access/native_installation/>`_.
   Modifications to the ``package_manager`` variant will change this behavior.

.. literalinclude:: ../../../../examples/gromacs_eessi_config.yaml
   :language: YAML

Executing Experiments
---------------------

.. tutorial-execute:: eessi_gromacs
   :single:
   :apps: gromacs
   :package-manager: none
   :dry-run-cmds: ls -la $RAMBLE_ROOT/var/ramble/workspaces/eessi_gromacs/experiments/gromacs/water_gmx50/pme_single_rank; cat $RAMBLE_ROOT/var/ramble/workspaces/eessi_gromacs/experiments/gromacs/water_gmx50/pme_single_rank/execute_experiment
   :include-foms:

Cleanup the Workspace
---------------------

.. tutorial-workspace-cleanup:: eessi_gromacs
   :single:


