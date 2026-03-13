# Common Pitfalls and Solutions

## Pull Returns Stale Data

**Symptom:** `sup sync pull` returns content that does not reflect recent
changes made on Preset (e.g., missing a chart rename, old SQL, stale CSS).

**Cause:** Preset's export endpoint may return cached data. There is no
cache-busting mechanism in the `sup` CLI.

**Mitigation:**
1. After every pull, compare the result against your last known good push
   (fingerprint or marker check).
2. If the pull is stale, do NOT build on top of it. Restore from git instead:
   ```bash
   git checkout <last-good-commit> -- <sync-folder>/assets/
   ```
3. If you need the absolute latest Preset state, use the REST API
   (`GET /api/v1/dashboard/{id}`) which is less likely to be cached.
4. Wait a few minutes and retry the pull — caches do expire.

## Filename Drift After Chart Rename

**Symptom:** After pulling, you see two YAML files for the same chart — the
old filename and a new one. Both contain the same UUID.

**Cause:** `sup sync pull` generates filenames from `slice_name`. Renaming a
chart on Preset creates a new file. The old file is never deleted by `sup`.

**Impact:**
- Confusion about which file is authoritative.
- If both files are pushed, Superset uses the UUID to match — so only one
  takes effect. But the duplicate clutters the repo.
- Scripts that reference charts by filename break when the name changes.

**Mitigation:**
- Run a dedup script after every pull. Group by UUID, keep the preferred file.
- Use ID-based naming (e.g., `Acquisition_2122.yaml`) to reduce drift.
- The dedup script should use `git rm` for tracked files to keep git clean.

## JWT Intermittent Failures

**Symptom:** `sup` commands fail with "Unable to fetch JWT" or similar
authentication errors, even though credentials are correct.

**Cause:** Preset Cloud's JWT endpoint has intermittent availability issues.
This is a server-side problem, not a local configuration issue.

**Mitigation:**
- Retry up to 3 times with 5-second delays between attempts.
- For validation-only workflows, prefer local file checks (YAML parse,
  fingerprint, marker checks) over `sup` commands.
- If auth is persistently failing, re-run `sup connect` to refresh the
  stored credentials.
- Check Preset status page for ongoing incidents.

## CSS Overwritten by sup sync Push

**Symptom:** After running `sup sync run --push-only --force`, dashboard CSS
reverts to an old version. Custom styles applied via REST API are lost.

**Cause:** The import bundle includes the dashboard YAML which contains a
`css:` field. On import, Superset replaces the entire CSS with whatever is
in the bundle — even if it is outdated.

**Mitigation:**
- **Always** push CSS via REST API AFTER `sup sync push`.
- Use a unified push script that runs both steps in sequence:
  1. `sup sync run --push-only --force` (datasets, charts)
  2. `PUT /api/v1/dashboard/{id}` with current CSS (via script)
- Keep the authoritative CSS in a known location (e.g., dashboard YAML or
  a separate CSS file) and always push from that source.

## Jinja Template Corruption

**Symptom:** After editing a dataset YAML, Preset shows SQL syntax errors or
filter expressions stop working. The SQL looks correct on visual inspection.

**Cause:** Using `yaml.dump()` to write the file re-encoded Jinja template
syntax. `{{ filter_values('col')[0] }}` may become quoted or escaped in a way
that breaks Jinja parsing.

**Mitigation:**
- Never use `yaml.dump()`. See `yaml-safety.md` for the safe editing pattern.
- After editing, search the file for `{{ }}` patterns and verify they are
  unchanged.
- If corruption has already occurred, restore the file from git and re-apply
  changes using string replacement only.

## Missing Markers After Push

**Symptom:** Post-push verification (pull-back + marker check) reports that
expected content markers are missing.

**Cause:** The push may have been partial — some assets were imported but
others failed silently. Or the pull-back returned cached pre-push data.

**Mitigation:**
1. Check the `sup sync` output for warnings or errors during push.
2. Wait 60 seconds, then pull again and re-check markers.
3. If still missing, inspect the specific asset via REST API
   (`GET /api/v1/chart/{id}`) to see its current state on Preset.
4. If the asset is genuinely missing, re-push. If it is present on Preset
   but the pull does not show it, this is a pull caching issue — see
   "Pull Returns Stale Data" above.

## Duplicate Files Accumulate Over Time

**Symptom:** The `assets/charts/` directory has many more files than there are
actual charts on the dashboard. Multiple files share the same UUID.

**Cause:** Every chart rename on Preset, plus some chart edits that change the
`slice_name`, generates a new file on the next pull. Old files persist.

**Impact:**
- Repository bloat.
- Confusion about which file to edit.
- Potential for pushing stale content if the wrong file is modified.

**Mitigation:**
- Integrate dedup into the pull workflow (run automatically after every pull).
- The dedup script should:
  1. Parse all YAML files to extract UUIDs.
  2. Group by UUID.
  3. When duplicates exist, keep the preferred file (e.g., by naming convention
     or newest mtime).
  4. Remove others with `git rm` (tracked) or `rm` (untracked).

## Row Limit Mismatch

**Symptom:** A table chart shows "Row limit reached" or displays fewer rows
than expected.

**Cause:** Chart YAML has `row_limit` set in both `params` and `query_context`.
If these values disagree, the lower limit wins.

**Mitigation:**
- When changing row_limit, update it in BOTH `params` and `query_context`.
- Search the raw YAML for all occurrences of `row_limit` and ensure they match:
  ```bash
  grep -o '"row_limit": [0-9]*' chart_file.yaml
  ```

## Changes Do Not Appear on Dashboard

**Symptom:** Push succeeded, but the dashboard still shows old content.

**Cause:** Preset caches chart query results and rendered content. The cache
may take several minutes to expire.

**Mitigation:**
1. Force-refresh the dashboard: append `?force=true` to the URL.
2. For individual charts: click the chart menu (...) and select "Force refresh".
3. Wait 3-5 minutes for cache expiry.
4. If changes still do not appear, pull back and verify the asset actually
   updated on Preset.
