---
name: ramble-repo-version-updater
description: "Update known versions of Ramble repository objects (applications, modifiers, etc.) by discovering new versions from package managers (e.g., Spack), auditing upstream changes for breaking differences (CLI syntax, workloads, FOM regexes, datasets, dependencies), applying version updates, and implementing conditional `with when()` directives to preserve backwards compatibility."
---

# Ramble Repo Object Version Updater

This skill guides you through the end-to-end process of updating known versions of Ramble repository objects (applications, base applications, modifiers, and package managers). 

Beyond merely appending new version numbers or updating package manager recipes, your primary responsibility is to **perform a rigorous breakage and compatibility audit**: investigating upstream changes (CLI arguments, benchmark workflows, output formats, dataset requirements, and dependencies) and implementing conditional `with when(...)` blocks in the object definition to ensure seamless execution across all supported versions.

---

## Core Workflow & Procedure

```mermaid
flowchart TD
    A[1. Identify Target Object & Definition] --> B[2. Discover New Upstream & Package Versions]
    B --> C[3. Audit Upstream Changes & Potential Breakages]
    C --> D[4. Update Object Definition & Apply when() Handling]
    D --> E[5. Validate Object Loading & Definitions]
    E --> F[6. Test Workspace Rendering & Run Dry-Runs]
    F --> G[7. Run Unit Tests & Style Checks]
```

---

### Step 1: Identify Target Object and Current Definition

1. **Locate the Definition File**:
   - Built-in Applications: `var/ramble/repos/builtin/applications/<name>/application.py`
   - Built-in Modifiers: `var/ramble/repos/builtin/modifiers/<name>/modifier.py`
   - External Repo Objects: `<repo_path>/applications/<name>/application.py`
2. **Inspect Current Capabilities via CLI**:
   - Run `ramble info -v <name>` to inspect:
     - Currently registered versions (and which is marked `preferred=True`).
     - Defined workloads and workload groups.
     - Workload variables, defaults, and allowed values (`values=[...]`).
     - Executables, command templates, and MPI usage.
     - Figures of Merit (FOM) regex patterns, units, and contexts.
     - Success criteria and verification strings.
     - Software specs, required packages, and compilers.

---

### Step 2: Discover Available Versions from Package Managers & Upstream

1. **Query Package Managers**:
   - **Spack Packages**:
     - Check local Spack recipes: `packages/<name>/package.py` or `spack info <name>`.
     - Inspect `version(...)` lines, checksums, git branches, and tags.
     - Note any version-dependent variants, dependencies (`depends_on(...)`), or patches.
   - **Python / Pip Packages**:
     - Check PyPI releases or `requirements.txt` / `pyproject.toml` in upstream repos.
   - **EESSI / EasyBuild**:
     - Check available module software versions and toolchains (e.g., `foss-2023b`).
2. **Examine Upstream Source & Release Channels**:
   - Find the upstream homepage/repository (often listed in the application's docstring or Spack's `homepage` / `git` attributes).
   - Check GitHub/GitLab Releases, Git tags, changelogs (`CHANGELOG.md`, `NEWS`, `RELEASENOTES.md`), and commit logs between the old and new version tags.

---

### Step 3: Upstream Change & Breakage Audit Checklist

Before editing the Ramble definition, perform a systematic audit comparing the new version with existing versions against each dimension:

| Area | What to Inspect | Potential Breaking Change | Ramble Mitigation |
| :--- | :--- | :--- | :--- |
| **CLI & Binary Names** | Executable binary names, subcommands, and flags | Binary renamed (e.g., `app_win` vs `app64_win`), changed flag syntax (e.g., `-n` replaced with `-np`, `-dlb` format changed), positional arguments reordered | `with when("@<new_ver>:"):` on `executable(...)` |
| **Workloads & Workload Groups** | Workload names, supported test cases, datasets | New benchmark mode added (e.g., convolution in heFFTe 2.2.0), obsolete workload removed | `with when("@<new_ver>:"):` on `workload(...)` and `workload_group(...)` |
| **Workload Variables** | Variable defaults, valid values | New configuration parameter required, flag values changed (e.g., backend solver options) | `with when("@<new_ver>:"):` on `workload_variable(...)` |
| **Input Files & Templates** | Input deck syntax, benchmark datasets | Input deck format changed, benchmark dataset URL/hash updated | `with when("@<new_ver>:"):` on `input_file(...)` or `register_template(...)` |
| **Environment Variables** | Runtime env vars (OpenSHMEM, OFI, OpenMP, CUDA) | Deprecated environment variable, new mandatory tuning parameter | `with when("@<new_ver>:"):` on `environment_variable(...)` |
| **Figures of Merit (FOMs)** | stdout / stderr / log file output format | Output text changed (e.g., `Time: 1.23s` -> `Elapsed Time (s): 1.23`), units changed (ms to s, GFlops to TFlops) | `with when("@<new_ver>:"):` on `figure_of_merit(...)` |
| **Success Criteria** | Verification strings & exit indicators | Verification message wording updated (e.g., `PASSED` -> `Verification Successful`) | `with when("@<new_ver>:"):` on `success_criteria(...)` |
| **Dependencies & Compilers** | Required language standard, MPI backend, libraries | Upstream now requires C++17/C++20 (needs newer GCC/Clang compiler spec), or new required library | `with when("@<new_ver>:"):` on `define_compiler(...)` or `software_spec(...)` |

