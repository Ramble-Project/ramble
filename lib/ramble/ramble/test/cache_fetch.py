# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
import sys

import pytest

from llnl.util.filesystem import mkdirp, touch

import ramble.config
from ramble.fetch_strategy import CacheURLFetchStrategy, NoCacheError
from ramble.stage import InputStage

is_windows = sys.platform == "win32"


@pytest.mark.parametrize("_fetch_method", ["curl", "urllib"])
def test_fetch_missing_cache(tmpdir, _fetch_method):
    """Ensure raise a missing cache file."""
    testpath = str(tmpdir)
    with ramble.config.override("config:url_fetch_method", _fetch_method):
        abs_pref = "" if is_windows else "/"
        url = "file://" + abs_pref + "not-a-real-cache-file"
        fetcher = CacheURLFetchStrategy(url=url)
        with InputStage(
            fetcher, name=f"test_fetch_missing_cache_{_fetch_method}", path=testpath
        ) as stage:
            with pytest.raises(NoCacheError, match=r"No cache"):
                fetcher.fetch()
            with pytest.raises(ramble.fetch_strategy.FetchError, match="All fetchers failed"):
                stage.fetch()


@pytest.mark.parametrize("_fetch_method", ["curl", "urllib"])
def test_fetch(tmpdir, _fetch_method):
    """Ensure a fetch after expanding is effectively a no-op."""
    testpath = str(tmpdir)
    cache = os.path.join(testpath, "cache.tar.gz")
    touch(cache)
    if is_windows:
        url_stub = "{0}"
    else:
        url_stub = "/{0}"
    url = "file://" + url_stub.format(cache)
    with ramble.config.override("config:url_fetch_method", _fetch_method):
        fetcher = CacheURLFetchStrategy(url=url)
        with InputStage(fetcher, name=f"test_fetch_{_fetch_method}", path=testpath) as stage:
            source_path = stage.source_path
            mkdirp(source_path)
            fetcher.fetch()
