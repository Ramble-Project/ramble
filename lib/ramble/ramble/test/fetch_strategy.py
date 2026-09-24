# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.
"""Perform tests of the fetch_strategy functions"""

import contextlib
import os
import shutil
from pathlib import Path
from unittest import mock

import pytest

from ramble import fetch_strategy
from ramble.fetch_strategy import FailedDownloadError, FetchError


@pytest.mark.parametrize(
    "url,expected_fetcher_type",
    [
        ("file://my-path", fetch_strategy.URLFetchStrategy),
        ("https://my-url", fetch_strategy.URLFetchStrategy),
        ("gs://my-bucket", fetch_strategy.GCSFetchStrategy),
        ("s3://my-bucket", fetch_strategy.S3FetchStrategy),
    ],
)
def test_from_url_scheme(url, expected_fetcher_type):
    fetcher = fetch_strategy.from_url_scheme(url)
    assert isinstance(fetcher, expected_fetcher_type)


def test_bad_from_url_scheme():
    with pytest.raises(ValueError, match="No FetchStrategy found"):
        fetch_strategy.from_url_scheme("unknown://my-url")


class TestFsCache:
    def test_store_uncachable(self, tmp_path):
        """Test that store does nothing for an uncachable fetcher."""
        cache = fetch_strategy.FsCache(str(tmp_path))
        # No digest, so uncachable
        fetcher = fetch_strategy.URLFetchStrategy(url="http://example.com")

        fetcher.archive = mock.Mock()

        cache.store(fetcher, "dest/file")

        fetcher.archive.assert_not_called()
        assert not (tmp_path / "dest").exists()

    def test_store_already_cached(self, tmp_path):
        """Test that store does nothing for an already cached fetcher."""
        cache = fetch_strategy.FsCache(str(tmp_path))
        fetcher = fetch_strategy.CacheURLFetchStrategy(url="file:///path/to/cache")

        fetcher.archive = mock.Mock()

        cache.store(fetcher, "dest/file")

        fetcher.archive.assert_not_called()
        assert not (tmp_path / "dest").exists()

    def test_store_cachable_and_destroy(self, tmp_path):
        """Test that store caches a cachable fetcher and destroy works."""
        cache = fetch_strategy.FsCache(str(tmp_path))
        fetcher = fetch_strategy.URLFetchStrategy(url="http://example.com", checksum="sha256:123")

        fetcher.archive = mock.Mock()

        dest_path = "dest/file"
        cache.store(fetcher, dest_path)

        expected_dst = os.path.join(str(tmp_path), dest_path)
        fetcher.archive.assert_called_once_with(expected_dst)

        assert (tmp_path / "dest").is_dir()

        cache.destroy()
        assert not tmp_path.exists()


