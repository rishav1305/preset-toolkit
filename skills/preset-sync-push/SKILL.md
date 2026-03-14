---
name: preset-sync-push
description: "Validate, check markers, dry-run, and push dashboard changes to Preset with approval gate"
---

# Sync Push

Validate and push local changes to Preset. This is a gated workflow: validation and marker checks must pass before pushing, and the user must approve the push after seeing the dry-run summary.

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

- `--css-only` -- Only push CSS and position via REST API (skip sup sync push).
- `--sync-only` -- Only push datasets/charts via sup sync (skip CSS API push).
- `--dry-run` -- Run all validation but stop before actual push.
- No arguments -- Full push: datasets/charts via sup sync + CSS via REST API.

## Prerequisites

```python
from scripts.config import ToolkitConfig
config = ToolkitConfig.discover()
```

## Execution Steps

### Step 1: Validate Sync Folder

```bash
sup sync validate <sync_folder>
```

- If validation fails: Show errors and STOP. Do not proceed to push.
- If validation passes: Continue.

### Step 2: Check Required Markers

```python
from scripts.fingerprint import check_markers
from pathlib import Path

markers_file = Path(config.get("validation.markers_file", ".preset-toolkit/markers.txt"))
assets = Path(config.sync_folder) / "assets"
dataset_yamls = list((assets / "datasets").rglob("*.yaml"))

for ds in dataset_yamls:
    result = check_markers(ds, markers_file)
    if not result.all_present:
        # BLOCK PUSH
        print(f"BLOCKED: Missing markers in {ds.name}:")
        for m in result.missing:
            print(f"  - {m}")
        print("Fix the missing content before pushing.")
        return
```

**Markers are a hard gate.** If any marker is missing, the push is BLOCKED. Tell the user what is missing and how to fix it.

### Step 3: Ownership Check (Advisory)

If `.preset-toolkit/ownership.yaml` exists, check for ownership warnings:

```python
from scripts.ownership import OwnershipMap

ownership_file = Path(".preset-toolkit/ownership.yaml")
if ownership_file.exists():
    omap = OwnershipMap.load(ownership_file)
    # Detect changed charts from git diff or file mtimes
    check = omap.check(
        user_email=config.user_email,
        changed_charts=changed_chart_ids,
        changed_datasets=changed_dataset_names,
    )
    if check.has_warnings:
        for w in check.warnings:
            print(f"  Advisory: {w}")
```

Ownership warnings are **advisory only** -- they never block a push. Show them so the user is aware.

### Step 4: Dry Run

```bash
sup sync run <sync_folder> --push-only --dry-run --force
```

Capture and display the output. This shows exactly what would change on Preset.

### Step 5: Approval Gate

Present a structured summary using `DryRunResult` from validate():

```python
from scripts.formatter import format_output

# result is the DryRunResult from validate()
print(format_output(result, fmt="table"))
```

This renders:

```
Validation: PASSED
Markers:    PASSED

Action       Type         Name
--------------------------------------------------
create       chart        New Revenue Chart
update       dataset      Main_Dataset

2 change(s) detected.
```

If no structured changes are parsed, the raw sup output is shown as fallback.

**This is the only approval question in the push flow.** Wait for explicit "yes" before proceeding.

If `--dry-run` was specified, stop here and report the summary without asking.

### Step 6: Push Datasets/Charts

If not `--css-only`:

```bash
sup sync run <sync_folder> --push-only --force
```

Retry up to 3 times on failure (JWT intermittent issues).

### Step 7: Push CSS/Position via REST API

If not `--sync-only` and `config.get("css.push_via_api")` is true:

```python
from scripts.push_dashboard import push_css_and_position
import yaml

# Read CSS from dashboard YAML
dash_dir = Path(config.sync_folder) / "assets" / "dashboards"
dash_yamls = list(dash_dir.glob("*.yaml"))
with open(dash_yamls[0]) as f:
    dash_data = yaml.safe_load(f)

css = dash_data.get("css", "")
position = dash_data.get("position_json", None)

result = push_css_and_position(config, css, position)
```

This is necessary because `sup sync push` overwrites CSS and position_json. The REST API push restores them. See `references/sup-cli.md` for why this two-step push exists.

### Step 8: Save Fingerprint

```python
from scripts.fingerprint import compute_fingerprint, save_fingerprint

dataset_yamls = list((assets / "datasets").rglob("*.yaml"))
if dataset_yamls:
    fp = compute_fingerprint(dataset_yamls[0])
    fp_file = Path(config.get("validation.fingerprint_file", ".preset-toolkit/.last-push-fingerprint"))
    save_fingerprint(fp, fp_file)
```

### Step 9: Pull-Back Verification

Pull back from Preset and verify the push landed correctly:

```bash
sup sync run <sync_folder> --pull-only --force
```

Then check markers again:

```python
result = check_markers(dataset_yamls[0], markers_file)
if not result.all_present:
    print("WARNING: Post-push verification failed. Some markers are missing after pull-back.")
    print("This may indicate the push was partially overwritten or cached.")
```

### Step 10: Git Commit

If the project is a git repo, commit the current state:

```bash
git add <sync_folder>/
git commit -m "Sync: push <description of changes>"
```

This ensures the pushed state is always recoverable from git. Never skip this step after a successful push.

### Step 11: Summary

```
Push Complete

  Datasets/charts: Pushed via sup sync
  CSS/position: Pushed via REST API
  Fingerprint: <hash> (<length> chars) -- saved
  Post-push verification: Markers all present / WARNING: markers missing
  Git commit: <commit hash>
```

## Using the Python API

```python
from scripts.sync import push
from scripts.config import ToolkitConfig

config = ToolkitConfig.discover()
result = push(config, css_only=False, sync_only=False, dry_run=False)
```

## Error Recovery

| Symptom | Cause | Fix |
|---|---|---|
| Validation fails | YAML syntax or reference errors | Fix the YAML, re-run validate |
| Markers missing | Content regression | Restore from git, re-apply changes |
| JWT failure during push | Intermittent Preset auth | Retry (built-in 3x retry) |
| CSS push fails | Auth or CSRF issue | Check credentials, retry with `--css-only` |
| Post-push markers missing | sup sync overwrote CSS | Re-push CSS via `--css-only` |
| Push partially applied | Network interruption | Re-run full push |
