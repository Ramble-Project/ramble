.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _workspace:

================
Ramble Workspace
================

In Ramble, a workspace is a self contained directory representing a set of
experiments that should be executed. This document describes overall aspects of
workspaces, and how to use them.

-------------------
Creating Workspaces
-------------------

The ``ramble workspace create`` command can be used to create workspaces.

Workspaces are created with a standard structure, and some basic configuration
files that the user can modify to control the exact behavior of the experiments
within the workspace.

Ramble can create two types of workspaces:
  * anonymous workspaces
  * named workspaces

^^^^^^^^^^^^^^^
Named Workspace
^^^^^^^^^^^^^^^

By default, Ramble creates named workspaces, which are workspaces which Ramble
will manage. To create a named workspace, use:

.. code-block:: console

    $ ramble workspace create <name_of_workspace>

These workspaces are created by default in ``$ramble/var/ramble/workspaces``,
but that location can be changed. For example, the following command will
change the default location for creating workspaces to
``~/.ramble/workspaces``:

.. code-block:: console

    $ ramble config add 'config:workspace_dirs:~/.ramble/workspaces'

^^^^^^^^^^^^^^^^^^^
Anonymous Workspace
^^^^^^^^^^^^^^^^^^^

Anonymous workspaces are workspaces that Ramble will not manage and will live
in a specified directory. To create an anonymous workspace, use:

.. code-block:: console

    $ ramble workspace create -d <path_to_workspace>

.. _workspace-links:

^^^^^^^^^^^^^^^
Workspace Links
^^^^^^^^^^^^^^^

In order to save disk space, sometimes it can be useful to share internal
workspace directories across workspaces when they reuse aspects of each others
workflows. Ramble provides a way to create a new workspace where the inputs and
software directories are symbolic links to external directories (whether in a
workspace or not), to help minimize duplication of files across workspaces.

To use this, when creating a workspace you can use the ``--inputs-dir`` and
``--software-dir`` argument to provide paths for the source of these symbolic
links.

As an example:

.. code-block:: console

  $ ramble workspace create -d foo
  $ ramble workspace create -d bar --software-dir foo/software --inputs-dir foo/inputs

In the above example, two workspaces are created (``foo`` and ``bar``). The
workspace named ``bar`` has symbolic links for its ``software`` and ``inputs``
directories that link to the same named directories in the ``foo`` workspace.

Additionally, these directories do not need to be part of any workspace, and
could instead be external directories used to have a common storage location
for software environments and input files.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Omitting Boilerplate Comments
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, newly created workspaces include explanatory boilerplate comments
at the top of the generated ``ramble.yaml`` configuration file. To omit these
comments when creating a workspace, pass ``-n`` / ``--no-comments`` to
``ramble workspace create``:

.. code-block:: console

    $ ramble workspace create -n <name_of_workspace>

Alternatively, the ``include_workspace_comments`` configuration option can be
set to ``false`` to omit boilerplate comments in newly created workspaces by
default:

.. code-block:: console

    $ ramble config add 'config:include_workspace_comments:false'

.. _workspace-structure:

-------------------
Workspace Structure
-------------------

Ramble creates workspaces using the following structure by default:

.. code-block:: console

    $workspace
    | - configs/
    |   | - ramble.yaml
    |   | - execute_experiment.tpl
    |   | - auxiliary_software_files/
    | - shared/
    |   | - utilities/
    | - experiments/
    | - inputs/
    | - logs/
    | - software/


This various parts of this directory structure are defined as:
  * ``configs/``: Contain configuration for the workspace
  * ``configs/auxiliary_software_files``: Contain files used by the package managers
  * ``shared/utilities``: Contain ramble-generated workspace utilities
  * ``experiments/``: Contain experiments define by the workspace configuration
  * ``inputs``: Contain the inputs experiments in this workspace require
  * ``logs``: Contain some logging output from ramble
  * ``software``: Contain software environments an application's package manager creates

In the ``configs`` directory, the ``ramble.yaml`` file is the primary workspace
configuration file. The definition for this file is documented in the
:ref:`workspace config documentation<workspace-config>`

^^^^^^^^^^^^^^^^^^^^^^^
Editing Workspace Files
^^^^^^^^^^^^^^^^^^^^^^^

The ``ramble workspace edit`` command opens workspace files in your configured
editor. By default, it opens ``configs/ramble.yaml`` and all template
(``*.tpl``) files in the workspace.

