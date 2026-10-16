.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _basic_application_tutorial:

========================================
Writing a basic application definition
========================================

This tutorial will provide an introduction to writing an application definition
in Ramble. In this tutorial, you will create and test an application definition
file to run the ``hostname`` linux utility as your application.

It is a good idea to have a basic working understanding of how to create and
use Ramble workspaces before starting this tutorial. You should at least be
familiar with the content of the
:ref:`Hello World Tutorial<hello_world_tutorial>`.

This tutorial is intended to be a practical, hands-on guide to creating a
simple application definition. For a more comprehensive reference on all
available directives and advanced features, please see the
:ref:`Application Definition Developers Guide<application-dev-guide>`.

.. raw:: html

   <div class="tn-ws-prompt"></div>

Installation
============

To install Ramble, see the :doc:`../getting_started` guide.

.. note::
   This tutorial does not require a package manager to be installed or configured.

.. include:: shared/repository_create.rst

Hostname Application Definition
===============================

For the remainder of this tutorial, we will be writing and testing the contents
of the hostname application definition.

Create Application Definition
-----------------------------

To begin with, we will create an empty application definition file. We will
populate this file throughout the remainder of this tutorial. To create it,
issue the following commands:

.. code-block:: console

    $ mkdir -p tutorial-repo/applications/hostname
    $ touch tutorial-repo/applications/hostname/application.py

For the remainder of this tutorial, ``ramble edit hostname`` will open this
file with the editor specified with your ``EDITOR`` environment variable.

Application Class
-----------------

Ramble provides a module (e.g. ``appkit``) which imports a large portion of the
features to write application definitions. Each application definition should
import this using:

.. code-block:: python

   from ramble.appkit import *

Every application definition in Ramble contains a python class that defines the
characteristics of the application. The name of this class matches the
directory name for the application, but converted to CamelCase. Since our
application name (``hostname``) does not have any hyphens or underscores in the
name, the python class name will be ``Hostname``. 

Ramble also provides a base class, ``ExecutableApplication`` which handles
applying the application language to the object. Every application definition
should inherit from either this, or something else that inherits from this
class.

Object definitions should have a name attribute that matches the directory name
as well. In this case: ``name = 'hostname'``.

As a result, our class definition file should contain the following to start.

.. code-block:: python

    from ramble.appkit import *

    class Hostname(ExecutableApplication):
      name = 'hostname'

At this stage, our application should show up in the output of ``ramble list``
and ``ramble info hostname`` should show limited information about this
application.

Definition Experiment Constructs
--------------------------------

To begin with, we will create some basic constructs within this application
definition that will help us test the creation of experiments.

Application Executables
^^^^^^^^^^^^^^^^^^^^^^^

The lowest level construct in an application definition is an executable.
Executables relate to arbitrary commands that you would normally execute when
running your specific application. Since we are writing an application
definition for hostname, our command simply looks like ``hostname``. The
language feature  ``executable`` can be used to define how Ramble should use
these. The documentation for the ``executable`` directive can be found at
:py:meth:`ramble.language.application_language.executable`.

For the purposes of this tutorial, we will begin by assuming we will not
execute ``hostname`` under an ``mpi`` runtime. The starting executable
definition will be:

.. code-block:: python

    executable(
      "local-execute",
      "hostname",
    )

This defines a new executable in the hostname application definition named
``local-execute`` and the template for the executable is simply the
``hostname`` command. The remaining arguments are left as the default which
will disable MPI on this executable.

.. note::
    Throughout these tutorials the directives such as ``executable`` are
    called using positional parameters as above. However, named parameters -
    or even a mix of positional and named parameters - are also allowed. For
    example, the following is identical to the above example:

    .. code-block:: python

        executable(
            name="local-execute",
            template="hostname",
        )

Application Workloads
^^^^^^^^^^^^^^^^^^^^^

Workloads are the construct that users refer to within workspaces to create
experiments. Workloads are the pairing of one or more executables with zero or
more input files. In the case of ``hostname`` we have no input files that are
required to run this application. The documentation for the workload directive
can be seen at: :py:meth:`ramble.language.application_language.workload`.

In our case, we will create a new workload that simply uses the
``local-execute`` executable. This directive should look like:

.. code-block:: python

    workload("local", executables=["local-execute"])

At this stage, our application definition should look like the following:

.. code-block:: python

    from ramble.appkit import *

    class Hostname(ExecutableApplication):

      name = "hostname"

      executable(
        "local-execute",
        "hostname"
      )

      workload("local", executables=["local-execute"])