---

### Step 4: Update Object Definition & Apply `when()` Handling

#### 1. Add Version Directives
- Declare new versions using the `version(...)` directive in the class body. In Ramble, `preferred` defaults to `False`, so omit `preferred=False` and only specify `preferred=True` on the single version designated as the default:
  ```python
  version("2026.0", description="Version 2026.0 of Gromacs")
  version("2025.3", description="Version 2025.3 of Gromacs", preferred=True)
  ```
- Never specify `preferred=False` explicitly. Only specify `preferred=True` if designating or updating the recommended default version.

#### 2. Update Software Specifications
- **Parameterized Specs**: If using the Ramble templating syntax (e.g., `software_spec("app-{application::app::version}", pkg_spec="app@{application::app::version}")`), verify whether the spec remains valid for the new version.
- **Explicit Version Specs**: If specs are version-specific or require different dependencies:
  ```python
  with when("package_manager_family=spack"):
      with when("@2.2.0:"):
          software_spec(
              "heffte",
              pkg_spec="heffte@2.2.0: +fftw +cuda",
              compiler="gcc14",
          )
      with when("@:2.1.0"):
          software_spec(
              "heffte",
              pkg_spec="heffte@:2.1.0 +fftw",
              compiler="gcc11",
          )
  ```

#### 3. Conditionalize Changed Directives with `when()`
Use `with when("@<version_spec>"):` blocks or inline `when=[...]` arguments.

> [!IMPORTANT]
> **Ramble Version Spec Syntax in `when()`**:
> - `@2.2.0:` : Version 2.2.0 and newer ($\ge 2.2.0$)
> - `@:2.1.0` : Version 2.1.0 and older ($\le 2.1.0$)
> - `@1.2.0:2.0.0` : Version range ($1.2.0 \le v \le 2.0.0$)
> - `@2.2.0` : Exact version ($== 2.2.0$)

##### Example: Conditional Executables and Workloads
```python
# Legacy executable for older versions
with when("@:2.1.0"):
    executable(
        "speed3d",
        "{heffte_path}/bin/speed3d {fft} {dim_x} {dim_y} {dim_z}",
        use_mpi=True,
    )
    workload("speed3d", executables=["speed3d"])

# New executables and workloads added in 2.2.0+
with when("@2.2.0:"):
    executable(
        "convolution",
        "{heffte_path}/share/heffte/benchmarks/convolution {fft} {precision} {dim_x} {dim_y} {dim_z} -{reorder} -n{num_runs}",
        use_mpi=True,
    )
    workload("convolution", executables=["convolution"])
```

##### Example: Conditional Workload Groups
```python
with when("@:2.1.0"):
    workload_group("all_workloads", workloads=["c2c", "r2c"])

with when("@2.2.0:"):
    workload_group("all_workloads", workloads=["c2c", "r2c", "convolution", "r2r"])
```

##### Example: Conditional Figures of Merit and Regexes
```python
with when("@:5.0"):
    figure_of_merit(
        "bandwidth",
        fom_regex=r"Bandwidth:\s+(?P<bw>[0-9.]+)\s+MB/s",
        group_name="bw",
        units="MB/s",
    )

with when("@5.1:"):
    figure_of_merit(
        "bandwidth",
        fom_regex=r"Aggregate Bandwidth:\s+(?P<bw>[0-9.]+)\s+GB/s",
        group_name="bw",
        units="GB/s",
    )
```

---

### Step 5: Validate and Verify with Ramble Tooling

