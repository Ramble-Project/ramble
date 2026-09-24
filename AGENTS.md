# AI Agent Context for Ramble

**Objective:** This document guides AI agents in assisting with questions and tasks related to the Ramble experimentation framework.

## What is Ramble?

Ramble is a multi-platform experimentation framework written in Python, designed to increase exploration productivity and improve reproducibility. It helps automate and manage tasks such as:

*   Software installation (often using Spack)
*   Acquiring input files
*   Configuring experiments (e.g., parameter sweeps, scaling studies)
*   Executing experiments
*   Extracting and analyzing results

Ramble works on Linux, macOS, and many supercomputers.

## Ramble Command Line Interface (CLI)

Ramble is primarily controlled through the `ramble` command. Key aspects of the CLI include:

*   You should always examine the command line interface before you execute any ramble commands, as the arguments might change over time.
*   **Getting Help:** Users can get help on any command by using `ramble help` or `ramble help --all` for more detailed information on all commands. Help is also available for subcommands (e.g., `ramble workspace --help`).
*   **Discovering Commands and Depth:** To discover the full command hierarchy and determine its maximum depth, start with `ramble help --all`. For any command that shows `...` in its help text (indicating it has subcommands), run that command with `--help` or `-h` to explore its subcommands (e.g., `ramble workspace --help`). This process can be repeated recursively until no more subcommands are found. The longest chain of commands reveals the maximum depth of the CLI.
*   **Key Commands:**
    *   `ramble workspace create`: To set up a new experiment workspace.
    *   `ramble workspace config`: To manage workspace configurations.
    *   `ramble on`: To execute the experiments defined in the workspace.
    *   `ramble list`: To list available applications, modifiers, etc.
    *   `ramble config`: To manage Ramble's configuration settings.
    *   `ramble repo`: To manage Ramble repositories.
