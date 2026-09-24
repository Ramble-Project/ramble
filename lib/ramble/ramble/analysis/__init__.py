# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Analysis package for Ramble"""

from ramble.analysis.backwards import BackwardsAnalysisStrategy

# flake8: noqa: F401
from ramble.analysis.base import AnalysisStrategyBase as AnalysisStrategyBase
from ramble.analysis.forward import ForwardAnalysisStrategy

_strategy_registry = {
    "forward": ForwardAnalysisStrategy,
    "backwards": BackwardsAnalysisStrategy,
}


def get_strategy(name, app_inst):
    """Get the analysis strategy instance by name."""
    if name not in _strategy_registry:
        raise ValueError(f"Unknown analysis strategy: {name}")
    return _strategy_registry[name](app_inst)
