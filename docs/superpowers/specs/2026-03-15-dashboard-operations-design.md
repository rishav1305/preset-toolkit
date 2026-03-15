# Dashboard Operations — Design Spec

**Sub-project:** 5 of 6 (sup CLI capabilities expansion)
**Date:** 2026-03-15
**Status:** Approved

---

## Goal

Expose `sup dashboard` subcommands (list, info, pull) as structured Python functions with typed results, formatter integration, and a new skill for natural language access.

## Current State

- Dashboards are handled only as part of full sync via `sup sync run`
- No way to list, inspect, or pull individual dashboards independently
- `sup dashboard` CLI has 3 subcommands: `list`, `info`, `pull` (no `push` — push uses REST API via `push_dashboard.py`)
- `scripts/chart.py` and `scripts/dataset.py` provide the established thin-wrapper pattern
- `scripts/formatter.py` handles table/json/yaml output for chart, dataset, and sql result types
- `scripts/sync.py` exports `run_sup` for CLI invocation with retry logic

## Architecture

### 1. New Module: `scripts/dashboard.py`

Three public functions and four dataclasses:

```python
import json
from dataclasses import dataclass, field
from typing import List, Optional

from scripts.config import ToolkitConfig
from scripts.sync import run_sup


@dataclass
class DashboardSummary:
    """Single dashboard in a list result."""
    id: int
    name: str
    status: str = ""
    url: str = ""
    modified: str = ""


@dataclass
class DashboardListResult:
    """Result from list_dashboards()."""
    success: bool
    dashboards: List[DashboardSummary] = field(default_factory=list)
    total: int = 0
    error: str = ""


@dataclass
class DashboardInfo:
    """Detailed metadata for a single dashboard."""
    success: bool
    id: int = 0
    name: str = ""
    status: str = ""
    url: str = ""
    slug: str = ""
    charts: List[dict] = field(default_factory=list)
    css: str = ""
    raw: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class DashboardPullResult:
    """Result from pull_dashboards()."""
    success: bool
    dashboards_pulled: int = 0
    files: List[str] = field(default_factory=list)
    error: str = ""


def _parse_dashboard_summary(item: dict) -> DashboardSummary:
    """Parse a single dashboard dict from sup JSON output."""


def list_dashboards(
    config: ToolkitConfig,
    search: Optional[str] = None,
    mine: bool = False,
    published: bool = False,
    draft: bool = False,
    folder: Optional[str] = None,
    limit: Optional[int] = None,
) -> DashboardListResult:
    """List dashboards with optional filtering. Uses sup dashboard list --json."""


def get_dashboard_info(config: ToolkitConfig, dashboard_id: int) -> DashboardInfo:
    """Get detailed metadata for a dashboard. Uses sup dashboard info <id> --json."""


def pull_dashboards(
    config: ToolkitConfig,
    dashboard_id: Optional[int] = None,
    dashboard_ids: Optional[List[int]] = None,
    search: Optional[str] = None,
    mine: bool = False,
    limit: Optional[int] = None,
    skip_dependencies: bool = False,
    overwrite: bool = True,
    assets_folder: Optional[str] = None,
) -> DashboardPullResult:
    """Pull dashboard definitions to local filesystem. Uses sup dashboard pull.

    dashboard_id and dashboard_ids are mutually exclusive. Provide one or neither:
    - dashboard_id: pull a single dashboard by ID (maps to --id <id>)
    - dashboard_ids: pull multiple dashboards by ID list (maps to --ids "1,2,3")
    Raises ValueError if both are provided.
    """
```

**Implementation pattern:** Identical to `scripts/chart.py` and `scripts/dataset.py`. Each function builds a CLI args list from its kwargs, calls `run_sup()` with `--json`, parses the JSON stdout into the appropriate dataclass.

**Reuse:** Imports `run_sup` from `scripts.sync` and `ToolkitConfig` from `scripts.config`.

### 2. CLI Mapping

