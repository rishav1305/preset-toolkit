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

### Preflight Check (1 Bash call)

Verify venv, playwright, and config all exist. Do NOT install anything.

```bash
test -f .venv/bin/python3 && .venv/bin/python3 -c "from playwright.async_api import async_playwright; print('PLAYWRIGHT_OK')" && test -f .preset-toolkit/config.yaml && echo "PREFLIGHT_OK" || echo "PREFLIGHT_FAILED"
```

If `PREFLIGHT_FAILED`: Stop and tell the user: "Dependencies missing. Run `/preset-toolkit:preset-setup` to install them."

### Check Storage State

```bash
test -f .preset-toolkit/.secrets/storage_state.json && echo "SESSION_EXISTS" || echo "NO_SESSION"
```

- If `SESSION_EXISTS`: Use existing session for headless capture.
- If `NO_SESSION` or `login` argument provided: Run interactive login first.

## Execution Steps

Find the plugin root for PYTHONPATH:
```bash
PLUGIN_ROOT=$(find ~/.claude/plugins -path "*/preset-toolkit/*/scripts/screenshot.py" -print -quit 2>/dev/null | sed 's|/scripts/screenshot.py||')
```

### Step 1: Interactive Login (if needed)

If no storage state exists or the user passed `login`:

Tell the user:
```
Opening browser for Preset login.
Log in with your credentials — the browser will stay open for up to 5 minutes.
Once you're on the dashboard, the screenshot will be captured automatically.
```

```bash
source .venv/bin/activate && PYTHONPATH="${PLUGIN_ROOT}:${PYTHONPATH:-}" .venv/bin/python3 -c "
from scripts.screenshot import capture_sync
from scripts.config import ToolkitConfig
from pathlib import Path

config = ToolkitConfig.discover()
output_dir = Path('screenshots')
result = capture_sync(config, output_dir=output_dir, headless=False)
if result.success:
    print(f'Full page: {result.full_page}')
    for chart_id, path in result.sections.items():
        print(f'Section: chart-{chart_id} -> {path}')
    print(f'Sections captured: {len(result.sections)}')
else:
    print(f'FAILED: {result.error}')
"
```

After login, the storage state is saved automatically for future headless runs.

### Step 2: Headless Capture (if session exists)

```bash
source .venv/bin/activate && PYTHONPATH="${PLUGIN_ROOT}:${PYTHONPATH:-}" .venv/bin/python3 -c "
from scripts.screenshot import capture_sync
from scripts.config import ToolkitConfig
from pathlib import Path

config = ToolkitConfig.discover()
output_dir = Path('screenshots')
storage_state = Path('.preset-toolkit/.secrets/storage_state.json')
result = capture_sync(
    config,
    output_dir=output_dir,
    storage_state=storage_state,
    headless=True,
)
if result.success:
    print(f'Full page: {result.full_page}')
    for chart_id, path in result.sections.items():
        print(f'Section: chart-{chart_id} -> {path}')
    print(f'Sections captured: {len(result.sections)}')
else:
    print(f'FAILED: {result.error}')
"
```

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

If the capture failed:

```
Screenshot capture failed: <error message>

Try running with `login` to refresh your session:
  /preset-toolkit:preset-screenshot login
```

## Error Recovery

| Symptom | Cause | Fix |
|---|---|---|
| PREFLIGHT_FAILED | Setup not run | Run `/preset-toolkit:preset-setup` |
| "Navigation failed" | Session expired or network issue | Run `/preset-toolkit:preset-screenshot login` |
| "Login timed out" | Browser closed or login took too long | Run again, complete login within 5 minutes |
| Empty screenshots | Page not fully loaded | Increase `screenshots.wait_seconds` in config |
| Missing chart sections | Charts not visible or collapsed | Expand dashboard sections before capture |
