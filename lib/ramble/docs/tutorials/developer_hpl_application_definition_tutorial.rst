.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _hpl_application_tutorial:

======================================
Writing an HPL application definition
======================================

This tutorial will provide an introduction to writing a more complex
application definition in Ramble. In this tutorial, you will create and test an
application definition file to run the `High-Performance Linpack (HPL)
<https://www.netlib.org/benchmark/hpl/>`_ benchmark.

This tutorial builds on the concepts introduced in the
:ref:`Basic Application Tutorial<basic_application_tutorial>` and introduces
new concepts such as software dependencies and input file templating.

It is a good idea to have a basic working understanding of how to create and
use Ramble workspaces before starting this tutorial. You should at least be
familiar with the content of the
:ref:`Hello World Tutorial<hello_world_tutorial>`.

.. tutorial-header::

Installation
============

To install Ramble, see the :doc:`../getting_started` guide.

.. note::
   This tutorial utilizes the ``spack`` package manager. As a result, it
   requires ``spack``. If ``spack`` is not installed and available in your
   ``PATH``, it will be bootstrapped for you. To see compilers already
   available to Spack, use ``spack compilers``.

.. tutorial-repo-create::


HPL Application Definition
==========================

For the remainder of this tutorial, we will be writing and testing the contents
of the HPL application definition.

Create Application Definition
-----------------------------

To begin with, we will create an empty application definition file and a
placeholder for our input file template. These will live in the same directory.

.. code-block:: console

    $ mkdir -p tutorial-repo/applications/hpl/templates
    $ touch tutorial-repo/applications/hpl/application.py
    $ touch tutorial-repo/applications/hpl/templates/HPL.dat.tpl

For the remainder of this tutorial, ``ramble edit hpl`` will open this
file with the editor specified with your ``EDITOR`` environment variable.

Application Class
-----------------

Following the description of the application class in the :ref:`Basic
Application Tutorial<basic_application_tutorial>`, the following can be used as
the beginning of our HPL application definition.

.. code-block:: python

    from ramble.appkit import *

    class Hpl(ExecutableApplication):
        name = 'hpl'

At this stage, our application should show up in the output of ``ramble list``
and ``ramble info hpl`` should show limited information about this application.


Software Specification
----------------------

Unlike the ``hostname`` utility, HPL is not typically pre-installed. We need to
tell Ramble how to build it. We can do this using the ``software_spec``
directive. This directive takes a `Spack spec
<https://spack.readthedocs.io/en/latest/spec_syntax.html>`_ to define the
software and its dependencies.

.. code-block:: python

        with when("package_manager_family=spack"):
            software_spec(name="hpl", pkg_spec="hpl@2.3")

This tells Ramble to use Spack to install HPL version 2.3. The ``with when(...)``
construct makes these directives conditional on the package manager being used.

.. note::
   By default, Spack will be allowed to select any MPI implementation it
   wants for this installation. Application definitions can optionally define
   additional ``software_specs`` to further control the default software stack for
   applications.

Input File Template
-------------------

HPL requires an ``HPL.dat`` input file to run. Ramble has directives for
downloading input files from websites. However, given this is a basic text
file, Ramble can generate this file from a template. We use the
``register_template`` directive to tell Ramble how to generate this file for
us. The documentation for the ``register_template`` directive can be found at
:py:meth:`ramble.language.shared_language.register_template`.

.. code-block:: python

        register_template(
            "hpl.dat.in",
            src_path="templates/HPL.dat.tpl",
            dest_path="HPL.dat"
        )

Now, let's populate the template file
``tutorial-repo/applications/hpl/templates/HPL.dat.tpl``. We can refer to any
workload variables we are going to add into the application definition using
curly brace syntax. When Ramble renders this file into the experiment
directory, these values will be expanded for us.

