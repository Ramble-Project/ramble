# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os

from ramble.appkit import *
from ramble.expander import Expander


class Sleep(ExecutableApplication):
    """This is an example application that will simply run sleep for a
    controlled random amount of time"""

    name = "sleep"

    tags("system-utility", "test-app")

    maintainers("douglasjacobsen")

    time_file = os.path.join(
        Expander.expansion_str("experiment_run_dir"), "time_output"
    )
    executable(
        "define_sleep_time",
        "export SLEEP_TIME={sleep_seconds}",
        output_capture="",
        redirect="",
    )
    executable(
        "sleep", "/usr/bin/time sleep $SLEEP_TIME", output_capture="&>>"
    )
    executable("echo", 'echo "Sleep for $SLEEP_TIME seconds"')

    workload("sleep", executables=["define_sleep_time", "echo", "sleep"])
    workload("rand_sleep", executables=["define_sleep_time", "echo", "sleep"])

    workload_variable(
        "sleep_seconds",
        default="3",
        description="Number of seconds to sleep for",
        workloads=["sleep"],
    )

    workload_variable(
        "rand_min",
        default="1",
        description="Minimum of the random range",
        workloads=["rand_sleep"],
    )

    workload_variable(
        "rand_max",
        default="5",
        description="Maximum of the random range",
        workloads=["rand_sleep"],
    )

    workload_variable(
        "sleep_seconds",
        default="{randint({rand_min}, {rand_max})}",
        description="Number of seconds to sleep for",
        workloads=["rand_sleep"],
    )

    echo_regex = r"Sleep for (?P<time>[0-9]+) seconds"
    figure_of_merit(
        "Sleep time",
        fom_regex=echo_regex,
        group_name="time",
        units="s",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "User time",
        fom_regex=r"(?P<user_time>[0-9]+\.[0-9]+)user",
        group_name="user_time",
        units="s",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "Elapsed minutes",
        fom_regex=r".*?(?P<mins>[0-9]+):(?P<secs>[0-9]+)\.(?P<millisecs>[0-9]+)elapsed",
        group_name="mins",
        units="minutes",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "Elapsed seconds",
        fom_regex=r".*?(?P<mins>[0-9]+):(?P<secs>[0-9]+)\.(?P<millisecs>[0-9]+)elapsed",
        group_name="secs",
        units="s",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "Elapsed milliseconds",
        fom_regex=r".*?(?P<mins>[0-9]+):(?P<secs>[0-9]+)\.(?P<millisecs>[0-9]+)elapsed",
        group_name="millisecs",
        units="ms",
        fom_type=FomType.TIME,
    )

    figure_of_merit(
        "mode",
        fom_regex=r"\s*(?P<mode>(Sleep|Wake)) for.*",
        group_name="mode",
        units="",
        fom_type=FomType.CATEGORY,
    )

    success_criteria("printed_sleep_time", mode="string", match=echo_regex)
