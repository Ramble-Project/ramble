.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _Mirrors_tutorial:

=======
Mirrors
=======

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
     -   <etc>        ^(short list of software prerequisistes for intel-mpi)

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
     -   <etc>        ^(short list of software prerequisistes for intel-mpi)

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
        │   └── berkeley-db-18.1.40.tar.gz -> ../_source-cache/archive/0c/0cecb2ef0c67b166de93732769abdeba0555086d51de1090df325e18ee8da9c8.tar.gz
        ├── bison
        │   └── bison-3.8.2.tar.gz -> ../_source-cache/archive/06/06c9e13bdf7eb24d4ceb6b59205a4f67c2c7e7213119644430fe82fbd14a0abb.tar.gz
        ├── bzip2
        │   └── bzip2-1.0.8.tar.gz -> ../_source-cache/archive/ab/ab5a03176ee106d3f0fa90e381da478ddae405918153cca248e682cd0c4a2269.tar.gz
        ├── ca-certificates-mozilla
        │   └── ca-certificates-mozilla-2023-05-30 -> ../_source-cache/archive/5f/5fadcae90aa4ae041150f8e2d26c37d980522cdb49f923fc1e1b5eb8d74e71ad
        ├── c-blosc
        │   └── c-blosc-1.21.4.tar.gz -> ../_source-cache/archive/e7/e72bd03827b8564bbb3dc3ea0d0e689b4863871ce3861d946f2efd7a186ecf3e.tar.gz
        ├── cmake
        │   └── cmake-3.26.3.tar.gz -> ../_source-cache/archive/bb/bbd8d39217509d163cb544a40d6428ac666ddc83e22905d3e52c925781f0f659.tar.gz
        ├── cpio
        │   └── cpio-2.14.tar.gz -> ../_source-cache/archive/14/145a340fd9d55f0b84779a44a12d5f79d77c99663967f8cfa168d7905ca52454.tar.gz
        ├── curl
        │   └── curl-8.1.2.tar.bz2 -> ../_source-cache/archive/b5/b54974d32fd610acace92e3df1f643144015ac65847f0a041fdc17db6f43f243.tar.bz2
        ├── diffutils
        │   └── diffutils-3.9.tar.xz -> ../_source-cache/archive/d8/d80d3be90a201868de83d78dad3413ad88160cc53bcc36eb9eaf7c20dbf023f1.tar.xz
        ├── findutils
        │   └── findutils-4.9.0.tar.xz -> ../_source-cache/archive/a2/a2bfb8c09d436770edc59f50fa483e785b161a3b7b9d547573cb08065fd462fe.tar.xz
        ├── gdbm
        │   └── gdbm-1.23.tar.gz -> ../_source-cache/archive/74/74b1081d21fff13ae4bd7c16e5d6e504a4c26f7cde1dca0d963a484174bbcacd.tar.gz
        ├── gettext
        │   └── gettext-0.21.1.tar.xz -> ../_source-cache/archive/50/50dbc8f39797950aa2c98e939947c527e5ac9ebd2c1b99dd7b06ba33a6767ae6.tar.xz
        ├── gmake
        │   ├── gmake-4.4.1.tar.gz -> ../_source-cache/archive/dd/dd16fb1d67bfab79a72f5e8390735c49e3e8e70b4945a15ab1f81ddb78658fb3.tar.gz
        │   ├── make-4.2.1-glob-fix-2.patch-fe5b60d -> ../_source-cache/archive/fe/fe5b60d091c33f169740df8cb718bf4259f84528b42435194ffe0dd5b79cd125
        │   └── make-4.2.1-glob-fix-3.patch-ca60bd9 -> ../_source-cache/archive/ca/ca60bd9c1a1b35bc0dc58b6a4a19d5c2651f7a94a4b22b2c5ea001a1ca7a8a7f
        ├── hdf5
        │   ├── gcc-8.patch-57cee5f -> ../_source-cache/archive/57/57cee5ff1992b4098eda079815c36fc2da9b10e00a9056df054f2384c4fc7523
        │   └── hdf5-1.14.1-2.tar.gz -> ../_source-cache/archive/cb/cbe93f275d5231df28ced9549253793e40cd2b555e3d288df09d7b89a9967b07.tar.gz
        ├── intel-mpi
        │   └── intel-mpi-2018.4.274.tgz -> ../_source-cache/archive/a1/a1114b3eb4149c2f108964b83cad02150d619e50032059d119ac4ffc9d5dd8e0.tgz
        ├── jasper
        │   └── jasper-3.0.3.tar.gz -> ../_source-cache/archive/1b/1b324f7746681f6d24d06fcf163cf3b8ae7ac320adc776c3d611b2b62c31b65f.tar.gz
        ├── krb5
        │   └── krb5-1.20.1.tar.gz -> ../_source-cache/archive/70/704aed49b19eb5a7178b34b2873620ec299db08752d6a8574f95d41879ab8851.tar.gz
        ├── libaec
        │   └── libaec-1.0.6.tar.gz -> ../_source-cache/archive/ab/abab8c237d85c982bb4d6bde9b03c1f3d611dcacbd58bca55afac2496d61d4be.tar.gz
        ├── libiconv
        │   └── libiconv-1.17.tar.gz -> ../_source-cache/archive/8f/8f74213b56238c85a50a5329f77e06198771e70dd9a739779f4c02f65d971313.tar.gz
        ├── libjpeg-turbo
        │   └── libjpeg-turbo-2.1.5.tar.gz -> ../_source-cache/archive/25/254f3642b04e309fee775123133c6464181addc150499561020312ec61c1bf7c.tar.gz
        ├── libpng
        │   └── libpng-1.6.39.tar.xz -> ../_source-cache/archive/1f/1f4696ce70b4ee5f85f1e1623dc1229b210029fa4b7aee573df3e2ba7b036937.tar.xz
        ├── libsigsegv
        │   └── libsigsegv-2.14.tar.gz -> ../_source-cache/archive/cd/cdac3941803364cf81a908499beb79c200ead60b6b5b40cad124fd1e06caa295.tar.gz
        ├── libtirpc
        │   └── libtirpc-1.2.6.tar.bz2 -> ../_source-cache/archive/42/4278e9a5181d5af9cd7885322fdecebc444f9a3da87c526e7d47f7a12a37d1cc.tar.bz2
        ├── libtool
        │   └── libtool-2.4.7.tar.gz -> ../_source-cache/archive/04/04e96c2404ea70c590c546eba4202a4e12722c640016c12b9b2f1ce3d481e9a8.tar.gz
        ├── libxml2
        │   ├── c9925454fd384a17c8c03d358c6778a552e9287b.patch-3e06d42 -> ../_source-cache/archive/3e/3e06d42596b105839648070a5921157fe284b932289ffdbfa304ddc3457e5637
        │   ├── libxml2-2.10.3.tar.xz -> ../_source-cache/archive/5d/5d2cc3d78bec3dbe212a9d7fa629ada25a7da928af432c93060ff5c17ee28a9c.tar.xz
        │   └── xmlts-2.10.3.tar.gz -> ../_source-cache/archive/96/96151685cec997e1f9f3387e3626d61e6284d4d6e66e0e440c209286c03e9cc7.tar.gz
        ├── lz4
        │   └── lz4-1.9.4.tar.gz -> ../_source-cache/archive/0b/0b0e3aa07c8c063ddf40b082bdf7e37a1562bda40a0ff5272957f3e987e0e54b.tar.gz
        ├── m4
        │   ├── m4-1.4.18-glibc-change-work-around.patch-fc9b616 -> ../_source-cache/archive/fc/fc9b61654a3ba1a8d6cd78ce087e7c96366c290bc8d2c299f09828d793b853c8
        │   └── m4-1.4.19.tar.gz -> ../_source-cache/archive/3b/3be4a26d825ffdfda52a56fc43246456989a3630093cced3fbddf4771ee58a70.tar.gz
        ├── nasm
        │   ├── 0001-Remove-invalid-pure_func-qualifiers.patch-ac9f315 -> ../_source-cache/archive/ac/ac9f315d204afa6b99ceefa1fe46d4eed2b8a23c7315d32d33c0f378d930e950
        │   └── nasm-2.15.05.tar.gz -> ../_source-cache/archive/91/9182a118244b058651c576baa9d0366ee05983c4d4ae1d9ddd3236a9f2304997.tar.gz
        ├── ncurses
        │   └── ncurses-6.4.tar.gz -> ../_source-cache/archive/69/6931283d9ac87c5073f30b6290c4c75f21632bb4fc3603ac8100812bed248159.tar.gz
        ├── netcdf-c
        │   ├── 00a722b253bae186bba403d0f92ff1eba719591f.patch?full_index=1-25b83de -> ../_source-cache/archive/25/25b83de1e081f020efa9e21c94c595220849f78c125ad43d8015631d453dfcb9
        │   ├── 1505.patch?full_index=1-495b3e5 -> ../_source-cache/archive/49/495b3e5beb7f074625bcec2ca76aebd339e42719e9c5ccbedbdcc4ffb81a7450
        │   ├── 1508.patch?full_index=1-19e7f31 -> ../_source-cache/archive/19/19e7f31b96536928621b1c29bb6d1a57bcb7aa672cea8719acf9ac934cdd2a3e
        │   ├── 386e2695286702156eba27ab7c68816efb192230.patch?full_index=1-cb928a9 -> ../_source-cache/archive/cb/cb928a91f87c1615a0788f95b95d7a2e3df91dc16822f8b8a34a85d4e926c0de
        │   ├── a7ea050ebb3c412a99cc352859d5176a9b5ef986.patch?full_index=1-38d34de -> ../_source-cache/archive/38/38d34de38bad99737d3308867071196f20a3fb39b936de7bfcfbc85eb0c7ef54
        │   ├── cfe6231aa6b018062b443cbe2fd9073f15283344.patch?full_index=1-4e10547 -> ../_source-cache/archive/4e/4e105472de95a1bb5d8b0b910d6935ce9152777d4fe18b678b58347fa0122abc
        │   ├── f8904d5a1d89420dde0f9d2c0e051ba08d08e086.patch?full_index=1-0161eb8 -> ../_source-cache/archive/01/0161eb870fdfaf61be9d70132c9447a537320342366362e76b8460c823bf95ca
        │   └── netcdf-c-4.9.2.tar.gz -> ../_source-cache/archive/bc/bc104d101278c68b303359b3dc4192f81592ae8640f1aee486921138f7f88cb7.tar.gz
        ├── netcdf-fortran
        │   └── netcdf-fortran-4.6.0.tar.gz -> ../_source-cache/archive/19/198bff6534cc85a121adc9e12f1c4bc53406c403bda331775a1291509e7b2f23.tar.gz
        ├── openssl
        │   ├── f9e578e720bb35228948564192adbe3bc503d5fb.patch?full_index=1-3fdcf2d -> ../_source-cache/archive/3f/3fdcf2d1e47c34f3a012f23306322c5a35cad55b180c9b6fb34537b55884645c
        │   └── openssl-3.1.1.tar.gz -> ../_source-cache/archive/b3/b3aa61334233b852b63ddb048df181177c2c659eb9d4376008118f9c08d07674.tar.gz
        ├── perl
        │   ├── 0001-Fix-Time-Local-tests.patch-8cf4302 -> ../_source-cache/archive/8c/8cf4302ca8b480c60ccdcaa29ec53d9d50a71d4baf469ac8c6fca00ca31e58a2
        │   ├── cpanm-5.38.0.tar.gz -> ../_source-cache/archive/9d/9da50e155df72bce55cb69f51f1dbb4b62d23740fb99f6178bb27f22ebdf8a46.tar.gz
        │   ├── perl5162-timelocal-y2020.patch-3bbd7d6 -> ../_source-cache/archive/3b/3bbd7d6f9933d80b9571533867b444c6f8f5a1ba0575bfba1fba4db9d885a71a
        │   ├── perl-5.26.1-guard_old_libcrypt_fix.patch-0eac10e -> ../_source-cache/archive/0e/0eac10ed90aeb0459ad8851f88081d439a4e41978e586ec743069e8b059370ac
        │   └── perl-5.38.0.tar.gz -> ../_source-cache/archive/21/213ef58089d2f2c972ea353517dc60ec3656f050dcc027666e118b508423e517.tar.gz
        ├── pigz
        │   └── pigz-2.7.tar.gz -> ../_source-cache/archive/d2/d2045087dae5e9482158f1f1c0f21c7d3de6f7cdc7cc5848bdabda544e69aa58.tar.gz
        ├── pkgconf
        │   └── pkgconf-1.9.5.tar.xz -> ../_source-cache/archive/1a/1ac1656debb27497563036f7bffc281490f83f9b8457c0d60bcfb638fb6b6171.tar.xz
        ├── readline
        │   ├── readline63-001-1a79bbb -> ../_source-cache/archive/1a/1a79bbb6eaee750e0d6f7f3d059b30a45fc54e8e388a8e05e9c3ae598590146f
        │   ├── readline63-002-39e304c -> ../_source-cache/archive/39/39e304c7a526888f9e112e733848215736fb7b9d540729b9e31f3347b7a1e0a5
        │   ├── readline63-003-ec41bdd -> ../_source-cache/archive/ec/ec41bdd8b00fd884e847708513df41d51b1243cecb680189e31b7173d01ca52f
        │   ├── readline63-004-4547b90 -> ../_source-cache/archive/45/4547b906fb2570866c21887807de5dee19838a60a1afb66385b272155e4355cc
        │   ├── readline63-005-877788f -> ../_source-cache/archive/87/877788f9228d1a9907a4bcfe3d6dd0439c08d728949458b41208d9bf9060274b
        │   ├── readline63-006-5c237ab -> ../_source-cache/archive/5c/5c237ab3c6c97c23cf52b2a118adc265b7fb411b57c93a5f7c221d50fafbe556
        │   ├── readline63-007-4d79b5a -> ../_source-cache/archive/4d/4d79b5a2adec3c2e8114cbd3d63c1771f7c6cf64035368624903d257014f5bea
        │   ├── readline63-008-3bc093c -> ../_source-cache/archive/3b/3bc093cf526ceac23eb80256b0ec87fa1735540d659742107b6284d635c43787
        │   ├── readline70-001-9ac1b3a -> ../_source-cache/archive/9a/9ac1b3ac2ec7b1bf0709af047f2d7d2a34ccde353684e57c6b47ebca77d7a376
        │   ├── readline70-002-8747c92 -> ../_source-cache/archive/87/8747c92c35d5db32eae99af66f17b384abaca961653e185677f9c9a571ed2d58
        │   ├── readline70-003-9e43aa9 -> ../_source-cache/archive/9e/9e43aa93378c7e9f7001d8174b1beb948deefa6799b6f581673f465b7d9d4780
        │   ├── readline70-004-f925683 -> ../_source-cache/archive/f9/f925683429f20973c552bff6702c74c58c2a38ff6e5cf305a8e847119c5a6b64
        │   ├── readline70-005-ca159c8 -> ../_source-cache/archive/ca/ca159c83706541c6bbe39129a33d63bbd76ac594303f67e4d35678711c51b753
        │   ├── readline80-001-d8e5e98 -> ../_source-cache/archive/d8/d8e5e98933cf5756f862243c0601cb69d3667bb33f2c7b751fe4e40b2c3fd069
        │   ├── readline80-002-36b0feb -> ../_source-cache/archive/36/36b0febff1e560091ae7476026921f31b6d1dd4c918dcb7b741aa2dad1aec8f7
        │   ├── readline80-003-94ddb22 -> ../_source-cache/archive/94/94ddb2210b71eb5389c7756865d60e343666dfb722c85892f8226b26bb3eeaef
        │   ├── readline80-004-b1aa3d2 -> ../_source-cache/archive/b1/b1aa3d2a40eee2dea9708229740742e649c32bb8db13535ea78f8ac15377394c
        │   ├── readline81-001-682a465 -> ../_source-cache/archive/68/682a465a68633650565c43d59f0b8cdf149c13a874682d3c20cb4af6709b9144
        │   ├── readline81-002-e55be05 -> ../_source-cache/archive/e5/e55be055a68cb0719b0ccb5edc9a74edcc1d1f689e8a501525b3bc5ebad325dc
        │   ├── readline82-001-bbf97f1 -> ../_source-cache/archive/bb/bbf97f1ec40a929edab5aa81998c1e2ef435436c597754916e6a5868f273aff7
        │   └── readline-8.2.tar.gz -> ../_source-cache/archive/3f/3feb7171f16a84ee82ca18a36d7b9be109a52c04f492a053331d7d1095007c35.tar.gz
        ├── snappy
        │   └── snappy-1.1.10.tar.gz -> ../_source-cache/archive/49/49d831bffcc5f3d01482340fe5af59852ca2fe76c3e05df0e67203ebbe0f1d90.tar.gz
        ├── _source-cache
        │   └── archive
        │       ├── 01
        │       │   └── 0161eb870fdfaf61be9d70132c9447a537320342366362e76b8460c823bf95ca
        │       ├── 03
        │       │   └── 03d908cf5768cfe6b7ad588c921c6ed21acabfb2b79b788d1330453507647aed.tar.gz
        │       ├── 04
        │       │   └── 04e96c2404ea70c590c546eba4202a4e12722c640016c12b9b2f1ce3d481e9a8.tar.gz
        │       ├── 06
        │       │   └── 06c9e13bdf7eb24d4ceb6b59205a4f67c2c7e7213119644430fe82fbd14a0abb.tar.gz
        │       ├── 0b
        │       │   └── 0b0e3aa07c8c063ddf40b082bdf7e37a1562bda40a0ff5272957f3e987e0e54b.tar.gz
        │       ├── 0c
        │       │   └── 0cecb2ef0c67b166de93732769abdeba0555086d51de1090df325e18ee8da9c8.tar.gz
        │       ├── 0e
        │       │   └── 0eac10ed90aeb0459ad8851f88081d439a4e41978e586ec743069e8b059370ac
        │       ├── 14
        │       │   └── 145a340fd9d55f0b84779a44a12d5f79d77c99663967f8cfa168d7905ca52454.tar.gz
        │       ├── 19
        │       │   ├── 198bff6534cc85a121adc9e12f1c4bc53406c403bda331775a1291509e7b2f23.tar.gz
        │       │   └── 19e7f31b96536928621b1c29bb6d1a57bcb7aa672cea8719acf9ac934cdd2a3e
        │       ├── 1a
        │       │   ├── 1a79bbb6eaee750e0d6f7f3d059b30a45fc54e8e388a8e05e9c3ae598590146f
        │       │   └── 1ac1656debb27497563036f7bffc281490f83f9b8457c0d60bcfb638fb6b6171.tar.xz
        │       ├── 1b
        │       │   └── 1b324f7746681f6d24d06fcf163cf3b8ae7ac320adc776c3d611b2b62c31b65f.tar.gz
        │       ├── 1c
        │       │   └── 1ce97f4fd09e440bdf00f67711b1c50439ac27595ea6796efbfb32e0b9a1f3e4
        │       ├── 1f
        │       │   └── 1f4696ce70b4ee5f85f1e1623dc1229b210029fa4b7aee573df3e2ba7b036937.tar.xz
        │       ├── 21
        │       │   └── 213ef58089d2f2c972ea353517dc60ec3656f050dcc027666e118b508423e517.tar.gz
        │       ├── 25
        │       │   ├── 254f3642b04e309fee775123133c6464181addc150499561020312ec61c1bf7c.tar.gz
        │       │   └── 25b83de1e081f020efa9e21c94c595220849f78c125ad43d8015631d453dfcb9
        │       ├── 27
        │       │   └── 27c7268f6c84b884d21e4afad0bab8554b06961cf4d6bfd7d0f5a457dcfdffb1
        │       ├── 33
        │       │   └── 333e111ed39f7452f904590b47b996812590b8818f1c51ad68407dc05a1b18b0
        │       ├── 36
        │       │   └── 36b0febff1e560091ae7476026921f31b6d1dd4c918dcb7b741aa2dad1aec8f7
        │       ├── 38
        │       │   └── 38d34de38bad99737d3308867071196f20a3fb39b936de7bfcfbc85eb0c7ef54
        │       ├── 39
        │       │   ├── 392615011adb7afeb0010152409a37b150f03dbde5b534503e9cd7363b742a19
        │       │   └── 39e304c7a526888f9e112e733848215736fb7b9d540729b9e31f3347b7a1e0a5
        │       ├── 3a
        │       │   └── 3a4e60fe56a450632140c48acbf14d22850c1d72835bf441e3f8514d6c617a9f
        │       ├── 3b
        │       │   ├── 3bbd7d6f9933d80b9571533867b444c6f8f5a1ba0575bfba1fba4db9d885a71a
        │       │   ├── 3bc093cf526ceac23eb80256b0ec87fa1735540d659742107b6284d635c43787
        │       │   └── 3be4a26d825ffdfda52a56fc43246456989a3630093cced3fbddf4771ee58a70.tar.gz
        │       ├── 3e
        │       │   └── 3e06d42596b105839648070a5921157fe284b932289ffdbfa304ddc3457e5637
        │       ├── 3f
        │       │   ├── 3fdcf2d1e47c34f3a012f23306322c5a35cad55b180c9b6fb34537b55884645c
        │       │   └── 3feb7171f16a84ee82ca18a36d7b9be109a52c04f492a053331d7d1095007c35.tar.gz
        │       ├── 42
        │       │   └── 4278e9a5181d5af9cd7885322fdecebc444f9a3da87c526e7d47f7a12a37d1cc.tar.bz2
        │       ├── 45
        │       │   └── 4547b906fb2570866c21887807de5dee19838a60a1afb66385b272155e4355cc
        │       ├── 49
        │       │   ├── 495b3e5beb7f074625bcec2ca76aebd339e42719e9c5ccbedbdcc4ffb81a7450
        │       │   └── 49d831bffcc5f3d01482340fe5af59852ca2fe76c3e05df0e67203ebbe0f1d90.tar.gz
        │       ├── 4d
        │       │   └── 4d79b5a2adec3c2e8114cbd3d63c1771f7c6cf64035368624903d257014f5bea
        │       ├── 4e
        │       │   └── 4e105472de95a1bb5d8b0b910d6935ce9152777d4fe18b678b58347fa0122abc
        │       ├── 50
        │       │   └── 50dbc8f39797950aa2c98e939947c527e5ac9ebd2c1b99dd7b06ba33a6767ae6.tar.xz
        │       ├── 57
        │       │   ├── 57c7a9b0d94dd41e4276b57b0a4a89d91303d36180c1068b9e3ab8f6149b18dd
        │       │   └── 57cee5ff1992b4098eda079815c36fc2da9b10e00a9056df054f2384c4fc7523
        │       ├── 5c
        │       │   └── 5c237ab3c6c97c23cf52b2a118adc265b7fb411b57c93a5f7c221d50fafbe556
        │       ├── 5d
        │       │   └── 5d2cc3d78bec3dbe212a9d7fa629ada25a7da928af432c93060ff5c17ee28a9c.tar.xz
        │       ├── 5f
        │       │   └── 5fadcae90aa4ae041150f8e2d26c37d980522cdb49f923fc1e1b5eb8d74e71ad
        │       ├── 60
        │       │   └── 60be2c504bd8f1fa6e424b1956495d7e7ced52a2ac94db5fd27f4b6bfc8f74f0.tar.gz
        │       ├── 68
        │       │   └── 682a465a68633650565c43d59f0b8cdf149c13a874682d3c20cb4af6709b9144
        │       ├── 69
        │       │   └── 6931283d9ac87c5073f30b6290c4c75f21632bb4fc3603ac8100812bed248159.tar.gz
        │       ├── 70
        │       │   └── 704aed49b19eb5a7178b34b2873620ec299db08752d6a8574f95d41879ab8851.tar.gz
        │       ├── 74
        │       │   └── 74b1081d21fff13ae4bd7c16e5d6e504a4c26f7cde1dca0d963a484174bbcacd.tar.gz
        │       ├── 7b
        │       │   └── 7be2968c67c2175cd40b57118d9732eda5fdb0828edaa25baf57cc289da1a9b8.tar.gz
        │       ├── 7e
        │       │   └── 7ee195e4ce4c9eac81920843b4d4d27254bec7b43e0b744f457858a9f156e621
        │       ├── 83
        │       │   └── 837a6a82f815c0905cf7ea4c4ef0112f36396fc8b2138028204000178a1befa5
        │       ├── 87
        │       │   ├── 8747c92c35d5db32eae99af66f17b384abaca961653e185677f9c9a571ed2d58
        │       │   └── 877788f9228d1a9907a4bcfe3d6dd0439c08d728949458b41208d9bf9060274b
        │       ├── 8c
        │       │   └── 8cf4302ca8b480c60ccdcaa29ec53d9d50a71d4baf469ac8c6fca00ca31e58a2
        │       ├── 8f
        │       │   └── 8f74213b56238c85a50a5329f77e06198771e70dd9a739779f4c02f65d971313.tar.gz
        │       ├── 91
        │       │   └── 9182a118244b058651c576baa9d0366ee05983c4d4ae1d9ddd3236a9f2304997.tar.gz
        │       ├── 94
        │       │   └── 94ddb2210b71eb5389c7756865d60e343666dfb722c85892f8226b26bb3eeaef
        │       ├── 96
        │       │   └── 96151685cec997e1f9f3387e3626d61e6284d4d6e66e0e440c209286c03e9cc7.tar.gz
        │       ├── 98
        │       │   └── 98e9c3d949d1b924e28e01eccb7deed865eefebf25c2f21c702e5cd5b63b85e1.tar.gz
        │       ├── 9a
        │       │   └── 9ac1b3ac2ec7b1bf0709af047f2d7d2a34ccde353684e57c6b47ebca77d7a376
        │       ├── 9d
        │       │   └── 9da50e155df72bce55cb69f51f1dbb4b62d23740fb99f6178bb27f22ebdf8a46.tar.gz
        │       ├── 9e
        │       │   └── 9e43aa93378c7e9f7001d8174b1beb948deefa6799b6f581673f465b7d9d4780
        │       ├── a1
        │       │   └── a1114b3eb4149c2f108964b83cad02150d619e50032059d119ac4ffc9d5dd8e0.tgz
        │       ├── a2
        │       │   └── a2bfb8c09d436770edc59f50fa483e785b161a3b7b9d547573cb08065fd462fe.tar.xz
        │       ├── ab
        │       │   ├── ab5a03176ee106d3f0fa90e381da478ddae405918153cca248e682cd0c4a2269.tar.gz
        │       │   └── abab8c237d85c982bb4d6bde9b03c1f3d611dcacbd58bca55afac2496d61d4be.tar.gz
        │       ├── ac
        │       │   └── ac9f315d204afa6b99ceefa1fe46d4eed2b8a23c7315d32d33c0f378d930e950
        │       ├── b1
        │       │   └── b1aa3d2a40eee2dea9708229740742e649c32bb8db13535ea78f8ac15377394c
        │       ├── b3
        │       │   ├── b3a24de97a8fdbc835b9833169501030b8977031bcb54b3b3ac13740f846ab30.tar.gz
        │       │   └── b3aa61334233b852b63ddb048df181177c2c659eb9d4376008118f9c08d07674.tar.gz
        │       ├── b4
        │       │   └── b4e7428ac6c2918beacc1b73f33e784ac520ef981d87e98285610b1bfa299d7b
        │       ├── b5
        │       │   └── b54974d32fd610acace92e3df1f643144015ac65847f0a041fdc17db6f43f243.tar.bz2
        │       ├── bb
        │       │   ├── bbd8d39217509d163cb544a40d6428ac666ddc83e22905d3e52c925781f0f659.tar.gz
        │       │   └── bbf97f1ec40a929edab5aa81998c1e2ef435436c597754916e6a5868f273aff7
        │       ├── bc
        │       │   └── bc104d101278c68b303359b3dc4192f81592ae8640f1aee486921138f7f88cb7.tar.gz
        │       ├── c5
        │       │   ├── c5162c23a132b377132924f8f1545313861c6cee5a627e9ebbdcf7b7b9d5726f
        │       │   └── c522c4733720df9a18237c06d8ab6199fa9674d78375b644aec7017cb38af9c5
        │       ├── ca
        │       │   ├── ca159c83706541c6bbe39129a33d63bbd76ac594303f67e4d35678711c51b753
        │       │   └── ca60bd9c1a1b35bc0dc58b6a4a19d5c2651f7a94a4b22b2c5ea001a1ca7a8a7f
        │       ├── cb
        │       │   ├── cb928a91f87c1615a0788f95b95d7a2e3df91dc16822f8b8a34a85d4e926c0de
        │       │   └── cbe93f275d5231df28ced9549253793e40cd2b555e3d288df09d7b89a9967b07.tar.gz
        │       ├── cd
        │       │   └── cdac3941803364cf81a908499beb79c200ead60b6b5b40cad124fd1e06caa295.tar.gz
        │       ├── d1
        │       │   └── d1b54b5c5432faed9791ffde813560e226896a68fc5933d066172bcf3b2eb8bd
        │       ├── d2
        │       │   ├── d2045087dae5e9482158f1f1c0f21c7d3de6f7cdc7cc5848bdabda544e69aa58.tar.gz
        │       │   └── d2358c930d5ab89e5965204dded499591b42a22d0a865e2149b8c0f1446fac34
        │       ├── d8
        │       │   ├── d80d3be90a201868de83d78dad3413ad88160cc53bcc36eb9eaf7c20dbf023f1.tar.xz
        │       │   └── d8e5e98933cf5756f862243c0601cb69d3667bb33f2c7b751fe4e40b2c3fd069
        │       ├── dd
        │       │   ├── dd16fb1d67bfab79a72f5e8390735c49e3e8e70b4945a15ab1f81ddb78658fb3.tar.gz
        │       │   └── dd172acb53867a68012f94c17389401b2f274a1aa5ae8f84cbfb8b7e383ea8d3.tar.bz2
        │       ├── e5
        │       │   └── e55be055a68cb0719b0ccb5edc9a74edcc1d1f689e8a501525b3bc5ebad325dc
        │       ├── e6
        │       │   └── e6c88ffc291c9d4bda4d6bedf3c9be89cb96ce7dc245163e251345221fa77216
        │       ├── e7
        │       │   └── e72bd03827b8564bbb3dc3ea0d0e689b4863871ce3861d946f2efd7a186ecf3e.tar.gz
        │       ├── ec
        │       │   └── ec41bdd8b00fd884e847708513df41d51b1243cecb680189e31b7173d01ca52f
        │       ├── f8
        │       │   ├── f8266916189ebbdfbad5c2c28ac00ed25f07be70f054d9830eb84ba84b3d03ef
        │       │   └── f82a18cf7334e0cbbfdf4ef3aa91ca26d4a372709f114ce0116b3fbb136ffac6
        │       ├── f9
        │       │   ├── f925683429f20973c552bff6702c74c58c2a38ff6e5cf305a8e847119c5a6b64
        │       │   └── f973bd33a7fd8af0002a9b8992216ffc04fdf2927917113e42e58f28b702dc14
        │       ├── fb
        │       │   └── fbacf0c81e62429df3e33bda4cee38756604f18e01d977338e23306a3e3b521e.tar.gz
        │       ├── fc
        │       │   └── fc9b61654a3ba1a8d6cd78ce087e7c96366c290bc8d2c299f09828d793b853c8
        │       └── fe
        │           └── fe5b60d091c33f169740df8cb718bf4259f84528b42435194ffe0dd5b79cd125
        ├── tar
        │   └── tar-1.34.tar.gz -> ../_source-cache/archive/03/03d908cf5768cfe6b7ad588c921c6ed21acabfb2b79b788d1330453507647aed.tar.gz
        ├── tcsh
        │   ├── tcsh-6.20.00-000-add-all-flags-for-gethost-build.patch-f826691 -> ../_source-cache/archive/f8/f8266916189ebbdfbad5c2c28ac00ed25f07be70f054d9830eb84ba84b3d03ef
        │   ├── tcsh-6.20.00-001-delay-arginp-interpreting.patch-57c7a9b -> ../_source-cache/archive/57/57c7a9b0d94dd41e4276b57b0a4a89d91303d36180c1068b9e3ab8f6149b18dd
        │   ├── tcsh-6.20.00-002-type-of-read-in-prompt-confirm.patch-837a6a8 -> ../_source-cache/archive/83/837a6a82f815c0905cf7ea4c4ef0112f36396fc8b2138028204000178a1befa5
        │   ├── tcsh-6.20.00-003-fix-out-of-bounds-read.patch-f973bd3 -> ../_source-cache/archive/f9/f973bd33a7fd8af0002a9b8992216ffc04fdf2927917113e42e58f28b702dc14
        │   ├── tcsh-6.20.00-004-do-not-use-old-pointer-tricks.patch-333e111 -> ../_source-cache/archive/33/333e111ed39f7452f904590b47b996812590b8818f1c51ad68407dc05a1b18b0
        │   ├── tcsh-6.20.00-005-reset-fixes-numbering.patch-d1b54b5 -> ../_source-cache/archive/d1/d1b54b5c5432faed9791ffde813560e226896a68fc5933d066172bcf3b2eb8bd
        │   ├── tcsh-6.20.00-006-cleanup-in-readme-files.patch-b4e7428 -> ../_source-cache/archive/b4/b4e7428ac6c2918beacc1b73f33e784ac520ef981d87e98285610b1bfa299d7b
        │   ├── tcsh-6.20.00-007-look-for-tgetent-in-libtinfo.patch-e6c88ff -> ../_source-cache/archive/e6/e6c88ffc291c9d4bda4d6bedf3c9be89cb96ce7dc245163e251345221fa77216
        │   ├── tcsh-6.20.00-008-guard-ascii-only-reversion.patch-7ee195e -> ../_source-cache/archive/7e/7ee195e4ce4c9eac81920843b4d4d27254bec7b43e0b744f457858a9f156e621
        │   ├── tcsh-6.20.00-009-fix-regexp-for-backlash-quoting-tests.patch-d2358c9 -> ../_source-cache/archive/d2/d2358c930d5ab89e5965204dded499591b42a22d0a865e2149b8c0f1446fac34
        │   ├── tcsh-6.20.00-manpage-memoryuse.patch-3a4e60f -> ../_source-cache/archive/3a/3a4e60fe56a450632140c48acbf14d22850c1d72835bf441e3f8514d6c617a9f
        │   ├── tcsh-6.22.02-avoid-gcc-to-fail.patch-3926150 -> ../_source-cache/archive/39/392615011adb7afeb0010152409a37b150f03dbde5b534503e9cd7363b742a19
        │   └── tcsh-6.24.00.tar.gz -> ../_source-cache/archive/60/60be2c504bd8f1fa6e424b1956495d7e7ced52a2ac94db5fd27f4b6bfc8f74f0.tar.gz
        ├── time
        │   └── time-1.9.tar.gz -> ../_source-cache/archive/fb/fbacf0c81e62429df3e33bda4cee38756604f18e01d977338e23306a3e3b521e.tar.gz
        ├── wrf
        │   ├── 238a7d219b7c8e285db28fe4f0c96ebe5068d91c.patch?full_index=1-27c7268 -> ../_source-cache/archive/27/27c7268f6c84b884d21e4afad0bab8554b06961cf4d6bfd7d0f5a457dcfdffb1
        │   ├── 4a084e03575da65f254917ef5d8eb39074abd3fc.patch-c522c47 -> ../_source-cache/archive/c5/c522c4733720df9a18237c06d8ab6199fa9674d78375b644aec7017cb38af9c5
        │   ├── 6087d9192f7f91967147e50f5bc8b9e49310cf98.patch-f82a18c -> ../_source-cache/archive/f8/f82a18cf7334e0cbbfdf4ef3aa91ca26d4a372709f114ce0116b3fbb136ffac6
        │   ├── 6502d5d9c15f5f9a652dec244cc12434af737c3c.patch?full_index=1-c5162c2 -> ../_source-cache/archive/c5/c5162c23a132b377132924f8f1545313861c6cee5a627e9ebbdcf7b7b9d5726f
        │   ├── 7c6fd575b7a8fe5715b07b38db160e606c302956.patch?full_index=1-1ce97f4 -> ../_source-cache/archive/1c/1ce97f4fd09e440bdf00f67711b1c50439ac27595ea6796efbfb32e0b9a1f3e4
        │   └── wrf-4.2.2.tar.gz -> ../_source-cache/archive/7b/7be2968c67c2175cd40b57118d9732eda5fdb0828edaa25baf57cc289da1a9b8.tar.gz
        ├── xz
        │   └── xz-5.4.1.tar.bz2 -> ../_source-cache/archive/dd/dd172acb53867a68012f94c17389401b2f274a1aa5ae8f84cbfb8b7e383ea8d3.tar.bz2
        ├── zlib
        │   └── zlib-1.2.13.tar.gz -> ../_source-cache/archive/b3/b3a24de97a8fdbc835b9833169501030b8977031bcb54b3b3ac13740f846ab30.tar.gz
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

**NOTE**: The ``--scope`` argument controls at what level Ramble is configured to use this mirror. The default scope
is ``user`` which places the config within the ``~/.ramble`` directory, and it only applies to the user that executed
this comment. Using ``--scope=site`` applies the config to the installation directory for Ramble, and all users that
use this same installation would have the config option applied to them.

To validate that the mirrors were installed correctly, try something like the following,

.. code-block:: console

    $ spack clean -a

    $ ramble clean -a

    $ ramble -d workspace setup --dry-run

and see if files are being retrieved from your mirrors instead of the internet.
