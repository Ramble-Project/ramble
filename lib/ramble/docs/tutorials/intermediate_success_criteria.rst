.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _success-criteria_tutorial:

================
Success Criteria
================

.. tutorial-header:: success_criteria

In this tutorial, you will learn how to use success criteria to validate experiments.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

Create a Workspace
------------------

.. tutorial-workspace-create:: success
   :separate-activate:

Configure Experiment Definitions
--------------------------------

To begin with, you need to configure the workspace. Within the ``ramble.yaml``
file, write the following contents, which represents the scaling study
configuration from previous tutorials:

.. tutorial-snippet:: success_criteria base.yaml

Success Criteria
----------------

Ramble provides you with the ability to define success criteria within an
application's ``application.py`` file, or within the ``success_criteria``
configuration scope (which can also be defined in a workspace's ``ramble.yaml``
configuration file). There are three supported types of success criteria,
including:

 #. Regular Expression String Matching
 #. Figure of Merit Logic Based
 #. Arbitrary Python Based

This tutorial will focus on the first two of these, as the third can only be
defined within the ``application.py`` file.

For more in-depth documentation about success criteria, see
:ref:`success-criteria`.

Regular Expression String Matching
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most common success criteria is regular expression based string
matching. These can be defined within either the ``application.py`` or the
``success_criteria`` configuration scope. Several ``application.py`` files
already define this type of success criteria in order to make it easier for
users to be sure their experiments completed successfully.

.. tutorial-app-template::
   :wrf: log_desc=outputs the time each timestep takes. To begin with, you will define a new success criteria within your workspace configuration file that validates some timing data is present in the output of an experiment. In the experiment output, the timing data is prefixed with the string ``Timing for main``.;sc_name=timing-present;sc_match=Timing for main.*;sc_file=rsl.out.base
   :gromacs: log_desc=writes detailed simulation logs to ``md.log``. To begin with, you will define a new success criteria within your workspace configuration file that validates the simulation completed successfully by matching the completion string in the log file.;sc_name=mdrun-finished;sc_match=Finished mdrun.*;sc_file=md.log
   :hpl: log_desc=outputs test validation results. To begin with, you will define a new success criteria within your workspace configuration file that validates the benchmark passed by matching the completion string ``PASSED`` in ``HPL.out``.;sc_name=passed;sc_match=.*PASSED.*;sc_file=HPL.out

   When {app_upper} runs, it {log_desc}

   This success criteria might look like the following:

   .. code-block:: YAML

       success_criteria:
       - name: '{sc_name}'
         mode: 'string'
         match: '{sc_match}'
         file: '{experiment_run_dir}/{sc_file}'

   Edit your workspace configuration file with:

   .. code-block:: console

       $ ramble workspace edit

   And add the example block within the ``{app_spec}`` application block. The resulting
   configuration file might look like the following:

   .. literalinclude:: /_generated/snippets/success_criteria_{app}_regex_criteria.yaml
      :language: YAML

   Placing the success criteria definition here applies it to all of the
   experiments defined within the ``{app_spec}`` application.

Figure of Merit Logic Based
~~~~~~~~~~~~~~~~~~~~~~~~~~~

In addition to string matching, Ramble allows you to define figure of merit
based success criteria. These success criteria can be defined as equations that
include placeholders for figures of merit the application will generate.

.. tutorial-app-template::
   :wrf: sc_desc=have at least 50 timesteps;sc_name=correct-timesteps;sc_fom=Number of timesteps;sc_formula=>= 50;scale_fom=Average Timestep Time;scale_val=1.0;scale_op=<=;scale_div=/
   :gromacs: sc_desc=complete within an expected wallclock threshold (e.g., at most 300 seconds);sc_name=max-walltime;sc_fom=Wall Time;sc_formula=<= 300;scale_fom=Wall Time;scale_val=100.0;scale_op=<=;scale_div=/
   :hpl: sc_desc=achieve an expected performance threshold (e.g., at least 1.0 GFLOP/s);sc_name=min-gflops;sc_fom=GFlops;sc_formula=>= 1.0;scale_fom=GFlops;scale_val=10.0;scale_op=>=;scale_div=*

   In this portion of the tutorial, you will define a new success criteria that
   ensures the experiments {sc_desc} to be considered
   successful. The figure of merit definition for this might look like the following:

   .. code-block:: YAML

       success_criteria:
       - name: '{sc_name}'
         mode: 'fom_comparison'
         fom_name: '{sc_fom}'
         formula: '{value} {sc_formula}'

   Edit your workspace configuration using:

   .. code-block:: console

       $ ramble workspace edit

   And add the success criteria within the ``{workload}`` workload definition. The
   resulting configuration file might look like the following:

   .. literalinclude:: /_generated/snippets/success_criteria_{app}_fom_criteria.yaml
      :language: YAML

   This new success criteria will apply to all experiments within the
   ``{workload}`` workload.

   It is important to note that the ``formula`` attribute of the success criteria
   definition can refer to other variables. As an example, one of the figures of
   merit output by the ``{app_spec}`` application definition is
   ``{scale_fom}``. If you had a single node value for this figure of
   merit and expected this to scale linearly you could define a success criteria
   as follows:

   .. code-block:: YAML

       variables:
         single_node_value: '{scale_val}'
       success_criteria:
       - name: 'valid-scaling'
         mode: 'fom_comparison'
         fom_name: '{scale_fom}'
         formula: '{value} {scale_op} {single_node_value} {scale_div} {n_nodes}'

   You won't test this success criteria in this tutorial, as the
   ``single_node_value`` might not be correct for your system, but feel free to
   explore using this after you perform experiments.

Execute Experiments
-------------------

.. tutorial-execute:: success
   :results-text: In ``results.latest.txt``, Ramble evaluates every configured success criterion (both application-defined and custom ``fom_comparison`` / ``string`` criteria) and prints ``SUCCESS`` (or ``FAILED``) for the status of each experiment.

   Running analyze in debug mode as:

   .. code-block:: console

       $ ramble -d workspace analyze

   will print significantly more output, including detailed debug messages showing
   where Ramble tests the configured success criteria.


Clean the Workspace
-------------------

.. tutorial-workspace-cleanup:: success