With this application definition, we are now at a point where experiments can
be constructed to test this definition file.

.. _basic_definition_test:

Testing Application Definitions
-------------------------------

To exercise the application definition, we need to construct and activate a
workspace. To do this, execute the following:

.. code-block:: console

    $ ramble workspace create -d tutorial-workspace -a

.. note::
   If you have an active workspace (e.g., if you used ``ramble workspace
   create -a`` in a previous session or this one), you must first deactivate it
   with ``ramble workspace deactivate`` or unset the ``RAMBLE_WORKSPACE``
   environment variable to avoid conflicts when creating a new workspace. Also,
   creating a workspace *without* the ``-a`` (activate) flag means you would need
   to either run ``ramble workspace activate tutorial-workspace`` or use the
   ``-D <workspace_path>`` flag with subsequent ``ramble`` commands to specify
   which workspace to operate on.

The following command can be used to add an experiment with the workload we defined earlier:

.. code-block:: console

   $ ramble workspace manage experiments hostname -v "n_nodes=1" -v "n_ranks=1" --overwrite

This will add a single experiment, named ``generated`` to the workspace that
will use the hostname application and the local workload (since this is the
only defined workload at the moment).

.. container:: tn-full-run-only

   The experiments can then be set up using:

   .. code-block:: console

      $ ramble workspace setup

.. container:: tn-dry-run-only

   With **Dry-Run Mode** enabled, set up the experiments using ``--dry-run``:

   .. code-block:: console

      $ ramble workspace setup --dry-run

The contents of the experiment's ``execute_experiment`` script can be examined
to ensure it looks correct. It should be inside the workspace in the
``experiments/hostname/local/generated/execute_experiment`` path. The contents
should look similar to the following (with some expected path differences):

.. code-block:: console

    #!/bin/bash
    # This is a template execution script for
    # running the execute pipeline.
    #
    # Variables surrounded by curly braces will be expanded
    # when generating a specific execution script.
    # Some example variables are:
    #   - experiment_run_dir (Will be replaced with the experiment directory)
    #   - command (Will be replaced with the command to run the experiment)
    #   - log_dir (Will be replaced with the logs directory)
    #   - experiment_name (Will be replaced with the name of the experiment)
    #   - workload_run_dir (Will be replaced with the directory of the workload
    #   - application_name (Will be replaced with the name of the application)
    #   - n_nodes (Will be replaced with the required number of nodes)
    #   Any experiment parameters will be available as variables as well.

    # ****************************************************
    # * No workflow is used with this experiment
    # * Execution command: /tmp/tutorial-workspace/experiments/hostname/local/generated/execute_experiment
    # * If this file is not the same as the above path, it is unlikely that this script
    # * is used when `ramble on` executes experiments.
    # ****************************************************


    cd "/tmp/tutorial-workspace/experiments/hostname/local/generated"

    rm -f "/tmp/tutorial-workspace/experiments/hostname/local/generated/generated.out"
    touch "/tmp/tutorial-workspace/experiments/hostname/local/generated/generated.out"
    export OMP_NUM_THREADS="1";
    hostname >> "/tmp/tutorial-workspace/experiments/hostname/local/generated/generated.out" 2>&1

The last line of this file shows the hostname command will be run, and the
output will be redirected to the experiment's log file.

.. container:: tn-full-run-only

   At this stage, this experiment can be executed (if you have access to the
   ``hostname`` binary) to ensure it executes properly. This can be accomplished using:

   .. code-block:: console

      $ ramble on

   After executing, the output of the hostname command should exist in the
   ``generated.out`` file inside the experiment's directory.

.. container:: tn-dry-run-only

   In dry-run mode, ``ramble on`` is skipped; inspecting the generated
   ``execute_experiment`` file above confirms that our new application definition
   renders the expected command line. In a full run, executing ``ramble on`` runs
   this script and writes the machine's hostname into ``generated.out`` inside the
   experiment directory.

This workflow can be used in the future to continue testing our application
definition.

Workload Variables
------------------

Workload variables are a mechanism that application definition developers can
use to expose aspects of an application or workload that users might want to
control. These can be anything from input flags / arguments, to parameter
definitions.

We will use workload variables to allow users to control the execution flags on
the ``hostname`` binary. While the default might be to only use the default
behavior of ``hostname``, adding this functionality in allows the application
definition to be more flexible for users in the future.

The :py:meth:`ramble.language.application_language.workload_variable` directive
is used to create a variable that users can easily know about. We will now
create a variable named ``input_arguments`` using the following directive:

