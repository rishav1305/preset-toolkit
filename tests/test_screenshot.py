"""Tests for screenshot module."""
from scripts.screenshot import ScreenshotResult


def test_screenshot_result_dataclass():
    """ScreenshotResult should be constructable with defaults."""
    r = ScreenshotResult()
    assert r.full_page is None
    assert r.sections == {}
    assert r.error == ""


def test_screenshot_result_with_error():
    """ScreenshotResult with error should report it."""
    r = ScreenshotResult(error="Navigation timeout")
    assert r.error == "Navigation timeout"
    assert r.full_page is None
