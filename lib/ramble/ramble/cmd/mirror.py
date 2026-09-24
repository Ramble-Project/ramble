# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
import ramble.config
import ramble.mirror
import ramble.util.web as web_util
from ramble.cmd.common import arguments
from ramble.util.logger import logger

import spack.util.url as url_util
from spack.util.spack_yaml import syaml_dict

description = "manage mirrors (inputs)"
section = "config"
level = "long"


def setup_parser(subparser):
    arguments.add_common_arguments(subparser, ["no_checksum"])

    sp = subparser.add_subparsers(metavar="SUBCOMMAND", dest="mirror_command")

    # Destroy
    destroy_parser = sp.add_parser(
        "destroy", help=mirror_destroy.__doc__, description=mirror_destroy.__doc__
    )

    destroy_target = destroy_parser.add_mutually_exclusive_group(required=True)
    destroy_target.add_argument(
        "-m",
        "--mirror-name",
        metavar="mirror_name",
        type=str,
        help="find mirror to destroy by name",
    )
    destroy_target.add_argument(
        "-u", "--mirror-url", metavar="mirror_url", type=str, help="find mirror to destroy by url"
    )

    # used to construct scope arguments below
    scopes = ramble.config.scopes()
    scopes_metavar = ramble.config.scopes_metavar

    # Add
    add_parser = sp.add_parser("add", help=mirror_add.__doc__, description=mirror_add.__doc__)
    add_parser.add_argument("name", help="mnemonic name for mirror", metavar="mirror")
    add_parser.add_argument("url", help="url of mirror directory from 'ramble mirror create'")
    add_parser.add_argument(
        "--scope",
        choices=scopes,
        metavar=scopes_metavar,
        default=ramble.config.default_modify_scope(),
        help="configuration scope to modify",
    )
    # Remove
    remove_parser = sp.add_parser(
        "remove", aliases=["rm"], help=mirror_remove.__doc__, description=mirror_remove.__doc__
    )
    remove_parser.add_argument("name", help="mnemonic name for mirror", metavar="mirror")
    remove_parser.add_argument(
        "--scope",
        choices=scopes,
        metavar=scopes_metavar,
        default=ramble.config.default_list_scope(),
        help="configuration scope to modify",
    )

    # Set-Url
    set_url_parser = sp.add_parser(
        "set-url", help=mirror_set_url.__doc__, description=mirror_set_url.__doc__
    )
    set_url_parser.add_argument("name", help="mnemonic name for mirror", metavar="mirror")
    set_url_parser.add_argument("url", help="url of mirror directory from 'ramble mirror create'")
    set_url_parser.add_argument(
        "--push", action="store_true", help="set only the URL used for uploading new resources"
    )
    set_url_parser.add_argument(
        "--scope",
        choices=scopes,
        metavar=scopes_metavar,
        default=ramble.config.default_modify_scope(),
        help="configuration scope to modify",
    )

    # List
    list_parser = sp.add_parser("list", help=mirror_list.__doc__, description=mirror_list.__doc__)
    list_parser.add_argument(
        "--scope",
        choices=scopes,
        metavar=scopes_metavar,
        default=ramble.config.default_list_scope(),
        help="configuration scope to read from",
    )


def mirror_add(args):
    """Add a mirror to Ramble."""
    url = url_util.format(args.url)
    ramble.mirror.add(args.name, url, args.scope)


def mirror_remove(args):
    """Remove a mirror by name."""
    ramble.mirror.remove(args.name, args.scope)


def mirror_set_url(args):
    """Change the URL of a mirror."""
    url = url_util.format(args.url)
    mirrors = ramble.config.get("mirrors", scope=args.scope)
    if not mirrors:
        mirrors = syaml_dict()

    if args.name not in mirrors:
        logger.die(f"No mirror found with name {args.name}.")

    entry = mirrors[args.name]
    try:
        fetch_url = entry["fetch"]
        push_url = entry["push"]
    except TypeError:
        fetch_url, push_url = entry, entry

    changes_made = False

    if args.push:
        changes_made = changes_made or push_url != url
        push_url = url
    else:
        changes_made = changes_made or push_url != url
        fetch_url, push_url = url, url

    items = [
        (
            (mirror_name, mirror_url)
            if mirror_name != args.name
            else (
                (mirror_name, {"fetch": fetch_url, "push": push_url})
                if fetch_url != push_url
                else (mirror_name, {"fetch": fetch_url, "push": fetch_url})
            )
        )
        for mirror_name, mirror_url in mirrors.items()
    ]

    mirrors = syaml_dict(items)
    ramble.config.set("mirrors", mirrors, scope=args.scope)

    if changes_made:
        logger.msg(
            "Changed%s url or connection information for mirror %s."
            % ((" (push)" if args.push else ""), args.name)
        )
    else:
        logger.msg(f"No changes made to mirror {args.name}.")


def mirror_list(args):
    """Print out available mirrors to the console."""

    mirrors = ramble.mirror.MirrorCollection(scope=args.scope)
    if not mirrors:
        logger.warn("No mirrors configured.")
        return 0

    mirrors.display()
    return 0


def mirror_destroy(args):
    """Given a url, recursively delete everything under it."""
    mirror_url = None

    if args.mirror_name:
        result = ramble.mirror.MirrorCollection().lookup(args.mirror_name)
        mirror_url = result.push_url
    elif args.mirror_url:
        mirror_url = args.mirror_url

    web_util.remove_url(mirror_url, recursive=True)


def mirror(parser, args):
    action = {
        "destroy": mirror_destroy,
        "add": mirror_add,
        "remove": mirror_remove,
        "rm": mirror_remove,
        "set-url": mirror_set_url,
        "list": mirror_list,
    }

    if args.no_checksum:
        ramble.config.set("config:checksum", False, scope="command_line")

    return action[args.mirror_command](args)