.. code-block:: python

      workload_variable(
        "input_arguments",
        default="",
        description="Input arguments for hostname",
        workloads=["*"],
      )

In this example, we set the default value to be ``""`` which will retain the
default ``hostname`` behavior, we can write a description to provide
information to users about what the purpose of this variable is, and we can
control which workloads this variable are associated with. In this example, we
use ``["*"]`` to glob all workloads and make it easier for this to be used on
all workloads. However, selecting specific workloads can allow developers to
change the default value of a variable based on the workload selected.

Now that we have a variable, we need to update the executable definition to
make sure it is used. The new ``local-execute`` definition should look like the
following:

.. code-block:: python

    executable(
      "local-execute",
      "hostname {input_arguments}"
    )

This definition allows the ``local-execute`` executable to expand the value of
the ``input_arguments`` variable and append it to the ``hostname`` executable.

If a user had the following in their workspace config:

.. code-block:: yaml

    variables:
      input_arguments: "-i"

The resulting rendered ``execute_experiment`` script will contain the ``-i``
flag, and the output should be an IP address instead of a hostname.

At this point, :ref:`the basic test<basic_definition_test>` can be used to see
how the ``input_arguments`` applies to experiments.

.. note::
   When using the ``workload`` or ``workloads`` arguments on the
   ``workload_variable`` directive, the directive needs to show up after the
   workloads it is attached to within the python class. Usage of
   ``workload_group`` s can mitigate this restriction.


Parallel Executables
--------------------

Some applications need to be executed under some parallel runtime, such as MPI.
Within application definitions, developers can convey this to Ramble by adding
the ``use_mpi=True`` argument when defining new executables.

When this argument is set to ``True``, Ramble will prepend the ``mpi_command``
variable definition to the command line within the resulting execution script.
Users can control the value of the ``mpi_command`` from their workspace, or the
definition can come from other object definitions (such as
``workflow_managers``), however this is the mechanism for executables to say
they should be executed in parallel.

To see how this behaves, we will create a new workload that will represent the
parallel execution of ``hostname``. In general, ``hostname`` only needs to be
executed once per node in the job. As a result, we will override the
``n_ranks`` variable definition to match the ``n_nodes`` value.

.. code-block:: python

    executable(
      "parallel-execute",
      "hostname {input_arguments}",
      use_mpi=True,
      variables={"n_ranks": "{n_nodes}"},
    )

    workload("parallel", executables=["parallel-execute"])


To test this, we can follow the steps in :ref:`the basic
test<basic_definition_test>` from earlier, which will now create experiments
for each of the two workloads.

.. note::
   If you had a value for ``input_arguments`` running the commands as-is
   could remove these from your workspace.

After setting up the workspace again, the parallel workload's generated
``execute_experiment`` script should contain:

.. code-block:: console

    mpirun -n 1 hostname  >> "/tmp/tutorial-workspace/experiments/hostname/parallel/generated/generated.out" 2>&1

The default ``mpi_command`` from the ``user-managed`` workflow manager happens
to be ``mpirun -n {n_ranks}``, which is prepended to our ``hostname``
executable in this line.

.. note::
   Execution of these experiments will fail if you do not have
   ``mpirun`` on the system you're running the experiments on. To execute only the
   experiments with the local workload, you can use:

.. code-block:: console

    $ ramble on --where '"{workload_name}" == "local"'

Analysis of experiments
-----------------------

Up until this point, we have focused on constructing the execution of
experiment. However, Ramble also handles analysis of the experiments. To do
this, application definitions define figures of merit. A figure of merit is an
arbitrary metric that Ramble should extract and track for each experiment
generated from this application definition. Additionally, success criteria can
be defined to help users know whether their experiment behaved the way it was
expected to or not.

Figure of merit
^^^^^^^^^^^^^^^

To begin with, we will add a figure of merit using the
:py:meth:`ramble.language.shared_language.figure_of_merit`
directive. Figures of merit are extracted using a regular expression match on
some file in the experiment directory. We will use the following definition to
track whatever the output from the experiment is as the possible hostname:

.. code-block:: python

    figure_of_merit(
      "possible hostname",
      fom_regex=r"(?P<hostname>\S+)",
      group_name="hostname",
      units="",
    )

In this directive, the name ``possible hostname`` will show up in the resulting
results file after analysis of a workspace. The ``fom_regex`` argument controls
what regular expression is used to extract this figure of merit. The
``group_name`` argument controls which regular expression group (from the
``fom_regex`` argument) matches this specific figure of merit. And the
``units`` argument allows us to define the units on the resulting figure of
merit.

