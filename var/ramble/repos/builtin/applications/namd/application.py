# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.appkit import *
from ramble.expander import Expander
from ramble.keywords import keywords


class Namd(ExecutableApplication):
    """Define NAMD application"""

    name = "namd"

    maintainers("douglasjacobsen")

    tags("molecular-dynamics", "hpc-benchmark", "charmpp")

    version("2.14", description="Version 2.14 of NAMD", preferred=True)

    with when("package_manager_family=spack"):
        define_compiler("gcc12", pkg_spec="gcc@12.2.0")

        software_spec(
            "impi2021p8",
            pkg_spec="intel-oneapi-mpi@2021.8.0",
        )

        software_spec(
            "charmpp",
            pkg_spec="charmpp backend=mpi build-target=charm++",
            compiler="gcc12",
        )

        software_spec(
            "namd-{application::namd::version}",
            pkg_spec="namd@{application::namd::version} interface=tcl",
            compiler="gcc12",
        )

        required_package("namd")

    input_file(
        "stmv",
        url="https://www.ks.uiuc.edu/Research/namd/utilities/stmv.tar.gz",
        sha256="2ef8beaa22046f2bf4ddc85bb8141391a27041302f101f5302f937d04104ccdd",
        description="STMV (virus) benchmark (1,066,628 atoms, periodic, PME",
    )

    input_file(
        "ApoA1",
        url="https://www.ks.uiuc.edu/Research/namd/utilities/apoa1.tar.gz",
        sha256="fe30322cc94d93dff6c4e517d28584c48d0d0a1a7b23e2cd74cdb36d03863b22",
        description="ApoA1 benchmark (92,224 atoms, periodic, PME)",
    )

    input_file(
        "ATPase",
        url="https://www.ks.uiuc.edu/Research/namd/utilities/f1atpase.tar.gz",
        sha256="ec34e31c69a7fc3c1649158bf7dbf20d20fe77520f73d05cbec4e9806b79148d",
        description="ATPase benchmark (327,506 atoms, periodic, PME)",
    )

    input_file(
        "20STMV",
        url="https://www.ks.uiuc.edu/Research/namd/utilities/stmv_sc14.tar.gz",
        sha256="e166ca309ae614417f1c2da3b0eed139c816666403d552955b04849f703ef719",
        description="20STMV and 210STMV benchmarks from SC14 paper",
    )

    input_file(
        "tiny",
        url="https://www.ks.uiuc.edu/Research/namd/utilities/tiny.tar.gz",
        sha256="dabf5986456d504a5ba40d3660bb8b6e6bd5d714b413390a733a4f819c1512ec",
        description="tiny benchmark (507 atoms, periodic, PME)",
    )

    input_file(
        "interactive_BPTI",
        url="https://www.ks.uiuc.edu/Research/namd/utilities/bpti_imd.tar.gz",
        sha256="751ab94d13fc227a3313bc0a323597943fbf1f9a98d88c81086717399d61b8ec",
        description="Interactive BPTI (882 atoms, small)",
    )

    input_file(
        "ER-GRE",
        url="https://www.ks.uiuc.edu/Research/namd/utilities/er-gre.tar.gz",
        sha256="8aaff093cddf5f28aec9ea65f9bce5853efa4f4346a64477efe0e0cde16740ce",
        description="ER-GRE benchmark (36573 atoms, spherical)",
    )

    input_file(
        "decalanin",
        url="https://www.ks.uiuc.edu/Research/namd/utilities/alanin.tar.gz",
        sha256="92f8b6f1a55b548d450fe858cde9db901445964ed24639d5aa3667f3fc1ec52c",
        description="decalanin (66 atoms, tiny, ancient)",
    )

    input_file(
        "tcl-forces",
        url="https://www.ks.uiuc.edu/Research/namd/utilities/tclforces.tar.gz",
        sha256="3daa557c51a41d4f2484aa3b4de7c1d96671da2baa159798ed0d90e638965eee",
        description="Tcl forces (decalanin)",
    )

    stage_files(
        name="stage-input",
        src="{input_path}/*",
        dst="{experiment_run_dir}/.",
    )
    executable("execute", "namd2 {namd_flags} {input_file}", use_mpi=True)

    # Configure standard benchmark workloads and variables
    # Assumes each benchmark workload has an input of the same name.
    benchmark_workloads = [
        ("stmv", ["stmv.namd"]),
        ("ApoA1", ["apoa1.namd"]),
        ("ATPase", ["f1atpase.namd"]),
        (
            "20STMV",
            ["1stmv2fs.namd", "210stmv2fs.namd", "compress_20stmv.namd"],
        ),
        ("tiny", ["tiny.namd"]),
        ("interactive_BPTI", ["bpti.namd"]),
        ("ER-GRE", ["er-gre.namd"]),
        ("decalanin", ["alanin.namd"]),
        ("tcl-forces", ["tclforces.namd"]),
    ]
    all_benchmark_workloads = [wl[0] for wl in benchmark_workloads]

    for wl_def in benchmark_workloads:
        workload(
            wl_def[0],
            executables=["stage-input", "execute"],
            inputs=[wl_def[0]],
        )

        workload_variable(
            "input_file",
            default=wl_def[1][0],
            values=wl_def[1],
            description="Input file for namd",
            workloads=[wl_def[0]],
        )

    workload_group("all_benchmarks", workloads=all_benchmark_workloads)

    workload_variable(
        "namd_flags",
        default="+ppn {processes_per_node} +setcpuaffinity",
        description="Flags for running NAMD",
        workload_group="all_benchmarks",
    )

    workload_variable(
        "input_path",
        description="Path to the workload inputs",
        workload_defaults={
            "stmv": "{stmv}",
            "ApoA1": "{ApoA1}",
            "ATPase": "{ATPase}",
            "20STMV": "{20STMV}",
            "tiny": "{tiny}",
            "interactive_BPTI": "{interactive_BPTI}",
            "ER-GRE": "{ER-GRE}",
            "decalanin": "{decalanin}",
            "tcl-forces": "{tcl-forces}",
        },
    )

    log_file_str = Expander.expansion_str(keywords.log_file)

    success_criteria(
        "Completion",
        mode="string",
        match=r".*?End of program",
        file=log_file_str,
    )

    # Timing FOMs
    timing_regex = (
        r"TIMING:\s+(?P<itr>[0-9]+)\s+CPU:\s+(?P<cpu>[0-9]+\.[0-9]+),\s+(?P<cpu_per_step>[0-9]+\.[0-9]+)/step\s+"
        + r"Wall:\s+(?P<wall>[0-9]+\.[0-9]+),\s+(?P<wall_per_step>[0-9]+\.[0-9]+)/step,\s+(?P<remaining>[0-9]+\.*[0-9]*)\s+"
        + r"hours\s+remaining,\s+(?P<mem>[0-9]+\.[0-9]+)\s+MB"
    )
    figure_of_merit_context(
        "Perf iteration",
        regex=timing_regex,
        output_format="Timing Itertion: {itr}",
    )

    figure_of_merit(
        "Timing iteration",
        log_file=log_file_str,
        fom_regex=timing_regex,
        group_name="itr",
        units="",
        contexts=["Perf iteration"],
    )

    figure_of_merit(
        "CPU time",
        log_file=log_file_str,
        fom_regex=timing_regex,
        group_name="cpu",
        units="s",
        contexts=["Perf iteration"],
    )

    figure_of_merit(
        "Avg. CPU time per time step",
        log_file=log_file_str,
        fom_regex=timing_regex,
        group_name="cpu_per_step",
        units="s/timestep",
        contexts=["Perf iteration"],
    )

    figure_of_merit(
        "Wall time",
        log_file=log_file_str,
        fom_regex=timing_regex,
        group_name="wall",
        units="s",
        contexts=["Perf iteration"],
    )

    figure_of_merit(
        "Avg. Wall time per time step",
        log_file=log_file_str,
        fom_regex=timing_regex,
        group_name="wall_per_step",
        units="s/timestep",
        contexts=["Perf iteration"],
    )

    figure_of_merit(
        "Wall time remaining",
        log_file=log_file_str,
        fom_regex=timing_regex,
        group_name="remaining",
        units="hours",
        contexts=["Perf iteration"],
    )

    figure_of_merit(
        "Memory used",
        log_file=log_file_str,
        fom_regex=timing_regex,
        group_name="mem",
        units="MB",
        contexts=["Perf iteration"],
    )

    # Energy context
    energy_regex = r"ENERGY:\s+(?P<itr>[0-9]+)"

    # Name/group_name, units
    energy_foms = [
        ("BOND", ""),
        ("ANGLE", ""),
        ("DIHED", ""),
        ("IMPRP", ""),
        ("ELECT", ""),
        ("VWD", ""),
        ("BOUNDARY", ""),
        ("MISC", ""),
        ("KINETIC", ""),
        ("TOTAL", ""),
        ("TEMP", ""),
        ("POTENTIAL", ""),
        ("TOTAL3", ""),
        ("TEMPAVG", ""),
        ("PRESSURE", ""),
        ("GPRESSURE", ""),
        ("VOLUME", ""),
        ("PRESSAVG", ""),
        ("GPRESSAVG", ""),
    ]

    # Build energy regex...
    for energy_fom in energy_foms:
        energy_regex += (
            r"\s+(?P<" + f"{energy_fom[0]}" + r">-*[0-9]+\.*[0-9]*)"
        )

    figure_of_merit_context(
        "Energy iteration",
        regex=energy_regex,
        output_format="Energy Iteration: {itr}",
    )

    figure_of_merit(
        "Energy iteration",
        log_file=log_file_str,
        fom_regex=timing_regex,
        group_name="itr",
        units="",
        contexts=["Energy iteration"],
    )

    for energy_fom in energy_foms:
        figure_of_merit(
            energy_fom[0],
            log_file=log_file_str,
            fom_regex=energy_regex,
            group_name=energy_fom[0],
            units=energy_fom[1],
            contexts=["Energy iteration"],
        )

    # Benchmark foms
    benchmark_regex = (
        r"Info:\s+Benchmark\s+time:\s+(?P<cpus>[0-9]+)\s+CPUs\s+"
        + r"(?P<wall_per_step>[0-9]+\.[0-9]+)\s+s/step\s+"
        + r"(?P<days_per_ns>[0-9]+\.[0-9]+)\s+days/ns\s+"
        + r"(?P<mem>[0-9]+\.[0-9]+)\s+MB\s+memory"
    )

    figure_of_merit(
        "Number of CPUs",
        log_file=log_file_str,
        fom_regex=benchmark_regex,
        group_name="cpus",
        units="",
    )

    figure_of_merit(
        "Benchmark wall time per step",
        log_file=log_file_str,
        fom_regex=benchmark_regex,
        group_name="wall_per_step",
        units="s",
    )

    figure_of_merit(
        "Benchmark days per nanosecond",
        log_file=log_file_str,
        fom_regex=benchmark_regex,
        group_name="days_per_ns",
        units="days/ns",
    )

    figure_of_merit(
        "Benchmark memory used",
        log_file=log_file_str,
        fom_regex=benchmark_regex,
        group_name="mem",
        units="MB",
    )

    # Global figures of merit
    end_regex = r"\s*WallClock:\s+(?P<wall>[0-9]+\.[0-9]+)\s+CPUTime:\s+(?P<cpu>[0-9]+\.[0-9]+)\s+Memory:\s+(?P<mem>[0-9]+\.[0-9]+)\s+MB"
    figure_of_merit(
        "Final wall time",
        log_file=log_file_str,
        fom_regex=end_regex,
        group_name="wall",
        units="s",
    )

    figure_of_merit(
        "Final CPU time",
        log_file=log_file_str,
        fom_regex=end_regex,
        group_name="cpu",
        units="s",
    )

    figure_of_merit(
        "Final Memory",
        log_file=log_file_str,
        fom_regex=end_regex,
        group_name="mem",
        units="MB",
    )

    figure_of_merit(
        "Nanoseconds per day",
        units="ns/day",
        formula="1.0 / {Benchmark days per nanosecond}",
        fom_type=FomType.THROUGHPUT,
    )
