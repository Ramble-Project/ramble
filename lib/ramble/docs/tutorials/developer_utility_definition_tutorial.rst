.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _utility-definition-tutorial:

===========================
Utility Definition Tutorial
===========================

This tutorial will guide you through creating a simple utility definition in Ramble. We will create a mock utility called ``my-tool`` that provides an executable and modifies the environment.

Installation
============

To install Ramble, see the :doc:`../getting_started` guide.

.. note::
   This tutorial does not require a package manager to be installed or configured.

.. include:: shared/repository_create.rst

Step 1: Setting up the file structure
=====================================

First, we need to create a directory for our utility within the ``tutorial-repo`` repository we created above.

Navigate to the utilities directory:

.. code-block:: console

    $ mkdir -p tutorial-repo/utilities/my-tool
    $ cd tutorial-repo/utilities/my-tool

Create a file named ``utility.py`` using your editor of choice.

Step 2: Defining the Class
==========================

Open ``utility.py`` and start by importing the necessary base classes and language directives.

.. code-block:: python

    from ramble.utility import UtilityBase
    from ramble.language.utility_language import *

    class MyTool(UtilityBase):
        """MyTool is a mock utility for this tutorial."""

        name = "my-tool"
        maintainers("your_username")

Step 3: Defining Variables and Bootstrapping
============================================

We want our utility to be able to be downloaded and installed by Ramble if the user doesn't already have it.

.. code-block:: python

        bootstrappable(True)

Next, we define a variable to hold the path to where the utility is installed. We use ``scoped=True`` so that the variable name is automatically namespaced to ``{utility::my-tool::path}``.

.. code-block:: python

        variable(
            name="path",
            default="system",
            description="Path to MyTool",
            scoped=True,
        )

Step 4: Providing Executables
=============================

Let's tell Ramble that this utility provides the ``my_tool_bin`` executable, and how Ramble can check the system to see if a valid version is already installed.

.. code-block:: python

        provides_executable(
            "my_tool_bin",
            version_cmd="my_tool_bin --version",
            version_regex=r"MyTool Version (\d+\.\d+\.\d+)"
        )

If a user requests this utility, Ramble will run ``my_tool_bin --version``. If the output matches the regex, Ramble can check the version against any ``min_version`` or ``max_version`` constraints requested by other objects.

Step 5: Modifying the Environment
=================================

Finally, we need to ensure that the experiments can actually use ``my_tool_bin``. We do this by prepending the utility's ``bin`` directory to the ``PATH`` environment variable.

.. code-block:: python

        env_prepend("PATH", "{utility::my-tool::path}/bin")

Step 6: Applying Utilities in Other Objects
===========================================

Now that we have defined a utility, other objects (like applications or modifiers) can apply it. To do this, the object definition uses the ``requires_utility`` directive.

For example, an application definition could apply our new utility like this:

.. code-block:: python

    from ramble.appkit import *

    class MyApplication(ExecutableApplication):
        name = "my-application"

        requires_utility("my-tool", min_version="2.0.0", max_version="3.0.0")

        executable(
            "run",
            "my_tool_bin run {arguments}",
            use_mpi=False,
        )

When an experiment uses this application, the variables and environment modifications defined in ``MyTool`` will be applied to the experiment, and Ramble will ensure the utility is either found on the system or bootstrapped.

Putting it all together
=======================

Your complete ``utility.py`` should look like this:

.. code-block:: python

    from ramble.utility import UtilityBase
    from ramble.language.utility_language import *

    class MyTool(UtilityBase):
        """MyTool is a mock utility for this tutorial."""

        name = "my-tool"
        maintainers("your_username")

        bootstrappable(True)

        variable(
            name="path",
            default="system",
            description="Path to MyTool",
            scoped=True,
        )

        provides_executable(
            "my_tool_bin",
            version_cmd="my_tool_bin --version",
            version_regex=r"MyTool Version (\d+\.\d+\.\d+)"
        )

        env_prepend("PATH", "{utility::my-tool::path}/bin")

You've successfully created your first utility definition! You can now reference ``my-tool`` in your workspace configuration under the ``utilities:`` section.

Cleanup
=======

.. container:: tn-repo-cleanup

   You are also free to delete the ``tutorial-repo`` repository, but make sure you
   unregister it from your list of repositories using the ``ramble repo rm``
   command:

   .. code-block:: console

     $ ramble repo rm tutorial-repo
     $ rm -rf tutorial-repo

