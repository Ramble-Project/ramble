# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
from collections import defaultdict

from ramble.modkit import *

_TUNABLE_LOG = "{experiment_run_dir}/tunables.log"

_PDSH_PREFIX = "pdsh -R ssh -w {hostlist}"

_FOM_ID = "fom"


class Tunables(BasicModifier):
    """A modifier for inspecting various tunables of the system."""

    name = "tunables"

    tags("system-info", "sysinfo", "platform-info")

    maintainers("linsword13")

    # TODO: add a "write" mode to manage some of the tunables.
    mode("info", description="info (read-only) mode for tunables")
    default_mode("info")

    software_spec(
        "pdsh", pkg_spec="pdsh", when=["package_manager_family=spack"]
    )

    required_variable("hostlist", modes=["info"], description="")

    archive_pattern("tunables.log")

    # Most of these OS-level tunables are mentioned in
    # https://www.amd.com/content/dam/amd/en/documents/epyc-technical-docs/tuning-guides/58479_amd-epyc-9005-tg-hpc.pdf
    info_list = [
        {
            "name": "address-space-randomization",
            "cmd": "cat /proc/sys/kernel/randomize_va_space",
            "fom_type": FomType.CATEGORY,
        },
        {
            "name": "numa-balancing",
            "cmd": "cat /proc/sys/kernel/numa_balancing",
            "fom_type": FomType.CATEGORY,
        },
        {
            "name": "smt-active",
            "cmd": "cat /sys/devices/system/cpu/smt/active",
            "fom_type": FomType.CATEGORY,
        },
        {
            "name": "thp-enabled",
            "cmd": "cat /sys/kernel/mm/transparent_hugepage/enabled | awk -F'[][]' '{print $2}'",
            "fom_type": FomType.CATEGORY,
        },
        {
            "name": "thp-defrag",
            "cmd": "cat /sys/kernel/mm/transparent_hugepage/defrag | awk -F'[][]' '{print $2}'",
            "fom_type": FomType.CATEGORY,
        },
        {
            "name": "hugepage-size",
            "cmd": "grep -i Hugepagesize /proc/meminfo | cut -d ':' -f 2",
            "fom_type": FomType.CATEGORY,
        },
        {
            "name": "hugepage-count",
            "cmd": "grep -i HugePages_Total /proc/meminfo | cut -d ':' -f 2",
            "fom_type": FomType.MEASURE,
        },
    ]

    register_builtin("get_tunable_info", injection_method="append")

    def get_tunable_info(self):
        """Collect tunable information."""
        cmd_list = []
        pdsh_prefix = self.expander.expand_var(_PDSH_PREFIX)
        for conf in self.info_list:
            cmd_prefix = f'{_FOM_ID}:{conf["name"]}:'
            cmd = conf["cmd"]
            cmd_list.append(
                f'{pdsh_prefix} "echo \\"{cmd_prefix}$({cmd})\\"" >> {_TUNABLE_LOG}'
            )
        return cmd_list

    def _prepare_analysis(self, workspace):
        del workspace
        log_path = self.expander.expand_var(_TUNABLE_LOG)
        if not os.path.isfile(log_path):
            return
        summary = defaultdict(dict)
        with open(log_path, encoding="utf-8") as f:
            for line in f:
                tuples = [v.strip() for v in line.split(":")]
                if len(tuples) < 2 or tuples[1] != _FOM_ID:
                    continue
                [host, _, name, value] = tuples
                if value not in summary[name]:
                    summary[name][value] = {host}
                else:
                    summary[name][value].add(host)
        for n, sum_dict in summary.items():
            if len(sum_dict) == 1:
                metric = next(iter(sum_dict))
            else:
                metric = sum_dict
            self.add_inmem_fom_value(n, str(metric))

    for conf in info_list:
        figure_of_merit(
            conf["name"],
            units="",
            fom_map_key=conf["name"],
            fom_type=conf["fom_type"],
        )
