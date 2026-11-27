.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.


.. _utilities:

=========
Utilities
=========

Utilities in Ramble represent external dependencies or tools that experiments rely on to function correctly. This can range from software package managers like `spack`, to cluster execution tools like `pdsh`. 

Utilities differ from Ramble's internal `software` definitions in that they are often required *before* the primary software stack can even be installed or configured, or they provide fundamental system-level capabilities that aren't strictly part of the experiment's scientific payload.

---------------------
Configuring Utilities
---------------------

Utilities can be requested and configured within the `ramble.yaml` configuration file using the `utilities:` dictionary.

When a utility is specified, Ramble will attempt to bootstrap it (if configured to do so) or locate it on the system before setting up the experiment's environment.

.. code-block:: yaml

  ramble:
    utilities:
      spack:
        version: "0.22.0"

In this example, the `spack` utility is requested at version `0.22.0`. If Spack is not already available on the system matching this requirement, Ramble can fetch and bootstrap it automatically into the workspace's shared directory (`$workspace/shared/bootstrapped_utilities/spack/0.22.0/source`).

---------------------------
Utility Variables & Scoping
---------------------------

When a utility is active for an experiment, it often injects variables into the experiment's context. To prevent namespace collisions, utility variables can be strongly scoped using the `utility::` prefix, followed by the utility's name. This is accomplished by setting ``scoped=True`` when defining the variable in the utility class.

For instance, the installation path of the `spack` utility can be accessed via:

.. code-block:: text

  {utility::spack::path}

These variables can be used in your workspace configurations or application definitions just like any other standard Ramble variable.

---------------------------------
Bootstrapping vs System Utilities
---------------------------------

By default, Ramble attempts to use an existing installation of a utility if it meets the requirements (e.g., if a matching version of `spack` is already in your `PATH` and satisfies the minimum version constraints).

If a suitable version is not found, and the utility is marked as `bootstrappable(True)`, Ramble will download and set it up automatically.

You can globally disable the bootstrapping of all utilities by modifying your Ramble configuration:

.. code-block:: yaml

  config:
    bootstrap_utilities: False

If bootstrapping is disabled, and the required utility is not found on the system, Ramble will halt with an error indicating the missing dependency.

-------------------------------------
Archiving and Deploying Utilities
-------------------------------------

To avoid bloating archives and deployments with cloned utility repositories or compiled binaries (such as packages installed into a bootstrapped Spack's ``opt`` directory), ``$workspace/shared/bootstrapped_utilities`` is omitted by default during ``ramble workspace archive`` and ``ramble deployment push``.

To include bootstrapped utilities, pass ``--include-utilities``:

.. code-block:: console

  $ ramble workspace archive --include-utilities
  $ ramble deployment push --include-utilities

When ``--include-utilities`` is specified, any paths matching ``archive_exclude`` directives on the utility definition (such as ``opt``, build stages, and caches for ``spack``) are automatically skipped.
