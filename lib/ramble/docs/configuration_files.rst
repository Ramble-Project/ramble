.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _configuration-files:

===================
Configuration Files
===================

Ramble supports several different configuration files to control its behavior.
Some of these apply changes to Ramble's internals, while some modify the
experiments ramble generates.

This document describes each config section and its purpose. This document
does not cover the :ref:`workspace configuration file<workspace-config>`, which has its own document.

Ramble's configuration logic closely follows
`Spack's configuration logic <https://spack.readthedocs.io/en/latest/configuration.html>`_.

-----------------------
Configuration Sections:
-----------------------

Currently, Ramble supports the following configuration sections:

* :ref:`applications <application-config>`
* :ref:`base_application_repos <repos-config>`
* :ref:`base_class_repos <repos-config>`
* :ref:`base_modifier_repos <repos-config>`
* :ref:`base_package_manager_repos <repos-config>`
* :ref:`base_workflow_manager_repos <repos-config>`
* :ref:`config <config-yaml>`
* :ref:`env_vars <env-vars-config>`
* :ref:`formatted_executables <formatted-execs-config>`
* :ref:`internals <internals-config>`
* :ref:`licenses <licenses-config>`
* :ref:`mirrors <mirrors-config>`
* :ref:`modifier_repos <modifier-repos-config>`
* :ref:`modifiers <modifiers-config>`
* :ref:`package_manager_repos <repos-config>`
* :ref:`repos <repos-config>`
* :ref:`software <software-config>`
* :ref:`success_criteria <success-criteria-config>`
* :ref:`tables <tables-config>`
* :ref:`variables <variables-config>`
* :ref:`variants <variants-config>`
* :ref:`workflow_manager_repos <repos-config>`
* :ref:`zips <zips-config>`

Each of these config sections has a defined schema contained in
``lib/ramble/ramble/schemas``.


.. _configuration_scopes:

--------------------
Configuration Scopes
--------------------

Ramble provides several configuration scopes, which are used to denote
precedence of configuration options. In precedence order (from lowest to
highest) Ramble contains the following scopes:

1. **default**: Stored in ``$(prefix)/etc/ramble/defaults/``. These are the
   default settings provided with Ramble. Users should generally not modify these
   settings, and instead use a higher precedence configuration scope. These
   defaults will change from version to version of Ramble.
2. **system**: Store in ``/etc/ramble/``. These are Ramble settings for an
   entire machine. These settings are typically managed by a systems
   administrator, or something with root access on the machine. Settings defined
   in this scope override settings in the **default** scope.
3. **site**: Stored in ``$(prefix)/etc/ramble/``. Settings here only affect
   *this instance* of Ramble, and they override both the **default** and
   **system** scopes.
4. **user**: Stored in ``~/.ramble/``. Settings here only affect a specific
   user, and override **default**, **system**, and **site** scopes.
5. **custom**: Stored in a custom directory, specified by ``--config-scope``.
   If multiple scopes are listed on the command line, they are ordered from lowest
   to highest precedence. Settings here override all previously defined scoped.
6. **included files in workspace configuration file**: Paths referred to in the
   file from #7 above. For more information see the
   :ref:`documentation for including external configuration files<workspace_including_external_files>`.
7. **workspace configuration file**: Stored in
   ``$(workspace_root)/configs/ramble.yaml``. Configuration scopes defined within
   this config file override all previously defined configuration scopes.
8. **workspace configs dir**: Stored in ``$(workspace_root)/configs``
   generally as a ``<config_section>.yaml`` file (i.e. ``variables.yaml``). These
   settings apply to a specific workspace, and override all previous configuration
   scopes.
9. **command line**: Configuration options defined on the command line take
   precedence over all other scopes.
10. **application / workload / experiment scope sections**: Several
    configuration sections can be defined within the ``application``,
    ``workload``, and ``experiment`` portions of the ``applications``
    configuration section. These will override all other scopes. See the
    :ref:`application section documentation<application-config>` for more
    details.

Each configuration directory may contain several configuration files, such as
``config.yaml``, ``variables.yaml``, or ``modifiers.yaml``. When configurations
conflict, settings from higher-precedence (higher number in the above list)
scopes override lower-precedence settings.

In order to determine what settings will be used in a given context:

