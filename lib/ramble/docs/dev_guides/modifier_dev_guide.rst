.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _modifier-dev-guide:

====================================
Modifier Definition Developers Guide
====================================

Modifier definition files represent standardized objects which can be composed
with applications and experiments to modify their behavior. These can
encapsulate many types of changes, including collecting additional system
information (such as the output of ``lscpu``) or injecting a performance
analysis tool into the experiment workflow.

This guide will provide general steps for creating a new modifier definition file.

**NOTE:** Modifiers are considered a more advanced feature of Ramble. Writing a
new modifier definition file in Ramble largely follows the same workflow as
writing an application definition file, although the intent and behavior are
different. It is recommended that you review :ref:`application-dev-guide`
before writing a modifier.

-----------
Preparation
-----------

Before writing a modifier definition file, it is helpful to determine what
aspects of the modification need to be grouped together.

It can be useful to think of a modifier as some pattern you would like to apply
to many experiments, that doesn't actually have anything to do with the
behavior of an application directly. Depending on your goal for modifiers and
the application of these patterns, you could write one modifier to apply all of
the changes, or encapsulate a smaller set of changes into many modifiers.

Some of the information you need to gather before writing your modifier include:

#. Commands you need to execute as part of your changes
#. Environment variables that need to be changed (set, appended, prepended, or unset)
#. An example of output the modifier would create (if any)

^^^^^^^^^^^^^^^^^^^^^^^^^^
Compilation / Installation
^^^^^^^^^^^^^^^^^^^^^^^^^^

Some modifiers require specific software packages to be available to function
properly. Modifiers can define software packages that will be install, or
required to be available when a supported package manager is used. See the
:ref:`application-definition-compilation` section of the application definition
developers guide.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Testing execution and Output information
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

For this step, it can be useful to manually execute the commands / steps you
want to encapsulate into a modifier. This step helps you understand how the
modification will actually behave, and can be used to get example output to
create modifier figures of merit and success criteria.

----------------------------
Modifier Definition Creation
----------------------------

Modifier definition files are stored within object repositories. These
repositories generally store modifiers within a directory named ``modifiers``.
Individual repositories can control this through their own config file (
``repo.yaml`` or ``modifier_repo.yaml`` ).

Within the repository, each modifier definition file is a python module that is
stored within a directory named for the modifier. As an example, Ramble comes
with a repository named ``builtin``. This repository contains several standard
modifier definitions that are provided to the community. One of the modifier
definition files provided is
`lscpu <https://github.com/Ramble-Project/ramble/blob/develop/var/ramble/repos/builtin/modifiers/lscpu/modifier.py>`_.

The lscpu modifier definition file is named ``modifier.py`` and is stored
within a directory named ``lscpu``. Within the ``modifier.py`` file, a python
class is defined with a similar name to the modifier directory. Ramble's
modifier definition naming syntax follows
`Spack's package naming rules <https://spack.readthedocs.io/en/latest/packaging_guide.html#naming-directory-structure>`_.

^^^^^^^^^^^^
Base Classes
^^^^^^^^^^^^

Ramble provides base classes which can be inherited when creating new modifier
definition files. These encapsulate most of the basic modifier functionality,
and allow new modifiers to function with only a little syntax.

New modifier definitions can also inherit their behavior from other
modifier classes to replicate aspects of their behavior.

Existing modifier classes can be referenced using the:
``from ramble.mod.builtin.<modifier_name> import <modifier_class>`` syntax.

-----------------------------
Writing a modifier definition
-----------------------------

After a modifier's ``modifier.py`` file is created, Ramble's language features
can be used to define the bahvior of the modifier. These language features
provide directives which define specific portions of the modifier's
functionality. 

There are many language features available to modifiers, and the ones you use
will change based on the specific modifier you need to implement. Some of the
language features are shared with applications and package managers, but some
are specific to modifiers. For more information see :mod:`ramble.language`.

The directives from Ramble's modifier language are placed alongside class
variables, as in:

.. code-block:: python

  class Lscpu(BasicModifier):
    mode(...)
    default_mode(...)
    modifier_variable(...)
    variable_modification(...)
    register_builtin(...)
    register_phase(...)
    executable_modification(...)
    env_var_modification(...)

^^^^^
Modes
^^^^^

Modifiers can have multiple ``modes`` which are used to change the behavior of
the modifier. This can be helpful if the general modifier stays the same, but
some aspects of the modifier change under different usage models.

