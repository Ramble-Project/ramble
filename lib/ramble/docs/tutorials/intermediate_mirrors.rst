.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _Mirrors_tutorial:

========================
Source and Input Mirrors
========================

This tutorial will provide a simple example demonstrating the creation
and use of :ref:`Ramble mirrors<mirror-config>`.

----------------
Mirror creation:
----------------
To start off with, let's set up a workspace with a basic experiment in it.
The experiment doesn't have to be very sophisticated, but it does need to
specify the application you want to mirror, and any application workloads
(with sha256 sums) that you want to have mirrored.

For the purpose of this demonstration, let's assume that you're using
a named workspace, and the application you want to mirror is ``wrf``.
We will call the workspace ``wrf_mirror_test``.

.. code-block:: console

    $ ramble workspace create wrf_mirror_test

    ==> Created workspace in wrf_mirror_test
    ==> You can activate this workspace with:
    ==>   ramble workspace activate wrf_mirror_test

    $ ramble workspace activate wrf_mirror_test

    $ ramble workspace edit -c

(The workspace's ramble.yaml file opens up in your favorite editor)

Write the following configuration into the file, save, and exit:

.. code-block:: yaml

    ramble:
      variants:
        package_manager: spack
      env_vars:
        set:
          OMP_NUM_THREADS: '{n_threads}'
      variables:
        mpi_command: mpirun -n {n_ranks}
        batch_submit: '{execute_experiment}'
        processes_per_node: 1
      applications:
        wrf@4.2:
          variables:
            app_workloads: [CONUS_2p5km, CONUS_12km]
          workloads:
            '{app_workloads}':
              experiments:
                single_node_{workload_name}_{n_nodes}_{processes_per_node}:
                  variables:
                    n_nodes: 1
                    processes_per_node: 30
      software:
        packages: {}
        environments: {}

Run ``ramble workspace concretize`` to fill in the software section. The result
will look something like this:

.. code-block:: yaml

    ramble:
      variants:
        package_manager: spack
      env_vars:
        set:
          OMP_NUM_THREADS: '{n_threads}'
      variables:
        mpi_command: mpirun -n {n_ranks}
        batch_submit: '{execute_experiment}'
        processes_per_node: 1
      applications:
        wrf@4.2:
          variables:
            app_workloads: [CONUS_2p5km, CONUS_12km]
          workloads:
            '{app_workloads}':
              experiments:
                single_node_{workload_name}_{n_nodes}_{processes_per_node}:
                  variables:
                    n_nodes: 1
                    processes_per_node: 30
      software:
        packages:
          gcc14:
            pkg_spec: gcc@14.2.0
          intel-mpi:
            pkg_spec: intel-oneapi-mpi@2021.17.2
          wrfv4-{application::wrf::version}:
            pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real
              nesting=basic ~chem ~pnetcdf
            compiler: gcc14
        environments:
          wrf@4.2:
            packages:
            - intel-mpi
            - wrfv4-{application::wrf::version}

Edit the file again (using ``ramble workspace edit -c``) if you need to
change compiler or mpi versions. Since we will be using this workspace only
for mirror creation, you don't need to be particular about the compiler version,
so use whatever compiler is already installed on your local system.

Then run the command ``ramble workspace mirror -d $HOME/wrf_mirror``. Warning,
it may take a long time to run, due to the time required to download input and
source files, which gives an example of why you would want to create
this mirror in the first place.

.. code-block:: console

    $ ramble workspace mirror -d $HOME/wrf_mirror

    ==>     Executing phase mirror_inputs
    ==>     Executing phase software_create_env
    ==> Concretized intel-oneapi-mpi@2021.17.2%gcc@<gcc-version>
     -   <hash>   intel-oneapi-mpi@2021.17.2%gcc@<version>_etc.
     -   <etc>        ^(short list of software prerequisites for intel-mpi)

    ==> Concretized wrf@4.2%gcc@<version> <wrf options>
     -   (long list of software prerequisites for wrf@4.2)

    ==>     Executing phase mirror_software
    ==>     Executing phase mirror_inputs
    ==>     Executing phase software_create_env
    ==> Created environment in <workspace_dirs path>/wrf_mirror_test/software/wrf@4.2.CONUS_12km
    ==> You can activate this environment with:
    ==>   spack env activate <workspace_dirs path>/wrf_mirror_test/software/wrf@4.2.CONUS_12km
    ==> Concretized wrf@4.2%gcc@<version> <wrf options>
     -   (long list of software prerequisites for wrf@4.2)

    ==> Concretized intel-oneapi-mpi@2021.17.2%gcc@<gcc-version>
     -   <hash>   intel-oneapi-mpi@2021.17.2%gcc@<version>_etc.
     -   <etc>        ^(short list of software prerequisites for intel-mpi)

    ==>     Executing phase mirror_software
    ==> Successfully updated spack software in $HOME/wrf_mirror
      Archive stats:
        44   already present
        44   added
        0    failed to fetch.
    ==> Successfully updated inputs in $HOME/wrf_mirror
      Archive stats:
        1    already present
        1    added
        0    failed to fetch.

The resulting structure of ``$HOME/wrf_mirror`` looks like

.. code-block:: console

    $ tree $HOME/wrf_mirror/
    
    /home/user/wrf_mirror/
    ├── inputs
    │   ├── _input-cache
    │   │   └── archive
    │   │       ├── 6a
    │   │       │   └── 6a0e87e3401efddc50539e71e5437fd7a5af9228b64cd4837e739737c3706fc3.tar.gz
    │   │       └── dc
    │   │           └── dcae9965d1873c1c1e34e21ad653179783302b9a13528ac10fab092b998578f6.tar.gz
    │   └── wrf
    │       ├── v42_bench_conus12km.tar.gz
    │       └── v42_bench_conus2.5km.tar.gz
    └── software
        ├── berkeley-db
        │   └── berkeley-db-18.1.40.tar.gz -> ../_source-cache/archive/0c/0cecb2ef0c67b166de93732769abdeba0555086d51de1090df325e18ee8da9c8.tar.gz
        ├── bison
        │   └── bison-3.8.2.tar.gz -> ../_source-cache/archive/06/06c9e13bdf7eb24d4ceb6b59205a4f67c2c7e7213119644430fe82fbd14a0abb.tar.gz
        ├── ...
        ├── hdf5
        │   ├── gcc-8.patch-57cee5f -> ../_source-cache/archive/57/57cee5ff1992b4098eda079815c36fc2da9b10e00a9056df054f2384c4fc7523
        │   └── hdf5-1.14.1-2.tar.gz -> ../_source-cache/archive/cb/cbe93f275d5231df28ced9549253793e40cd2b555e3d288df09d7b89a9967b07.tar.gz
        ├── intel-mpi
        │   └── intel-mpi-2018.4.274.tgz -> ../_source-cache/archive/a1/a1114b3eb4149c2f108964b83cad02150d619e50032059d119ac4ffc9d5dd8e0.tgz
        ├── ...
        ├── _source-cache
        │   └── archive
        │       ├── 01
        │       │   └── 0161eb870fdfaf61be9d70132c9447a537320342366362e76b8460c823bf95ca
        │       ├── 03
        │       │   └── 03d908cf5768cfe6b7ad588c921c6ed21acabfb2b79b788d1330453507647aed.tar.gz
        │       ├── ...
        │       └── fe
        │           └── fe5b60d091c33f169740df8cb718bf4259f84528b42435194ffe0dd5b79cd125
        ├── ...
        ├── wrf
        │   ├── ...
        │   └── wrf-4.2.2.tar.gz -> ../_source-cache/archive/7b/7be2968c67c2175cd40b57118d9732eda5fdb0828edaa25baf57cc289da1a9b8.tar.gz
        └── zstd
            └── zstd-1.5.5.tar.gz -> ../_source-cache/archive/98/98e9c3d949d1b924e28e01eccb7deed865eefebf25c2f21c702e5cd5b63b85e1.tar.gz

    133 directories, 204 files


-----------
Mirror use:
-----------
Once a mirror has been created locally, follow the directions in :ref:`Mirror use<using-created-mirrors>` to use
the ``inputs`` and ``software`` directories as Ramble input and Spack software mirrors, respectively.

For example, using the  mirror directories we created above,

.. code-block:: console

    $ ramble mirror add --scope=site ramble_mirror $HOME/wrf_mirror/inputs

    $ spack mirror add spack_mirror $HOME/wrf_mirror/software

.. note::
   The ``--scope`` argument controls at what level Ramble is configured to use this mirror. The default scope
   is ``user`` which places the config within the ``~/.ramble`` directory, and it only applies to the user that executed
   this command. Using ``--scope=site`` applies the config to the installation directory for Ramble, and all users that
   use this same installation would have the config option applied to them.

To validate that the mirrors were installed correctly, try something like the following,

.. code-block:: console

    $ spack clean -a

    $ ramble clean -a

    $ ramble -d workspace setup --dry-run

and see if files are being retrieved from your mirrors instead of the internet.
