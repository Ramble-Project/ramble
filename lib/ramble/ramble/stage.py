# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.


import errno
import hashlib
import os
import stat
import sys
from typing import Dict, List

from llnl.util.filesystem import (
    can_access,
    install,
    install_tree,
    mkdirp,
    remove_linked_tree,
)

import ramble.caches
import ramble.error
import ramble.fetch_strategy as fs
import ramble.mirror
import ramble.util.lock
from ramble.util.logger import logger

import spack.config
import spack.util.url as url_util
from spack.util import pattern
from spack.util.crypto import bit_length, prefix_bits

# The well-known stage source subdirectory name.
_input_subdir = "input"


class InputStage:
    """Manages a stage directory for containing input files.

    A Stage object is a context manager that handles a directory where
    some workload inputs are downloaded.
    It handles fetching inputs, either as an archive to be
    expanded or by checking it out of a repository.  A stage's
    lifecycle looks like this::

        with InputStage() as stage:      # Context manager creates the stage
                                    # directory
            stage.fetch()           # Fetch an input archive into the stage.
            stage.expand_archive()  # Expand the archive into input_path.

    Because the input files are needed to execute various experiments,
    the stage is retained by default.

    You can also use the stage's create/destroy functions manually,
    like this::

        stage = InputStage()
        try:
            stage.create()          # Explicitly create the stage directory.
            stage.fetch()           # Fetch a source archive into the stage.
            stage.expand_archive()  # Expand the archive into source_path.
            <install>               # Build and install the archive.
                                    # (handled by user of Stage)
        finally:
            stage.destroy()         # Explicitly destroy the stage directory.

    InputStages are required to be named by default. The name should match
    a workload namespace.
    """

    """Shared dict of all stage locks."""
    stage_locks: Dict[str, ramble.util.lock.Lock] = {}

    """Most staging is managed by Ramble.  DIYStage is one exception."""
    managed_by_ramble = True

    def __init__(
        self,
        url_or_fetch_strategy,
        name=None,
        path=None,
        mirror_paths=None,
        keep=True,
        lock=True,
        search_fn=None,
    ):
        """Create a stage object.
        Parameters:
          url_or_fetch_strategy
              URL of the archive to be downloaded into this stage, OR
              a valid FetchStrategy.

          name
              If a name is provided, then this stage is a named stage
              and will persist between runs (or if you construct another
              stage object later).  If name is not provided, then this
              stage will be given a unique name automatically.

          mirror_paths
              If provided, Stage will search Rambles's mirrors for
              this archive at each of the provided relative mirror paths
              before using the default fetch strategy.

          keep
              By default, when used as a context manager, the Stage
              is deleted on exit when no exceptions are raised.
              Pass True to keep the stage intact even if no
              exceptions are raised.

         path
              If provided, the stage path to use for associated builds.

         lock
              True if the stage directory file lock is to be used, False
              otherwise.

         search_fn
              The search function that provides the fetch strategy
              instance.
        """
        # TODO: fetch/stage coupling needs to be reworked -- the logic
        # TODO: here is convoluted and not modular enough.
        if isinstance(url_or_fetch_strategy, str):
            self.fetcher = fs.from_url_scheme(url_or_fetch_strategy)
        elif isinstance(url_or_fetch_strategy, fs.FetchStrategy):
            self.fetcher = url_or_fetch_strategy
        else:
            raise ValueError("Can't construct Stage without url or fetch strategy")
        self.fetcher.stage = self
        # self.fetcher can change with mirrors.
        self.default_fetcher = self.fetcher
        self.search_fn = search_fn
        # used for mirrored archives of repositories.
        self.skip_checksum_for_mirror = True

        self.srcdir = None

        self.input_subdir = _input_subdir

        self.name = name
        if name is None:
            raise StageError("InputStage requires a name")
        self.mirror_paths = mirror_paths

        # Use the provided path or construct an optionally named stage path.
        self.path = path

        # Flag to decide whether to delete the stage folder on exit or not
        self.keep = keep

        # File lock for the stage directory.  We use one file for all
        # stage locks. See spack.database.Database.prefix_lock for
        # details on this approach.
        self._lock = None
        if lock:
            if self.name not in InputStage.stage_locks:
                sha1 = hashlib.sha1(self.name.encode("utf-8")).digest()
                lock_id = prefix_bits(sha1, bit_length(sys.maxsize))
                stage_lock_path = os.path.join(self.path, ".lock")

                logger.debug(f"Creating stage lock {self.name}")
                InputStage.stage_locks[self.name] = ramble.util.lock.Lock(
                    stage_lock_path, lock_id, 1, desc=self.name
                )

            self._lock = InputStage.stage_locks[self.name]

        # When stages are reused, we need to know whether to re-create
        # it.  This marks whether it has been created/destroyed.
        self.created = False

    def __enter__(self):
        """
        Entering a stage context will create the stage directory

        Returns:
            InputStage: self
        """
        if self._lock is not None:
            self._lock.acquire_write(timeout=60)
        self.create()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exiting from a stage context will unlock the stage directory.

        Args:
            exc_type: exception type
            exc_val: exception value
            exc_tb: exception traceback

        Returns:
            bool: Always returns ``False`` to prevent exception suppression
        """
        if self._lock is not None:
            self._lock.release_write()

        # Delete when there are no exceptions, unless asked to keep.
        if exc_type is None and not self.keep:
            self.destroy()

    def set_subdir(self, subdir_name):
        self.input_subdir = subdir_name

    @property
    def expected_archive_files(self):
        """Possible archive file paths."""
        paths: List[str] = []

        fnames: List[str] = []
        expanded = True
        if isinstance(self.default_fetcher, fs.URLFetchStrategy):
            expanded = self.default_fetcher.expand_archive
            if self.default_fetcher.url:
                fnames.append(os.path.basename(self.default_fetcher.url))

        if self.mirror_paths:
            fnames.extend(os.path.basename(x) for x in self.mirror_paths)

        if self.path:
            paths.extend(os.path.join(self.path, f) for f in fnames)
        if not expanded and self.source_path:
            # If the download file is not compressed, the "archive" is a
            # single file placed in Stage.source_path
            paths.extend(os.path.join(self.source_path, f) for f in fnames)

        return paths

    @property
    def save_filename(self):
        possible_filenames = self.expected_archive_files
        if possible_filenames:
            # This prefers using the URL associated with the default fetcher if
            # available, so that the fetched resource name matches the remote
            # name
            return possible_filenames[0]

    @property
    def archive_file(self):
        """Path to the source archive within this stage directory."""
        for path in self.expected_archive_files:
            if os.path.exists(path):
                return path
        else:
            return None

    @property
    def expanded(self):
        """Returns True if source path expanded; else False."""
        return os.path.exists(self.source_path)

    @property
    def source_path(self):
        """Returns the well-known source directory path."""
        return os.path.join(self.path, self.input_subdir)

    def fetch(self, mirror_only=False, err_msg=None):
        """Retrieves the code or archive

        Args:
            mirror_only (bool): only fetch from a mirror
            err_msg (str | None): the error message to display if all fetchers
                fail or ``None`` for the default fetch failure message
        """
        fetchers = []
        if not mirror_only:
            fetchers.append(self.default_fetcher)

        # TODO: move mirror logic out of here and clean it up!
        # TODO: Or @alalazo may have some ideas about how to use a
        # TODO: CompositeFetchStrategy here.
        self.skip_checksum_for_mirror = True
        if self.mirror_paths:
            # Join URLs of mirror roots with mirror paths. Because
            # urljoin() will strip everything past the final '/' in
            # the root, so we add a '/' if it is not present.
            mirror_urls: List[str] = []
            for mirror in ramble.mirror.MirrorCollection().values():
                mirror_urls.extend(
                    url_util.join(mirror.fetch_url, rel_path) for rel_path in self.mirror_paths
                )

            # If this archive is normally fetched from a tarball URL,
            # then use the same digest.  `spack mirror` ensures that
            # the checksum will be the same.
            digest = None
            expand = True
            extension = None
            if isinstance(self.default_fetcher, fs.URLFetchStrategy):
                digest = self.default_fetcher.digest
                expand = self.default_fetcher.expand_archive
                extension = self.default_fetcher.extension

            # Have to skip the checksum for things archived from
            # repositories.  How can this be made safer?
            self.skip_checksum_for_mirror = not bool(digest)

            # Add URL strategies for all the mirrors with the digest
            # Insert fetchers in the order that the URLs are provided.
            for url in reversed(mirror_urls):
                fetchers.insert(
                    0, fs.from_url_scheme(url, digest, expand=expand, extension=extension)
                )

            if self.default_fetcher.cachable:
                for rel_path in reversed(list(self.mirror_paths)):
                    cache_fetcher = ramble.caches.fetch_cache.fetcher(
                        rel_path, digest, expand=expand, extension=extension
                    )
                    fetchers.insert(0, cache_fetcher)

        def generate_fetchers():
            yield from fetchers
            # The search function may be expensive, so wait until now to
            # call it so the user can stop if a prior fetcher succeeded
            if self.search_fn and not mirror_only:
                dynamic_fetchers = self.search_fn()
                yield from dynamic_fetchers

        def print_errors(errors):
            for msg in errors:
                logger.debug(msg)

        errors = []
        for fetcher in generate_fetchers():
            try:
                fetcher.stage = self
                self.fetcher = fetcher
                self.fetcher.fetch()
                break
            except spack.fetch_strategy.NoCacheError:
                # Don't bother reporting when something is not cached.
                continue
            except ramble.error.RambleError as e:
                errors.append(f"Fetching from {fetcher} failed.")
                logger.debug(e)
                continue
            except spack.util.web.SpackWebError as e:
                errors.append(f"Fetching from {fetcher} failed.")
                logger.debug(e)
                continue

        else:
            print_errors(errors)

            self.fetcher = self.default_fetcher
            raise fs.FetchError(err_msg or "All fetchers failed", None)

        print_errors(errors)

    def check(self):
        """Check the downloaded archive against a checksum digest.
        No-op if this stage checks code out of a repository."""
        if self.fetcher is not self.default_fetcher and self.skip_checksum_for_mirror:
            logger.warn(
                "Fetching from mirror without a checksum!",
                "This input is normally checked out from a version "
                "control system, but it has been archived on a "
                "mirror.  This means we cannot know a checksum for the "
                "tarball in advance. Be sure that your connection to "
                "this mirror is secure!",
            )
        elif ramble.config.get("config:checksum"):
            self.fetcher.check()

    def cache_local(self):
        ramble.caches.fetch_cache.store(self.fetcher, self.mirror_paths.storage_path)

    def cache_mirror(self, mirror, stats):
        """Perform a fetch if the resource is not already cached

        Arguments:
            mirror (ramble.caches.MirrorCache): the mirror to cache this Stage's resource in
            stats (ramble.mirror.MirrorStats): this is updated depending on whether the
                caching operation succeeded or failed
        """
        if isinstance(self.default_fetcher, fs.BundleFetchStrategy):
            # BundleFetchStrategy has no source to fetch. The associated
            # fetcher does nothing but the associated stage may still exist.
            # There is currently no method available on the fetcher to
            # distinguish this ('cachable' refers to whether the fetcher
            # refers to a resource with a fixed ID, which is not the same
            # concept as whether there is anything to fetch at all) so we
            # must examine the type of the fetcher.
            return

        if not fs.stable_target(self.default_fetcher):
            return

        absolute_storage_path = os.path.join(mirror.root, self.mirror_paths.storage_path)

        if os.path.exists(absolute_storage_path):
            logger.debug(f"Already existed: {absolute_storage_path}")
            stats.already_existed(absolute_storage_path)
            logger.debug(f"   Stats? {stats.present}")
        else:
            self.fetch()
            self.check()
            mirror.store(self.fetcher, self.mirror_paths.storage_path)
            logger.debug(f"Added: {absolute_storage_path}")
            stats.added(absolute_storage_path)

        if not os.path.exists(absolute_storage_path):
            stats.error(absolute_storage_path)

        mirror.symlink(self.mirror_paths)

    def expand_archive(self):
        """Changes to the stage directory and attempt to expand the downloaded
        archive.  Fail if the stage is not set up or if the archive is not yet
        downloaded."""
        if not self.expanded:
            self.fetcher.expand()
            logger.debug(f"Created stage in {self.path}")
        else:
            logger.debug(f"Already staged {self.name} in {self.path}")

    def restage(self):
        """Removes the expanded archive path if it exists, then re-expands
        the archive.
        """
        self.fetcher.reset()

    def create(self):
        """
        Ensures the top-level (config:build_stage) directory exists.
        """
        # Emulate file permissions for tempfile.mkdtemp.
        if not os.path.exists(self.path):
            mkdirp(self.path, mode=stat.S_IRWXU)
        elif not os.path.isdir(self.path):
            os.remove(self.path)
            mkdirp(self.path, mode=stat.S_IRWXU)

        # Make sure we can actually do something with the stage we made.
        ensure_access(self.path)
        self.created = True

    def destroy(self):
        """Removes this stage directory."""
        remove_linked_tree(self.path)

        # Make sure we don't end up in a removed directory
        try:
            os.getcwd()
        except OSError as e:
            logger.debug(e)
            os.chdir(os.path.dirname(self.path))

        # mark as destroyed
        self.created = False


class ResourceStage(InputStage):

    def __init__(self, url_or_fetch_strategy, root, resource, **kwargs):
        super().__init__(url_or_fetch_strategy, **kwargs)
        self.root_stage = root
        self.resource = resource

    def restage(self):
        super().restage()
        self._add_to_root_stage()

    def expand_archive(self):
        super().expand_archive()
        self._add_to_root_stage()

    def _add_to_root_stage(self):
        """
        Move the extracted resource to the root stage (according to placement).
        """
        root_stage = self.root_stage
        resource = self.resource

        if resource.placement:
            placement = resource.placement
        elif self.srcdir:
            placement = self.srcdir
        else:
            placement = self.source_path

        if not isinstance(placement, dict):
            placement = {"": placement}

        target_path = os.path.join(root_stage.source_path, resource.destination)

        try:
            os.makedirs(target_path)
        except OSError as err:
            logger.debug(err)
            if err.errno == errno.EEXIST and os.path.isdir(target_path):
                pass
            else:
                raise

        for key, value in placement.items():
            destination_path = os.path.join(target_path, value)
            source_path = os.path.join(self.source_path, key)

            if not os.path.exists(destination_path):
                logger.info(
                    "Moving resource stage\n\tsource : "
                    "{stage}\n\tdestination : {destination}".format(
                        stage=source_path, destination=destination_path
                    )
                )

                src = os.path.realpath(source_path)

                if os.path.isdir(src):
                    install_tree(src, destination_path)
                else:
                    install(src, destination_path)


class StageComposite(pattern.Composite):
    """Composite for Stage type objects. The first item in this composite is
    considered to be the root workload, and operations that return a value are
    forwarded to it."""

    #
    # __enter__ and __exit__ delegate to all stages in the composite.
    #

    def __init__(self):
        super().__init__(
            [
                "fetch",
                "create",
                "created",
                "check",
                "expand_archive",
                "restage",
                "destroy",
                "cache_local",
                "cache_mirror",
                "managed_by_ramble",
            ]
        )

    def __enter__(self):
        for item in self:
            item.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for item in reversed(self):
            item.keep = getattr(self, "keep", False)
            item.__exit__(exc_type, exc_val, exc_tb)

    #
    # Below functions act only on the *first* stage in the composite.
    #
    @property
    def source_path(self):
        return self[0].source_path

    @property
    def expanded(self):
        return self[0].expanded

    @property
    def path(self):
        return self[0].path

    @property
    def archive_file(self):
        return self[0].archive_file


class DIYStage:
    """
    Simple class that allows any directory to be a ramble input stage.
    Consequently, it does not expect or require that the source path adhere to
    the standard directory naming convention.
    """

    """DIY staging is, by definition, not managed by Ramble."""
    managed_by_ramble = False

    def __init__(self, path):
        if path is None:
            raise ValueError("Cannot construct DIYStage without a path.")
        elif not os.path.isdir(path):
            raise StagePathError("The stage path directory does not exist:", path)

        self.archive_file = None
        self.path = path
        self.source_path = path
        self.created = True

    # DIY stages do nothing as context managers.
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def fetch(self, *args, **kwargs):
        logger.debug("No need to fetch for DIY.")

    def check(self):
        logger.debug("No checksum needed for DIY.")

    def expand_archive(self):
        logger.debug(f"Using source directory: {self.source_path}")

    @property
    def expanded(self):
        """Returns True since the source_path must exist."""
        return True

    def restage(self):
        raise RestageError("Cannot restage a DIY stage.")

    def create(self):
        self.created = True

    def destroy(self):
        # No need to destroy DIY stage.
        pass

    def cache_local(self):
        logger.debug("Sources for DIY stages are not cached")


def ensure_access(file):
    """Ensure we can access a directory and die with an error if we can't."""
    if not can_access(file):
        logger.die(f"Insufficient permissions for {file}")


class StageError(ramble.error.RambleError):
    """ "Superclass for all errors encountered during staging."""


class StagePathError(StageError):
    """ "Error encountered with stage path."""


class RestageError(StageError):
    """ "Error encountered during restaging."""


# Keep this in namespace for convenience
FailedDownloadError = fs.FailedDownloadError
