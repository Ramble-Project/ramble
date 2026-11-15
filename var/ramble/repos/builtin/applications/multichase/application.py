# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from ramble.appkit import *

_LATENCY_REGEX = r"^\s*(?P<latency>[0-9\.]+)\s*$"


class Multichase(ExecutableApplication):
    """Multichase pointer chaser benchmark.

    Includes a latency workload that benchmarks latency for a given array size.
    """

    name = "multichase"

    maintainers("linsword")

    tags("benchmark", "memory", "latency", "bandwidth")

    with when("package_manager_family=spack"):
        define_compiler("gcc", pkg_spec="gcc")
        software_spec(
            "multichase",
            pkg_spec="multichase",
            compiler="gcc",
        )
        required_package("multichase")

    executable(
        "execute",
        "{multichase_bin} -m {array_size} {additional_args}",
        use_mpi=False,
    )

    # Workloads
    workload("latency", executable="execute")

    # Workload variables for latency
    workload_variable(
        "multichase_bin",
        default="multichase",
        description="Path or binary name for multichase",
        workloads=["latency"],
    )
    workload_variable(
        "array_size",
        default="1g",
        description="Array size for pointer chasing",
        workloads=["latency"],
    )
    workload_variable(
        "stride",
        default="256",
        description="Stride size in bytes",
        workloads=["latency"],
    )
    workload_variable(
        "threads",
        default="1",
        description="Number of threads",
        workloads=["latency"],
    )
    workload_variable(
        "samples",
        default="5",
        description="Number of 0.5 second samples",
        workloads=["latency"],
    )
    workload_variable(
        "additional_args",
        default="-s {stride} -t {threads} -n {samples}",
        description="Additional arguments for multichase",
        workloads=["latency"],
    )

    register_validator(
        name="single_node",
        predicate="{n_nodes} == 1",
        message=(
            "The multichase application is intended to be used on a single "
            "node, but is configured with n_nodes = {n_nodes}"
        ),
        fail_on_invalid=False,
    )

    with when("workload_name=latency"):
        figure_of_merit(
            "Multichase Best Latency",
            fom_regex=_LATENCY_REGEX,
            group_name="latency",
            units="ns",
        )

        def _parse_array_size(app):
            s = str(app.expander.expand_var("{array_size}")).strip().lower()
            units = {"k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}
            if s and s[-1] in units:
                return int(float(s[:-1]) * units[s[-1]])
            return int(float(s))

        figure_of_merit(
            "Array Size",
            formula=_parse_array_size,
            units="bytes",
        )
