"""Dashboard screenshot capture using Playwright Python bindings."""
import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from scripts.config import ToolkitConfig


@dataclass
class ScreenshotResult:
    full_page: Optional[Path] = None
    sections: Dict[str, Path] = field(default_factory=dict)
    error: str = ""


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

    dashboard_url = (
        f"{config.workspace_url.rstrip('/')}/superset/dashboard/{config.dashboard_id}/"
    )
    wait_ms = config.get("screenshots.wait_seconds", 15) * 1000
    mask_selectors = config.get("screenshots.mask_selectors", [])

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context_kwargs = {}
        if storage_state and storage_state.exists():
            context_kwargs["storage_state"] = str(storage_state)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            **context_kwargs,
        )
        page = await context.new_page()

        try:
            await page.goto(dashboard_url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(wait_ms)
        except Exception as e:
            result.error = f"Navigation failed: {e}"
            await browser.close()
            return result

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
                    except Exception:
                        pass  # Element may not be visible

        # Save storage state for reuse
        secrets_dir = config.project_root / ".preset-toolkit" / ".secrets"
        secrets_dir.mkdir(parents=True, exist_ok=True)
        state_path = secrets_dir / "storage_state.json"
        await context.storage_state(path=str(state_path))

        await browser.close()

    return result


def capture_sync(config: ToolkitConfig, output_dir: Path, **kwargs) -> ScreenshotResult:
    """Synchronous wrapper for capture_dashboard."""
    return asyncio.run(capture_dashboard(config, output_dir, **kwargs))
