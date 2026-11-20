# Copyright 2022-2026 The Ramble Authors
#
# Licensed under the Apache License, Version 2.0 <LICENSE-APACHE or
# https://www.apache.org/licenses/LICENSE-2.0> or the MIT license
# <LICENSE-MIT or https://opensource.org/licenses/MIT>, at your
# option. This file may not be copied, modified, or distributed
# except according to those terms.

import os
from unittest.mock import patch

import pytest

from ramble.util.logger import Logger


@pytest.fixture
def logger():
    return Logger()


def test_aggregate_warnings(logger):
    """Test that warnings are aggregated when aggregate_warnings is on."""
    logger.aggregate_warnings(on=True)
    with patch("ramble.util.logger.tty.warn") as mock_warn:
        logger.warn("This is a warning")
        mock_warn.assert_not_called()
    assert len(logger.global_warnings) == 1


def test_suppress_warnings(logger):
    """Test that warnings are not printed when suppress_warnings is on."""
    logger.aggregate_warnings(on=True)
    with patch("ramble.util.logger.tty.warn") as mock_warn:
        logger.warn("This is a warning")
        # In suppress mode, all_warnings is not called, so we don't call it
    mock_warn.assert_not_called()


def test_print_aggregated_warnings(logger):
    """Test that warnings are printed at the end."""
    logger.aggregate_warnings(on=True)
    with patch("ramble.util.logger.tty.warn") as mock_warn:
        logger.warn("This is a global warning")
        with open("test.log", "w", encoding="utf-8") as f:
            logger.warn("This is a file warning", stream=f)

        logger.all_warnings()

        mock_warn.assert_any_call("This is a global warning")
        mock_warn.assert_any_call("This is a file warning", stream=f)
    os.remove("test.log")


def test_print_warnings_immediately(logger):
    """Test that warnings are printed immediately when aggregate_warnings is off."""
    logger.aggregate_warnings(on=False)
    with patch("ramble.util.logger.tty.warn") as mock_warn:
        logger.warn("This is a warning")
        mock_warn.assert_called_with("This is a warning")


def test_add_log_context(logger, tmpdir):
    """Test basic functionality of add_log_context."""
    log_path = os.path.join(tmpdir, "test.log")
    assert len(logger.log_stack) == 0

    with logger.add_log_context(log_path):
        assert len(logger.log_stack) == 1
        assert logger.log_stack[-1][0] == log_path

    assert len(logger.log_stack) == 0


def test_add_log_context_exception(logger, tmpdir):
    """Test that log is removed even if an exception occurs."""
    log_path = os.path.join(tmpdir, "test.log")
    assert len(logger.log_stack) == 0

    try:
        with logger.add_log_context(log_path):
            assert len(logger.log_stack) == 1
            raise RuntimeError("Something went wrong")
    except RuntimeError:
        pass

    assert len(logger.log_stack) == 0


def test_add_log_context_unbalanced_nested(logger, tmpdir):
    """Test that a warning is issued if the log to be removed is not active."""
    log_path1 = os.path.join(tmpdir, "test1.log")
    log_path2 = os.path.join(tmpdir, "test2.log")

    assert len(logger.log_stack) == 0

    with patch("ramble.util.logger.tty.warn") as mock_warn:
        with logger.add_log_context(log_path1):
            # Manually add another log inside without removing it
            logger.add_log(log_path2)
            assert len(logger.log_stack) == 2

        mock_warn.assert_called_once()
        assert "is no longer the active log" in mock_warn.call_args[0][0]

        # Both logs should still be in the stack
        assert len(logger.log_stack) == 2
        assert logger.log_stack[0][0] == log_path1
        assert logger.log_stack[1][0] == log_path2

    # Clean up
    logger.remove_log()
    logger.remove_log()


def test_configure_colors_exception_cleanup(logger):
    import llnl.util.tty.color as color

    old_color_setting = color._force_color
    try:
        color.set_color_when(True)
        with pytest.raises(RuntimeError):
            with logger.configure_colors(stream=object()):
                assert color.get_color_when() is False
                raise RuntimeError("test error")
        assert color.get_color_when() is True
    finally:
        color.set_color_when(old_color_setting)


