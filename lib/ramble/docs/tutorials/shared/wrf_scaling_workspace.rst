.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

Configure Experiment Definitions
--------------------------------

To being with, you need to configure the workspace. The workspace's root
location can be seen under the ``Location`` output of:

.. code-block:: console

    $ ramble workspace info

Alternatively, the files can be edited directly with:

.. code-block:: console

    $ ramble workspace edit

Within the ``ramble.yaml`` file, write the following contents, which is the
final configuration from a previous tutorial.

**NOTE**: This workspace utilizes the ``spack`` package
manager. As a result, it requires either that you
manually installed ``spack`` and it is available in
your path, or it will bootstrap a spack installation
for you in the workspace's ``shared/`` directory.
Modifications to the ``package_manager`` variant will
change this behavior.


.. literalinclude:: /../../../examples/wrf_scaling_config.yaml
   :language: YAML

The above configuration will execute 2 experiments, comprising a basic scaling
study on 2 different sets of nodes. This is primarily defined by the use of
vector experiments, which are documented in the :ref:`vector
logic<ramble-vector-logic>` portion of the workspace configuration file
documentation. Vector experiments were also introduced in the :ref:`vector and
matrix tutorial <vector_and_matrix_tutorial>`.

