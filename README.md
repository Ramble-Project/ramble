Ramble is a multi-platform experimentation framework that increases exploration
productivity and improves reproducibility. Ramble is capable of driving
software installation, acquiring input files, configuring experiments, and
extracting results.
It works on Linux, macOS, and many supercomputers.

Ramble can be used to configure a variety of experiments for applications.
These can include anything from:
 - Scientific parameter sweeps
 - Performance focused scaling studies
 - Compiler flag sweeps

To install ramble and configure your experiment workspace, make sure you have
Python, and Ramble’s dependencies are installed as per the dependency section
below.
Then:

    git clone -c feature.manyFiles=true https://github.com/Ramble-Project/ramble.git
    python3 -m venv ramble/env
    . ramble/env/bin/activate
    pip install -r ramble/requirements.txt
    ./ramble/bin/ramble workspace create -d test_workspace -c ramble/examples/basic_hostname_config.yaml

Alternatively, you can also use `uv` ([link to uv installation](https://docs.astral.sh/uv/getting-started/installation/#installing-uv)) to install Ramble:

    git clone -c feature.manyFiles=true https://github.com/Ramble-Project/ramble.git
    uv venv # or uv venv --python <python_version> for using specific Python version
    . .venv/bin/activate
    uv pip install -r ramble/requirements.txt
    ramble/bin/ramble workspace create -d test_workspace -c ramble/examples/basic_hostname_config.yaml

Dependencies
------------

Ramble’s python dependencies can be installed using the included requirements.txt file.

e.g.

    pip install -r requirements.txt

We recommend Python >= 3.7 for Ramble, but a best effort attempt is made to
support Python 3.6 as it is used by older operating systems.
Specifically, you might need to update `pip` and downgrade `protobuf` when
using Python 3.6.

Outside of these requirements, Ramble requires package managers to be
configured if they will be used as part of the experiments Ramble creates.

Although package manager support is not required to use Ramble, some
experiments are more easily accomplished by allowing Ramble to drive the
package manager execution. To allow this, package managers generally need to be
installed indepednently from Ramble. For more information on this, see
[Ramble's supported package managers](https://ramble.readthedocs.io/en/latest/package_managers.html).

Documentation
----------------

Ramble’s documentation can be viewed at
[https://ramble.readthedocs.io/](https://ramble.readthedocs.io/).

For help with Ramble’s commands, run `ramble help` or `ramble help --all`.

For more information on concepts in Ramble, see Ramble’s
[Getting Started](./lib/ramble/docs/getting_started.rst) guide.

Example configuration files are also contained in the
[examples](./examples) directory.

Community
------------------------

Ramble is an open source project.  Questions, discussion, and
contributions are welcome. Contributions can be anything from new
packages to bugfixes, documentation, or even new core features.

Resources:

* [**Github Discussions**](https://github.com/Ramble-Project/ramble/discussions): not just for discussions, also Q&A.

Contributing
------------------------
When developing features for Ramble, it can be helpful to install the
development requirements instead of the user requirements:

e.g.

    pip install -r requirements-dev.txt

Ramble's CI tests use a pinned set of dependencies. These can be installed
using:

    pip install -r requirements-pinned.txt

Contributing to Ramble is relatively easy.  Just send us a
[pull request](https://help.github.com/articles/using-pull-requests/).
When you send your request, make ``develop`` the destination branch on the
[Ramble repository](https://github.com/Ramble-Project/ramble).

Your PR must pass Ramble's unit tests and documentation tests, and must be
[PEP 8](https://www.python.org/dev/peps/pep-0008/) compliant.  We enforce
these guidelines with our CI process.

These tests can be run locally through test runners in the share/ramble/qa/
directory. Alternatively, [pre-commit](https://pre-commit.com/#install) can be
used to manage our git hooks. To install the hooks, simply run:
- pre-commit install

 For additional requirements about contributing, see our
 [Contribution Guide](.github/CONTRIBUTING.md).


Ramble's `develop` branch has the latest contributions. Pull requests
should target `develop`, and users who want the latest package versions,
features, etc. can use `develop`.

Releases
--------

Each Ramble release series also has a corresponding branch, e.g.
`releases/v0.1` has `0.1.x` versions of Ramble, and `releases/v0.2` has
`0.2.x` versions. We backport important bug fixes to these branches but
we do not advance the application definitions or make other changes that would
change the way experiments Ramble would create within a release branch.
So, you can base your Ramble deployment on a release branch subsequent updates
can be considered non-breaking.

The latest release is always available with the `releases/latest` tag.

Code of Conduct
------------------------

Please note that Ramble has a
[**Code of Conduct**](.github/CODE_OF_CONDUCT.md). By participating in
the Ramble community, you agree to abide by its rules.

Authors
----------------
Many thanks go to Ramble's [contributors](https://github.com/Ramble-Project/ramble/graphs/contributors).

Ramble was created by Doug Jacobsen, dwjacobsen@google.com.

License
----------------

This software is distributed under the terms of both the MIT license and the
Apache License (Version 2.0).

See LICENSE for details.

SPDX-License-Identifier: (Apache-2.0 OR MIT)