class TestURLFetchStrategy:
    @pytest.fixture
    def mock_curl(self, monkeypatch):
        """Mock the curl executable."""
        mock_curl_exe = mock.MagicMock()

        def mock_which(name, required=False):
            if name == "curl":
                return mock_curl_exe
            return mock.MagicMock()

        monkeypatch.setattr(fetch_strategy, "which", mock.MagicMock(side_effect=mock_which))
        return mock_curl_exe

    @pytest.fixture
    def mock_config(self, monkeypatch):
        """Mock ramble.config."""
        config = {
            "config:url_fetch_method": "curl",
            "config:verify_ssl": True,
            "config:connect_timeout": 10,
            "config:debug": False,
        }

        def get(key, default=None):
            return config.get(key, default)

        mock_config_get = mock.MagicMock(side_effect=get)
        monkeypatch.setattr(fetch_strategy.ramble.config, "get", mock_config_get)
        return mock_config_get, config

    @pytest.fixture
    def mock_tty(self, monkeypatch):
        """Mock tty."""
        mock_msg_enabled = mock.MagicMock(return_value=False)
        monkeypatch.setattr(fetch_strategy.tty, "msg_enabled", mock_msg_enabled)
        return mock_msg_enabled

    @pytest.fixture
    def fetcher(self, tmp_path):
        """Create a URLFetchStrategy with a mock stage."""
        f = fetch_strategy.URLFetchStrategy(url="http://example.com/foo.tar.gz")

        stage = mock.MagicMock()
        stage.path = str(tmp_path)
        stage.save_filename = str(tmp_path / "foo.tar.gz")

        f.stage = stage
        return f

    def test_fetch_curl_success(self, fetcher, mock_curl, mock_config, mock_tty, tmp_path):
        """Test successful fetch with curl."""
        mock_curl.return_value = "HTTP/1.1 200 OK\r\nContent-Type: application/x-gzip"
        mock_curl.returncode = 0

        partial, save = fetcher._fetch_curl("http://example.com/foo.tar.gz")

        assert save == str(tmp_path / "foo.tar.gz")
        assert partial == str(tmp_path / "foo.tar.gz.part")

        mock_curl.assert_called_once()
        args, _ = mock_curl.call_args

        assert "http://example.com/foo.tar.gz" in args
        assert "-o" in args
        assert str(tmp_path / "foo.tar.gz.part") in args

    def test_fetch_curl_404(self, fetcher, mock_curl, mock_config, mock_tty, tmp_path):
        """Test fetch with curl when a 404 error occurs."""
        mock_curl.returncode = 22  # Not found
        fetcher.stage.archive_file = None

        partial_file = tmp_path / "foo.tar.gz.part"
        partial_file.touch()

        with pytest.raises(FailedDownloadError, match="URL .* was not found!"):
            fetcher._fetch_curl("http://example.com/foo.tar.gz")

        assert not partial_file.exists()

    def test_fetch_curl_cert_error(self, fetcher, mock_curl, mock_config, mock_tty):
        """Test fetch with curl when a certificate error occurs."""
        mock_curl.returncode = 60  # Certificate error
        fetcher.stage.archive_file = None

        with pytest.raises(FailedDownloadError, match="invalid certificate"):
            fetcher._fetch_curl("http://example.com/foo.tar.gz")

    def test_fetch_curl_content_mismatch(
        self,
        fetcher,
        mock_curl,
        mock_config,
        mock_tty,
        monkeypatch,
    ):
        """Test fetch with curl when content type is HTML."""
        mock_warn = mock.MagicMock()
        monkeypatch.setattr(fetch_strategy, "warn_content_type_mismatch", mock_warn)

        mock_curl.return_value = "HTTP/1.1 200 OK\r\nContent-Type: text/html"
        mock_curl.returncode = 0

        fetcher._fetch_curl("http://example.com/foo.tar.gz")

        mock_warn.assert_called_once()

    def test_fetch_curl_no_verify_ssl(self, fetcher, mock_curl, mock_config, mock_tty):
        """Test that -k is passed to curl when verify_ssl is false."""
        mock_config_get, config = mock_config
        config["config:verify_ssl"] = False

        mock_curl.return_value = "HTTP/1.1 200 OK"
        mock_curl.returncode = 0
        fetcher._fetch_curl("http://example.com/foo.tar.gz")

        mock_curl.assert_called_once()
        args, kwargs = mock_curl.call_args
        assert "-k" in args

    def test_fetch_curl_custom_timeout(self, fetcher, mock_curl, mock_config, mock_tty):
        """Test that valid custom timeout is passed to curl."""
        fetcher.extra_options = {"timeout": 45}
        mock_curl.return_value = "HTTP/1.1 200 OK"
        mock_curl.returncode = 0
        fetcher._fetch_curl("http://example.com/foo.tar.gz")

        mock_curl.assert_called_once()
        args, _ = mock_curl.call_args
        assert "--connect-timeout" in args
        idx = args.index("--connect-timeout")
        assert args[idx + 1] == "45"

    def test_fetch_curl_invalid_timeout(self, fetcher, mock_curl, mock_config, mock_tty):
        """Test that invalid timeout raises FetchError."""
        fetcher.extra_options = {"timeout": "invalid"}
        with pytest.raises(FetchError, match="Invalid timeout value 'invalid'"):
            fetcher._fetch_curl("http://example.com/foo.tar.gz")

    def test_urllib_web_error(self, fetcher, mock_config, mock_tty, monkeypatch):
        """Test that RambleWebError from urllib is converted to FailedDownloadError."""
        _, config = mock_config
        config["config:url_fetch_method"] = "urllib"
        fetcher.stage.archive_file = None

        monkeypatch.setattr(
            fetch_strategy.ramble.util.web,
            "read_from_url",
            mock.MagicMock(
                side_effect=fetch_strategy.ramble.util.web.RambleWebError("Download failed")
            ),
        )

        with pytest.raises(FailedDownloadError, match="Urllib fetch failed to verify url"):
            fetcher._existing_url("http://example.com/foo.tar.gz")

        with pytest.raises(FailedDownloadError, match="urllib failed to fetch with error"):
            fetcher._fetch_urllib("http://example.com/foo.tar.gz")


