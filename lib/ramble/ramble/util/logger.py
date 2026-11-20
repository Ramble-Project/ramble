# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

from contextlib import contextmanager
from pathlib import Path

import llnl.util.tty.log
from llnl.util import tty

import ramble.util.colors as color


class Logger:
    """Logger class

    This class providers additional functionality on top of LLNL's tty utility.
    Namely, this class provides a stack of log files, and allows errors to be
    printed to all log files instead of only one.
    """

    def __init__(self):
        """Construct a a logger instance

        A logger instance consists of a stack of logs (self.log_stack) and an
        enabled flag.

        If the enabled flag is set to False, the logger will only print to
        screen instead of to underlying files.
        """
        self.log_stack = []
        self.enabled = True
        self._aggregated_warnings = False
        self.file_warnings = {}
        self.global_warnings = []

    def aggregate_warnings(self, on=True):
        """Control whether warnings are aggregated or not"""
        self._aggregated_warnings = on

    def is_verbose(self):
        """Return whether verbose logging is enabled."""
        return tty.is_verbose()

    def set_verbose(self, flag):
        """Enable or disable verbose logging."""
        tty.set_verbose(flag)

    def debug_level(self):
        """Return the current debug verbosity level."""
        return tty.debug_level()

    def is_debug(self, level=1):
        """Return whether debug logging is enabled at or above ``level``."""
        return tty.is_debug(level)

    def set_debug(self, level=0):
        """Set the debug verbosity level."""
        tty.set_debug(level)

    def set_stacktrace(self, flag):
        """Enable or disable stacktraces on log output."""
        tty.set_stacktrace(flag)

    def set_timestamp(self, flag):
        """Enable or disable timestamps on log output."""
        tty.set_timestamp(flag)

    def msg_enabled(self):
        """Return whether standard message output is enabled."""
        return tty.msg_enabled()

    def set_msg_enabled(self, flag):
        """Enable or disable standard message output."""
        tty.set_msg_enabled(flag)

    def warn_enabled(self):
        """Return whether warning output is enabled."""
        return tty.warn_enabled()

    def set_warn_enabled(self, flag):
        """Enable or disable warning output."""
        tty.set_warn_enabled(flag)

    def error_enabled(self):
        """Return whether error output is enabled."""
        return tty.error_enabled()

    def set_error_enabled(self, flag):
        """Enable or disable error output."""
        tty.set_error_enabled(flag)

    @contextmanager
    def suppress_output(self, msg_enabled=False, warn_enabled=False, error_enabled=True):
        """Context manager to temporarily configure output suppression.

        By default, suppresses messages and warnings while keeping errors
        enabled. Restores previous output settings on exit.
        """
        with tty.SuppressOutput(
            msg_enabled=msg_enabled,
            warn_enabled=warn_enabled,
            error_enabled=error_enabled,
        ):
            yield

    def get_yes_or_no(self, prompt, default=None):
        """Prompt the user for a yes or no response."""
        return tty.get_yes_or_no(prompt, default=default)

    def add_log(self, path):
        """Add a log to the current log stack

        Opens (with 'a+' permissions) the file provided by the 'path' argument,
        and stores both the path, and the opened stream object in the current stack
        in the active position.

        Args:
            path: File path for the new log file
        """
        if isinstance(path, str) and self.enabled:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            stream = llnl.util.tty.log.Unbuffered(open(path, "a+", encoding="utf-8"))
            self.log_stack.append((path, stream))

    def remove_log(self):
        """Remove the active stack

        Pop the active log from the log stack, and close the log stream.
        """
        if self.enabled:
            last_log = self.log_stack.pop()
            last_log[1].close()

    @contextmanager
    def add_log_context(self, path):
        """Context manager to add and remove a log file

        Ensures that the log is removed from the stack even if an exception occurs.
        If inner add_log/remove_log calls disrupt the stack order, it ensures
        it only removes the log it added.
        """
        initial_len = len(self.log_stack)
        added_log = None
        try:
            self.add_log(path)
            if len(self.log_stack) > initial_len:
                added_log = self.log_stack[-1]
            yield
        finally:
            if added_log:
                if len(self.log_stack) > initial_len:
                    if self.log_stack[-1] == added_log:
                        self.remove_log()
                    else:
                        tty.warn(
                            f"Cannot remove log {added_log[0]} as it is no longer the active log. "
                            f"The log stack was modified within the `add_log_context` block."
                        )

    def active_log(self):
        """Return the path for the active log

        If any logs are in the log stack, return the filepath of the active log.
        Otherwise, return the string 'stdout'
        """
        if self.log_stack:
            return self.log_stack[-1][0]
        return "stdout"

    def active_stream(self):
        """Return the stream for the active log

        If any logs are in the log stack, return the stream object of the active log.
        Otherwise, return None to indicate the system is handling printing.
        """
        if self.log_stack:
            return self.log_stack[-1][1]
        return None

    def _stream_kwargs(self, default_kwargs=None, index=None):
        """Construct keyword arguments for a stream

        Build keyword arguments of the form: {'stream': <log_stream>} to allow
        LLNL's tty utility to print to a specific stream.

        When default_kwargs are passed in, these are applied on top of the
        constructed kwargs.

        When index is passed in, the stream added into kwargs is the log in
        position index within the stack (where -1 is considered active).

        Args:
            default_kwargs: Default keyword arguments to use
            index: Index of log (in stack) to build kwargs for

        Returns:
            kwargs: Constructed kwargs with defaults applied
        """
        if default_kwargs is None:
            default_kwargs = {}
        kwargs = {}
        stream_index = None
        if index is not None:
            if index >= 0 and index <= len(self.log_stack):
                stream_index = index
            else:
                tty.die(
                    f"Error: Requested stream index of {index} is outside of "
                    f"the stream range of 0 - {len(self.log_stack)}"
                )

        else:
            if self.log_stack:
                stream_index = len(self.log_stack) - 1

        if stream_index is not None:
            kwargs["stream"] = self.log_stack[stream_index][1]

        kwargs.update(default_kwargs)

        return kwargs

    @contextmanager
    def configure_colors(self, **kwargs):
        old_value = color.get_color_when()
        try:
            if "stream" in kwargs:
                color.set_color_when("never")
            yield
        finally:
            color.set_color_when(old_value)

    def all_msg(self, *args, **kwargs):
        """Print a message to all logs

        Pass all args and kwargs to tty.info (which will concatenate and
        print). Perform this action for all logs and the default log (to
        screen).
        """
        if not self.msg_enabled():
            return

        for idx, _ in enumerate(self.log_stack):
            st_kwargs = self._stream_kwargs(default_kwargs=kwargs, index=idx)
            with self.configure_colors(**st_kwargs):
                tty.info(*args, **st_kwargs)

        self.screen_msg(*args, **kwargs)

    def screen_msg(self, *args, **kwargs):
        """Print a message to the screen only, bypassing active log files.

        Pass all args and kwargs to tty.msg.
        """
        tty.msg(*args, **kwargs)

    def msg(self, *args, **kwargs):
        """Print a message to the active log

        Pass all args and kwargs to tty.info (which will concatenate and
        print). Perform this action for the active log only.
        """
        if not self.msg_enabled():
            return

        st_kwargs = self._stream_kwargs(default_kwargs=kwargs)
        with self.configure_colors(**st_kwargs):
            tty.info(*args, **st_kwargs)

    def info(self, *args, **kwargs):
        """Print a message to the active log

        Pass all args and kwargs to tty.info (which will concatenate and
        print). Perform this action for the active log only.
        """
        if not self.msg_enabled():
            return

        st_kwargs = self._stream_kwargs(default_kwargs=kwargs)
        with self.configure_colors(**st_kwargs):
            tty.info(*args, **st_kwargs)

    def verbose(self, *args, **kwargs):
        """Print a verbose message to the active log

        Pass all args and kwargs to tty.verbose (which will concatenate and
        print). Perform this action for the active log only.
        """
        if self.is_verbose():
            st_kwargs = self._stream_kwargs(default_kwargs=kwargs)
            with self.configure_colors(**st_kwargs):
                tty.verbose(*args, **st_kwargs)

    def warn(self, *args, **kwargs):
        """Print a warning message to the active log

        Pass all args and kwargs to tty.warn (which will concatenate and
        print). Perform this action for the active log only.
        """
        if not self.warn_enabled():
            return

        st_kwargs = self._stream_kwargs(default_kwargs=kwargs)
        if self._aggregated_warnings:
            if "stream" in st_kwargs:
                file_name = st_kwargs["stream"].name
                if file_name not in self.file_warnings:
                    self.file_warnings[file_name] = []
                self.file_warnings[file_name].append((args, kwargs))
            else:
                self.global_warnings.append((args, kwargs))

        else:
            if "stream" in st_kwargs:
                with self.configure_colors(**st_kwargs):
                    tty.warn(*args, **st_kwargs)

            tty.warn(*args, **kwargs)

    def all_warnings(self):
        """Print all warnings that have been encountered

        This is intended to be called once, and will print all warnings that
        were encountered over the course of the execution.
        """

        if self._aggregated_warnings:
            if self.file_warnings:
                for file_name, warnings in self.file_warnings.items():
                    suffix = "s" if len(warnings) > 1 else ""
                    tty.info("")
                    tty.info(f"File {file_name} encountered {len(warnings)} warning{suffix}.")
                    for args, kwargs in warnings:
                        tty.warn(*args, **kwargs)

            if self.global_warnings:
                suffix = "s" if len(self.global_warnings) > 1 else ""
                tty.info("")
                tty.info(f"Encountered {len(self.global_warnings)} global warning{suffix}.")
                for args, kwargs in self.global_warnings:
                    tty.warn(*args, **kwargs)

    def debug(self, *args, **kwargs):
        """Print a debug message to the active log

        Pass all args and kwargs to tty.debug (which will concatenate and
        print). Perform this action for the active log only.
        """
        if self.debug_level():
            st_kwargs = self._stream_kwargs(default_kwargs=kwargs)
            with self.configure_colors(**st_kwargs):
                tty.debug(*args, **st_kwargs)

    def error(self, *args, **kwargs):
        """Print an error message

        Pass all args and kwargs to tty.error (which will concatenate and
        print). Perform this action all logs, and the default stream (print to
        screen).
        """
        for idx, _ in enumerate(self.log_stack):
            st_kwargs = self._stream_kwargs(index=idx, default_kwargs=kwargs)
            with self.configure_colors(**st_kwargs):
                tty.error(*args, **st_kwargs)

        tty.error(*args, **kwargs)

    def die(self, *args, **kwargs):
        """Print an error message and terminate execution

        Pass all args and kwargs to tty.error (which will concatenate and
        print). Perform this action all logs. After all logs are printed to,
        terminate execution (and error) using tty.die.
        """
        for idx, _ in enumerate(self.log_stack):
            st_kwargs = self._stream_kwargs(index=idx, default_kwargs=kwargs)
            with self.configure_colors(**st_kwargs):
                tty.error(*args, **st_kwargs)

        while self.log_stack:
            self.remove_log()

        tty.die(*args, **kwargs)


logger = Logger()
