---
name: troubleshoot
description: "Decision tree for diagnosing and fixing common Preset dashboard issues"
---

# Troubleshoot

Diagnose and fix common Preset dashboard issues using a structured decision tree. Start by asking what the user is seeing, then follow the appropriate diagnostic path.

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

## Entry Point

Ask the user: **"What problem are you seeing?"**

Then route to the appropriate diagnostic path based on their description.

## Diagnostic Paths

### Path 1: "Changes don't show up"

The user pushed changes but they are not visible on the dashboard.

**Diagnosis steps:**

1. **Check if CSS was pushed via API.** The `sup sync push` command overwrites CSS. If only `sup sync` was used (without the REST API CSS push), CSS changes will be lost.
   ```python
   # Verify CSS was pushed via REST API
   from scripts.push_dashboard import fetch_dashboard
   remote = fetch_dashboard(config)
   remote_css = remote.get("css", "")
   # Compare against local CSS in dashboard YAML
   ```

2. **Check browser cache.** Preset caches aggressively.
   - Try adding `?force=true` to the dashboard URL.
   - Try hard-refreshing the browser (Cmd+Shift+R).
   - Wait 3-5 minutes for cache to clear.

3. **Pull back and verify.** Pull from Preset and check if the pushed content is actually there:
   ```bash
   sup sync run <sync_folder> --pull-only --force
   ```
   Then check markers to verify content.

4. **Check for partial push failure.** The push may have succeeded for some assets but failed for others (e.g., datasets pushed but CSS was overwritten).

**Fix:** Re-push using the full push workflow: `/preset push` (which handles both sup sync and CSS API push).

### Path 2: "Push failed"

The push command returned an error.

**Diagnosis steps:**

1. **Check validation.** Run `sup sync validate <sync_folder>` to check for YAML errors.

2. **Check markers.** Run marker check to see if content has regressed:
   ```python
   from scripts.fingerprint import check_markers
   ```

3. **Check auth.** JWT tokens expire frequently.
   - Run `sup version` to verify the CLI is installed.
   - Try `sup connect` to re-authenticate.
   - Check that `PRESET_API_TOKEN` and `PRESET_API_SECRET` are set.

4. **Check for JWT intermittent failure.** The `sup` CLI can fail randomly with "Unable to fetch JWT". Retry up to 3 times. If persistent, wait a few minutes and try again. See `references/preset-cli.md` for details.

5. **Check dry-run output.** Run a dry-run to see what would have been pushed:
   ```bash
   sup sync run <sync_folder> --push-only --dry-run --force
   ```

**Fix:** Address the specific error (YAML fix, re-auth, retry), then re-push.

### Path 3: "Visual looks wrong" (layout, fonts, spacing)

The dashboard renders but looks different from expected.

**Diagnosis steps:**

1. **Capture a screenshot and compare against baseline:**
   ```
   /preset diff
   ```

2. **Check CSS truncation.** Preset truncates CSS at approximately 33,345 characters. Check current length:
   ```python
   # In dashboard YAML, check len(css)
   ```
   If over 30K, compress by removing dead selectors and comments. See `references/preset-api.md` for truncation details.

3. **Check for dead CSS selectors.** `[data-chart-id]` does not exist in the DOM -- use `[data-test-chart-id]` instead. Search for dead selectors:
   ```bash
   grep -n 'data-chart-id' <dashboard_yaml>
   ```

4. **Check if sup sync overwrote CSS.** If `sup sync push` was run without the CSS API follow-up, position_json and CSS are overwritten.

**Fix:** Edit the dashboard YAML CSS, then push with `/preset push --css-only`.

### Path 4: "Data is stale"

Dashboard shows old data or data stops at an unexpected date.

**Diagnosis steps:**

1. **Check pull freshness.** Pull may return cached data:
   ```python
   from scripts.fingerprint import compute_fingerprint, load_fingerprint
   ```
   Compare fingerprint against last push.

2. **Check if pull is stale.** Run markers check after pull. If markers are missing, the pull returned regressed content.

3. **Check dbt freshness.** If the underlying data pipeline (dbt) has not run recently, the dashboard will show stale data regardless of Preset state.

4. **Check source table dates.** Common stale sources:
   - `app_platform_sessionstart_and_pageviewed`: May be stuck at an old date.
   - `off_prop_weekly_copy`: Refreshes Mondays only.

**Fix:** If Preset data is stale, re-pull. If source data is stale, check dbt pipeline. If pull returns cached data, restore from git.

### Path 5: "Tiles are broken"

Individual tiles show errors, missing data, or wrong formatting.

**Diagnosis steps:**

1. **Check dataset SQL.** Open the dataset YAML and verify the SQL query is syntactically valid and Jinja templates are intact (`{{ }}` not escaped or broken).

2. **Check `row_limit`.** In the chart YAML, verify `row_limit` matches the `query_context` `row_limit`. If the chart has more rows than the limit, data will be truncated:
   ```bash
   grep -n 'row_limit' <chart_yaml>
   ```

3. **Check `allow_render_html`.** HTML-rendering charts (e.g., KPI tiles with HTML content) require `allow_render_html: true` in the chart YAML. If missing, HTML is displayed as raw text.

4. **Check Jinja escaping.** If `yaml.dump()` was used instead of string replacement, Jinja templates may be corrupted. Look for escaped curly braces. See `references/preset-cli.md` for the safe YAML edit pattern.

**Fix:** Edit the relevant chart or dataset YAML to fix the specific issue, then push.

## Quick Reference: Common Fixes

| Problem | Likely Cause | Quick Fix |
|---|---|---|
| CSS not applied | sup sync overwrote it | `/preset push --css-only` |
| Stale pull data | Preset cache | Restore from git, re-push |
| JWT failure | Intermittent auth | Retry 3x, wait 2 min |
| Duplicate files | Chart renamed on Preset | Run dedup: `/preset pull` |
| Markers missing | Content regression | Restore from git, check edits |
| HTML as raw text | `allow_render_html` missing | Add to chart YAML, re-push |
| Truncated CSS | Over 33K chars | Compress CSS, remove dead selectors |
