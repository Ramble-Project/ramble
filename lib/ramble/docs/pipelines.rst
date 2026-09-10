.. Copyright 2022-2026 The Ramble Authors

   Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
   https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
   <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
   option. This file may not be copied, modified, or distributed
   except according to those terms.

.. _ramble-pipelines:

=========================
Pipelines and Phases
=========================

Unlike frameworks with a single fixed execution pipeline, Ramble defines high-level workflows
(**Pipelines**) that execute an ordered graph of steps (**Phases**).

-------------------------
Common Workspace Workflow
-------------------------

An example of a Ramble workspace workflow might look like the following:

.. graphviz::

    digraph workspace_workflow {
        fontsize=12;
        rankdir=TB;
        nodesep=0.4;
        ranksep=0.4;

        node [
            shape=box,
            style="filled,rounded",
            fontsize=11,
            margin="0.3,0.12",
            width=3.8
        ];
        edge [fontsize=10, color="#333333", penwidth=1.5];

        step1 [
            label=<<b>1. Workspace Creation</b><br/>(ramble workspace create)>,
            fillcolor="#f8f9fa",
            color="#495057"
        ];
        step2 [
            label=<<b>2. YAML &amp; Template Configuration</b><br/>(ramble workspace edit)>,
            fillcolor="#e9ecef",
            color="#495057"
        ];
        step3 [
            label=<<b>3. Workspace Concretization</b><br/>(ramble workspace concretize)>,
            fillcolor="#e2e3e5",
            color="#495057"
        ];
        step4 [
            label=<<b>4. Setup Pipeline</b><br/>(ramble workspace setup)>,
            fillcolor="#d4edda",
            color="#28a745"
        ];
        step5 [
            label=<<b>5. Execute Pipeline</b><br/>(ramble on)>,
            fillcolor="#cce5ff",
            color="#004085"
        ];
        step6 [
            label=<<b>6. Analyze Pipeline</b><br/>(ramble workspace analyze)>,
            fillcolor="#ffe8cc",
            color="#d9480f"
        ];
        step7 [
            label=<<b>7. Workspace Reporting</b><br/>(ramble results)>,
            fillcolor="#d1ecf1",
            color="#0c5460"
        ];
        step8 [
            label=<<b>8. Archive Pipeline</b><br/>(ramble workspace archive)>,
            fillcolor="#eebefa",
            color="#862e9c"
        ];

        step1 -> step2 -> step3 -> step4 -> step5 -> step6 -> step7 -> step8;
    }

1. **Creation**: Initialize a workspace using :ref:`ramble workspace create
   <ramble-workspace-create>`.
2. **YAML and Template Configuration**: Edit the primary configuration file
   ``$workspace/configs/ramble.yaml`` or custom execution templates like ``execute_experiment.tpl``
   using :ref:`ramble workspace edit <ramble-workspace-edit>` (see :doc:`workspace_config`).
3. **Concretization**: Resolve software specs and experiment matrix combinations using :ref:`ramble
   workspace concretize <ramble-workspace-concretize>`.
4. **Setup Pipeline**: Run :ref:`ramble workspace setup <ramble-workspace-setup>` to build
   software environments, download datasets, and render execution scripts.
5. **Execution Pipeline**: Launch experiments via :ref:`ramble on <ramble-on>`. :doc:`Workflow
   Managers <workflow_managers>` (e.g., Slurm, PBS, Google Batch) expand ``{batch_submit}`` to
   submit jobs to batch schedulers or execute scripts directly on compute nodes.
6. **Analysis Pipeline**: Extract Figures of Merit (FOMs) and evaluate success criteria using
   :ref:`ramble workspace analyze <ramble-workspace-analyze>`.
7. **Reporting**: View summary statistics and result tables using :ref:`ramble results
   <ramble-results>` (see :doc:`results`).
8. **Archiving Pipeline**: Package logs, rendered templates, and inventory files into an archive
   via :ref:`ramble workspace archive <ramble-workspace-archive>`.

For a more detailed explanation of pipelines and phases, refer to the :ref:`advanced pipelines and phases <ramble-pipelines-and-phases>` documentation.