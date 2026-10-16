.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _ramble_basics_tutorial:

=====================================================
Ramble Basics: Discovering Applications and Objects
=====================================================

**Learning Objectives**

By the end of this tutorial, you will understand how to:

* Navigate the Ramble command-line interface (CLI) and built-in help system
* Understand Ramble's core object types
* Search and filter available objects using ``ramble list``
* Explore object metadata, tags, and maintainers using ``ramble attributes``
* Inspect detailed information about applications, workloads, variables, and modifiers using ``ramble info``
* View detailed configuration sections using ``ramble config``

Introduction
============

Before configuring and running experiments in a workspace, it is helpful to understand how to explore what Ramble provides out of the box. Ramble includes a rich set of built-in object definitions, along with front-end CLI commands designed to help you discover and inspect them.

.. note::
   This tutorial assumes you have followed the :doc:`Getting Started
   <../getting_started>` guide and have ``ramble`` available in your ``PATH``.

Getting Help from the CLI
=========================

Ramble is primarily controlled through the ``ramble`` command. Whenever you want to see available commands or learn about command-specific flags, you can use Ramble's built-in help system.

To view the most common commands and global flags:

.. code-block:: console

    $ ramble --help

To see the complete list of all Ramble commands grouped by category (including developer, configuration, and workspace commands):

.. code-block:: console

    $ ramble help --all

Any command or subcommand accepts ``--help`` (or ``-h``) to display detailed usage information. For example, to explore the options for ``ramble list`` or ``ramble workspace``:

.. code-block:: console

    $ ramble list --help
    $ ramble workspace --help

Core Object Types in Ramble
===========================

Ramble is built around modular, reusable object definitions stored in repositories. The four primary object types you will interact with when designing experiments are:

* **Applications** (``applications``): Define the building blocks for experiments. This includes workloads, input files, executables, common workload variables, figures of merit, success criteria and software stack information.
* **Package Managers** (``package_managers``): Define interfaces to tools that build or load software stacks for experiments (such as ``spack``, ``eessi``, or ``pip``).
* **Workflow Managers** (``workflow_managers``): Define interfaces to job schedulers and execution environments (such as ``slurm``, ``gke``, or ``google-batch``).
* **Modifiers** (``modifiers``): Define reusable layers that can be applied to experiments to alter their behavior—such as wrapping executables in profilers (e.g., ``intel-aps``, ``nsys``), collecting system information (e.g., ``lscpu``), or injecting environment settings.
* **Platforms** (``platforms``): Define Attributes of a particular compute node within a system. This typically includes hardware focused attributes, such as the amount of memory per node, the number of cores on a node, or any accelerator configuration on the node.
* **Systems** (``systems``): Define attributes of an underlying cluster. This includes setting default values for the ``package_manager`` or ``workflow_manager``, applying common ``modifiers``, defining the allowed ``platforms``, and registering common software definitions. Think of these as definitions of the whole cluster.

By default, Ramble's query commands (``ramble list``, ``ramble attributes``, and ``ramble info``) operate on ``applications``, but all of them accept a ``--type`` flag (or object-type flag) so you can inspect any object type in the exact same way.

Listing and Searching Objects (``ramble list``)
===============================================

Listing Applications
--------------------

To see all applications currently available in your configured Ramble repositories, run:

.. code-block:: console

    $ ramble list

By default, ``ramble list`` prints every available application. You can narrow the results by providing one or more case-insensitive filter arguments.

Substring and Glob Filtering
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Passing a plain word searches for any application whose name contains that substring. For example, to list all applications containing the letter ``h``:

.. code-block:: console

    $ ramble list h

which produces:

.. literalinclude:: ../_generated/snippets/ramble_basics_hostname_list_h.out
   :language: console

You can also use shell glob characters such as ``*`` and ``?`` (wrapped in quotes so your shell does not expand them before passing them to Ramble). For example, to list only applications whose names **start** with ``h``:

.. code-block:: console

    $ ramble list "h*"

which produces:

.. literalinclude:: ../_generated/snippets/ramble_basics_hostname_list_hstar.out
   :language: console

Searching Descriptions
^^^^^^^^^^^^^^^^^^^^^^

If you know the domain or functionality you are looking for rather than the exact application name, add the ``-d`` (``--search-description``) flag to search both application names and docstrings/descriptions:

.. code-block:: console

    $ ramble list -d "molecular dynamics"

Filtering by Tags
^^^^^^^^^^^^^^^^^

Every object in Ramble can be annotated with descriptive tags (information on how to see what tags are available will be provided later in this tutorial). You can filter ``ramble list`` by tag using ``-t`` (``--tags``):

.. code-block:: console

    $ ramble list -t test-app

which outputs:

.. literalinclude:: ../_generated/snippets/ramble_basics_hostname_list_tag.out
   :language: console

Listing Other Object Types
--------------------------

To list objects other than applications, pass ``--type <object_type>`` to ``ramble list``.

For example, to list all available **modifiers**:

.. code-block:: console

    $ ramble list --type modifiers

which produces:

.. literalinclude:: ../_generated/snippets/ramble_basics_hostname_list_modifiers.out
   :language: console

