.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _package-manager-dev-guide:

===========================================
Package Manager Definition Developers Guide
===========================================

Package manager definitions files contain objects which encapsulate the
behaviors of specific package managers. Application definition files are
written in an abstract way that is not tied to a specific package manager, and
layering a package manager on top of the experiment allows Ramble to manage the
software stack for its generated experiments. By default, Ramble does not
impose a specific package manager on the experiments it generates, allowing
experiments to reference manually created software stacks.

This guide will provide general steps for creating a new package manager
definition file.

**NOTE:** Package managers are considered a more advanced feature of Ramble.
Writing a new pcakage manager definition file in Ramble largely follows the
same workflow as writing an application definition file, although the intent
and behavior are different. It is recommended that you review
:ref:`application-dev-guide` before writing a modifier.

-----------
Preparation
-----------

Before writing a package manager definition file, it is helpful to understand
how to manually accomplish the following steps with the package manager:

#. Installation of new software
#. Environment creation (preferred, but not strictly required depending on the
   package manager)
#. Installed package path extraction
#. Provenance extraction for installed packages
#. (Optional) Package mirroring
#. (Optional) Package caching / repository building

Ramble and its documentation cannot help with these steps. It is best to
research how to perform these steps (if they are possible) with the package
manager you are working with.


-----------------------------------
Package Manager Definition Creation
-----------------------------------

Package manager definition files are stored within object repositories. These
repositories generally store package managers within a directory named
``package_managers``. Individual repositories can control this through their
own config file (``repo.yaml`` or ``package_manager_repo.yaml``).

Within the repository, each package manager definition file is a python module
that is stored within a directory named for the package manager. As an example,
Ramble comes with a repository named ``builtin``. This repository contains
several standard package manager definitions that are provided to the
community. One of the package manager definition files provided is 
`spack <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack/package_manager.py>`_
which inherits from
`spack-lightweight <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/package_managers/spack-lightweight/package_manager.py>`_.

The ``spack`` package manager definition file is named ``package_manager.py``
and is stored within a directory named ``spack``. Witihn the
``package_manager.py`` file, a python class is defined with a similar name to
the package manager directory.  Ramble's package manager definition naming
syntax follows
`Spack's package naming rules <https://spack.readthedocs.io/en/latest/packaging_guide.html#naming-directory-structure>`_.

When creating a new package manager, it is recommended that a ``runner`` class
is created to encapsulate executing commands under the specific package
manager. The ``runner`` class for ``spack`` is included in the
``spack-lightweight`` package manager definition.

^^^^^^^^^^^^
Base Classes
^^^^^^^^^^^^

Ramble provides base classes which can be inherited when creating new package manager
definition files. These encapsulate most of the basic package manager functionality,
and allow new package managers to function with only a little syntax.

New package manager definitions can also inherit their behavior from other
package manager classes to replicate aspects of their behavior.

Existing package manager classes can be referenced using the:
``from ramble.pkg_man.builtin.<package_manager_name> import <package_manager_class>``
syntax.

------------------------------------
Writing a package manager definition
------------------------------------

After a package manager's ``package_manager.py`` file is created, Ramble's
language features can be used to define the bahvior of the modifier. These
language features provide directives which define specific portions of the
package managers's functionality. 

There are many language features available to package managers, and the ones
you use will change based on the specific package manager you need to
implement. Some of the language features are shared with applications and
modifiers, but some are specific to package managers. For more information see
:mod:`ramble.language`.

The directives from Ramble's package manager language are placed alongside
class variables, as in:

.. code-block:: python

  class Spack(PackageManagerBase):
    package_manager_variable(...)
    package_manager_family(...)
    register_builtin(...)
    register_phase(...)

^^^^^^^^^^^^^^^^^^^^^^^^^
Package Manager Variables
^^^^^^^^^^^^^^^^^^^^^^^^^

When aspects of a package manager are able to be parameterized, it can be
useful for a package manager to define a variable which users can modify to
control the package manager's behavior. The ``package_manager_variable``
directive can be used to define these variables.

^^^^^^^^^^^^^^^^^^^^^^^^^
Package Manager Families
^^^^^^^^^^^^^^^^^^^^^^^^^

Package managers can be grouped into families. This allows other objects to
conditionally apply logic based on the family of the package manager being
used. The ``package_manager_family`` directive is used to add a package manager
to one or more families.

^^^^^^^^
Builtins
^^^^^^^^

A builtin is a specific command that is injected within an experiment. Builtins
can have dependencies, and can be injected either at the beginning or end of
the experiments. Builtins are written as class methods that return a list of
strings which are explicit commands to add into an experiment. The
``register_builtin`` directive can be used to add a builtin into an experiment.

For more information on builtins, see the advanced topic documentation on
:ref:`ramble-builtins`.

^^^^^^^^^^^^^^^^^^
Phase Registration
^^^^^^^^^^^^^^^^^^

In Ramble there are several different ``pipelines`` which are groupings of
phases to perform a specific action (such as ``setup`` or ``analyze``). Some
modifiers need to inject phases into one or more of these pipelines. The
``register_phase`` directive can be used to add a phase into a pipeline. Phases
are written as class methods with a specific signature, and will be
automatically executed as part of the pipeline they belong to.

Package managers will primarily define new phases, and register them into
specific experiments to modify the behavior of the different pipelines.

For more information on phases and pipelines, see documentation for
:ref:`ramble-pipelines-and-phases`.

-------------------------
Testing a Package Manager
-------------------------

The package manager that is used in specific experiments is defined using the
:ref:`variants <variants-config>` configuration section. Specifically
``variants:package_manager:<package_manager_name>``. This quantity can be
parameterized, and can refer to a variable which defines which package manager
is used.

The behavior of a package manager when executing a ``dry-run`` depends on how
the runner and package manager were implemented. It is recommended that each
individual runner implement its own ``dry-run`` behavior to enable exploration
with the package manager without having to perform full installation. Existing
package managers can be used as a reference.

**NOTE**: Ramble's unit tests contain a tests called
`known_applications
<https://github.com/Ramble-Project/ramble/blob/develop/lib/ramble/ramble/test/end_to_end/known_applications.py>`_.
This unit test by default will dry-run every possible application with every
possible package manager. As a result, it is unlikely that a package manager
without dry-run support would pass Ramble's unit tests.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Versions, Variants, and Conditional Logic
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Ramble package managers support version and variants, just as applications do
(see :ref:`application-dev-version-directive` and
:ref:`application-dev-variant-directive`).

Versions and variants can be used to control the behavior of many of the
directives within a package manager, and their use follows the
discussion in :ref:`application-dev-conditional-logic`.
