.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _utility-dev-guide:

=======================
Utility Developer Guide
=======================

This guide details how to create and manage utility definitions in Ramble.

What is a Utility?
==================

Utilities in Ramble are external dependencies or tools that are required by experiments or applications to function correctly. This could include package managers (like Spack), system monitoring tools, or job execution frameworks.

Utilities are defined as Python classes that inherit from `UtilityBase`.

Creating a New Utility
======================

To create a new utility, you must define a class that inherits from `UtilityBase`. This definition must be placed in a file named `utility.py` within a directory named after your utility, inside a valid repository's `utilities/` folder.

For example, a utility named `my_util` would be located at `var/ramble/repos/builtin/utilities/my_util/utility.py`.

Basic Structure
---------------

.. code-block:: python

    from ramble.utility import UtilityBase
    from ramble.language.utility_language import *

    class MyUtil(UtilityBase):
        """MyUtil provides system information capabilities."""

        name = "my_util"
        maintainers("your_username")

        bootstrappable(True)

        variable(
            name="path",
            default="system",
            description="Path to MyUtil",
            scoped=True,
        )

        provides_executable(
            "my_util_bin",
            version_cmd="my_util_bin --version",
            version_regex=r"my_util version (\d+\.\d+\.\d+)"
        )

        env_prepend("PATH", "{utility::my_util::path}/bin")

Utility Directives
==================

Utilities have access to a specific set of declarative directives to define their behavior.

``bootstrappable``
------------------

Indicates whether Ramble is capable of downloading and installing this utility if it is not found on the system.

.. code-block:: python

    bootstrappable(True)

``variable`` and Scoping
------------------------

Utilities can define variables just like applications. However, to prevent namespace collisions, utility variables are strongly encouraged to use `scoped=True`.

.. code-block:: python

    variable(
        name="path",
        default="system",
        description="Path to the utility",
        scoped=True,
    )

When `scoped=True` is used, Ramble automatically prefixes the variable name with the utility's namespace. In the example above, the `path` variable becomes `{utility::my_util::path}`. This allows other parts of Ramble, or other utilities, to reference this variable safely.

``provides_executable``
-----------------------

This directive declares an executable that the utility provides, and optionally, how Ramble should check the system to see if the utility is already installed and meets version requirements.

.. code-block:: python

    provides_executable(
        "cmake",
        version_cmd="cmake --version",
        version_regex=r"cmake version (\d+\.\d+\.\d+)"
    )

If an object requiring this utility provides a `min_version` or `max_version`, Ramble will verify the system's executable meets the constraints using this regex. If it does, Ramble will skip the bootstrapping phase and use the system's version.

``archive_exclude``
-------------------

Bootstrapped utilities are omitted from workspace archives and deployments by default unless ``--include-utilities`` is passed. When ``--include-utilities`` is used, ``archive_exclude`` specifies relative paths or glob patterns (relative to the bootstrapped utility's ``source`` directory, or its parent version directory when prefixed with ``../``) to skip so build stages, caches, or compiled binary trees do not bloat the archive or deployment.

.. code-block:: python

    archive_exclude("opt")
    archive_exclude("var/spack/stage")
    archive_exclude("var/spack/cache")

``requires_utility``
--------------------

Other objects (like Applications or Modifiers) can require a utility and optionally specify a minimum or maximum version using the ``requires_utility`` directive. You can also specify if the utility can be provided by the system with the ``allow_external`` boolean flag (defaults to ``True``).

.. code-block:: python

    requires_utility("cmake", min_version="3.20.0", max_version="3.30.0", allow_external=True)

Environment Modifications
=========================

Utilities often need to modify the environment (e.g., setting paths, exporting variables) for the experiments that use them. Ramble provides a unified set of directives to handle this. These modifications are automatically applied to both the Ramble runner's environment and the generated experiment bash scripts.

``env_source``
--------------

Sources a bash script.

.. code-block:: python

    env_source("{utility::my_util::path}/setup.sh")

``env_set``
-----------

Sets an environment variable to a specific value.

.. code-block:: python

    env_set("MY_UTIL_DIR", "{utility::my_util::path}")

``env_prepend`` and ``env_append``
----------------------------------

Prepends or appends a value to a colon-separated environment variable (like `PATH`).

.. code-block:: python

    env_prepend("PATH", "{utility::my_util::path}/bin")
    env_append("LD_LIBRARY_PATH", "{utility::my_util::path}/lib")

Lifecycle Hooks
===============

If a utility requires complex setup logic that cannot be captured declaratively, you can override lifecycle hooks provided by `UtilityBase`.

``install(self, workspace)``
----------------------------

Executed when Ramble bootstraps the utility. This is where you place the logic to compile or configure the utility after it has been downloaded.

``modify_bootstrap(self, workspace, app_inst)``
-----------------------------------------------

Executed after the utility has been installed. This allows the utility to modify its own installation (e.g., altering default configuration files). The `app_inst` argument is the application instance that triggered the bootstrap. You can retrieve scoped variables from `app_inst.variables`.