class TestGitFetchStrategy:
    @pytest.fixture
    def mock_git(self, monkeypatch):
        """Mock the git executable and related functions."""
        mock_git_exe = mock.MagicMock()
        mock_git_exe.add_default_arg = mock.Mock()
        mock_git_exe.add_default_env = mock.Mock()

        def mock_which(name, required=False):
            if name == "git":
                return mock_git_exe
            return mock.MagicMock()

        monkeypatch.setattr(fetch_strategy, "which", mock.MagicMock(side_effect=mock_which))

        def mock_get_single_file(path):
            # Create a dummy directory to be "moved"
            repo_dir = os.path.join(path, "repo-dir")
            os.mkdir(repo_dir)
            return "repo-dir"

        monkeypatch.setattr(
            fetch_strategy, "get_single_file", mock.MagicMock(side_effect=mock_get_single_file)
        )
        monkeypatch.setattr(fetch_strategy.shutil, "move", shutil.move)

        return mock_git_exe

    @pytest.fixture
    def mock_config(self, monkeypatch):
        """Mock ramble.config."""
        config = {"config:debug": False, "config:verify_ssl": True}

        def get(key, default=None):
            return config.get(key, default)

        mock_config_get = mock.MagicMock(side_effect=get)
        monkeypatch.setattr(fetch_strategy.ramble.config, "get", mock_config_get)
        return mock_config_get, config

    @pytest.fixture
    def fetcher(self, tmp_path, monkeypatch):
        """Create a GitFetchStrategy with a mock stage."""
        monkeypatch.setattr(
            fetch_strategy.GitFetchStrategy,
            "version_from_git",
            mock.MagicMock(return_value=fetch_strategy.ver("2.51.0")),
        )

        f = fetch_strategy.GitFetchStrategy(git="https://example.com/repo.git")

        stage = mock.MagicMock()
        stage.path = str(tmp_path)
        stage.source_path = str(tmp_path / "source")
        f.stage = stage

        return f

    def test_clone_basic(self, fetcher, mock_git, mock_config):
        """Test basic git clone."""
        fetcher.clone()

        clone_call = None
        for call in mock_git.call_args_list:
            if "clone" in call[0]:
                clone_call = call
                break

        assert clone_call is not None
        assert "https://example.com/repo.git" in clone_call[0]

        assert os.path.isdir(fetcher.stage.source_path)

    def test_clone_with_commit(self, fetcher, mock_git, mock_config):
        """Test clone with a specific commit."""
        fetcher.commit = "abcdef"
        fetcher.clone(commit="abcdef")

        calls = mock_git.call_args_list

        assert "clone" in calls[0][0]
        assert "https://example.com/repo.git" in calls[0][0]

        assert "checkout" in calls[1][0]
        assert "abcdef" in calls[1][0]

        assert os.path.isdir(fetcher.stage.source_path)

    def test_clone_with_submodules(self, fetcher, mock_git, mock_config):
        """Test clone with submodules."""
        fetcher.submodules = True
        fetcher.clone()

        submodule_call = None
        for call in mock_git.call_args_list:
            if "submodule" in call[0]:
                submodule_call = call
                break

        assert submodule_call is not None
        assert "update" in submodule_call[0]
        assert "--init" in submodule_call[0]
        assert "--recursive" in submodule_call[0]

        assert os.path.isdir(fetcher.stage.source_path)