To list all available **package managers**:

.. code-block:: console

    $ ramble list --type package_managers

.. literalinclude:: ../_generated/snippets/ramble_basics_hostname_list_package_managers.out
   :language: console

And to list all available **workflow managers**:

.. code-block:: console

    $ ramble list --type workflow_managers

.. literalinclude:: ../_generated/snippets/ramble_basics_hostname_list_workflow_managers.out
   :language: console

Exploring Object Attributes (``ramble attributes``)
===================================================

How do you know which tags or maintainers exist across Ramble's repositories? The ``ramble attributes`` command lets you inspect object metadata across one or all objects.

Viewing Tags by Application
---------------------------

To see the tags defined for every application:

.. code-block:: console

    $ ramble attributes --all --tags

Grouping Applications by Tag or Maintainer
------------------------------------------

If you instead want to see a mapping from each tag to the list of applications that carry that tag, add ``--by-attribute``:

.. code-block:: console

    $ ramble attributes --all --tags --by-attribute

You can also query maintainers instead of tags using ``--maintainers`` (the default attribute), or query attributes for other object types such as ``--modifiers``:

.. code-block:: console

    $ ramble attributes --all --modifiers --tags --by-attribute

Inspecting Object Details (``ramble info``)
===========================================

Once you have identified an application or modifier of interest using ``ramble list``, use ``ramble info`` to inspect its structure, workloads, tunable variables, software specs, and figures of merit.

Viewing an Application Summary
------------------------------

Let's inspect the ``hostname`` application:

.. code-block:: console

    $ ramble info hostname

This command prints a comprehensive overview of the ``hostname`` application:

.. literalinclude:: ../_generated/snippets/ramble_basics_hostname_info.out
   :language: console

From this output, you can see:

* **Description**: What the application does.
* **Tags**: Metadata tags associated with the application (``test-app``).
* **Workloads**: Named execution scenarios supported by the application (``local``, ``parallel``, ``serial``), along with their associated executables and inputs.
* **Figures of Merit**: Performance or validation metrics that Ramble automatically extracts when analyzing experiment output (``possible hostname``).
* **Success Criteria**: Conditions Ramble checks to determine whether an experiment succeeded (``wrote_anything``).
* **Builtin Executables**: Internal steps injected into the execution pipeline (``builtin::env_vars``). These are defined in either the application definition, or one of it's ancestors.

Viewing Attribute Overviews and Filtering Attributes
----------------------------------------------------

Complex applications (such as ``gromacs`` or ``wrf``) define many workloads, variables, and software specs. To see a quick summary of which attribute categories are populated on an object without printing all of their contents, use ``-o`` (``--overview``):

.. code-block:: console

    $ ramble info hostname -o

.. literalinclude:: ../_generated/snippets/ramble_basics_hostname_info_overview.out
   :language: console

You can then inspect one or more specific attributes using ``--attrs`` (or ``--attributes``) and request verbose details (such as workload variables and defaults) using ``-v`` (``--verbose``):

.. code-block:: console

    $ ramble info hostname --attrs workloads -v

which produces:

.. literalinclude:: ../_generated/snippets/ramble_basics_hostname_filtered_info.out
   :language: console

Notice how adding ``-v`` reveals the **Variables** defined on each workload (such as ``input_arguments``, ``n_ranks``, and ``n_threads``), along with their default values and descriptions.

You can also filter the items shown within an attribute section using ``-p`` (``--pattern``) with a glob pattern. For example, to view only workload matching ``water*`` on ``gromacs``:

.. code-block:: console

    $ ramble info gromacs --attrs workloads -p "water*"
    or;
    $ ramble info gromacs --attrs workloads -p "water*" -v

Inspecting Modifiers and Other Objects
--------------------------------------

Just like ``ramble list``, ``ramble info`` can inspect any object type using ``--type <object_type>`` or a fully qualified namespace spec (such as ``builtin.mod.<name>``).

For example, to inspect the ``lscpu`` modifier:

.. code-block:: console

    $ ramble info --type modifiers lscpu

or equivalently:

.. code-block:: console

    $ ramble info builtin.mod.lscpu

which produces:

.. literalinclude:: ../_generated/snippets/ramble_basics_hostname_info_modifier_lscpu.out
   :language: console

Inspecting Configuration Sections
=================================

Finally, it can be useful to know how to inspect the configuration sections in Ramble.

Ramble uses hierarchical configuration scopes (``defaults``, ``system``, ``site``, ``user``, and an active ``workspace``). Each of these scopes can contain definitions for a number of configuration sections. To list all configuration sections supported by Ramble:

.. code-block:: console

    $ ramble config list

.. literalinclude:: ../_generated/snippets/ramble_basics_hostname_config_list.out
   :language: console

To inspect the current values in a section (such as ``config``) or see which configuration file each setting came from (``blame``):

.. code-block:: console

    $ ramble config get config
    $ ramble config blame config

Next Steps
==========

Now that you know how to discover applications, inspect workloads and variables with ``ramble info``, and explore Ramble's built-in objects, you are ready to create your first workspace and run a :ref:`"Hello World" experiment <hello_world_tutorial>`.
