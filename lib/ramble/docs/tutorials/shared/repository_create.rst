.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

Ramble Repositories
===================

.. container:: tn-repo-create

   Before writing our definitions, we will create a repository to house
   the application definition. Repositories in Ramble can house any object type,
   and are not limited to only those in this tutorial.

   The ``ramble repo`` command is used to manage object repositories in Ramble. To
   create a new repository, execute the following:

   .. code-block:: console

       $ ramble repo create tutorial-repo

   This will create a new directory named ``tutorial-repo`` in your current
   directory. Inside, directories will exist for each of the object types. These
   will include things like ``applications`` and ``package_managers``. Resulting
   object paths in this repo would look like:

   .. code-block:: console

       tutorial-repo/applications/hostname/application.py

   You can also create a repository without object subdirectories using:

   .. code-block:: console

       $ ramble repo create tutorial-repo -d ""

   In this case, the resulting structure looks like:

   .. code-block:: console

       tutorial-repo/hostname/application.py

   This latter layout allows objects with the same name but different types to
   coexist in the same directory. For example, if there was a package manager
   named hostname, it would exist in the following path:

   .. code-block:: console

       tutorial-repo/hostname/package_manager.py

   The remaining commands in this tutorial will assume your repository layout
   matches the first example, but you can feel free to use either layout. Just map
   any paths to the correct layout.

   The actual object files within the repository are named based on the object
   they represent. Below is a mapping of some object types to file names:

    * Application - ``application.py``
    * Base Application - ``base_application.py``
    * Modifier - ``modifier.py``
    * Package Manager - ``package_manager.py``
    * Workflow Manager - ``workflow_manager.py``
    * System - ``system.py``
    * Platform - ``platform.py``

   As listed with the ``application.py`` file, each object also has a
   corresponding ``base`` version, that is mostly used to help inheritance into
   several concrete objects.

   Once your repository is created, you can register it with Ramble by issuing the
   following command:

   .. code-block:: console

       $ ramble repo add tutorial-repo

   .. note::
      Ramble comes with a default ``builtin`` repository. Adding new
      repositories gives them a higher precedence to other existing repositories.
      Ramble uses this precedence ordering to decide which object definition is used
      when multiple exist with the same name. Each repository has a namespace, and
      these namespaces can be used to refer to specific instances of each object
      definition.

Referencing Objects with Namespaces
-----------------------------------

When multiple repositories contain objects with the same name, or when you want
to be explicit about which repository an object comes from, you can use fully-qualified
namespaced specs.

Namespaced specs take the form:

* ``<namespace>.<object_name>`` (e.g., ``tutorial-repo.hostname``, ``builtin.wrf``)
* ``<namespace>.<type_abbrev>.<object_name>`` (e.g., ``tutorial-repo.app.hostname``, ``builtin.mod.my_modifier``)
* ``<namespace>.<type_abbrev>.<object_name>@<version>`` (e.g., ``builtin.app.wrf@4.2``, ``builtin.app.wrf@{version}``)

Common object type abbreviations include:

* ``app`` or ``application`` for applications
* ``mod`` or ``modifier`` for modifiers
* ``pkg_man`` or ``package_manager`` for package managers
* ``wm`` or ``workflow_manager`` for workflow managers
* ``sys`` or ``system`` for systems
* ``plat`` or ``platform`` for platforms

Base objects can be referenced with the ``base_<type_abbrev>`` prefix.

These namespaced specs can be used in CLI commands (e.g., ``ramble info <spec>``,
``ramble edit <spec>``, ``ramble create <spec>``) and in workspace configuration files
(``ramble.yaml``) under the ``applications:`` and ``environments:`` sections.