class TestVCSFetchStrategy:
    @pytest.fixture
    def mock_tar(self, monkeypatch):
        """Mock the tar executable."""
        mock_tar_exe = mock.MagicMock()
        mock_tar_exe.add_default_arg = mock.Mock()

        def mock_which(name, required=False):
            if name == "tar":
                return mock_tar_exe
            return mock.MagicMock()

        monkeypatch.setattr(fetch_strategy, "which", mock.MagicMock(side_effect=mock_which))
        return mock_tar_exe

    class DummyVCS(fetch_strategy.VCSFetchStrategy):
        url_attr = "dummy_url"
        optional_attrs = ["revision"]

    def test_init(self):
        """Test initialization of VCSFetchStrategy."""
        fetcher = self.DummyVCS(dummy_url="some_url", revision="123")
        assert fetcher.url == "some_url"
        assert fetcher.revision == "123"

    def test_init_no_url(self):
        """Test that __init__ raises ValueError if url_attr is missing."""
        with pytest.raises(ValueError, match="requires dummy_url argument"):
            self.DummyVCS(revision="123")

    def test_check_and_expand(self):
        """Test that check() and expand() run without error."""
        fetcher = self.DummyVCS(dummy_url="some_url")
        fetcher.stage = mock.MagicMock()
        fetcher.check()
        fetcher.expand()

    def test_archive(self, tmp_path, mock_tar):
        """Test the archive method."""
        source_path = tmp_path / "source"
        source_path.mkdir()
        (source_path / "file.txt").write_text("content")

        stage = mock.MagicMock()
        stage.path = str(tmp_path)
        stage.source_path = str(source_path)
        stage.srcdir = None

        fetcher = self.DummyVCS(dummy_url="some_url")
        fetcher.stage = stage

        destination = str(tmp_path / "archive.tar.gz")
        fetcher.archive(destination)

        mock_tar.assert_called_once_with("-czf", destination, "source")

    def test_archive_with_srcdir(self, tmp_path, mock_tar, monkeypatch):
        """Test the archive method with stage.srcdir set."""
        source_path = tmp_path / "source"
        source_path.mkdir()
        (source_path / "file.txt").write_text("content")

        stage = mock.MagicMock()
        stage.path = str(tmp_path)
        stage.source_path = str(source_path)
        stage.srcdir = "renamed-source"

        fetcher = self.DummyVCS(dummy_url="some_url")
        fetcher.stage = stage

        @contextlib.contextmanager
        def mock_temp_rename(src, dest):
            os.rename(src, dest)
            yield
            os.rename(dest, src)

        monkeypatch.setattr(fetch_strategy, "temp_rename", mock_temp_rename)

        destination = str(tmp_path / "archive.tar.gz")
        fetcher.archive(destination)

        mock_tar.assert_called_once_with("-czf", destination, "renamed-source")
        assert source_path.exists()
        assert not (tmp_path / "renamed-source").exists()

    def test_archive_with_exclude(self, tmp_path, mock_tar):
        """Test the archive method with exclude patterns."""
        source_path = tmp_path / "source"
        source_path.mkdir()
        (source_path / "file.txt").write_text("content")

        stage = mock.MagicMock()
        stage.path = str(tmp_path)
        stage.source_path = str(source_path)
        stage.srcdir = None

        fetcher = self.DummyVCS(dummy_url="some_url")
        fetcher.stage = stage

        destination = str(tmp_path / "archive.tar.gz")
        fetcher.archive(destination, exclude=[".git", "*.log"])

        calls = [mock.call("--exclude=.git"), mock.call("--exclude=*.log")]
        mock_tar.add_default_arg.assert_has_calls(calls, any_order=True)
        mock_tar.assert_called_once_with("-czf", destination, "source")

    def test_str(self):
        """Test __str__ method."""
        fetcher = self.DummyVCS(dummy_url="some_url")
        assert str(fetcher) == "VCS: some_url"


