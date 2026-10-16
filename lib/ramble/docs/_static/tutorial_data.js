window.RAMBLE_TUTORIAL_DATA = {
  "tutorials": {
    "ramble_basics": {
      "title": "Ramble Basics",
      "url": "tutorials/beginner_ramble_basics.html",
      "level": "Beginner",
      "duration": "10 min",
      "description": "Learn Ramble's introductory CLI commands including help, listing objects, exploring attributes, inspecting object details, software definitions, and configuration.",
      "order_rank": 5
    },
    "hello_world": {
      "title": "Hello World",
      "url": "tutorials/beginner_hello_world.html",
      "level": "Beginner",
      "duration": "5 min",
      "description": "Create a workspace, configure a simple hostname experiment, set up, execute, and analyze results.",
      "order_rank": 10,
      "default_workspace_name": "hello_world"
    },
    "workspace_manage_cmd": {
      "title": "Workspace Manage Experiments Command",
      "url": "tutorials/beginner_workspace_manage_experiments_command.html",
      "level": "Beginner",
      "duration": "10 min",
      "description": "Add, modify, and manage experiments across workloads using the CLI.",
      "order_rank": 15,
      "default_workspace_name": "manage-workspace",
      "workspace_dir_mode": true
    },
    "single_experiment": {
      "title": "Creating a Single Experiment Workspace",
      "url": "tutorials/beginner_creating_a_single_experiment_workspace.html",
      "level": "Beginner",
      "duration": "10 min",
      "dry_run_duration": "5 min",
      "description": "Execute a multi-node experiment and analyze figures of merit.",
      "order_rank": 20,
      "default_workspace_name": "tutorial-workspace-{app}"
    },
    "modify_experiment": {
      "title": "Modifying an Existing Experiment",
      "url": "tutorials/beginner_modifying_an_experiment.html",
      "level": "Beginner",
      "duration": "10 min",
      "dry_run_duration": "5 min",
      "description": "Override workload variables, customize commands, and adjust experiment configurations.",
      "order_rank": 30,
      "default_workspace_name": "tutorial-workspace-{app}",
      "reuses_workspace_from": "single_experiment"
    },
    "vectors_matrices": {
      "title": "Using Vectors and Matrices",
      "url": "tutorials/beginner_using_vectors_and_matrices.html",
      "level": "Beginner",
      "duration": "15 min",
      "dry_run_duration": "8 min",
      "description": "Explore parameter spaces and generate combinatorial experiments with vectors and matrices.",
      "order_rank": 40,
      "default_workspace_name": "tutorial-workspace-{app}",
      "reuses_workspace_from": "single_experiment"
    },
    "software_stack": {
      "title": "Changing Your Software Stack",
      "url": "tutorials/intermediate_changing_your_software_stack.html",
      "level": "Intermediate",
      "duration": "20 min",
      "dry_run_duration": "10 min",
      "description": "Explore the impact of changing the software stack used in an experiment.",
      "order_rank": 100,
      "default_workspace_name": "tutorial-workspace-{app}",
      "reuses_workspace_from": "single_experiment"
    },
    "scaling_study": {
      "title": "Configuring a Scaling Study",
      "url": "tutorials/intermediate_configuring_a_scaling_study.html",
      "level": "Intermediate",
      "duration": "25 min",
      "dry_run_duration": "10 min",
      "description": "Set up scaling experiments from an existing experiment.",
      "order_rank": 110,
      "default_workspace_name": "tutorial-workspace-{app}",
      "reuses_workspace_from": "single_experiment"
    },
    "success_criteria": {
      "title": "Success Criteria",
      "url": "tutorials/intermediate_success_criteria.html",
      "level": "Intermediate",
      "duration": "15 min",
      "dry_run_duration": "8 min",
      "description": "Define automated pass/fail validation rules and ensure benchmark data integrity.",
      "order_rank": 120,
      "default_workspace_name": "tutorial-workspace-{app}",
      "reuses_workspace_from": "single_experiment"
    },
    "modifiers": {
      "title": "Using Modifiers",
      "url": "tutorials/intermediate_using_modifiers.html",
      "level": "Intermediate",
      "duration": "25 min",
      "dry_run_duration": "10 min",
      "description": "Inject profilers (Intel-APS, perf, hpctoolkit, etc.), monitors, and execution hooks across experiments.",
      "order_rank": 130,
      "default_workspace_name": "tutorial-workspace-{app}",
      "reuses_workspace_from": "single_experiment"
    },
    "mirrors": {
      "title": "Managing Mirrors",
      "url": "tutorials/intermediate_mirrors.html",
      "level": "Intermediate",
      "duration": "15 min",
      "description": "Create and manage offline mirrors for software tarballs and experiment input files.",
      "order_rank": 190,
      "default_workspace_name": "wrf_mirror_test"
    },
    "eessi": {
      "title": "EESSI Package Manager",
      "url": "tutorials/intermediate_eessi_package_manager.html",
      "level": "Intermediate",
      "duration": "15 min",
      "dry_run_duration": "8 min",
      "description": "Leverage pre-optimized scientific software from the EESSI repository in your workspaces.",
      "order_rank": 199,
      "default_workspace_name": "eessi_gromacs"
    },
    "zips_matrices": {
      "title": "Using Zips and Matrices",
      "url": "tutorials/advanced_using_zips_and_matrices.html",
      "level": "Advanced",
      "duration": "20 min",
      "dry_run_duration": "10 min",
      "description": "Learn to couple parameters across multi-dimensional grids without full Cartesian explosion.",
      "order_rank": 200,
      "default_workspace_name": "tutorial-workspace-{app}",
      "reuses_workspace_from": "single_experiment"
    },
    "var_expansion": {
      "title": "Variable Expansion, Indirection & Software Stack Parameterization",
      "url": "tutorials/advanced_var_expansion_indirection_and_stack_parameterization.html",
      "level": "Advanced",
      "duration": "20 min",
      "dry_run_duration": "10 min",
      "description": "Leverage dynamic variable evaluation, double-indirection, and parameterization of software stacks.",
      "order_rank": 210,
      "default_workspace_name": "tutorial-workspace-{app}",
      "reuses_workspace_from": "single_experiment"
    },
    "internals": {
      "title": "Using Internals",
      "url": "tutorials/advanced_using_internals.html",
      "level": "Advanced",
      "duration": "15 min",
      "dry_run_duration": "8 min",
      "description": "Learn to manipulate internal experiment aspects using workspace configuration files.",
      "order_rank": 220,
      "default_workspace_name": "internals_{app}"
    },
    "workspace_config_cmd": {
      "title": "Workspace Config Command",
      "url": "tutorials/advanced_workspace_config_command.html",
      "level": "Advanced",
      "duration": "10 min",
      "description": "Nesting configuration files (includes), squashing, and simplifying workspace configuration files.",
      "order_rank": 290,
      "default_workspace_name": "includes-workspace",
      "workspace_dir_mode": true
    },
    "dev_basic_app": {
      "title": "Basic Application Definition",
      "url": "tutorials/developer_basic_application_definition_tutorial.html",
      "level": "Developer",
      "duration": "30 min",
      "dry_run_duration": "20 min",
      "description": "Author new Python application definitions using Ramble directives, executables, and workloads.",
      "order_rank": 300,
      "default_workspace_name": "tutorial-workspace",
      "workspace_dir_mode": true,
      "default_repo_name": "tutorial-repo"
    },
    "dev_hpl_app": {
      "title": "HPL Application Definition",
      "url": "tutorials/developer_hpl_application_definition_tutorial.html",
      "level": "Developer",
      "duration": "30 min",
      "dry_run_duration": "18 min",
      "description": "Develop complex definitions featuring template generation, FOM extractors, and software specs.",
      "order_rank": 310,
      "default_workspace_name": "tutorial-workspace",
      "workspace_dir_mode": true,
      "reuses_workspace_from": "dev_basic_app",
      "default_repo_name": "tutorial-repo",
      "reuses_repo_from": "dev_basic_app"
    },
    "dev_system_platform": {
      "title": "System and Platform Definitions",
      "url": "tutorials/developer_system_and_platform_definition_tutorial.html",
      "level": "Developer",
      "duration": "25 min",
      "description": "Define system topologies and platform specifications for multi-architecture deployments.",
      "order_rank": 320,
      "default_workspace_name": "test-sys-plat",
      "workspace_dir_mode": true,
      "default_repo_name": "tutorial-repo"
    },
    "dev_utility": {
      "title": "Utility Definition Tutorial",
      "url": "tutorials/developer_utility_definition_tutorial.html",
      "level": "Developer",
      "duration": "20 min",
      "description": "Build reusable utility objects to share execution logic across applications.",
      "order_rank": 330,
      "default_repo_name": "tutorial-repo",
      "reuses_repo_from": "dev_system_platform"
    }
  },
  "goals": {
    "ramble_front_end": {
      "title": "I want to learn Ramble's front-end commands for creating experiment definitions",
      "icon": "\ud83d\udcbb",
      "description": "Learn the basics of Ramble, and how to utilize front-end commands for creating experiments",
      "tutorials": [
        "ramble_basics",
        "hello_world",
        "workspace_manage_cmd"
      ]
    },
    "scaling_study": {
      "title": "I want to perform a scaling study with an existing experiment",
      "icon": "\ud83d\udcc8",
      "description": "Learn to scale applications using vectors and matrices.",
      "tutorials": [
        "ramble_basics",
        "hello_world",
        "single_experiment",
        "modify_experiment",
        "vectors_matrices",
        "scaling_study"
      ]
    },
    "profiling_modifiers": {
      "title": "I want to analyze the performance of my experiments",
      "icon": "\u23f1\ufe0f",
      "description": "Learn how to configure experiments, and apply modifiers to manipulate their behavior. Including injecting profilers.",
      "tutorials": [
        "ramble_basics",
        "hello_world",
        "single_experiment",
        "modify_experiment",
        "scaling_study",
        "modifiers"
      ]
    },
    "software_management": {
      "title": "I want to explore changes to my experiment's software stack",
      "icon": "\ud83d\udce6",
      "description": "Learn to manipulate the software stack used within a workspace's experiments",
      "tutorials": [
        "ramble_basics",
        "hello_world",
        "single_experiment",
        "software_stack"
      ]
    },
    "package_manager_changes": {
      "title": "I want to experiment with different package managers",
      "icon": "\ud83e\uddf0",
      "description": "Learn to use different package managers within a workspace's experiments",
      "tutorials": [
        "ramble_basics",
        "hello_world",
        "single_experiment",
        "software_stack",
        "eessi"
      ]
    },
    "metrics_validation": {
      "title": "I want to validate some aspect of my system",
      "icon": "\ud83c\udfaf",
      "description": "Learn to use success criteria to automate benchmark validation, assert exit criteria, and verify figure-of-merit thresholds.",
      "tutorials": [
        "ramble_basics",
        "hello_world",
        "single_experiment",
        "scaling_study",
        "success_criteria"
      ]
    },
    "parameter_sweeps": {
      "title": "I want to explore a complex parameter for my workload",
      "icon": "\ud83c\udf9b\ufe0f",
      "description": "Learn how to define multi-dimensional parameter exploration, zip variables, and use indirection to create the experimental study you want.",
      "tutorials": [
        "ramble_basics",
        "hello_world",
        "single_experiment",
        "vectors_matrices",
        "zips_matrices",
        "var_expansion",
        "internals"
      ]
    },
    "ramble_config_indirection": {
      "title": "I want to learn more advanced techniques for manipulating workspace configuration files.",
      "icon": "\ud83e\udde9",
      "description": "Learn how workspace indirection (includes) works, how to squash indirection out, and how to simplify aspects of a workspace.",
      "tutorials": [
        "workspace_config_cmd"
      ]
    },
    "author_applications": {
      "title": "I want to create a new experiment from a workload that does not exist in Ramble already",
      "icon": "\ud83d\udee0\ufe0f",
      "description": "Extend Ramble by writing custom application classes, defining executables, workloads, and FOMs.",
      "tutorials": [
        "ramble_basics",
        "hello_world",
        "single_experiment",
        "dev_basic_app",
        "dev_hpl_app"
      ]
    },
    "author_infrastructure": {
      "title": "I want to add support for my system into Ramble, including defining external dependencies",
      "icon": "\u2699\ufe0f",
      "description": "Write reusable object definitions including system classes (clusters), platform classes (compute nodes), and utility classes (external / bootstrapped dependencies).",
      "tutorials": [
        "ramble_basics",
        "hello_world",
        "dev_utility",
        "dev_system_platform"
      ]
    },
    "offline_mirrors": {
      "title": "I want to create a mirror of the software and inputs used within my experiments",
      "icon": "\ud83e\ude9e",
      "description": "Cache software source tarballs and input datasets to backup or run experiments without internet access.",
      "tutorials": [
        "ramble_basics",
        "hello_world",
        "mirrors"
      ]
    }
  },
  "recipes": {
    "using_internals": {
      "title": "Internals",
      "mode": "selectable",
      "default_app": "wrf",
      "apps": {
        "wrf": {
          "name": "WRF",
          "workload": "CONUS_12km",
          "description": "Weather Research and Forecasting atmospheric model",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create internals_wrf",
              "in_commands_sh": false
            },
            {
              "display": "$ ramble workspace activate internals_wrf"
            },
            {
              "display": "$ ramble workspace edit"
            }
          ],
          "snippets": {
            "base": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n",
            "new_exec": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}:\n              internals:\n                custom_executables:\n                  start_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/start_time'\n                    use_mpi: false\n                  end_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/end_time'\n                    use_mpi: false\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n",
            "exec_order": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}:\n              internals:\n                custom_executables:\n                  start_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/start_time'\n                    use_mpi: false\n                  end_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/end_time'\n                    use_mpi: false\n                executables:\n                - builtin::env_vars\n                - package_manager_builtin::spack::spack_source\n                - package_manager_builtin::spack::spack_activate\n                - stage-files\n                - stage-namelist\n                - cleanup\n                - define_nproc_y\n                - define_nproc_x\n                - fix_12km_start_hour\n                - fix_12km_restart\n                - start_time\n                - execute\n                - end_time\n                - copy-logs\n                - post-exec-clean\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n",
            "exec_injection": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}:\n              internals:\n                custom_executables:\n                  start_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/start_time'\n                    use_mpi: false\n                  end_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/end_time'\n                    use_mpi: false\n                executable_injection:\n                - name: start_time\n                  order: before\n                  relative_to: execute\n                - name: end_time\n                  order: after\n                  relative_to: execute\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n",
            "final": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}:\n              internals:\n                custom_executables:\n                  start_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/start_time'\n                    use_mpi: false\n                  end_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/end_time'\n                    use_mpi: false\n                executable_injection:\n                - name: start_time\n                  order: before\n                  relative_to: execute\n                - name: end_time\n                  order: after\n                  relative_to: execute\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n"
          }
        },
        "gromacs": {
          "name": "GROMACS",
          "workload": "water_bare",
          "description": "Molecular dynamics simulation package",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create internals_gromacs",
              "in_commands_sh": false
            },
            {
              "display": "$ ramble workspace activate internals_gromacs"
            },
            {
              "display": "$ ramble workspace edit"
            }
          ],
          "snippets": {
            "base": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    gromacs@2025.3:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n",
            "new_exec": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    gromacs@2025.3:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}:\n              internals:\n                custom_executables:\n                  start_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/start_time'\n                    use_mpi: false\n                  end_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/end_time'\n                    use_mpi: false\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n",
            "exec_order": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    gromacs@2025.3:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}:\n              internals:\n                custom_executables:\n                  start_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/start_time'\n                    use_mpi: false\n                  end_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/end_time'\n                    use_mpi: false\n                executables:\n                - builtin::env_vars\n                - package_manager_builtin::spack::spack_source\n                - package_manager_builtin::spack::spack_activate\n                - print-binary-info\n                - pre-process\n                - start_time\n                - execute-gen\n                - end_time\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n",
            "exec_injection": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    gromacs@2025.3:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}:\n              internals:\n                custom_executables:\n                  start_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/start_time'\n                    use_mpi: false\n                  end_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/end_time'\n                    use_mpi: false\n                executable_injection:\n                - name: start_time\n                  order: before\n                  relative_to: execute-gen\n                - name: end_time\n                  order: after\n                  relative_to: execute-gen\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n",
            "final": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    gromacs@2025.3:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}:\n              internals:\n                custom_executables:\n                  start_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/start_time'\n                    use_mpi: false\n                  end_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/end_time'\n                    use_mpi: false\n                executable_injection:\n                - name: start_time\n                  order: before\n                  relative_to: execute-gen\n                - name: end_time\n                  order: after\n                  relative_to: execute-gen\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n"
          }
        },
        "hpl": {
          "name": "HPL",
          "workload": "calculator",
          "description": "High-Performance Linpack benchmark",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create internals_hpl",
              "in_commands_sh": false
            },
            {
              "display": "$ ramble workspace activate internals_hpl"
            },
            {
              "display": "$ ramble workspace edit"
            }
          ],
          "snippets": {
            "base": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    hpl:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@2.3 +openmp\n        compiler: gcc14\n    environments:\n      hpl:\n        packages:\n        - intel-mpi\n        - hpl\n",
            "new_exec": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    hpl:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}:\n              internals:\n                custom_executables:\n                  start_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/start_time'\n                    use_mpi: false\n                  end_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/end_time'\n                    use_mpi: false\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@2.3 +openmp\n        compiler: gcc14\n    environments:\n      hpl:\n        packages:\n        - intel-mpi\n        - hpl\n",
            "exec_order": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    hpl:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}:\n              internals:\n                custom_executables:\n                  start_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/start_time'\n                    use_mpi: false\n                  end_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/end_time'\n                    use_mpi: false\n                executables:\n                - builtin::env_vars\n                - package_manager_builtin::spack::spack_source\n                - package_manager_builtin::spack::spack_activate\n                - start_time\n                - execute\n                - end_time\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@2.3 +openmp\n        compiler: gcc14\n    environments:\n      hpl:\n        packages:\n        - intel-mpi\n        - hpl\n",
            "exec_injection": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    hpl:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}:\n              internals:\n                custom_executables:\n                  start_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/start_time'\n                    use_mpi: false\n                  end_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/end_time'\n                    use_mpi: false\n                executable_injection:\n                - name: start_time\n                  order: before\n                  relative_to: execute\n                - name: end_time\n                  order: after\n                  relative_to: execute\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@2.3 +openmp\n        compiler: gcc14\n    environments:\n      hpl:\n        packages:\n        - intel-mpi\n        - hpl\n",
            "final": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    hpl:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}:\n              internals:\n                custom_executables:\n                  start_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/start_time'\n                    use_mpi: false\n                  end_time:\n                    template:\n                    - date +%s\n                    redirect: '{experiment_run_dir}/end_time'\n                    use_mpi: false\n                executable_injection:\n                - name: start_time\n                  order: before\n                  relative_to: execute\n                - name: end_time\n                  order: after\n                  relative_to: execute\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@2.3 +openmp\n        compiler: gcc14\n    environments:\n      hpl:\n        packages:\n        - intel-mpi\n        - hpl\n"
          }
        }
      }
    },
    "zips_matrices": {
      "title": "Using Zips and Matrices",
      "mode": "selectable",
      "default_app": "wrf",
      "apps": {
        "wrf": {
          "name": "WRF",
          "workload": "CONUS_12km",
          "description": "Weather Research and Forecasting atmospheric model",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create zips_wrf",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:processes_per_node:[16, 18, 20]"
              ],
              "display": "$ ramble config add 'variables:processes_per_node:[16, 18, 20]'"
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:platform:[platform1, platform2, platform3]"
              ],
              "display": "$ ramble config add 'variables:platform:[platform1, platform2, platform3]'"
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:n_ranks:\"{processes_per_node}*{n_nodes}\""
              ],
              "display": "$ ramble config add 'variables:n_ranks:\"{processes_per_node}*{n_nodes}\"'"
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:mpi_command:mpirun -n {n_ranks}"
              ],
              "display": "$ ramble config add 'variables:mpi_command:mpirun -n {n_ranks}'"
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:batch_submit:\"{execute_experiment}\""
              ],
              "display": "$ ramble config add 'variables:batch_submit:\"{execute_experiment}\"'"
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "wrf",
                "--workload-filter",
                "CONUS_12km",
                "-e",
                "scaling_{n_nodes}_{platform}",
                "-V",
                "package_manager=spack",
                "-v",
                "n_nodes=[1, 2]",
                "--zip",
                "platform_config=[platform,processes_per_node]",
                "-m",
                "platform_config,n_nodes"
              ],
              "display": "$ ramble workspace manage experiments wrf --workload-filter CONUS_12km -e 'scaling_{n_nodes}_{platform}' -V package_manager=spack -v 'n_nodes=[1, 2]' --zip 'platform_config=[platform,processes_per_node]' -m platform_config,n_nodes"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        },
        "gromacs": {
          "name": "GROMACS",
          "workload": "water_bare",
          "description": "Molecular dynamics simulation package",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create zips_gromacs",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:processes_per_node:[16, 18, 20]"
              ],
              "display": "$ ramble config add 'variables:processes_per_node:[16, 18, 20]'"
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:platform:[platform1, platform2, platform3]"
              ],
              "display": "$ ramble config add 'variables:platform:[platform1, platform2, platform3]'"
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:n_ranks:\"{processes_per_node}*{n_nodes}\""
              ],
              "display": "$ ramble config add 'variables:n_ranks:\"{processes_per_node}*{n_nodes}\"'"
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:mpi_command:mpirun -n {n_ranks}"
              ],
              "display": "$ ramble config add 'variables:mpi_command:mpirun -n {n_ranks}'"
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:batch_submit:\"{execute_experiment}\""
              ],
              "display": "$ ramble config add 'variables:batch_submit:\"{execute_experiment}\"'"
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "gromacs",
                "--workload-filter",
                "water_bare",
                "-e",
                "scaling_{n_nodes}_{platform}",
                "-V",
                "package_manager=spack",
                "-v",
                "n_nodes=[1, 2]",
                "--zip",
                "platform_config=[platform,processes_per_node]",
                "-m",
                "platform_config,n_nodes"
              ],
              "display": "$ ramble workspace manage experiments gromacs --workload-filter water_bare -e 'scaling_{n_nodes}_{platform}' -V package_manager=spack -v 'n_nodes=[1, 2]' --zip 'platform_config=[platform,processes_per_node]' -m platform_config,n_nodes"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        },
        "hpl": {
          "name": "HPL",
          "workload": "calculator",
          "description": "High Performance Linpack benchmark",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create zips_hpl",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:processes_per_node:[16, 18, 20]"
              ],
              "display": "$ ramble config add 'variables:processes_per_node:[16, 18, 20]'"
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:platform:[platform1, platform2, platform3]"
              ],
              "display": "$ ramble config add 'variables:platform:[platform1, platform2, platform3]'"
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:n_ranks:\"{processes_per_node}*{n_nodes}\""
              ],
              "display": "$ ramble config add 'variables:n_ranks:\"{processes_per_node}*{n_nodes}\"'"
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:mpi_command:mpirun -n {n_ranks}"
              ],
              "display": "$ ramble config add 'variables:mpi_command:mpirun -n {n_ranks}'"
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:batch_submit:\"{execute_experiment}\""
              ],
              "display": "$ ramble config add 'variables:batch_submit:\"{execute_experiment}\"'"
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "hpl",
                "--workload-filter",
                "calculator",
                "-e",
                "scaling_{n_nodes}_{platform}",
                "-V",
                "package_manager=spack",
                "-v",
                "n_nodes=[1, 2]",
                "-v",
                "memory_per_node=8",
                "--zip",
                "platform_config=[platform,processes_per_node]",
                "-m",
                "platform_config,n_nodes"
              ],
              "display": "$ ramble workspace manage experiments hpl --workload-filter calculator -e 'scaling_{n_nodes}_{platform}' -V package_manager=spack -v 'n_nodes=[1, 2]' -v memory_per_node=8 --zip 'platform_config=[platform,processes_per_node]' -m platform_config,n_nodes"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        }
      }
    },
    "var_expansion": {
      "title": "Variable Expansion, Indirection, and Software Stack Parameterization",
      "mode": "selectable",
      "default_app": "wrf",
      "apps": {
        "wrf": {
          "name": "WRF",
          "workload": "CONUS_12km",
          "description": "Weather Research and Forecasting atmospheric model",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create var_expansion_wrf",
              "in_commands_sh": false
            },
            {
              "display": "$ ramble workspace activate var_expansion_wrf"
            },
            {
              "display": "$ ramble workspace edit"
            }
          ],
          "snippets": {
            "base": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}_{platform}:\n              variables:\n                n_nodes: [1, 2]\n              matrix:\n              - platform_config\n              - n_nodes\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n",
            "mpi": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n    mpi_name: [intel-mpi, openmpi]\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}_{platform}:\n              variables:\n                n_nodes: [1, 2]\n              matrix:\n              - platform_config\n              - n_nodes\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      openmpi:\n        pkg_spec: openmpi@5.0.8\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2-{mpi_name}:\n        packages:\n        - '{mpi_name}'\n        - wrfv4-{application::wrf::version}\n",
            "mpi_matrix": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n    mpi_name: ['intel-mpi', 'openmpi']\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}_{platform}_{mpi_name}:\n              variables:\n                n_nodes: [1, 2]\n                env_name: 'wrf@4.2-{mpi_name}'\n              matrix:\n              - platform_config\n              - n_nodes\n              - mpi_name\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      openmpi:\n        pkg_spec: openmpi@5.0.8\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2-{mpi_name}:\n        packages:\n        - '{mpi_name}'\n        - wrfv4-{application::wrf::version}\n",
            "expansion_indirection": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n\n    # Execution Template\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun {{mpi_name}_args}\n\n    # Experiment Expansions\n    mpi_name: [intel-mpi, openmpi]\n    intel-mpi_args: -n {n_ranks} -ppn {processes_per_node}\n    openmpi_args: --np {n_ranks} --map-by ppr:{processes_per_node}:node -x OMP_NUM_THREADS\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}_{platform}_{mpi_name}:\n              variables:\n                n_nodes: [1, 2]\n                env_name: 'wrf@4.2-{mpi_name}'\n              matrix:\n              - platform_config\n              - n_nodes\n              - mpi_name\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      openmpi:\n        pkg_spec: openmpi@5.0.8\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2-{mpi_name}:\n        packages:\n        - '{mpi_name}'\n        - wrfv4-{application::wrf::version}\n",
            "final": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n\n    # Execution Template\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun {{mpi_name}_args}\n\n    # Experiment Expansions\n    mpi_name: [intel-mpi, openmpi]\n    intel-mpi_args: -n {n_ranks} -ppn {processes_per_node}\n    openmpi_args: --np {n_ranks} --map-by ppr:{processes_per_node}:node -x OMP_NUM_THREADS\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}_{platform}_{mpi_name}:\n              variables:\n                n_nodes: [1, 2]\n                env_name: 'wrf@4.2-{mpi_name}'\n              matrix:\n              - platform_config\n              - n_nodes\n              - mpi_name\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      openmpi:\n        pkg_spec: openmpi@5.0.8\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2-{mpi_name}:\n        packages:\n        - '{mpi_name}'\n        - wrfv4-{application::wrf::version}\n"
          }
        },
        "gromacs": {
          "name": "GROMACS",
          "workload": "water_bare",
          "description": "Molecular dynamics simulation package",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create var_expansion_gromacs",
              "in_commands_sh": false
            },
            {
              "display": "$ ramble workspace activate var_expansion_gromacs"
            },
            {
              "display": "$ ramble workspace edit"
            }
          ],
          "snippets": {
            "base": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    gromacs:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}_{platform}:\n              variables:\n                n_nodes: [1, 2]\n              matrix:\n              - platform_config\n              - n_nodes\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@2025.3\n        compiler: gcc14\n    environments:\n      gromacs:\n        packages:\n        - intel-mpi\n        - gromacs\n",
            "mpi": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n    mpi_name: [intel-mpi, openmpi]\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    gromacs:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}_{platform}:\n              variables:\n                n_nodes: [1, 2]\n              matrix:\n              - platform_config\n              - n_nodes\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      openmpi:\n        pkg_spec: openmpi@5.0.8\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@2025.3\n        compiler: gcc14\n    environments:\n      gromacs-{mpi_name}:\n        packages:\n        - '{mpi_name}'\n        - gromacs\n",
            "mpi_matrix": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n    mpi_name: ['intel-mpi', 'openmpi']\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    gromacs:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}_{platform}_{mpi_name}:\n              variables:\n                n_nodes: [1, 2]\n                env_name: 'gromacs-{mpi_name}'\n              matrix:\n              - platform_config\n              - n_nodes\n              - mpi_name\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      openmpi:\n        pkg_spec: openmpi@5.0.8\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@2025.3\n        compiler: gcc14\n    environments:\n      gromacs-{mpi_name}:\n        packages:\n        - '{mpi_name}'\n        - gromacs\n",
            "expansion_indirection": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n\n    # Execution Template\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun {{mpi_name}_args}\n\n    # Experiment Expansions\n    mpi_name: [intel-mpi, openmpi]\n    intel-mpi_args: -n {n_ranks} -ppn {processes_per_node}\n    openmpi_args: --np {n_ranks} --map-by ppr:{processes_per_node}:node -x OMP_NUM_THREADS\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    gromacs:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}_{platform}_{mpi_name}:\n              variables:\n                n_nodes: [1, 2]\n                env_name: 'gromacs-{mpi_name}'\n              matrix:\n              - platform_config\n              - n_nodes\n              - mpi_name\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      openmpi:\n        pkg_spec: openmpi@5.0.8\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@2025.3\n        compiler: gcc14\n    environments:\n      gromacs-{mpi_name}:\n        packages:\n        - '{mpi_name}'\n        - gromacs\n",
            "final": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n\n    # Execution Template\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun {{mpi_name}_args}\n\n    # Experiment Expansions\n    mpi_name: [intel-mpi, openmpi]\n    intel-mpi_args: -n {n_ranks} -ppn {processes_per_node}\n    openmpi_args: --np {n_ranks} --map-by ppr:{processes_per_node}:node -x OMP_NUM_THREADS\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    gromacs:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}_{platform}_{mpi_name}:\n              variables:\n                n_nodes: [1, 2]\n                env_name: 'gromacs-{mpi_name}'\n              matrix:\n              - platform_config\n              - n_nodes\n              - mpi_name\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      openmpi:\n        pkg_spec: openmpi@5.0.8\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@2025.3\n        compiler: gcc14\n    environments:\n      gromacs-{mpi_name}:\n        packages:\n        - '{mpi_name}'\n        - gromacs\n"
          }
        },
        "hpl": {
          "name": "HPL",
          "workload": "calculator",
          "description": "High Performance Linpack benchmark",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create var_expansion_hpl",
              "in_commands_sh": false
            },
            {
              "display": "$ ramble workspace activate var_expansion_hpl"
            },
            {
              "display": "$ ramble workspace edit"
            }
          ],
          "snippets": {
            "base": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    hpl:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}_{platform}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n              matrix:\n              - platform_config\n              - n_nodes\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@2.3 +openmp\n        compiler: gcc14\n    environments:\n      hpl:\n        packages:\n        - intel-mpi\n        - hpl\n",
            "mpi": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n    mpi_name: [intel-mpi, openmpi]\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    hpl:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}_{platform}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n              matrix:\n              - platform_config\n              - n_nodes\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      openmpi:\n        pkg_spec: openmpi@5.0.8\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@2.3 +openmp\n        compiler: gcc14\n    environments:\n      hpl-{mpi_name}:\n        packages:\n        - '{mpi_name}'\n        - hpl\n",
            "mpi_matrix": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n    mpi_name: ['intel-mpi', 'openmpi']\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    hpl:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}_{platform}_{mpi_name}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n                env_name: 'hpl-{mpi_name}'\n              matrix:\n              - platform_config\n              - n_nodes\n              - mpi_name\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      openmpi:\n        pkg_spec: openmpi@5.0.8\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@2.3 +openmp\n        compiler: gcc14\n    environments:\n      hpl-{mpi_name}:\n        packages:\n        - '{mpi_name}'\n        - hpl\n",
            "expansion_indirection": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n\n    # Execution Template\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun {{mpi_name}_args}\n\n    # Experiment Expansions\n    mpi_name: [intel-mpi, openmpi]\n    intel-mpi_args: -n {n_ranks} -ppn {processes_per_node}\n    openmpi_args: --np {n_ranks} --map-by ppr:{processes_per_node}:node -x OMP_NUM_THREADS\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    hpl:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}_{platform}_{mpi_name}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n                env_name: 'hpl-{mpi_name}'\n              matrix:\n              - platform_config\n              - n_nodes\n              - mpi_name\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      openmpi:\n        pkg_spec: openmpi@5.0.8\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@2.3 +openmp\n        compiler: gcc14\n    environments:\n      hpl-{mpi_name}:\n        packages:\n        - '{mpi_name}'\n        - hpl\n",
            "final": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    platform: [platform1, platform2]\n    processes_per_node: [16, 18]\n\n    # Execution Template\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun {{mpi_name}_args}\n\n    # Experiment Expansions\n    mpi_name: [intel-mpi, openmpi]\n    intel-mpi_args: -n {n_ranks} -ppn {processes_per_node}\n    openmpi_args: --np {n_ranks} --map-by ppr:{processes_per_node}:node -x OMP_NUM_THREADS\n  zips:\n    platform_config:\n    - platform\n    - processes_per_node\n  applications:\n    hpl:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}_{platform}_{mpi_name}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n                env_name: 'hpl-{mpi_name}'\n              matrix:\n              - platform_config\n              - n_nodes\n              - mpi_name\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      openmpi:\n        pkg_spec: openmpi@5.0.8\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@2.3 +openmp\n        compiler: gcc14\n    environments:\n      hpl-{mpi_name}:\n        packages:\n        - '{mpi_name}'\n        - hpl\n"
          }
        }
      }
    },
    "single_experiment": {
      "title": "Creating a Single Experiment Workspace",
      "mode": "selectable",
      "default_app": "wrf",
      "apps": {
        "wrf": {
          "name": "WRF",
          "workload": "CONUS_12km",
          "description": "Weather Research and Forecasting atmospheric model",
          "commands": [
            {
              "cmd": [
                "info",
                "--attrs",
                "workloads",
                "-v",
                "-p",
                "CONUS_12km",
                "wrf"
              ],
              "display": "$ ramble info --attrs workloads -v -p \"CONUS_12km\" wrf",
              "use_workspace": false,
              "use_pty": true,
              "command_file": "info_workload_cmd.sh",
              "output_file": "info_workload.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "info",
                "--attrs",
                "known_versions,software_specs,compilers",
                "-v",
                "wrf"
              ],
              "display": "$ ramble info --attrs known_versions,software_specs,compilers -v wrf",
              "use_workspace": false,
              "use_pty": true,
              "command_file": "info_software_cmd.sh",
              "output_file": "info_software.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create basic_wrf",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "wrf",
                "--workload-filter",
                "CONUS_12km",
                "-e",
                "single_rank",
                "-V",
                "package_manager=spack",
                "-v",
                "n_ranks=1",
                "-v",
                "n_threads=1"
              ],
              "display": "$ ramble workspace manage experiments wrf --workload-filter CONUS_12km -e single_rank -V package_manager=spack -v n_ranks=1 -v n_threads=1"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        },
        "gromacs": {
          "name": "GROMACS",
          "workload": "water_bare",
          "description": "Molecular dynamics simulation package",
          "commands": [
            {
              "cmd": [
                "info",
                "--attrs",
                "workloads",
                "-v",
                "-p",
                "water_bare",
                "gromacs"
              ],
              "display": "$ ramble info --attrs workloads -v -p \"water_bare\" gromacs",
              "use_workspace": false,
              "use_pty": true,
              "command_file": "info_workload_cmd.sh",
              "output_file": "info_workload.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "info",
                "--attrs",
                "known_versions,software_specs,compilers",
                "-v",
                "gromacs"
              ],
              "display": "$ ramble info --attrs known_versions,software_specs,compilers -v gromacs",
              "use_workspace": false,
              "use_pty": true,
              "command_file": "info_software_cmd.sh",
              "output_file": "info_software.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create basic_gromacs",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "gromacs",
                "--workload-filter",
                "water_bare",
                "-e",
                "single_rank",
                "-V",
                "package_manager=spack",
                "-v",
                "n_ranks=1",
                "-v",
                "n_threads=1",
                "-v",
                "size=0003",
                "-v",
                "type=pme"
              ],
              "display": "$ ramble workspace manage experiments gromacs --workload-filter water_bare -e single_rank -V package_manager=spack -v n_ranks=1 -v n_threads=1 -v size=0003 -v type=pme"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        },
        "hpl": {
          "name": "HPL",
          "workload": "calculator",
          "description": "High-Performance Linpack benchmark",
          "commands": [
            {
              "cmd": [
                "info",
                "--attrs",
                "workloads",
                "-v",
                "-p",
                "calculator",
                "hpl"
              ],
              "display": "$ ramble info --attrs workloads -v -p \"calculator\" hpl",
              "use_workspace": false,
              "use_pty": true,
              "command_file": "info_workload_cmd.sh",
              "output_file": "info_workload.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "info",
                "--attrs",
                "known_versions,software_specs,compilers",
                "-v",
                "hpl"
              ],
              "display": "$ ramble info --attrs known_versions,software_specs,compilers -v hpl",
              "use_workspace": false,
              "use_pty": true,
              "command_file": "info_software_cmd.sh",
              "output_file": "info_software.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create basic_hpl",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "hpl",
                "--workload-filter",
                "calculator",
                "-e",
                "single_rank",
                "-V",
                "package_manager=spack",
                "-v",
                "n_ranks=1",
                "-v",
                "n_threads=1",
                "-v",
                "memory_per_node=8"
              ],
              "display": "$ ramble workspace manage experiments hpl --workload-filter calculator -e single_rank -V package_manager=spack -v n_ranks=1 -v n_threads=1 -v memory_per_node=8"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        }
      }
    },
    "hello_world": {
      "title": "Getting Started Running A 'Hello World' Experiment",
      "mode": "static",
      "default_app": "hostname",
      "apps": {
        "hostname": {
          "name": "Hostname",
          "workload": "local",
          "description": "Standard Linux hostname utility for basic experiment testing",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create -d hello_world",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "info"
              ],
              "display": "$ ramble workspace info",
              "output_file": "workspace_info_initial.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "hostname",
                "--workload-filter",
                "local",
                "-e",
                "test",
                "-v",
                "n_ranks=1"
              ],
              "display": "$ ramble workspace manage experiments hostname --workload-filter local -e test -v n_ranks=1"
            },
            {
              "cmd": [
                "workspace",
                "info"
              ],
              "display": "$ ramble workspace info",
              "output_file": "workspace_info.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "setup"
              ],
              "display": "$ ramble workspace setup",
              "global_args": [
                "--disable-progress-bar"
              ],
              "output_file": "setup.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "on"
              ],
              "display": "$ ramble on",
              "output_file": "on.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "analyze"
              ],
              "display": "$ ramble workspace analyze",
              "global_args": [
                "--disable-progress-bar"
              ],
              "output_file": "analyze.out",
              "in_commands_sh": false
            },
            {
              "read_file": "{ws}/results/results.latest.txt",
              "output_file": "results.txt",
              "in_commands_sh": false
            }
          ]
        }
      }
    },
    "modify_experiment": {
      "title": "Modifying an Experiment",
      "mode": "selectable",
      "default_app": "wrf",
      "apps": {
        "wrf": {
          "name": "WRF",
          "workload": "CONUS_12km",
          "workspace_name": "basic_wrf",
          "description": "Weather Research and Forecasting atmospheric model",
          "commands": [
            {
              "cmd": [
                "info",
                "--attrs",
                "workloads",
                "-v",
                "-p",
                "CONUS_12km",
                "wrf"
              ],
              "display": "$ ramble info --attrs workloads -v -p \"CONUS_12km\" wrf",
              "use_workspace": false,
              "use_pty": true,
              "command_file": "info_workload_cmd.sh",
              "output_file": "info_workload.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ]
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "wrf",
                "--workload-filter",
                "CONUS_12km",
                "-e",
                "single_rank",
                "-V",
                "package_manager=spack",
                "-v",
                "n_ranks=1",
                "-v",
                "n_threads=1"
              ]
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ]
            },
            {
              "cmd": [
                "workspace",
                "info"
              ],
              "display": "$ ramble workspace info",
              "use_pty": true,
              "output_file": "workspace_info.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "info",
                "--expansions"
              ],
              "display": "$ ramble workspace info --expansions",
              "use_pty": true,
              "output_file": "workspace_info_expansions_initial.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "wrf",
                "--workload-filter",
                "CONUS_12km",
                "-e",
                "single_rank",
                "--overwrite",
                "-V",
                "package_manager=spack",
                "-V",
                "wrf_tiles=true",
                "-v",
                "n_ranks=1",
                "-v",
                "n_threads=1",
                "-v",
                "num_tiles=2"
              ],
              "display": "$ ramble workspace manage experiments wrf --workload-filter CONUS_12km -e single_rank --overwrite -V package_manager=spack -V wrf_tiles=true -v n_ranks=1 -v n_threads=1 -v num_tiles=2"
            },
            {
              "cmd": [
                "workspace",
                "info",
                "--expansions"
              ],
              "display": "$ ramble workspace info --expansions",
              "use_pty": true,
              "output_file": "workspace_info_expansions_modified.out",
              "in_commands_sh": false
            }
          ]
        },
        "gromacs": {
          "name": "GROMACS",
          "workload": "water_bare",
          "workspace_name": "basic_gromacs",
          "description": "Molecular dynamics simulation package",
          "commands": [
            {
              "cmd": [
                "info",
                "--attrs",
                "workloads",
                "-v",
                "-p",
                "water_bare",
                "gromacs"
              ],
              "display": "$ ramble info --attrs workloads -v -p \"water_bare\" gromacs",
              "use_workspace": false,
              "use_pty": true,
              "command_file": "info_workload_cmd.sh",
              "output_file": "info_workload.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ]
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "gromacs",
                "--workload-filter",
                "water_bare",
                "-e",
                "single_rank",
                "-V",
                "package_manager=spack",
                "-v",
                "n_ranks=1",
                "-v",
                "n_threads=1",
                "-v",
                "size=0003",
                "-v",
                "type=pme"
              ]
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ]
            },
            {
              "cmd": [
                "workspace",
                "info"
              ],
              "display": "$ ramble workspace info",
              "use_pty": true,
              "output_file": "workspace_info.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "info",
                "--expansions"
              ],
              "display": "$ ramble workspace info --expansions",
              "use_pty": true,
              "output_file": "workspace_info_expansions_initial.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "gromacs",
                "--workload-filter",
                "water_bare",
                "-e",
                "single_rank",
                "--overwrite",
                "-V",
                "package_manager=spack",
                "-v",
                "n_ranks=1",
                "-v",
                "n_threads=1",
                "-v",
                "size=0006",
                "-v",
                "type=pme"
              ],
              "display": "$ ramble workspace manage experiments gromacs --workload-filter water_bare -e single_rank --overwrite -V package_manager=spack -v n_ranks=1 -v n_threads=1 -v size=0006 -v type=pme"
            },
            {
              "cmd": [
                "workspace",
                "info",
                "--expansions"
              ],
              "display": "$ ramble workspace info --expansions",
              "use_pty": true,
              "output_file": "workspace_info_expansions_modified.out",
              "in_commands_sh": false
            }
          ]
        },
        "hpl": {
          "name": "HPL",
          "workload": "calculator",
          "workspace_name": "basic_hpl",
          "description": "High-Performance Linpack benchmark",
          "commands": [
            {
              "cmd": [
                "info",
                "--attrs",
                "workloads",
                "-v",
                "-p",
                "calculator",
                "hpl"
              ],
              "display": "$ ramble info --attrs workloads -v -p \"calculator\" hpl",
              "use_workspace": false,
              "use_pty": true,
              "command_file": "info_workload_cmd.sh",
              "output_file": "info_workload.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ]
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "hpl",
                "--workload-filter",
                "calculator",
                "-e",
                "single_rank",
                "-V",
                "package_manager=spack",
                "-v",
                "n_ranks=1",
                "-v",
                "n_threads=1",
                "-v",
                "memory_per_node=8"
              ]
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ]
            },
            {
              "cmd": [
                "workspace",
                "info"
              ],
              "display": "$ ramble workspace info",
              "use_pty": true,
              "output_file": "workspace_info.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "info",
                "--expansions"
              ],
              "display": "$ ramble workspace info --expansions",
              "use_pty": true,
              "output_file": "workspace_info_expansions_initial.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "hpl",
                "--workload-filter",
                "calculator",
                "-e",
                "single_rank",
                "--overwrite",
                "-V",
                "package_manager=spack",
                "-v",
                "n_ranks=1",
                "-v",
                "n_threads=1",
                "-v",
                "memory_per_node=8",
                "-v",
                "percent_mem=80"
              ],
              "display": "$ ramble workspace manage experiments hpl --workload-filter calculator -e single_rank --overwrite -V package_manager=spack -v n_ranks=1 -v n_threads=1 -v memory_per_node=8 -v percent_mem=80"
            },
            {
              "cmd": [
                "workspace",
                "info",
                "--expansions"
              ],
              "display": "$ ramble workspace info --expansions",
              "use_pty": true,
              "output_file": "workspace_info_expansions_modified.out",
              "in_commands_sh": false
            }
          ]
        }
      }
    },
    "ramble_basics": {
      "title": "Ramble Basics: Discovering Applications and Objects",
      "mode": "static",
      "default_app": "hostname",
      "apps": {
        "hostname": {
          "name": "Hostname",
          "workload": "local",
          "description": "Standard Linux hostname utility for basic object inspection",
          "commands": [
            {
              "cmd": [
                "list",
                "h"
              ],
              "display": "$ ramble list h",
              "use_workspace": false,
              "use_pty": true,
              "output_file": "list_h.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "list",
                "h*"
              ],
              "display": "$ ramble list \"h*\"",
              "use_workspace": false,
              "use_pty": true,
              "output_file": "list_hstar.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "list",
                "-t",
                "test-app"
              ],
              "display": "$ ramble list -t test-app",
              "use_workspace": false,
              "use_pty": true,
              "output_file": "list_tag.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "list",
                "--type",
                "modifiers"
              ],
              "display": "$ ramble list --type modifiers",
              "use_workspace": false,
              "use_pty": true,
              "output_file": "list_modifiers.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "list",
                "--type",
                "package_managers"
              ],
              "display": "$ ramble list --type package_managers",
              "use_workspace": false,
              "use_pty": true,
              "output_file": "list_package_managers.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "list",
                "--type",
                "workflow_managers"
              ],
              "display": "$ ramble list --type workflow_managers",
              "use_workspace": false,
              "use_pty": true,
              "output_file": "list_workflow_managers.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "info",
                "hostname"
              ],
              "display": "$ ramble info hostname",
              "use_workspace": false,
              "use_pty": true,
              "output_file": "info.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "info",
                "hostname",
                "-o"
              ],
              "display": "$ ramble info hostname -o",
              "use_workspace": false,
              "use_pty": true,
              "output_file": "info_overview.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "info",
                "hostname",
                "--attrs",
                "workloads",
                "-v"
              ],
              "display": "$ ramble info hostname --attrs workloads -v",
              "use_workspace": false,
              "use_pty": true,
              "output_file": "filtered_info.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "info",
                "--type",
                "modifiers",
                "lscpu"
              ],
              "display": "$ ramble info --type modifiers lscpu",
              "use_workspace": false,
              "use_pty": true,
              "output_file": "info_modifier_lscpu.out",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "list"
              ],
              "display": "$ ramble config list",
              "use_workspace": false,
              "use_pty": true,
              "output_file": "config_list.out",
              "in_commands_sh": false
            }
          ]
        }
      }
    },
    "vectors_matrices": {
      "title": "Using Vectors and Matrices",
      "mode": "selectable",
      "default_app": "wrf",
      "apps": {
        "wrf": {
          "name": "WRF",
          "workload": "CONUS_12km",
          "description": "Weather Research and Forecasting atmospheric model",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create vectors_wrf",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:processes_per_node:16"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:mpi_command:mpirun -n {n_ranks} -ppn {processes_per_node}"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:batch_submit:\"{execute_experiment}\""
              ]
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "wrf",
                "--workload-filter",
                "CONUS_12km",
                "--workload-filter",
                "CONUS_2p5km",
                "-w",
                "app_workload",
                "-e",
                "tile_{num_tiles}_{n_ranks}ranks",
                "-V",
                "package_manager=spack",
                "-V",
                "wrf_tiles=true",
                "-v",
                "n_ranks=[1, 2]",
                "-v",
                "n_threads=1",
                "-v",
                "num_tiles=[1, 2]",
                "-m",
                "app_workload,num_tiles,n_ranks"
              ],
              "display": "$ ramble workspace manage experiments wrf --workload-filter CONUS_12km --workload-filter CONUS_2p5km -w app_workload -e 'tile_{num_tiles}_{n_ranks}ranks' -V package_manager=spack -V wrf_tiles=true -v 'n_ranks=[1, 2]' -v n_threads=1 -v 'num_tiles=[1, 2]' -m app_workload,num_tiles,n_ranks"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        },
        "gromacs": {
          "name": "GROMACS",
          "workload": "water_bare",
          "description": "Molecular dynamics simulation package",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create vectors_gromacs",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:processes_per_node:16"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:mpi_command:mpirun -n {n_ranks} -ppn {processes_per_node}"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:batch_submit:\"{execute_experiment}\""
              ]
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "gromacs",
                "--workload-filter",
                "water_bare",
                "--workload-filter",
                "water_gmx50",
                "-w",
                "app_workload",
                "-e",
                "{type}_{n_ranks}ranks",
                "-V",
                "package_manager=spack",
                "-v",
                "n_ranks=[1, 2]",
                "-v",
                "n_threads=1",
                "-v",
                "size=0003",
                "-v",
                "type=[pme, rf]",
                "-m",
                "app_workload,type,n_ranks"
              ],
              "display": "$ ramble workspace manage experiments gromacs --workload-filter water_bare --workload-filter water_gmx50 -w app_workload -e '{type}_{n_ranks}ranks' -V package_manager=spack -v 'n_ranks=[1, 2]' -v n_threads=1 -v size=0003 -v 'type=[pme, rf]' -m app_workload,type,n_ranks"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        },
        "hpl": {
          "name": "HPL",
          "workload": "calculator",
          "description": "High-Performance Linpack benchmark",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create vectors_hpl",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:processes_per_node:16"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:mpi_command:mpirun -n {n_ranks} -ppn {processes_per_node}"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:batch_submit:\"{execute_experiment}\""
              ]
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "hpl",
                "--workload-filter",
                "calculator",
                "--workload-filter",
                "standard",
                "-w",
                "app_workload",
                "-e",
                "pfact_{PFACTs}_{n_ranks}ranks",
                "-V",
                "package_manager=spack",
                "-v",
                "n_ranks=[1, 2]",
                "-v",
                "n_threads=1",
                "-v",
                "memory_per_node=8",
                "-v",
                "PFACTs=[0, 1]",
                "-m",
                "app_workload,PFACTs,n_ranks"
              ],
              "display": "$ ramble workspace manage experiments hpl --workload-filter calculator --workload-filter standard -w app_workload -e 'pfact_{PFACTs}_{n_ranks}ranks' -V package_manager=spack -v 'n_ranks=[1, 2]' -v n_threads=1 -v memory_per_node=8 -v 'PFACTs=[0, 1]' -m app_workload,PFACTs,n_ranks"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        }
      }
    },
    "software_stack": {
      "title": "Changing a Software Stack",
      "mode": "selectable",
      "default_app": "wrf",
      "apps": {
        "wrf": {
          "name": "WRF",
          "workload": "CONUS_12km",
          "description": "Weather Research and Forecasting atmospheric model",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create software_wrf",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:processes_per_node:16"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:mpi_command:mpirun -n {n_ranks} -ppn {processes_per_node}"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:batch_submit:\"{execute_experiment}\""
              ]
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "software",
                "--package-name",
                "gcc14",
                "--package-spec",
                "gcc@14.2.0",
                "--compiler-spec",
                "gcc@14.2.0"
              ],
              "display": "$ ramble workspace manage software --package-name gcc14 --package-spec gcc@14.2.0 --compiler-spec gcc@14.2.0"
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "software",
                "--package-name",
                "intel-mpi",
                "--package-spec",
                "intel-oneapi-mpi@2021.17.2",
                "--compiler",
                "gcc14"
              ],
              "display": "$ ramble workspace manage software --package-name intel-mpi --package-spec intel-oneapi-mpi@2021.17.2 --compiler gcc14"
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "software",
                "--package-name",
                "wrf-{wrf_version}",
                "--package-spec",
                "wrf@{wrf_version} build_type=dm+sm compile_type=em_real nesting=basic ~pnetcdf",
                "--compiler",
                "gcc14",
                "--environment-name",
                "wrf-{wrf_version}",
                "--environment-packages",
                "intel-mpi,wrf-{wrf_version}"
              ],
              "display": "$ ramble workspace manage software --package-name 'wrf-{wrf_version}' --package-spec 'wrf@{wrf_version} build_type=dm+sm compile_type=em_real nesting=basic ~pnetcdf' --compiler gcc14 --environment-name 'wrf-{wrf_version}' --environment-packages 'intel-mpi,wrf-{wrf_version}'"
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "wrf",
                "--workload-filter",
                "CONUS_12km",
                "--workload-filter",
                "CONUS_2p5km",
                "-w",
                "app_workload",
                "-e",
                "tile_{num_tiles}_{n_ranks}ranks-{wrf_version}",
                "-V",
                "package_manager=spack",
                "-V",
                "wrf_tiles=true",
                "-v",
                "n_ranks=[1, 2]",
                "-v",
                "n_threads=1",
                "-v",
                "num_tiles=[1, 2]",
                "-v",
                "wrf_version=[4.2, 3.9.1.1]",
                "-v",
                "env_name=wrf-{wrf_version}",
                "-m",
                "app_workload,num_tiles,n_ranks,wrf_version"
              ],
              "display": "$ ramble workspace manage experiments wrf --workload-filter CONUS_12km --workload-filter CONUS_2p5km -w app_workload -e 'tile_{num_tiles}_{n_ranks}ranks-{wrf_version}' -V package_manager=spack -V wrf_tiles=true -v 'n_ranks=[1, 2]' -v n_threads=1 -v 'num_tiles=[1, 2]' -v 'wrf_version=[4.2, 3.9.1.1]' -v 'env_name=wrf-{wrf_version}' -m app_workload,num_tiles,n_ranks,wrf_version"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        },
        "gromacs": {
          "name": "GROMACS",
          "workload": "water_bare",
          "description": "Molecular dynamics simulation package",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create software_gromacs",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:processes_per_node:16"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:mpi_command:mpirun -n {n_ranks} -ppn {processes_per_node}"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:batch_submit:\"{execute_experiment}\""
              ]
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "software",
                "--package-name",
                "gcc14",
                "--package-spec",
                "gcc@14.2.0",
                "--compiler-spec",
                "gcc@14.2.0"
              ],
              "display": "$ ramble workspace manage software --package-name gcc14 --package-spec gcc@14.2.0 --compiler-spec gcc@14.2.0"
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "software",
                "--package-name",
                "intel-mpi",
                "--package-spec",
                "intel-oneapi-mpi@2021.17.2",
                "--compiler",
                "gcc14"
              ],
              "display": "$ ramble workspace manage software --package-name intel-mpi --package-spec intel-oneapi-mpi@2021.17.2 --compiler gcc14"
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "software",
                "--package-name",
                "gromacs-{gromacs_version}",
                "--package-spec",
                "gromacs@{gromacs_version}",
                "--compiler",
                "gcc14",
                "--environment-name",
                "gromacs-{gromacs_version}",
                "--environment-packages",
                "intel-mpi,gromacs-{gromacs_version}"
              ],
              "display": "$ ramble workspace manage software --package-name 'gromacs-{gromacs_version}' --package-spec 'gromacs@{gromacs_version}' --compiler gcc14 --environment-name 'gromacs-{gromacs_version}' --environment-packages 'intel-mpi,gromacs-{gromacs_version}'"
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "gromacs",
                "--workload-filter",
                "water_bare",
                "--workload-filter",
                "water_gmx50",
                "-w",
                "app_workload",
                "-e",
                "{type}_{n_ranks}ranks-{gromacs_version}",
                "-V",
                "package_manager=spack",
                "-v",
                "n_ranks=[1, 2]",
                "-v",
                "n_threads=1",
                "-v",
                "size=0003",
                "-v",
                "type=[pme, rf]",
                "-v",
                "gromacs_version=[2025.3, 2025.4]",
                "-v",
                "env_name=gromacs-{gromacs_version}",
                "-m",
                "app_workload,type,n_ranks,gromacs_version"
              ],
              "display": "$ ramble workspace manage experiments gromacs --workload-filter water_bare --workload-filter water_gmx50 -w app_workload -e '{type}_{n_ranks}ranks-{gromacs_version}' -V package_manager=spack -v 'n_ranks=[1, 2]' -v n_threads=1 -v size=0003 -v 'type=[pme, rf]' -v 'gromacs_version=[2025.3, 2025.4]' -v 'env_name=gromacs-{gromacs_version}' -m app_workload,type,n_ranks,gromacs_version"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        },
        "hpl": {
          "name": "HPL",
          "workload": "calculator",
          "description": "High-Performance Linpack benchmark",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create software_hpl",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:processes_per_node:16"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:mpi_command:mpirun -n {n_ranks} -ppn {processes_per_node}"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:batch_submit:\"{execute_experiment}\""
              ]
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "software",
                "--package-name",
                "gcc14",
                "--package-spec",
                "gcc@14.2.0",
                "--compiler-spec",
                "gcc@14.2.0"
              ],
              "display": "$ ramble workspace manage software --package-name gcc14 --package-spec gcc@14.2.0 --compiler-spec gcc@14.2.0"
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "software",
                "--package-name",
                "intel-mpi",
                "--package-spec",
                "intel-oneapi-mpi@2021.17.2",
                "--compiler",
                "gcc14"
              ],
              "display": "$ ramble workspace manage software --package-name intel-mpi --package-spec intel-oneapi-mpi@2021.17.2 --compiler gcc14"
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "software",
                "--package-name",
                "hpl-{hpl_version}",
                "--package-spec",
                "hpl@{hpl_version} +openmp",
                "--compiler",
                "gcc14",
                "--environment-name",
                "hpl-{hpl_version}",
                "--environment-packages",
                "intel-mpi,hpl-{hpl_version}"
              ],
              "display": "$ ramble workspace manage software --package-name 'hpl-{hpl_version}' --package-spec 'hpl@{hpl_version} +openmp' --compiler gcc14 --environment-name 'hpl-{hpl_version}' --environment-packages 'intel-mpi,hpl-{hpl_version}'"
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "hpl",
                "--workload-filter",
                "calculator",
                "--workload-filter",
                "standard",
                "-w",
                "app_workload",
                "-e",
                "pfact_{PFACTs}_{n_ranks}ranks-{hpl_version}",
                "-V",
                "package_manager=spack",
                "-v",
                "n_ranks=[1, 2]",
                "-v",
                "n_threads=1",
                "-v",
                "memory_per_node=8",
                "-v",
                "PFACTs=[0, 1]",
                "-v",
                "hpl_version=[2.3, 2.2]",
                "-v",
                "env_name=hpl-{hpl_version}",
                "-m",
                "app_workload,PFACTs,n_ranks,hpl_version"
              ],
              "display": "$ ramble workspace manage experiments hpl --workload-filter calculator --workload-filter standard -w app_workload -e 'pfact_{PFACTs}_{n_ranks}ranks-{hpl_version}' -V package_manager=spack -v 'n_ranks=[1, 2]' -v n_threads=1 -v memory_per_node=8 -v 'PFACTs=[0, 1]' -v 'hpl_version=[2.3, 2.2]' -v 'env_name=hpl-{hpl_version}' -m app_workload,PFACTs,n_ranks,hpl_version"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        }
      }
    },
    "scaling_study": {
      "title": "Configuring a Scaling Study",
      "mode": "selectable",
      "default_app": "wrf",
      "apps": {
        "wrf": {
          "name": "WRF",
          "workload": "CONUS_12km",
          "description": "Weather Research and Forecasting atmospheric model",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create scaling_wrf",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:processes_per_node:16"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:n_ranks:\"{processes_per_node}*{n_nodes}\""
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:mpi_command:mpirun -n {n_ranks}"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:batch_submit:\"{execute_experiment}\""
              ]
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "wrf",
                "--workload-filter",
                "CONUS_12km",
                "-e",
                "scaling_{n_nodes}",
                "-V",
                "package_manager=spack",
                "-v",
                "n_nodes=[1, 2]"
              ],
              "display": "$ ramble workspace manage experiments wrf --workload-filter CONUS_12km -e 'scaling_{n_nodes}' -V package_manager=spack -v 'n_nodes=[1, 2]'"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        },
        "gromacs": {
          "name": "GROMACS",
          "workload": "water_bare",
          "description": "Molecular dynamics simulation package",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create scaling_gromacs",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:processes_per_node:16"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:n_ranks:\"{processes_per_node}*{n_nodes}\""
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:mpi_command:mpirun -n {n_ranks}"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:batch_submit:\"{execute_experiment}\""
              ]
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "gromacs",
                "--workload-filter",
                "water_bare",
                "-e",
                "scaling_{n_nodes}",
                "-V",
                "package_manager=spack",
                "-v",
                "n_nodes=[1, 2]"
              ],
              "display": "$ ramble workspace manage experiments gromacs --workload-filter water_bare -e 'scaling_{n_nodes}' -V package_manager=spack -v 'n_nodes=[1, 2]'"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        },
        "hpl": {
          "name": "HPL",
          "workload": "calculator",
          "description": "High-Performance Linpack benchmark",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create scaling_hpl",
              "in_commands_sh": false
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:processes_per_node:16"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:n_ranks:\"{processes_per_node}*{n_nodes}\""
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:mpi_command:mpirun -n {n_ranks}"
              ]
            },
            {
              "cmd": [
                "config",
                "add",
                "variables:batch_submit:\"{execute_experiment}\""
              ]
            },
            {
              "cmd": [
                "workspace",
                "manage",
                "experiments",
                "hpl",
                "--workload-filter",
                "calculator",
                "-e",
                "scaling_{n_nodes}",
                "-V",
                "package_manager=spack",
                "-v",
                "n_nodes=[1, 2]",
                "-v",
                "memory_per_node=8"
              ],
              "display": "$ ramble workspace manage experiments hpl --workload-filter calculator -e 'scaling_{n_nodes}' -V package_manager=spack -v 'n_nodes=[1, 2]' -v memory_per_node=8"
            },
            {
              "cmd": [
                "workspace",
                "concretize"
              ],
              "display": "$ ramble workspace concretize"
            }
          ]
        }
      }
    },
    "success_criteria": {
      "title": "Success Criteria",
      "mode": "selectable",
      "default_app": "wrf",
      "apps": {
        "wrf": {
          "name": "WRF",
          "workload": "CONUS_12km",
          "description": "Weather Research and Forecasting atmospheric model",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create success_wrf",
              "in_commands_sh": false
            },
            {
              "display": "$ ramble workspace activate success_wrf"
            },
            {
              "display": "$ ramble workspace edit"
            }
          ],
          "snippets": {
            "base": "ramble:\n  variants:\n    package_manager: spack\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n",
            "regex_criteria": "ramble:\n  variants:\n    package_manager: spack\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    wrf@4.2:\n      success_criteria:\n      - name: timing-present\n        mode: string\n        match: Timing for main.*\n        file: '{experiment_run_dir}/rsl.out.base'\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n",
            "fom_criteria": "ramble:\n  variants:\n    package_manager: spack\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    wrf@4.2:\n      success_criteria:\n      - name: timing-present\n        mode: string\n        match: Timing for main.*\n        file: '{experiment_run_dir}/rsl.out.base'\n      workloads:\n        CONUS_12km:\n          success_criteria:\n          - name: correct-timesteps\n            mode: fom_comparison\n            fom_name: Number of timesteps\n            formula: '{value} >= 50'\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n",
            "final": "ramble:\n  variants:\n    package_manager: spack\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    wrf@4.2:\n      success_criteria:\n      - name: timing-present\n        mode: string\n        match: Timing for main.*\n        file: '{experiment_run_dir}/rsl.out.base'\n      workloads:\n        CONUS_12km:\n          success_criteria:\n          - name: correct-timesteps\n            mode: fom_comparison\n            fom_name: Number of timesteps\n            formula: '{value} >= 50'\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n"
          }
        },
        "gromacs": {
          "name": "GROMACS",
          "workload": "water_bare",
          "description": "Molecular dynamics simulation package",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create success_gromacs",
              "in_commands_sh": false
            },
            {
              "display": "$ ramble workspace activate success_gromacs"
            },
            {
              "display": "$ ramble workspace edit"
            }
          ],
          "snippets": {
            "base": "ramble:\n  variants:\n    package_manager: spack\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    gromacs@2025.3:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n",
            "regex_criteria": "ramble:\n  variants:\n    package_manager: spack\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    gromacs@2025.3:\n      success_criteria:\n      - name: mdrun-finished\n        mode: string\n        match: Finished mdrun.*\n        file: '{experiment_run_dir}/md.log'\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n",
            "fom_criteria": "ramble:\n  variants:\n    package_manager: spack\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    gromacs@2025.3:\n      success_criteria:\n      - name: mdrun-finished\n        mode: string\n        match: Finished mdrun.*\n        file: '{experiment_run_dir}/md.log'\n      workloads:\n        water_bare:\n          success_criteria:\n          - name: max-walltime\n            mode: fom_comparison\n            fom_name: Wall Time\n            formula: '{value} <= 300'\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n",
            "final": "ramble:\n  variants:\n    package_manager: spack\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    gromacs@2025.3:\n      success_criteria:\n      - name: mdrun-finished\n        mode: string\n        match: Finished mdrun.*\n        file: '{experiment_run_dir}/md.log'\n      workloads:\n        water_bare:\n          success_criteria:\n          - name: max-walltime\n            mode: fom_comparison\n            fom_name: Wall Time\n            formula: '{value} <= 300'\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n"
          }
        },
        "hpl": {
          "name": "HPL",
          "workload": "calculator",
          "description": "High-Performance Linpack benchmark",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create success_hpl",
              "in_commands_sh": false
            },
            {
              "display": "$ ramble workspace activate success_hpl"
            },
            {
              "display": "$ ramble workspace edit"
            }
          ],
          "snippets": {
            "base": "ramble:\n  variants:\n    package_manager: spack\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    hpl@2.3:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@{application::hpl::version} +openmp\n        compiler: gcc14\n    environments:\n      hpl@2.3:\n        packages:\n        - intel-mpi\n        - hpl\n",
            "regex_criteria": "ramble:\n  variants:\n    package_manager: spack\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    hpl@2.3:\n      success_criteria:\n      - name: passed\n        mode: string\n        match: '.*PASSED.*'\n        file: '{experiment_run_dir}/HPL.out'\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@{application::hpl::version} +openmp\n        compiler: gcc14\n    environments:\n      hpl@2.3:\n        packages:\n        - intel-mpi\n        - hpl\n",
            "fom_criteria": "ramble:\n  variants:\n    package_manager: spack\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    hpl@2.3:\n      success_criteria:\n      - name: passed\n        mode: string\n        match: '.*PASSED.*'\n        file: '{experiment_run_dir}/HPL.out'\n      workloads:\n        calculator:\n          success_criteria:\n          - name: min-gflops\n            mode: fom_comparison\n            fom_name: GFlops\n            formula: '{value} >= 1.0'\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@{application::hpl::version} +openmp\n        compiler: gcc14\n    environments:\n      hpl@2.3:\n        packages:\n        - intel-mpi\n        - hpl\n",
            "final": "ramble:\n  variants:\n    package_manager: spack\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    hpl@2.3:\n      success_criteria:\n      - name: passed\n        mode: string\n        match: '.*PASSED.*'\n        file: '{experiment_run_dir}/HPL.out'\n      workloads:\n        calculator:\n          success_criteria:\n          - name: min-gflops\n            mode: fom_comparison\n            fom_name: GFlops\n            formula: '{value} >= 1.0'\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@{application::hpl::version} +openmp\n        compiler: gcc14\n    environments:\n      hpl@2.3:\n        packages:\n        - intel-mpi\n        - hpl\n"
          }
        }
      }
    },
    "using_modifiers": {
      "title": "Modifiers",
      "mode": "selectable",
      "default_app": "wrf",
      "apps": {
        "wrf": {
          "name": "WRF",
          "workload": "CONUS_12km",
          "description": "Weather Research and Forecasting atmospheric model",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create modifiers_wrf",
              "in_commands_sh": false
            },
            {
              "display": "$ ramble workspace activate modifiers_wrf"
            },
            {
              "display": "$ ramble workspace edit"
            }
          ],
          "snippets": {
            "base": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n",
            "lscpu": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  modifiers:\n  - name: lscpu\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n",
            "aps_error": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  modifiers:\n  - name: lscpu\n  - name: intel-aps\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n",
            "aps_final": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  modifiers:\n  - name: lscpu\n  - name: intel-aps\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      aps:\n        pkg_spec: intel-oneapi-vtune\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n        - aps\n",
            "final": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  modifiers:\n  - name: lscpu\n  - name: intel-aps\n  applications:\n    wrf@4.2:\n      workloads:\n        CONUS_12km:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      aps:\n        pkg_spec: intel-oneapi-vtune\n      wrfv4-{application::wrf::version}:\n        pkg_spec: wrf@{application::wrf::version} build_type=dm+sm compile_type=em_real\n          nesting=basic ~pnetcdf\n        compiler: gcc14\n    environments:\n      wrf@4.2:\n        packages:\n        - intel-mpi\n        - wrfv4-{application::wrf::version}\n        - aps\n"
          }
        },
        "gromacs": {
          "name": "GROMACS",
          "workload": "water_bare",
          "description": "Molecular dynamics simulation package",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create modifiers_gromacs",
              "in_commands_sh": false
            },
            {
              "display": "$ ramble workspace activate modifiers_gromacs"
            },
            {
              "display": "$ ramble workspace edit"
            }
          ],
          "snippets": {
            "base": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    gromacs@2025.3:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n",
            "lscpu": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  modifiers:\n  - name: lscpu\n  applications:\n    gromacs@2025.3:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n",
            "aps_error": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  modifiers:\n  - name: lscpu\n  - name: intel-aps\n  applications:\n    gromacs@2025.3:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n",
            "aps_final": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  modifiers:\n  - name: lscpu\n  - name: intel-aps\n  applications:\n    gromacs@2025.3:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      aps:\n        pkg_spec: intel-oneapi-vtune\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n        - aps\n",
            "final": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  modifiers:\n  - name: lscpu\n  - name: intel-aps\n  applications:\n    gromacs@2025.3:\n      workloads:\n        water_bare:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      aps:\n        pkg_spec: intel-oneapi-vtune\n      gromacs:\n        pkg_spec: gromacs@{application::gromacs::version}\n        compiler: gcc14\n    environments:\n      gromacs@2025.3:\n        packages:\n        - intel-mpi\n        - gromacs\n        - aps\n"
          }
        },
        "hpl": {
          "name": "HPL",
          "workload": "calculator",
          "description": "High-Performance Linpack benchmark",
          "commands": [
            {
              "cmd": [
                "workspace",
                "create",
                "-d",
                "{ws}"
              ],
              "display": "$ ramble workspace create modifiers_hpl",
              "in_commands_sh": false
            },
            {
              "display": "$ ramble workspace activate modifiers_hpl"
            },
            {
              "display": "$ ramble workspace edit"
            }
          ],
          "snippets": {
            "base": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  applications:\n    hpl@2.3:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@{application::hpl::version} +openmp\n        compiler: gcc14\n    environments:\n      hpl@2.3:\n        packages:\n        - intel-mpi\n        - hpl\n",
            "lscpu": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  modifiers:\n  - name: lscpu\n  applications:\n    hpl@2.3:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@{application::hpl::version} +openmp\n        compiler: gcc14\n    environments:\n      hpl@2.3:\n        packages:\n        - intel-mpi\n        - hpl\n",
            "aps_error": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  modifiers:\n  - name: lscpu\n  - name: intel-aps\n  applications:\n    hpl@2.3:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      hpl:\n        pkg_spec: hpl@{application::hpl::version} +openmp\n        compiler: gcc14\n    environments:\n      hpl@2.3:\n        packages:\n        - intel-mpi\n        - hpl\n",
            "aps_final": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  modifiers:\n  - name: lscpu\n  - name: intel-aps\n  applications:\n    hpl@2.3:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      aps:\n        pkg_spec: intel-oneapi-vtune\n      hpl:\n        pkg_spec: hpl@{application::hpl::version} +openmp\n        compiler: gcc14\n    environments:\n      hpl@2.3:\n        packages:\n        - intel-mpi\n        - hpl\n        - aps\n",
            "final": "ramble:\n  variants:\n    package_manager: spack\n  env_vars:\n    set:\n      OMP_NUM_THREADS: '{n_threads}'\n  variables:\n    processes_per_node: 16\n    n_ranks: '{processes_per_node}*{n_nodes}'\n    batch_submit: '{execute_experiment}'\n    mpi_command: mpirun -n {n_ranks}\n  modifiers:\n  - name: lscpu\n  - name: intel-aps\n  applications:\n    hpl@2.3:\n      workloads:\n        calculator:\n          experiments:\n            scaling_{n_nodes}:\n              variables:\n                n_nodes: [1, 2]\n                memory_per_node: 8\n  software:\n    packages:\n      gcc14:\n        pkg_spec: gcc@14.2.0\n      intel-mpi:\n        pkg_spec: intel-oneapi-mpi@2021.17.2\n        compiler: gcc14\n      aps:\n        pkg_spec: intel-oneapi-vtune\n      hpl:\n        pkg_spec: hpl@{application::hpl::version} +openmp\n        compiler: gcc14\n    environments:\n      hpl@2.3:\n        packages:\n        - intel-mpi\n        - hpl\n        - aps\n"
          }
        }
      }
    }
  },
  "selectable_applications": {
    "wrf": {
      "name": "WRF",
      "workload": "CONUS_12km",
      "description": "Weather Research and Forecasting atmospheric model"
    },
    "gromacs": {
      "name": "GROMACS",
      "workload": "water_bare",
      "description": "Molecular dynamics simulation package"
    },
    "hpl": {
      "name": "HPL",
      "workload": "calculator",
      "description": "High-Performance Linpack benchmark"
    }
  }
};
