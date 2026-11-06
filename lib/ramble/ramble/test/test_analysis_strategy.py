# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Unit tests for analysis strategy pattern"""

import pytest

import ramble.analysis
from ramble.analysis.forward import ForwardAnalysisStrategy


class DummyApp:
    pass


def test_get_strategy():
    app = DummyApp()

    strategy = ramble.analysis.get_strategy("forward", app)
    assert isinstance(strategy, ForwardAnalysisStrategy)
    assert strategy.app_inst is app

    from ramble.analysis.backwards import BackwardsAnalysisStrategy

    strategy_backwards = ramble.analysis.get_strategy("backwards", app)
    assert isinstance(strategy_backwards, BackwardsAnalysisStrategy)
    assert strategy_backwards.app_inst is app

    with pytest.raises(ValueError, match="Unknown analysis strategy: invalid"):
        ramble.analysis.get_strategy("invalid", app)


def test_read_file_backwards(tmpdir):
    from ramble.analysis.backwards import _read_file_backwards

    temp_file = tmpdir.join("test_backwards.txt")
    lines = ["line 1\n", "line 2\n", "line 3\n"]
    temp_file.write("".join(lines))

    result = list(_read_file_backwards(str(temp_file)))
    assert result == ["line 3\n", "line 2\n", "line 1\n"]


def test_backwards_strategy_validation():
    from ramble.analysis.backwards import BackwardsAnalysisStrategy

    class MockResult:
        def read_cache(self, workspace, app):
            return False

    class MockApp:
        def __init__(self):
            self.success_list = None
            self.get_status = lambda: None
            self.result = MockResult()

        def analysis_dicts(self, criteria_list):
            files = {"test.log": {"contexts": {"some_context": ["fom1"]}, "success_criteria": []}}
            return files, {}, {}

    app = MockApp()
    app.analysis_strategy = "backwards"
    strategy = BackwardsAnalysisStrategy(app)

    class MockWorkspace:
        dry_run = False

    msg = "BackwardsAnalysisStrategy cannot be used because context"
    with pytest.raises(ValueError, match=msg):
        strategy(MockWorkspace())


def test_backwards_strategy_fallback(monkeypatch):
    from ramble.analysis.backwards import BackwardsAnalysisStrategy

    called_forward = False

    class MockForwardStrategy:
        def __init__(self, app):
            pass

        def __call__(self, workspace):
            nonlocal called_forward
            called_forward = True

    monkeypatch.setitem(ramble.analysis._strategy_registry, "forward", MockForwardStrategy)

    class MockResult:
        def read_cache(self, workspace, app):
            return False

    class MockApp:
        def __init__(self):
            self.success_list = None
            self.get_status = lambda: None
            self.result = MockResult()
            self.analysis_strategy = None

        def analysis_dicts(self, criteria_list):
            files = {"test.log": {"contexts": {"some_context": ["fom1"]}, "success_criteria": []}}
            return files, {}, {}

    app = MockApp()
    strategy = BackwardsAnalysisStrategy(app)

    class MockWorkspace:
        dry_run = False

    strategy(MockWorkspace())
    assert called_forward


def test_backwards_strategy_dynamic_foms_validation():
    from ramble.analysis.backwards import BackwardsAnalysisStrategy

    class MockResult:
        def read_cache(self, workspace, app):
            return False

    class MockApp:
        def __init__(self):
            self.success_list = None
            self.get_status = lambda: None
            self.result = MockResult()

        def analysis_dicts(self, criteria_list):
            files = {"test.log": {"contexts": {"null": ["fom1"]}, "success_criteria": []}}
            f_defs = {
                "null": {
                    "foms": {
                        "fom1": {
                            "fom_name_expanded": None,
                            "units_expanded": "s",
                        }
                    }
                }
            }
            return files, f_defs, {}

    app = MockApp()
    app.analysis_strategy = "backwards"
    strategy = BackwardsAnalysisStrategy(app)

    class MockWorkspace:
        dry_run = False

    msg = "BackwardsAnalysisStrategy cannot be used because FOM 'fom1' has dynamic name or units."
    with pytest.raises(ValueError, match=msg):
        strategy(MockWorkspace())


