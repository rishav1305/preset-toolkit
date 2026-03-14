# sup CLI Reference

The `sup` CLI (pip package: `superset-sup`) is the sync tool for Preset dashboards.

## Installation

```bash
pip install superset-sup
```

Verify installation:

```bash
sup --version
```

## Authentication

Run `sup config` to authenticate. It prompts for workspace credentials.

Credentials are stored locally by the sup CLI. Never commit credentials to version control.

## Core Commands

### Pulling Dashboard State

```bash
sup sync run <sync-folder> --pull-only --force
```

Downloads the current state of all dashboards, charts, datasets, and databases
defined in the sync folder. Files land in `<sync-folder>/assets/`.

The `--force` flag bypasses interactive confirmation prompts. Always use it in
automated workflows.

**Warning:** Pull may return cached or stale data. Preset does not guarantee
the response reflects the absolute latest state. After pulling, always verify
content against the last known good push (e.g., via fingerprint comparison).

### Pushing Local Changes

```bash
sup sync run <sync-folder> --push-only --force
```

Uploads the local YAML assets to Preset as an import bundle. This creates or
updates dashboards, charts, and datasets by matching on UUID.

**Critical side effect:** The import bundle OVERWRITES the dashboard `css` and
`position_json` fields. Any CSS or layout changes applied via the REST API will
be lost. This is why CSS must be pushed separately after `sup sync push`.

### Dry Run

```bash
sup sync run <sync-folder> --push-only --dry-run --force
```

Shows what would change without actually pushing. Use this before every real
push to catch unexpected modifications.

### Validation

```bash
sup sync validate <sync-folder>
```

Checks YAML structure and references. Run this before pushing to catch syntax
errors, missing UUIDs, or broken dataset references.

## Important Flags

| Flag | Purpose |
|---|---|
| `--force` | Bypass confirmation prompts |
| `--overwrite` | Replace existing assets that match by UUID |
| `--disallow-edits` | Prevent import from modifying existing assets (create-only mode) |
| `--pull-only` | Only pull from Preset, do not push |
| `--push-only` | Only push to Preset, do not pull |
| `--dry-run` | Show what would change without applying |

## Jinja Escaping

Preset SQL fields frequently contain Jinja2 template syntax such as
`{{ filter_values('column') }}` or `{% if %}...{% endif %}`. These must be
preserved literally in YAML files.

When reading or writing YAML containing Jinja expressions:
- Do NOT use `yaml.dump()` — it re-encodes curly braces and breaks templates.
- Use raw string replacement to modify SQL fields.
- After editing, verify the Jinja syntax is intact by searching for `{{ }}`.

## JWT Intermittent Failures

The `sup` CLI authenticates via JWT tokens that can fail randomly with errors
like "Unable to fetch JWT". This is a known Preset Cloud issue.

Mitigation:
- Retry the command up to 3 times with a short delay between attempts.
- Prefer dry-run + local file assertions for validation.
- Batch changes and push once rather than making many small pushes.

## File Structure After Pull

```
<sync-folder>/
  assets/
    dashboards/       # One YAML per dashboard
    charts/           # One YAML per chart (filename from slice_name)
    datasets/
      <database>/     # One YAML per dataset, grouped by database connection
    databases/        # Database connection configs
  metadata.yaml       # Sync configuration (workspace, filters)
```

## Filename Gotchas

`sup sync pull` generates filenames from the chart's `slice_name` field. If a
chart is renamed on Preset, the next pull creates a NEW file with the new name.
The old file is NOT deleted. This causes duplicate files to accumulate over
time. Always run a dedup step after pulling.
