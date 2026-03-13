---
name: preset-validate
description: "Health check: run validation, marker checks, and fingerprint comparison"
---

# Validate (Health Check)

Run a comprehensive health check on the local dashboard state: YAML validation, required marker verification, and fingerprint comparison against the last push.

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

### Step 1: YAML Validation

```bash
sup sync validate <sync_folder>
```

Capture the output. Report:
- PASS: "Validation passed -- all YAML files are structurally valid."
- FAIL: Show the specific validation errors and which files are affected.

### Step 2: Marker Check

```python
from scripts.fingerprint import check_markers
from pathlib import Path

markers_file = Path(config.get("validation.markers_file", ".preset-toolkit/markers.txt"))
assets = Path(config.sync_folder) / "assets"
dataset_yamls = list((assets / "datasets").rglob("*.yaml"))

marker_results = {}
for ds in dataset_yamls:
    if markers_file.exists():
        mr = check_markers(ds, markers_file)
        marker_results[ds.name] = mr
```

Report:
- PASS: "All X markers present in dataset SQL."
- FAIL: List each missing marker with the dataset file name.

### Step 3: Fingerprint Comparison

```python
from scripts.fingerprint import compute_fingerprint, load_fingerprint

fp_file = Path(config.get("validation.fingerprint_file", ".preset-toolkit/.last-push-fingerprint"))
last_fp = load_fingerprint(fp_file)

if dataset_yamls:
    current_fp = compute_fingerprint(dataset_yamls[0])
```

Report:
- Match: "Fingerprint matches last push: `<hash>`"
- Changed: "Fingerprint has changed since last push: `<old_hash>` -> `<new_hash>`"
- No baseline: "No previous fingerprint saved. Run a push to establish baseline."

### Step 4: CSS Length Check

```python
import yaml

dash_dir = Path(config.sync_folder) / "assets" / "dashboards"
for dy in dash_dir.glob("*.yaml"):
    with open(dy) as f:
        data = yaml.safe_load(f)
    css = data.get("css", "")
    css_max = config.get("css.max_length", 30000)
    if len(css) > css_max:
        print(f"WARNING: CSS is {len(css)} chars (limit: {css_max}). Risk of truncation on Preset.")
    else:
        print(f"CSS: {len(css)} chars (under {css_max} limit)")
```

### Step 5: Summary Report

```
Health Check Report

  YAML Validation:    PASS / FAIL
  Required Markers:   X/Y present (PASS) / X missing (FAIL)
  Fingerprint:        Matches / Changed / No baseline
  CSS Length:          XXXX chars (PASS) / XXXX chars (WARNING: over limit)

  Overall: HEALTHY / ISSUES FOUND
```

If issues are found, provide specific remediation steps for each one.

## Using the Python API

```python
from scripts.sync import validate
from scripts.config import ToolkitConfig

config = ToolkitConfig.discover()
result = validate(config)

# result.success -- bool
# result.steps_completed -- list of step descriptions
# result.error -- error message if failed
```