.. code-block:: console

    $ ramble config blame <section>

Will provide a listing of the configuration options within a given
configuration section, and where the setting is being derived from. Issuing
this command with an active workspace will include configuration sections
defined within a workspace scope.

Ramble's merging logic closely follows `Spack's configuration scope logic
<https://spack.readthedocs.io/en/latest/configuration.html#configuration-scopes>`_.

.. _application-config:

--------------------
Application Section:
--------------------

The application configuration section is used to define the experiments a
workspace should generate. The general format for this config section is as follows:

.. code-block:: yaml

    applications:
      <application_name>:
        [optional_definitions]:
        workloads:
          <workload_name>:
            [optional_definitions]:
            experiments:
              <experiment_name>:
                [optional_definitions]:
                variables: {}
                [matrix]:
                [matrices]:


In the above ``[optional_definitions]`` can include any of:

* :ref:`env_vars <env-vars-config>`
* :ref:`internals <internals-config>`
* :ref:`modifiers <modifiers-config>`
* :ref:`success_criteria <success-criteria-config>`
* :ref:`tables <tables-config>`
* :ref:`variables <variables-config>`
* :ref:`variants <variants-config>`

Each of these will be described in their own section below.

Within an experiment, each portion of ``[optional_definitions]`` will be merged
together, with the order of precedence (from lowest to highest) being:

* application
* workload
* experiment

.. _config-yaml:

---------------
Config Section
---------------

The config configuration section is used to control internal aspects of Ramble.
The current default configuration is as follows:

.. code-block:: yaml

    config:
      shell: 'bash'
      spack:
        install:
          flags: '--fresh'
        concretize:
          flags: '--fresh'
        buildcache:
          flags: ''
        env_create:
          flags: ''
        global:
          flags: ''
        env_view:
          link_type: 'symlink'
      input_cache: '$ramble/var/ramble/cache'
      workspace_dirs: '$ramble/var/ramble/workspaces'
      upload:
        type: 'BigQuery'
        uri: ''


.. _spack-config-option:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Spack
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``spack`` config options within the config configuration section can be used to
customize Spack's behavior. The ``install``, ``concretize``, ``buildcache``,
and ``env_create`` sections can be used to customize the flags passed to these
Spack commands (with ``env_create`` being equivalent to ``spack env create``).

The ``global`` section is used to define flags that should be passed to
``spack`` directly, as in:
``spack {flags} {subcommand}...``

The ``env_view`` section is used to customize the `spack environment views
<https://spack.readthedocs.io/en/latest/environments.html#environment-views>`_
that Ramble creates. Currently, the only accepted option within this section is
``link_type`` which can take any value supported via Spack.

.. _upload-config-option:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Upload
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Ramble aims to support the upload of experiment outcomes (including FOMs), to
SQL-like datastores. To do this we can specify an ``upload:type`` as defined by
:mod:`ramble.uploader.uploader_types`, and a ``upload:uri`` to specify the
destination. Supported types include ``BigQuery`` and ``PrintOnly`` (which
only logs the data without performing an actual upload).

As part of the upload it tries to attribute the data to a user. This can be
specified via ``config:user``, or if blank ramble will try deduce it based on
the calling user.


.. _disable-passthrough-config-option:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Disable Passthrough
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An optional flag can be set in ``config`` or with ``--disable-passthrough``
on the command line to disable expansion passthrough. Its format is as follows:

.. code-block:: yaml

    config:
      disable_passthrough: True

Expansion passthrough allows variables that don't expand completely to pass
through and not cause an error. This is useful for things like `${ENV_VAR}` 
that are recognized as a variable. When passthrough is disabled, any variables
that fail to expand will raise a syntax error, which can aid in debugging.

.. _overwrite-inventories-config-option:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Overwrite Experiment Inventories
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An optional flag can be set in ``config`` or with ``--overwrite-inventories``
on the command line to force workspace pipelines to overwrite existing
experiment inventories and hashes. This will disable the hash checking / error
semantics, and replace them with reconstruction of the hash regardless of it's
previous contents. Its format is as follows:

.. code-block:: yaml

    config:
      overwrite_inventories: True

.. _experiment-repeats-config-option:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Experiment Repeats
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The repeats config options within the ``config`` section are used to define a number
of times each experiment will be repeated. Summary statistics will be calculated for
the set of repeats. Its format is as follows:

