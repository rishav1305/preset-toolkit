---
name: sync-pull
description: "Pull latest dashboard state from Preset, deduplicate files, and verify integrity"
---

# Sync Pull

Pull the latest dashboard state from Preset, deduplicate chart/dataset files, and verify content integrity against the last known good push.

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

Load the project config -- all paths and parameters come from here:

```python
from scripts.config import ToolkitConfig
config = ToolkitConfig.discover()
```

The sync folder, markers file, and fingerprint file paths are all derived from config. Never ask the user for these.

## Execution Steps

### Step 1: Pull from Preset

Run `sup sync pull` with retry logic (up to 3 attempts on failure):

```bash
sup sync run <sync_folder> --pull-only --force
```

Where `<sync_folder>` comes from `config.sync_folder`.

If all 3 attempts fail, report the error and stop. Common causes:
- JWT authentication failure (intermittent -- suggest retry in a few minutes)
- Network timeout
- Invalid sync folder configuration

### Step 2: Deduplicate Files

After a successful pull, run dedup on charts and datasets:

```python
from scripts.dedup import apply_dedup
from pathlib import Path

assets = Path(config.sync_folder) / "assets"

# Dedup charts
charts_removed = apply_dedup(assets / "charts")

# Dedup datasets (each database subdirectory)
datasets_dir = assets / "datasets"
dataset_removed = 0
if datasets_dir.exists():
    for subdir in datasets_dir.iterdir():
        if subdir.is_dir():
            dataset_removed += apply_dedup(subdir)
```

Report how many duplicates were removed.

### Step 3: Fingerprint Comparison

Compare the current content against the last saved fingerprint:

```python
from scripts.fingerprint import compute_fingerprint, load_fingerprint, check_markers

fp_file = Path(config.get("validation.fingerprint_file", ".preset-toolkit/.last-push-fingerprint"))
last_fp = load_fingerprint(fp_file)

# Find the primary dataset YAML
dataset_yamls = list((assets / "datasets").rglob("*.yaml"))
if dataset_yamls:
    current_fp = compute_fingerprint(dataset_yamls[0])
```

- If fingerprint matches last push: "Content is consistent with last push."
- If fingerprint changed: "Content has changed since last push." -- This could mean someone else pushed changes, or it could be stale data.

### Step 4: Marker Verification

Check that all required content markers are present:

```python
markers_file = Path(config.get("validation.markers_file", ".preset-toolkit/markers.txt"))
if markers_file.exists() and dataset_yamls:
    result = check_markers(dataset_yamls[0], markers_file)
```

- If all markers present: "All required markers verified."
- If markers are missing: **This is a critical warning.**

```
WARNING: Pull returned content missing required markers:
  - Missing: Revenue - Ads | Subs Sales
  - Missing: wcbm-section__hdr">Activation</div>

This pull may contain stale or regressed data.
Recommendation: Restore from the last known good state using git.

Do NOT build on top of this pull. Use `git checkout -- <sync_folder>/` to restore.
```

### Step 5: Summary

Print a summary report:

```
Pull Complete

  Sync folder: <sync_folder>
  Files pulled: <count from sync output>
  Duplicates removed: <charts_removed + dataset_removed>
  Fingerprint: <current_fp.hash> (<current_fp.sql_length> chars)
  Fingerprint status: Matches last push / Changed / No previous fingerprint
  Markers: All present / X missing (WARNING)
```

## Using the Python API

The complete pull workflow is also available as a single function call:

```python
from scripts.sync import pull
from scripts.config import ToolkitConfig

config = ToolkitConfig.discover()
result = pull(config)

# result.success -- bool
# result.steps_completed -- list of step descriptions
# result.warnings -- list of warning messages
# result.error -- error message if failed
```

## Error Recovery

| Symptom | Cause | Fix |
|---|---|---|
| "Unable to fetch JWT" | Intermittent Preset auth issue | Retry in 1-2 minutes |
| Markers missing after pull | Stale/cached data returned | Restore from git, do not use this pull |
| Fingerprint changed unexpectedly | Someone else pushed changes | Review the diff before proceeding |
| Dedup removed files | Chart renamed on Preset | Normal behavior, expected after renames |
