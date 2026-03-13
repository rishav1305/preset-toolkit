---
name: preset-checkpoint
description: "Daily checkpoint: pull, validate, screenshot, visual diff, and generate summary report"
---

# Daily Checkpoint

Orchestrate the full daily checkpoint workflow: pull latest state, validate integrity, capture screenshots, run visual regression, and generate a summary report. This is the primary review workflow.

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

## Prerequisites

```python
from scripts.config import ToolkitConfig
config = ToolkitConfig.discover()
```

## Execution Steps

### Step 1: Pull Latest

Invoke the `preset-sync-pull` skill to pull, dedup, and verify.

```python
from scripts.sync import pull
pull_result = pull(config)
```

If the pull fails, note the failure but continue with the remaining steps using the local state.

If markers are missing after pull, warn:
```
WARNING: Pull returned stale data (missing markers). Using local state for remaining checks.
```

### Step 2: Validate

Invoke the `preset-validate` skill to run health checks.

```python
from scripts.sync import validate
val_result = validate(config)
```

Record: validation status, marker status, fingerprint comparison.

### Step 3: Capture Screenshots

Invoke the `preset-screenshot` skill to capture current state.

```python
from scripts.screenshot import capture_sync
from pathlib import Path
from datetime import date

today = date.today().isoformat()
output_dir = Path(f".preset-toolkit/screenshots/{today}")
screenshot_result = capture_sync(config, output_dir=output_dir)
```

### Step 4: Visual Regression

Invoke the `preset-visual-regression` skill to compare against baselines.

```python
from scripts.visual_diff import compare_images

baseline_dir = Path(config.get("visual_regression.baseline_dir", ".preset-toolkit/baselines"))
threshold = config.get("visual_regression.threshold", 0.01)

regression_results = {}
for baseline_img in baseline_dir.glob("*.png"):
    current_img = output_dir / baseline_img.name
    if current_img.exists():
        diff = compare_images(baseline_img, current_img, threshold=threshold)
        regression_results[baseline_img.stem] = diff
```

### Step 5: Ownership Scan

Check for any uncommitted changes and their ownership implications:

```python
from scripts.ownership import OwnershipMap

ownership_file = Path(".preset-toolkit/ownership.yaml")
if ownership_file.exists():
    omap = OwnershipMap.load(ownership_file)
    # Check uncommitted changes
    check = omap.check(user_email=config.user_email, changed_charts=..., changed_datasets=...)
```

### Step 6: Generate Report

Compile all results into a daily checkpoint report:

```
Daily Checkpoint Report -- YYYY-MM-DD

1. PULL STATUS
   Result: Success / Failed (error message)
   Files pulled: X
   Duplicates removed: X

2. HEALTH CHECK
   Validation: PASS / FAIL
   Markers: X/Y present
   Fingerprint: <hash> (matches / changed / no baseline)
   CSS Length: XXXX chars

3. SCREENSHOTS
   Full page: .preset-toolkit/screenshots/YYYY-MM-DD/full-page.png
   Sections: X captured

4. VISUAL REGRESSION
   Threshold: 1.0%
   Results:
     full-page:   0.02% PASS
     chart-2084:  0.00% PASS
     chart-2087:  3.45% FAIL
   Summary: X passed, Y failed

5. OWNERSHIP
   Warnings: None / X advisory warnings

OVERALL STATUS: HEALTHY / ISSUES FOUND
```

### Step 7: Decision Point

If there are visual regressions or issues:

```
Issues found during checkpoint:
  - Visual regression in chart-2087 (3.45% diff)
  - Fingerprint changed since last push

What would you like to do?
  1. Investigate the regressions
  2. Accept changes and update baselines
  3. Push a fix
```

If everything is healthy:

```
All checks passed. Dashboard is healthy.

Anything you'd like to change today?
```

## Staging/Production Split

If the project uses a staging/production split (detected from config or separate dashboard IDs):

```
Staging dashboard is healthy.

Promote staging changes to production? (yes/no)
```

This is the only time the "promote to production" question is asked.
