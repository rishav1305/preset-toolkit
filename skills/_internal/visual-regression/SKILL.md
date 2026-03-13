---
name: visual-regression
description: "Visual diff: compare current screenshots against baselines, report pixel-level regressions"
---

# Visual Regression

Compare current dashboard screenshots against stored baselines to detect unintended visual changes. Uses pixel-level comparison with configurable tolerance.

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

### Step 1: Check for Baselines

```python
from pathlib import Path

baseline_dir = Path(config.get("visual_regression.baseline_dir", ".preset-toolkit/baselines"))
has_baselines = baseline_dir.exists() and any(baseline_dir.glob("*.png"))
```

If no baselines exist:
```
No baselines found. Capturing current screenshots as the baseline.
Future diffs will compare against these.
```

Capture current screenshots and copy them to the baseline directory:

```python
from scripts.screenshot import capture_sync
import shutil

# Capture current
temp_dir = Path(".preset-toolkit/screenshots/current")
result = capture_sync(config, output_dir=temp_dir, ...)

# Save as baselines
baseline_dir.mkdir(parents=True, exist_ok=True)
for png in temp_dir.glob("*.png"):
    shutil.copy2(png, baseline_dir / png.name)
```

Report the files saved and stop -- there is nothing to diff against on the first run.

### Step 2: Capture Current Screenshots

If baselines exist, capture a fresh set of screenshots:

```python
from scripts.screenshot import capture_sync

current_dir = Path(".preset-toolkit/screenshots/current")
result = capture_sync(
    config,
    output_dir=current_dir,
    storage_state=config.project_root / ".preset-toolkit" / ".secrets" / "storage_state.json",
    headless=True,
)
```

If capture fails, report the error and stop.

### Step 3: Run Pixel Diff

Compare each baseline image against the corresponding current image:

```python
from scripts.visual_diff import compare_images

threshold = config.get("visual_regression.threshold", 0.01)
diff_dir = Path(".preset-toolkit/screenshots/diffs")
diff_dir.mkdir(parents=True, exist_ok=True)

results = {}
for baseline_img in sorted(baseline_dir.glob("*.png")):
    current_img = current_dir / baseline_img.name
    if not current_img.exists():
        results[baseline_img.stem] = "MISSING -- no current screenshot"
        continue

    diff_result = compare_images(
        baseline=baseline_img,
        current=current_img,
        threshold=threshold,
        diff_output=diff_dir / f"diff-{baseline_img.name}",
        color_tolerance=35,
    )
    results[baseline_img.stem] = diff_result
```

### Step 4: Report Results

```
Visual Regression Report

  Threshold: 1.0% pixel difference

  Section               Diff Ratio    Status
  --------------------  ----------    ------
  full-page             0.02%         PASS
  chart-2084            0.00%         PASS
  chart-2087            3.45%         FAIL
  chart-2089            0.12%         PASS
  chart-2090            0.00%         PASS

  Summary: 4 passed, 1 failed

  Failed sections:
    chart-2087 (Activation): 3.45% pixel diff
      Diff image: .preset-toolkit/screenshots/diffs/diff-chart-2087.png
```

### Step 5: Handle Failures

If any section fails the threshold check, ask:

```
Visual changes detected in 1 section. Are these changes intentional?

  - chart-2087: 3.45% pixel diff (Activation section)

If yes, I'll update the baselines with the current screenshots.
If no, investigate what changed before proceeding.
```

- If the user confirms the changes are intentional: Copy current screenshots to baselines, replacing the old ones.
- If the user says no: Suggest investigating with `/preset troubleshoot` or reviewing the specific chart YAML.

### Step 6: Update Baselines (if approved)

```python
import shutil

for baseline_img in baseline_dir.glob("*.png"):
    current_img = current_dir / baseline_img.name
    if current_img.exists():
        shutil.copy2(current_img, baseline_img)

# Also copy any new screenshots that don't have baselines yet
for current_img in current_dir.glob("*.png"):
    if not (baseline_dir / current_img.name).exists():
        shutil.copy2(current_img, baseline_dir / current_img.name)
```

## Using the Agent

For batch processing across many screenshots, you can delegate to the `visual-diff-agent`:

```
Invoke agents/visual-diff-agent with:
  baseline_dir: .preset-toolkit/baselines
  current_dir: .preset-toolkit/screenshots/current
```

See `agents/visual-diff-agent.md` for the agent specification.

## Error Recovery

| Symptom | Cause | Fix |
|---|---|---|
| Size mismatch | Viewport changed or page layout shifted | Recapture with consistent viewport (1920x1080) |
| High diff on all sections | Session expired, login page captured | Re-authenticate with `/preset screenshot login` |
| Diff images are all black | Baseline images corrupted | Delete baselines, re-capture with `/preset diff` |
