# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import argparse
import math
import os
import sys
from typing import Callable, Dict

from llnl.util.tty.colify import colify

import ramble.repository
from ramble.cmd.common import arguments
from ramble.util import object_utils
from ramble.util.logger import logger

formatters: Dict[str, Callable] = {}


def formatter(func):
    """Decorator used to register formatters"""
    formatters[func.__name__] = func
    return func


@formatter
def name_only(objs, out, object_type):
    obj_def = ramble.repository.type_definitions[object_type]
    indent = 0
    if out.isatty():
        logger.msg(f'{len(objs)} {obj_def["dir_name"]}')
    colify(objs, indent=indent, output=out)


def rows_for_ncols(elts, ncols):
    """Print out rows in a table with ncols of elts laid out vertically."""
    clen = int(math.ceil(len(elts) / ncols))
    for r in range(clen):
        row = []
        for c in range(ncols):
            i = c * clen + r
            row.append(elts[i] if i < len(elts) else None)
        yield row


@formatter
def version_json(obj_names, out, object_type):
    """Print all objects with their latest versions."""
    objs = [ramble.repository.get(name, object_type=object_type) for name in obj_names]

    out.write("[\n")

    # output name and latest version for each object
    obj_latest = ",\n".join([f'  {{"name": "{obj.name}"\n}}' for obj in objs])
    out.write(obj_latest)
    # important: no trailing comma in JSON arrays
    out.write("\n]\n")


@formatter
def html(obj_names, out, object_type):
    """Print out information on all objects in Sphinx HTML.

    This is intended to be inlined directly into Sphinx documentation.
    We write HTML instead of RST for speed; generating RST from *all*
    objects causes the Sphinx build to take forever. Including this as
    raw HTML is much faster.
    """

    obj_def = ramble.repository.type_definitions[object_type]

    # Read in all objects
    objs = [ramble.repository.get(name, object_type=object_type) for name in obj_names]

    # Start at 2 because the title of the page from Sphinx is id1.
    span_id = 2

    # HTML header with an increasing id span
    def head(n, span_id, title, anchor=None):
        if anchor is None:
            anchor = title
        out.write(
            (
                '<span id="id%d"></span>'
                '<h1>%s<a class="headerlink" href="#%s" '
                'title="Permalink to this headline">&para;</a>'
                "</h1>\n"
            )
            % (span_id, title, anchor)
        )

    # Start with the number of objects, skipping the title and intro
    # blurb, which we maintain in the RST file.
    out.write("<p>\n")
    out.write(f'Ramble currently has {len(objs)} mainline {obj_def["dir_name"]}:\n')
    out.write("</p>\n")

    # Table of links to all objects
    out.write('<table border="1" class="docutils">\n')
    out.write('<tbody valign="top">\n')
    for i, row in enumerate(rows_for_ncols(obj_names, 3)):
        out.write('<tr class="row-odd">\n' if i % 2 == 0 else '<tr class="row-even">\n')
        for name in row:
            out.write("<td>\n")
            if name is not None:
                out.write(f'<a class="reference internal" href="#{name}">{name}</a>')
            out.write("</td>\n")
        out.write("</tr>\n")
    out.write("</tbody>\n")
    out.write("</table>\n")
    out.write('<hr class="docutils"/>\n')

    # Output some text for each objects.
    for obj in objs:
        out.write(f'<div class="section" id="{obj.name}">\n')
        head(2, span_id, obj.name)
        span_id += 1

        obj.to_html_docs(out, obj_def)

        out.write('<hr class="docutils"/>\n')
        out.write("</div>\n")


def setup_list_parser(subparser):
    subparser.add_argument(
        "filter",
        nargs=argparse.REMAINDER,
        help="optional case-insensitive glob patterns to filter results",
    )
    subparser.add_argument(
        "-d",
        "--search-description",
        action="store_true",
        default=False,
        help="filtering will also search the description for a match",
    )
    subparser.add_argument(
        "--format",
        default="name_only",
        choices=formatters,
        help="format to be used to print the output [default: name_only]",
    )
    subparser.add_argument(
        "--update",
        metavar="FILE",
        default=None,
        action="store",
        help="write output to the specified file, if any object is newer",
    )

    arguments.add_common_arguments(subparser, ["tags", "obj_type"])


def perform_list(args):
    # retrieve the formatter to use from args
    formatter = formatters[args.format]

    object_type = ramble.repository.simplify_object_type(args.type)

    sorted_objects = object_utils.filter_by_name(args.filter, args.search_description, object_type)

    # Filter by tags
    if args.tags:
        objects_with_tags = set(ramble.repository.paths[object_type].objects_with_tags(*args.tags))
        matching_tags = set(sorted_objects) & objects_with_tags
        sorted_objects = sorted(matching_tags)

    if not sorted_objects:
        filter_strs = []
        if args.filter:
            filter_strs.append(f"filter '{' '.join(args.filter)}'")
        if args.tags:
            filter_strs.append(f"tags '{', '.join(args.tags)}'")
        if filter_strs:
            logger.warn(f"No {object_type.name} found matching {' and '.join(filter_strs)}.")
        else:
            logger.warn(f"No {object_type.name} found.")
        return 0

    if args.update:
        # change output stream if user asked for update
        if os.path.exists(args.update):
            if os.path.getmtime(args.update) > ramble.repository.paths[object_type].last_mtime():
                logger.msg(f"File is up to date: {args.update}")
                return 0

        logger.msg(f"Updating file: {args.update}")
        with open(args.update, "w", encoding="utf-8") as f:
            formatter(sorted_objects, f, object_type)

    else:
        # Print to stdout
        formatter(sorted_objects, sys.stdout, object_type)

    return 0
