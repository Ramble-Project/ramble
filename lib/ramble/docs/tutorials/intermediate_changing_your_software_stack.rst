.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _changing_a_software_stack_tutorial:

=============================
Changing Your Software Stack
=============================

.. tutorial-header:: software_stack

In this tutorial, you will learn how to configure software packages, compilers,
and environments in a Ramble workspace. You will explore how Ramble specifies
software stacks via package managers like Spack, how to modify package versions
and variants, and how to parameterize software environments across parameter
sweeps using vectors and matrices.

This tutorial builds on concepts introduced in previous tutorials. Please make
sure you review :ref:`vector_and_matrix_tutorial` before starting.

.. contents:: Table of Contents
   :depth: 2
   :local:

Creating the Workspace
----------------------

.. tutorial-workspace-create:: software

   Then, set the workspace-level variables:

   .. code-block:: console

       $ ramble config add variables:processes_per_node:16
       $ ramble config add "variables:mpi_command:mpirun -n {n_ranks} -ppn {processes_per_node}"
       $ ramble config add 'variables:batch_submit:"{execute_experiment}"'

Software Description
--------------------

A Ramble workspace defines its software requirements inside the ``software:``
block of ``ramble.yaml``. Software stacks are composed of two core concepts:

1. **Packages** (``software:packages``): Define individual software
   specifications (e.g. compilers, MPI libraries, application binaries) using
   the syntax of the chosen package manager (such as Spack specs). Packages
   can declare dependencies on other defined packages, such as a compiler.
2. **Environments** (``software:environments``): Group one or more defined
   packages into a cohesive execution environment.

Let's examine how a software stack is represented in the configuration:

.. tutorial-app-template::

   .. code-block:: YAML

       software:
         packages:
           gcc14:
             pkg_spec: gcc@14.2.0
             compiler_spec: gcc@14.2.0
           intel-mpi:
             pkg_spec: intel-oneapi-mpi@2021.17.2
             compiler: gcc14
           {pkg_name}:
             pkg_spec: {pkg_spec}
             compiler: gcc14
         environments:
           {app}:
             packages:
             - intel-mpi
             - {pkg_name}

In this configuration:

* The ``packages`` block defines the software packages available for experiments.
* The ``compiler`` attribute points to another package defined in the ``packages`` block that provides the compiler.
* The ``environments`` block groups defined packages. By default, an experiment
  looks for an environment named after its application (e.g., an experiment for
  ``wrf`` looks for an environment named ``wrf``). You can override this default
  by setting the ``env_name`` variable in an experiment's variables block.

You can view the software stack configured in your workspace at any time:

.. code-block:: console

    $ ramble workspace info

This command prints a summary of both experiment definitions and the rendered
software packages and environments.

.. tutorial-app-template::

   .. code-block:: console

       Software Stack:
           Template package: gcc14
             spack packages:
               Rendered package: gcc14
                 Spec: gcc@14.2.0
                 Compiler spec: gcc@14.2.0
           Template package: intel-mpi
             spack packages:
               Rendered package: intel-mpi
                 Spec: intel-oneapi-mpi@2021.17.2
                 Compiler: gcc14
           Template package: {pkg_name}
             spack packages:
               Rendered package: {pkg_name}
                 Spec: {pkg_spec}
                 Compiler: gcc14
           Template environment: {app}
             Base environment: {app}
               Packages:
               - intel-mpi
               - {pkg_name}

Changing Software Definitions
-----------------------------

When ``variants:package_manager:spack`` is set, Ramble uses Spack to realize
the software environment. You can query information about any package directly
from Spack:

.. tutorial-app-template::

   .. code-block:: console

       $ spack info {app}

This command displays all versions, variants, and dependencies known to Spack.

Modifying Packages via the CLI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can manage software definitions directly using ``ramble workspace manage software``.
For example, to update or overwrite an existing package definition:

.. tutorial-app-template::
   :wrf: mod_spec=wrf@4.2 build_type=dm+sm compile_type=em_real nesting=basic ~pnetcdf
   :gromacs: mod_spec=gromacs@2025.4
   :hpl: mod_spec=hpl@2.3 +openmp

   .. code-block:: console

       $ ramble workspace manage software --package-name {pkg_name} \
           --package-spec '{mod_spec}' \
           --compiler gcc14 \
           --overwrite


Modifying Packages by Editing Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Alternatively, you can edit ``configs/ramble.yaml`` directly using:

.. code-block:: console

    $ ramble workspace edit

This opens your workspace configuration in your default ``$EDITOR``. After making
changes, verify the software stack with ``ramble workspace info``.

Versions in Ramble
------------------

In addition to Spack's versioning, Ramble maintains its own internal version
awareness within each application definition. This enables conditional logic
and directives based on application version numbers.

You can inspect the versions known to Ramble:

.. tutorial-app-template::

   .. code-block:: console

       $ ramble info --attrs known_versions -v {app}

If an application version is not yet defined in Ramble, it can be added to the
application definition using the ``version()`` directive. See the
:ref:`developer guide<application-dev-version-directive>` for details.

Adding Package Variants
-----------------------

Spack variants allow you to customize compiler optimizations, feature flags,
and external library support. These are defined directly within the ``pkg_spec``
string.

