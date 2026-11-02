.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _system_platform_tutorial:

=====================================================
Writing a system and platform definition
=====================================================

This tutorial will provide an introduction to writing system and platform definitions
in Ramble. You should learn what these definition files are for, and how to use
them to standardize experiments in your compute facility. The examples will
focus on generic systems, but should still provide a good introduction.

It is a good idea to have a basic working understanding of how to create and
use Ramble workspaces before starting this tutorial. You should at least be
familiar with the content of the
:ref:`Hello World Tutorial<hello_world_tutorial>`.

This tutorial is intended to be a practical, hands-on guide to creating a
simple set of system and platform definitions.

.. tutorial-header::

Installation
============

To install Ramble, see the :doc:`../getting_started` guide.

.. note::
   This tutorial does not require a package manager to be installed or configured.

.. tutorial-repo-create::


System And Platform Classes
===========================

System classes are intended to represent a cluster in a compute facility, while
a platform class is intended to represent a compute node within the system.
These objects are composable, as a system could be constructed out of many
different platform types.

Systems allow specification of a default workflow manager, default package
manager, and a default platform. Users are allowed to override these within
their workspaces. Systems can define their available platforms, which will
force users to select one of the available platforms.

To begin with, we'll create a platform definition, and then a system definition
that uses the new platform definition.

Your Platform Definition
===============================

In this section, you will write a platform definition representing whatever
machine you are running the tutorial on. The values in this section don't
actually matter, but we will refer to Linux commands to get some system
information.

Platform definitions are intended to represent a specific node. As a result,
they have some node level definitions in them. The base platform definition is
expected to define the following variables.

 * ``max_accelerators_per_node`` - (GPU/TPU/etc.) The number of accelerators each node has
 * ``max_sockets_per_node`` - (CPU) The number of sockets each node has
 * ``max_threads_per_core`` - (CPU) The number of threads available on each core
 * ``max_cores_per_node`` - (CPU) The number of cores available on each node
 * ``max_memory_per_node`` - (RAM) The amount of RAM in GB each node has

By default, a variant (``validate_platform``) is defined, and set to True, that
requires these variables to be defined. You are free to change the default for
your platform, however you can also simply define them to be any value within
your platform definition.

To collect the CPU quantities, we will use the ``lscpu`` command. Examine the
output of this command, and extract all of the CPU quantities. We will refer to
these later when we're writing the platform definition. The RAM quantity can be
collected using ``free -h``, which will print the total amount of RAM on your
system. How you query the number of accelerators varies based on the
accelerator you are using. For the purposes of this tutorial, we will assume
your platform has 2 GPU accelerators.

Create Platform Definition
--------------------------

At this point, you should create a new platform file in:

.. code-block:: console

   tutorial-repo/platforms/my-platform/platform.py

You can create this file using the following commands, or you can use whatever
method you prefer:

.. code-block:: console

   $ mkdir -p tutorial-repo/platforms/my-platform
   $ touch tutorial-repo/platforms/my-platform/platform.py

You can edit the ``platform.py`` file using your editor of choice, or by
executing:

.. code-block:: console

   $ ramble edit --type platforms my-platform


Platform Class
--------------

Ramble provides a module (e.g. ``platkit``) which imports useful methods,
language features, and utility classes when constructing platform definitions.
Each platform definition should import this using:

.. code-block:: python

   from ramble.platkit import *

Platform definitions in Ramble contain a python class that defines the attributes of the
platform. The name of the class matches the directory name for the platform,
but converted to CamelCase. For example, our platform directory is named
``my-platform`` and the class name should be ``MyPlatform`` as a result.

Ramble also provides a base class, ``PlatformBase`` which handles applying the
language definitions, and several other standard aspects of how platforms
function in Ramble. Repositories are allowed to define base platform classes
(of the ``base_platform.py`` type) that can be used to build more complicated
inheritance chains, but we will not cover those in this tutorial.

