"""Tests for structured logging module."""
import logging
from scripts.logger import get_logger, set_debug, sanitize, SECRET_PATTERNS


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


# ── Sanitize tests ──


def test_sanitize_redacts_tokens():
    text = "token=abc123secret"
    result = sanitize(text)
    assert "abc123secret" not in result
    assert "[REDACTED]" in result


def test_sanitize_redacts_bearer():
    text = "bearer=eyJhbGciOiJIUzI1Ni"
    result = sanitize(text)
    assert "eyJhbG" not in result
    assert "[REDACTED]" in result


def test_sanitize_redacts_api_key():
    text = "api_key=supersecretkey123"
    result = sanitize(text)
    assert "supersecretkey123" not in result


def test_sanitize_preserves_safe_text():
    text = "This is a normal error message"
    assert sanitize(text) == text


def test_sanitize_truncates():
    text = "x" * 1000
    assert len(sanitize(text, max_length=200)) == 200


def test_sanitize_case_insensitive():
    text = "SECRET=mysecret"
    result = sanitize(text)
    assert "mysecret" not in result
