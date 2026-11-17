# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import platform

import ramble.util.version

import spack.platforms

description = "debugging commands for troubleshooting Ramble"
section = "developer"
level = "long"


def setup_parser(subparser):
    sp = subparser.add_subparsers(metavar="SUBCOMMAND", dest="debug_command")
    sp.add_parser("report", help="print information useful for bug reports")


def report(args):
    host_platform = spack.platforms.host()
    host_os = host_platform.operating_system("frontend")
    host_target = host_platform.target("frontend")
    architecture = f"{host_platform}-{host_os}-{host_target}"
    print("* **Ramble:**", ramble.util.version.get_version())
    print("* **Python:**", platform.python_version())
    print("* **Platform:**", architecture)


def debug(parser, args):
    action = {
        "report": report,
    }
    action[args.debug_command](args)
