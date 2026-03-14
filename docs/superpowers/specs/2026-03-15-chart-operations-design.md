# Chart Operations — Design Spec

**Sub-project:** 2 of 6 (sup CLI capabilities expansion)
**Date:** 2026-03-15
**Status:** Approved

---

## Goal

Expose all 6 `sup chart` commands (list, info, sql, data, pull, push) as structured Python functions with typed results, a new skill for natural language access, and formatter integration.

## Current State

- Charts are handled only as part of full dashboard sync via `sup sync run`
- No way to list, inspect, query, or operate on individual charts
- `scripts/sync.py` uses `_run_sup()` for CLI invocation with retry logic
- `scripts/formatter.py` provides table/json/yaml output formatting
- sup CLI supports `--json` output for all chart commands (unlike `sup sync --dry-run` which is text-only)

## Architecture

### 1. New Module: `scripts/chart.py`

Six public functions, each wrapping a `sup chart` subcommand:

```python
from typing import Optional

def list_charts(
    config: ToolkitConfig,
    search: Optional[str] = None,
    dashboard_id: Optional[int] = None,
    viz_type: Optional[str] = None,
    dataset_id: Optional[int] = None,
    mine: bool = False,
    modified_after: Optional[str] = None,
    limit: Optional[int] = None,
    order: Optional[str] = None,
    desc: bool = False,
) -> ChartListResult:
    """List charts with optional filtering. Uses sup chart list --json."""

def get_chart_info(config: ToolkitConfig, chart_id: int) -> ChartInfo:
    """Get detailed metadata for a chart. Uses sup chart info <id> --json."""

def get_chart_sql(config: ToolkitConfig, chart_id: int) -> ChartSQL:
    """Get the compiled SQL query for a chart. Uses sup chart sql <id> --json."""

def get_chart_data(
    config: ToolkitConfig, chart_id: int, limit: Optional[int] = None,
) -> ChartData:
    """Get actual data results from a chart. Uses sup chart data <id> --json."""

def pull_charts(
    config: ToolkitConfig,
    chart_id: Optional[int] = None,
    chart_ids: Optional[str] = None,
    name: Optional[str] = None,
    mine: bool = False,
    modified_after: Optional[str] = None,
    limit: Optional[int] = None,
    skip_dependencies: bool = False,
    overwrite: bool = True,
    assets_folder: Optional[str] = None,
) -> ChartPullResult:
    """Pull chart definitions to local filesystem. Uses sup chart pull.

    chart_id and chart_ids are mutually exclusive. Provide one or neither:
    - chart_id: pull a single chart by ID (maps to --chart-id <id>)
    - chart_ids: pull multiple charts by comma-separated IDs (maps to --chart-ids "2085,2088,2090")
    Raises ValueError if both are provided.
    """

def push_charts(
    config: ToolkitConfig,
    assets_folder: Optional[str] = None,
    overwrite: bool = True,
    force: bool = True,
    continue_on_error: bool = False,
    load_env: bool = False,
) -> ChartPushResult:
    """Push chart definitions to workspace. Uses sup chart push."""
```

**Implementation pattern:** Each function builds a CLI args list from its kwargs, calls `run_sup()` with `--json` flag, parses the JSON stdout into the appropriate dataclass. Non-None kwargs map to `--flag value` pairs. Boolean flags (like `--mine`) are appended when True.

**Reuse:** Imports `run_sup` and `ensure_sup` from `scripts.sync`. As part of this sub-project, `_run_sup` and `_ensure_sup` will be renamed to `run_sup` and `ensure_sup` (public API) since they are now used by multiple modules. Backward-compatible aliases (`_run_sup = run_sup`, `_ensure_sup = ensure_sup`) will be kept in sync.py to avoid breaking any existing internal callers.

### 2. Result Dataclasses (in `scripts/chart.py`)

```python
@dataclass
class ChartSummary:
    """Single chart in a list result."""
    id: int
    name: str
    viz_type: str
    dataset_name: str = ""
    modified: str = ""

@dataclass
class ChartListResult:
    success: bool
    charts: List[ChartSummary]
    total: int = 0
    error: str = ""

@dataclass
class ChartInfo:
    success: bool
    id: int = 0
    name: str = ""
    viz_type: str = ""
    dataset_name: str = ""
    query_context: str = ""
    params: str = ""
    raw: dict = field(default_factory=dict)
    error: str = ""

@dataclass
class ChartSQL:
    success: bool
    sql: str = ""
    error: str = ""

@dataclass
class ChartData:
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[dict] = field(default_factory=list)
    row_count: int = 0
    error: str = ""

@dataclass
class ChartPullResult:
    success: bool
    charts_pulled: int = 0
    files: List[str] = field(default_factory=list)
    error: str = ""

@dataclass
class ChartPushResult:
    success: bool
    charts_pushed: int = 0
    errors: List[str] = field(default_factory=list)
    error: str = ""
```

