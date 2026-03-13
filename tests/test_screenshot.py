"""Tests for screenshot module."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.screenshot import ScreenshotResult, capture_dashboard
from scripts.config import ToolkitConfig


def _make_screenshot_config(tmp_path):
    import yaml
    config_dir = tmp_path / ".preset-toolkit"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(yaml.safe_dump({
        "version": 1,
        "workspace": {"url": "https://test.preset.io", "id": "w1"},
        "dashboard": {"id": 42, "name": "Test"},
        "screenshots": {"wait_seconds": 1, "sections": True, "mask_selectors": []},
    }))
    return ToolkitConfig.load(config_path)


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


def test_capture_nav_failure_returns_error(tmp_path):
    """Navigation failure should return ScreenshotResult with error, not crash."""
    cfg = _make_screenshot_config(tmp_path)
    output_dir = tmp_path / "screenshots"

    mock_page = AsyncMock()
    mock_page.goto.side_effect = Exception("net::ERR_CONNECTION_REFUSED")

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    mock_pw_cm = AsyncMock()
    mock_pw_cm.__aenter__ = AsyncMock(return_value=mock_playwright)
    mock_pw_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("scripts.screenshot.get_telemetry", return_value=MagicMock(track=MagicMock(), track_error=MagicMock())):
        with patch("scripts.screenshot.async_playwright", return_value=mock_pw_cm, create=True):
            # Patch at the import site
            import scripts.screenshot as ss
            original = None
            try:
                from playwright.async_api import async_playwright as _orig
                original = _orig
            except ImportError:
                pass

            with patch.object(ss, "capture_dashboard", wraps=ss.capture_dashboard):
                # We need to mock the playwright import inside the function
                with patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.async_api": MagicMock(async_playwright=lambda: mock_pw_cm)}):
                    result = asyncio.run(capture_dashboard(cfg, output_dir))

    assert result.error != ""
    assert "Connection" in result.error or "net::" in result.error
    mock_browser.close.assert_called_once()


def test_capture_browser_always_closed(tmp_path):
    """Browser should be closed even when screenshot fails."""
    cfg = _make_screenshot_config(tmp_path)
    output_dir = tmp_path / "screenshots"

    mock_page = AsyncMock()
    mock_page.goto = AsyncMock()  # navigation succeeds
    mock_page.wait_for_timeout = AsyncMock()
    mock_page.screenshot.side_effect = Exception("screenshot failed")
    mock_page.query_selector_all = AsyncMock(return_value=[])

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page
    mock_context.storage_state = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser

    mock_pw_cm = AsyncMock()
    mock_pw_cm.__aenter__ = AsyncMock(return_value=mock_playwright)
    mock_pw_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("scripts.screenshot.get_telemetry", return_value=MagicMock(track=MagicMock(), track_error=MagicMock())):
        with patch.dict("sys.modules", {"playwright": MagicMock(), "playwright.async_api": MagicMock(async_playwright=lambda: mock_pw_cm)}):
            # The screenshot() exception will propagate — browser.close should still be called
            with pytest.raises(Exception, match="screenshot failed"):
                asyncio.run(capture_dashboard(cfg, output_dir))

    mock_browser.close.assert_called_once()