.. code-block:: yaml

    config:
      n_repeats: 'int'
      repeat_success_strict: [True/False]

By default, a set of repeats is successful if all individual repeats are successful.
When ``repeat_success_strict`` is set to false, the set will be considered successful
if any repeat succeeds, and statistics will be calculated over the successful experiments
only.

More information on using repeats within a workspace can be found in the
:ref:`workspace configuration file<workspace-config>`.

.. _general-config-options:

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
General Config Options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Several general configuration options can be set within the ``config`` section:

* ``report_dirs``: Defines the directory where Ramble will store generated reports.
  Default is ``~/.ramble/reports``.
* ``stage_method``: Defines the method used to stage files. Valid options are
  ``cp``, ``rsync``, ``symbolic_link``, and ``hard_link``. Default is ``cp``.
* ``resolve_variables_in_subprocesses``: A boolean flag that controls if environment
  variables should be resolved in subprocesses. Default is ``False``.
* ``shell``: Defines the shell to use for generated scripts. Default is ``bash``.

.. _env-vars-config:

------------------------------
Environment Variables Section:
------------------------------

The environment variables config section is named ``env_vars`` and controls
what environment variable modifications ramble should inject into experiments.

The format of this config section is as follows:

.. code-block:: yaml

    env_vars:
      set:
        var_name: var_value
      append:
      - var-separator: ','
        vars:
          var_to_append: val_to_append
        paths:
          path_to_append: val_to_append
      prepend:
      - paths:
          path_to_prepend: val_to_prepend
      unset:
      - var_to_unset


The above example is general, and intended to show the available functionality
of configuring environment variables. Below the ``env_vars`` level, one of four
actions is available. These actions are:

* ``set`` - Define a variable equal to a given value. Overwrites previously
  configured values
* ``append`` - Append the given value to the end of a previous variable
  definition. Delimited for vars is defined by ``var_separator``, ``paths``
  uses ``:``
* ``prepend`` - Prepent the given value to the beginning of a previous variable
  definition. Only supports paths, delimiter is ``:``
* ``unset`` - Remove a variable definition, if it is set.

.. _filter-groups-config:

----------------------
Filter Groups Section:
----------------------

The filter groups config section is named ``filter_groups`` and allows users to
define persistent, named groups of filters. These groups can be referenced in
commands to easily select subsets of experiments (e.g., specific workloads,
scaling studies) without typing complex logical expressions on the CLI.

Filter groups can be defined globally in ``~/.ramble/filter_groups.yaml`` (user scope)
or per-workspace in ``$workspace/configs/ramble.yaml`` (workspace scope).

If a filter group with the same name is defined in multiple configuration scopes (e.g., in both the user scope and a workspace scope), the definition in the higher-precedence scope completely overrides any definitions from lower-precedence scopes. The definitions (including the ``where`` and ``exclude_where`` lists) are not merged.

The format of this config section is as follows:

.. code-block:: yaml

    filter_groups:
      small-scale:
        where:
        - "{n_nodes} < 4"
        exclude_where:
        - "'{mpi_provider}' == 'tcp'"
      large-scale:
        where:
        - "{n_nodes} >= 8"

Each filter group maps to an object containing lists of filter expressions:

* ``where``: A list of inclusive filter expressions. All expressions must evaluate to ``True`` for an experiment to be included.
* ``exclude_where``: A list of exclusive filter expressions. If any expression evaluates to ``True``, the experiment is excluded.

These groups can then be used on the CLI using the ``-fg`` / ``--filter-group`` (inclusive) and ``-efg`` / ``--exclude-filter-group`` (exclusive) flags on commands like ``ramble on`` or ``ramble workspace setup``. Multiple filter groups can be combined in a single flag using logical expressions (supporting ``and``, ``or``, ``not``, and parentheses):

.. code-block:: console

    $ ramble on -fg "small-scale and not single-node"

Global filter groups can be managed using the top-level ``ramble filter-groups`` command:

.. code-block:: console

    $ ramble filter-groups add -n global-small --where "{n_nodes} < 2"
    $ ramble filter-groups remove -n global-small
    $ ramble filter-groups list
    $ ramble filter-groups blame