You can also open specific configuration or auxiliary files using flags (which
can be combined):

  * ``-c`` / ``--config``: Open ``configs/ramble.yaml``
  * ``-t`` / ``--templates``: Open all ``configs/*.tpl`` template files
  * ``-l`` / ``--licenses``: Open ``configs/licenses.yaml``
  * ``--all-configs`` / ``--all``: Open all ``*.yaml`` and ``*.tpl`` files in ``configs/``
  * ``-r`` / ``--results``: Open the latest analysis result files (``results/results.latest.*``)
  * ``--tables``: Open the latest generated table files (``tables/*.latest.*``)
  * ``--logs``: Open the latest pipeline log files (``logs/*.latest.out``)
  * ``--software-files`` / ``--auxiliary-software-files``: Open files in ``configs/auxiliary_software_files/``
  * ``-i`` / ``--includes``: Open configuration files referenced in the ``include:`` section
  * ``-e`` / ``--experiments-script``: Open the root ``all_experiments`` script
  * ``-f <file>`` / ``--file <file>``: Open a specific file (supports workspace path variables such as ``{workspace_results}`` or ``$workspace_tables``)

^^^^^^^^^^^^^^^^^^^^^^^^
Workspace Template Files
^^^^^^^^^^^^^^^^^^^^^^^^

Every file with the ``.tpl`` extension is considered a template file in the
workspace. Every one of these are rendered into each experiment (with the
extension omitted).

Workflows can be constructed by chaining multiple of these template files
together. Ramble will define a variable within each experiment that will be the
name of the file (without the extenison) and the value will be the absolute
path to the rendered template.

As an example, if the file ``configs/execute_experiment.tpl`` exists, each
experiment will have a variable ``execute_experiment`` who's value is set to
something like:
``{workspace_root}/experiments/{application_name}/{workload_name}/{experiment_name}/execute_experiment``

Ramble supports arbitrary format template files. Variables can be referenced
within these files using the standard ``{`` and ``}`` syntax. Nested variable
expansion is possible by using repeated curly braces (i.e. ``{{foo}}`` will
evaluate ``{foo}``, and if this expands to ``bar`` then the result will be the
expansion of ``{bar}``).

**NOTE:** Some file formats require escaping curly braces to ensure their
format is correct. This happens frequently with JSON and YAML formatted
template files. For more information on escaping expansion characters, see
:ref:`ramble-escaped-variables` in the :ref:`workspace config
documentation<workspace-config>`


----------------------
Activating a Workspace
----------------------

Several Ramble commands require an activated workspace to function properly. A workspace can be activated in a few different ways:

.. code-block:: console

    $ ramble workspace activate <name_or_path>

will activate a workspace until it is deactivated, while

.. code-block:: console

    $ ramble -D <path_to_workspace workspace ...

    or

    $ ramble -w <workspace_name> workspace ...

will activate a workspace for the specific command.

To indicate the activated workspace, an option ``-p`` can be supplied to the ``activate`` command.
This updates the shell prompt to display the name of the currently active workspace.

.. code-block:: console

    $ ramble workspace activate -p <name_or_path>

Alternatively, a config ``enable_workspace_prompt`` exists, to allow controlling for this behavior
at the desired configuration granularity.

.. code-block:: console

    $ ramble config add 'config:enable_workspace_prompt:true'


A filter group can also be persistently activated for a workspace session by passing the ``-fg`` / ``--filter-group`` flag to the ``activate`` command:

.. code-block:: console

    $ ramble workspace activate <workspace_name> -fg small-scale

This will export the ``RAMBLE_ACTIVE_FILTER_GROUP`` environment variable to the shell, which will be used by subsequent workspace commands as the default filter group. Deactivating the workspace will unset this variable.


------------------------------
Printing Workspace Information
------------------------------
In order to see an overview of what experiments a workspace contains, one can
use:

.. code-block:: console

    $ ramble workspace info

To get basic information, and:

.. code-block:: console

    $ ramble workspace info -vvv

To get more detailed information, including which variables are defined and
where they come from.

------------------------
Concretizing a Workspace
------------------------

The software definitions in a workspace need to be concretized before the
workspace can be set up. To have Ramble pull software definitions from the
application definition files, one can use:

.. code-block:: console

    $ ramble workspace concretize

To remove any unused software definitions from the workspace configuration,
as well as unused experiment templates, one can use:

.. code-block:: console

    $ ramble workspace concretize --simplify

Note: This command will also remove comments within the edited section
of the workspace config file.

.. _workspace-manage:

------------------------
Workspace Manage
------------------------

In addition to helping you automatically define software for your applications,
ramble also offers a CLI interface to more finely control various aspects of
the workspace configuration -- ``ramble workspace manage``.

Specifically, this command can help you populate values in the ramble.yaml for:
  * Experiment definitions
  * Software definitions
  * Workspace includes
  * Workspace modifiers

These can be combined over multiple invocations to express very powerful
experiment configurations. The options are extensive, and are thus not covered
here but users are invited to experiment and pass the ``-h`` for more
information.

Advanced options like ``--workflow-manager`` and ``--package-manager`` can be
used to set key variable variants to quickly invoke additional core ramble
features, and the intended user for this feature is both automation and human
users alike.

Below are some examples that can be used as starting points:

.. code-block:: console

    $ ramble workspace manage experiments <application_name>

This command populates a workspace with default experiments and workloads for a
given application, including setting default values for key variables. When
paired with ``ramble workspace concretize`` it can quickly allow a user to
generate a functioning workspace.

In cases where a user wants to specify software that is different to the output
of concretize, the following gives a easy and repeatable way to fine tune the
selection. If for example you wanted to update a specific package to a
different version, one may type:

.. code-block:: console

    $ ramble workspace manage software --pkg gcc14 --package-spec gcc@14.2.0 --overwrite

This would update the software package definition names ``gcc14`` to have a new package spec.

Modifiers can be applied to various levels of a workspace configuration. To
simplify the workflow around adding and removing modifiers from a set of
experiments, users can use the following commands:

.. code-block:: console

  $ ramble workspace manage modifiers --list
  $ ramble workspace manage modifiers --add -s workspace -n lscpu
  $ ramble workspace manage modifiers --remove -s workspace -n lscpu

When performing the ``--remove`` action, the scope argument (``-s``) on these
commands has a robust syntax that allows users to specify various scopes within
a workspace (``workspace``, ``application``, ``application:workload``, or
``application:workload:experiment``).

Finally, ``ramble workspace manage includes`` can be used to quickly and easy
add includes when using a hierarchical workspace.

Filter groups can also be managed via the CLI using the ``ramble workspace manage filter-groups`` subcommand:

.. code-block:: console

  $ ramble workspace manage filter-groups add -n small-scale --where "{n_nodes} < 4"
  $ ramble workspace manage filter-groups remove -n small-scale
  $ ramble workspace manage filter-groups list
  $ ramble workspace manage filter-groups blame

These commands allow adding, removing, listing, and viewing the sources (blame) of filter groups within the active workspace.


---------------------
Workspace Deployments
---------------------

A deployment is one mechanism of transferring a configured workspace from one
location to another. Ramble provides commands to handle creating (and pushing)
a deployment from a local workspace to a remote location, or pulling a
deployment from a remote location into a local workspace.

A deployment is a directory that contains the necessary artifacts required to
recreate the experiments in the workspace on a separate machine. Deployments
copy the workspace configuration file, along with creating an object
repository, containing the application, modifier, and any package manager files
needed for the experiments (that might not be upstreamed).  This section
describes the commands that can be used to use deployments.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Preparing a Workspace Deployment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Once a workspace is configured, it can be used to create a deployment.  To prepare a
deployment, one can use:

.. code-block:: console

  $ ramble deployment push

This will populate a directory named ``deployments``, where the default is the
name of the workspace.

The name of the created deployment can be controlled using:

.. code-block:: console

  $ ramble deployment push -d <deployment_name>

Additionally, Ramble can create a tar of the deployment using:

.. code-block:: console

  $ ramble deployment push -t

And upload the deployment to a remote URL using:

.. code-block:: console

  $ ramble deployment push -u <remote_url>

The arguments ``-d`` and ``-u`` can refer to ``variables`` defined within any
configuration scope that is workspace level or lower (i.e. site, user, etc..).
This does not include variables defined within the ``applications``
configuration section.

For example:

.. code-block:: yaml

  ramble:
    variables:
      test_name: test
      test_url: gs://test-bucket/test-dir
    ...

When paired with

.. code-block:: console

  $ ramble deployment push -d '{test_name}' -u '{test_url}'

Would attempt to create a deployment in ``gs://test-bucket/test-dir/test``.


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Pulling a Workspace Deployment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To apply a deployment to an existing workspace, the ``pull`` sub-command can be used. For example:

.. code-block:: console

  $ ramble deployment pull -p file://path/to/deployment

Will overwrite the contents of the currently active workspace with the contents
from the deployment contained in ``file://path/to/deployment``.

It is important to note that this command is destructive, and there is no way
to revert a workspace back to its state prior to the pull action.

.. _workspace-setup:

----------------------
Setting up a Workspace
----------------------

To make Ramble fully configure a workspace, one can use:

.. code-block:: console

    $ ramble workspace setup

This can be an expensive process, and Ramble will:
  * Install software
  * Download input files
  * Create all experiment directives and content

To perform a light-weight test version of this, one can use:

.. code-block:: console

    $ ramble workspace setup --dry-run

Which will create experiments, but it won't download anything, or execute any
package manager commands.

^^^^^^^^^^^^^^^
Phase Selection
^^^^^^^^^^^^^^^

Some workflows would benefit from more fine-grained control of the phases that
are executed by Ramble. A good example is that sometimes one only wants to run
the ``make_experiments`` phase of a workspace instead of all of the phases.

The ``ramble workspace setup`` command has a ``--phases`` argument, which can
take phase filters which will be used to down-select the phases which should be
executed.

As an example:

.. code-block:: console

    $ ramble workspace setup --phases make_experiments

Would execute only the ``make_experiments`` phase of all experiments that have
this phase.

The ``--phases`` argument supports wildcard matching, i.e.:

.. code-block:: console

    $ ramble workspace setup --phases *_experiments

Would execute all phases that have then ``_experiments`` suffix.

.. _filter-experiments:

^^^^^^^^^^^^^^^^^^^^^
Filtering Experiments
^^^^^^^^^^^^^^^^^^^^^

Several of the workspace commands support filtering the experiments they should
act on. This can be performed using the ``--where`` argument for inclusive
filtering, the ``--exclude-where`` argument for exclusive filtering, or the
``--filter-tags`` argument to filter based on experiment tags. These arguments
take a string representing a logical expression, which can use variables the
experiment would define. The expression can use any of the logical and mathematical
operators supported by Ramble variables (see :ref:`ramble-supported-functions`).
If the logical expression evaluates to true, the experiment will be included or
excluded for action (respectively).

As an example:

.. code-block:: console

   $ ramble workspace setup --where '"{n_ranks}" < 500'

Will only setup experiments that have less than 500 ranks, and:

.. code-block:: console

    $ ramble workspace setup --exclude-where '"{application_name}" == "hostname"'

Will exclude all experiments from the ``hostname`` application.

To filter by tags, see the following example:

.. code-block:: console

  $ ramble workspace setup --filter-tags my-tag

Will only setup experiments that have the ``my-tag`` on them.

The commands that accept these filters are:

.. code-block:: console

    $ ramble workspace analyze
    $ ramble workspace archive
    $ ramble workspace mirror
    $ ramble workspace setup
    $ ramble on

**NOTE:** The exclusive filter takes precedence over the inclusive filter.


^^^^^^^^^^^^^^^^^^^^^
Software Environments
^^^^^^^^^^^^^^^^^^^^^

When setting up a workspace, Ramble will install software defined by the
workspace configuration file. Ramble uses external package mangers to perform
the installation and generate software environments for each experiment.

As an example, if the applications and workspace configuration file provide a
configuration for Spack, Ramble will generate
`Spack environments <https://spack.readthedocs.io/en/latest/environments.html>`_.

By default, Ramble uses the following format for creating a spack environment file:

.. code-block:: yaml

    spack:
      concretizer:
        unify: true
      specs:
      - packages
      - for
      - environment
      include:
      - files
      - from
      - auxiliary_software_files

In addition to generating a ``spack.yaml`` file for each software environment,
Ramble will expand unique copies of each file contained in the
``configs/auxiliary_software_files`` directory into every software environment
it generates.

These can be used to modify the behavior of Spack environments generated by Ramble.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Workspace Inventory and Hash
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Setting up a workspace will create inventory files that can be used to identify
which aspects of experiments or workspaces change between different
invocations.

Most of an experiment's inventory is defined regardless of if ``--dry-run`` is
used or not. The notable exception to this is the ``software`` hashes. The file
that is hashed depends on if the underlying software environment is fully
defined or not.

As an example, if Spack applications are used, ``--dry-run`` only creates (and
hashes) ``spack.yaml`` files, which are not concrete. When ``--dry-run`` is not
used, Ramble will cause Spack to generate ``spack.lock`` files, which will then
be hashed, giving better information about if the file changes or not.

The hash for a workspace is written to ``$workspace/workspace_hash.sha256``,
and the inventories are written to
``$workspace/experiments/<application>/<workload>/<experiment>/ramble_inventory.json``
and ``$workspace/ramble_inventory.json``.

Below is an example of a workspace inventory:

.. code-block:: json

    {
      "experiments": [
        {
          "name": "gromacs.water_bare.test",
          "digest": "3f4a333db9f76a06826e4c3775bb4384af8904f474a74a4b1eb61f4d6d02939c",
          "contents": {
            "attributes": [
              {
                "name": "variables",
                "digest": "0fc2c3b848885404201f5435389e9028460ea68affd6c78149b7a8c7e925d004"
              },
              {
                "name": "modifiers",
                "digest": "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"
              },
              {
                "name": "chained_experiments",
                "digest": "74234e98afe7498fb5daf1f36ac2d78acc339464f950703b8c019892f982b90b"
              },
              {
                "name": "internals",
                "digest": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a"
              },
              {
                "name": "env_vars",
                "digest": "035f0c03572706ee6da6f0f74614717b201aabe0f7671fc094478d1a97e5dcc4"
              },
              {
                "name": "template",
                "digest": "fcbcf165908dd18a9e49f7ff27810176db8e9f63b4352213741664245224f8aa"
              }
            ],
            "inputs": [
              {
                "name": "water_bare",
                "digest": "2fb58b2b856117515c75be9141450cca14642be2a1afe53baae3c85d06935caf"
              }
            ],
            "software": [
              {
                "name": "software/gromacs.water_bare",
                "digest": "12f222f06ca05cb6fca37368452b3adedf316bc224ea447e894c87d672333cca"
              }
            ],
            "templates": [
              {
                "name": "execute_experiment",
                "digest": "ea07af55040670edaf23e2bfd0b537c8ed70280a3616021a5203bdf65e08a4c6"
              }
            ]
          }
        }
      ],
      "versions": [
        {
          "name": "ramble",
          "version": "0.3.0 (9947210de68fb42dfd843ed1ab982aba0145e9d3)",
          "digest": "02f5fbbfe0a9fe38b99186619e7fb1d11e6398c637a24bb972fffa66e82bf3fe"
        },
        {
          "name": "spack",
          "version": "0.20.0.dev0 (3c3a4c75776ece43c95df46908dea026ac2a9276)",
          "digest": "21fb90b4cffd46b2257469da346cdf0bcf7070227290262b000bb6c467acfc44"
        }
      ]
    }

As mentioned above, the only part that varies when switching ``--dry-run`` on
and off are the digest values for each software attribute. The hash of the
workspace is the hash of its inventory file. All hashes are sha256.

---------------------
Executing a Workspace
---------------------

Once a workspace is set up, the experiments inside it can be executed using:

.. code-block:: console

    $ ramble on

^^^^^^^^^^^^^^^^
Custom Executors
^^^^^^^^^^^^^^^^

When executing the experiments within a workspace, an executor is used.
Executors are arbitrary strings which are expanded for each experiment, and
then executed directly.

The default executor is ``'{batch_submit}'`` as this is the variable that is
used to generate the execution command in the ``all_experiments`` script.

Custom executors can be defined using the ``--executor`` argument to ``ramble
on`` as in:

.. code-block:: console

    $ ramble on --executor 'echo "{experiment_namespace}"'

This executor will echo each experiment's fully qualified namespace instead of
executing the experiment.

The value of the executor will be expanded for each experiment, and executed
independently. Custom executors can be used to have more control over what
actions to perform with an experiment.

---------------------
Analyzing a Workspace
---------------------

After the experiments inside a workspace are complete, they can be analyzed using:

.. code-block:: console

    $ ramble workspace analyze

By default this creates text output describing the figures of merit from the
workspace's experiments. The format can be controlled using:

.. code-block:: console

    $ ramble workspace analyze --format text json yaml

With supported formats being ``text``, ``json``, or ``yaml``.

Ramble also include an experimental capability to uplodate figures of merit
into a back-end data base. Currently BigQuery is the only supported back-end,
however more back-ends can be implemented. To upload data, one can use:

.. code-block:: console

    $ ramble workspace analyze --upload

This will automatically read the upload configuration from the ``upload`` block
of :ref:`Ramble's config file<config-yaml>`.

---------------------
Archiving a Workspace
---------------------

A workspace can be archived to either:
  * Share with other people
  * Keep for future reproduction

In order to archive a workspace, one can use:

.. code-block:: console

    $ ramble workspace archive

An archive can be automatically uploaded to a mirror using:

.. code-block:: console

    $ ramble workspace archive -t --upload-url <mirror_url>

When Ramble creates an archive, it will collect the following files:
  * All files in ``$workspace/configs``
  * Generated files for each software environment. (i.e. Each ``spack.yaml`` for spack environments)

For each experiment, the following are collected:
  * Every rendered template (created from a ``$workspace/configs/*.tpl`` file)
  * Every file a success criteria or figure of merit would be extract from
  * Every file that matches an ``archive_pattern`` from the ``application.py``