class TestCvsFetchStrategy:
    @pytest.fixture
    def mock_vcs_executables(self, monkeypatch):
        """Mock vcs executables."""
        mocks = {"tar": mock.MagicMock(), "cvs": mock.MagicMock()}
        mocks["tar"].add_default_arg = mock.Mock()

        def mock_which(name, required=False):
            if name in mocks:
                return mocks[name]
            return mock.MagicMock()

        monkeypatch.setattr(fetch_strategy, "which", mock.MagicMock(side_effect=mock_which))
        return mocks

    @pytest.fixture
    def fetcher(self, tmp_path):
        """Create a CvsFetchStrategy with a mock stage."""
        f = fetch_strategy.CvsFetchStrategy(
            cvs=":pserver:anonymous@example.com:/cvsroot%module=my-module"
        )

        stage = mock.MagicMock()
        stage.path = str(tmp_path)
        stage.source_path = str(tmp_path / "source")
        os.makedirs(stage.source_path)
        stage.expanded = False
        f.stage = stage

        return f

    def test_init(self):
        fetcher = fetch_strategy.CvsFetchStrategy(cvs="url", branch="my-branch", date="2025-10-12")
        assert fetcher.url == "url"
        assert fetcher.branch == "my-branch"
        assert fetcher.date == "2025-10-12"

    def test_cachable(self):
        fetcher = fetch_strategy.CvsFetchStrategy(cvs="url")
        assert not fetcher.cachable

        fetcher.branch = "a-branch"
        assert fetcher.cachable

        fetcher.branch = None
        fetcher.date = "a-date"
        assert fetcher.cachable

    def test_source_id(self):
        fetcher = fetch_strategy.CvsFetchStrategy(cvs="url")
        assert fetcher.source_id() is None

        fetcher.branch = "my-branch"
        assert fetcher.source_id() == "id-branch=my-branch"

        fetcher.date = "2025-10-12"
        assert fetcher.source_id() == "id-branch=my-branch-date=2025-10-12"

        fetcher.branch = None
        assert fetcher.source_id() == "id-date=2025-10-12"

    def test_mirror_id(self):
        fetcher = fetch_strategy.CvsFetchStrategy(
            cvs=":pserver:anonymous@example.com:/cvsroot/my-module%module=my-module"
        )
        assert fetcher.mirror_id() is None

        fetcher.branch = "my-branch"
        expected_id = (
            os.path.join("cvs", "cvsroot", "my-module%module=my-module") + "%branch=my-branch"
        )
        assert fetcher.mirror_id() == expected_id

    def test_fetch(self, fetcher, mock_vcs_executables, monkeypatch):
        mock_cvs = mock_vcs_executables["cvs"]
        monkeypatch.setattr(
            fetch_strategy, "get_single_file", mock.MagicMock(return_value="my-module")
        )
        monkeypatch.setattr(fetch_strategy.shutil, "move", mock.Mock())

        fetcher.fetch()

        mock_cvs.assert_called_once_with(
            "-z9",
            "-d",
            ":pserver:anonymous@example.com:/cvsroot",
            "checkout",
            "my-module",
        )
        fetch_strategy.get_single_file.assert_called_once_with(".")
        fetch_strategy.shutil.move.assert_called_once_with("my-module", fetcher.stage.source_path)
        assert fetcher.stage.srcdir == "my-module"

    def test_archive(self, fetcher, mock_vcs_executables):
        source_path = fetcher.stage.source_path
        (Path(source_path) / "file.txt").touch()
        fetcher.stage.srcdir = None

        destination = os.path.join(fetcher.stage.path, "archive.tar.gz")
        fetcher.archive(destination)

        mock_tar = mock_vcs_executables["tar"]
        mock_tar.add_default_arg.assert_called_once_with("--exclude=CVS")
        mock_tar.assert_called_once_with("-czf", destination, "source")

    def test_reset(self, fetcher, mock_vcs_executables, monkeypatch):
        mock_cvs = mock_vcs_executables["cvs"]
        mock_remove_untracked = mock.Mock()
        monkeypatch.setattr(fetcher, "_remove_untracked_files", mock_remove_untracked)

        with fetch_strategy.working_dir(fetcher.stage.path):
            fetcher.reset()

        mock_remove_untracked.assert_called_once()
        mock_cvs.assert_called_once_with("update", "-C", ".")

    def test_remove_untracked_files(self, fetcher, mock_vcs_executables, monkeypatch):
        mock_cvs = mock_vcs_executables["cvs"]
        mock_cvs.return_value = "? file.txt\n? dir/"

        source_path = fetcher.stage.source_path
        (Path(source_path) / "file.txt").touch()
        (Path(source_path) / "dir").mkdir()

        mock_unlink = mock.Mock()
        monkeypatch.setattr(os, "unlink", mock_unlink)

        def mock_isfile(p):
            return p == "file.txt"

        monkeypatch.setattr(os.path, "isfile", mock.Mock(side_effect=mock_isfile))

        with fetch_strategy.working_dir(source_path):
            fetcher._remove_untracked_files()

        mock_cvs.assert_called_once_with("-qn", "update", output=str)
        mock_unlink.assert_called_once_with("file.txt")

    def test_str(self):
        fetcher = fetch_strategy.CvsFetchStrategy(cvs="url")
        assert str(fetcher) == "[cvs] url"


