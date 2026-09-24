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

import llnl.util.filesystem as fs

import ramble.config
from ramble.error import RambleCommandError
from ramble.main import RambleCommand

import spack.util.url

mirror = RambleCommand("mirror")

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="does not run on windows")


@pytest.fixture
def tmp_scope():
    """Creates a temporary configuration scope"""

    base_name = "internal-testing-scope"
    current_overrides = {x.name for x in ramble.config.config.matching_scopes(rf"^{base_name}")}

    num_overrides = 0
    scope_name = base_name
    while scope_name in current_overrides:
        scope_name = f"{base_name}{num_overrides}"
        num_overrides += 1

    with ramble.config.override(ramble.config.InternalConfigScope(scope_name)):
        yield scope_name


def _validate_url(url):
    return


@pytest.fixture(autouse=True)
def url_check(monkeypatch):
    monkeypatch.setattr(spack.util.url, "require_url_format", _validate_url)


def test_mirror_nonexisting(tmp_scope):
    with pytest.raises(RambleCommandError):
        mirror("remove", "--scope", tmp_scope, "not-a-mirror")

    with pytest.raises(RambleCommandError):
        mirror("set-url", "--scope", tmp_scope, "not-a-mirror", "http://ramble.io")


def test_mirror_list_empty(tmp_scope):
    out = mirror("list", "--scope", tmp_scope)
    assert mirror.returncode == 0
    assert "No mirrors configured." in out


def test_mirror_add(tmp_scope):
    mirror("add", "--scope", tmp_scope, "first", "my.url.com")

    output = mirror("list")
    assert "my.url.com" in output
    assert "first" in output


def test_mirror_remove(tmp_scope):
    mirror("add", "--scope", tmp_scope, "first", "my.url.com")
    mirror("add", "--scope", tmp_scope, "second", "another.url.com")

    output = mirror("list")
    assert "my.url.com" in output
    assert "first" in output
    assert "another.url.com" in output
    assert "second" in output

    output = mirror("remove", "--scope", tmp_scope, "second")
    assert "Removed mirror second" in output

    output = mirror("list")
    assert "second" not in output
    assert "first" in output


def test_mirror_set_url(tmp_scope):
    mirror("add", "--scope", tmp_scope, "first", "my.url.com")
    output = mirror("list")
    assert "my.url.com" in output
    assert "url" in output
    mirror("set-url", "--scope", tmp_scope, "first", "changed.url.com")
    output = mirror("list")
    assert "changed.url.com" in output


def test_mirror_set_push_url(tmp_scope):
    mirror("add", "--scope", tmp_scope, "first", "my.url.com")
    output = mirror("list")
    assert "my.url.com" in output
    assert "url" in output
    mirror("set-url", "--scope", tmp_scope, "first", "changed.url.com", "--push")
    output = mirror("list")
    assert "my.url.com (fetch)" in output
    assert "changed.url.com (push)" in output


def test_mirror_name_collision(tmp_scope):
    mirror("add", "--scope", tmp_scope, "first", "1")

    with pytest.raises(RambleCommandError):
        mirror("add", "--scope", tmp_scope, "first", "1")


def test_mirror_destroy(
    install_mockery_mutable_config,
    mock_applications,
    mock_fetch,
    mock_archive,
    mutable_config,
    monkeypatch,
    tmpdir,
):
    mirror_dir = tmpdir.join("mirror_dir")
    mirror_url = f"file://{mirror_dir.strpath}"
    mirror("add", "atest", mirror_url)

    fs.mkdirp(mirror_dir.strpath)
    assert os.path.exists(mirror_dir.strpath)

    # Destroy mirror by name
    mirror("destroy", "-m", "atest")

    assert not os.path.exists(mirror_dir.strpath)

    # Destroy mirror by url
    fs.mkdirp(mirror_dir.strpath)
    assert os.path.exists(mirror_dir.strpath)
    mirror("destroy", "--mirror-url", mirror_url)

    assert not os.path.exists(mirror_dir.strpath)

    mirror("remove", "atest")
