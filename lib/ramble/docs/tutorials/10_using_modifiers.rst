.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _modifiers_tutorial:

=============
10) Modifiers
=============

In this tutorial, you will learn how to discover modifiers, learn about their
functionality, and apply them to experiments for
`WRF <https://www.mmm.ucar.edu/models/wrf>`_, a free and open-source
application for atmospheric research and operational forecasting applications.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

**NOTE:** In this tutorial, you will encounter expected errors when copying and
pasting the commands. This is to help show situations you might run into when
trying to use Ramble on your own, and illustrate how you might fix them.

Create a Workspace
------------------

To begin with, you need a workspace to configure the experiments. This can be
created with the following command:

.. code-block:: console

    $ ramble workspace create modifiers_wrf


Activate the Workspace
----------------------

Several of Ramble's commands require an activated workspace to function
properly. Activate the newly created workspace using the following command:
(NOTE: you only need to run this if you do not currently have the workspace
active).

.. code-block:: console

    $ ramble workspace activate modifiers_wrf

.. include:: shared/wrf_scaling_workspace.rst

Discovering Modifiers
---------------------

In Ramble, a ``modifier`` is an abstract object that can be applied to a large
set of experiments. Modifiers are intended to encasulate reusable patterns that
perform a specific extension of a workload focused experiment. Some examples of
useful modifiers include:

 * Collecting system level information
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

This shows there are four modifiers in this installation of Ramble. Two very
general modifiers in this list are ``lscpu`` and ``intel-aps``. Modifiers are
allowed to behave in different ways. Their functionality should be documented
at a high-level through the ``ramble info --type modifiers`` command. To get information
about the ``lscpu`` modifier, execute:

.. code-block:: console

    $ ramble info --type modifiers lscpu
    or;
    $ ramble info builtin.mod.lscpu

This modifier adds the execution of ``lscpu`` to each experiment in a workspace
(to capture additional platform level details, such as the CPU model), and
defines additional figures of merit related to the output to ``lscpu``.

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


And add the following lines, at the workspace scope:

.. code-block:: YAML

    modifiers:
    - name: lscpu

The resulting configuration file should look like the following.


.. literalinclude:: ../../../../examples/tutorial_10_lscpu_config.yaml
   :language: YAML

The ``modifiers`` dictionary can be defined at any scope ``variables`` can be
defined at. Defined ``modifiers`` are inherited by all experiments at lower
scope levels.

.. include:: shared/wrf_execute.rst

In addition to these WRF defined figures of merit, you should also see
``lscpu`` defined figures of merit. These might include the following:

 * CPU family
 * Model
 * Core(s) per socket
 * Socket(s)

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
additional difference relateive to ``lscpu`` is that the ``Software Specs:``
section at the bottom of the output now has information in it. This is because
Intel APS needs to be installed to be able to run applications under it.

To apply the ``intel-aps`` modifier, edit the workspace configuration file
using:

.. code-block:: console

    $ ramble workspace edit

Within this file, add:

.. code-block:: YAML

    - name: intel-aps

To the list of modifiers. This will cause both ``lscpu`` and ``intel-aps`` to
be applied to all of the experiments. The resulting configuration file should
look like the following:

.. literalinclude:: ../../../../examples/tutorial_10_aps_error_config.yaml
   :language: YAML

To test some aspects of the workspace configuration before spending time
performing a real setup, use:

.. code-block:: console

    $ ramble workspace setup --dry-run

This will perform many of the validation checks, and generate the experiment
directories as a normal setup would, but can execute much faster. Before this
command proceeds too far, you should see the following error message:

.. code-block:: console

    ==> Error: Software spec intel-oneapi-vtune is not defined in environment wrf@4.2, but is required by the intel-aps modifier definition

As mentioned earlier, this is because the ``intel-aps`` modifier requires
additional software to function properly. In this case, it requires the
``intel-oneapi-vtune`` package. However, this package is not defined, nor is it
in your environment definition.

To remedy this issue, again edit your workspace configuration file using:

.. code-block:: console

    $ ramble workspace edit

And write a Spack package definition for ``intel-oneapi-vtune``. After the
package is defined, add the package to the ``wrf@4.2`` environment. The resulting
configuration file should look like the following:

.. literalinclude:: ../../../../examples/tutorial_10_aps_final_config.yaml
   :language: YAML

.. include:: shared/wrf_execute.rst

In addition to these WRF defined figures of merit, you should also see
``lscpu``, and ``intel-aps`` defined figures of merit. These might include the
following:

 * CPU family - From ``lscpu``
 * Model - From ``lscpu``
 * Core(s) per socket - From ``lscpu``
 * Socket(s) - From ``lscpu``
 * MPI Time - From ``intel-aps``
 * Disk I/O Time - From ``intel-aps``

Clean the Workspace
-------------------

Once you are finished with the tutorial content, make sure you deactivate your workspace:

.. code-block:: console

    $ ramble workspace deactivate

Additionally, you can remove the workspace and all of its content with:

.. code-block:: console

    $ ramble workspace remove modifiers_wrf