class TestSvnFetchStrategy:
    @pytest.fixture
    def mock_vcs_executables(self, monkeypatch):
        """Mock vcs executables."""
        mocks = {"tar": mock.MagicMock(), "svn": mock.MagicMock()}
        mocks["tar"].add_default_arg = mock.Mock()

        def mock_which(name, required=False):
            if name in mocks:
                return mocks[name]
            return mock.MagicMock()

        monkeypatch.setattr(fetch_strategy, "which", mock.MagicMock(side_effect=mock_which))
        return mocks

    @pytest.fixture
    def fetcher(self, tmp_path):
        """Create a SvnFetchStrategy with a mock stage."""
        f = fetch_strategy.SvnFetchStrategy(svn="http://example.com/svn/trunk")

        stage = mock.MagicMock()
        stage.path = str(tmp_path)
        stage.source_path = str(tmp_path / "source")
        os.makedirs(stage.source_path)
        stage.expanded = False
        f.stage = stage

        return f

    def test_init(self):
        fetcher = fetch_strategy.SvnFetchStrategy(svn="url", revision="12345")
        assert fetcher.url == "url"
        assert fetcher.revision == "12345"

    def test_cachable(self):
        fetcher = fetch_strategy.SvnFetchStrategy(svn="url")
        assert not fetcher.cachable
        fetcher.revision = "12345"
        assert fetcher.cachable

    def test_source_id(self):
        fetcher = fetch_strategy.SvnFetchStrategy(svn="url")
        assert fetcher.source_id() is None
        fetcher.revision = "12345"
        assert fetcher.source_id() == "12345"

    def test_mirror_id(self):
        fetcher = fetch_strategy.SvnFetchStrategy(svn="http://example.com/svn/trunk")
        assert fetcher.mirror_id() is None
        fetcher.revision = "12345"
        assert fetcher.mirror_id() == "svn//svn/trunk/12345"

    def test_fetch(self, fetcher, mock_vcs_executables, monkeypatch):
        mock_svn = mock_vcs_executables["svn"]
        monkeypatch.setattr(
            fetch_strategy, "get_single_file", mock.MagicMock(return_value="trunk")
        )
        monkeypatch.setattr(fetch_strategy.shutil, "move", mock.Mock())

        fetcher.fetch()

        mock_svn.assert_called_once_with(
            "checkout", "--force", "--quiet", "http://example.com/svn/trunk"
        )
        fetch_strategy.get_single_file.assert_called_once_with(".")
        fetch_strategy.shutil.move.assert_called_once_with("trunk", fetcher.stage.source_path)
        assert fetcher.stage.srcdir == "trunk"

    def test_archive(self, fetcher, mock_vcs_executables):
        mock_tar = mock_vcs_executables["tar"]
        (Path(fetcher.stage.source_path) / "file.txt").touch()
        fetcher.stage.srcdir = None

        destination = os.path.join(fetcher.stage.path, "archive.tar.gz")
        fetcher.archive(destination)

        mock_tar.add_default_arg.assert_called_once_with("--exclude=.svn")
        mock_tar.assert_called_once_with("-czf", destination, "source")

    def test_reset(self, fetcher, mock_vcs_executables, monkeypatch):
        mock_svn = mock_vcs_executables["svn"]
        mock_remove_untracked = mock.Mock()
        monkeypatch.setattr(fetcher, "_remove_untracked_files", mock_remove_untracked)

        with fetch_strategy.working_dir(fetcher.stage.path):
            fetcher.reset()

        mock_remove_untracked.assert_called_once()
        mock_svn.assert_called_once_with("revert", ".", "-R")

    def test_str(self):
        fetcher = fetch_strategy.SvnFetchStrategy(svn="url")
        assert str(fetcher) == "[svn] url"


