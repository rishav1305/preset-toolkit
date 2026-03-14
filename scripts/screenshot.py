"""Dashboard screenshot capture using Playwright Python bindings."""
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from scripts.config import ToolkitConfig
from scripts.logger import get_logger
from scripts.telemetry import get_telemetry

log = get_logger("screenshot")


async def _test_context(playwright, config, dashboard_url, storage_state=None, cookies=None):
    """Create a headless browser + context, navigate, check if authenticated.

    Returns (browser, context, page) if on the dashboard (not login page).
    Closes both browser and context on failure.
    """
    browser = await playwright.chromium.launch(headless=True)
    try:
        context_kwargs = {"viewport": {"width": 1920, "height": 1080}}
        if storage_state:
            context_kwargs["storage_state"] = storage_state
        context = await browser.new_context(**context_kwargs)

        if cookies:
            await context.add_cookies(cookies)

        page = await context.new_page()
        nav_timeout = config.get("screenshots.navigation_timeout", 60) * 1000
        await page.goto(dashboard_url, wait_until="networkidle", timeout=nav_timeout)

        current_url = page.url
        on_login_page = "/login" in current_url or "/superset/welcome" in current_url
        if on_login_page:
            await browser.close()
            return None, None, None

        return browser, context, page
    except Exception as e:
        log.debug("Auth test failed: %s", e)
        await browser.close()
        return None, None, None


async def _try_auth_context(playwright, config, storage_state_path, dashboard_url):
    """Try to get an authenticated Playwright context without user interaction.

    Returns (browser, context, page, method_name) on success.
    Returns (None, None, None, None) on failure.
    Caller is responsible for closing browser on success.
    """
    # Step 1: Try saved storage state
    if storage_state_path and storage_state_path.exists():
        log.debug("Trying saved storage state...")
        browser, context, page = await _test_context(
            playwright, config, dashboard_url,
            storage_state=str(storage_state_path),
        )
        if context:
            return browser, context, page, "storage_state"

    # Step 2: Try browser cookies
    try:
        from urllib.parse import urlparse

        from scripts.browser_cookies import extract_cookies
        domain = urlparse(config.workspace_url).hostname or ""
        cookies = extract_cookies(domain)
        if cookies:
            log.debug("Trying %d browser cookies...", len(cookies))
            browser, context, page = await _test_context(
                playwright, config, dashboard_url, cookies=cookies,
            )
            if context:
                return browser, context, page, "browser_cookies"
    except Exception as e:
        log.debug("Browser cookie extraction failed: %s", e)

    return None, None, None, None


@dataclass
class ScreenshotResult:
    full_page: Optional[Path] = None
    sections: Dict[str, Path] = field(default_factory=dict)
    error: str = ""

    @property
    def success(self) -> bool:
        return not self.error and self.full_page is not None


async def capture_dashboard(
    config: ToolkitConfig,
    output_dir: Path,
    storage_state: Optional[Path] = None,
    headless: bool = True,
) -> ScreenshotResult:
    """Capture full-page and per-section screenshots of a Preset dashboard."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        from scripts.deps import ensure_playwright
        ensure_playwright()
        from playwright.async_api import async_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    result = ScreenshotResult()
    t = get_telemetry(config._path)

    url_pattern = config.get("api.dashboard_url_pattern", "/superset/dashboard/{id}/")
    dashboard_url = f"{config.workspace_url.rstrip('/')}{url_pattern.format(id=config.dashboard_id)}"
    wait_ms = config.get("screenshots.wait_seconds", 15) * 1000
    mask_selectors = config.get("screenshots.mask_selectors", [])

    auth_method = None

    async with async_playwright() as p:
        # --- Auth fallback chain ---
        storage_state_path = storage_state or (
            config.project_root / ".preset-toolkit" / ".secrets" / "storage_state.json"
        )
        browser, context, page, auth_method = await _try_auth_context(
            p, config, storage_state_path, dashboard_url,
        )

        if context:
            log.info("Authenticated via %s", auth_method)
            await page.wait_for_timeout(wait_ms)
        else:
            # Fall back to manual login (original behavior)
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            try:
                nav_timeout = config.get("screenshots.navigation_timeout", 60) * 1000
                await page.goto(dashboard_url, wait_until="networkidle", timeout=nav_timeout)

                login_timeout = 5 * 60 * 1000  # 5 minutes for user to log in
                current_url = page.url
                on_login_page = "/login" in current_url or "/superset/welcome" in current_url
                if on_login_page:
                    log.info("Waiting for login — complete sign-in in the browser...")
                    try:
                        await page.wait_for_url(
                            f"**/dashboard/{config.dashboard_id}/**",
                            timeout=login_timeout,
                        )
                        await page.wait_for_timeout(wait_ms)
                    except Exception:
                        result.error = "Login timed out — browser was closed or login took too long"
                        await browser.close()
                        return result
                else:
                    await page.wait_for_timeout(wait_ms)
            except Exception as e:
                log.error("Dashboard navigation failed: %s", e)
                result.error = f"Navigation failed: {e}"
                await browser.close()
                return result

        try:
            # Mask dynamic elements
            for selector in mask_selectors:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    await el.evaluate("e => { e.style.visibility = 'hidden'; }")

            # Full page screenshot
            full_path = output_dir / "full-page.png"
            await page.screenshot(path=str(full_path), full_page=True)
            result.full_page = full_path

            # Per-section screenshots (by chart ID)
            if config.get("screenshots.sections", True):
                chart_elements = await page.query_selector_all("[data-test-chart-id]")
                for el in chart_elements:
                    chart_id = await el.get_attribute("data-test-chart-id")
                    if chart_id:
                        section_path = output_dir / f"chart-{chart_id}.png"
                        try:
                            await el.screenshot(path=str(section_path))
                            result.sections[chart_id] = section_path
                        except Exception as e:
                            log.debug("Could not capture chart %s: %s", chart_id, e)

            # Save storage state for reuse (only on success)
            if not result.error:
                try:
                    secrets_dir = config.project_root / ".preset-toolkit" / ".secrets"
                    secrets_dir.mkdir(parents=True, exist_ok=True)
                    state_path = secrets_dir / "storage_state.json"
                    await context.storage_state(path=str(state_path))
                except Exception as e:
                    log.debug("Could not save storage state: %s", e)
        finally:
            await browser.close()

    t.track("screenshot_complete", {
        "sections_captured": len(result.sections),
        "has_full_page": result.full_page is not None,
        "has_error": bool(result.error),
        "auth_method": auth_method or "manual_login",
    })
    if result.error:
        t.track_error("screenshot", "capture_failed", result.error)
    return result


def capture_sync(config: ToolkitConfig, output_dir: Path, **kwargs) -> ScreenshotResult:
    """Synchronous wrapper for capture_dashboard."""
    return asyncio.run(capture_dashboard(config, output_dir, **kwargs))
