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

.. raw:: html

   <div class="tn-app-switcher" data-recipe="software_stack"></div>

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

.. container:: tn-workspace-create

   First, create and activate a new workspace for this tutorial:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace create software_wrf
          $ ramble workspace activate software_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace create software_gromacs
          $ ramble workspace activate software_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace create software_hpl
          $ ramble workspace activate software_hpl

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

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: YAML

       software:
         packages:
           gcc14:
             pkg_spec: gcc@14.2.0
             compiler_spec: gcc@14.2.0
           intel-mpi:
             pkg_spec: intel-oneapi-mpi@2021.17.2
             compiler: gcc14
           wrfv4-4.2:
             pkg_spec: wrf@4.2 build_type=dm+sm compile_type=em_real nesting=basic ~pnetcdf
             compiler: gcc14
         environments:
           wrf:
             packages:
             - intel-mpi
             - wrfv4-4.2

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: YAML

       software:
         packages:
           gcc14:
             pkg_spec: gcc@14.2.0
             compiler_spec: gcc@14.2.0
           intel-mpi:
             pkg_spec: intel-oneapi-mpi@2021.17.2
             compiler: gcc14
           gromacs-2025.3:
             pkg_spec: gromacs@2025.3
             compiler: gcc14
         environments:
           gromacs:
             packages:
             - intel-mpi
             - gromacs-2025.3

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: YAML

       software:
         packages:
           gcc14:
             pkg_spec: gcc@14.2.0
             compiler_spec: gcc@14.2.0
           intel-mpi:
             pkg_spec: intel-oneapi-mpi@2021.17.2
             compiler: gcc14
           hpl-2.3:
             pkg_spec: hpl@2.3 +openmp
             compiler: gcc14
         environments:
           hpl:
             packages:
             - intel-mpi
             - hpl-2.3

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

.. container:: tn-app-variant tn-app-wrf

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
           Template package: wrfv4-4.2 
             spack packages:
               Rendered package: wrfv4-4.2 
                 Spec: wrf@4.2 build_type=dm+sm compile_type=em_real nesting=basic ~pnetcdf
                 Compiler: gcc14
           Template environment: wrf
             Base environment: wrf
               Packages:
               - intel-mpi
               - wrfv4-4.2

.. container:: tn-app-variant tn-app-gromacs

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
           Template package: gromacs-2025.3 
             spack packages:
               Rendered package: gromacs-2025.3 
                 Spec: gromacs@2025.3
                 Compiler: gcc14
           Template environment: gromacs
             Base environment: gromacs
               Packages:
               - intel-mpi
               - gromacs-2025.3

.. container:: tn-app-variant tn-app-hpl

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
           Template package: hpl-2.3 
             spack packages:
               Rendered package: hpl-2.3 
                 Spec: hpl@2.3 +openmp
                 Compiler: gcc14
           Template environment: hpl
             Base environment: hpl
               Packages:
               - intel-mpi
               - hpl-2.3

Changing Software Definitions
-----------------------------

When ``variants:package_manager:spack`` is set, Ramble uses Spack to realize
the software environment. You can query information about any package directly
from Spack:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       $ spack info wrf

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       $ spack info gromacs

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       $ spack info hpl

This command displays all versions, variants, and dependencies known to Spack.

Modifying Packages via the CLI
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You can manage software definitions directly using ``ramble workspace manage software``.
For example, to update or overwrite an existing package definition:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       $ ramble workspace manage software --package-name wrfv4-4.2 \
           --package-spec 'wrf@4.2 build_type=dm+sm compile_type=em_real nesting=basic ~pnetcdf' \
           --compiler gcc14 \
           --overwrite

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       $ ramble workspace manage software --package-name gromacs-2025.3 \
           --package-spec 'gromacs@2025.4' \
           --compiler gcc14 \
           --overwrite

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       $ ramble workspace manage software --package-name hpl-2.3 \
           --package-spec 'hpl@2.3 +openmp' \
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

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       $ ramble info --attrs known_versions -v wrf

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       $ ramble info --attrs known_versions -v gromacs

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       $ ramble info --attrs known_versions -v hpl

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

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: YAML

       software:
         packages:
           wrfv4-custom:
             pkg_spec: wrf@4.2 build_type=dm+sm compile_type=em_real nesting=basic ~pnetcdf
             compiler: gcc14

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: YAML

       software:
         packages:
           gromacs-custom:
             pkg_spec: gromacs@2025.3 +openmp ~mpi
             compiler: gcc14

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: YAML

       software:
         packages:
           hpl-custom:
             pkg_spec: hpl@2.3 +openmp
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

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/software_stack_wrf_commands.sh
      :language: console

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/software_stack_gromacs_commands.sh
      :language: console

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/software_stack_hpl_commands.sh
      :language: console

