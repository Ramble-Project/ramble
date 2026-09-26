# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

from ramble.appkit import *

from spack.util.path import canonicalize_path


class Fio(ExecutableApplication):
    """Flexible I/O Tester. Fio spawns a number of threads or processes doing a
    particular type of I/O action as specified by the user. fio takes a number
    of global parameters, each inherited by the thread unless otherwise
    parameters given to them overriding that setting is given.
    """

    name = "fio"

    maintainers("dapomeroy")

    tags("io-benchmark", "storage-benchmark")

    version("3.37", "Version 3.37 of fio", preferred=True)

    with when("package_manager_family=spack"):
        define_compiler("gcc13", pkg_spec="gcc@13.1.0")
        software_spec(
            "fio-{application::fio::version}",
            pkg_spec="fio@{application::fio::version} +libaio",
            compiler="gcc13",
        )

    executable(
        "run",
        template=[
            "echo 'Running job file {job_file}...'",
            "fio --output={out_file} --output-format {out_format} --eta=never {job_file_path}",
        ],
        use_mpi=False,
    )

    # Use client/server mode to run on multiple nodes
    executable(
        "multinode-run",
        template=[
            "echo 'Starting fio servers...'",
            "pdsh -w {hostlist} {experiment_run_dir}/fio_start_server.sh",
            "echo 'Creating test directory if needed...'",
            "mkdir -p {directory}",
            'echo "Running job file {job_file} on nodes: {hostlist}"',
            "fio --output={out_file} --output-format {out_format} --eta=never --client={hostfile} {job_file_path}",
            "echo 'Fio jobs finished.'",
            "echo 'Stopping fio servers...'",
            "pdsh -w {hostlist} {experiment_run_dir}/fio_stop_server.sh",
        ],
        use_mpi=False,
    )

    executable(
        "cleanup",
        template=[
            "echo 'Deleting temporary files'",
            "rm -f {directory}/*{experiment_name}.[0-9]*",
        ],
        use_mpi=False,
    )

    workload("standard", executables=["run", "cleanup"])
    workload("multinode", executables=["multinode-run", "cleanup"])
    workload_group("all_workloads", workloads=["standard", "multinode"])

    with default_args(workload_group="all_workloads"):
        workload_variable(
            "job_file",
            description="Job file to run. If a job file is not specified, one will be generated from variables.",
            default="generated.conf",
        )
        workload_variable(
            "job_file_path",
            description="Path to job file.",
            default="{experiment_run_dir}/{job_file}",
        )
        workload_variable(
            "out_file",
            description="File to write results",
            default="fio.out",
        )
        workload_variable(
            "out_format",
            description="Format to write results. Defaults to 'json' for Ramble to analyze results.",
            default="json",
        )
        workload_variable(
            "job_name",
            description="Job name",
            default="{experiment_name}",
        )
        workload_variable(
            "directory",
            description="Used to place files in a different location than ./",
            default="{experiment_run_dir}",
        )

        # variables set using strings / numbers stored as strings
        _STR_VARS = {
            "ioengine",
            "runtime",
            "size",
            "rw",
            "bs",
            "iodepth",
            "numjobs",
            "directory",
        }

        # variables that are set using boolean value (var=0|1)
        _BOOL_VARS = {
            "buffered",
            "direct",
            "randrepeat",
        }

        # variables that are set using the var name, defaults to unset
        _SET_VARS = {
            "group_reporting",
            "norandommap",
            "refill_buffers",
            "time_based",
            "stonewall",
        }

        # If not set in Ramble, workload vars are not written to job file / use fio application default
        workload_variable(
            "ioengine",
            description="I/O engine",
            default=None,
        )
        workload_variable(
            "direct",
            description="If true, use non-buffered I/O",
            default=None,
        )
        workload_variable(
            "buffered",
            description="If true, use buffered I/O. This is the opposite of the direct option",
            default=None,
        )
        workload_variable(
            "time_based",
            description="If set, fio will run for the duration of the runtime specified even if the file(s) are completely read or written.",
            default=None,
        )
        workload_variable(
            "runtime",
            description="Limit runtime. The test will run until it completes the configured I/O workload or until it has run for this specified amount of time, whichever occurs first.",
            default=None,
        )
        workload_variable(
            "refill_buffers",
            description="If this option is given, fio will refill the I/O buffers on every submit. ",
            default=None,
        )
        workload_variable(
            "norandommap",
            description="Normally fio will cover every block of the file when doing random I/O. If this option is given, fio will just get a new random offset without looking at past I/O history.",
            default=None,
        )
        workload_variable(
            "randrepeat",
            description="Seed all random number generators in a predictable way so the pattern is repeatable across runs. ",
            default=None,
        )
        workload_variable(
            "group_reporting",
            description="To see the final report per-group instead of per-job, use group_reporting. Jobs in a file will be part of the same reporting group, unless if separated by a stonewall, or by using new_group.",
            default=None,
        )
        workload_variable(
            "size",
            description="The total size of file I/O for each thread of this job.",
            default=None,
        )
        workload_variable(
            "rw",
            description="Type of I/O pattern",
            default=None,
        )
        workload_variable(
            "bs",
            description="The block size in bytes used for I/O units.",
            default=None,
        )
        workload_variable(
            "iodepth",
            description="Number of I/O units to keep in flight against the file.",
            default=None,
        )
        workload_variable(
            "numjobs",
            description="Create the specified number of clones of this job.",
            default=None,
        )

    # Job-level FOMs
    job_fom_defs = [
        ("Job Name", "jobname", ""),
        ("Job Runtime", "job_runtime", "msec"),
        ("CPU Usage (User)", "usr_cpu", ""),
        ("CPU Usage (System)", "sys_cpu", ""),
        ("Context Switches", "ctx", ""),
        ("Major Faults", "majf", ""),
        ("Minor Faults", "minf", ""),
        ("FIO Version", "fio version", ""),
    ]

    for fom_title, fom_key, fom_unit in job_fom_defs:
        figure_of_merit(
            fom_title,
            fom_map_key=fom_key,
            units=fom_unit,
        )

    # Shared FOMs for read, write, trim I/O modes
    shared_fom_defs = [
        ("Total I/O (Bytes)", "io_bytes", "B"),
        ("Total I/O", "io_kbytes", "KiB"),
        ("Bandwidth B/sec", "bw_bytes", "B/sec"),
        ("Bandwidth", "bw", "KiB/sec"),
        ("IOPS", "iops", ""),
        ("Runtime", "runtime", "msec"),
        ("Total I/Os", "total_ios", ""),
        ("Short I/Os", "short_ios", ""),
        ("Dropped I/Os", "drop_ios", ""),
        ("Submission Latency (Min)", "slat_min", "ns"),
        ("Submission Latency (Max)", "slat_max", "ns"),
        ("Submission Latency (Mean)", "slat_mean", "ns"),
        ("Submission Latency (StdDev)", "slat_stddev", "ns"),
        ("Submission Latency (N)", "slat_N", ""),
        ("Completion Latency (Min)", "clat_min", "ns"),
        ("Completion Latency (Max)", "clat_max", "ns"),
        ("Completion Latency (Mean)", "clat_mean", "ns"),
        ("Completion Latency (StdDev)", "clat_stddev", "ns"),
        ("Completion Latency (N)", "clat_N", ""),
        ("Total Latency (Min)", "lat_min", "ns"),
        ("Total Latency (Max)", "lat_max", "ns"),
        ("Total Latency (Mean)", "lat_mean", "ns"),
        ("Total Latency (StdDev)", "lat_stddev", "ns"),
        ("Total Latency (N)", "lat_N", ""),
        ("Bandwidth (Min)", "bw_min", ""),
        ("Bandwidth (Max)", "bw_max", ""),
        ("Bandwidth (Aggregate % of Total)", "bw_agg", ""),
        ("Bandwidth (Mean)", "bw_mean", ""),
        ("Bandwidth (StdDev)", "bw_dev", ""),
        ("Bandwidth (N Samples)", "bw_samples", ""),
        ("IOPS (Min)", "iops_min", ""),
        ("IOPS (Max)", "iops_max", ""),
        ("IOPS (Mean)", "iops_mean", ""),
        ("IOPS (StdDev)", "iops_stddev", ""),
        ("IOPS (N Samples)", "iops_samples", ""),
    ]

    for io_mode in ["read", "write", "trim"]:
        for fom_title, fom_key, fom_unit in shared_fom_defs:
            figure_of_merit(
                f"{io_mode} {fom_title}",
                fom_map_key=f"{io_mode}:{fom_key}",
                units=fom_unit,
            )

    register_template(
        "fio_start_server",
        src_path="fio_start_server.sh.tpl",
        dest_path="fio_start_server.sh",
        extra_vars_func="software_env_cmds",
    )

    def _software_env_cmds(self):
        env_commands = ""
        if self.package_manager:
            env_commands = self.package_manager.environment_load_commands()
        if isinstance(env_commands, list):
            env_commands = "\n".join(env_commands)

        return {"load_software_env": env_commands}

    register_template(
        "fio_stop_server",
        src_path="fio_stop_server.sh.tpl",
        dest_path="fio_stop_server.sh",
    )

    register_phase(
        "write_jobfile", pipeline="setup", run_after=["make_experiments"]
    )

    def _write_jobfile(self, workspace, app_inst):
        """Writes a job file if one is not specified"""
        job_file = self.expander.expand_var_name("job_file")
        if job_file != "generated.conf":
            return

        jobfile_path = get_file_path(
            canonicalize_path(
                os.path.join(
                    self.expander.expand_var_name("experiment_run_dir"),
                    job_file,
                )
            ),
            workspace,
        )

        with open(jobfile_path, "w+", encoding="utf-8") as f:
            f.write(
                "[" + self.expander.expand_var_name("experiment_name") + "]\n"
            )
            for str_var in self._STR_VARS:
                str_val = self.expander.expand_var_name(str_var)
                if str_val != "None":
                    f.write(f"{str_var}={str_val}\n")

            for bool_var in self._BOOL_VARS:
                bool_val = self.expander.expand_var_name(bool_var, typed=True)
                if bool_val != "None":
                    # FIO takes bool as int
                    if bool(bool_val) is True:
                        bool_val = 1
                    else:
                        bool_val = 0
                    f.write(f"{bool_var}={bool_val}\n")

            for set_var in self._SET_VARS:
                set_val = self.expander.expand_var_name(set_var, typed=True)
                if set_val != "None":
                    f.write(f"{set_var}\n")

    def _prepare_analysis(self, workspace, app_inst):
        """Reads JSON metrics from fio.out and records in-memory FOMs.

        FIO outputs a single JSON with a list of all jobs in the job file. Each
        job has nested dicts up to 4 levels deep. Since Ramble only supports a
        single level of contexts, these levels have been flattened and Ramble
        generates one job per experiment/job file.

        For standard workloads, a single job output is generated. For
        client/server multinode workloads, Ramble uses the summary of all
        clients.
        """
        import json

        def _split_unit(in_str):
            if "_ns" in in_str or "_us" in in_str or "_ms" in in_str:
                metric, unit = in_str.split("_")
            else:
                metric, unit = in_str, ""
            return metric, unit

        fio_outfile = get_file_path(
            canonicalize_path(
                os.path.join(
                    app_inst.expander.experiment_run_dir,
                    app_inst.expander.expand_var_name("out_file"),
                )
            ),
            workspace,
        )

        if not os.path.exists(fio_outfile):
            return

        with open(fio_outfile, encoding="utf-8") as f:
            file = ""
            # ignore client/server output headers that begin with <server-hostname>
            for line in f:
                if line.startswith("<"):
                    continue
                else:
                    file += line

            try:
                metrics_dict = json.loads(file)

                data_key = "jobs"
                # client/server mode outputs data with a different key
                if "client_stats" in metrics_dict:
                    data_key = "client_stats"

                # for standard mode using generated conf, there should be one job in dict["jobs"]
                # for client/server mode, if run on a single node/server there will be one job in
                # dict["client_stats"]. If run on n>1 nodes/servers, output is n jobs and 1 summary
                if len(metrics_dict[data_key]) == 1:
                    job = metrics_dict[data_key][0]
                elif (
                    len(metrics_dict[data_key]) > 1
                    and data_key == "client_stats"
                ):
                    for j in metrics_dict[data_key]:
                        # When summary exists, skip individual jobs
                        if j["jobname"] != "All clients":
                            continue
                        else:
                            job = j
                else:
                    logger.warn(
                        "Found more than one job result in experiment output."
                    )

                # first level: job-level data, read/write dicts, depth/latency dicts, etc
                for key, val in job.items():
                    if isinstance(val, dict):
                        # second level: read/write data, depth/latency stats, statistical dicts
                        for key2, val2 in val.items():
                            if isinstance(val2, dict):
                                key2, unit = _split_unit(key2)
                                scale = {"us": 1000, "ms": 1000000}.get(
                                    unit, 1
                                )

                                # third level: contains values and percentile dict, flatten with l2
                                for key3, val3 in val2.items():
                                    # todo: if percentile data is useful, flatten and add FOM(s)
                                    if key3 == "percentile":
                                        continue

                                    if key3 != "N":
                                        val3 = val3 * scale

                                    self.add_inmem_fom_value(
                                        f"{key}:{key2}_{key3}", val3
                                    )
                            else:
                                self.add_inmem_fom_value(f"{key}:{key2}", val2)
                    else:
                        self.add_inmem_fom_value(key, val)

                self.add_inmem_fom_value(
                    "fio version", metrics_dict["fio version"]
                )

            except Exception as e:
                logger.warn(f"Error reading metrics data: {e}")