.. code-block:: jinja

    HPLinpack benchmark input file
    Innovative Computing Laboratory, University of Tennessee
    HPL.out      output file name (if any)
    6            device out (6=stdout,7=stderr,file)
    1            # of problems sizes (N)
    {Ns}         Ns
    1            # of NBs
    {NBs}        NBs
    0            PMAP process mapping (0=Row-,1=Column-major)
    1            # of process grids (P x Q)
    {Ps}         Ps
    {Qs}         Qs
    16.0         threshold
    1            # of panel fact
    2            PFACTs (0=left, 1=Crout, 2=Right)
    1            # of recursive stopping criterium
    4            NBMINs (>= 1)
    1            # of panels in recursion
    2            NDIVs
    1            # of recursive panel fact.
    1            RFACTs (0=left, 1=Crout, 2=Right)
    1            # of broadcast
    1            BCASTs (0=1rg,1=1rM,2=2rg,3=2rM,4=Lng,5=LnM)
    1            # of lookahead depth
    1            DEPTHs (>= 0)
    2            SWAP (0=bin-exch,1=long,2=mix)
    64           swapping threshold
    0            L1 in (0=transposed,1=no-transposed) form
    0            U  in (0=transposed,1=no-transposed) form
    1            Equilibration (0=no,1=yes)
    8            memory alignment in double (> 0)

Definition Experiment Constructs
--------------------------------

Now we will define the executable and workload for HPL.

Application Executables
^^^^^^^^^^^^^^^^^^^^^^^

HPL is an MPI application. We will define an executable that runs `xhpl`, the
HPL executable. We'll set ``use_mpi=True`` to tell Ramble to prepend the
workspace's MPI command to this executable. This allows users to run it with an
MPI launcher like `mpirun` or `srun`.

.. code-block:: python

        executable(
            "hpl-execute",
            "xhpl",
            use_mpi=True,
        )

Application Workloads
^^^^^^^^^^^^^^^^^^^^^

Here, we'll create a default workload that uses our executable. Given our input
file is generated from a template, we do not need to list it in the workload
specification.

.. code-block:: python

        workload(
            "default",
            executables=["hpl-execute"],
        )

Workload Variables
^^^^^^^^^^^^^^^^^^

Now that we have a workload defined, we can define the variables that we added
into our template input file (e.g. ``{Ns}``). We need to define them in our
application definition using the ``workload_variable`` directive so users can
set them.

.. code-block:: python

        workload_variable("Ns", default=1000, description="Problem size", workload="default")
        workload_variable("NBs", default=256, description="Block size", workload="default")
        workload_variable("Ps", default=1, description="Number of process rows", workload="default")
        workload_variable("Qs", default=1, description="Number of process columns", workload="default")

Analysis of experiments
-----------------------

Ramble can analyze experiment output to extract performance metrics and
determine success or failure.

Figure of merit
^^^^^^^^^^^^^^^


HPL itself provides a mechanism for running several problem sizes in an attempt
to maximize the GFlops rating. To ensure we do not lose data when extracting
GFlops rating from HPL, we can create a figure of merit context to relate the
GFlops rating to the input parameters. We can then define the figure of merit
to exist within this context. The context can look like the following:

.. code-block:: python

        figure_of_merit_context(
            "problem-name",
            regex=r".*?\s+(?P<N>[0-9]+)\s+(?P<NB>[0-9]+)\s+(?P<P>[0-9]+)\s+(?P<Q>[0-9]+)\s+(?P<time>[0-9]+\.[0-9]+)\s+(?P<gflops>\S+)",
            output_format="N-NB-P-Q = {N}-{NB}-{P}-{Q}",
        )

This creates a new figure of merit context named ``problem-name`` which figures
of merit can be associated with. The context will have the ``N``, ``NB``,
``P``, and ``Q`` values associated with all figures of merit within. Since
HPL reports its performance in Gflops, we extract this value using the
``figure_of_merit`` directive with a regular expression.

.. code-block:: python

        figure_of_merit(
            "gflops",
            fom_regex=r".*?\s+(?P<N>[0-9]+)\s+(?P<NB>[0-9]+)\s+(?P<P>[0-9]+)\s+(?P<Q>[0-9]+)\s+(?P<time>[0-9]+\.[0-9]+)\s+(?P<gflops>\S+)",
            group_name="gflops",
            units="Gflops",
            contexts=["problem-name"],
            fom_type=FomType.THROUGHPUT
        )

Here we have associated the figure of merit with the ``problem-name`` and also
added the ``fom_type`` attribute to convey to users (and Ramble) that this is a
throughput metric.

HPL additionally outputs time for the experiments. We can track this as a
separate figure of merit:

