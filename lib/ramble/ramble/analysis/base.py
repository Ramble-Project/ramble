# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

"""Define base classes for analysis strategies"""

from ramble.language.application_language import ApplicationMeta


class AnalysisStrategyBase(metaclass=ApplicationMeta):

    def __init__(self, app_inst):
        self.app_inst = app_inst

    def __call__(self, workspace):
        raise NotImplementedError