Resulting Workspace Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The resulting ``configs/ramble.yaml`` file should contain the following:

.. container:: tn-app-variant tn-app-wrf

   .. literalinclude:: ../_generated/snippets/software_stack_wrf_ramble.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-gromacs

   .. literalinclude:: ../_generated/snippets/software_stack_gromacs_ramble.yaml
      :language: YAML

.. container:: tn-app-variant tn-app-hpl

   .. literalinclude:: ../_generated/snippets/software_stack_hpl_ramble.yaml
      :language: YAML

Inspecting the Matrix Experiments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Running ``ramble workspace info`` demonstrates how Ramble expands the combinatorial
software matrix into 16 distinct experiments across workloads, rank counts, and software versions:

.. container:: tn-app-variant tn-app-wrf

   .. code-block:: console

       $ ramble workspace info
       Workspace: software_wrf

       Experiments:
         Application: wrf
           Workload: {app_workload}
             Experiment 1: wrf.CONUS_12km.tile_1_1ranks-4.2
             Experiment 2: wrf.CONUS_12km.tile_1_1ranks-3.9.1.1
             Experiment 3: wrf.CONUS_12km.tile_1_2ranks-4.2
             Experiment 4: wrf.CONUS_12km.tile_1_2ranks-3.9.1.1
             Experiment 5: wrf.CONUS_12km.tile_2_1ranks-4.2
             Experiment 6: wrf.CONUS_12km.tile_2_1ranks-3.9.1.1
             Experiment 7: wrf.CONUS_12km.tile_2_2ranks-4.2
             Experiment 8: wrf.CONUS_12km.tile_2_2ranks-3.9.1.1
             Experiment 9: wrf.CONUS_2p5km.tile_1_1ranks-4.2
             Experiment 10: wrf.CONUS_2p5km.tile_1_1ranks-3.9.1.1
             Experiment 11: wrf.CONUS_2p5km.tile_1_2ranks-4.2
             Experiment 12: wrf.CONUS_2p5km.tile_1_2ranks-3.9.1.1
             Experiment 13: wrf.CONUS_2p5km.tile_2_1ranks-4.2
             Experiment 14: wrf.CONUS_2p5km.tile_2_1ranks-3.9.1.1
             Experiment 15: wrf.CONUS_2p5km.tile_2_2ranks-4.2
             Experiment 16: wrf.CONUS_2p5km.tile_2_2ranks-3.9.1.1

.. container:: tn-app-variant tn-app-gromacs

   .. code-block:: console

       $ ramble workspace info
       Workspace: software_gromacs

       Experiments:
         Application: gromacs
           Workload: {app_workload}
             Experiment 1: gromacs.water_bare.pme_1ranks-2025.3
             Experiment 2: gromacs.water_bare.pme_1ranks-2025.4
             Experiment 3: gromacs.water_bare.pme_2ranks-2025.3
             Experiment 4: gromacs.water_bare.pme_2ranks-2025.4
             Experiment 5: gromacs.water_bare.rf_1ranks-2025.3
             Experiment 6: gromacs.water_bare.rf_1ranks-2025.4
             Experiment 7: gromacs.water_bare.rf_2ranks-2025.3
             Experiment 8: gromacs.water_bare.rf_2ranks-2025.4
             Experiment 9: gromacs.water_gmx50.pme_1ranks-2025.3
             Experiment 10: gromacs.water_gmx50.pme_1ranks-2025.4
             Experiment 11: gromacs.water_gmx50.pme_2ranks-2025.3
             Experiment 12: gromacs.water_gmx50.pme_2ranks-2025.4
             Experiment 13: gromacs.water_gmx50.rf_1ranks-2025.3
             Experiment 14: gromacs.water_gmx50.rf_1ranks-2025.4
             Experiment 15: gromacs.water_gmx50.rf_2ranks-2025.3
             Experiment 16: gromacs.water_gmx50.rf_2ranks-2025.4