By default, these commands edit the global ``user`` scope. You can target a different scope (such as ``workspace``) using the ``--scope`` option.

Alternatively, workspace-scoped filter groups can also be managed using the :ref:`workspace-manage` command.


.. _formatted-execs-config:

------------------------------
Formatted Executables Section:
------------------------------

The formatted executables config section is named ``formatted_executables`` and
controls the creation of variables that represent the complete list of
executables an experiment needs to execute.

The format of this config section is as follows:

.. code-block:: yaml

  formatted_executables:
    command_name:
      [indentation: integer number of indentation spaces]
      [prefix: prefix string]
      [join_separator: string to use to join commands]
      [commands: [list, of, commands]]

In the above, the ``indentation`` attribute is an integer that will be used to
inject spaces at the beginning of each line. The ``prefix`` attribute is used
to define a prefix (after the indentation) to add to each line of the formatted
executable. The ``join_separator`` attribute defines the string that will be
used to join independent lines of the formatted executable. The ``commands``
attribute is a list of strings that will be re-formatted using the definitions
in the rest of the formatted executable definition. Each entry will be split
across new line characters before reformatting.

The default values for the attributes are:

.. code-block:: yaml

  formatted_executables:
    command:
      indentation: 0
      prefix: ''
      join_separator: '\n'
      commands:
      - '{unformatted_command}'

A more complete exampe of using formatted executables can be seen below:

.. code-block:: yaml

  formatted_executables:
    new_command:
      indentation: 8
      prefix: '- '
      join_separator: '\n'

The above example defines a new variable named ``new_command`` which will be a
new-line (``\n``) demlimited list of executables, where each executable is
prefixed with ``'- '`` and is indented 8 space characters.

The default configuration files define one formatted executable named
``command``. Its definition can be seen with:

.. code-block:: console

  $ ramble config get formatted_executables

.. _internals-config:

------------------
Internals Section:
------------------

The internals config section is used to modify internal aspects of an
application definition when creating experiments.

**NOTE:** This section is intended as more of an advanced user section, and can
easily break aspects of the experiment if used incorrectly.

The format of the internals config section is as follows:

.. code-block:: yaml

    internals:
      custom_executables:
        <executable_name>:
          template: [list, of, commands, for, template]
          use_mpi: [True/False] # Default: False
          redirect: 'where_to_redirect_output' # Default '{log_file}'
          output_capture: 'operator_to_use_for_redirection' # Default >>
          force: [True/False] # Default: False
      executables:
      - list of
      - executables
      - to use in
      - experiments
      executable_injection:
      - name: <executable_name>
        order: 'before' / 'after' # Default: 'after'
        [relative_to: <relative_executable_name>]
      custom_inputs:
        <input_name>:
          url: 'url_or_path_to_input' # Supports variable expansion: {var}
          sha256: 'checksum_or_null' # Default: None (or null to disable check)
          target_dir: 'target_directory' # Default: '{workload_input_dir}'
          expand: [True/False] # Default: True
          extension: 'extension' # Optional file extension override
          description: 'description_of_input' # Optional
      custom_workloads:
        <workload_name>:
          executables:
          - list of executables
          inputs:
          - list of input names
          tags:
          - list of tags

Currently this section has five sub-sections: ``custom_executables``,
``executables``, ``executable_injection``, ``custom_inputs``, and
``custom_workloads``.

The ``custom_executables`` sub-section can be used to define new executables
that an experiment can use. It can also be used to override the definition
of an internally defined executable within an experiment, when the ``force``
property is set to ``True``.

The ``executables`` sub-section can be used to control the order executables
will be used in the experiment. This is also the mechanism to inject custom
executables into an experiment.

The ``executable_injection`` sub-section can be used to inject custom
executables into the list of executables an experiment would use without having
to define the entire list. The ``name`` attribute should be set to the name of
an executable. This can be either a custom executable (defined in
``custom_executables``) or an existing executable (including a ``builtin``).
The ``order`` attrbite can be set to either ``before`` or ``after`` with
``after`` being the default value if it is not specified. The ``relative_to``
attribute can be set to the name of an executable already in the list of
experiment executables (including custom executables that are already injected).

Processing the ``executable_injection`` sub-section occurs after processing the
``executables`` sub-section. Executables are injected in the order they are
listed in the YAML file, with lower precedence scopes being processed first.
(e.g. ``workspace`` executables are injected before ``experiment`` executables
are).

