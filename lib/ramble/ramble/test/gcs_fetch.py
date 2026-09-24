# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import io
import os
from unittest import mock

import pytest

import ramble.config
import ramble.fetch_strategy
import ramble.stage

import spack.util.gcs


@pytest.mark.parametrize("_fetch_method", ["curl", "urllib"])
def test_gcsfetchstrategy_without_url(_fetch_method):
    """Ensure constructor with no URL fails."""
    with ramble.config.override("config:url_fetch_method", _fetch_method):
        with pytest.raises(ValueError):
            ramble.fetch_strategy.GCSFetchStrategy(None)


@pytest.mark.parametrize("_fetch_method", ["curl", "urllib"])
def test_gcsfetchstrategy_bad_url(tmpdir, _fetch_method):
    """Ensure fetch with bad URL fails as expected."""
    testpath = str(tmpdir)

    with ramble.config.override("config:url_fetch_method", _fetch_method):
        fetcher = ramble.fetch_strategy.GCSFetchStrategy(url="file:///does-not-exist")
        assert fetcher is not None

        with ramble.stage.InputStage(fetcher, name="test", path=testpath) as stage:
            assert stage is not None
            assert fetcher.archive_file is None
            with pytest.raises(ramble.fetch_strategy.FetchError):
                fetcher.fetch()


@pytest.mark.parametrize("_fetch_method", ["curl", "urllib"])
def test_gcsfetchstrategy_downloaded(tmpdir, _fetch_method):
    """Ensure fetch with archive file already downloaded is a noop."""
    testpath = str(tmpdir)
    archive = os.path.join(testpath, "gcs.tar.gz")

    with ramble.config.override("config:url_fetch_method", _fetch_method):

        class Archived_GCSFS(ramble.fetch_strategy.GCSFetchStrategy):
            @property
            def archive_file(self):
                return archive

        url = f"gcs:///{archive}"
        fetcher = Archived_GCSFS(url=url)
        with ramble.stage.InputStage(fetcher, name="test", path=testpath):
            fetcher.fetch()


class MockBlob:
    def __init__(self, data=b'{"test": "data"}', content_type="application/json", exists_val=True):
        self.data = data
        self.content_type = content_type
        self.content_encoding = None
        self.content_language = None
        self.md5_hash = None
        self._exists = exists_val

    def exists(self):
        return self._exists

    def open(self, mode="rb"):
        return io.BytesIO(self.data)


class MockBucket:
    def __init__(self, name, blob_obj=None):
        self.name = name
        self.blob_obj = blob_obj or MockBlob()

    def exists(self):
        return True

    def create(self):
        pass

    def blob(self, blob_path):
        return self.blob_obj

    def get_blob(self, blob_path):
        return self.blob_obj


class MockGcsClient:
    def __init__(self, blob_obj=None):
        self.blob_obj = blob_obj or MockBlob()

    def bucket(self, name):
        return MockBucket(name, blob_obj=self.blob_obj)


@pytest.mark.parametrize("_fetch_method", ["curl", "urllib"])
def test_gcsfetchstrategy_download(tmpdir, _fetch_method, monkeypatch):
    """Ensure GCS fetch downloads file properly using mock client."""
    mock_data = b'{"key": "value"}'
    mock_blob = MockBlob(data=mock_data, content_type="application/json")
    monkeypatch.setattr(spack.util.gcs, "gcs_client", lambda: MockGcsClient(blob_obj=mock_blob))

    testpath = str(tmpdir)
    path = "gs://mock-bucket/build_cache/index.json"

    with ramble.config.override("config:url_fetch_method", _fetch_method):
        fetcher = ramble.fetch_strategy.GCSFetchStrategy(url=path)
        with ramble.stage.InputStage(fetcher, name="test", path=testpath):
            fetcher.fetch()
            downloaded = os.path.join(testpath, "index.json")
            assert os.path.exists(downloaded)
            with open(downloaded, "rb") as f:
                assert f.read() == mock_data


def test_gcsfetchstrategy_content_type_mismatch(tmpdir, monkeypatch):
    """Ensure GCS fetch warns when content type is text/html."""
    mock_warn = mock.MagicMock()
    monkeypatch.setattr(ramble.fetch_strategy, "warn_content_type_mismatch", mock_warn)

    mock_blob = MockBlob(data=b"<html></html>", content_type="text/html")
    monkeypatch.setattr(spack.util.gcs, "gcs_client", lambda: MockGcsClient(blob_obj=mock_blob))

    testpath = str(tmpdir)
    path = "gs://mock-bucket/build_cache/index.json"

    fetcher = ramble.fetch_strategy.GCSFetchStrategy(url=path)
    with ramble.stage.InputStage(fetcher, name="test", path=testpath):
        fetcher.fetch()
        mock_warn.assert_called_once()
