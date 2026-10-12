# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Tests on the ExperimentResult class"""

import os
import time

import pytest

from ramble.experiment_result import ExperimentResult
from ramble.util.file_util import get_newest_experiment_file


@pytest.fixture
def experiment_result():
    """Returns a basic experiment result"""

    class AppInst:
        def __init__(self):
            class Expander:
                def __init__(self):
                    self.experiment_run_dir = ""

            self.expander = Expander()
            self.experiment_hash = "test_hash"

    return ExperimentResult(AppInst())


def test_experiment_result_to_dict(mutable_mock_apps_repo):
    basic_app_inst = mutable_mock_apps_repo.get("basic")
    basic_app_inst.set_variables_and_variants(
        {"workload_name": "test_wl", "experiment_status": "placeholder", "test_var": "my_var"},
        {},
        None,
        None,
    )
    basic_app_inst.set_status("UNKNOWN")
    exp_res = ExperimentResult(basic_app_inst)
    exp_res.finalize(None)
    res_dict = exp_res.to_dict()

    assert "name" in res_dict
    assert "application_name" in res_dict
    assert res_dict["RAMBLE_STATUS"] == "FAILED"
    assert res_dict["RAMBLE_RAW_VARIABLES"]["experiment_status"] == "UNKNOWN"
    assert "EXPERIMENT_CHAIN" in res_dict
    assert "CONTEXTS" in res_dict
    assert "TAGS" in res_dict
    assert res_dict["N_REPEATS"] == 0
    assert res_dict["RAMBLE_VARIABLES"]["test_var"] == "my_var"
    assert res_dict["RAMBLE_RAW_VARIABLES"]["test_var"] == "my_var"
    assert "RAMBLE_RAW_VARIABLES" in res_dict


def test_experiment_result_read_write_cache(tmpdir, experiment_result):
    """Test that the cache is written and read correctly"""
    experiment_dir = tmpdir.mkdir("experiment")
    experiment_result._app_inst.expander.experiment_run_dir = str(experiment_dir)

    # Test that the cache is written
    experiment_result.write_cache(experiment_result._app_inst)
    cache_file = os.path.join(str(experiment_dir), experiment_result.cache_file_name)
    assert os.path.exists(cache_file)

    # Test that the cache is read correctly
    assert experiment_result.read_cache(None, experiment_result._app_inst)


def test_experiment_result_cache_invalidation_new_file(tmpdir, experiment_result):
    """Test that the cache is invalidated if a file is newer than the cache"""
    experiment_dir = tmpdir.mkdir("experiment")
    experiment_result._app_inst.expander.experiment_run_dir = str(experiment_dir)

    # Write the cache
    experiment_result.write_cache(experiment_result._app_inst)
    time.sleep(0.1)

    # Create a new file
    new_file = os.path.join(str(experiment_dir), "new_file")
    with open(new_file, "w", encoding="utf-8") as f:
        f.write("test")

    # Test that the cache is invalidated
    assert not experiment_result.read_cache(None, experiment_result._app_inst)


def test_experiment_result_cache_invalidation_hash_change(tmpdir, experiment_result):
    """Test that the cache is invalidated if the experiment hash changes"""
    experiment_dir = tmpdir.mkdir("experiment")
    experiment_result._app_inst.expander.experiment_run_dir = str(experiment_dir)

    # Write the cache
    experiment_result.write_cache(experiment_result._app_inst)

    # Change the experiment hash
    experiment_result._app_inst.experiment_hash = "new_hash"

    # Test that the cache is invalidated
    assert not experiment_result.read_cache(None, experiment_result._app_inst)


def test_experiment_result_get_newest_experiment_file(tmpdir):
    """Test that the newest experiment file is found correctly"""
    experiment_dir = tmpdir.mkdir("experiment")
    sub_dir = os.path.join(str(experiment_dir), "sub")
    os.mkdir(sub_dir)

    # Create some files
    file1 = os.path.join(str(experiment_dir), "file1")
    file2 = os.path.join(sub_dir, "file2")
    ramble_file = os.path.join(str(experiment_dir), "ramble_file")

    with open(file1, "w", encoding="utf-8") as f:
        f.write("test")
    time.sleep(0.1)

    with open(file2, "w", encoding="utf-8") as f:
        f.write("test")
    time.sleep(0.1)

    with open(ramble_file, "w", encoding="utf-8") as f:
        f.write("test")

    # Test that the newest file is found correctly
    newest_file, _ = get_newest_experiment_file(str(experiment_dir))
    assert newest_file == file2

    # Test that ramble_file is ignored
    newest_file, _ = get_newest_experiment_file(str(experiment_dir))
    assert "ramble_file" not in newest_file


