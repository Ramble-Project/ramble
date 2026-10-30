.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _modifiers_tutorial:

=========
Modifiers
=========

.. tutorial-header:: modifiers

In this tutorial, you will learn how to discover modifiers, learn about their
functionality, and apply them to experiments.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

.. note::
   In this tutorial, you will encounter expected errors when copying and
   pasting the commands. This is to help show situations you might run into when
   trying to use Ramble on your own, and illustrate how you might fix them.

Create a Workspace
------------------

.. tutorial-workspace-create:: modifiers
   :separate-activate:

Configure Experiment Definitions
--------------------------------

To begin with, you need to configure the workspace. Within the ``ramble.yaml``
file, write the following contents, which represents a base scaling study
configuration:

.. tutorial-snippet:: modifiers base.yaml

Discovering Modifiers
---------------------

In Ramble, a ``modifier`` is an abstract object that can be applied to a large
set of experiments. Modifiers are intended to encapsulate reusable patterns that
perform a specific extension of a workload-focused experiment. Some examples of
useful modifiers include:

 * Collecting system-level information
 * Changing underlying system / library functionality
 * Injecting Performance Analysis Tools

To discover which modifiers are available, execute:

.. code-block:: console

    $ ramble list --type modifiers

Which might output the following:

.. code-block:: console

    ==> 33 modifiers
    amd-uprof          darshan             execution-date     hpctoolkit      intel-vtune  nccl-tcpxo      pre-post-capture  sys-stat   wait-for-bg-jobs
    apptainer          docker              exit-code          install-ramble  lscpu        nvidia-smi      pyxis-enroot      tunables
    collection-daemon  env-var-aggregator  gcp-cloud-logging  install-spack   nccl-env     perf            run-directory     tuned-adm
    conditional-psm3   ethtool             gcp-metadata       intel-aps       nccl-gib     pre-exec-print  status-markers    turbostat

This shows all of the modifiers in this installation of Ramble. Two very
general modifiers in this list are ``lscpu`` and ``intel-aps``. Modifiers are
allowed to behave in different ways. Their functionality should be documented
at a high level through the ``ramble info --type modifiers`` command. To get information
about the ``lscpu`` modifier, execute:

.. code-block:: console

    $ ramble info --type modifiers lscpu
    or;
    $ ramble info builtin.mod.lscpu

This modifier adds the execution of ``lscpu`` to each experiment in a workspace
(to capture additional platform-level details, such as the CPU model), and
defines additional figures of merit related to the output of ``lscpu``.

The output of this command lists all supported modes of operation for the
modifier, along with some of the behaviors each mode presents. A ``mode`` is a
grouping of behaviors that control what the modifier will do to the
experiments. Some modifiers only have a single mode of operation (as ``lscpu``
only has ``standard``), while others might contain more. Modes are provided to
allow users to easily control the behavior of the modifier.

Applying the ``lscpu`` Modifier
-------------------------------

In the minimal case, a modifier can be added to all experiments in a workspace
with two lines. In the general case, each modifier that is applied to
experiments must define the mode of operation it will use. In the case that a
modifier only has a single ``mode``, it will be automatically selected as the
default. Additionally, modifiers are allowed to define their own default modes
to simplify its usage within a workspace.

To apply the ``lscpu`` modifier to your experiments, edit the workspace
configuration file with:

.. code-block:: console

    $ ramble workspace edit

And add the following lines at the workspace scope:

.. code-block:: YAML

    modifiers:
    - name: lscpu

The resulting configuration file should look like the following:

.. tutorial-snippet:: modifiers lscpu.yaml

The ``modifiers`` dictionary can be defined at any scope ``variables`` can be
defined at. Defined ``modifiers`` are inherited by all experiments at lower
scope levels.

Execute Experiments
~~~~~~~~~~~~~~~~~~~