Platform definitions should also have a class level ``name`` attribute that
matches (exactly) the directory name of the object. In our case:

.. code-block:: python

   name = 'my-platform'

Our beginning platform definition might look something like the following:

.. code-block:: python

   from ramble.platkit import *

   class MyPlatform(PlatformBase):
     name = 'my-platform'

At this point, you should be able to see your platform definition in the output
of:

.. code-block:: console

   $ ramble list --type platforms

Adding Platform Attributes
--------------------------

Previously, you collected information about your platform. In this section, you
will add variable definitions to ensure your platform functions correctly.

This tutorial will assume you have 2 sockets per node, 1 thread per core, 64
cores per node, and 512 GB of RAM. It will also assume you have 2 accelerators
on your platform, and they are both GPUs.

You can use the ``variable`` directive to define variables within the platform
definition for each of these quantities. For example, defining the amount of
memory per node can be done using:

.. code-block:: python

   variable(
     "max_memory_per_node",
     default=512,
     description="Amount of RAM in GB on each node",
   )

Additionally, you can use the ``variant`` directive to enable users to control
aspects of the platform. The ``PlatformBase`` class automatically adds two
variants for ``accelerator`` which can be ``True`` or ``False`` (defaults to
``False``), and ``accelerator_type`` which has a default value of ``None`` but
can take a value of a string.

Since we are assuming your platform has 2 GPUs per node, we will update these
variants, but if your platform doesn't actually have this you can ignore this
portion. These variants can be defined as follows:

.. code-block:: python

   variant(
     "accelerator",
     default=True,
     description="Whether platform has accelerators or not",
   )

   variant(
     "accelerator_type",
     default="GPU",
     values=[None, "GPU"],
     description="Type of accelerator on this platform",
   )

Now, if you add the remaining variable definitions to the class, it might look
something like the following:

.. code-block:: python

   from ramble.platkit import *

   class MyPlatform(PlatformBase):
     name = 'my-platform'

     variable(
       "max_sockets_per_node",
       default=2,
       description="Number of sockets on each node",
     )

     variable(
       "max_threads_per_core",
       default=1,
       description="Threads on each core",
     )

     variable(
       "max_cores_per_node",
       default=64,
       description="Number of cores on each node"
     )

     variable(
       "max_memory_per_node",
       default=512,
       description="Amount of RAM in GB on each node"
     )

     variable(
       "max_accelerators_per_node",
       default=2,
       description="Number of accelerators on each node",
     )

     variant(
       "accelerator",
       default=True,
       description="Whether this platform has accelerators or not",
     )

     variant(
       "accelerator_type",
       default="GPU",
       values=[None, "GPU"],
       description="Type of accelerator on this platform",
     )

All of this information should show up correctly when you execute:

.. code-block:: console

   $ ramble info --type platforms my-platform

While this concludes the creation of your platform class in this tutorial, you
are free to add additional variables, variants, and more advanced features to
your platform definition.

Your System Definition
===============================

In this section, you will write a system definition representing a fictitious
cluster created out of nodes from the platform class you just created. We will
assume your cluster will use the Spack package manager, and the SLURM workload
manager just to show off some of the features of system classes. However, you
are free to manipulate your system class however you wish.

System classes are intended to represent a cluster. Clusters are assumed to be
collections of nodes that are represented by platform classes, like the one you
just created. While the platform class has several required variables, the
system class only has one that it directly requires, but other aspects of a
system can imply additional required variables.

The only variable the system class requires is ``max_nodes`` which should
define how many nodes of a given platform there are. Each platform in the
system can have a different number of nodes, and this variable can take
different values based on the platform selected. For the purposes of this
tutorial, we'll assume you have 4 nodes in your system and you only have nodes
of the type ``my-platform``.

Create System Definition
--------------------------

At this point, you should create a new system file in:

.. code-block:: console

   tutorial-repo/systems/my-system/system.py