After defining this figure of merit, the:

.. code-block:: console

   $ ramble workspace analyze

command can be used to extract figures of merit from our experiments.

.. note::
   This figure of merit definition will only extract the last line from
   the experiment's output file. In the case of a parallel run, this will not
   contain all of the hostnames. To build this list, we would use an in-memory
   figure of merit, but we will leave the definition of this for a later tutorial.

Success Criteria
^^^^^^^^^^^^^^^^

To help users know if their experiments worked or not, application developers
can define success criteria. Success criteria can examine several aspects of an
experiment, including checking for existence of (or non-existence) of a
particular string, comparing the value of a figure of merit, or executing
arbitrary python to determine if the experiment succeeded or failed.

For this tutorial, we will add a basic success criteria that just ensures
something was written from the ``hostname`` executable. This success criteria
should look like the following:

.. code-block:: python

    success_criteria("wrote_anything", mode="string", match=r".*")

Putting it all together
-----------------------

At this point, we should have a fairly complete ``hostname`` application
definition that includes workloads for running locally on a given machine, and
in parallel on many different machines. Users should also get reasonable
figures of merit as output, and their experiments should inform them of failed
runs.

Application Definition
^^^^^^^^^^^^^^^^^^^^^^

Our complete application definition at this point is as follows:

.. code-block:: python

    from ramble.appkit import *

    class Hostname(ExecutableApplication):
        name = 'hostname'

        executable(
            "local-execute",
            "hostname {input_arguments}",
        )

        workload("local", executables=["local-execute"])

        executable(
            "parallel-execute",
            "hostname {input_arguments}",
            use_mpi=True,
            variables={"n_ranks": "{n_nodes}"}
        )

        workload("parallel", executables=["parallel-execute"])

        workload_variable(
            "input_arguments",
            default="",
            description="Arguments for executing `hostname`",
            workloads=["*"]
        )

        figure_of_merit(
            "possible hostname",
            fom_regex=r"(?P<hostname>\S+)",
            group_name="hostname",
            units="",
        )

        success_criteria("wrote_anything", mode="string", match=r".*")

Final Tests
^^^^^^^^^^^

To complete this tutorial we will test the ``local`` workload to see how
everything works.

To begin with, delete the tutorial workspace, and recreate it using:

.. code-block:: console

  $ ramble workspace deactivate
  $ rm -rf tutorial-workspace
  $ ramble workspace create -d tutorial-workspace -a

Now, we can add an experiment to exercise the local workload using:

.. code-block:: console

  $ ramble workspace manage experiments hostname --workload-filter local -v n_ranks=1 -v n_nodes=1

The ``--workload-filter local`` arguments are added here to filter the
workloads so we only use the local workload.

.. container:: tn-full-run-only

   Now, to complete the test we can execute:

   .. code-block:: console

     $ ramble workspace setup
     $ ramble on
     $ ramble workspace analyze

   The result of these commands should be the creation of a ``results.latest.txt``
   file that contains the hostname of your machine.

.. container:: tn-dry-run-only

   Since **Dry-Run Mode** is enabled, we can set up the experiment using
   ``--dry-run`` without executing it or analyzing results:

   .. code-block:: console

     $ ramble workspace setup --dry-run

   Instead of running ``ramble on`` and ``ramble workspace analyze``, you can
   explore the generated experiment directory and examine the rendered
   ``execute_experiment`` script:

   .. code-block:: console

     $ ls -la tutorial-workspace/experiments/hostname/local/generated
     $ cat tutorial-workspace/experiments/hostname/local/generated/execute_experiment

   If you were to execute and analyze the experiment in a full run, Ramble would
   create a ``results.latest.txt`` file that contains the hostname of your
   machine.



Summary and Final Cleanup
-------------------------

At this stage, you have now created a new application definition to execute the
``hostname`` binary. You have tested it within a workspace, and have
constructed a custom object repository to create new definitions in.

.. container:: tn-workspace-cleanup

   To clean up your system, make sure to deactivate your workspace before trying
   to remove it. These steps can be completed with:

   .. code-block:: console

     $ ramble workspace deactivate
     $ rm -rf tutorial-workspace

.. container:: tn-repo-cleanup

   You are also free to delete the ``tutorial-repo`` repository, but make sure you
   unregister it from your list of repositories using the ``ramble repo rm``
   command:

   .. code-block:: console

     $ ramble repo rm tutorial-repo
     $ rm -rf tutorial-repo
