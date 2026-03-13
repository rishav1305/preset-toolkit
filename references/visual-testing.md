# Visual Regression Testing Guide

## Overview

Visual testing captures screenshots of the dashboard and compares them against
known-good baselines. This catches regressions that are invisible to YAML
parsing or marker checks — layout shifts, broken styles, missing tiles, or
data rendering issues.

## Screenshot Capture

### Technology Stack

- **Playwright** (Python) for browser automation
- **Chromium** in headless mode
- **Viewport:** 1920x1080 (standard desktop resolution)

### Waiting for Data

Superset dashboards load charts asynchronously. The page may appear "ready"
while charts are still fetching data. A robust wait strategy:

1. Wait for `networkidle` (no pending network requests for 500ms).
2. Add an explicit wait of 10-15 seconds after networkidle.
3. Optionally, poll for specific DOM elements that indicate charts have
   rendered (e.g., `.chart-container svg` or table rows).

```python
# Wait for dashboard to finish loading
await page.wait_for_load_state('networkidle')
await page.wait_for_timeout(12000)  # 12s buffer for slow charts
```

### Masking Dynamic Content

Dashboard elements that change between captures must be hidden or masked
to prevent false-positive diffs:

```python
# Hide dynamic elements before screenshot
await page.evaluate("""
    // Hide the filter bar (date changes between runs)
    document.querySelectorAll('.filter-scope-container, .dashboard-header')
        .forEach(el => el.style.visibility = 'hidden');

    // Hide loading spinners if any remain
    document.querySelectorAll('.loading-image, .spinner')
        .forEach(el => el.style.display = 'none');

    // Hide timestamps and "last refreshed" indicators
    document.querySelectorAll('.header-with-actions .last-saved')
        .forEach(el => el.style.visibility = 'hidden');
""")
```

Elements to consider masking:
- Dashboard header (title, last-saved timestamp)
- Filter bar (selected date values)
- "Last updated" timestamps on individual charts
- Any animation or transition in progress

### Freezing the Dashboard Date

For deterministic captures, set a fixed "As Of" date using the dashboard's
native filter. This ensures the same data appears in every screenshot run,
regardless of when the capture happens.

Apply the filter via URL parameter or by interacting with the filter component
programmatically before capturing.

## Baseline Management

### Initial Baseline

On the first run (or after intentional changes), screenshots become the new
baseline:

```
.preset-toolkit/
  baselines/
    full-dashboard.png       # Full-page capture
    chart-2103.png           # Individual chart captures
    chart-2085.png
    ...
```

### Comparison Flow

1. **Capture** current screenshots into a temp directory.
2. **Compare** each screenshot against its baseline using pixel diff.
3. **Report** differences:
   - If diff percentage <= threshold (default 1%): PASS
   - If diff percentage > threshold: FLAG as potential regression
4. **Generate** a diff image highlighting changed pixels for review.

### Approving Changes

When a visual change is intentional (e.g., you restyled a chart or renamed a
label), update the baseline:

```bash
/preset diff approve
```

This copies the current screenshots to the baselines directory, making them
the new reference point.

## Pixel Comparison

### Algorithm

Use Euclidean RGB distance for each pixel pair:

```python
distance = sqrt((r1-r2)^2 + (g1-g2)^2 + (b1-b2)^2)
```

A pixel pair is "different" if `distance > tolerance`.

### Color Tolerance

Default tolerance: **35** (on a 0-441 scale, where 441 = max distance between
black and white).

This tolerance accounts for:
- Anti-aliasing differences between captures (font rendering varies slightly)
- Sub-pixel rendering differences
- Minor color interpolation differences in charts

A tolerance of 35 ignores subtle rendering noise while catching meaningful
color changes (e.g., a blue bar turning red, or text disappearing).

### Diff Percentage

```
diff_pct = (pixels_different / total_pixels) * 100
```

Threshold recommendations:
- **< 0.1%**: Identical for practical purposes (rendering noise only)
- **0.1% - 1.0%**: Minor differences — likely anti-aliasing or font changes
- **1.0% - 5.0%**: Noticeable changes — review the diff image
- **> 5.0%**: Significant change — likely a layout shift or content change

Default threshold: **1%** — flags anything above this for human review.

## Per-Section Screenshots

Capture each chart individually for targeted diffing. This isolates which
specific chart changed rather than flagging the entire dashboard.

```python
# Find all chart containers
charts = await page.query_selector_all('[data-test-chart-id]')

for chart in charts:
    chart_id = await chart.get_attribute('data-test-chart-id')
    await chart.screenshot(path=f'screenshots/chart-{chart_id}.png')
```

Benefits:
- Pinpoints exactly which chart has a regression
- Smaller images = faster comparison
- Can set different thresholds per chart (e.g., stricter for KPI tiles)

## Full-Page Capture

In addition to per-chart captures, take a full-page screenshot for overall
layout validation:

```python
await page.screenshot(path='screenshots/full-dashboard.png', full_page=True)
```

This catches:
- Layout shifts (tiles moved or resized)
- Missing tiles (deleted or failed to render)
- Spacing/padding changes between sections
- Filter bar or header changes

## Session State and Authentication

Preset dashboards require authentication. Use Playwright's storage state
feature to persist login across screenshot runs:

1. **One-time interactive login:**
   ```python
   browser = await playwright.chromium.launch(headless=False)
   # Log in manually through the UI
   context.storage_state(path='.secrets/preset_storage_state.json')
   ```

2. **Subsequent headless runs:**
   ```python
   context = await browser.new_context(
       storage_state='.secrets/preset_storage_state.json'
   )
   ```

Storage state files contain session cookies. Store them in `.secrets/`
(gitignored) and never commit them.

## CI Integration

For automated regression testing in CI:

1. Store baseline screenshots as artifacts (or in a dedicated branch).
2. On each push, capture new screenshots and compare.
3. If diff > threshold, fail the check and attach the diff images.
4. Reviewer approves or investigates the visual change.

Note: Headless Chrome rendering can differ slightly between OS environments.
Pin the Chromium version and run comparisons on the same OS to avoid
false positives from platform rendering differences.
