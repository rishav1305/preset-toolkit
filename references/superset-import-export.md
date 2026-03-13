# Superset Import/Export Bundle Format

## Overview

`sup sync` uses Apache Superset's native import/export mechanism. On pull, it
downloads a ZIP bundle and extracts it into YAML files. On push, it reassembles
the YAML files into a ZIP bundle and uploads it.

Understanding this format is essential because it determines what can be changed
locally and how those changes are applied on Preset.

## Bundle Structure

```
assets/
  databases/
    <database_name>.yaml          # Connection configs (host, port, creds)
  datasets/
    <database_name>/
      <dataset_name>.yaml         # SQL, columns, metrics, cache settings
  charts/
    <chart_name>.yaml             # Visualization type, params, query config
  dashboards/
    <dashboard_name>_<id>.yaml    # Layout, CSS, filters, chart references
  metadata.yaml                   # Sync folder config (workspace, team URL)
```

## UUID Identity

Every asset (dashboard, chart, dataset, database) has a `uuid` field in its
YAML file. This UUID is the primary identity key.

When importing:
- If a UUID matches an existing asset on Preset, that asset is **updated**.
- If no match exists, a **new** asset is created.
- Filenames are irrelevant for matching — only UUIDs matter.

This means you can rename files locally without affecting import behavior, as
long as the UUID inside the file remains correct.

## Filename Generation and Drift

`sup sync pull` generates filenames from the asset's display name:
- Charts: `slice_name` field (e.g., `Acquisition_2122.yaml`)
- Datasets: dataset name (e.g., `WCBM_Audience_Tile_Source.yaml`)
- Dashboards: `dashboard_title` + ID (e.g., `Weekly_Consumer_Business_Metrics_Dashboard_76.yaml`)

**The drift problem:** When a chart is renamed on Preset (e.g., from
"Revenue" to "Revenue - Ads | Subs"), the next pull creates a NEW file
(`Revenue_-_Ads__Subs_2085.yaml`) without deleting the old one
(`Revenue.yaml`). Both files contain the same UUID. Over time, duplicate files
accumulate.

**Mitigation:** Run a dedup script after every pull. Group files by UUID and
keep only the newest (or preferred) file for each UUID.

## Import Behavior

### `--overwrite` (Default)

Assets matching by UUID are replaced with the imported version. New UUIDs create
new assets. This is the standard mode for pushing updates.

### `--disallow-edits`

Existing assets (matching UUIDs) are left unchanged. Only new UUIDs create
assets. Useful when seeding new charts without risking changes to existing ones.

## Dependency Resolution

Import bundles resolve dependencies automatically:

- **Dashboard import** pulls in all referenced charts and their datasets.
- **Chart import** pulls in the associated dataset.
- **Dataset import** pulls in the associated database connection.

This means a dashboard YAML file references charts by UUID, and Superset
follows the chain to find all required assets in the bundle.

If a referenced asset is missing from the bundle, the import may fail or create
a broken reference. Always include the full dependency tree.

## Critical Limitation: CSS and Position Overwrite

**The most important thing to understand about import bundles:**

When a dashboard is imported via `sup sync push`, the import process overwrites
these fields with whatever is in the YAML file:
- `css` — custom dashboard CSS
- `position_json` — tile grid layout positions

This means:
1. If you update CSS via the REST API and then run `sup sync push`, your CSS
   changes are lost (replaced by whatever CSS is in the dashboard YAML).
2. If you update layout via the Preset UI and then push, your layout changes
   are lost.

**Workaround:** Always push CSS and position_json separately via the REST API
(`PUT /api/v1/dashboard/{id}`) AFTER running `sup sync push`. The push order
must be:

1. `sup sync run <folder> --push-only --force` (pushes charts, datasets)
2. REST API `PUT` to dashboard endpoint (pushes CSS, position_json)

## YAML File Format

### Dashboard YAML

Key fields:
- `dashboard_title` — display name
- `css` — custom CSS string (can be very long)
- `position_json` — JSON object defining grid layout
- `metadata.native_filter_configuration` — dashboard filters
- `slug` — URL-friendly identifier

### Chart YAML

Key fields:
- `slice_name` — display name
- `viz_type` — chart type (e.g., `table`, `echarts_timeseries`, `markdown`)
- `params` — JSON string with visualization config
- `query_context` — JSON string with query parameters (row_limit, filters)
- `dataset_uuid` — reference to the associated dataset

### Dataset YAML

Key fields:
- `table_name` — name in the UI
- `sql` — the SQL query (virtual datasets) or empty (physical tables)
- `columns` — column definitions including `expression` for calculated columns
- `metrics` — saved metric definitions
- `database_uuid` — reference to the database connection

## Editing YAML Files Safely

See `yaml-safety.md` for the full guide. The short version:
- **Never** use `yaml.dump()` to write these files.
- Parse with `yaml.safe_load()` to inspect values.
- Apply changes with string replacement on the raw file content.
- Verify with `yaml.safe_load()` after editing to ensure valid YAML.
