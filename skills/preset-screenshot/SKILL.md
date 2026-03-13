---
name: preset-screenshot
description: "Capture full-page and per-section dashboard screenshots using Playwright"
---

# Screenshot

Capture full-page and per-section screenshots of the Preset dashboard using Playwright. Screenshots are saved locally for review and visual regression tracking.

## Conversation Principles (MANDATORY)

**NEVER ask about:**
- Config formats, file paths, YAML structure, directory layout
- Which scripts to run, CLI flags, sync modes, technical parameters
- Auth methods, tokens, API endpoints, CSRF handling
- Git branches, merge strategies, commit messages
- Infrastructure, server details, environment setup

**ONLY ask about:**
- Business intent: "What change do you want to make?"
- Logic validation: "Revenue = Ads + Subs. Is that correct?"
- Data correctness: "The current value is $3M. Does that look right?"
- Visual specifics: "Should the label say 'X' or 'Y'?"
- Ownership clarity: "This tile is in Bob's section. Notify him?"
- Approval gates: "Here's what changes. Push it?"

## Arguments

- No arguments: Capture headless screenshots using existing session state.
- `login`: Run interactive (non-headless) browser for login, then capture screenshots.
- `YYYY-MM-DD`: Use as a date suffix for the output directory (e.g., `screenshots/2026-03-13/`).

## Prerequisites

```python
from scripts.config import ToolkitConfig
config = ToolkitConfig.discover()
```

### Check Playwright Installation

```bash
python -c "from playwright.async_api import async_playwright; print('OK')" 2>/dev/null || echo "PLAYWRIGHT_NOT_INSTALLED"
```

If not installed:

```bash
pip install playwright
playwright install chromium
```

This requires network access to download the Chromium browser binary.

### Check Storage State

```python
from pathlib import Path

storage_state = config.project_root / ".preset-toolkit" / ".secrets" / "storage_state.json"
has_session = storage_state.exists()
```

- If `has_session` is True: Use existing session for headless capture.
- If `has_session` is False or `login` argument provided: Run interactive login first.

## Execution Steps

### Step 1: Interactive Login (if needed)

If no storage state exists or the user passed `login`:

```python
from scripts.screenshot import capture_sync

result = capture_sync(
    config,
    output_dir=Path(".preset-toolkit/screenshots"),
    headless=False,  # Opens visible browser for login
)
```

Tell the user:
```
Opening browser for Preset login.
Log in with your credentials, then the screenshot will be captured automatically.
```

After login, the storage state is saved automatically for future headless runs.

### Step 2: Headless Capture

```python
from scripts.screenshot import capture_sync
from pathlib import Path

# Determine output directory
output_dir = Path(".preset-toolkit/screenshots")
if date_arg:
    output_dir = output_dir / date_arg

storage_state = config.project_root / ".preset-toolkit" / ".secrets" / "storage_state.json"

result = capture_sync(
    config,
    output_dir=output_dir,
    storage_state=storage_state if storage_state.exists() else None,
    headless=True,
)
```

The capture function:
1. Navigates to the dashboard URL (derived from `config.workspace_url` and `config.dashboard_id`).
2. Waits for the page to fully load (configurable wait time from `config.get("screenshots.wait_seconds")`).
3. Masks dynamic elements (configurable selectors from `config.get("screenshots.mask_selectors")`).
4. Takes a full-page screenshot.
5. Takes per-section screenshots for each chart element (`[data-test-chart-id]`).
6. Saves storage state for future use.

### Step 3: Summary

```
Screenshots Captured

  Output directory: <output_dir>
  Full page: full-page.png
  Sections: X chart screenshots captured
    - chart-2084.png (Audience)
    - chart-2087.png (Activation)
    - chart-2089.png (Engagement)
    ...

  Storage state saved for future headless runs.
```

If the capture failed (e.g., navigation timeout, session expired):

```
Screenshot capture failed: <error message>

Try running with `login` to refresh your session:
  /preset screenshot login
```

## Error Recovery

| Symptom | Cause | Fix |
|---|---|---|
| "Navigation failed" | Session expired or network issue | Run `/preset screenshot login` to re-authenticate |
| "Playwright not installed" | Missing dependency | Run `pip install playwright && playwright install chromium` |
| Empty screenshots | Page not fully loaded | Increase `screenshots.wait_seconds` in config |
| Missing chart sections | Charts not visible or collapsed | Expand dashboard sections before capture |
