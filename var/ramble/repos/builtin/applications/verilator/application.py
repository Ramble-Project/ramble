# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import glob
import os
import re

from ramble.appkit import *


class Verilator(ExecutableApplication):
    """Verilator is the open-source Verilog/SystemVerilog simulator that compiles
    RTL into optimized C++ models.

    This benchmark application uses the RTLMeter benchmark harness and reference
    designs (including NVDLA, XiangShan, OpenTitan, Caliptra, BlackParrot, VeeR,
    and Vortex GPGPU) to benchmark EDA front-end RTL simulation across two
    decoupled phases (because compilation and simulation have very different
    CPU/memory per job requirements):

      1. Compile phase (compile_* workloads, or executable 'build_model'):
         Runs on 1 node with multiple cores (e.g. --cpus-per-task=32, 32 GB RAM)
         to execute single-threaded 'verilate' (Verilog -> C++) and multi-threaded
         'cppbuild' (make -j) into a shared compile_dir.

      2. Benchmark phase (1 CPU per rank across 1 to N nodes, reusing compile_dir):
         - Option 1, Weak scaling:
           Runs N concurrent copies of the same cases (one per rank via srun/mpirun)
           and aggregates makespan, per-copy wall-time and RTLMeter execution-time
           percentiles (min/p50/mean/p95/max), and peak memory across all ranks.
         - Option 2 Lite, Logic regression (regression_* workloads):
           Distributes a heterogeneous suite of RTLMeter cases (+standard and/or
           NVDLA, repeated R times) across the allocated ranks using a dynamic
           work queue and reports regression makespan, throughput (tests/hour),
           core efficiency, and per-test runtime percentiles.

    https://verilator.org
    https://github.com/verilator/rtlmeter
    """

    name = "verilator"

    maintainers("juntangc")

    tags(
        "eda",
        "simulation",
        "verilator",
        "rtl",
        "benchmark",
        "eda-proxy",
    )

    version("5.052", "Version 5.052 of Verilator", preferred=True)
    version("5.050", "Version 5.050 of Verilator")
    version("5.030", "Version 5.030 of Verilator")

    with when("package_manager_family=spack"):
        define_compiler("gcc14", pkg_spec="gcc@14.2.0")

        software_spec(
            "verilator",
            pkg_spec="verilator@{application::verilator::version}",
            compiler="gcc14",
        )

        required_package("verilator")

    input_file(
        "rtlmeter_src",
        url="https://github.com/verilator/rtlmeter/archive/d4cd38138eba33ea5121a76a8e8fc4aedebe0f5b.tar.gz",
        description="RTLMeter benchmark suite and reference designs archive",
    )

    # -------------------------------------------------------------------------
    # Phase 1: Compile (verilate + multi-threaded cppbuild)
    # -------------------------------------------------------------------------
    executable(
        "build_model",
        template=[
            "{rtlmeter_setup}",
            '{rtlmeter_cmd} run --cases "{case}" {compile_args} --compileRoot {compile_dir} --nExecute 0 {additional_args}',
            "{rtlmeter_cmd} report --steps 'verilate cppbuild' {compile_dir}",
        ],
        use_mpi=False,
    )

    # -------------------------------------------------------------------------
    # Phase 2A (Option 1): Weak-scaling simulation executables
    # -------------------------------------------------------------------------
    # Runs {case} concurrently on every MPI/Slurm rank using pre-built {compile_dir}.
    # Each copy (rank_0 .. rank_{N-1}) records its start timestamp, end timestamp,
    # and full `rtlmeter report --steps execute` table into
    # {experiment_run_dir}/weak_metrics/rank_<RANK_ID>.report.
    executable(
        "prepare_distributed",
        template=[
            'if [ ! -d "{compile_dir}" ]; then echo "ERROR: compile_dir {compile_dir} not found. Run the compile step (build_model) first." >&2; exit 1; fi',
            # Each workload extracts its own RTLMeter copy ({workload_input_dir}),
            # so the venv built by build_model is not visible here.
            "{rtlmeter_setup}",
            'CASES=$({rtlmeter_cmd} show --cases 2>/dev/null | tr -d "," | (set -f; while read -r c tags; do '
            '[[ "$c" == *:*:* ]] || continue; '
            "for p in {case}; do "
            'if [[ "$p" == +* ]]; then '
            'for t in $tags; do if [ "+$t" = "$p" ]; then echo "$c"; break 2; fi; done; '
            'elif [[ "$c" == $p ]]; then echo "$c"; break; fi; '
            "done; done)); "
            'if [ -z "$CASES" ]; then echo "ERROR: No cases matched ({case}). Check apptainer/rtlmeter_cmd on the batch node." >&2; exit 1; fi; '
            'for c in $CASES; do IFS=: read -r d cfg _ <<< "$c"; '
            'if [ "$(cat "{compile_dir}/$d/$cfg/compile-0/_cppbuild/status" 2>/dev/null)" != "success" ]; then '
            'echo "ERROR: Model $d:$cfg is not compiled in {compile_dir}. Run the compile step (build_model) first." >&2; exit 1; fi; done',
            'rm -rf "{experiment_run_dir}/weak_metrics" "{experiment_run_dir}/failed_logs" && mkdir -p "{experiment_run_dir}/weak_metrics"',
        ],
        use_mpi=False,
    )

    executable(
        "simulate_distributed",
        template=[
            "bash -c '"
            "RANK_ID=$SLURM_PROCID; "
            '[ -z "$RANK_ID" ] && RANK_ID=$OMPI_COMM_WORLD_RANK; '
            '[ -z "$RANK_ID" ] && RANK_ID=$PMI_RANK; '
            '[ -z "$RANK_ID" ] && RANK_ID=$PMIX_RANK; '
            '[ -z "$RANK_ID" ] && RANK_ID=$(tr "\\0" "\\n" < /proc/$PPID/environ 2>/dev/null | sed -n "s/^\\(SLURM_PROCID\\|OMPI_COMM_WORLD_RANK\\|PMI_RANK\\|PMIX_RANK\\)=//p" | head -n 1); '
            '[ -z "$RANK_ID" ] && [ {n_ranks} -le 1 ] && RANK_ID=0; '
            'if [ -z "$RANK_ID" ]; then echo "ERROR: Could not determine rank ID (SLURM_PROCID/OMPI_COMM_WORLD_RANK/PMI_RANK/PMIX_RANK) with n_ranks={n_ranks}" >&2; exit 1; fi; '
            'WORKER_DIR="{execute_dir}/rank_$RANK_ID"; '
            'MDIR="{experiment_run_dir}/weak_metrics"; '
            'rm -rf "$WORKER_DIR" && mkdir -p "$WORKER_DIR" "$MDIR" || exit 1; '
            'T0=$(date +%s.%N); TS0=$(date -u +"%Y-%m-%dT%H:%M:%SZ"); '
            '{rtlmeter_cmd} run --cases "{case}" --compileRoot {compile_dir} --executeRoot "$WORKER_DIR" --nExecute {n_execute} {additional_args} > "$WORKER_DIR/run.log" 2>&1; '
            'RC=$?; T1=$(date +%s.%N); TS1=$(date -u +"%Y-%m-%dT%H:%M:%SZ"); '
            '( printf "=== Copy %s (host: %s, exit: %s) ===\\nStart Time: %s (epoch: %s)\\nEnd Time:   %s (epoch: %s)\\n" "$RANK_ID" "$(hostname)" "$RC" "$TS0" "$T0" "$TS1" "$T1"; '
            '  {rtlmeter_cmd} report --steps "execute" "$WORKER_DIR" 2>&1; '
            '  printf "\\n" ) > "$MDIR/rank_$RANK_ID.report"; '
            'if [ $RC -eq 0 ]; then rm -rf "$WORKER_DIR"; else mkdir -p "{experiment_run_dir}/failed_logs" && cp -f "$WORKER_DIR/run.log" "{experiment_run_dir}/failed_logs/rank_${RANK_ID}_run.log" 2>/dev/null || true; fi; '
            "exit $RC"
            "'",
        ],
        use_mpi=True,
    )

    executable(
        "report_distributed",
        template=[
            '( find "{experiment_run_dir}/weak_metrics" -maxdepth 1 -name "rank_*.report" | sort -V | xargs -r cat 2>/dev/null || true )',
            'echo "=== Weak-scaling complete ==="',
        ],
        use_mpi=False,
    )

    # -------------------------------------------------------------------------
    # Phase 2B (Option 2 Lite): Intra-allocation multi-case logic regression
    # -------------------------------------------------------------------------
    # Each rank starts with workload index IDX = RANK_ID at t=0 (avoiding a lock spike
    # when all ranks launch simultaneously) and pulls subsequent indices from the
    # shared .regression_next_idx queue as tests finish, update index after pulling.
    # NOTE: {experiment_run_dir} must be on a filesystem shared by all nodes with
    # working flock(2). That rules out GCSFuse (no cross-node POSIX lock coherence)
    # and Lustre unless mounted with `-o flock`.
    executable(
        "prepare_regression",
        template=[
            'if [ ! -d "{compile_dir}" ]; then echo "ERROR: compile_dir {compile_dir} not found. Run the compile step (build_model) first." >&2; exit 1; fi',
            "{rtlmeter_setup}",
            'CASES=$({rtlmeter_cmd} show --cases 2>/dev/null | tr -d "," | (set -f; while read -r c tags; do '
            '[[ "$c" == *:*:* ]] || continue; '
            "for p in {regression_cases}; do "
            'if [[ "$p" == +* ]]; then '
            'for t in $tags; do if [ "+$t" = "$p" ]; then echo "$c"; break 2; fi; done; '
            'elif [[ "$c" == $p ]]; then echo "$c"; break; fi; '
            "done; done)); "
            'if [ -z "$CASES" ]; then echo "ERROR: No regression cases matched ({regression_cases}). Check apptainer/rtlmeter_cmd on the batch node." >&2; exit 1; fi; '
            'for c in $CASES; do IFS=: read -r d cfg _ <<< "$c"; '
            'if [ "$(cat "{compile_dir}/$d/$cfg/compile-0/_cppbuild/status" 2>/dev/null)" != "success" ]; then '
            'echo "ERROR: Model $d:$cfg is not compiled in {compile_dir}. Run the compile step (build_model) first." >&2; exit 1; fi; done; '
            'rm -rf "{experiment_run_dir}/regression_metrics" "{experiment_run_dir}/failed_logs" && mkdir -p "{experiment_run_dir}/regression_metrics"; '
            'for _ in $(seq 1 {regression_repeat}); do printf "%s\\n" $CASES; done '
            '| shuf | nl -v0 -w1 > "{experiment_run_dir}/regression_manifest.tsv"; '
            'if ! ( flock 9 && echo {n_ranks} >&9 ) 9> "{experiment_run_dir}/.regression_next_idx"; then '
            'echo "ERROR: flock failed on {experiment_run_dir}/.regression_next_idx. experiment_run_dir must be on a shared filesystem with working flock (not GCSFuse, and Lustre requires -o flock)." >&2; exit 1; fi',
        ],
        use_mpi=False,
    )

    executable(
        "simulate_regression",
        template=[
            "bash -c '"
            "RANK_ID=$SLURM_PROCID; "
            '[ -z "$RANK_ID" ] && RANK_ID=$OMPI_COMM_WORLD_RANK; '
            '[ -z "$RANK_ID" ] && RANK_ID=$PMI_RANK; '
            '[ -z "$RANK_ID" ] && RANK_ID=$PMIX_RANK; '
            '[ -z "$RANK_ID" ] && RANK_ID=$(tr "\\0" "\\n" < /proc/$PPID/environ 2>/dev/null | sed -n "s/^\\(SLURM_PROCID\\|OMPI_COMM_WORLD_RANK\\|PMI_RANK\\|PMIX_RANK\\)=//p" | head -n 1); '
            '[ -z "$RANK_ID" ] && [ {n_ranks} -le 1 ] && RANK_ID=0; '
            'if [ -z "$RANK_ID" ]; then echo "ERROR: Could not determine rank ID (SLURM_PROCID/OMPI_COMM_WORLD_RANK/PMI_RANK/PMIX_RANK) with n_ranks={n_ranks}" >&2; exit 1; fi; '
            'MANIFEST="{experiment_run_dir}/regression_manifest.tsv"; '
            'QFILE="{experiment_run_dir}/.regression_next_idx"; '
            'MDIR="{experiment_run_dir}/regression_metrics"; '
            'rm -f "$MDIR/rank_$RANK_ID.timing"; '
            "IDX=$RANK_ID; END=$((RANK_ID + 1)); RC_ANY=0; "
            'NJOBS=$(wc -l < "$MANIFEST"); KMAX={regression_claim_max}; '
            'while [ "$IDX" -lt "$NJOBS" ]; do '
            "  while read -r IDX CASE; do "
            '    [ -z "$CASE" ] && continue; '
            '    TDIR="{execute_dir}/test_$IDX"; '
            '    rm -rf "$TDIR" && mkdir -p "$TDIR"; '
            '    T0=$(date +%s.%N); TS0=$(date -u +"%Y-%m-%dT%H:%M:%SZ"); '
            '    {rtlmeter_cmd} run --cases "$CASE" --compileRoot {compile_dir} --executeRoot "$TDIR" --nExecute {n_execute} {additional_args} > "$TDIR/run.log" 2>&1; '
            '    RC=$?; T1=$(date +%s.%N); TS1=$(date -u +"%Y-%m-%dT%H:%M:%SZ"); '
            '    RPT_ROW=$({rtlmeter_cmd} report --steps "execute" "$TDIR" 2>/dev/null | grep -F "$CASE" | head -n 1); '
            '    [ -z "$RPT_ROW" ] && echo "WARNING: Empty report row for case $CASE (test $IDX, rank $RANK_ID, exit $RC)" >&2; '
            '    printf "%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n" "$IDX" "$RANK_ID" "$(hostname)" "$CASE" "$TS0" "$T0" "$TS1" "$T1" "$RC" "$RPT_ROW" >> "$MDIR/rank_$RANK_ID.timing"; '
            '    if [ $RC -eq 0 ] && [ -n "$RPT_ROW" ]; then rm -rf "$TDIR"; else [ $RC -ne 0 ] && RC_ANY=$RC || RC_ANY=1; mkdir -p "{experiment_run_dir}/failed_logs" && cp -f "$TDIR/run.log" "{experiment_run_dir}/failed_logs/test_${IDX}_rank_${RANK_ID}_run.log" 2>/dev/null || true; fi; '
            '  done < <(sed -n "$((IDX + 1)),${END}p;$((END + 1))q" "$MANIFEST" 2>/dev/null); '
            '  CLAIM=$( (flock 9 || exit 1; read -r cur <&9; [ -z "$cur" ] && cur={n_ranks}; '
            'k=$(( (NJOBS - cur + 2 * {n_ranks} - 1) / (2 * {n_ranks}) )); [ "$k" -gt "$KMAX" ] && k=$KMAX; [ "$k" -lt 1 ] && k=1; '
            'printf "%d\\n" $((cur + k)) > "$QFILE"; echo "$cur $((cur + k))") 9<>"$QFILE" ) || { echo "ERROR: flock failed on $QFILE (rank $RANK_ID)" >&2; exit 1; }; '
            '  read -r IDX END <<< "$CLAIM"; '
            "done; "
            "exit $RC_ANY"
            "'",
        ],
        use_mpi=True,
    )

    executable(
        "report_regression",
        template=[
            '( printf "Test\\tRank\\tHost\\tCase\\tStart_Time\\tStart_Epoch\\tEnd_Time\\tEnd_Epoch\\tExit\\tRTLMeter_Execute_Row\\n" > "{experiment_run_dir}/regression_report.tsv" )',
            '( find "{experiment_run_dir}/regression_metrics" -maxdepth 1 -name "*.timing" | xargs -r cat 2>/dev/null | sort -n -k1,1 >> "{experiment_run_dir}/regression_report.tsv" || true )',
            'cat "{experiment_run_dir}/regression_report.tsv"',
            'echo "=== Regression complete ==="',
        ],
        use_mpi=False,
    )

    compile_executables = ["build_model"]

    weak_scaling_executables = [
        "prepare_distributed",
        "simulate_distributed",
        "report_distributed",
    ]

    regression_executables = [
        "prepare_regression",
        "simulate_regression",
        "report_regression",
    ]

    # -------------------------------------------------------------------------
    # Workloads: 4 Core Use Cases Across Compile, Weak-Scaling, and Regression
    #   1. All NVDLA ("NVDLA:*")
    #   2. All Standard ("+standard")
    #   3. All Standard + NVDLA ("+standard NVDLA:*")
    #   4. Custom hand-picked design/config ("NVDLA:default:conv" default)
    # -------------------------------------------------------------------------
    compile_workloads = {
        "compile_nvdla": (
            "NVDLA:*",
            "Compile all NVDLA models (NVDLA:default shared by all six NVDLA tests)",
        ),
        "compile_standard": (
            "+standard",
            "Compile all 18 RTLMeter +standard suite models",
        ),
        "compile_mixed": (
            "+standard NVDLA:*",
            "Compile all 19 RTLMeter models (+standard suite plus all NVDLA)",
        ),
        "compile_custom": (
            "NVDLA:default:conv",
            "Compile user-specified RTLMeter case pattern(s)",
        ),
    }

    for wl_name, (wl_case, wl_desc) in compile_workloads.items():
        workload(
            wl_name, executables=compile_executables, inputs=["rtlmeter_src"]
        )
        workload_variable(
            "case",
            default=wl_case,
            description=f"{wl_desc} ({wl_name})",
            workloads=[wl_name],
        )

    workload_group("compile", workloads=list(compile_workloads.keys()))

    benchmark_workloads = {
        "nvdla_all": (
            "NVDLA:*",
            "Run all NVDLA test cases",
        ),
        "standard_all": (
            "+standard",
            "Run all +standard suite test cases",
        ),
        "mixed_all": (
            "+standard NVDLA:*",
            "Run all +standard suite plus all NVDLA test cases (24 cases per rank)",
        ),
        "custom": (
            "NVDLA:default:conv",
            "Custom RTLMeter case pattern (e.g. NVDLA:default:conv or XiangShan:mini-chisel3:*)",
        ),
    }

    for wl_name, (wl_case, wl_desc) in benchmark_workloads.items():
        workload(
            wl_name,
            executables=weak_scaling_executables,
            inputs=["rtlmeter_src"],
        )
        workload_variable(
            "case",
            default=wl_case,
            description=f"{wl_desc} ({wl_name})",
            workloads=[wl_name],
        )

    workload_group(
        "case_workloads",
        workloads=list(compile_workloads.keys())
        + list(benchmark_workloads.keys()),
    )

    regression_workloads = {
        "regression_nvdla": (
            "NVDLA:*",
            "All six NVDLA tests (anet, relu, gnet, conv, pool, hello)",
        ),
        "regression_standard": (
            "+standard",
            "RTLMeter +standard suite (18 heterogeneous cases)",
        ),
        "regression_mixed": (
            "+standard NVDLA:*",
            "Mixed regression of 24 cases (+standard suite plus all six NVDLA tests)",
        ),
        "regression_custom": (
            "NVDLA:default:conv",
            "User-defined regression case list or pattern",
        ),
    }

    for wl_name, (wl_cases, wl_desc) in regression_workloads.items():
        workload(
            wl_name,
            executables=regression_executables,
            inputs=["rtlmeter_src"],
        )
        workload_variable(
            "regression_cases",
            default=wl_cases,
            description=f"RTLMeter case pattern(s) for {wl_name}: {wl_desc}",
            workloads=[wl_name],
        )
        workload_variable(
            "case",
            default=wl_cases,
            description=f"Case list used if build_model is run directly on {wl_name}",
            workloads=[wl_name],
        )

    workload_group("regression", workloads=list(regression_workloads.keys()))

    workload_variable(
        "regression_cases",
        default="{case}",
        description="Case list for regression executables when used on case_workloads",
        workload_group="case_workloads",
    )

    workload_group(
        "all_workloads",
        workloads=list(compile_workloads.keys())
        + list(benchmark_workloads.keys())
        + list(regression_workloads.keys()),
    )

    # -------------------------------------------------------------------------
    # Shared Workload Variables
    # -------------------------------------------------------------------------
    workload_variable(
        "rtlmeter_path",
        default="{rtlmeter_src}",
        description="Path to RTLMeter repository root (can be overridden to local path, e.g. /opt/rtlmeter)",
        workload_group="all_workloads",
    )

    workload_variable(
        "rtlmeter_cmd",
        default=(
            "if [ -x /opt/rtlmeter/rtlmeter ]; then "
            "export PYTHONPATH=/opt/rtlmeter; unset PYTHONHOME; RTL_CMD=(/opt/rtlmeter/rtlmeter); "
            'elif [ -f "{container_path}" ]; then '
            'RTL_CMD=(apptainer exec {apptainer_run_args} "{container_path}" /opt/rtlmeter/rtlmeter); '
            "else "
            'RTL_DIR="{rtlmeter_path}"; '
            'for d in "$RTL_DIR" "$RTL_DIR"/*; do '
            'if [ -d "$d/src/rtlmeter" ] || [ -f "$d/rtlmeter" ]; then RTL_DIR="$d"; break; fi; '
            "done; "
            'export RTLMETER_ROOT="$RTL_DIR"; '
            'export PYTHONPATH="$RTL_DIR/src:$RTL_DIR:$PYTHONPATH"; '
            'if [ -x "$RTL_DIR/venv/bin/python3" ]; then RTL_PY="$RTL_DIR/venv/bin/python3"; else RTL_PY="python3"; fi; '
            'RTL_CMD=("$RTL_PY" -m src.rtlmeter.main); '
            "fi; "
            '"${RTL_CMD[@]}"'
        ),
        description="Command invocation for RTLMeter runner",
        workload_group="all_workloads",
    )

    workload_variable(
        "rtlmeter_python",
        default="python3",
        description="Host Python (>= 3.10) used to run helper scripts and create the RTLMeter venv",
        workload_group="all_workloads",
    )

    # Mirrors RTLMeter's python-requirements.txt at the pinned commit
    # (d4cd38138eba33ea5121a76a8e8fc4aedebe0f5b)
    workload_variable(
        "rtlmeter_python_deps",
        default=(
            "jsonschema==4.23.0 numpy==2.2.2 pyyaml==6.0.2 scikit-learn==1.6.1 "
            "scipy==1.15.1 tabulate==0.9.0 termcolor==2.5.0 wcwidth==0.8.0"
        ),
        description="Python packages installed into <rtlmeter>/venv for the RTLMeter runner",
        workload_group="all_workloads",
    )

    workload_variable(
        "rtlmeter_setup",
        default=(
            'if [ -x /opt/rtlmeter/rtlmeter ] || [ -f "{container_path}" ]; then true; else ( '
            'RTL_DIR="{rtlmeter_path}"; '
            'for d in "$RTL_DIR" "$RTL_DIR"/*; do '
            'if [ -d "$d/src/rtlmeter" ] || [ -f "$d/rtlmeter" ]; then RTL_DIR="$d"; break; fi; '
            "done; "
            'RTL_VENV="$RTL_DIR/venv"; '
            "RTL_CHECK='import jsonschema, numpy, scipy, sklearn, tabulate, termcolor, yaml'; "
            'if ! "$RTL_VENV/bin/python3" -c "$RTL_CHECK" >/dev/null 2>&1; then '
            "( flock 9; "
            'if ! "$RTL_VENV/bin/python3" -c "$RTL_CHECK" >/dev/null 2>&1; then '
            'echo "=== Creating RTLMeter Python venv in $RTL_VENV ==="; '
            'rm -rf "$RTL_VENV" && {rtlmeter_python} -m venv "$RTL_VENV" && '
            '"$RTL_VENV/bin/python3" -m pip install --quiet --disable-pip-version-check '
            "{rtlmeter_python_deps}; "
            'fi ) 9>"$RTL_DIR/.venv.lock"; '
            "fi; "
            'if "$RTL_VENV/bin/python3" -c "$RTL_CHECK"; then '
            'echo "=== RTLMeter Python venv OK ==="; '
            'else echo "ERROR: RTLMeter Python dependencies missing in $RTL_VENV" >&2; exit 1; fi '
            ") || exit 1; fi"
        ),
        description="Bootstrap the RTLMeter Python virtual environment if needed",
        workload_group="all_workloads",
    )

    workload_variable(
        "compile_dir",
        default="{experiment_run_dir}/compile_root",
        description="Directory for verilated and compiled simulation models (shared between compile and benchmark runs)",
        workload_group="all_workloads",
    )

    workload_variable(
        "execute_dir",
        default="{experiment_run_dir}/execute_root",
        description="Directory for simulation execution runs (e.g. /scratch/$USER/val_sim/{experiment_name})",
        workload_group="all_workloads",
    )

    workload_variable(
        "n_execute",
        default="1",
        description="Number of simulation runs per test invocation",
        workload_group="all_workloads",
    )

    workload_variable(
        "compile_args",
        default="",
        description="Extra arguments passed to Verilator compilation (e.g. --compileArgs '--threads 2')",
        workload_group="all_workloads",
    )

    workload_variable(
        "additional_args",
        default="",
        description="Additional command line arguments for RTLMeter run",
        workload_group="all_workloads",
    )

    # Intra-allocation regression variables (Option 2 Lite)
    workload_variable(
        "regression_repeat",
        default="1",
        description="Repeat the regression_cases list R times (total tests = len(cases) * R)",
        workload_group="all_workloads",
    )

    workload_variable(
        "regression_claim_max",
        default="1",
        description=(
            "Max manifest indices a rank claims per shared-queue lock. Claims taper as "
            "remaining/(2*n_ranks) so the tail stays balanced. 1 = one lock per job. "
            "Use 16-64 for 10k+ ranks or when the queue lives on cross-region NFS."
        ),
        workload_group="all_workloads",
    )

    # -------------------------------------------------------------------------
    # Figures of Merit (FOMs)
    # -------------------------------------------------------------------------
    figure_of_merit_context(
        "step",
        regex=r"^(?P<step_name>verilate|cppbuild|compile|execute)\s*$",
        output_format="{step_name}",
    )

    figure_of_merit(
        "Step Elapsed Time",
        fom_regex=r"^\s*[│|]\s*All\s*[│|](?:.*[│|])?\s*(?P<step_elapsed>\d+\.?\d*)\s*[│|]\s*(?:\d+\.?\d*)\s*[│|]",
        group_name="step_elapsed",
        units="s",
        contexts=["step"],
    )

    figure_of_merit(
        "Step Peak Memory",
        fom_regex=r"^\s*[│|]\s*All\s*[│|](?:.*[│|])?\s*(?:\d+\.?\d*)\s*[│|]\s*(?P<step_mem>\d+\.?\d*)\s*[│|]",
        group_name="step_mem",
        units="MB",
        contexts=["step"],
    )

    metrics_log = os.path.join("{experiment_run_dir}", "metrics.out")

    # Option 1 Weak-Scaling Summary FOMs: "Weak <key>: <value>" in metrics.out
    weak_foms = [
        ("copies_total", "copies"),
        ("copies_passed", "copies"),
        ("copies_failed", "copies"),
        ("copies_missing", "copies"),
        ("makespan_s", "s"),
        ("copy_wall_min_s", "s"),
        ("copy_wall_p50_s", "s"),
        ("copy_wall_mean_s", "s"),
        ("copy_wall_p95_s", "s"),
        ("copy_wall_max_s", "s"),
        ("rtlmeter_all_min_s", "s"),
        ("rtlmeter_all_p50_s", "s"),
        ("rtlmeter_all_mean_s", "s"),
        ("rtlmeter_all_p95_s", "s"),
        ("rtlmeter_all_max_s", "s"),
        ("peak_mem_max_mb", "MB"),
    ]
    for fom_key, fom_units in weak_foms:
        figure_of_merit(
            f"Weak {fom_key}",
            log_file=metrics_log,
            fom_regex=r"^Weak\s+"
            + fom_key
            + r":\s+(?P<value>-?\d+\.?\d*)\s*$",
            group_name="value",
            units=fom_units,
        )

    # Option 2 Lite Regression FOMs: "Regression <key>: <value>" in metrics.out
    regression_foms = [
        ("tests_total", "tests"),
        ("tests_passed", "tests"),
        ("tests_failed", "tests"),
        ("ranks_active", "ranks"),
        ("max_concurrent_jobs", "jobs"),
        ("initial_ramp_s", "s"),
        ("initial_launch_rate_jobs_per_s", "jobs/s"),
        ("sustained_launch_rate_jobs_per_s", "jobs/s"),
        ("tail_drain_s", "s"),
        ("makespan_s", "s"),
        ("throughput_tests_per_hour", "tests/hour"),
        ("core_efficiency", ""),
        ("rank_imbalance_max_over_min", ""),
        ("test_wall_min_s", "s"),
        ("test_wall_p50_s", "s"),
        ("test_wall_mean_s", "s"),
        ("test_wall_p95_s", "s"),
        ("test_wall_max_s", "s"),
        ("sim_elapsed_mean_s", "s"),
        ("sim_speed_mean_khz", "kHz"),
        ("sim_peak_mem_max_mb", "MB"),
    ]
    for fom_key, fom_units in regression_foms:
        figure_of_merit(
            f"Regression {fom_key}",
            log_file=metrics_log,
            fom_regex=r"^Regression\s+"
            + fom_key
            + r":\s+(?P<value>-?\d+\.?\d*)\s*$",
            group_name="value",
            units=fom_units,
        )

    success_criteria(
        "passed",
        mode="string",
        match=r".*(All cases passed|=== Weak-scaling complete ===|=== Regression complete ===)",
        file="{log_file}",
    )

    success_criteria(
        "has_report",
        mode="string",
        match=r".*(Elapsed time \[s\]|=== Weak-scaling complete ===|=== Regression complete ===)",
        file="{log_file}",
    )

    success_criteria(
        "no_failed_tasks",
        mode="string",
        anti_match=r"^(Weak copies_failed|Regression tests_failed):\s+[1-9]",
        file=metrics_log,
    )

    def _prepare_analysis(self, workspace, app_inst=None):
        exp = (app_inst or self).expander
        rdir = exp.experiment_run_dir

        # metrics.out is rebuilt from the raw per-rank files on every analyze.
        # Remove the previous one first so it can never be reported again for
        # a run that produced no new data.
        metrics_path = os.path.join(rdir, "metrics.out")
        if os.path.isfile(metrics_path):
            os.remove(metrics_path)

        def mean(xs):
            return (sum(xs) / len(xs)) if xs else None

        def pct(xs, p):
            return (
                sorted(xs)[int(round((len(xs) - 1) * p / 100.0))]
                if xs
                else None
            )

        def fmt(v):
            if isinstance(v, float):
                return f"{v:.2f}"
            return str(v) if v is not None else "NA"

        out_lines = []

        try:
            n_expected = int(exp.expand_var_name("n_ranks"))
        except (TypeError, ValueError):
            n_expected = 0

        # 1. Weak-scaling per-copy analysis (weak_metrics/rank_*.report)
        wdir = os.path.join(rdir, "weak_metrics")
        if os.path.isdir(wdir):  # created by prepare_distributed
            wfiles = sorted(glob.glob(os.path.join(wdir, "rank_*.report")))
            # A rank that never launched, or died before writing its report,
            # leaves no file. Count it as failed instead of dropping it, and
            # never report an empty run as zero failures.
            copies_total = max(n_expected, len(wfiles), 1)
            w_walls, w_starts, w_ends, w_all_el, w_all_mem, w_pass = (
                [],
                [],
                [],
                [],
                [],
                0,
            )
            for wf in wfiles:
                with open(wf, encoding="utf-8", errors="replace") as fh:
                    txt = fh.read()
                m_rc = re.search(r"exit:\s*(\d+)", txt)
                m_t0 = re.search(r"Start Time:.*?\(epoch:\s*([0-9.]+)\)", txt)
                m_t1 = re.search(r"End Time:.*?\(epoch:\s*([0-9.]+)\)", txt)
                m_all = re.search(
                    r"^\s*[│|]\s*All\s*[│|].*?[│|]\s*([0-9.]+)\s*[│|]\s*([0-9.]+)\s*[│|]",
                    txt,
                    re.M,
                )
                if m_rc and int(m_rc.group(1)) == 0 and m_all:
                    w_pass += 1
                if m_t0 and m_t1:
                    t0, t1 = float(m_t0.group(1)), float(m_t1.group(1))
                    w_starts.append(t0)
                    w_ends.append(t1)
                    w_walls.append(t1 - t0)
                if m_all:
                    w_all_el.append(float(m_all.group(1)))
                    w_all_mem.append(float(m_all.group(2)))
            w_span = (
                (max(w_ends) - min(w_starts))
                if w_starts and max(w_ends) > min(w_starts)
                else None
            )
            for k, v in [
                ("copies_total", copies_total),
                ("copies_passed", w_pass),
                ("copies_failed", copies_total - w_pass),
                ("copies_missing", copies_total - len(wfiles)),
                ("makespan_s", w_span),
                ("copy_wall_min_s", pct(w_walls, 0)),
                ("copy_wall_p50_s", pct(w_walls, 50)),
                ("copy_wall_mean_s", mean(w_walls)),
                ("copy_wall_p95_s", pct(w_walls, 95)),
                ("copy_wall_max_s", pct(w_walls, 100)),
                ("rtlmeter_all_min_s", pct(w_all_el, 0)),
                ("rtlmeter_all_p50_s", pct(w_all_el, 50)),
                ("rtlmeter_all_mean_s", mean(w_all_el)),
                ("rtlmeter_all_p95_s", pct(w_all_el, 95)),
                ("rtlmeter_all_max_s", pct(w_all_el, 100)),
                ("peak_mem_max_mb", max(w_all_mem) if w_all_mem else None),
            ]:
                out_lines.append(f"Weak {k}: {fmt(v)}")

        # 2. Regression per-test analysis (regression_metrics/*.timing)
        mpath = os.path.join(rdir, "regression_manifest.tsv")
        mdir = os.path.join(rdir, "regression_metrics")
        if os.path.exists(mpath):
            with open(mpath, encoding="utf-8") as mfh:
                n_total = sum(1 for ln in mfh if ln.strip())
            (
                walls,
                starts,
                ends,
                sim_el,
                sim_spd,
                sim_mem,
                n_pass,
                rank_busy,
                rank_last_end,
            ) = (
                [],
                [],
                [],
                [],
                [],
                [],
                0,
                {},
                {},
            )
            seen_idx = set()
            for tf in sorted(glob.glob(os.path.join(mdir, "*.timing"))):
                with open(tf, encoding="utf-8", errors="replace") as tfh:
                    tlines = tfh.readlines()
                for raw in tlines:
                    p = raw.rstrip("\n").split("\t")
                    if len(p) < 9 or not p[0].isdigit() or p[0] in seen_idx:
                        continue
                    try:
                        rk, t0, t1, rc = (
                            p[1],
                            float(p[5]),
                            float(p[7]),
                            int(p[8]),
                        )
                    except ValueError:
                        continue
                    seen_idx.add(p[0])
                    cols = (
                        [
                            c.strip()
                            for c in re.split(r"[│|]", p[9])
                            if c.strip()
                        ]
                        if len(p) >= 10
                        else []
                    )
                    if len(cols) >= 5:
                        try:
                            sim_spd.append(float(cols[2]))
                            sim_el.append(float(cols[3]))
                            sim_mem.append(float(cols[4]))
                        except ValueError:
                            pass
                    walls.append(t1 - t0)
                    starts.append(t0)
                    ends.append(t1)
                    rank_busy[rk] = rank_busy.get(rk, 0.0) + (t1 - t0)
                    if t1 > rank_last_end.get(rk, 0.0):
                        rank_last_end[rk] = t1
                    n_pass += int(rc == 0 and len(cols) >= 5)
            span = (
                (max(ends) - min(starts))
                if starts and max(ends) > min(starts)
                else None
            )
            bvals = list(rank_busy.values())
            events = sorted(
                [(t0, 1) for t0 in starts] + [(t1, -1) for t1 in ends]
            )
            cur_c = max_c = 0
            for _, d in events:
                cur_c += d
                if cur_c > max_c:
                    max_c = cur_c
            s_sorted = sorted(starts)
            n_rk = len(rank_busy)
            n_alloc = max(n_expected, n_rk)
            wave0 = s_sorted[:n_rk] if n_rk else []
            ramp_s = (
                (wave0[-1] - wave0[0])
                if len(wave0) > 1 and wave0[-1] > wave0[0]
                else None
            )
            init_rate = (len(wave0) / ramp_s) if ramp_s else None
            launch_span = (
                (s_sorted[-1] - s_sorted[0])
                if len(s_sorted) > 1 and s_sorted[-1] > s_sorted[0]
                else None
            )
            sust_rate = (len(s_sorted) / launch_span) if launch_span else None
            tail_s = (
                (max(rank_last_end.values()) - min(rank_last_end.values()))
                if rank_last_end
                else None
            )
            for k, v in [
                ("tests_total", n_total),
                ("tests_passed", n_pass),
                ("tests_failed", n_total - n_pass),
                ("ranks_active", n_rk),
                ("max_concurrent_jobs", max_c),
                ("initial_ramp_s", ramp_s),
                ("initial_launch_rate_jobs_per_s", init_rate),
                ("sustained_launch_rate_jobs_per_s", sust_rate),
                ("tail_drain_s", tail_s),
                ("makespan_s", span),
                (
                    "throughput_tests_per_hour",
                    (n_pass / (span / 3600.0)) if span else None,
                ),
                (
                    "core_efficiency",
                    (
                        (sum(walls) / (n_alloc * span))
                        if (n_alloc and span)
                        else None
                    ),
                ),
                (
                    "rank_imbalance_max_over_min",
                    (
                        (max(bvals) / min(bvals))
                        if bvals and min(bvals) > 0
                        else None
                    ),
                ),
                ("test_wall_min_s", pct(walls, 0)),
                ("test_wall_p50_s", pct(walls, 50)),
                ("test_wall_mean_s", mean(walls)),
                ("test_wall_p95_s", pct(walls, 95)),
                ("test_wall_max_s", pct(walls, 100)),
                ("sim_elapsed_mean_s", mean(sim_el)),
                ("sim_speed_mean_khz", mean(sim_spd)),
                ("sim_peak_mem_max_mb", max(sim_mem) if sim_mem else None),
            ]:
                out_lines.append(f"Regression {k}: {fmt(v)}")

        if out_lines:
            with open(metrics_path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(out_lines) + "\n")
