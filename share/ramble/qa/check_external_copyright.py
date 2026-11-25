#!/usr/bin/env python3
# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import re
import sys

# Packages with special locations
_LOCATIONS = {
    "sbang": "bin/sbang",
}


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ramble_root = os.path.abspath(os.path.join(script_dir, "..", "..", ".."))

    copyright_path = os.path.join(ramble_root, "COPYRIGHT")
    external_dir = os.path.join(ramble_root, "lib", "ramble", "external")

    if not os.path.exists(copyright_path):
        print(f"Error: COPYRIGHT file not found at {copyright_path}", file=sys.stderr)
        return 1

    copyright_packages = set()
    with open(copyright_path, "r", encoding="utf-8") as f:
        content = f.read()

    matches = re.findall(r"^PackageName:\s*(\S+)", content, flags=re.MULTILINE)
    for pkg in matches:
        copyright_packages.add(pkg)

    copyright_expected_paths = {}
    for pkg in copyright_packages:
        if pkg in _LOCATIONS:
            copyright_expected_paths[pkg] = {_LOCATIONS[pkg]}
        else:
            copyright_expected_paths[pkg] = {
                f"lib/ramble/external/{pkg}",
                f"lib/ramble/external/{pkg}.py",
            }

    actual_relative_paths = set()

    for rel_path in _LOCATIONS.values():
        if os.path.exists(os.path.join(ramble_root, rel_path)):
            actual_relative_paths.add(rel_path)

    if os.path.isdir(external_dir):
        for entry in os.listdir(external_dir):
            if entry.startswith(("__", ".")):
                continue
            full_path = os.path.join(external_dir, entry)
            rel_path = os.path.relpath(full_path, ramble_root)
            actual_relative_paths.add(rel_path)

    errors = []

    # Check that every package in COPYRIGHT is present in the filesystem
    for pkg, expected_paths in copyright_expected_paths.items():
        if not any(os.path.exists(os.path.join(ramble_root, p)) for p in expected_paths):
            display_path = min(expected_paths)
            errors.append(f"Package '{pkg}' is listed in COPYRIGHT but not found (expected: '{display_path}')")

    # Check that every actual filesystem path is documented in COPYRIGHT
    for actual_rel_path in actual_relative_paths:
        matched_pkg = None
        for pkg, expected_paths in copyright_expected_paths.items():
            if actual_rel_path in expected_paths:
                matched_pkg = pkg
                break
        if not matched_pkg:
            errors.append(f"Found path '{actual_rel_path}' in the filesystem but it is not listed in COPYRIGHT")

    if errors:
        print("Copyright/External verification failed:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("Verification successful: COPYRIGHT matches bundled external packages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