You can create this file using the following commands, or you can use whatever
method you prefer:

.. code-block:: console

   $ mkdir -p tutorial-repo/systems/my-system
   $ touch tutorial-repo/systems/my-system/system.py

You can edit the ``system.py`` file using your editor of choice, or by
executing:

.. code-block:: console

   $ ramble edit --type systems my-system

System Class
------------

Like with platform classes, Ramble provides a module (e.g. ``syskit``) which
imports useful functionality for creating system classes. Each system
definition should import this using:

.. code-block:: python

   from ramble.syskit import *

The name of system classes follows the same pattern as platform classes (as
well as any other class in Ramble). As a result, your system class should be
named ``MySystem``, and it should have ``name = 'my-system'`` as a class level
attribute.

The result might look something like the following:

.. code-block:: python

   from ramble.syskit import *

   class MySystem(SystemBase):
     name = 'my-system'


As with platforms, you should be able to see the ``my-system`` system listed in
the output of:

.. code-block:: console

   $ ramble list --type systems

Defining The System
-------------------

Similar to platform classes, the system classes can define variables. In this
case, we need to define ``max_nodes``, but then are free to define
additional variables. Additionally, system classes can define defaults for
each of the package manager, workflow manager, and platform. System classes can
also define the available platforms, to help prevent users from configuring
experiments that won't function properly. It is important to note that any
validation can be disabled by the user, by setting the variant
``validate_system: False`` in their workspace.

As mentioned before, we will assume your system has Spack as the package
manager, and SLURM as the workflow manager. The resulting system class might
look something like the following:

.. code-block:: python

   from ramble.syskit import *

   class MySystem(SystemBase):
     name = 'my-system'

     available_platforms(['my-platform'])

     default_workflow_manager('slurm')
     default_package_manager('spack')
     default_platform('my-platform')

     with when("platform=my-platform"):
       variable(
         "max_nodes",
         default=4,
         description="Number of nodes of this platform in system",
       )

At this stage, you have a fairly complete system class, and all of this
information should be viewable using ``ramble info --type systems my-system``.

As shown in this example, the ``with when(...)`` context manager can be used to
define variables for each platform, and construct more complicated behaviors
within a system class.

Default Workflow Manager Variables
----------------------------------

Some workflow managers have additional required variables, to ensure they
function properly. In this case, we are using the SLURM workflow manager, which
requires a variable ``slurm_partition`` to be defined, that tells experiments
how to submit jobs onto the correct hardware. As mentioned earlier, a system
could contain multiple platforms, representing different physical nodes (and in
the case of SLURM, these might be separate partitions).

To help connect our platform to our workflow manager, the system can define the
required variables. This can be done using the ``with when`` context manager we
saw earlier, or it can be accomplished using the ``platform_variable_map``
directive. This directive functions as almost the inverse of the context
manager. Below is an example of this directive being used to define the
``slurm_partition`` variable.

.. code-block:: python

   platform_variable_map(
     "slurm_partition",
     var_map = {
       "my-platform": "partition1",
     }
   )


Default Software Configuration
------------------------------

Systems (and platforms) sometimes have software installed on them that should
be used when building new software for experiments. This might include system
provided compilers, or MPI implementations, or even something like OpenSSH.
Package managers have their own mechanisms available to connect to this software, and
systems can help provide system specific configuration files to the package
manager in Ramble. In this case, we're assuming you are using Spack.

Spack has several configuration files that can be manipulated to customize
Spack's behavior on your system. As an example, Spack has a `packages.yaml
<https://spack.readthedocs.io/en/latest/packages_yaml.html>`_ file that can be
used to control package preferences and to connect to external packages or
compilers.

For the purposes of this tutorial, we will assume that the image your system
uses has OpenSSH and OpenMPI both installed in ``/usr/``, and we want to tell
Spack (through Ramble) that these exist, and users shouldn't build their own
installation of these packages. An example ``packages.yaml`` file can be seen
below:


