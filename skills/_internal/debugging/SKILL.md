---
name: debugging
description: "Systematic debugging for Preset dashboard issues with known failure modes and fixes"
---

# Debugging

Systematic debugging for Preset dashboard issues. This skill provides structured diagnosis workflows for known failure modes specific to the Preset/Superset ecosystem.

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

## Known Failure Modes

### 1. JWT Authentication Failure

**Symptom:** `sup` commands fail with "Unable to fetch JWT" or 401 errors.

**Root cause:** Preset Cloud JWT tokens are short-lived and can fail intermittently. This is a known platform issue.

**Diagnosis:**
```bash
sup version                    # Verify CLI installed
sup sync validate <sync_folder>  # Lightweight auth test
```

**Fix:**
- Retry the command up to 3 times (built into `scripts.sync._run_sup`).
- If persistent, wait 2-5 minutes and retry.
- Re-authenticate: `sup connect`
- Verify credentials: check `PRESET_API_TOKEN` and `PRESET_API_SECRET` are set.
- As a last resort, regenerate API keys in the Preset UI (Settings > API Keys).

### 2. CSS Truncation

**Symptom:** Dashboard CSS is partially applied. Styles near the end of the CSS are missing.

**Root cause:** Preset truncates CSS at approximately 33,345 characters. Any CSS beyond this limit is silently dropped.

**Diagnosis:**
```python
import yaml
from pathlib import Path

dash_yaml = Path(config.sync_folder) / "assets" / "dashboards"
for dy in dash_yaml.glob("*.yaml"):
    with open(dy) as f:
        data = yaml.safe_load(f)
    css = data.get("css", "")
    print(f"CSS length: {len(css)} chars")
    if len(css) > 30000:
        print("WARNING: Over safe limit (30K). Truncation likely.")
```

**Fix:**
- Remove dead selectors (`[data-chart-id]` does NOT exist in the DOM).
- Remove CSS comments.
- Consolidate duplicate selectors.
- Target: keep under 30K characters.

### 3. Import Overwrites CSS/Position

**Symptom:** After `sup sync push`, CSS reverts to an old version. Layout positions change unexpectedly.

**Root cause:** `sup sync run --push-only` creates an import bundle that includes the dashboard CSS and `position_json` fields. This overwrites whatever is currently on Preset, including any changes made via the REST API.

**Diagnosis:**
```python
from scripts.push_dashboard import fetch_dashboard

remote = fetch_dashboard(config)
remote_css = remote.get("css", "")
# Compare against local CSS
```

**Fix:**
- Always push CSS via REST API AFTER running `sup sync push`.
- Use `/preset push` which handles both automatically.
- For CSS-only updates: `/preset push --css-only`.

See `references/preset-cli.md` for the explanation of this two-step push.

### 4. Pull Returns Stale Data

**Symptom:** After pulling, content is missing or reverted. Markers fail.

**Root cause:** Preset's pull endpoint may return cached data that does not reflect the latest state.

**Diagnosis:**
```python
from scripts.fingerprint import compute_fingerprint, load_fingerprint, check_markers

# Compare fingerprint
fp_file = Path(config.get("validation.fingerprint_file", ".preset-toolkit/.last-push-fingerprint"))
last_fp = load_fingerprint(fp_file)
current_fp = compute_fingerprint(dataset_yaml)

# Check markers
markers_file = Path(config.get("validation.markers_file", ".preset-toolkit/markers.txt"))
result = check_markers(dataset_yaml, markers_file)
```

**Fix:**
- Do NOT build on top of stale pull data.
- Restore from git: `git checkout -- <sync_folder>/`
- Re-pull after a few minutes (cache may have cleared).
- If persistent, use git state as the source of truth and re-push.

### 5. Duplicate Files After Pull

**Symptom:** Multiple YAML files for the same chart/dataset. Chart appears twice in the sync folder.

**Root cause:** When a chart is renamed on Preset, `sup sync pull` creates a new file with the new name but does NOT delete the old file. Over time, duplicates accumulate.

**Diagnosis:**
```python
from scripts.dedup import find_duplicates
from pathlib import Path

charts_dir = Path(config.sync_folder) / "assets" / "charts"
dupes = find_duplicates(charts_dir)
for uuid, files in dupes.items():
    print(f"Duplicate UUID {uuid}: {[f.name for _, f in files]}")
```

**Fix:**
- Run dedup: built into `/preset pull` automatically.
- Manual dedup: `apply_dedup(charts_dir)`.
- Dedup logic keeps the file without a numeric ID suffix (preserves script references), or newest by mtime.

### 6. Markers Missing After Edit

**Symptom:** After editing a dataset YAML, marker checks fail.

**Root cause:** The edit accidentally removed or altered a required content marker (label, section header, formula indicator).

**Diagnosis:**
```python
from scripts.fingerprint import check_markers

result = check_markers(dataset_yaml, markers_file)
for m in result.missing:
    print(f"Missing marker: {m}")
```

**Fix:**
- Review the edit to find what was accidentally removed.
- Undo the edit and re-apply more carefully.
- The marker strings are defined in `.preset-toolkit/markers.txt` -- check exactly what was expected.
- Common cause: search-and-replace that was too broad and caught the marker string.

### 7. Jinja Template Corruption

**Symptom:** Dashboard filters stop working. SQL errors on chart rendering. `{{ }}` appears as literal text.

**Root cause:** Using `yaml.dump()` to write back a YAML file re-encodes Jinja template syntax (`{{ filter_values('...') }}`) and breaks it.

**Diagnosis:**
Search for escaped Jinja in the dataset YAML:
```bash
grep -n '{{' <dataset_yaml>
grep -n "'{'" <dataset_yaml>
```

Compare against a known good version from git.

**Fix:**
- Restore the file from git: `git checkout -- <file>`
- Re-apply the edit using the safe YAML edit pattern (raw string replacement, NEVER `yaml.dump()`).

See `references/preset-cli.md` for the safe YAML edit pattern.

### 8. Row Limit Mismatch

**Symptom:** Chart shows "Row limit reached" warning. Data is truncated. Not all tiles appear.

**Root cause:** The `row_limit` in the chart YAML does not match the `row_limit` in `query_context`. Or the row limit is too low for the number of rows the query returns.

**Diagnosis:**
```bash
grep -n 'row_limit' <chart_yaml>
```

Check both the top-level `row_limit` field and the `row_limit` inside `query_context`.

**Fix:**
- Set both `row_limit` values to be equal and high enough for the data.
- Typical safe values: 1000 for summary charts, 10000 for detail charts.

## Debugging Workflow

When the user reports an issue, follow this systematic approach:

1. **Classify:** Match the symptom to one of the known failure modes above.
2. **Diagnose:** Run the specific diagnostic steps.
3. **Confirm:** Show the diagnosis to the user in business terms (never technical details).
4. **Fix:** Apply the fix automatically or guide the user through it.
5. **Verify:** Run health check after the fix: markers + fingerprint + validate.

If the issue does not match any known failure mode, escalate to general debugging:
- Check `git diff` for recent changes.
- Compare current state against last known good commit.
- Check Preset UI directly for discrepancies.
