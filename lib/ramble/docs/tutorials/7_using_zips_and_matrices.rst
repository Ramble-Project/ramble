.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _zips_and_matrices_tutorial:

==============================
7) Zips and Matrices
==============================

In this tutorial, you will learn how to generate a more comprehensive set of
experiments using zips and matrices. For this tutorial we will use
`WRF <https://www.mmm.ucar.edu/models/wrf>`_, a free and open-source
application for atmospheric research and operational forecasting applications.

This tutorial builds off of concepts introduced in previous tutorials. Please
make sure you review those before starting with this tutorial's content.

**NOTE:** In this tutorial, you will encounter expected errors when copying and
pasting the commands. This is to help show situations you might run into when
trying to use Ramble on your own, and illustrate how you might fix them.

Create a Workspace
------------------

To begin with, you need a workspace to configure the experiments. This can be
created with the following command:

.. code-block:: console

    $ ramble workspace create zips_and_matrices_wrf


Activate the Workspace
----------------------

Several of Ramble's commands require an activated workspace to function
properly. Activate the newly created workspace using the following command:
(NOTE: you only need to run this if you do not currently have the workspace
active).

.. code-block:: console

    $ ramble workspace activate zips_and_matrices_wrf

.. include:: shared/wrf_scaling_workspace.rst

We will now expand this to perform more experiments using the zip
(:ref:`zips documentation<ramble-explicit-zips>`) and matrix
(:ref:`matrix documentation<ramble-matrix-logic>`)
functionality in Ramble.

Construct Platforms Zip
-----------------------

For the purposes of this tutorial, you will construct a zip representing
multiple platforms. The platforms will differ by their value of the
``processes_per_node`` variable.

Zips are explicit groupings of variables, that are combined into a larger
variable set. A zip is defined by a list of variable definitions, where each
individual variable is a list / vector variable and all variables are the same
length. As an example, imagine we had the following variable / zip definitions:

.. code-block:: YAML

    variables:
      platform: ['platform1', 'platform2']
      processes_per_node: ['16', '20']
    zips:
      platform_config:
      - platform
      - processes_per_node

The result of this is that ``platform_config`` would be a list of length 2. The
first index would contain ``(platform1, 16)`` and the second index would contain
``(platform2, 20)``. Using this, we can group an arbitrary number of variables
into a single name.

For the purposes of this tutorial, we'll assume your system has 4 total cores,
allowing us to use the platform definitions from the above YAML.

Edit your workspace configuration file to include the ``platform_config`` from
the above section. The result should look like the following:


.. literalinclude:: ../../../../examples/tutorial_7_base_config.yaml
   :language: YAML

Define an Experiment Matrix
---------------------------

At this point, your workspace should have a single zip along with one other
list variable, ``n_nodes``. This configuration will not work properly for two reasons.

The first is that neither the zip ( ``platform_config`` ), nor ``n_nodes`` are
unconsumed. Unconsumed zips and variables are zipped together to attempt to
create a set of experiments. In this case, ``n_nodes`` is a different length
than ``platform_config``, and Ramble will refuse to zip them. Running:

.. code-block:: console

    $ ramble workspace info

might give the following error messages:

.. code-block:: console

    ==> Error: Length mismatch in vector variables in experiment scaling_{n_nodes}
        Variable n_nodes has length 2
        Variable platform has length 3
        Variable processes_per_node has length 3

This error message identifies that the ``platform_config`` zip was unzipped
(since it is not consumed) and the length of the resulting variables are
different.

To fix this issue, you must define an experiment matrix to consume the
variables. An experiment matrix is defined within an experiment inside the
``ramble.yaml`` configuration file. In this case, your goal is to execute the
``n_nodes`` scaling study on each of the two platforms. So, you are looking to
create a set of experiments from the cross product of ``platform_config`` and
``n_nodes``. A matrix definition consists of a list of variable or zip names,
which are crossed with each other to create a final set of experiments. As an
example:

.. code-block:: YAML

    matrix:
    - platform_config
    - n_nodes

Would result in 4 experiments. Adding this to your workspace configuration, you
should have the following in your ``ramble.yaml``:

.. literalinclude:: ../../../../examples/tutorial_7_matrix_config.yaml
   :language: YAML

At this stage, running:

.. code-block:: console

    $ ramble workspace info

should give the following error message:

.. code-block:: console

    ==> Warning: Two experiments are defined with the name wrf@4.2.CONUS_12km.scaling_1
    ==> Warning:   -> Collision Origin: Within the same YAML experiment block: 'scaling_{n_nodes}' (Matrix/Vector Expansion)
    ==> Warning: Variables unique to previously defined experiment:
    ==> Warning:   - experiment_index
    ==> Warning: Variable differences between experiment definitions:
    ==> Warning:   - processes_per_node: {'previous': 16, 'new': 20}
    ==> Warning:   - platform: {'previous': 'platform1', 'new': 'platform2'}
    ==> Warning: 
    ==> Warning: ==> SUGGESTION: Your experiment name template does not distinguish between parallel expansions.
    ==> Warning:     To make the namespaces unique, add one or more of these differing matrix variables into your 'scaling_{n_nodes}' template:
    ==> Warning:     -> {processes_per_node}
    ==> Warning:     -> {platform}
    ==> Warning: 
    ==> Error: Experiment wrf@4.2.CONUS_12km.scaling_1 is not unique.


This is because your experiment name template is not unique across the values
of ``platform_config``. To remedy this issue, you can update the experiment
name template to include either ``platform`` or ``processes_per_node``. The
below example will use ``platform``, but you are free to experiment with these.
Your final configuration file should look something like:


.. literalinclude:: ../../../../examples/tutorial_7_final_config.yaml
   :language: YAML

.. include:: shared/wrf_execute.rst

**NOTE** Some of these experiments can take a while to execute. Experiments can
be filtered using the :ref:`--where <filter-experiments>` option to execute the
higher scale experiments if desired. To do this, try:

.. code-block:: console

    $ ramble workspace setup --where '{n_ranks} >= 20'
    $ ramble on
    $ ramble workspace analyze --where '{n_ranks} >= 20'

Ramble also supports generating machine readable results in YAML or JSON format.
To use this functionality, use the ``--formats`` option on
``ramble workspace analyze``.

Clean the Worksapce
-------------------

Once you are finished with the tutorial content, make sure you deactivate the workspace using:

.. code-block:: console

    $ ramble workspace deactivate

Additionally, you can remove the workspace and all of its content with:

.. code-block:: console

    $ ramble workspace remove zips_and_matrices_wrf
