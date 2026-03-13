---
name: preset-testing
description: "Preset TDD loop: make change, validate, push, pull-back verify, screenshot diff"
---

# Testing (Preset TDD Loop)

Run the full test-driven development loop for Preset dashboard changes: make a change, validate it locally, push, pull back to verify, and screenshot-diff against baseline.

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

## The TDD Loop

Each change goes through all 8 stages. No stage can be skipped.

### Stage 1: Make Change

Apply the local edit to the relevant YAML file(s). Use the safe YAML edit pattern for dataset SQL changes:

```python
# Safe pattern: read raw -> yaml.safe_load -> modify -> raw string replace -> write
import yaml

with open(yaml_path) as f:
    raw = f.read()
data = yaml.safe_load(raw)
sql = data.get("sql", "")

# Verify pattern exists exactly N times
old_pattern = "old text"
count = sql.count(old_pattern)
assert count > 0, f"Pattern not found: {old_pattern}"

new_sql = sql.replace(old_pattern, "new text")
new_raw = raw.replace(sql, new_sql)

with open(yaml_path, "w") as f:
    f.write(new_raw)
```

For chart YAML changes, direct editing is safe. For CSS changes, edit the `css` field in the dashboard YAML.

### Stage 2: Validate

```bash
sup sync validate <sync_folder>
```

- PASS: Continue to Stage 3.
- FAIL: Fix the YAML error and retry Stage 1.

### Stage 3: Check Markers

```python
from scripts.fingerprint import check_markers
from pathlib import Path

markers_file = Path(config.get("validation.markers_file", ".preset-toolkit/markers.txt"))
assets = Path(config.sync_folder) / "assets"

for ds in (assets / "datasets").rglob("*.yaml"):
    result = check_markers(ds, markers_file)
    if not result.all_present:
        print(f"FAIL: Missing markers in {ds.name}: {result.missing}")
        # Fix and retry from Stage 1
```

- PASS: Continue to Stage 4.
- FAIL: The edit removed required content. Fix and retry.

### Stage 4: Dry-Run

```bash
sup sync run <sync_folder> --push-only --dry-run --force
```

Review the dry-run output to confirm only expected changes will be pushed.

- Expected changes: Continue to Stage 5.
- Unexpected changes: Investigate before proceeding.

### Stage 5: Push

Push all changes to Preset. This runs the two-step push:

1. `sup sync run <sync_folder> --push-only --force` -- datasets and charts.
2. CSS/position via REST API -- to restore CSS that sup sync overwrites.

```python
from scripts.sync import push

result = push(config, css_only=False, sync_only=False)
if not result.success:
    print(f"Push failed: {result.error}")
    # Fix and retry
```

### Stage 6: Pull-Back Verify

Pull from Preset and verify the push landed correctly:

```bash
sup sync run <sync_folder> --pull-only --force
```

Then check markers again:

```python
for ds in (assets / "datasets").rglob("*.yaml"):
    result = check_markers(ds, markers_file)
    if not result.all_present:
        print("WARNING: Post-push verification failed")
        print(f"Missing markers: {result.missing}")
```

- All markers present: Continue to Stage 7.
- Markers missing: The push was partially overwritten or stale. Investigate (likely CSS overwrite or Preset cache).

### Stage 7: Fingerprint Save + Verify

```python
from scripts.fingerprint import compute_fingerprint, save_fingerprint

dataset_yamls = list((assets / "datasets").rglob("*.yaml"))
if dataset_yamls:
    fp = compute_fingerprint(dataset_yamls[0])
    fp_file = Path(config.get("validation.fingerprint_file", ".preset-toolkit/.last-push-fingerprint"))
    save_fingerprint(fp, fp_file)
    print(f"Fingerprint saved: {fp}")
```

### Stage 8: Screenshot + Visual Diff

Capture a screenshot and compare against baseline:

```python
from scripts.screenshot import capture_sync
from scripts.visual_diff import compare_images

# Capture
screenshot_dir = Path(".preset-toolkit/screenshots/test")
capture_result = capture_sync(config, output_dir=screenshot_dir)

# Diff against baseline
baseline_dir = Path(config.get("visual_regression.baseline_dir", ".preset-toolkit/baselines"))
threshold = config.get("visual_regression.threshold", 0.01)

if capture_result.full_page and (baseline_dir / "full-page.png").exists():
    diff = compare_images(
        baseline=baseline_dir / "full-page.png",
        current=capture_result.full_page,
        threshold=threshold,
    )
    if diff.passed:
        print(f"Visual: PASS ({diff.diff_ratio:.2%} diff)")
    else:
        print(f"Visual: CHANGED ({diff.diff_ratio:.2%} diff) -- review screenshot")
```

Report:
```
TDD Loop Complete

  Stage 1: Change applied .............. PASS
  Stage 2: Validation .................. PASS
  Stage 3: Markers ..................... PASS (X/X)
  Stage 4: Dry-run ..................... PASS
  Stage 5: Push ........................ PASS
  Stage 6: Pull-back verify ........... PASS
  Stage 7: Fingerprint ................ Saved (<hash>)
  Stage 8: Visual ..................... PASS (0.02% diff)

  All stages passed. Change is verified.
```

## After a Successful Loop

1. **Git commit:**
   ```bash
   git add <sync_folder>/
   git commit -m "Sync: <description>"
   ```

2. **Update baselines (if visual change was intentional):**
   Copy current screenshots to baseline directory.

## Quick TDD for CSS-Only Changes

For pure CSS changes that do not affect datasets or charts:

```
Stages: 1 (edit CSS) -> 2 (validate) -> 5 (push --css-only) -> 8 (screenshot)
```

Stages 3 (markers), 4 (dry-run), 6 (pull-back), and 7 (fingerprint) can be skipped for CSS-only changes since CSS is pushed via REST API and does not affect dataset content.
