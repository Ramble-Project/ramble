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