.. code-block:: yaml

    packages:
      openssh:
        buildable: false
        externals:
        - spec: openssh@9.9p1
          prefix: /usr
      openmpi:
        buildable: false
        externals:
        - spec: openmpi@4.1.4
          prefix: /usr

Ramble has a directive ``auxiliary_software_file`` that can be used to add a
file that should be included in every environment created within a workspace,
when a specific package manager is used. By default, this directive will search
for files along side the python file for the object that is registering the
auxiliary software file.

To use this directive, write the contents from the example ``packages.yaml``
into the file:

.. code-block:: console

   tutorial-repo/systems/my-system/packages.yaml.tpl

Now, within the system class, add the following:

.. code-block:: python

    with when("package_manager_family=spack"):
        auxiliary_software_file(
            "packages.yaml",
            src_path="packages.yaml.tpl",
            dest_path="packages.yaml",
        )

This will cause experiments that are generated using the ``my-system`` system
class, that also use the Spack package manager to apply our example
``packages.yaml`` file to their software environments.

.. note::
   While we are showing this directive in the context of system classes,
   any object can register auxiliary software files.

.. note::
   The context manager here uses the family of package managers rather
   than an explicit package manager name. This helps to ensure that inherited
   package managers with customized behavior will still be identified as part of
   this family.

.. note::
   While the Spack package manager handles applying these YAML files to
   resulting environments, other package managers might handle this behavior
   differently.

Testing System and Platform Definitions
=======================================

At this point, you have successfully created both a platform, and a system
class. You are now able to create experiments that would utilize these two
classes. This section will walk through testing these classes, but you won't
actually execute any experiments.

Configure Experiments
---------------------

To begin with, we need to create a workspace that uses these new classes. Here,
we will pretend we are going to create experiments using Gromacs. To begin
with, create and activate a test workspace:

.. code-block:: console

   $ ramble workspace create -d test-sys-plat -a

Next, we will add some gromacs experiments to the workspace:

.. code-block:: console

   $ ramble workspace manage experiments gromacs --wf water_bare -V system=my-system \
     -v n_ranks={processes_per_node}*{n_nodes} -v n_nodes=[1,2,4] -v processes_per_node={max_cores_per_node} \
     -e system-test-{n_nodes}

Now that the experiments are configured, we will add some software packages and
an environment.

.. code-block:: console

   $ ramble workspace manage software --pkg gcc --spec "gcc@14.2.0 +binutils target=x86_64"
   $ ramble workspace manage software --pkg gromacs --spec gromacs@{application::version} --compiler gcc
   $ ramble workspace manage software --pkg openmpi --spec openmpi@4.1.4
   $ ramble workspace manage software --env gromacs --environment-packages gromacs,openmpi

At this point you should be able to examine the experiments in the workspace using:

.. code-block:: console

   $ ramble workspace info

This should show that there are three experiments, all using Gromacs, and
changing the node count between 1, 2, and 4. Once this prints the three
experiments correctly, you can perform a dry-run setup using:

.. code-block:: console

   $ ramble workspace setup --dry-run

You can now examine the ``slurm_experiment_sbatch`` scripts inside the
experiment directories (i.e.
``test-sys-plat/experiments/gromacs/water_bare/system-test-1/slurm_experiment_sbatch``)
to see the partition name is applied correctly, and the number of cores per node
and other platform settings are correct.

Once this is verified, you can examine the contents of the software environment
(i.e. ``test-sys-plat/software/spack/gromacs/spack.yaml``) and see that the
``packages`` section has been applied from the template config we defined
earlier.

Summary and Final Cleanup
-------------------------

At this stage, you have now created new system and platform definitions that
can customize the behavior of a workspace for a specific set of hardware. You
have tested it within a workspace, and have constructed a custom object
repository to create new definitions in.

.. tutorial-workspace-cleanup:: test-sys-plat
   :dir:

.. tutorial-repo-cleanup::

