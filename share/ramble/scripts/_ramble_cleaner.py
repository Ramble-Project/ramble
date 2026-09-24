# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import argparse
import os
import re
import shutil
import sys


def matches_whole_path(regex, path):
    return regex.fullmatch(path) is not None


def perform_cleanup(args):
    directory = args.directory
    pattern = args.regex
    recurse = args.recurse

    if not os.path.isdir(directory):
        print(f"Directory {directory} does not exist. Skipping cleanup.", file=sys.stderr)
        return 0

    try:
        regex = re.compile(pattern)
    except re.error as e:
        print(f"Invalid regex pattern '{pattern}': {e}", file=sys.stderr)
        return 1

    paths_to_delete = []
    if recurse:
        for root, dirs, files in os.walk(directory, topdown=True):
            for d in list(dirs):
                d_path = os.path.join(root, d)
                if matches_whole_path(regex, d_path):
                    paths_to_delete.append(d_path)
                    dirs.remove(d)
            for f in files:
                f_path = os.path.join(root, f)
                if matches_whole_path(regex, f_path):
                    paths_to_delete.append(f_path)
    else:
        try:
            with os.scandir(directory) as entries:
                paths_to_delete.extend(
                    entry.path
                    for entry in entries
                    if matches_whole_path(regex, entry.path)
                )
        except Exception as e:
            print(f"Error scanning directory {directory}: {e}", file=sys.stderr)
            return 1

    for path in paths_to_delete:
        try:
            if os.path.islink(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as e:
            print(f"Error removing {path}: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ramble Directory Cleaner")
    parser.add_argument("--directory", required=True, help="Directory to clean")
    parser.add_argument("--regex", required=True, help="Regex pattern to match paths")
    parser.add_argument("--recurse", action="store_true", help="Search recursively")

    args = parser.parse_args()
    sys.exit(perform_cleanup(args))