class TestHgFetchStrategy:
    @pytest.fixture
    def mock_vcs_executables(self, monkeypatch):
        """Mock vcs executables."""
        mocks = {"tar": mock.MagicMock(), "hg": mock.MagicMock()}
        mocks["tar"].add_default_arg = mock.Mock()

        def mock_which(name, required=False):
            if name in mocks:
                return mocks[name]
            return mock.MagicMock()

        monkeypatch.setattr(fetch_strategy, "which", mock.MagicMock(side_effect=mock_which))
        return mocks

    @pytest.fixture
    def fetcher(self, tmp_path):
        """Create a HgFetchStrategy with a mock stage."""
        f = fetch_strategy.HgFetchStrategy(hg="http://example.com/hg/repo")

        stage = mock.MagicMock()
        stage.path = str(tmp_path)
        stage.source_path = str(tmp_path / "source")
        os.makedirs(stage.source_path)
        stage.expanded = False
        f.stage = stage

        return f

    def test_init(self):
        fetcher = fetch_strategy.HgFetchStrategy(hg="url", revision="12345")
        assert fetcher.url == "url"
        assert fetcher.revision == "12345"

    def test_cachable(self):
        fetcher = fetch_strategy.HgFetchStrategy(hg="url")
        assert not fetcher.cachable
        fetcher.revision = "12345"
        assert fetcher.cachable

    def test_source_id(self):
        fetcher = fetch_strategy.HgFetchStrategy(hg="url")
        assert fetcher.source_id() is None
        fetcher.revision = "12345"
        assert fetcher.source_id() == "12345"

    def test_mirror_id(self):
        fetcher = fetch_strategy.HgFetchStrategy(hg="http://example.com/hg/repo")
        assert fetcher.mirror_id() is None
        fetcher.revision = "12345"
        assert fetcher.mirror_id() == "hg//hg/repo/12345"

    def test_fetch(self, fetcher, mock_vcs_executables, monkeypatch):
        mock_hg = mock_vcs_executables["hg"]
        monkeypatch.setattr(fetch_strategy, "get_single_file", mock.MagicMock(return_value="repo"))
        monkeypatch.setattr(fetch_strategy.shutil, "move", mock.Mock())

        fetcher.fetch()

        mock_hg.assert_called_once_with("clone", "http://example.com/hg/repo")
        fetch_strategy.get_single_file.assert_called_once_with(".")
        fetch_strategy.shutil.move.assert_called_once_with("repo", fetcher.stage.source_path)
        assert fetcher.stage.srcdir == "repo"

    def test_archive(self, fetcher, mock_vcs_executables):
        mock_tar = mock_vcs_executables["tar"]
        (Path(fetcher.stage.source_path) / "file.txt").touch()
        fetcher.stage.srcdir = None

        destination = os.path.join(fetcher.stage.path, "archive.tar.gz")
        fetcher.archive(destination)

        mock_tar.add_default_arg.assert_called_once_with("--exclude=.hg")
        mock_tar.assert_called_once_with("-czf", destination, "source")

    def test_reset(self, fetcher, mock_vcs_executables, monkeypatch):
        mock_hg = mock_vcs_executables["hg"]
        mock_rmtree = mock.Mock()
        mock_move = mock.Mock()
        monkeypatch.setattr(shutil, "rmtree", mock_rmtree)
        monkeypatch.setattr(shutil, "move", mock_move)

        with fetch_strategy.working_dir(fetcher.stage.path):
            fetcher.reset()

        mock_hg.assert_called_once_with("clone", fetcher.stage.source_path, "scrubbed-source-tmp")
        mock_rmtree.assert_called_once_with(fetcher.stage.source_path, ignore_errors=True)
        mock_move.assert_called_once_with("scrubbed-source-tmp", fetcher.stage.source_path)

    def test_str(self):
        fetcher = fetch_strategy.HgFetchStrategy(hg="url")
        assert str(fetcher) == "[hg] url"