Always validate your changes using Ramble's built-in commands:

1. **Verify Object Definition and Verbose Rendering**:
   ```bash
   ramble info -v <object_name>
   ```
   - Verify that all versions, workloads, executables, variables, FOMs, and software specs render cleanly without exceptions.

2. **Verify Software Spec Consistency**:
   ```bash
   ramble software-definitions --summary
   ramble software-definitions --conflicts
   ```
   - Ensure the new software spec introduces no package naming or version conflicts.

3. **Dry-Run Workspace Verification**:
   - Create a test workspace to verify concretization and experiment generation across both old and new versions:
   ```bash
   # Create a temporary workspace
   ramble workspace create -d /tmp/test_ws
   
   # Test experiment with the new version
   ramble -D /tmp/test_ws workspace manage experiments <app_name> --workload-filter <workload>
   
   # Validate experiment info
   ramble -D /tmp/test_ws workspace info
   
   # Test dry-run setup
   ramble -D /tmp/test_ws workspace setup --dry-run
   ```

4. **Run Unit Tests**:
   - Execute Ramble's test suite, filtering for the target application:
   ```bash
   ramble unit-test -k <app_name>
   ```
   - If unit tests for the application exist in `lib/ramble/ramble/test/`, add test cases covering the new version or updated workloads.

---

### Step 6: Code Style & Formatting

Ensure all modified files strictly comply with Ramble repository standards:

1. **Run Style Checks**:
   ```bash
   ramble style <path_to_modified_file>
   ```
2. **Automatically Fix Style Issues**:
   ```bash
   ramble style --fix <path_to_modified_file>
   ```
3. **Check License & Copyright Headers**:
   - Ensure the top of the file contains the valid SPDX Apache-2.0 / MIT header with current year range (e.g., `# Copyright 2022-2026 The Ramble Authors` or Google LLC where appropriate).
4. **Update Docstrings & URLs**:
   - Ensure homepage, upstream URLs, and application documentation links in the class docstring are current.

---

## Common Patterns & Reference Solutions

### Pattern 1: Parameterized Version with Package-Manager-Specific Specs
```python
version("2026.0", description="Version 2026.0 of Gromacs")
version("2025.3", description="Version 2025.3 of Gromacs", preferred=True)

with when("package_manager_family=spack"):
    define_compiler("gcc14", pkg_spec="gcc@14.2.0")

    with default_args(compiler="gcc14"):
        software_spec(
            "gromacs-{application::gromacs::version}",
            pkg_spec="gromacs@{application::gromacs::version}",
        )

# Fixed EESSI software spec for specific version
software_spec(
    "gromacs-2024.1",
    pkg_spec="GROMACS/2024.1-foss-2023b",
    when=["package_manager_family=eessi", "application_version=2024.1"],
)
```

### Pattern 2: Modifiers with Version-Specific Flags
```python
version("3.4.6", description="Version 3.4.6 of Darshan", preferred=True)
version("3.3.1", description="Version 3.3.1 of Darshan")

with when("package_manager_family=spack"):
    software_spec(
        "darshan-runtime-{modifier_version}",
        pkg_spec="darshan-runtime@{modifier_version} +mpi",
    )
```

### Pattern 3: Workload Variable Default Change Across Versions
```python
with when("@:2.0.0"):
    workload_variable(
        "solver_backend",
        default="legacy_cpu",
        values=["legacy_cpu", "openmp"],
        workload_group="all_workloads",
    )

with when("@2.1.0:"):
    workload_variable(
        "solver_backend",
        default="hybrid_omp",
        values=["hybrid_omp", "cuda", "rocm"],
        workload_group="all_workloads",
    )
```

---

## Agent Execution Checklist

Before concluding any version update task, verify:
- [ ] New versions discovered from package manager (e.g. Spack recipe) and upstream repository.
- [ ] Upstream changelog, release notes, and diff audited for CLI, workload, FOM, and dataset differences.
- [ ] `version(...)` directives added; `preferred=True` specified only when setting the default version (never add `preferred=False`).
- [ ] `with when("@<version_spec>"):` conditions applied to any divergent executables, workloads, variables, input files, or FOMs.
- [ ] Backwards compatibility with older supported versions verified.
- [ ] `ramble info -v <name>` executes successfully and renders all workloads and versions.
- [ ] `ramble software-definitions --conflicts` passes without errors.
- [ ] `ramble unit-test -k <name>` passes.
- [ ] `ramble style <path>` passes without style or lint violations.