def test_get_newest_experiment_file_outer_file_not_found(tmpdir, monkeypatch):
    """Test that FileNotFoundError is handled in outer loop of get_newest_experiment_file"""
    experiment_dir = tmpdir.mkdir("experiment")
    sub_dir = os.path.join(str(experiment_dir), "sub")
    os.mkdir(sub_dir)

    file1 = os.path.join(str(experiment_dir), "file1")
    with open(file1, "w", encoding="utf-8") as f:
        f.write("test")

    orig_scandir = os.scandir

    def mock_scandir(path):
        if str(path) == sub_dir:
            raise FileNotFoundError("Mock file not found")
        return orig_scandir(path)

    monkeypatch.setattr(os, "scandir", mock_scandir)

    # Should not raise exception and should find file1
    newest_file, _ = get_newest_experiment_file(str(experiment_dir))
    assert newest_file == file1


def test_get_newest_experiment_file_inner_file_not_found(tmpdir, monkeypatch):
    """Test that FileNotFoundError is handled in inner loop of get_newest_experiment_file"""
    experiment_dir = tmpdir.mkdir("experiment")

    class MockEntry:
        def __init__(self, path):
            self.path = path
            self.name = os.path.basename(path)

        def is_file(self):
            return True

        def is_dir(self, follow_symlinks=False):
            return False

        def stat(self):
            raise FileNotFoundError("Mock file not found")

    class MockScandir:
        def __init__(self, path):
            self.path = path

        def __enter__(self):
            return iter([MockEntry(os.path.join(self.path, "phantom_file"))])

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    monkeypatch.setattr(os, "scandir", MockScandir)

    # Should not raise exception and should return None, None as no valid file is found
    newest_file, max_mtime = get_newest_experiment_file(str(experiment_dir))
    assert newest_file is None
    assert max_mtime is None


def test_extract_inmem_foms_skips_none(mutable_mock_apps_repo):
    """Test that extract_inmem_foms skips FOMs with None value"""
    app_inst = mutable_mock_apps_repo.get("basic")

    # Set up _fom_map to return None for a key
    app_inst._fom_map = {"test_key": None}

    inmem_defs = {
        "test_context": {
            "foms": {
                "test_fom": {
                    "fom_name_expanded": "test_fom",
                    "fom_map_key": "test_key",
                    "units_expanded": "s",
                    "origin": "test",
                    "origin_type": "test",
                    "fom_type": "test",
                }
            }
        }
    }

    fom_values = {}
    app_inst.extract_inmem_foms(inmem_defs, fom_values)

    # Assert that test_fom is NOT in fom_values
    assert "test_context" not in fom_values or "test_fom" not in fom_values["test_context"]