*   **Command Reference:** A full list of commands and their options is available in the [Command Reference](https://ramble.readthedocs.io/en/latest/command_index.html) section of the documentation.

## Ramble Configuration Files

Ramble uses YAML files for configuration, drawing inspiration from Spack's configuration system. Configurations are applied in scopes, with higher precedence scopes overriding lower ones (e.g., user settings override system defaults, workspace settings override user settings).

### Workspace Configuration

*   **Main File:** Each workspace has a primary configuration file located at `$workspace/configs/ramble.yaml`. This file defines the experiments, software, and variables for the workspace.
*   **Structure:** All content within `ramble.yaml` lives under the top-level `ramble:` dictionary.
*   **Detailed Documentation:** [Workspace Configuration File](https://ramble.readthedocs.io/en/latest/workspace_config.html)

### Configuration Sections

Ramble supports various sections within its configuration files. These can exist in the workspace `ramble.yaml`, in separate files within `$workspace/configs/`, or in other configuration scopes (user, site, system). Key sections include:

*   `applications`: Defines the experiments to be generated, including application, workload, and experiment scopes, variables, matrices, etc. See the [Application Section](https://ramble.readthedocs.io/en/latest/configuration_files.html#application-section).
*   `config`: Controls internal Ramble behavior, shell settings, Spack command flags, and upload configurations. See the [Config Section](https://ramble.readthedocs.io/en/latest/configuration_files.html#config-section).
*   `env_vars`: Manages environment variable modifications (set, append, prepend, unset) for experiments. See the [Environment Variables Section](https://ramble.readthedocs.io/en/latest/configuration_files.html#environment-variables-section).
*   `software`: Defines software packages and environments, specifying package manager specs (e.g., Spack specs), compilers, and dependencies. See the [Software Section](https://ramble.readthedocs.io/en/latest/configuration_files.html#software-section).
*   `variables`: Defines key-value pairs used for parameterization and expansion within other configuration sections and templates. See the [Variables Section](https://ramble.readthedocs.io/en/latest/configuration_files.html#variables-section).
*   `variants`: Customizes variants for experiment creation, such as selecting the `package_manager`. See the [Variants Section](https://ramble.readthedocs.io/en/latest/configuration_files.html#variants-section).
*   `modifiers`: Specifies experiment modifiers to be applied to experiments, including mode and target executables. See the [Modifiers Section](https://ramble.readthedocs.io/en/latest/configuration_files.html#modifiers-section).
*   `repos`: Lists paths to repositories containing Application definitions.
*   `modifier_repos`: Lists paths to repositories containing Modifier definitions.
*   **Other Sections:**
    *   `base_application_repos`
    *   `base_class_repos`
    *   `base_modifier_repos`
    *   `base_package_manager_repos`
    *   `base_workflow_manager_repos`
    *   `formatted_executables`
    *   `internals`
    *   `licenses`
    *   `mirrors`
    *   `package_manager_repos`
    *   `success_criteria`
    *   `tables`
    *   `workflow_manager_repos`
    *   `zips`

*   **Full Details:** See the [Configuration Files Documentation](https://ramble.readthedocs.io/en/latest/configuration_files.html) for a complete description of all sections and scopes.

## Package Managers

Ramble can leverage various package managers to install the software required for experiments. The configuration of package managers is detailed in the [Package Managers Documentation](https://ramble.readthedocs.io/en/latest/package_managers.html).

### Spack

A key feature of Ramble is its ability to manage software stacks, often using **Spack**.

*   **Spack:** Spack is a flexible package manager for supercomputers, Linux, and macOS, supporting multiple versions, configurations, platforms, and compilers.
*   **Ramble's Usage:** Ramble can be configured to use an existing Spack instance. Experiment configuration files in Ramble define the software stacks required, which Ramble can then realize using Spack.
*   **Spack Documentation:** To understand how to use Spack, specify packages, versions, compilers, and variants, refer to the official Spack Documentation:
    *   **Spack Homepage:** [https://spack.io/](https://spack.io/)
    *   **Spack Documentation:** [https://spack.readthedocs.io/en/latest/](https://spack.readthedocs.io/en/latest/)
    *   [Getting Started](https://spack.readthedocs.io/en/latest/getting_started.html)
    *   [Spec Syntax](https://spack.readthedocs.io/en/latest/spec_syntax.html)
    *   [Spack Environments](https://spack.readthedocs.io/en/latest/replace_conda_homebrew.html)
    *   [Command Reference](https://spack.readthedocs.io/en/latest/command_index.html)
*   **Key Concepts:** When assisting with Ramble and Spack, be aware of Spack concepts like `spack.yaml`, environments, compilers, and specs.

## Developing New Object Definitions

Ramble is extensible through user-defined objects. These objects are Python classes that follow specific conventions and structures. Ramble uses a specialized language structure, defined in Python, to parse and manage these definitions.

*   **Definition Files:** Each object definition resides in a Python file (e.g., `application.py` for an application) within a directory named after the object inside a repository.
*   **Object Types:** The primary object types that users can define include:
    *   **Applications:** Define the core software and execution logic for an experiment.
    *   **Modifiers:** Allow for systematic alterations to application configurations or execution parameters.
    *   **Package Managers:** Interfaces to software installation tools like Spack, EESSI, etc.
    *   **Workflow Managers:** Interfaces to batch systems or workflow tools (e.g., Slurm, LSF).
    These types, and their base classes, are enumerated in `lib/ramble/ramble/repository.py` within the `ObjectTypes` Enum.
*   **Ramble Definition Language:** Ramble uses a set of Python classes and decorators to define the structure and attributes of each object type. These are implemented in the `lib/ramble/ramble/language` directory. This includes files like:
    *   `application_language.py`
    *   `modifier_language.py`
    *   `package_manager_language.py`
    *   `workflow_manager_language.py`
    *   `shared_language.py`
    These modules define the valid keywords, sections, and expected types for the object definition classes.
*   **Developer Guides:** Ramble provides guides for creating new definitions:
    *   [Application Definition Developers Guide](https://ramble.readthedocs.io/en/latest/dev_guides/application_dev_guide.html)
    *   [Modifier Definition Developers Guide](https://ramble.readthedocs.io/en/latest/dev_guides/modifier_dev_guide.html)
    *   [Package Manager Definition Developers Guide](https://ramble.readthedocs.io/en/latest/dev_guides/package_manager_dev_guide.html)
    *   [Advanced Topics for Definition Developers](https://ramble.readthedocs.io/en/latest/dev_guides/advanced_topics.html)

New definitions are typically placed in a user-created repository and added to the Ramble configuration.

### How to Write an Application Definition

This section provides a practical guide for creating a new Ramble application definition by focusing on the key patterns and concepts.

1.  **Repository Structure**: To determine the correct directory structure for a custom definition, inspect the `ObjectTypes` Enum in `lib/ramble/ramble/repository.py`. This enum defines the valid object types (e.g., `APPLICATIONS`, `MODIFIERS`). The value of each enum member (e.g., `'applications'`) is the name of the required subdirectory within a repository. Each specific definition should then be placed in its own directory inside that subdirectory. For example, a new application would be located at `my-repo/applications/my-app-name/application.py`.

2.  **The Definition File**: The definition file (e.g., `application.py`) contains a Python class that inherits from a base class. There are two categories of base definitions to be aware of:
    *   **Fundamental Base Classes**: These are the abstract building blocks for new definitions (e.g., `executable-application`, `basic-modifier`). This is the most common starting point for creating a new definition from scratch. You can discover them by running:
        ```bash
        ramble list --type base_classes
        ```
    *   **Inheritable Concrete Definitions**: These are fully-formed definitions that are designed to be inherited by other definitions to promote code reuse (e.g., a `base_application` like `hpcg`). This is a more advanced pattern. You can discover them by running `ramble list --type base_<object_type>`, for example:
        ```bash
        ramble list --type base_applications
        ramble list --type base_modifiers
        ramble list --type base_package_managers
        ramble list --type base_workflow_managers
        ```

3.  **Key Concepts and Patterns**:
    *   **Declarative Directives**: The application's behavior is defined by calling special functions (directives) within the class body. Instead of writing imperative code, you declare the application's properties.
    *   **Logical Grouping of Directives**: Directives can be understood in logical groups based on their purpose:
        *   **Metadata**: Directives that set the application's `name`, `maintainers`, and `tags`.
        *   **Software Dependencies**: Directives for specifying required software packages (`software_spec`) and compilers (`define_compiler`). These often contain package-manager-specific syntax.
        *   **Execution & Workloads**: Directives for defining `executable` commands, `input_file` data sources, and `workload`s, which are combinations of executables and inputs that represent a specific test case.
        *   **Parameterization**: The `workload_variable` directive is used to define parameters that can be set in the Ramble configuration, allowing for flexible and reusable workload definitions.
        *   **Results & Validation**: Directives for defining how to parse results (`figure_of_merit`) and determine a successful run (`success_criteria`) from output files, typically using regular expressions.
        *   **Templating**: A `register_template` directive exists to generate complex input or configuration files from a template file.
    *   **Conditional Logic**: A core pattern in Ramble is the use of a `with when(...)` context manager. This allows directives to be applied conditionally, based on factors like the chosen package manager, system architecture, or other variants. This is the standard way to create a single, portable definition that works in multiple environments.

4.  **Best Practices**:
    *   **Study Existing Definitions**: The most effective way to understand the current, concrete syntax is to study the built-in application definitions. These provide real-world examples of the patterns described above. Good starting points are `hostname` (simple), `gromacs` (complex), and `hpcg` (inheritance).
    *   **Write Informative Docstrings**: The docstring for the application class should clearly describe the application and include links to its official website, documentation, and source code.
    *   **Check for Software Conflicts**: Before adding a new `software_spec`, check for existing definitions of the same package to ensure consistency.
        1.  Get a summary of all existing software definitions: `ramble software-definitions --summary`
        2.  Search the output for the package you intend to add.
        3.  Use a consistent version and spec to avoid conflicts and encourage software reuse.
        4.  After adding your `software_spec`, confirm that no conflicts were introduced: `ramble software-definitions --conflicts`


## Key Ramble Resources

*   **GitHub Repository:** [https://github.com/Ramble-Project/ramble](https://github.com/Ramble-Project/ramble)
    *   Source code, issue tracker, and discussions.
    *   The `develop` branch has the latest contributions.
*   **Documentation:** [https://ramble.readthedocs.io/en/latest/](https://ramble.readthedocs.io/en/latest/)
    *   [Getting Started Guide](https://ramble.readthedocs.io/en/latest/getting_started.html)
    *   [Tutorials](https://ramble.readthedocs.io/en/latest/tutorials.html)
    *   [Configuration Files](https://ramble.readthedocs.io/en/latest/configuration_files.html)
    *   [Ramble Workspace](https://ramble.readthedocs.io/en/latest/workspace.html)
    *   [Package Managers](https://ramble.readthedocs.io/en/latest/package_managers.html)
    *   [Developer Guides](https://ramble.readthedocs.io/en/latest/dev_guides.html)
    *   [Command Reference](https://ramble.readthedocs.io/en/latest/command_index.html)
*   **Examples:** The [examples directory](https://github.com/Ramble-Project/ramble/tree/develop/examples) in the GitHub repo contains many example configuration files.

## Common Tasks & Questions

*   **Using the CLI:** How to use `ramble` commands to perform tasks.
*   **Writing Configs:** Understanding the YAML syntax and available sections for `ramble.yaml` and other config files.
*   **Setting up a workspace:** Users often start by creating a Ramble workspace using `ramble workspace create`.
*   **Defining software:** Software requirements are specified in YAML configuration files, often leveraging Spack specs.
*   **Running experiments:** How to launch, monitor, and manage experiment sets.
*   **Creating new Components:** How to write new Application, Modifier, or other object definitions using Ramble's Python-based definition structure.
*   **Troubleshooting:** Issues related to software builds with Spack, configuration errors, or execution problems.

### Running a Simple Test Experiment

This workflow details how to create a workspace, configure it for a single experiment with a specific workload, and then run and analyze the experiment. This is a common task for quickly testing the Ramble environment.

1.  **Create an empty workspace:**
    ```bash
    ramble workspace create -d <workspace_name>
    ```
    *   The `-d` flag is important, as it creates an empty workspace directory.

2.  **Add the experiment with a specific workload:**
    ```bash
    ramble -D <workspace_name> workspace manage experiments <application_name> --workload-filter <workload_name>
    ```
    *   Replace `<application_name>` with the application you want to test (e.g., `hostname`).
    *   Replace `<workload_name>` with the specific workload for that application (e.g., `local`).
    *   The `-D <workspace_name>` flag directs the command to the correct workspace without needing to activate it globally.

3.  **Verify the experiment configuration:**
    ```bash
    ramble -D <workspace_name> workspace info
    ```
    *   This command should show that only the `<application_name>.<workload_name>.generated` experiment is configured.

4.  **Set up the workspace:**
    ```bash
    ramble -D <workspace_name> workspace setup
    ```
    *   This step generates the necessary scripts and files for the experiment to run.

5.  **Run the experiment:**
    ```bash
    ramble -D <workspace_name> on
    ```

6.  **Analyze the results:**
    ```bash
    ramble -D <workspace_name> workspace analyze
    ```

7.  **View the results:**
    ```bash
    cat <workspace_name>/results.latest.txt
    ```


## Guidance for AI Agents

*   When Ramble and software are mentioned together, a package manager like Spack is likely involved in the software installation process.
*   Refer to the official Ramble documentation on Read the Docs as the primary source of truth for Ramble-specific questions.
*   Refer to the official Spack documentation for questions about Spack usage, syntax, and concepts.
*   Direct users to the **Developer Guides** when they ask about creating new object types, and explain that definitions are Python classes using a structure defined in `ramble.language`.
*   Point users to the **Command Reference** for CLI usage questions.
*   For configuration questions, guide users to the **Configuration Files** and **Workspace Configuration File** sections of the Ramble documentation.
*   Use the examples in the GitHub repository to understand common configuration patterns.
* Encourage users to provide their Ramble configuration files and any error messages for debugging.
* When making Python code changes, consult `bin/ramble` to determine the officially supported Python versions.
* Ensure all Python code is compatible with the full range of supported versions. Avoid using APIs that have been deprecated or removed in newer Python versions. When necessary, use feature detection (`hasattr`) or version checks (`sys.version_info`) to maintain broad compatibility.
* **Implementing Directives & Mock Tests**: When adding new directives (which are processed by `DirectiveMeta` in `ramble.language`), keep in mind that directives are processed lazily based on the module namespace. If you create a mock class inside a unit test to test a directive, you **must** explicitly set its `__module__` attribute to a valid Ramble namespace (e.g. `__module__ = "ramble.app"` or `__module__ = "ramble.mod"`). Without this, `DirectiveMeta` will silently skip processing the directives for your test class.
* **Mock Objects and Style Checks**: When creating mock applications or modifiers (e.g., in `var/ramble/repos/builtin.mock/`), ensure these files contain valid Python syntax and conform to Ramble's style guide (including copyright headers). The `ramble style` command runs on the entire repository, and poorly formatted or syntactically invalid mock files will cause the style checker to fail.


## Running Unit Tests

Ramble uses `pytest` for its unit tests. Tests **must** be run using the `ramble unit-test` wrapper command, not by invoking `pytest` directly, as the wrapper handles necessary test environment setup.

*   **Running all tests in parallel:** The `-n auto` option enables parallel test execution:
    ```bash
    ramble unit-test -n auto
    ```

*   **Running all tests serially:** For troubleshooting or if `pytest-xdist` is unavailable:
    ```bash
    ramble unit-test
    ```

*   **Passing Pytest Arguments:** You can pass any `pytest` arguments to the command. For example, to only run tests with "gromacs" in their name:
    ```bash
    ramble unit-test -k gromacs
    ```

Using `-k` is particularly useful for running only newly added tests.

*   **Writing Unit Tests & Using Test Fixtures**:
    *   **Prefer `workspace manage` for Experiment & Workspace Setup**: When configuring workspaces in CLI tests, command workflows, or application `test_cases/`, prefer using `workspace manage` subcommands (e.g., `workspace("manage", "experiments", ...)`, `workspace("manage", "software", ...)`, `workspace("manage", "modifiers", ...)`, `workspace("manage", "filter-groups", ...)`) or `setup.yaml` instead of manually writing raw YAML strings to `ramble.yaml`. Use `-V <variant>=<value>` (e.g., `-V package_manager=spack`) rather than deprecated flags like `-p` or `--wm`.
    *   **Workspace Creation Fixture**: When a test requires programmatic raw configuration fixtures, **ALWAYS** use the `make_workspace_from_config` fixture from `conftest.py`. Avoid manually creating workspace directories via `tmpdir` or writing YAML files manually.
    *   **`make_workspace_from_config(config_str=None, name=None, activate=False)`**:
        *   Accepts a raw YAML configuration string (`config_str`) defining the `ramble:` dictionary.
        *   Automatically isolates workspace files under `mutable_mock_workspace_path` and mocks configuration scopes (`mutable_config`).
        *   Returns `(ws, ws_name)` where `ws` is the `ramble.workspace.Workspace` object and `ws_name` is the string name of the workspace (auto-generated from test function name if `name` is omitted).
        *   Pass `activate=True` if the test requires an activated workspace environment (`ramble.workspace.activate(ws)`).
        *   *Example*:
            ```python
            def test_my_workspace_feature(make_workspace_from_config):
                test_config = """
            ramble:
              variables:
                mpi_command: 'mpirun -n {n_ranks}'
              applications:
                hostname:
                  workloads:
                    local:
                      experiments:
                        test_exp: {}
            """
                ws, ws_name = make_workspace_from_config(test_config, activate=True)
                # Test logic using ws or ws_name
            ```
    *   **Other Fixtures**: Look up available fixtures in `conftest.py` for other testing needs (such as configuration overrides, mock executables, or mock repositories).

*   **Getting Help:**
    *   For help with the `ramble unit-test` command itself: `ramble unit-test --help`
    *   For a full list of all available `pytest` options: `ramble unit-test --pytest-help`

## Running Style Checks

Ramble uses `isort`, `black`, `flake8`, `mypy`, and `ruff` to enforce a consistent code style and type safety. You can check and fix style issues using the `ramble style` command.

*   **Checking for Style Errors:** To check for any style violations in the files you've changed in your current branch:
    ```bash
    ramble style
    ```
    To check all files in the project, use the `--all` flag:
    ```bash
    ramble style --all
    ```

*   **Fixing Style Errors:** To automatically fix any style errors in your changed files:
    ```bash
    ramble style --fix
    ```
    To fix all files in the project, combine `--all` and `--fix`:
    ```bash
    ramble style --all --fix
    ```

*   **Advanced Usage:** You can also specify which styling tools to run or skip. For example, to only run `isort` and `black`:
    ```bash
    ramble style -t isort -t black
    ```
    To skip `flake8` and `mypy`:
    ```bash
    ramble style -s flake8 -s mypy
    ```
