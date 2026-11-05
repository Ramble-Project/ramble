.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _mirror-config:

==============
Ramble Mirrors
==============

The ``ramble workspace setup`` command can take a long time (or fail)
to run when an application's input files are large or internet access
to input file URLs is slow or restricted. Since the setup command runs
``spack`` to install software, downloading source tarballs or zip files
could have similar problems.

Another reason one might want to set up mirrors would be to ensure
reproducibility of results, since remote input and source files might change
without warning.

As a means to work around these issues on the software installation side,
Spack provides the ``mirror`` command, documented
[here](https://spack.readthedocs.io/en/latest/mirrors.html).

Ramble provides a similar ``mirror`` command, in order to find workload input files
locally first instead of in their default locations.

The ``ramble mirror`` set of commands largely follow the same form as ``spack mirror`` commands
(``add``, ``list``, ``set-url``, ``remove``, ``destroy``), with the exception of mirror creation.

Since Ramble input mirrors are intended to be used by applications, and applications are used
via Ramble workspaces, Ramble input mirrors are created via the ``ramble workspace mirror``
command, documented below. This command creates both the ramble input file mirror and the
spack source archive mirror, both of which are automatically restricted to mirror only those
input files and packages required for the ramble applications used in the workspace.

Once ramble input and spack software mirrors have been created, the user wishing to use those
will then run both ``spack mirror add SOFTWARE_MIRROR_URL`` and ``ramble mirror add INPUT_MIRROR_URL``.
The ``spack mirror`` commands, as described in the above documentation,
are also documented via ``spack mirror -h``. Likewise, short descriptions of
``ramble mirror`` commands can be found via ``ramble mirror -h``.

-----------------------
Creating Ramble Mirrors
-----------------------

In an activated named or anonymous workspace (specified via the ``ramble -D`` argument), write
a configuration for any applications and application experiment workloads you want to create
a mirror for.

Then run the following command to create input file and software mirrors:
.. code-block:: console

    $ ramble [-D WORKSPACE_DIR] workspace mirror -d MIRROR_PATH

Note that the ``-d MIRROR_PATH`` argument is not optional, even though ``ramble workspace mirror -h``
indicates that it is an optional argument. The path must be located on the local
filesystem.

----------------
Mirror Structure
----------------

``ramble workspace mirror`` creates ramble and spack mirrors with a structure
similar to the following, which uses a mirror of wrf as an example:

.. code-block:: console

    $workspace
    ├── inputs
    │   ├── _input-cache
    │   │   └── archive
    │   │       └── 19
    │   │           └── 1919a0e0499057c1a570619d069817022bae95b17cf1a52bdaa174f8e8d11508.tar.bz2
    │   └── wrf
    │       ├── bench_12km.tar.bz2
    │       └── bench_2.5km.tar.bz2
    └── software
        ├── _source-cache
        │   └── archive
        │       ├── 1c
        │       │   └── 1ce97f4fd09e440bdf00f67711b1c50439ac27595ea6796efbfb32e0b9a1f3e4
        │       ├── 27
        │       │   └── 27c7268f6c84b884d21e4afad0bab8554b06961cf4d6bfd7d0f5a457dcfdffb1
        │       ├── a0
        │       │   └── a04f5c425bedd262413ec88192a0f0896572cc38549de85ca120863c43df047a.tar.gz
        │       └── c5
        │           └── c5162c23a132b377132924f8f1545313861c6cee5a627e9ebbdcf7b7b9d5726f
        └── wrf
            ├── 238a7d219b7c8e285db28fe4f0c96ebe5068d91c.patch?full_index=1-27c7268 -> ../_source-cache/archive/27/27c7268f6c84b884d21e4afad0bab8554b06961cf4d6bfd7d0f5a457dcfdffb1
            ├── 6502d5d9c15f5f9a652dec244cc12434af737c3c.patch?full_index=1-c5162c2 -> ../_source-cache/archive/c5/c5162c23a132b377132924f8f1545313861c6cee5a627e9ebbdcf7b7b9d5726f
            ├── 7c6fd575b7a8fe5715b07b38db160e606c302956.patch?full_index=1-1ce97f4 -> ../_source-cache/archive/1c/1ce97f4fd09e440bdf00f67711b1c50439ac27595ea6796efbfb32e0b9a1f3e4
            └── wrf-3.9.1.1.tar.gz -> ../_source-cache/archive/a0/a04f5c425bedd262413ec88192a0f0896572cc38549de85ca120863c43df047a.tar.gz

The various parts of this directory structure are defined as:
  * ``inputs/``: Contains the Ramble input file mirror
  * ``software``: Contains the Spack software tarball/zipfile mirror
  * ``input/_input-cache/archive``: Contains files with names corresponding to the sha256 sums of the associated input files
  * ``software/_source-cache/archive``: Contains files with names corresponding to the sha256 sums of the associated source tarballs and patch files.

You can run ``ramble workspace mirror -d MIRROR_PATH``, using the same MIRROR_PATH, from several
different workspaces, in order to populate the local mirror with inputs and source files from
different applications. Alternatively, you can put multiple applications into the same workspace
configuration and create a multi-application mirror in a single run.

Once your mirrors are created locally, you can copy them to any fileserver close to the intended installation.

.. _using-created-mirrors:

---------------------
Using Created Mirrors
---------------------
If you have copied the directories into, for example ``URLBASE``, with
inputs and software subdirectories under ``URLBASE``, you could use them as follows:

.. code-block:: console

    $ ramble mirror add --scope=[site,user] URLBASE/inputs

    $ spack mirror add URLBASE/software