.. code-block:: python

        figure_of_merit(
            "Time",
            fom_regex=r".*?\s+(?P<N>[0-9]+)\s+(?P<NB>[0-9]+)\s+(?P<P>[0-9]+)\s+(?P<Q>[0-9]+)\s+(?P<time>[0-9]+\.[0-9]+)\s+(?P<gflops>\S+)",
            group_name="time",
            units="s",
            contexts=["problem-name"],
            fom_type=FomType.TIME,
        )


Putting it all together
-----------------------

Our complete application definition at this point is as follows:

.. code-block:: python

    from ramble.appkit import *

    class Hpl(ExecutableApplication):
        name = 'hpl'

        with when("package_manager_family=spack"):
            software_spec(name="hpl", pkg_spec="hpl@2.3")

        register_template(
            "hpl.dat.in",
            src_path="templates/HPL.dat.tpl",
            dest_path="HPL.dat"
        )

        executable(
            "hpl-execute",
            "xhpl",
            use_mpi=True,
        )

        workload(
            "default",
            executables=["hpl-execute"],
        )

        workload_variable("Ns", default=1000, description="Problem size", workload="default")
        workload_variable("NBs", default=256, description="Block size", workload="default")
        workload_variable("Ps", default=1, description="Number of process rows", workload="default")
        workload_variable("Qs", default=1, description="Number of process columns", workload="default")

        figure_of_merit_context(
            "problem-name",
            regex=r".*?\s+(?P<N>[0-9]+)\s+(?P<NB>[0-9]+)\s+(?P<P>[0-9]+)\s+(?P<Q>[0-9]+)\s+(?P<time>[0-9]+\.[0-9]+)\s+(?P<gflops>\S+)",
            output_format="N-NB-P-Q = {N}-{NB}-{P}-{Q}",
        )

        figure_of_merit(
            "gflops",
            fom_regex=r".*?\s+(?P<N>[0-9]+)\s+(?P<NB>[0-9]+)\s+(?P<P>[0-9]+)\s+(?P<Q>[0-9]+)\s+(?P<time>[0-9]+\.[0-9]+)\s+(?P<gflops>\S+)",
            group_name="gflops",
            units="Gflops",
            contexts=["problem-name"],
            fom_type=FomType.THROUGHPUT
        )

        figure_of_merit(
            "Time",
            fom_regex=r".*?\s+(?P<N>[0-9]+)\s+(?P<NB>[0-9]+)\s+(?P<P>[0-9]+)\s+(?P<Q>[0-9]+)\s+(?P<time>[0-9]+\.[0-9]+)\s+(?P<gflops>\S+)",
            group_name="time",
            units="s",
            contexts=["problem-name"],
            fom_type=FomType.TIME,
        )


Final Tests
-----------

To complete this tutorial we will test the application.

.. tutorial-workspace-create:: tutorial-workspace
   :single:
   :dir:

Now, add an experiment. We'll need to provide values for the number of nodes
and ranks. For HPL, the number of ranks should equal PxQ.

.. code-block:: console

  $ ramble workspace manage experiments hpl --overwrite \
      -V package_manager=spack \
      -v n_nodes=1 \
      -v n_ranks=4 \
      -v Ps=2 \
      -v Qs=2 \
      -v Ns=2000 \
      -v NBs=256

.. tutorial-execute:: tutorial-workspace
   :single:
   :concretize:
   :package-manager: none
   :dry-run-cmds: ls -la tutorial-workspace/experiments/hpl/standard/generated/; cat tutorial-workspace/experiments/hpl/standard/generated/HPL.dat; cat tutorial-workspace/experiments/hpl/standard/generated/execute_experiment
   :results-text: This creates a ``results.latest.txt`` file containing the extracted ``Time`` and ``GFlops`` figures of merit from your HPL application definition.

   The ``ramble workspace concretize`` command pulls the default software
   environment and package specs from the HPL application definition into the
   workspace configuration.

Summary and Final Cleanup
-------------------------

At this stage, you have now created a new application definition to build and
run the HPL benchmark.

.. tutorial-workspace-cleanup:: tutorial-workspace
   :dir:

.. tutorial-repo-cleanup::

The application definition you have now matches some of the basic functionality
from Ramble's HPL implementation. You should now be able to compare your
definition with the one seen by using
``ramble edit --type base_applications -N builtin hpl``.
