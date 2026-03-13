---
name: preset-code-review
description: "Review checklist for Preset dashboard changes -- verify safety, correctness, and completeness"
---

# Code Review

Run a comprehensive review checklist for Preset dashboard changes. Verify that all safety rules are followed, content is correct, and no regressions were introduced.

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

## Review Checklist

Run each check in order. Report PASS/FAIL/SKIP for each item.

### 1. No yaml.dump() Usage

Search for `yaml.dump` in all changed files. This function re-encodes Jinja templates and breaks dashboard functionality.

```bash
grep -rn 'yaml\.dump' <changed_files>
```

- PASS: No `yaml.dump()` found in any changes.
- FAIL: Found `yaml.dump()` usage. Must use raw string replacement instead. See `references/preset-cli.md`.

### 2. Jinja Templates Preserved

Check that Jinja template syntax (`{{ }}`, `{% %}`) is intact in all dataset SQL fields.

```bash
grep -c '{{' <dataset_yamls>  # Should have expected count
grep -c '{%' <dataset_yamls>  # Should have expected count
```

Compare Jinja expression count before and after the change. If count decreased, a template may have been corrupted.

- PASS: Jinja expression count unchanged or correctly modified.
- FAIL: Jinja expressions missing or corrupted.

### 3. CSS Under Length Limit

```python
import yaml
from pathlib import Path

dash_dir = Path(config.sync_folder) / "assets" / "dashboards"
css_max = config.get("css.max_length", 30000)

for dy in dash_dir.glob("*.yaml"):
    with open(dy) as f:
        data = yaml.safe_load(f)
    css = data.get("css", "")
    length = len(css)
```

- PASS: CSS is under the configured limit (default 30K).
- FAIL: CSS exceeds limit. Risk of truncation on Preset (truncates at ~33K).

### 4. All Required Markers Present

```python
from scripts.fingerprint import check_markers

markers_file = Path(config.get("validation.markers_file", ".preset-toolkit/markers.txt"))
assets = Path(config.sync_folder) / "assets"

for ds in (assets / "datasets").rglob("*.yaml"):
    result = check_markers(ds, markers_file)
```

- PASS: All markers present in all dataset files.
- FAIL: Missing markers. Content regression detected.

### 5. Ownership Violations Checked

```python
from scripts.ownership import OwnershipMap

ownership_file = Path(".preset-toolkit/ownership.yaml")
if ownership_file.exists():
    omap = OwnershipMap.load(ownership_file)
    check = omap.check(
        user_email=config.user_email,
        changed_charts=changed_chart_ids,
        changed_datasets=changed_dataset_names,
    )
```

- PASS: No ownership warnings, or warnings acknowledged.
- WARN: Advisory warnings present (show them but do not block).
- SKIP: No ownership.yaml configured.

### 6. Row Limit Consistency

For each changed chart YAML, verify that `row_limit` matches `query_context` `row_limit`:

```python
import yaml, json

for chart_yaml in changed_chart_files:
    with open(chart_yaml) as f:
        data = yaml.safe_load(f)
    top_limit = data.get("params", {}).get("row_limit") if isinstance(data.get("params"), dict) else None
    qc = data.get("query_context")
    if qc:
        if isinstance(qc, str):
            qc = json.loads(qc)
        qc_limit = None
        for query in qc.get("queries", []):
            qc_limit = query.get("row_limit")
```

- PASS: Row limits are consistent across all changed charts.
- FAIL: Mismatch found. The chart may truncate data or show a "Row limit reached" warning.

### 7. allow_render_html Set for HTML Charts

Charts that render HTML content (KPI tiles with styled divs) must have `allow_render_html: true` in their params.

```python
for chart_yaml in html_chart_files:
    with open(chart_yaml) as f:
        data = yaml.safe_load(f)
    params = data.get("params", {})
    if isinstance(params, str):
        params = json.loads(params)
    allow_html = params.get("allow_render_html", False)
```

- PASS: All HTML-rendering charts have the flag set.
- FAIL: Flag missing. HTML will render as raw text.
- SKIP: No HTML-rendering charts in the changeset.

### 8. No Ambiguous YAML Aliases/Anchors

Check for YAML anchors (`&name`) and aliases (`*name`) that could cause unexpected behavior:

```bash
grep -n '&\w\+' <changed_yamls>
grep -n '\*\w\+' <changed_yamls>
```

- PASS: No anchors or aliases found, or they are intentional and correct.
- WARN: Anchors/aliases found. Verify they resolve correctly.

### 9. Fingerprint Updated After Push

If changes have been pushed, verify that the fingerprint file was updated:

```python
from scripts.fingerprint import load_fingerprint, compute_fingerprint

fp_file = Path(config.get("validation.fingerprint_file", ".preset-toolkit/.last-push-fingerprint"))
saved_fp = load_fingerprint(fp_file)
current_fp = compute_fingerprint(primary_dataset_yaml)

if saved_fp and saved_fp.hash == current_fp.hash:
    print("Fingerprint is current.")
else:
    print("WARNING: Fingerprint is stale or missing.")
```

- PASS: Fingerprint matches current state.
- FAIL: Fingerprint not saved after push, or does not match current files.
- SKIP: No push has been made yet.

## Summary Report

```
Code Review Report

  Check                          Status
  ----------------------------   ------
  1. No yaml.dump() usage        PASS
  2. Jinja templates preserved   PASS
  3. CSS under length limit      PASS (21,450 chars)
  4. All markers present         PASS (15/15)
  5. Ownership checked           WARN (2 advisory)
  6. Row limit consistency       PASS
  7. allow_render_html           PASS
  8. No YAML aliases             PASS
  9. Fingerprint current         PASS

  Overall: APPROVED / ISSUES FOUND

  Advisory warnings:
    - Chart 2087 is in alice@'s section (Activation)
    - Dataset 'WCBM_Audience_Tile_Source' is shared
```

## When to Run This Review

- Before every push (automatically invoked by `/preset push`).
- After completing a multi-step plan.
- Before submitting changes for approval by another team member.
- As part of the daily checkpoint workflow.