The ``custom_inputs`` sub-section can be used to define new input files or
override built-in inputs for an experiment. When overriding an existing input,
unspecified attributes (such as ``target_dir``, ``expand``, or ``description``)
are preserved from the original application definition. The ``url`` attribute
supports variable expansion (e.g., ``url: 'https://mirror.org/{dataset}.tar.gz'``),
allowing datasets to be swept across variable matrices. To disable sha256 checksum
verification (for instance when using modified or custom datasets), specify
``sha256: null``.

The ``custom_workloads`` sub-section allows users to compose custom workloads or
override built-in workloads directly in YAML without writing Python application code.
It links executables (built-in or ``custom_executables``), inputs (built-in or
``custom_inputs``), and tags. Any workload tags defined here are attached to the
experiment's tags. Workload variables corresponding to the input names (e.g.
``{<input_name>}``) are automatically made available to templates and executable
commands, expanding to the expanded input directory or file path.

.. _licenses-config:

-----------------
Licenses Section:
-----------------

The licenses config section is used to configure license environment variables
to applications. Its format is as follows:

.. code-block:: yaml

    licenses:
      <application_name>:
        set:
          var_to_set: 'VALUE'
        append:
        - var-separator: ','
          vars:
            var_to_append: 'VALUE'
        - paths:
            path_to_append: 'VALUE'
        prepend:
        - paths:
            path_to_prepend: 'VALUE'
        unset:
        - var_to_unset


Ramble will automatically inject these environment variable modifications into
experiments that use the application defined by ``<application_name>``.

.. _mirrors-config:

----------------
Mirrors Section:
----------------

The mirrors config section is used to control alternative locations Ramble
should download input files from. Mirros are checked before the default URL for
an input file. The format of the mirrors section is as follows:


.. code-block:: yaml

    mirrors:
      <mirror1_name>: 'url'
      <mirror2_name>:
        fetch: 'fetch_url'
        push: 'push_url'


.. _modifier-repos-config:

-----------------------
Modifier Repos Section:
-----------------------

The modifier repos config section is used to control which repositories should
be searched for when looking for modifiers. Its format is as follows:

.. code-block:: yaml

    modifier_repos:
    - 'path/to/repo'


.. _modifiers-config:

------------------
Modifiers Section:
------------------

The modifiers config section is used to control which modifiers will be used on
experiments ramble generates. Its format is as follows:

.. code-block:: yaml

    modifiers:
    - name: <modifier_name>
      mode: <mode_for_modifier> # Optional if modifier only has one mode or if default_mode is set
      on_executable: # Defaults to '*', follows glob syntax
      - list of
      - executables to apply
      - modifier to

**NOTE**: Every modifier has a ``disabled`` mode by default that can be set
(only explicitly) to turn off all of the modifier's functionality.


.. _repos-config:

--------------
Repos Section:
--------------

The repos config section is used to control which repositories should
be searched for when looking for application definitions. Other sections
controlling different types of object repositories follow the same format.
These include:

* ``base_application_repos``
* ``base_class_repos``
* ``base_modifier_repos``
* ``base_package_manager_repos``
* ``base_workflow_manager_repos``
* ``package_manager_repos``
* ``workflow_manager_repos``

The format for these sections is as follows:

.. code-block:: yaml

    repos:
    - 'path/to/repo'


.. _software-config:

-----------------
Software Section:
-----------------

The software config section is used to define package definitions, and software
environments created from those packages. Its format is as follows:

.. code-block:: yaml

    software:
      [variables: {}]
      packages:
        <package_name>:
          pkg_spec: 'pkg_spec_for_package'
          compiler_spec: 'Compiler spec, if different from pkg_spec' # Default: None
          compiler: 'package_name_to_use_as_compiler' # Default: None
          [variables: {}]
          [matrix:]
          [matrices:]
      environments:
        <environment_name>:
          packages:
          - list of
          - packages in
          - environment
          [variables: {}]
          [matrix:]
          [matrices:]
        <external_env_name>:
          external_env: 'name_or_path_to_spack_env'