If a modifier only has a single ``mode`` defined, this becomes the default
mode. The default mode can be specified using the ``default_mode`` directive.

Every modifier has a ``disabled`` mode added by default, which cannot be passed
into the ``default_mode`` directive. This mode allows turning off modifiers
without having to remove them from the workspace configuration file.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Modifier Variables and Variable Modifications
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Sometimes a modifier needs to define or manipulate variable definitions inside an
experiment. This could include something like adding arguments to a command
(like ``mpirun``) or defining new variables entirely.

The ``modifier_variable`` and ``variable_modification`` directives can be used
to define or edit variables within experiments.

^^^^^^^^
Builtins
^^^^^^^^

A builtin is a specific command that is injected within an experiment. Builtins
can have dependencies, and and be injected either at the beginning or end of
the experiments. Builtins are written as class methods that return a list of
strings which are explicit commands to add into an experiment. The
``register_builtin`` directive can be used to add a builtin into an experiment.

^^^^^^^^^^^^^^^^^^
Phase Registration
^^^^^^^^^^^^^^^^^^

In Ramble there are several different ``pipelines`` which are groupings of
phases to perform a specific action (such as ``setup`` or ``analyze``). Some
modifiers need to inject phases into one or more of these pipelines. The
``register_phase`` directive can be used to add a phase into a pipeline. Phases
are written as class methods with a specific signature, and will be
automatically executed as part of the pipeline they belong to.

^^^^^^^^^^^^^^^^^^^^^^^
Executable Modification
^^^^^^^^^^^^^^^^^^^^^^^

One of the most powerful modifications available within modifier definitions is
the ``executable_modifier`` directive . Some modifiers will require the
ability to inject commands around commands that exist in the experiments
already. A good example of this is a performance analysis tool, which needs to
modify the execution command to profile the experiment, and generate a summary
of the performance characteristics of the experiment after it is complete.

To accomplish this goal, the ``executable_modifier`` directive can be used,
which is implemented as a class method which returns two lists of
``CommandExecutable`` objects, which are injected before and after each
executable.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Package Manager Requirements
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Modifiers can define requirements that must be met when using a package manager.
The ``package_manager_requirement`` directive
(:py:meth:`ramble.language.modifier_language.package_manager_requirement`) can
be used to ensure certain package manager commands return expected output.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Environment Variable Modification
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some modifiers need to edit environment variables within an experiment. The
``env_var_modification`` directive can be used to change existing environment
variables.

^^^^^^^^^^^^^^^^^^^^
Shared Functionality
^^^^^^^^^^^^^^^^^^^^

There are several directives that are shared between applications and modifiers.
These include success criteria, figures of merit, and figures of merit context.
For more information on these, refer to either the :ref:`application-dev-guide` or 
guide, :mod:`ramble.language`.

------------------
Testing a Modifier
------------------

Modifiers are added into experiments using the :ref:`modifiers
<modifiers-config>` configuration section.

Modifiers are used within ``dry-run`` pipeline executions in Ramble. As an
example, it can be useful to verify the behvior of the modifier is functioning
correctly by using ``ramble workspace setup --dry-run``. The output from the
preparation steps can be copied into the experiment directory to verify the
``ramble workspace analyze`` pipeline works, without having to execute the
experiment itself.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Versions, Variants, and Conditional Logic
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Ramble modifiers support versions and variants, just as applications do (see
:ref:`application-dev-version-directive` and
:ref:`application-dev-variant-directive`).

Variants can be used to control the behavior of many of the
directives within a modifier, and their use follows the discussion
in :ref:`application-dev-conditional-logic`.

^^^^^^^^^^^^^^^^^^^^^^^^
Multi-modifier Conflicts
^^^^^^^^^^^^^^^^^^^^^^^^

Ramble supports repeating modifier definitions within the ``modifiers``
configuration section. This can be useful (when applying varying modes of the
same modifier) but can also present a challenge to modifier developers.
Modifiers are not inherently able to be replicated multiple times on the same
experiment without providing some unexpected behaviors.

In the modifier language, Ramble allows modifiers to define how they should
conflict with other modifier definitions when aspects of their definitions
overlap.

The ``modifier_conflict`` language feature can be used to control what Ramble's
behavior should be when repeated definitions of the same modifier exist. An
enum is provided in ``ramble.util.conflicts`` named ``MODIFIER_CONFLICT`` to
understand what options exist.

This language feature supports the ``when`` and variant logic that was
previously described, which can allow the conflict behavior to change based on
variant settings.
