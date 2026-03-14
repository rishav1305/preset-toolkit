# Dataset Operations — Design Spec

**Sub-project:** 3 of 6 (sup CLI capabilities expansion)
**Date:** 2026-03-15
**Status:** Approved

---

## Goal

Expose all 6 `sup dataset` commands (list, info, sql, data, pull, push) as structured Python functions with typed results, a new skill for natural language access, and formatter integration.

## Current State

- Datasets are handled only as part of full dashboard sync via `sup sync run`
- No way to list, inspect, query, or operate on individual datasets
- `scripts/chart.py` provides the established pattern for wrapping `sup` subcommands
- `scripts/formatter.py` provides table/json/yaml output formatting for chart and sync result types
- `scripts/sync.py` exports `run_sup` (public API) for CLI invocation with retry logic
- sup CLI supports `--json` output for all dataset commands

## Architecture

### 1. New Module: `scripts/dataset.py`

Six public functions, each wrapping a `sup dataset` subcommand:

```python
from typing import Optional, List

def list_datasets(
    config: ToolkitConfig,
    search: Optional[str] = None,
    database_id: Optional[int] = None,
    mine: bool = False,
    modified_after: Optional[str] = None,
    limit: Optional[int] = None,
    order: Optional[str] = None,
    desc: bool = False,
) -> DatasetListResult:
    """List datasets with optional filtering. Uses sup dataset list --json."""

def get_dataset_info(config: ToolkitConfig, dataset_id: int) -> DatasetInfo:
    """Get detailed metadata for a dataset. Uses sup dataset info <id> --json."""

def get_dataset_sql(config: ToolkitConfig, dataset_id: int) -> DatasetSQL:
    """Get the SQL definition for a dataset. Uses sup dataset sql <id> --json."""

def get_dataset_data(
    config: ToolkitConfig, dataset_id: int, limit: Optional[int] = None,
) -> DatasetData:
    """Get sample data from a dataset. Uses sup dataset data <id> --json."""

def pull_datasets(
    config: ToolkitConfig,
    dataset_id: Optional[int] = None,
    dataset_ids: Optional[List[int]] = None,
    name: Optional[str] = None,
    mine: bool = False,
    modified_after: Optional[str] = None,
    limit: Optional[int] = None,
    skip_dependencies: bool = False,
    overwrite: bool = True,
    assets_folder: Optional[str] = None,
) -> DatasetPullResult:
    """Pull dataset definitions to local filesystem. Uses sup dataset pull.

    dataset_id and dataset_ids are mutually exclusive. Provide one or neither:
    - dataset_id: pull a single dataset by ID (maps to --dataset-id <id>)
    - dataset_ids: pull multiple datasets by ID list (maps to --dataset-ids "1,2,3")
    Raises ValueError if both are provided.
    """

def push_datasets(
    config: ToolkitConfig,
    assets_folder: Optional[str] = None,
    overwrite: bool = True,
    force: bool = True,
    continue_on_error: bool = False,
    load_env: bool = False,
) -> DatasetPushResult:
    """Push dataset definitions to workspace. Uses sup dataset push."""
```

**Implementation pattern:** Identical to `scripts/chart.py`. Each function builds a CLI args list from its kwargs, calls `run_sup()` with `--json` flag, parses the JSON stdout into the appropriate dataclass.

**Reuse:** Imports `run_sup` from `scripts.sync` and `ToolkitConfig` from `scripts.config`.

### 2. Result Dataclasses (in `scripts/dataset.py`)

```python
@dataclass
class DatasetSummary:
    """Single dataset in a list result."""
    id: int
    name: str
    database: str = ""
    schema: str = ""
    modified: str = ""

@dataclass
class DatasetListResult:
    success: bool
    datasets: List[DatasetSummary] = field(default_factory=list)
    total: int = 0
    error: str = ""

@dataclass
class DatasetInfo:
    success: bool
    id: int = 0
    name: str = ""
    database: str = ""
    schema: str = ""
    sql: str = ""
    columns: List[dict] = field(default_factory=list)
    metrics: List[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    error: str = ""

@dataclass
class DatasetSQL:
    success: bool
    sql: str = ""
    error: str = ""

@dataclass
class DatasetData:
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[dict] = field(default_factory=list)
    row_count: int = 0
    error: str = ""

@dataclass
class DatasetPullResult:
    success: bool
    datasets_pulled: int = 0
    files: List[str] = field(default_factory=list)
    error: str = ""

@dataclass
class DatasetPushResult:
    success: bool
    datasets_pushed: int = 0
    errors: List[str] = field(default_factory=list)
    error: str = ""
```

