.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _success-criteria:

================
Success Criteria
================

Ramble supports various methods of defining success criteria, which mark
experiments as successfully completed, or failed when analyzing a workspace.

This document describes the supported functionality, and how to use success
criteria in general.

-------------------------
Types of Success Criteria
-------------------------

Success criteria can be defined in two places:
* An application.py file
* A :ref:`ramble.yaml workspace config file<workspace-config>`

Success criteria defined in an application.py file applies to **all**
experiments this application generates. These are intended to provide more of a
"did my experiment complete" success criteria.

Success criteria defined in a workspace config file only applies to those
specific experiments. These criteria can evaluate if an experiment performed
adequately.

The ``application.py`` interface is documented in the
:ref:`application developers guide<application-dev-guide>`.

The rest of this document focuses on how to write success criteria in a
workspace configuration file. But it will describe general aspects of success
criteria that can apply to either definition.

-------------------------
Defining Success Criteria
-------------------------

Success criteria defined in a workspace config file are all merged together,
following the logic for optional sections in the workspace config file.

A block of success criteria is defined as a list of independent criteria that
should be evaluated.

.. code-block:: yaml

    success_criteria:
    - name: criteria1
      mode: 'string'
      match: 'Completed'
    - name: criteria2
      mode: 'application_function'

Success criteria can mix modes, and are all evaluated. If **any** success
criteria returns false, the experiment is marked as ``FAILED`` in the output of
``ramble workspace analyze``.

----------------------
Success Criteria Modes
----------------------

Each success criteria has a mode. Currently, there are three supported modes.

* ``'application_function'``
* ``'fom_comparison'``
* ``'string'``

We will cover each of these supported modes in more detail below.

^^^^^^^^^^^^^^^^^^^^^^^^^^
Mode: Application Function
^^^^^^^^^^^^^^^^^^^^^^^^^^

A success criteria with ``mode='application_function'`` will use an
application.py's defined ``evaluate_success`` function to test for experiment
success. This hook allows an application developer to perform more complicated
actions that are specific to the experiment.

**NOTE:** A success criteria with ``mode='application_function'`` is added by
default to all experiments. The base ``evaluate_success`` function always
returns ``True``.

^^^^^^^^^^^^^^^^^^^^
Mode: FOM Comparison
^^^^^^^^^^^^^^^^^^^^

Success criteria with ``mode='fom_comparison'`` allow experiments to define
complex mathematical logic to evaluate success of an experiment. Defining
these criteria within a workspace configuration file is as follows:

.. code-block:: yaml

    success_criteria:
    - name: my_criteria
      mode: fom_comparison
      fom_name: 'application_fom_*'
      [fom_context: 'fom_context_*']
      formula: '{value} > 1.0'

The above example shows the full interface for defining success criteria with
``mode='fom_comparison'``. The available attributes are:

* ``name``: The name of the specific criteria
* ``mode``: The mode of the specific criteria
* ``fom_name``: The name of the FOM to use for evaluating the formula
* ``formula``: The formula to evaluate for success.
* ``fom_context``: (Optional) The context ``fom_name`` should exist in. Defaults to ``null``.

Both ``fom_name`` and ``fom_context`` support
`python style globbing <https://docs.python.org/3/library/fnmatch.html>`_.

When using the globbing functionality, all contexts that match the
``fom_context`` argument are searched. Within each context, all FOMs that match
``fom_name`` are tested with ``formula``. The success criteria will only pass
if **all** matched figures of merit satisfy the formula.

The ``formula`` attribute can access any variables defined within an
experiment. Additionally, an extra ``value`` variable is defined, which takes
the value of the FOM as extracted from the output.

The ``fom_context`` attribute also supports variable expansion, allowing a
criterion to dynamically target a specific context using experiment variables:

.. code-block:: yaml

    success_criteria:
    - name: hpl_target_perf
      mode: fom_comparison
      fom_context: 'N-NB-P-Q = {Ns}-{NBs}-{Ps}-{Qs}'
      fom_name: 'GFlops'
      formula: '{value} > 12000.0'

If a workload variable contains multiple values (for example, ``Ns: '1000 20000'``
in HPL's ``standard`` workload), a separate variable can be defined to target
the specific context of interest:

.. code-block:: yaml

    variables:
      Ns: '1000 20000'
      Optimal-N: 20000
    success_criteria:
    - name: hpl_target_perf
      mode: fom_comparison
      fom_context: 'N-NB-P-Q = {Optimal-N}-{NBs}-{Ps}-{Qs}'
      fom_name: 'GFlops'
      formula: '{value} > 12000.0'


^^^^^^^^^^^^^^^^^^^^
Mode: String
^^^^^^^^^^^^^^^^^^^^

Success criteria with ``mode='string'`` allow experiments to define expected
string regular expression matching. This criteria mode is useful if an
application prints a string whenever it successfully completes, or if it
prints an error message when it fails. Defining these criteria within a
workspace configuration file is as follows:

.. code-block:: yaml

    success_criteria:
    - name: my_criteria
      mode: 'string'
      match: '\s+Completed\s+'
      [file: '{log_file}']


The above shows the full interface for defining success criteria with
``mode='string'``. The available attributes are:

* ``name``: The name of the specific criteria.
* ``mode``: The mode of the specific criteria.
* ``match``: The regular expression used to test for success. If this is found
  the criteria is marked as a success.
* ``anti_match``: The regular expression used to test for failure. If this is
  found the criteria is marked as a failure.
* ``file``: (Optional) The file (or variable that refers to a file) to test
  for the ``match`` or ``anti_match`` in.

Note that ``match`` and ``anti_match`` are mutually exclusive.

If ``match`` is used, and found inside ``file`` this criteria is marked as
success. If it is not found, then the criteria is marked as failed.

If ``anti_match`` is used, and found inside ``file`` this criteria is marked as
failed. If it is not found, then the criteria is marked as success.