### 3. JSON Parsing Strategy

All chart commands support `--json` output. The parser extracts known fields into dataclass attributes and preserves the full response in `raw` (for `ChartInfo`) or ignores unknown fields (for simpler types).

**Error handling:** If `run_sup()` returns non-zero, set `success=False` and populate `error` from stderr. If JSON parsing fails (unexpected format), set `success=False` with a parse error message and preserve `raw_output` where available.

**Key field mappings from sup JSON output:**
- `ChartSummary`: `id`, `slice_name` -> `name`, `viz_type`, `datasource_name_text` -> `dataset_name`, `changed_on_utc` -> `modified`
- `ChartInfo`: Same as summary plus `query_context`, `params` (both kept as raw JSON strings)
- `ChartSQL`: `result` -> `sql`
- `ChartData`: `columns` (list of column name strings), `data` (list of row dicts), `rowcount` -> `row_count`

These field names are based on Superset's REST API response format which sup mirrors. If field names differ, the parser falls back gracefully (empty defaults, no crash).

### 4. Formatter Extension

Extend `scripts/formatter.py` to handle chart result types:

- `ChartListResult` table format: `ID | Name | Type | Dataset | Modified` columns
- `ChartInfo` table format: key-value display of chart metadata
- `ChartSQL` table format: syntax-highlighted SQL block (plain text, no ANSI for SQL itself)
- `ChartData` table format: columnar data table with row count footer
- `ChartPullResult` / `ChartPushResult` table format: summary with file/chart count

JSON and YAML formats use `dataclasses.asdict()` as before.

### 5. New Skill: `skills/preset-chart/SKILL.md`

Routes natural language chart operations:
- "list my charts" -> `list_charts(mine=True)`
- "show chart 2085" -> `get_chart_info(chart_id=2085)`
- "what SQL does chart 2085 use?" -> `get_chart_sql(chart_id=2085)`
- "get data from chart 2088" -> `get_chart_data(chart_id=2088)`
- "pull chart 2085" -> `pull_charts(chart_id=2085)`
- "push charts" -> `push_charts()`

The skill follows the same conversation principles as other skills: never ask technical questions, only business-relevant ones.

The router skill (`skills/preset/SKILL.md`) will be updated to route chart-related intents to this skill.

## What We're NOT Doing

- **Not replacing `sup sync` for dashboard-level operations** — `chart pull/push` is for individual charts; `sync` remains for full dashboard sync
- **Not caching chart list results** — fresh data every call
- **Not adding chart CRUD (create/delete)** — sup doesn't support it; charts are created via Preset UI or sync push
- **Not parsing `--porcelain` output** — `--json` gives us structured data directly

## Impact on Existing Code

| File | Change | Breaking? |
|------|--------|-----------|
| `scripts/chart.py` | New file | No |
| `scripts/formatter.py` | Add table formatters for chart result types | No |
| `scripts/sync.py` | Rename `_run_sup`/`_ensure_sup` to public `run_sup`/`ensure_sup`; add backward-compat aliases | No |
| `skills/preset-chart/SKILL.md` | New skill | No |
| `skills/preset/SKILL.md` | Add chart routing | No |
| `tests/test_chart.py` | New file | No |
| `tests/test_formatter.py` | Add chart formatter tests | No |

## Testing Strategy

- **Unit tests for each function** — mock `run_sup()` to return known JSON stdout, verify dataclass population
- **Filter building tests** — verify each kwarg maps to the correct CLI flag
- **Mutual exclusivity tests** — `pull_charts(chart_id=1, chart_ids="1,2")` raises `ValueError`
- **Error handling tests** — non-zero return code, malformed JSON, missing fields
- **Formatter tests** — table/json/yaml rendering for each chart result type
- **Integration boundary** — no live sup calls in tests; all mocked

## Dependencies

No new dependencies. Uses:
- `json` (stdlib) — for parsing sup's `--json` output
- `dataclasses` (stdlib)
- `scripts.sync.run_sup` — existing retry/discovery infrastructure (renamed from `_run_sup` to public API)