def test_backwards_strategy_dynamic_foms_fallback(monkeypatch):
    from ramble.analysis.backwards import BackwardsAnalysisStrategy

    called_forward = False

    class MockForwardStrategy:
        def __init__(self, app):
            pass

        def __call__(self, workspace):
            nonlocal called_forward
            called_forward = True

    monkeypatch.setitem(ramble.analysis._strategy_registry, "forward", MockForwardStrategy)

    class MockResult:
        def read_cache(self, workspace, app):
            return False

    class MockApp:
        def __init__(self):
            self.success_list = None
            self.get_status = lambda: None
            self.result = MockResult()
            self.analysis_strategy = None

        def analysis_dicts(self, criteria_list):
            files = {"test.log": {"contexts": {"null": ["fom1"]}, "success_criteria": []}}
            f_defs = {
                "null": {
                    "foms": {
                        "fom1": {
                            "fom_name_expanded": "fom1",
                            "units_expanded": None,
                        }
                    }
                }
            }
            return files, f_defs, {}

    app = MockApp()
    strategy = BackwardsAnalysisStrategy(app)

    class MockWorkspace:
        dry_run = False

    strategy(MockWorkspace())
    assert called_forward


def test_forward_strategy_ignores_unformatted_context_regex_groups(tmpdir, monkeypatch):
    import re
    from unittest.mock import patch

    from llnl.util import tty

    import ramble.util.lock as lk

    log_file = str(tmpdir.join("test.log"))
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("size 64 val 1.5\n")
        f.write("size 64 val 2.5\n")

    shared_regex = re.compile(r"size (?P<size>\d+) val (?P<val>[\d.]+)")

    class MockResult:
        def __init__(self):
            self.contexts = []
            self.success_criteria = {}

        def read_cache(self, workspace, app):
            return False

        def finalize(self, workspace):
            pass

    class MockApp:
        def __init__(self):
            self.success_list = None
            self.get_status = lambda: None
            self.set_status = lambda status: None
            self.result = MockResult()
            self.experiment_lock = lk.Lock(str(tmpdir.join("lock")))
            self.workflow_manager = None
            self.extract_inmem_foms = lambda *args: None

        def analysis_dicts(self, criteria_list):
            files = {log_file: {"contexts": {"size_ctx": ["val_fom"]}, "success_criteria": []}}
            f_defs = {
                "size_ctx": {
                    "definition": {
                        "regex": shared_regex,
                        "format": "Size: {size}",
                    },
                    "foms": {
                        "val_fom": {
                            "regex": shared_regex,
                            "group": "val",
                            "fom_name_expanded": "Value",
                            "units": "s",
                            "units_expanded": "s",
                            "origin": "test",
                            "origin_type": "application",
                            "fom_type": None,
                            "contexts": ["size_ctx"],
                        }
                    },
                }
            }
            return files, f_defs, {}

    class MockWorkspace:
        dry_run = False

    monkeypatch.setattr(tty, "_debug", 0)
    app = MockApp()
    strategy = ForwardAnalysisStrategy(app)
    with patch("ramble.util.logger.logger.warn") as mock_warn:
        strategy(MockWorkspace())
        mock_warn.assert_not_called()

    assert len(app.result.contexts) == 1
    assert app.result.contexts[0]["name"] == "Size: 64"
    assert app.result.contexts[0]["context_vars"] == {"size": "64"}
    assert app.result.contexts[0]["foms"][0]["value"] == "2.5"

    # Verify debug mode emits a warning on duplicate context match and debug log on FOM overwrite
    monkeypatch.setattr(tty, "_debug", 1)
    app_debug = MockApp()
    strategy_debug = ForwardAnalysisStrategy(app_debug)
    with patch("ramble.util.logger.logger.warn") as mock_warn:
        with patch("ramble.util.logger.logger.debug") as mock_debug:
            strategy_debug(MockWorkspace())
            mock_warn.assert_called_once_with(
                "Context 'Size: 64' (from 'size_ctx') matched multiple times; "
                "earlier FOM values in this context may be overwritten."
            )
            mock_debug.assert_any_call(
                " --- Overwriting FOM 'Value' in context 'Size: 64' (1.5 -> 2.5)"
            )


def test_hpl_problem_name_context_includes_tv():
    import re

    import ramble.repository

    hpl_inst = ramble.repository.get("hpl")
    ctx_def = hpl_inst.figure_of_merit_contexts[frozenset()]["problem-name"]
    assert ctx_def["output_format"] == "T/V-N-NB-P-Q = {TV}-{N}-{NB}-{P}-{Q}"

    line = "WR00L2L2        1000   128     1     1               0.00              4.442e+01"
    match = re.match(ctx_def["regex"], line)
    assert match is not None
    assert match.groupdict() == {
        "TV": "WR00L2L2",
        "N": "1000",
        "NB": "128",
        "P": "1",
        "Q": "1",
    }
