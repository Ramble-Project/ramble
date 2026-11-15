# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import re

import ramble.util.stats
from ramble.appkit import *
from ramble.expander import Expander


class Openfoam(ExecutableApplication):
    """Base application definition for OpenFoam"""

    name = "openfoam"

    maintainers("douglasjacobsen")

    tags("cfd")

    motorbike_workloads = [
        "motorbike",
        "motorbike_20m",
        "motorbike_42m",
        "motorbike_100m",
        "motorbike_200m",
    ]

    for wl in motorbike_workloads:
        workload(
            wl,
            executables=[
                "clean",
                "stage_input",
                "stage_trisurface",
                "stage_geometry",
                "stage_0",
                "configure_mesh",
                "surfaceFeatures",
                "blockMesh",
                "decomposePar1",
                "snappyHexMesh",
                "configure_simplefoam",
                "redistributePar",
                "decomposePar2",
                "patchSummary",
                "potentialFoam",
                "checkMesh",
                "simpleFoam",
                "post-exec-clean",
            ],
        )

    workload_variable(
        "input_path",
        default="$FOAM_TUTORIALS/incompressible/simpleFoam/motorBike",
        description="Path to the tutorial input",
        workloads=["motorbike*"],
    )
    workload_variable(
        "geometry_path",
        default="$FOAM_TUTORIALS/resources/geometry/motorBike.obj.gz",
        description="Path to the geometry resource",
        workloads=["motorbike*"],
    )
    workload_variable(
        "decomposition_path",
        default="system/decomposeParDict",
        description="Path to decomposition files",
        workloads=["motorbike*"],
    )
    workload_variable(
        "control_path",
        default="system/controlDict",
        description="Path to control file",
        workloads=["motorbike*"],
    )
    workload_variable(
        "block_mesh_path",
        default="system/blockMeshDict",
        description="Path to block mesh file",
        workloads=["motorbike*"],
    )
    workload_variable(
        "hex_mesh_path",
        default="system/snappyHexMeshDict",
        description="Path to hexh mesh file",
        workloads=["motorbike*"],
    )
    workload_variable(
        "decomposition_method",
        default="",
        description="Set the decomposition method. Empty string means no change",
        workloads=["motorbike*"],
    )
    workload_variable(
        "file_handler",
        default="uncollated",
        description="Control how processes write output",
        values=["uncollated", "collated", "masterUncollated"],
        workloads=["*"],
    )

    workload_variable(
        "end_time",
        default="250",
        description="End time for simulation",
        workloads=["motorbike*"],
    )
    workload_variable(
        "write_interval",
        default="500",
        description="Interval to write output files",
        workloads=["motorbike*"],
    )
    workload_variable(
        "start_from",
        default="startTime",
        description="How to start a new simulation",
        workloads=["motorbike*"],
    )
    workload_variable(
        "mesh_size",
        default="(20 8 8)",
        description="Mesh size for simulation",
        workload="motorbike",
    )
    workload_variable(
        "mesh_size",
        default="(100 40 40)",
        description="Mesh size for simulation",
        workload="motorbike_20m",
    )
    workload_variable(
        "mesh_size",
        default="(130 52 52)",
        description="Mesh size for simulation",
        workload="motorbike_42m",
    )
    workload_variable(
        "mesh_size",
        default="(180 72 72)",
        description="Mesh size for simulation",
        workload="motorbike_100m",
    )
    workload_variable(
        "mesh_size",
        default="(226 90 90)",
        description="Mesh size for simulation",
        workload="motorbike_200m",
    )
    workload_variable(
        "max_local_cells",
        default="100000",
        description="Max local cells for simulation",
        workloads=["motorbike*"],
    )
    workload_variable(
        "max_global_cells",
        default="300000000",
        description="Max global cells for simulation",
        workloads=["motorbike*"],
    )

    workload_variable(
        "n_ranks_hex",
        default="16",
        description="Number of ranks to use for snappyHexMesh",
        workloads=["motorbike*"],
    )
    workload_variable(
        "hex_flags",
        default="-overwrite",
        description="Flags for snappyHexMesh",
        workloads=["motorbike*"],
    )
    workload_variable(
        "potential_flags",
        default="-writePhi",
        description="Flags for potentialFoam",
        workloads=["motorbike*"],
    )
    workload_variable(
        "simple_flags",
        default="",
        description="Flags for simpleFoam",
        workloads=["motorbike*"],
    )

    workload_variable(
        "dict_delim",
        description="Delimiter for dictionary entries",
        default="/",
        workloads=["motorbike*"],
    )

    workload_variable(
        "coeffs_dict",
        description="Coeffs dictionary name",
        default="hierarchicalCoeffs",
        workloads=["motorbike*"],
    )

    variant(
        "openfoam_clean_after_run",
        default=False,
        values=[True, False],
        description="Whether to clean execution artifacts (processor* dirs) after completion or not",
    )

    executable(
        "post-exec-clean",
        template=[
            "rm -rf {experiment_run_dir}/processor*",
        ],
        when=["+openfoam_clean_after_run"],
    )

    executable("clean", template=["rm -rf processor* constant system log.*"])

    stage_files(
        name="stage_input", src="{input_path}/*", dst="{experiment_run_dir}/."
    )
    stage_files(
        name="stage_trisurface",
        src="{geometry_path}",
        dst="constant/triSurface/.",
    )
    stage_files(
        name="stage_geometry", src="{geometry_path}", dst="constant/geometry/."
    )
    stage_files(name="stage_0", src="0/U", dst="0/U.orig")

    executable(
        "configure_mesh",
        template=[
            ". $WM_PROJECT_DIR/bin/tools/RunFunctions",
            'foamDictionary -entry "numberOfSubdomains" -set "{n_ranks_hex}" {decomposition_path}',
            'foamDictionary -entry "{coeffs_dict}{dict_delim}n" -set "({min({n_ranks_hex}, {processes_per_node})} {ceil({n_ranks_hex}/{processes_per_node})} 1)" {decomposition_path}',
            # Only set if the user explicitly gives us a value
            'if [ -n "{decomposition_method}" ]; then foamDictionary -entry "method" -set "{decomposition_method}" {decomposition_path}; fi',
            'foamDictionary -entry "castellatedMeshControls{dict_delim}maxLocalCells" -set "{max_local_cells}" {hex_mesh_path}',
            'foamDictionary -entry "castellatedMeshControls{dict_delim}maxGlobalCells" -set "{max_global_cells}" {hex_mesh_path}',
            'sed "s/(20 8 8)/{mesh_size}/" -i {block_mesh_path}',
        ],
        use_mpi=False,
    )

    executable(
        "configure_simplefoam",
        template=[
            ". $WM_PROJECT_DIR/bin/tools/RunFunctions",
            'foamDictionary -entry "numberOfSubdomains" -set "{n_ranks}" {decomposition_path}',
            'foamDictionary -entry "{coeffs_dict}{dict_delim}n" -set "({processes_per_node} {n_nodes} 1)" {decomposition_path}',
            'foamDictionary -entry "endTime" -set "{end_time}" {control_path}',
            'foamDictionary -entry "writeInterval" -set "{write_interval}" {control_path}',
            'foamDictionary -entry "startFrom" -set "{start_from}" {control_path}',
            # 'foamDictionary -entry "OptimizationSwitches{dict_delim}fileHandler" -set "{file_handler}" {control_path}',
            'foamDictionary system/fvSolution -entry relaxationFactors{dict_delim}fields -add "{}"',
            'foamDictionary system/fvSolution -entry relaxationFactors{dict_delim}fields{dict_delim}p -set "0.3"',
            'foamDictionary system/fvSolution -entry solvers{dict_delim}p{dict_delim}nPreSweeps -set "0"',
            'foamDictionary system/fvSolution -entry solvers{dict_delim}p{dict_delim}nPostSweeps -set "2"',
            'foamDictionary system/fvSolution -entry solvers{dict_delim}p{dict_delim}cacheAgglomeration -set "on"',
            'foamDictionary system/fvSolution -entry solvers{dict_delim}p{dict_delim}agglomerator -set "faceAreaPair"',
            'foamDictionary system/fvSolution -entry solvers{dict_delim}p{dict_delim}nCellsInCoarsestLevel -set "10"',
            'foamDictionary system/fvSolution -entry solvers{dict_delim}p{dict_delim}mergeLevels -set "1"',
            'foamDictionary system/fvSolution -entry SIMPLE{dict_delim}consistent -set "yes"',
        ],
        use_mpi=False,
    )

    executable(
        "surfaceFeatures",
        template=["surfaceFeatures", "surfaceFeatureExtract"],
        use_mpi=False,
        redirect="{experiment_run_dir}/log.surfaceFeatures",
    )

    executable(
        "blockMesh",
        "blockMesh",
        use_mpi=False,
        redirect="{experiment_run_dir}/log.blockMesh",
    )

    executable(
        "decomposePar1",
        template=["decomposePar -noZero -force"],
        use_mpi=False,
        redirect="{experiment_run_dir}/log.decomposePar1",
    )

    executable(
        "decomposePar2",
        template=["rm -rf processor*/0", "decomposePar -copyZero -fields"],
        use_mpi=False,
        redirect="{experiment_run_dir}/log.decomposePar2",
    )

    executable(
        "snappyHexMesh",
        template=["snappyHexMesh -parallel {hex_flags}"],
        use_mpi=True,
        variables={"n_ranks": "{n_ranks_hex}"},
        redirect="{experiment_run_dir}/log.snappyHexMesh",
    )

    executable(
        "redistributePar",
        "redistributePar -noZero -overwrite -parallel",
        use_mpi=True,
        redirect="{experiment_run_dir}/log.redistributePar",
    )

    executable(
        "patchSummary",
        "patchSummary -parallel",
        use_mpi=True,
        redirect="{experiment_run_dir}/log.patchSummary",
    )
    executable(
        "checkMesh",
        "checkMesh -parallel -constant",
        use_mpi=True,
        redirect="{experiment_run_dir}/log.checkMesh",
    )
    executable(
        "potentialFoam",
        "potentialFoam -parallel {potential_flags}",
        use_mpi=True,
        redirect="{experiment_run_dir}/log.potentialFoam",
    )
    executable(
        "simpleFoam",
        "simpleFoam -parallel {simple_flags}",
        use_mpi=True,
        redirect="{experiment_run_dir}/log.simpleFoam",
    )

    workload_variable(
        "export_prefix",
        default="-x",
        description="Prefix for exporting an environment variable with mpirun",
        workloads=["*"],
    )

    workload_variable(
        "workload_exports",
        default="",
        description="Placeholder variable which holds all variable exports. Defined during setup.",
        workloads=["*"],
    )

    workload_variable(
        "export_variables",
        description="Comma separated list of all env-var names that need to be exported",
        default="PATH,LD_LIBRARY_PATH,FOAM_APP,FOAM_APPBIN,FOAM_ETC,"
        + "FOAM_EXT_LIBBIN,FOAM_INST_DIR,FOAM_JOB_DIR,FOAM_LIBBIN,"
        + "FOAM_MPI,FOAM_RUN,FOAM_SETTINGS,FOAM_SIGFPE,FOAM_SITE_APPBIN,"
        + "FOAM_SITE_LIBBIN,FOAM_SOLVERS,FOAM_SRC,FOAM_TUTORIALS,"
        + "FOAM_USER_APPBIN,FOAM_USER_LIBBIN,FOAM_UTILITIES,WM_ARCH,"
        + "WM_ARCH_OPTION,WM_CC,WM_CFLAGS,WM_COMPILER,WM_COMPILER_LIB_ARCH,"
        + "WM_COMPILER_TYPE,WM_COMPILE_OPTION,WM_CXX,WM_CXXFLAGS,WM_DIR,"
        + "WM_LABEL_OPTION,WM_LABEL_SIZE,WM_LDFLAGS,WM_LINK_LANGUAGE,WM_MPLIB,"
        + "WM_OPTIONS,WM_OSTYPE,WM_PRECISION_OPTION,WM_PROJECT,WM_PROJECT_DIR,"
        + "WM_PROJECT_INST_DIR,WM_PROJECT_USER_DIR,WM_PROJECT_VERSION,"
        + "WM_THIRD_PARTY_DIR,MPI_ARCH_FLAGS,MPI_ARCH_INC,MPI_ARCH_LIBS,"
        + "MPI_ARCH_PATH,MPI_BUFFER_SIZE,MPI_ROOT",
        workloads=["*"],
    )

    log_prefix = os.path.join(
        Expander.expansion_str("experiment_run_dir"), "log."
    )

    config_file = "{experiment_run_dir}/openfoam_config"

    figure_of_merit(
        "Number of cells",
        log_file=(log_prefix + "snappyHexMesh"),
        fom_regex=r"Layer mesh\s+:\s+cells:(?P<ncells>[0-9]+)\s+",
        group_name="ncells",
        units="",
    )

    figure_of_merit(
        "snappyHexMesh Time",
        log_file=(log_prefix + "snappyHexMesh"),
        fom_regex=r"Finished meshing in = (?P<mesh_time>[0-9]+\.?[0-9]*)",
        group_name="mesh_time",
        units="s",
    )

    figure_of_merit(
        "snappyHexMesh Ranks",
        formula="{n_ranks_hex}",
        units="",
    )

    simple_foam_exec_regex = (
        r"\s*ExecutionTime = (?P<foam_time>[0-9]+\.?[0-9]*)"
    )
    figure_of_merit(
        "simpleFoam Time",
        log_file=(log_prefix + "simpleFoam"),
        fom_regex=simple_foam_exec_regex,
        group_name="foam_time",
        units="s",
    )

    figure_of_merit(
        "simpleFoam Ranks",
        formula="{n_ranks}",
        units="",
    )

    figure_of_merit(
        "potentialFoam Time",
        log_file=(log_prefix + "potentialFoam"),
        fom_regex=r"\s*ExecutionTime = (?P<foam_time>[0-9]+\.?[0-9]*)",
        group_name="foam_time",
        units="s",
    )

    figure_of_merit(
        "potentialFoam Ranks",
        formula="{n_ranks}",
        units="",
    )

    success_criteria(
        "snappyHexMesh_completed",
        mode="string",
        match="Finalising parallel run",
        file="{experiment_run_dir}/log.snappyHexMesh",
    )

    success_criteria(
        "simpleFoam_completed",
        mode="string",
        match="Finalising parallel run",
        file="{experiment_run_dir}/log.simpleFoam",
    )

    success_criteria(
        "nan",
        mode="string",
        anti_match=r".*?[+-=\s]nan",
        file="{experiment_run_dir}/log.simpleFoam",
    )

    figure_of_merit(
        "simpleFoam Number of Timesteps",
        fom_map_key="simple-foam-time-n-timesteps",
        units="",
    )
    for stat in ramble.util.stats.all_stats:
        figure_of_merit(
            f"simpleFoam Timestep {stat.name}",
            fom_map_key=f"simple-foam-time-{stat.name}",
            units=stat.get_unit("s"),
        )

    def _prepare_analysis(self, workspace, app_inst=None):

        sf_log = self.expander.expand_var(
            "{experiment_run_dir}" + os.sep + "log.simpleFoam"
        )
        if os.path.isfile(sf_log):
            exec_times = []
            exec_regex = re.compile(self.simple_foam_exec_regex)
            with open(sf_log, encoding="utf-8") as f:
                for line in f:
                    m = exec_regex.match(line)
                    if m:
                        exec_times.append(float(m.group("foam_time")))

            self.add_inmem_fom_value(
                "simple-foam-time-n-timesteps", len(exec_times)
            )

            # Drop first time, to avoid init time
            if len(exec_times) > 1:
                timestep_times = [
                    exec_times[i + 1] - exec_times[i]
                    for i in range(len(exec_times) - 1)
                ]

                # Compute statistics from other times
                for stat in ramble.util.stats.all_stats:
                    self.add_inmem_fom_value(
                        f"simple-foam-time-{stat.name}",
                        stat.compute(timestep_times),
                    )

    register_phase(
        "define_exports", pipeline="setup", run_before=["make_experiments"]
    )

    def _define_exports(self, workspace, app_inst=None):
        export_prefix = self.expander.expand_var_name("export_prefix")
        export_vars = self.expander.expand_var_name("export_variables").split(
            ","
        )

        export_args = [f"{export_prefix} {var}" for var in export_vars]

        export_str = " ".join(export_args)

        self.define_variable("workload_exports", export_str)
