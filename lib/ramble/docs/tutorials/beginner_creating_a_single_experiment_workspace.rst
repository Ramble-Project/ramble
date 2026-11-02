.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _running_an_experiment_tutorial:

======================================
Creating a Single Experiment Workspace
======================================

.. tutorial-header:: single_experiment

In this tutorial, you will set up and run a benchmark simulation using a real
scientific application.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content,
however this tutorial is fully stand-alone as far as steps you need to perform.

Application Information
-----------------------

.. tutorial-app-template::
   :wrf: link=`Weather Research and Forecasting (WRF) <https://www.mmm.ucar.edu/models/wrf>`_;desc=model, a next-generation mesoscale numerical weather prediction system;wl_desc=as it represents a standard continental United States forecast benchmark
   :gromacs: link=`GROMACS <https://www.gromacs.org/>`_;desc=application definition, a free and open-source application for molecular dynamics;wl_desc=as it is able to execute in a short amount of time
   :hpl: link=`High-Performance Linpack (HPL) <https://www.netlib.org/benchmark/hpl/>`_;desc=benchmark, a widely used benchmark measuring floating-point compute performance;wl_desc=which automatically determines problem dimensions and grid parameters based on system memory and node count

   This tutorial uses the {link} {desc}. We will begin with the ``{workload}``
   workload, {wl_desc}.

Using a previously installed ``ramble``, the following command can be used to
get information about this workload:

.. tutorial-snippet:: single_experiment info_workload_cmd.sh

.. tutorial-app-template::

   Under the workload marked by ``Workload: {workload}``, you should see output similar to:

   .. literalinclude:: /_generated/snippets/single_experiment_{app}_info_workload.out
      :language: console

.. container:: tn-app-variant tn-app-gromacs

   Here we see that this workload has a ``type`` variable (with possible values
   of ``pme`` and ``rf``) and a ``size`` variable with a variety of available sizes.

To determine a suggested software configuration, you can use:

.. tutorial-snippet:: single_experiment info_software_cmd.sh

With this command, you should see output similar to the following:

.. tutorial-snippet:: single_experiment info_software.out

This output does not represent the only possible configuration that works for
this application, it only presents a good starting point. When using Ramble,
these can be modified freely.

Configuring Experiments
-----------------------

You will use a Ramble workspace to manage these experiments.

Create and Activate a Workspace
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. tutorial-workspace-create:: basic
   :separate-activate:

Configure the Workspace
~~~~~~~~~~~~~~~~~~~~~~~

Within the workspace directory, Ramble creates a directory named ``configs``.
This directory contains configuration and template files:

* ``ramble.yaml``: Describes all aspects of the workspace, including software, experiments, and variables.
* ``execute_experiment.tpl``: A template shell script rendered to execute each experiment.

You can configure this experiment using the ``ramble workspace manage`` and ``ramble workspace concretize`` commands:

.. tutorial-snippet:: single_experiment commands.sh
   :alt-yaml: ramble.yaml

.. note::
   This workspace utilizes the ``spack`` package manager. As a result, it
   requires ``spack``. If ``spack`` is not installed and available in your
   ``PATH``, it will be bootstrapped for you. To see compilers already
   available to Spack, use ``spack compilers``.

The second file in the ``configs`` directory is the ``execute_experiment.tpl``
template file. It will be rendered into an execution script for each generated
experiment; for this tutorial, the default value will work.

Executing Experiments
---------------------

.. tutorial-execute:: basic
   :dry-run-cmds: ls -la $RAMBLE_ROOT/var/ramble/workspaces/basic_{app}/experiments/{app}/{workload}/single_rank; cat $RAMBLE_ROOT/var/ramble/workspaces/basic_{app}/experiments/{app}/{workload}/single_rank/execute_experiment
   :include-foms:

   For each setup run, logs are created under ``$workspace_root/logs`` (such as
   ``logs/setup.latest/<app>.<workload>.single_rank.out``). In addition to ``ramble on``,
   experiments can also be executed using the generated ``./all_experiments`` script in
   the root of the workspace.

Workspace Directory Structure
-----------------------------

After analyzing the workspace, you can examine its structure:

.. tutorial-app-template::

   .. code-block:: console

       $ ls $RAMBLE_ROOT/var/ramble/workspaces/basic_{app}

Within this directory, you should see the following directories:

* ``configs`` - Contains all configuration files for the workspace
* ``experiments`` - Contains experiment execution directories
* ``inputs`` - Contains input files needed for the experiments
* ``logs`` - Contains log files from any Ramble command acting on the workspace
* ``shared`` - Contains auxiliary files such as environment variable scripts
* ``software`` - Contains software environments for the experiments

Cleanup the Workspace
---------------------

.. tutorial-workspace-cleanup:: basic


