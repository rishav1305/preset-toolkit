# SQL Execution — Design Spec

**Sub-project:** 4 of 6 (sup CLI capabilities expansion)
**Date:** 2026-03-15
**Status:** Approved

---

## Goal

Expose `sup sql` as a structured Python function with typed results, database ID auto-resolution, formatter integration, and a new skill for natural language access.

## Current State

- No way to execute arbitrary SQL against Preset databases from the toolkit
- `sup sql` CLI accepts a query string, `--database-id`, `--limit`, `--json` flags
- `scripts/chart.py` and `scripts/dataset.py` provide the established thin-wrapper pattern
- `scripts/formatter.py` handles table/json/yaml output for chart and dataset result types
- `scripts/sync.py` exports `run_sup` for CLI invocation with retry logic
- Sync folder contains `assets/databases/*.yaml` files with database connection configs after a pull

## Architecture

### 1. New Module: `scripts/sql.py`

One public function, one helper, and two dataclasses:

```python
from typing import Optional, List
from dataclasses import dataclass, field

@dataclass
class SqlResult:
    """Result of executing a SQL query."""
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[dict] = field(default_factory=list)
    row_count: int = 0
    error: str = ""

def resolve_database_id(config: ToolkitConfig) -> Optional[int]:
    """Scan sync folder's databases/ dir for the first database YAML and extract its ID.

    Reads each YAML file in <sync_folder>/assets/databases/, looks for an 'id'
    field, and returns the first one found. Returns None if no database files
    exist or none contain an ID.
    """

def execute_sql(
    config: ToolkitConfig,
    query: str,
    database_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> SqlResult:
    """Execute a SQL query via sup sql --json.

    If database_id is None, calls resolve_database_id() to auto-detect from
    the sync folder. If resolution also returns None, executes without
    --database-id (sup will use its configured default).
    """
```

**Implementation pattern:** Same thin-wrapper as `scripts/chart.py` and `scripts/dataset.py`. Builds a CLI args list from kwargs, calls `run_sup()` with `--json`, parses JSON stdout into `SqlResult`.

**Reuse:** Imports `run_sup` from `scripts.sync` and `ToolkitConfig` from `scripts.config`.

### 2. CLI Mapping

```
execute_sql(config, "SELECT * FROM orders", database_id=5, limit=100)
  → sup sql "SELECT * FROM orders" --database-id 5 --limit 100 --json
```

| Python kwarg | CLI flag | Behavior |
|---|---|---|
| `query` | positional arg | Required — the SQL string |
| `database_id` | `--database-id <id>` | Optional — auto-resolved if None |
| `limit` | `--limit <n>` | Optional — sup defaults to 1000 |

### 3. Database ID Auto-Resolution

`resolve_database_id(config)` scans `<config.sync_folder>/assets/databases/` for YAML files. Each database YAML pulled by `sup sync` contains an `id` field. The helper reads the first file found and extracts the ID.

**Edge cases:**
- No databases/ directory → return None
- Empty directory → return None
- YAML without `id` field → skip, try next file
- Multiple databases → return the first one found (deterministic via sorted glob)

When `resolve_database_id()` returns None, `execute_sql()` omits `--database-id` entirely, letting sup use its own default.

### 4. JSON Parsing Strategy

Same as chart/dataset operations. `sup sql --json` returns structured output.

**Key field mappings from sup JSON output:**
- `columns` → list of column name strings
- `data` → list of row dicts (each key is a column name)
- `rowcount` → `row_count`

**Error handling:** If `run_sup()` returns non-zero, set `success=False` and populate `error` from stderr. If JSON parsing fails, set `success=False` with a parse error message.

### 5. Formatter Extension

Extend `scripts/formatter.py` to handle `SqlResult`:

- `SqlResult` table format: columnar data table with column headers, separator, rows, and row count footer — same layout as `_format_table_chart_data` and `_format_table_dataset_data`
- Error display: if `success=False`, show error message
- Empty result: show "No rows returned."

JSON and YAML formats use `dataclasses.asdict()` as before.

### 6. New Skill: `skills/preset-sql/SKILL.md`

Routes natural language SQL operations:
- "run SELECT * FROM orders" → `execute_sql(config, query="SELECT * FROM orders")`
- "query the database for active users" → `execute_sql(config, query="SELECT * FROM users WHERE active = 1")`
- "execute this SQL: ..." → `execute_sql(config, query="...")`
- "run this on database 5: SELECT 1" → `execute_sql(config, query="SELECT 1", database_id=5)`

The router skill (`skills/preset/SKILL.md`) will be updated to route SQL-related intents to this skill.

## What We're NOT Doing

- **Not wrapping `sup database list/info/use`** — database management is a separate concern; defer to a future sub-project if needed
- **Not supporting `--interactive` mode** — interactive sessions don't fit the function-call pattern
- **Not supporting `--csv` or `--yaml` output from sup** — we always use `--json` for parsing, then format locally via `format_output()`
- **Not caching database ID resolution** — fresh scan every call (sync folder may change between calls)
- **Not supporting multi-statement SQL** — sup handles this; we pass through as-is

## Impact on Existing Code

| File | Change | Breaking? |
|------|--------|-----------|
| `scripts/sql.py` | New file | No |
| `scripts/formatter.py` | Add table formatter for SqlResult | No |
| `skills/preset-sql/SKILL.md` | New skill | No |
| `skills/preset/SKILL.md` | Add sql routing | No |
| `tests/test_sql.py` | New file | No |
| `tests/test_formatter.py` | Add sql formatter tests | No |

## Testing Strategy

- **Unit tests for `execute_sql`** — mock `run_sup()` to return known JSON stdout, verify SqlResult population
- **Unit tests for `resolve_database_id`** — create temp directories with/without database YAML files, verify ID extraction and edge cases
- **Flag building tests** — verify `database_id` and `limit` map to correct CLI flags
- **Auto-resolution integration** — verify `execute_sql` calls `resolve_database_id` when `database_id` is None
- **Error handling tests** — non-zero return code, malformed JSON, missing fields
- **Formatter tests** — table/json/yaml rendering for SqlResult
- **Integration boundary** — no live sup calls in tests; all mocked

## Dependencies

No new dependencies. Uses:
- `json` (stdlib) — for parsing sup's `--json` output
- `dataclasses` (stdlib)
- `pathlib` (stdlib) — for scanning database YAML files
- `yaml` — for reading database YAML files (already a project dependency)
- `scripts.sync.run_sup` — existing retry/discovery infrastructure