.. container:: tn-app-variant tn-app-hpl

   .. code-block:: console

       $ ramble workspace info
       Workspace: software_hpl

       Experiments:
         Application: hpl
           Workload: {app_workload}
             Experiment 1: hpl.calculator.pfact_0_1ranks-2.3
             Experiment 2: hpl.calculator.pfact_0_1ranks-2.2
             Experiment 3: hpl.calculator.pfact_0_2ranks-2.3
             Experiment 4: hpl.calculator.pfact_0_2ranks-2.2
             Experiment 5: hpl.calculator.pfact_1_1ranks-2.3
             Experiment 6: hpl.calculator.pfact_1_1ranks-2.2
             Experiment 7: hpl.calculator.pfact_1_2ranks-2.3
             Experiment 8: hpl.calculator.pfact_1_2ranks-2.2
             Experiment 9: hpl.standard.pfact_0_1ranks-2.3
             Experiment 10: hpl.standard.pfact_0_1ranks-2.2
             Experiment 11: hpl.standard.pfact_0_2ranks-2.3
             Experiment 12: hpl.standard.pfact_0_2ranks-2.2
             Experiment 13: hpl.standard.pfact_1_1ranks-2.3
             Experiment 14: hpl.standard.pfact_1_1ranks-2.2
             Experiment 15: hpl.standard.pfact_1_2ranks-2.3
             Experiment 16: hpl.standard.pfact_1_2ranks-2.2

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

.. container:: tn-full-run-only

   .. note::
      By default, the experiments in this tutorial use `Spack <https://spack.io/>`_
      (configured via ``package_manager: spack``) to build and install the required
      software stack. ``spack`` can either be installed in your ``PATH``, or Ramble
      will automatically bootstrap it for you.

   .. note::
      When not running in dry-run mode, both setup and execution can take a very
      long time:

      * ``ramble workspace setup`` will concretize and build **multiple software
        environments** (including multiple application versions and compilers) from
        source if they are not already installed on your system, and download input
        datasets for multiple workloads.
      * ``ramble on`` executes all 16 experiments in the matrix across both
        software stacks and workloads (including larger workloads like
        ``CONUS_2p5km`` and ``water_gmx50``).

      You can optionally enable **Dry-Run Mode** at the top of this tutorial or pass
      the ``--dry-run`` flag to setup (``ramble workspace setup --dry-run``) to quickly
      generate and inspect the experiment directories without building software or
      running the experiments.

   To set up, run, and analyze the experiments:

   .. code-block:: console

       $ ramble workspace setup
       $ ramble on
       $ ramble workspace analyze

   After analysis, ``results.latest.txt`` in the workspace root will compare the figures
   of merit across the different software environments and compilers.

.. container:: tn-dry-run-only

   With **Dry-Run Mode** enabled, set up the workspace using ``--dry-run``:

   .. code-block:: console

       $ ramble workspace setup --dry-run

   Because we are running in dry-run mode, we do **not** execute ``ramble on`` or
   ``ramble workspace analyze``. Instead, explore the generated ``software/`` and
   ``experiments/`` directories in the workspace to see how Ramble generated separate
   Spack environment configurations (``spack.yaml``) and ``execute_experiment`` scripts
   for each software stack:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/software_wrf/software/
          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/software_wrf/experiments/wrf/CONUS_12km/

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/software_gromacs/software/
          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/software_gromacs/experiments/gromacs/water_bare/

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/software_hpl/software/
          $ ls -la $RAMBLE_ROOT/var/ramble/workspaces/software_hpl/experiments/hpl/calculator/

   **Example Output (Full Run):**

   In a full run where ``ramble on`` and ``ramble workspace analyze`` are executed,
   Ramble generates a ``results.latest.txt`` summary comparing the application's
   figures of merit across each software environment in the experiment matrix.


Cleaning the Workspace
----------------------

.. container:: tn-workspace-cleanup

   Once you have completed this tutorial, deactivate and optionally remove your workspace:

   .. code-block:: console

       $ ramble workspace deactivate

   To completely delete the workspace directory:

   .. container:: tn-app-variant tn-app-wrf

      .. code-block:: console

          $ ramble workspace remove software_wrf

   .. container:: tn-app-variant tn-app-gromacs

      .. code-block:: console

          $ ramble workspace remove software_gromacs

   .. container:: tn-app-variant tn-app-hpl

      .. code-block:: console

          $ ramble workspace remove software_hpl