.. tutorial-execute:: modifiers
   :dry-run-cmds: cat $RAMBLE_ROOT/var/ramble/workspaces/modifiers_{app}/experiments/{app}/{workload}/single_rank/execute_experiment
   :results-text: In addition to the application-defined figures of merit, ``results.latest.txt`` includes the ``lscpu`` figures of merit:

* CPU family
* Model
* Core(s) per socket
* Socket(s)

.. container:: tn-full-run-only

   You may also examine the ``execute_experiment`` script in each of the
   experiment run directories to see what changed after applying the ``lscpu``
   modifier.

Advanced Modifiers
------------------

Some modifiers have additional functionality, which can include requiring
specific software packages to be present. An example of this is the
``intel-aps`` modifier, which applies Intel's
`Application Performance Snapshot <https://www.intel.com/content/www/us/en/docs/vtune-profiler/user-guide-application-snapshot-linux/2023-0/introducing-application-performance-snapshot.html>`_
to a workspace's experiments.

To get information about the ``intel-aps`` modifier, execute:

.. code-block:: console

    $ ramble info --type modifiers intel-aps
    or;
    $ ramble info builtin.mod.intel-aps

In the output from this command, you should see a ``mode`` named ``mpi``. One
additional difference relative to ``lscpu`` is that the ``Software Specs:``
section at the bottom of the output now has information in it. This is because
Intel APS needs to be installed to be able to run applications under it.

To apply the ``intel-aps`` modifier, edit the workspace configuration file
using:

.. code-block:: console

    $ ramble workspace edit

Within this file, add:

.. code-block:: YAML

    - name: intel-aps

to the list of modifiers. This will cause both ``lscpu`` and ``intel-aps`` to
be applied to all of the experiments. The resulting configuration file should
look like the following:

.. tutorial-snippet:: modifiers aps_error.yaml

To test some aspects of the workspace configuration before spending time
performing a real setup, use:

.. code-block:: console

    $ ramble workspace setup --dry-run

This will perform many of the validation checks, and generate the experiment
directories as a normal setup would, but can execute much faster. Before this
command proceeds too far, you should see an error message similar to:

.. tutorial-app-template::

   .. code-block:: console

       ==> Error: Software spec intel-oneapi-vtune is not defined in environment {app_spec}, but is required by the intel-aps modifier definition

As mentioned earlier, this is because the ``intel-aps`` modifier requires
additional software to function properly. In this case, it requires the
``intel-oneapi-vtune`` package. However, this package is not defined, nor is it
in your environment definition.

To remedy this issue, again edit your workspace configuration file using:

.. code-block:: console

    $ ramble workspace edit

And write a Spack package definition for ``intel-oneapi-vtune``. After the
package is defined, add the package to the application environment. The resulting
configuration file should look like the following:

.. tutorial-snippet:: modifiers aps_final.yaml

Execute Experiments
~~~~~~~~~~~~~~~~~~~

.. tutorial-execute:: modifiers
   :timing-note: Because adding the ``intel-aps`` modifier introduced ``intel-oneapi-vtune`` into the workspace's software environment, running ``ramble workspace setup`` without ``--dry-run`` will install ``intel-oneapi-vtune`` if it is not already present on your system, and ``ramble on`` will re-execute the experiments under APS profiling.
   :dry-run-cmds: cat $RAMBLE_ROOT/var/ramble/workspaces/modifiers_{app}/experiments/{app}/{workload}/single_rank/execute_experiment
   :results-text: In addition to the application-defined figures of merit, ``results.latest.txt`` includes both ``lscpu`` and ``intel-aps`` figures of merit:

* CPU family - From ``lscpu``
* Model - From ``lscpu``
* Core(s) per socket - From ``lscpu``
* Socket(s) - From ``lscpu``
* MPI Time - From ``intel-aps``
* Disk I/O Time - From ``intel-aps``


Clean the Workspace
-------------------

.. tutorial-workspace-cleanup:: modifiers

