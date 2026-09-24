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


def edit_file(args):
    if not os.path.exists(args.file):
        content = ""
    else:
        # Use newline='' to preserve original line endings across platforms
        with open(args.file, newline="", encoding="utf-8") as f:
            content = f.read()

    def unescape(s):
        if s is None:
            return None
        return s.encode("utf-8").decode("unicode_escape")

    new_content = content
    if args.mode == "regex":
        if args.function:
            func = None
            if args.import_module:
                import importlib.util

                if not os.path.exists(args.import_module):
                    print(f"Error: Module file {args.import_module} not found.")
                    return 1
                spec = importlib.util.spec_from_file_location(
                    "custom_functions", args.import_module
                )
                if spec is None or spec.loader is None:
                    print(f"Error: Could not load spec for module {args.import_module}.")
                    return 1
                custom_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(custom_module)
                func = getattr(custom_module, args.function, None)
            else:
                func = globals().get(args.function)

            if func:
                new_content = func(content)
                if not isinstance(new_content, str):
                    print(
                        f"Error: Function {args.function} must return a string, "
                        f"not {type(new_content).__name__}"
                    )
                    return 1
            else:
                print(f"Error: Function {args.function} not found.")
                return 1

        if args.match and args.replace is not None:
            new_content = re.sub(args.match, unescape(args.replace), new_content)
        if args.append:
            new_content = new_content + unescape(args.append)
        if args.prepend:
            new_content = unescape(args.prepend) + new_content
    elif args.mode == "patch":
        if not shutil.which("patch"):
            print("Error: 'patch' utility not found.")
            print(
                "On Windows, please ensure a tool providing 'patch' "
                "(e.g., Git Bash, MSYS2, Cygwin) is installed and in your PATH."
            )
            return 1

        import subprocess

        try:
            subprocess.run(["patch", args.file, args.patch_file], check=True)
            return 0
        except Exception as e:
            print(f"Error applying patch: {e}")
            return 1

    needs_write = new_content != content or not os.path.exists(args.file)
    if needs_write:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(args.file)), exist_ok=True)
        with open(args.file, "w", newline="", encoding="utf-8") as f:
            f.write(new_content)

    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ramble File Editor")
    parser.add_argument("--mode", choices=["regex", "patch"], required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--match", help="Regex pattern to match")
    parser.add_argument("--replace", help="Replacement string")
    parser.add_argument("--append", help="String to append")
    parser.add_argument("--prepend", help="String to prepend")
    parser.add_argument("--patch-file", help="Path to patch file")
    parser.add_argument("--function", help="Name of custom function to execute")
    parser.add_argument(
        "--import-module", help="Path to python module containing custom functions"
    )

    args = parser.parse_args()
    sys.exit(edit_file(args))