The packages dictionary houses ramble descriptions of software packages that
can be used to construct environments with. A package is defined as software
that the defined package manager should install for the user. These have one
required attribute, and two optional attributes. The ``pkg_spec`` attribute is
required to be defined, and should be the arguments passed to the package
manager's ``install`` subcommand. Optionally, a package can define a
``compiler_spec`` attribute, which will be the spec used when this package is
used as a compiler for another package. Packages can also optionally define a
``compiler`` attribute, which is the name of another package that should be
used as it's compiler.

The environments dictionary contains descriptions of groups of packages that
Ramble might generate based on the requested experiments. Environments are
defined as a list of packages (in the aforementioned packages dictionary) that
should be bundled into a shared environment within the package manager.

Below is an annotated example of the software dictionary.

.. code-block:: yaml

    software:
      packages:
        gcc14: # Abstract name to refer to this package
          pkg_spec: gcc@14.2.0 target=x86_64 # Spack spec for this package
          compiler_spec: gcc@14.2.0 # Spack compiler spec for this package
        intel-mpi:
          pkg_spec: intel-oneapi-mpi@2021.17.2 target=x86_64
          compiler: gcc14 # Other package name to use as compiler for this package
        gromacs:
          pkg_spec: gromacs@2025.3
          compiler: gcc14
      environments:
        gromacs:
          packages: # List of packages to include in this environment
          - intel-mpi
          - gromacs

Packages and environments defined inside the ``software`` config section are
merely templates. They will be rendered into explicit environments and packages
by each individual experiment.

^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Package Manager Specific Packages
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When selecting package managers within Ramble experiments, the default spec a
package manager will use is contained in the ``pkg_spec`` attribute. If
multiple package managers will use the same package definition, specs for each
can be defined using the ``<package_manager>_pkg_spec`` syntax. This syntax can
be used on the ``compiler`` and ``compiler_spec`` attributes as well, if the
package manager supports selecting a specific compiler.


^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
External Spack Environment Support:
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**NOTE**: Using external Spack environments is an advanced feature.

Some experiments will want to use an externally defined Spack environment
instead of having Ramble generate its own Spack environment file. This can be
useful when the Spack environment a user wants to experiment with is
complicated.

This section shows how this feature can be used.

.. code-block:: yaml

    software:
      environments:
        gromacs:
          external_env: name_or_path_to_spack_env

In the above example, the ``external_env`` keyword refers an external
Spack environment. This can be the name of a named Spack environment, or the
path to a directory which contains a Spack environment. Ramble will copy the
``spack.yaml`` file from this environment, instead of generating its own.

This allows users to describe custom Spack environments and allow them to be
used with Ramble generated experiments.

It is important to note that Ramble copies in the external environment files
every time ``ramble workspace setup`` is called. The new files will clobber the
old files, changing the configuration of the environment that Ramble will use
for the experiments it generates.


.. _success-criteria-config:

-------------------------
Success Criteria Section:
-------------------------

The success criteria section is used to control what criteria experiment should
use when determining if they were successful or not. Its format is as follows:

.. code-block:: yaml

    success_criteria:
    - name: 'criteria_name'
      mode: 'criteria_mode' # i.e. 'string' for string matching
      match: 'regex_for_matching'
      file: 'file_criteria_should_be_found_in'


For more information about using success criteria, see the
:ref:`success criteria documentation<success-criteria>`.

.. _tables-config:

---------------
Tables Section:
---------------

The tables section is used to define tables that should be generated when a
workspace is analyzed. Its format is as follows:

.. code-block:: yaml

     tables:
     - name: "table_name_template"
       [optional table attributes]
       columns:
       - name: "column_name_template"
         [column_attributes]


In the tables section, a list of tables can be provided. Tables can also be
included in the :ref:`applications<application-config>` section. In this case,
tables are scoped to the section they are added in (i.e. a table added within a
specific application name will only generate data for that application's
experiments, and likewise for workloads and experiment blocks).

In the above, ``[optional table attributes]`` includes any of the following:

.. code-block:: yaml

   group_by:
   - "list of column names"
   - "to group (collapse) data by"
   group_method: "max" # Method of applying the grouping
   sort_by:
   - "list of column names"
   - "to sort data by"
   where:
   - "list of expressions"
   - "to filter experiments"
   - "to build table from"
   transpose: true # Optional: transpose the table before writing out