### 3. JSON Parsing Strategy

Same as chart operations. All dataset commands support `--json` output.

**Error handling:** If `run_sup()` returns non-zero, set `success=False` and populate `error` from stderr. If JSON parsing fails, set `success=False` with a parse error message.

**Key field mappings from sup JSON output:**
- `DatasetSummary`: `id`, `table_name` → `name`, `database_name` → `database`, `schema` → `schema`, `changed_on_utc` → `modified`
- `DatasetInfo`: Same as summary plus `sql`, `columns` (list of column dicts), `metrics` (list of metric dicts)
- `DatasetSQL`: `result` → `sql`
- `DatasetData`: `columns` (list of column name strings), `data` (list of row dicts), `rowcount` → `row_count`

### 4. Formatter Extension

Extend `scripts/formatter.py` to handle dataset result types:

- `DatasetListResult` table format: `ID | Name | Database | Schema | Modified` columns
- `DatasetInfo` table format: key-value display of dataset metadata
- `DatasetSQL` table format: SQL text block
- `DatasetData` table format: columnar data table with row count footer
- `DatasetPullResult` / `DatasetPushResult` table format: summary with file/dataset count

JSON and YAML formats use `dataclasses.asdict()` as before.

### 5. New Skill: `skills/preset-dataset/SKILL.md`

Routes natural language dataset operations:
- "list datasets" → `list_datasets(config)`
- "show dataset 42" → `get_dataset_info(config, dataset_id=42)`
- "what SQL does dataset 42 use?" → `get_dataset_sql(config, dataset_id=42)`
- "get data from dataset 42" → `get_dataset_data(config, dataset_id=42)`
- "pull dataset 42" → `pull_datasets(config, dataset_id=42)`
- "push datasets" → `push_datasets(config)`

The router skill (`skills/preset/SKILL.md`) will be updated to route dataset-related intents to this skill.

## What We're NOT Doing

- **Not replacing `sup sync` for dashboard-level operations** — `dataset pull/push` is for individual datasets; `sync` remains for full dashboard sync
- **Not caching dataset list results** — fresh data every call
- **Not adding dataset CRUD (create/delete)** — sup doesn't support it
- **Not duplicating the shared `_parse_chart_summary` helper** — dataset has its own `_parse_dataset_summary` with different field mappings

## Impact on Existing Code

| File | Change | Breaking? |
|------|--------|-----------|
| `scripts/dataset.py` | New file | No |
| `scripts/formatter.py` | Add table formatters for dataset result types | No |
| `skills/preset-dataset/SKILL.md` | New skill | No |
| `skills/preset/SKILL.md` | Add dataset routing | No |
| `tests/test_dataset.py` | New file | No |
| `tests/test_formatter.py` | Add dataset formatter tests | No |

## Testing Strategy

- **Unit tests for each function** — mock `run_sup()` to return known JSON stdout, verify dataclass population
- **Filter building tests** — verify each kwarg maps to the correct CLI flag
- **Mutual exclusivity tests** — `pull_datasets(dataset_id=1, dataset_ids=[1, 2])` raises `ValueError`
- **Error handling tests** — non-zero return code, malformed JSON, missing fields
- **Formatter tests** — table/json/yaml rendering for each dataset result type
- **Integration boundary** — no live sup calls in tests; all mocked

## Dependencies

No new dependencies. Uses:
- `json` (stdlib) — for parsing sup's `--json` output
- `dataclasses` (stdlib)
- `scripts.sync.run_sup` — existing retry/discovery infrastructure