For instance, you might customize build types or enable/disable SIMD instruction
sets:

.. tutorial-app-template::
   :wrf: custom_pkg=wrfv4-custom;custom_spec=wrf@4.2 build_type=dm+sm compile_type=em_real nesting=basic ~pnetcdf
   :gromacs: custom_pkg=gromacs-custom;custom_spec=gromacs@2025.3 +openmp ~mpi
   :hpl: custom_pkg=hpl-custom;custom_spec=hpl@2.3 +openmp

   .. code-block:: YAML

       software:
         packages:
           {custom_pkg}:
             pkg_spec: {custom_spec}
             compiler: gcc14

Vector and Matrix Software Definitions
--------------------------------------

Just as experiment parameters can be expanded using vectors and matrices,
software definitions can also be parameterized with variables. This allows you
to run experiments across multiple software versions, compilers, or build
configurations within a single workspace.

To matrix across software versions:

1. Define a variable vector for the version in your experiment definition (or at the workspace level).
2. Parameterize package and environment names using the variable syntax (e.g. ``{wrf_version}``, ``{gromacs_version}``, or ``{hpl_version}``).
3. Set ``env_name`` in the experiment variables to point to the parameterized environment.
4. Add the version variable to the experiment's ``matrix`` list.

Full Workflow Commands
~~~~~~~~~~~~~~~~~~~~~~

Here are the complete commands to set up the parameterized software matrix workspace:

.. tutorial-snippet:: software_stack commands.sh

Resulting Workspace Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The resulting ``configs/ramble.yaml`` file should contain the following:

.. tutorial-snippet:: software_stack ramble.yaml

Inspecting the Matrix Experiments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Running ``ramble workspace info`` demonstrates how Ramble expands the combinatorial
software matrix into 16 distinct experiments across workloads, rank counts, and software versions:

.. tutorial-app-template::

   .. code-block:: console

       $ ramble workspace info
       Workspace: software_{app}

       Experiments:
         Application: {app}
           Workload: {app_workload}
             Experiment 1: {app}.{workload}.{vec_p1}_1ranks-{sw_v1}
             Experiment 2: {app}.{workload}.{vec_p1}_1ranks-{sw_v2}
             Experiment 3: {app}.{workload}.{vec_p1}_2ranks-{sw_v1}
             Experiment 4: {app}.{workload}.{vec_p1}_2ranks-{sw_v2}
             Experiment 5: {app}.{workload}.{vec_p2}_1ranks-{sw_v1}
             Experiment 6: {app}.{workload}.{vec_p2}_1ranks-{sw_v2}
             Experiment 7: {app}.{workload}.{vec_p2}_2ranks-{sw_v1}
             Experiment 8: {app}.{workload}.{vec_p2}_2ranks-{sw_v2}
             Experiment 9: {app}.{workload2}.{vec_p1}_1ranks-{sw_v1}
             Experiment 10: {app}.{workload2}.{vec_p1}_1ranks-{sw_v2}
             Experiment 11: {app}.{workload2}.{vec_p1}_2ranks-{sw_v1}
             Experiment 12: {app}.{workload2}.{vec_p1}_2ranks-{sw_v2}
             Experiment 13: {app}.{workload2}.{vec_p2}_1ranks-{sw_v1}
             Experiment 14: {app}.{workload2}.{vec_p2}_1ranks-{sw_v2}
             Experiment 15: {app}.{workload2}.{vec_p2}_2ranks-{sw_v1}
             Experiment 16: {app}.{workload2}.{vec_p2}_2ranks-{sw_v2}

Changing Package Managers
-------------------------

The experiments in this tutorial assumed the use of ``spack`` as your package
manager:

.. code-block:: YAML

    variants:
      package_manager: spack

Ramble supports multiple package managers. You can view all available package
managers using:

.. code-block:: console

    $ ramble list --type package_managers

To disable package manager integration and rely entirely on pre-existing host
software, set ``package_manager`` to ``user-managed``:

.. code-block:: YAML

    variants:
      package_manager: user-managed

.. note::
   When using the ``user-managed`` package manager, all software needs to be
   either referred to with absolute paths, or within the path of the execution
   environment. Ramble has some variable definitions that will be required /
   expected to help facilitate this for you, and they will show up as
   ``<pkg_name>_path`` variables, where ``<pkg_name>`` is the name of the
   software package used in the experiment. For example: ``wrf_path`` would
   refer to the location where WRF is installed.

Executing Experiments
---------------------

.. tutorial-execute:: software
   :timing-note: When not running in dry-run mode, ``ramble workspace setup`` will concretize and build multiple software environments (including multiple application versions and compilers) from source if they are not already installed on your system, and ``ramble on`` executes all 16 experiments in the matrix across both software stacks and workloads.
   :dry-run-cmds: ls -la $RAMBLE_ROOT/var/ramble/workspaces/software_{app}/software/; ls -la $RAMBLE_ROOT/var/ramble/workspaces/software_{app}/experiments/{app}/{workload}/
   :results-text: After analysis, ``results.latest.txt`` in the workspace root will compare the figures of merit across the different software environments and compilers.


Cleaning the Workspace
----------------------

.. tutorial-workspace-cleanup:: software