The ``group_method`` can be selected from any `groupby method supported by
Pandas dataframes
<https://pandas.pydata.org/docs/reference/groupby.html#dataframegroupby-computations-descriptive-stats>`_.

Additionally, ``[column_attributes]`` can include any of the following:

.. code-block:: yaml

   columns:
   - name: "column name template"
     where:
     - "list of expressions"
     - "to filter experiments"
     - "when building this column"
     expression: "Ramble-style expression for column value"
     figure_of_merit: "Figure of merit name for column value"
     figure_of_merit_context: "Context name to extract figure of merit from"
     figure_of_merit_origin_type: "Origin type to extract figure of merit from"

One of ``expression`` and ``figure_of_merit`` are required for each column. If
a context is not provided, Ramble will attempt to auto-detect the context.
Similarly, if the origin type is not provided, Ramble will auto detect the
origin type.

Tables also support ``autocolumns``, which allow columns to be generated
dynamically based on the contexts and figures of merit found in an experiment's
results. The attributes for ``autocolumns`` are as follows:

.. code-block:: yaml

   autocolumns:
   - name: "column name template"
     context_name: "glob or regex for context definition name or instance name"
     figure_of_merit: "glob or regex for figure of merit name"
     figure_of_merit_origin_type: "Origin type to extract figure of merit from"
     sort_by:
     - "list of context variables"
     - "to sort generated columns by"
     where:
     - "list of expressions"
     - "to filter experiments"
     - "when building this column"

In an ``autocolumn``, ``name`` and ``figure_of_merit`` are required. If
``context_name`` is omitted, Ramble will match figures of merit that are not
within any specific context (the "null" context).

The ``name`` template for an ``autocolumn`` can include any variables from the
matched context, as well as the special variables ``{fom_name}`` and
``{context_name}`` (the name of the specific context instance). If regular
expressions are used for ``context_name`` or ``figure_of_merit``, any named
capture groups will also be available as variables in the ``name`` template.

Columns are built in YAML order. The ``expression`` attribute can be used to
refer to values from other columns that are defined before the current column.
Explicitly defined columns are always added to the table before any generated
``autocolumns``. Within a set of generated columns from the same template, the
``sort_by`` field determines their relative order.

Both ``table_name_template`` and ``column_name_template`` can include Ramble
variables, to automatically generate new tables and columns. As an example:

.. code-block:: yaml

   tables:
   - name: '{workload_name} status'
     columns:
     - name: Experiment
       expression: '{experiment_name}'
     - name: Status
       expression: '{experiment_status}'

Will automatically create one table per workload, with the status summary of
that workload's experiments.

.. _variables-config:

------------------
Variables Section:
------------------

The variables config section is used to define variables within ramble
experiments. These variables are used in several places within Ramble. Its
format is as follows:

.. code-block:: yaml

    variables:
      var_name: 'var_value'
      list_var_name: ['val1', 'val2']
      cross_reference_var: 'var in <app>.<workload>.<exp>'

Variables can be defined as lists, scalars, or can refer to a variable defined in
another fully qualified experiment (through the syntax shown in ``cross_reference_var``).

For more information on variable expansion rules, see:
:ref:`workspace variable dictionary definitions<variable-dictionaries>`.

.. _variants-config:

----------------
Variants Section
----------------

The variants config section is used to customize variants to the experiment creation.
These can include application defined variants, or higher level Ramble provided
variants. The format of this section, along with some example variants, can be seen below:

.. code-block:: yaml

    variants:
      package_manager: <pkg_man_name> or user-managed
      workflow_manager: <work_flow_man_name> or user-managed
      system: <sys_name> or user-managed
      platform: <plat_name> or user-managed

Variants are expanded following the same logic to expand variables (so a
variant could be lazily expanded based on an experiment's variable definitions).

Selection of variants can customize your workspace beyond the YAML
configuration. These can be used to change the behavior of experiment objects,
or define system or platform selections that can encapsulate many defaults.

.. _zips-config:

-------------
Zips Section:
-------------

The zips config section is used to define explicit groupings of variables that
are related and should be iterated over together when generating experiments.
Its format is as follows:

.. code-block:: yaml

    zips:
      <zip_name>:
      - <var1>
      - <var2>

For more information on using zips, see the :ref:`explicit variable zips
documentation<ramble-explicit-zips>`.