def test_analyze_experiments_skips_none_fom(mutable_mock_apps_repo, monkeypatch, tmpdir):
    """Test that _analyze_experiments skips FOMs when value group is None"""
    app_inst = mutable_mock_apps_repo.get("basic")

    # Create a temp file to analyze
    log_file = tmpdir.join("test.out")
    log_file.write("Match line but optional group is empty: Value=\nValid Value=42\n")

    import re

    # Mock analysis_dicts
    def mock_analysis_dicts(criteria_list):
        files = {
            str(log_file): {
                "success_criteria": [],
                "contexts": {"null": ["test_fom", "valid_fom"]},
            }
        }
        f_defs = {
            "null": {
                "foms": {
                    "test_fom": {
                        "regex": re.compile(r"Value=(?P<val>\d*)"),  # Optional digits
                        "group": "val",
                        "fom_name_expanded": "test_fom",
                        "units": "",
                        "origin": "test",
                        "origin_type": "test",
                        "fom_type": "test",
                        "contexts": [],
                        "units_expanded": None,
                        "origin_type_expanded": "test",
                        "fom_type_expanded": "test",
                    },
                    "valid_fom": {
                        "regex": re.compile(r"Valid Value=(?P<val>\d+)"),
                        "group": "val",
                        "fom_name_expanded": "valid_fom",
                        "units": "",
                        "origin": "test",
                        "origin_type": "test",
                        "fom_type": "test",
                        "contexts": [],
                        "units_expanded": None,
                        "origin_type_expanded": "test",
                        "fom_type_expanded": "test",
                    },
                }
            }
        }
        inmem_defs = {}
        return files, f_defs, inmem_defs

    monkeypatch.setattr(app_inst, "analysis_dicts", mock_analysis_dicts)

    # Mock other dependencies of _analyze_experiments
    monkeypatch.setattr(app_inst.result, "read_cache", lambda *args: False)
    monkeypatch.setattr(app_inst, "get_status", lambda: None)
    monkeypatch.setattr(app_inst, "set_status", lambda status: None)
    monkeypatch.setattr(app_inst.result, "finalize", lambda workspace: None)

    from unittest.mock import MagicMock

    app_inst._exp_lock = MagicMock()

    class MockExpander:
        def expand_var(self, val, extra_vars=None):
            if val == "{experiment_run_dir}":
                return str(tmpdir)
            return val

        def expand_var_name(self, var_name, extra_vars=None):
            return self.expand_var(f"{{{var_name}}}", extra_vars=extra_vars)

    app_inst.expander = MockExpander()

    class MockCriteriaList:
        def all_criteria(self):
            return []

        def passed(self):
            return True

    criteria_list = MockCriteriaList()

    # Call the method
    app_inst._analyze_experiments(criteria_list)

    # Verify that the FOM was not added to app_inst.result.contexts
    fom_found = False
    valid_fom_found = False
    for context in app_inst.result.contexts:
        if context["name"] == "null":
            for fom in context["foms"]:
                if fom["name"] == "test_fom":
                    fom_found = True
                if fom["name"] == "valid_fom":
                    valid_fom_found = True

    assert not fom_found
    assert valid_fom_found


def test_derived_foms_extraction(mutable_mock_apps_repo):
    """Test string and callable formula FOMs and get_fom_value in extract_inmem_foms"""
    from ramble.expander import Expander

    app_inst = mutable_mock_apps_repo.get("basic")
    app_inst.expander = Expander({}, None)

    null_key = ("null", "null", frozenset())
    iter_key = ("Iteration 1", "iteration", frozenset({("itr", "1")}))
    fom_values = {
        null_key: {
            "Days per ns": {
                "value": "2.0",
                "units": "days/ns",
                "origin": "test",
                "origin_type": "application",
                "fom_type": "test",
            }
        },
        iter_key: {
            "Step time": {
                "value": "0.25",
                "units": "s",
                "origin": "test",
                "origin_type": "application",
                "fom_type": "test",
            }
        },
    }
    context_metadata = {
        null_key: {"name": "null", "def_name": "null", "vars": {}},
        iter_key: {
            "name": "Iteration 1",
            "def_name": "iteration",
            "vars": {"itr": "1"},
        },
    }

    def _make_def(name, formula, extra_vars=None):
        return {
            "fom_name_expanded": name,
            "fom_map_key": None,
            "formula": formula,
            "extra_vars": extra_vars,
            "units_expanded": "1/s",
            "origin": "test",
            "origin_type": "application",
            "fom_type": "test",
        }

    inmem_defs = {
        "null": {
            "foms": {
                "Scaled throughput": _make_def(
                    "Scaled throughput",
                    lambda app: float(app.get_fom_value("Ns per day")) * 4.0,
                ),
                "Ns per day": _make_def(
                    "Ns per day",
                    "1.0 / {Days per ns} * {mod_factor}",
                    extra_vars={"mod_factor": 2.0},
                ),
                "Missing dependency FOM": _make_def(
                    "Missing dependency FOM", "1.0 / {Missing FOM}"
                ),
            }
        },
    }

    app_inst.extract_inmem_foms(inmem_defs, fom_values, context_metadata)

    assert float(fom_values[null_key]["Ns per day"]["value"]) == pytest.approx(1.0)
    assert float(fom_values[null_key]["Scaled throughput"]["value"]) == pytest.approx(4.0)
    assert "Missing dependency FOM" not in fom_values[null_key]
    assert app_inst.get_fom_value("Step time", context="Iteration 1") == "0.25"
    assert app_inst.get_fom_values("Step time", context="iteration") == ["0.25"]
    assert app_inst.get_fom_value("Missing dependency FOM") is None
