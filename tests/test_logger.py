"""Tests for structured logging module."""
import logging
from scripts.logger import get_logger, set_debug


def test_get_logger_returns_named_logger():
    log = get_logger("test.module")
    assert log.name == "preset_toolkit.test.module"


def test_default_level_is_info():
    log = get_logger("test.default")
    assert log.getEffectiveLevel() == logging.INFO


def test_set_debug_changes_level():
    log = get_logger("test.debug")
    set_debug(True)
    assert log.level == logging.DEBUG
    set_debug(False)
    assert log.level == logging.INFO


def test_log_output_has_timestamp_and_module(capfd):
    log = get_logger("test.output")
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s [%(name)s] %(levelname)s: %(message)s"))
    log.addHandler(handler)
    log.info("hello")
    captured = capfd.readouterr()
    assert "preset_toolkit.test.output" in captured.err
    assert "hello" in captured.err
    log.removeHandler(handler)
