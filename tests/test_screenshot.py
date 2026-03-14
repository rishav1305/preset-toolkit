"""Tests for screenshot module."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.screenshot import ScreenshotResult, _try_auth_context, capture_dashboard
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
    assert r.success is False  # no full_page yet


def test_screenshot_result_success():
    """ScreenshotResult.success should be True when full_page is set and no error."""
    r = ScreenshotResult(full_page=Path("/tmp/full.png"))
    assert r.success is True
    r_err = ScreenshotResult(full_page=Path("/tmp/full.png"), error="oops")
    assert r_err.success is False


def test_screenshot_result_with_error():
    """ScreenshotResult with error should report it."""
    r = ScreenshotResult(error="Navigation timeout")
    assert r.error == "Navigation timeout"
    assert r.full_page is None
    assert r.success is False


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


# ── Auth fallback chain tests ────────────────────────────────────────


def test_try_auth_context_uses_storage_state_first(tmp_path):
    """When storage_state.json exists and works, use it."""
    cfg = _make_screenshot_config(tmp_path)
    state_path = tmp_path / ".preset-toolkit" / ".secrets" / "storage_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text('{"cookies": []}')

    mock_page = AsyncMock()
    mock_page.url = "https://test.preset.io/superset/dashboard/42/"  # not a login page
    mock_page.goto = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    dashboard_url = "https://test.preset.io/superset/dashboard/42/"
    result = asyncio.run(_try_auth_context(mock_pw, cfg, state_path, dashboard_url))
    browser, context, page, method = result
    assert method == "storage_state"
    assert context is not None


def test_try_auth_context_falls_through_to_manual(tmp_path):
    """When both storage state and cookies fail, return None."""
    cfg = _make_screenshot_config(tmp_path)
    state_path = tmp_path / "nonexistent_state.json"  # doesn't exist

    with patch("scripts.browser_cookies.extract_cookies", return_value=[]):
        dashboard_url = "https://test.preset.io/superset/dashboard/42/"
        result = asyncio.run(_try_auth_context(AsyncMock(), cfg, state_path, dashboard_url))
    browser, context, page, method = result
    assert browser is None
    assert method is None


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