| Python kwarg | CLI flag | Functions |
|---|---|---|
| `search` | `--search <text>` | list, pull |
| `mine` | `--mine` | list, pull |
| `published` | `--published` | list |
| `draft` | `--draft` | list |
| `folder` | `--folder <pattern>` | list |
| `limit` | `--limit <n>` | list, pull |
| `dashboard_id` | `--id <id>` | pull |
| `dashboard_ids` | `--ids "1,2,3"` | pull |
| `skip_dependencies` | `--skip-dependencies` | pull |
| `overwrite` | `--overwrite` (True) / omitted (False) | pull |
| `assets_folder` | positional arg | pull |

Note: `pull_dashboards` uses `--id` and `--ids` (not `--dashboard-id`/`--dashboard-ids` like the dataset module). This matches the actual `sup dashboard pull` CLI flags.

### 3. JSON Parsing Strategy

Same as chart/dataset operations. All dashboard commands support `--json` output.

**Key field mappings from sup JSON output:**
- `DashboardSummary`: `id`, `dashboard_title` → `name`, `status` → `status` (published/draft), `url` → `url`, `changed_on_utc` → `modified`
- `DashboardInfo`: Same as summary plus `slug`, `charts` (list of chart dicts), `css`, and the full raw dict
- `DashboardPullResult`: `dashboards_pulled` (count), `files` (list of paths)

**Error handling:** If `run_sup()` returns non-zero, set `success=False` and populate `error` from stderr. If JSON parsing fails, set `success=False` with a parse error message.

### 4. Formatter Extension

Extend `scripts/formatter.py` to handle dashboard result types:

- Import `DashboardListResult`, `DashboardInfo`, `DashboardPullResult` from `scripts.dashboard`
- Add `_format_table_dashboard_list(result: DashboardListResult) -> str`: `ID | Name | Status | URL | Modified` columns
- Add `_format_table_dashboard_info(result: DashboardInfo) -> str`: key-value display of dashboard metadata
- Add `_format_table_dashboard_pull(result: DashboardPullResult) -> str`: summary with dashboard/file count
- Add `isinstance` branches to `format_output()` dispatch chain

JSON and YAML formats use `dataclasses.asdict()` as before.

### 5. New Skill: `skills/preset-dashboard/SKILL.md`

Routes natural language dashboard operations:
- "list dashboards" → `list_dashboards(config)`
- "show dashboard 76" → `get_dashboard_info(config, dashboard_id=76)`
- "pull dashboard 76" → `pull_dashboards(config, dashboard_id=76)`
- "list my dashboards" → `list_dashboards(config, mine=True)`
- "find sales dashboards" → `list_dashboards(config, search="sales")`

The router skill (`skills/preset/SKILL.md`) will be updated to route dashboard-related intents to this skill.

## What We're NOT Doing

- **Not adding a `push_dashboards` function** — dashboard push uses REST API (`push_dashboard.py`), not `sup dashboard push` (which doesn't exist)
- **Not duplicating sync functionality** — `pull_dashboards` is for individual dashboard operations; `sup sync` remains for full dashboard sync
- **Not caching dashboard list results** — fresh data every call
- **Not adding dashboard CRUD (create/delete)** — sup doesn't support it

## Impact on Existing Code

| File | Change | Breaking? |
|------|--------|-----------|
| `scripts/dashboard.py` | New file | No |
| `scripts/formatter.py` | Add table formatters for dashboard result types | No |
| `skills/preset-dashboard/SKILL.md` | New skill | No |
| `skills/preset/SKILL.md` | Add dashboard routing | No |
| `tests/test_dashboard.py` | New file | No |
| `tests/test_formatter.py` | Add dashboard formatter tests | No |

## Testing Strategy

- **Unit tests for each function** — mock `run_sup()` to return known JSON stdout, verify dataclass population
- **Filter building tests** — verify each kwarg maps to the correct CLI flag
- **Mutual exclusivity tests** — `pull_dashboards(dashboard_id=1, dashboard_ids=[1, 2])` raises `ValueError`
- **Error handling tests** — non-zero return code, malformed JSON, missing fields
- **Formatter tests** — table/json/yaml rendering for each dashboard result type
- **Integration boundary** — no live sup calls in tests; all mocked

## Dependencies

No new dependencies. Uses:
- `json` (stdlib) — for parsing sup's `--json` output
- `dataclasses` (stdlib)
- `scripts.sync.run_sup` — existing retry/discovery infrastructure