def test_suppress_output(logger):
    """Test that suppress_output suppresses messages and warnings and restores state."""
    assert logger.msg_enabled() is True
    assert logger.warn_enabled() is True
    assert logger.error_enabled() is True

    with patch("ramble.util.logger.tty.info") as mock_info, patch(
        "ramble.util.logger.tty.msg"
    ) as mock_msg, patch("ramble.util.logger.tty.warn") as mock_warn, patch(
        "ramble.util.logger.tty.error"
    ) as mock_error:
        with logger.suppress_output():
            assert logger.msg_enabled() is False
            assert logger.warn_enabled() is False
            assert logger.error_enabled() is True

            logger.msg("suppressed msg")
            logger.info("suppressed info")
            logger.all_msg("suppressed all_msg")
            logger.warn("suppressed warn")
            logger.error("visible error")

        mock_info.assert_not_called()
        mock_msg.assert_not_called()
        mock_warn.assert_not_called()
        mock_error.assert_called_once_with("visible error")

    assert logger.msg_enabled() is True
    assert logger.warn_enabled() is True
    assert logger.error_enabled() is True


def test_suppress_output_exception_cleanup(logger):
    """Test that suppress_output restores state when an exception is raised."""
    with pytest.raises(RuntimeError):
        with logger.suppress_output(msg_enabled=False, warn_enabled=False, error_enabled=False):
            assert logger.msg_enabled() is False
            assert logger.warn_enabled() is False
            assert logger.error_enabled() is False
            raise RuntimeError("boom")

    assert logger.msg_enabled() is True
    assert logger.warn_enabled() is True
    assert logger.error_enabled() is True


def test_suppress_output_skips_aggregated_warnings(logger):
    """Test that warnings are not aggregated when warn_enabled is False."""
    logger.aggregate_warnings(on=True)
    with logger.suppress_output(warn_enabled=False):
        logger.warn("ignored warning")
    assert logger.global_warnings == []


def test_screen_msg_bypasses_log_stack(logger, tmpdir):
    """Test that screen_msg writes only to screen and not active log files."""
    log_path = os.path.join(tmpdir, "screen_msg.log")
    with logger.add_log_context(log_path):
        with patch("ramble.util.logger.tty.msg") as mock_tty_msg:
            logger.screen_msg("screen only")
            mock_tty_msg.assert_called_once_with("screen only")

        logger.msg("logged message")

    with open(log_path, encoding="utf-8") as f:
        content = f.read()
    assert "screen only" not in content
    assert "logged message" in content


def test_get_yes_or_no(logger):
    """Test that get_yes_or_no delegates to tty.get_yes_or_no."""
    with patch("ramble.util.logger.tty.get_yes_or_no", return_value=True) as mock_prompt:
        assert logger.get_yes_or_no("Continue?", default=False) is True
        mock_prompt.assert_called_once_with("Continue?", default=False)


def test_logger_tty_settings(logger):
    """Test verbose, debug, stacktrace, timestamp, and enable/disable setters."""
    old_verbose = logger.is_verbose()
    old_debug = logger.debug_level()
    old_msg = logger.msg_enabled()
    old_warn = logger.warn_enabled()
    old_error = logger.error_enabled()
    try:
        logger.set_verbose(True)
        assert logger.is_verbose() is True
        logger.set_verbose(False)
        assert logger.is_verbose() is False

        logger.set_debug(2)
        assert logger.debug_level() == 2
        assert logger.is_debug(1) is True
        assert logger.is_debug(2) is True
        assert logger.is_debug(3) is False
        logger.set_debug(0)
        assert logger.is_debug() is False

        logger.set_msg_enabled(False)
        assert logger.msg_enabled() is False
        logger.set_warn_enabled(False)
        assert logger.warn_enabled() is False
        logger.set_error_enabled(False)
        assert logger.error_enabled() is False

        with patch("ramble.util.logger.tty.set_stacktrace") as mock_st, patch(
            "ramble.util.logger.tty.set_timestamp"
        ) as mock_ts:
            logger.set_stacktrace(True)
            logger.set_timestamp(True)
            mock_st.assert_called_once_with(True)
            mock_ts.assert_called_once_with(True)
    finally:
        logger.set_verbose(old_verbose)
        logger.set_debug(old_debug)
        logger.set_msg_enabled(old_msg)
        logger.set_warn_enabled(old_warn)
        logger.set_error_enabled(old_error)
