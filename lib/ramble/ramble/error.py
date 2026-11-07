# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import inspect
import sys
from typing import Optional, Tuple, Type

from ramble.util.logger import logger

#: whether we should write stack traces or short error messages
#: this is module-scoped because it needs to be set very early
debug = False


class RambleError(Exception):
    """This is the superclass for all Ramble errors.
    Subclasses can be found in the modules they have to do with.
    """

    def __init__(self, message: str, long_message: Optional[str] = None) -> None:
        super().__init__()
        self.message: str = message
        self._long_message: Optional[str] = long_message

        # we allow exceptions to print debug info via print_context()
        # before they are caught at the top level. If they *haven't*
        # printed context early, we do it by default when die() is
        # called, so we need to remember whether it's been called.
        self.printed: bool = False

    @property
    def long_message(self) -> Optional[str]:
        return self._long_message

    def print_context(self) -> None:
        """Print extended debug information about this exception.

        This is usually printed when the top-level Ramble error handler
        calls ``die()``, but it can be called separately beforehand if a
        lower-level error handler needs to print error context and
        continue without raising the exception to the top level.
        """
        if self.printed:
            return

        # basic debug message
        logger.error(self.message)
        if self.long_message:
            sys.stderr.write(self.long_message)
            sys.stderr.write("\n")

        # stack trace, etc. in debug mode.
        if debug:
            sys.excepthook(*sys.exc_info())

        sys.stderr.flush()
        self.printed = True

    def die(self) -> None:
        self.print_context()
        sys.exit(1)

    def __str__(self) -> str:
        msg = self.message
        if self._long_message:
            msg += f"\n    {self._long_message}"
        return msg

    def __repr__(self) -> str:
        args = [repr(self.message), repr(self.long_message)]
        args = ",".join(args)
        module = inspect.getmodule(self)
        if module:
            qualified_name = f"{module.__name__}.{type(self).__name__}"
        else:
            qualified_name = type(self).__name__
        return qualified_name + "(" + args + ")"

    def __reduce__(self) -> Tuple[Type["RambleError"], Tuple[str, Optional[str]]]:
        return type(self), (self.message, self.long_message)


class DirectiveError(RambleError):
    """This is raised when something is wrong with a language directive."""


class RambleCommandError(Exception):
    """Raised when RambleCommand execution fails."""


class ApplicationError(RambleError):
    """
    Exception that is raised by applications
    """


class ExecutableNameError(RambleError):
    """
    Exception raised when a name collision in executables happens
    """


class FormattedExecutableError(ApplicationError):
    """
    Exception raise when there are issues defining formatted executables
    """


class ChainCycleDetectedError(ApplicationError):
    """
    Exception raised when a cycle is detected in a defined experiment chain
    """


class InvalidChainError(ApplicationError):
    """
    Exception raised when a invalid chained experiment is defined
    """


class ObjectValidationError(ApplicationError):
    """Error when an object validator fails"""


class ModifierError(RambleError):
    """
    Exception that is raised by modifiers
    """


class ConflictingModifiersError(ModifierError):
    """
    Exception raised when two modifiers on the same experiment conflict
    """


class InvalidModeError(ModifierError):
    """
    Exception raised when an invalid mode is passed
    """


class PackageManagerError(RambleError):
    """
    Exception that is raised by package managers
    """
