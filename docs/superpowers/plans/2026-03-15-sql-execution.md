# SQL Execution Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose `sup sql` as a structured Python function with database ID auto-resolution, typed results, formatter integration, and NLP skill.

**Architecture:** Single module `scripts/sql.py` with one dataclass (`SqlResult`), one helper (`resolve_database_id`), and one public function (`execute_sql`). Follows the thin-wrapper pattern from `scripts/chart.py` and `scripts/dataset.py`.

**Tech Stack:** Python 3.8+, PyYAML, dataclasses, scripts.sync.run_sup

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/sql.py` | Create | SqlResult dataclass, resolve_database_id helper, execute_sql function |
| `scripts/formatter.py` | Modify | Add `_format_table_sql_result` + dispatch branch |
| `skills/preset-sql/SKILL.md` | Create | NLP routing for SQL execution intents |
| `skills/preset/SKILL.md` | Modify | Add sql menu item + routing row + NLP examples |
| `tests/test_sql.py` | Create | Unit tests for sql module |
| `tests/test_formatter.py` | Modify | Add sql formatter tests |
| `.claude-plugin/marketplace.json` | Modify | Version bump to 0.9.0 |
| `README.md` | Modify | Version, test count, skill count, architecture tree |

---

## Chunk 1: Core Module

### Task 1: SqlResult Dataclass

**Files:**
- Create: `scripts/sql.py`
- Create: `tests/test_sql.py`

- [ ] **Step 1: Create test file with dataclass construction test**

Create `tests/test_sql.py`:

```python
"""Tests for SQL execution module."""
import json as json_mod
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from scripts.sql import SqlResult


def test_sql_result_creation():
    """SqlResult holds query execution results."""
    result = SqlResult(
        success=True,
        columns=["id", "name", "amount"],
        rows=[{"id": 1, "name": "Alice", "amount": 100}],
        row_count=1,
    )
    assert result.success is True
    assert result.columns == ["id", "name", "amount"]
    assert len(result.rows) == 1
    assert result.row_count == 1
    assert result.error == ""


def test_sql_result_defaults():
    """SqlResult defaults to empty collections."""
    result = SqlResult(success=False, error="something broke")
    assert result.columns == []
    assert result.rows == []
    assert result.row_count == 0
    assert result.error == "something broke"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sql.py::test_sql_result_creation tests/test_sql.py::test_sql_result_defaults -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.sql'`

- [ ] **Step 3: Create scripts/sql.py with SqlResult dataclass**

Create `scripts/sql.py`:

```python
"""SQL execution: run arbitrary queries against Preset databases.

Wraps sup sql command as a structured Python function.
Calls run_sup() with --json and parses the output into a typed dataclass.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

from scripts.config import ToolkitConfig
from scripts.sync import run_sup


@dataclass
class SqlResult:
    """Result of executing a SQL query."""
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[dict] = field(default_factory=list)
    row_count: int = 0
    error: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_sql.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/sql.py tests/test_sql.py
git commit -m "feat: SqlResult dataclass for SQL execution"
```

---

### Task 2: resolve_database_id Helper

**Files:**
- Modify: `scripts/sql.py`
- Modify: `tests/test_sql.py`

- [ ] **Step 1: Add resolve_database_id tests**

Append to `tests/test_sql.py`:

```python
from scripts.sql import SqlResult, resolve_database_id
from scripts.config import ToolkitConfig


def _make_sql_config(tmp_path):
    """Helper to create a minimal ToolkitConfig for sql tests."""
    config_dir = tmp_path / ".preset-toolkit"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(yaml.safe_dump({
        "version": 1,
        "workspace": {"url": "https://test.preset.io", "id": "test123"},
        "dashboard": {"id": 1, "name": "Test"},
    }))
    return ToolkitConfig.load(config_path)


def test_resolve_database_id_from_yaml(tmp_path):
    """resolve_database_id extracts ID from first database YAML file."""
    cfg = _make_sql_config(tmp_path)
    db_dir = tmp_path / "sync" / "assets" / "databases"
    db_dir.mkdir(parents=True)
    (db_dir / "analytics_db.yaml").write_text(yaml.safe_dump({"id": 5, "database_name": "analytics_db"}))
    result = resolve_database_id(cfg)
    assert result == 5


def test_resolve_database_id_no_directory(tmp_path):
    """resolve_database_id returns None when databases/ doesn't exist."""
    cfg = _make_sql_config(tmp_path)
    result = resolve_database_id(cfg)
    assert result is None


def test_resolve_database_id_empty_directory(tmp_path):
    """resolve_database_id returns None when databases/ is empty."""
    cfg = _make_sql_config(tmp_path)
    db_dir = tmp_path / "sync" / "assets" / "databases"
    db_dir.mkdir(parents=True)
    result = resolve_database_id(cfg)
    assert result is None


def test_resolve_database_id_no_id_field(tmp_path):
    """resolve_database_id skips YAML files without id field."""
    cfg = _make_sql_config(tmp_path)
    db_dir = tmp_path / "sync" / "assets" / "databases"
    db_dir.mkdir(parents=True)
    (db_dir / "bad_db.yaml").write_text(yaml.safe_dump({"database_name": "bad"}))
    result = resolve_database_id(cfg)
    assert result is None


def test_resolve_database_id_malformed_yaml(tmp_path):
    """resolve_database_id skips malformed YAML files."""
    cfg = _make_sql_config(tmp_path)
    db_dir = tmp_path / "sync" / "assets" / "databases"
    db_dir.mkdir(parents=True)
    (db_dir / "corrupt.yaml").write_text(":::not valid yaml[[[")
    result = resolve_database_id(cfg)
    assert result is None


def test_resolve_database_id_sorted_determinism(tmp_path):
    """resolve_database_id returns ID from first file alphabetically."""
    cfg = _make_sql_config(tmp_path)
    db_dir = tmp_path / "sync" / "assets" / "databases"
    db_dir.mkdir(parents=True)
    (db_dir / "a_db.yaml").write_text(yaml.safe_dump({"id": 10}))
    (db_dir / "z_db.yaml").write_text(yaml.safe_dump({"id": 99}))
    result = resolve_database_id(cfg)
    assert result == 10
```

Also update the import at the top of the file to include `resolve_database_id` and `_make_sql_config` helper. Move the `_make_sql_config` helper and imports to the top of the file (after existing imports).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_sql.py::test_resolve_database_id_from_yaml -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_database_id'`

- [ ] **Step 3: Implement resolve_database_id in scripts/sql.py**

Append to `scripts/sql.py` after the SqlResult dataclass:

```python
def resolve_database_id(config: ToolkitConfig) -> Optional[int]:
    """Scan sync folder's databases/ dir for the first database YAML and extract its ID.

    Reads each YAML file in <sync_folder>/assets/databases/ (sorted for
    determinism), looks for a top-level 'id' field, and returns the first
    one found. Returns None if no database files exist or none contain an ID.
    """
    db_dir = config.project_root / config.sync_assets_path / "databases"
    if not db_dir.is_dir():
        return None
    for db_file in sorted(db_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(db_file.read_text())
        except (yaml.YAMLError, OSError):
            continue
        if isinstance(data, dict) and "id" in data:
            return int(data["id"])
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_sql.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/sql.py tests/test_sql.py
git commit -m "feat: resolve_database_id() with YAML scanning and edge case handling"
```

---

### Task 3: execute_sql Function

**Files:**
- Modify: `scripts/sql.py`
- Modify: `tests/test_sql.py`

- [ ] **Step 1: Add execute_sql tests**

Append to `tests/test_sql.py`:

```python
from scripts.sql import SqlResult, resolve_database_id, execute_sql


def test_execute_sql_success(tmp_path):
    """execute_sql parses JSON output into SqlResult."""
    cfg = _make_sql_config(tmp_path)
    sup_json = json_mod.dumps({
        "columns": ["id", "name", "amount"],
        "data": [
            {"id": 1, "name": "Alice", "amount": 100},
            {"id": 2, "name": "Bob", "amount": 200},
        ],
        "rowcount": 2,
    })
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = execute_sql(cfg, query="SELECT * FROM orders")

    assert result.success is True
    assert result.columns == ["id", "name", "amount"]
    assert len(result.rows) == 2
    assert result.rows[0]["name"] == "Alice"
    assert result.row_count == 2

    args = mock_sup.call_args[0][0]
    assert "sql" in args
    assert "SELECT * FROM orders" in args
    assert "--json" in args


def test_execute_sql_with_database_id(tmp_path):
    """execute_sql passes --database-id when explicitly provided."""
    cfg = _make_sql_config(tmp_path)
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout='{"columns":[],"data":[],"rowcount":0}', stderr="")
        execute_sql(cfg, query="SELECT 1", database_id=5)

    args = mock_sup.call_args[0][0]
    assert "--database-id" in args
    assert "5" in args


def test_execute_sql_with_limit(tmp_path):
    """execute_sql passes --limit flag when specified."""
    cfg = _make_sql_config(tmp_path)
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout='{"columns":[],"data":[],"rowcount":0}', stderr="")
        execute_sql(cfg, query="SELECT 1", limit=50)

    args = mock_sup.call_args[0][0]
    assert "--limit" in args
    assert "50" in args


def test_execute_sql_auto_resolves_database_id(tmp_path):
    """execute_sql calls resolve_database_id when database_id is None."""
    cfg = _make_sql_config(tmp_path)
    db_dir = tmp_path / "sync" / "assets" / "databases"
    db_dir.mkdir(parents=True)
    (db_dir / "analytics_db.yaml").write_text(yaml.safe_dump({"id": 7}))
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout='{"columns":[],"data":[],"rowcount":0}', stderr="")
        execute_sql(cfg, query="SELECT 1")

    args = mock_sup.call_args[0][0]
    assert "--database-id" in args
    assert "7" in args


def test_execute_sql_no_database_id_available(tmp_path):
    """execute_sql omits --database-id when resolution returns None."""
    cfg = _make_sql_config(tmp_path)
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout='{"columns":[],"data":[],"rowcount":0}', stderr="")
        execute_sql(cfg, query="SELECT 1")

    args = mock_sup.call_args[0][0]
    assert "--database-id" not in args


def test_execute_sql_sup_failure(tmp_path):
    """execute_sql returns error on sup failure."""
    cfg = _make_sql_config(tmp_path)
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="auth error")
        result = execute_sql(cfg, query="SELECT 1")

    assert result.success is False
    assert "auth error" in result.error


def test_execute_sql_malformed_json(tmp_path):
    """execute_sql handles malformed JSON gracefully."""
    cfg = _make_sql_config(tmp_path)
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
        result = execute_sql(cfg, query="SELECT 1")

    assert result.success is False
    assert "parse" in result.error.lower() or "json" in result.error.lower()
```

Update the import line at the top to include `execute_sql`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_sql.py::test_execute_sql_success -v`
Expected: FAIL with `ImportError: cannot import name 'execute_sql'`

- [ ] **Step 3: Implement execute_sql in scripts/sql.py**

Append to `scripts/sql.py` after `resolve_database_id`:

```python
def execute_sql(
    config: ToolkitConfig,
    query: str,
    database_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> SqlResult:
    """Execute a SQL query via sup sql --json.

    The query string is passed as a single list element to run_sup();
    no shell quoting needed.

    If database_id is None, calls resolve_database_id() to auto-detect from
    the sync folder. If resolution also returns None, executes without
    --database-id (sup will use its configured default).
    """
    args = ["sql", query, "--json"]

    resolved_db_id = database_id if database_id is not None else resolve_database_id(config)
    if resolved_db_id is not None:
        args.extend(["--database-id", str(resolved_db_id)])
    if limit is not None:
        args.extend(["--limit", str(limit)])

    r = run_sup(args)
    if r.returncode != 0:
        return SqlResult(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return SqlResult(success=False, error=f"JSON parse error: {e}")

    return SqlResult(
        success=True,
        columns=data.get("columns", []),
        rows=data.get("data", []),
        row_count=data.get("rowcount", 0),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_sql.py -v`
Expected: 16 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/sql.py tests/test_sql.py
git commit -m "feat: execute_sql() with auto-resolution, flag mapping, and JSON parsing"
```

---

## Chunk 2: Formatter + Skill + Finalization

### Task 4: Formatter Extension

**Files:**
- Modify: `scripts/formatter.py:1-336`
- Modify: `tests/test_formatter.py`

- [ ] **Step 1: Add formatter tests**

Append to `tests/test_formatter.py`:

```python
from scripts.sql import SqlResult

# ── SQL table format ─────────────────────────────────────────────────


def test_format_sql_result_table():
    """Table format renders SQL results as columnar data."""
    result = SqlResult(
        success=True,
        columns=["id", "name", "amount"],
        rows=[
            {"id": 1, "name": "Alice", "amount": 100},
            {"id": 2, "name": "Bob", "amount": 200},
        ],
        row_count=2,
    )
    output = format_output(result, fmt="table")
    assert "id" in output
    assert "name" in output
    assert "Alice" in output
    assert "2 row(s)" in output


def test_format_sql_result_empty_table():
    """Table format handles empty SQL results."""
    result = SqlResult(success=True, columns=[], rows=[], row_count=0)
    output = format_output(result, fmt="table")
    assert "No rows returned." in output


def test_format_sql_result_error():
    """Table format shows error message on failure."""
    result = SqlResult(success=False, error="auth error")
    output = format_output(result, fmt="table")
    assert "ERROR" in output
    assert "auth error" in output


def test_format_sql_result_json():
    """JSON format renders SqlResult as valid JSON."""
    result = SqlResult(success=True, columns=["id"], rows=[{"id": 1}], row_count=1)
    output = format_output(result, fmt="json")
    parsed = json.loads(output)
    assert parsed["success"] is True
    assert parsed["columns"] == ["id"]


def test_format_sql_result_yaml():
    """YAML format renders SqlResult as valid YAML."""
    result = SqlResult(success=True, columns=["id"], rows=[{"id": 1}], row_count=1)
    output = format_output(result, fmt="yaml")
    parsed = yaml.safe_load(output)
    assert parsed["success"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_formatter.py::test_format_sql_result_table -v`
Expected: FAIL (SqlResult not handled by format_output dispatch)

- [ ] **Step 3: Add SqlResult formatter to scripts/formatter.py**

Add import at top of `scripts/formatter.py` (after the dataset import block):

```python
from scripts.sql import SqlResult
```

Add table formatter function (after `_format_table_dataset_push`):

```python
def _format_table_sql_result(result: SqlResult) -> str:
    """Render SqlResult as a columnar table."""
    lines = []
    if result.columns:
        header = " | ".join(f"{col:<15}" for col in result.columns)
        lines.append(header)
        lines.append("-" * len(header))
        for row in result.rows:
            line = " | ".join(f"{str(row.get(col, '')):<15}" for col in result.columns)
            lines.append(line)
        lines.append("")
        lines.append(f"{result.row_count} row(s) returned.")
    else:
        lines.append("No rows returned.")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)
```

Add dispatch branch in `format_output()` (before the `else: return str(dataclasses.asdict(data))` line):

```python
        elif isinstance(data, SqlResult):
            return _format_table_sql_result(data)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_formatter.py -v`
Expected: all pass (previous 26 + 5 new = 31)

- [ ] **Step 5: Commit**

```bash
git add scripts/formatter.py tests/test_formatter.py
git commit -m "feat: formatter table/json/yaml support for SqlResult"
```

---

### Task 5: SQL Skill

**Files:**
- Create: `skills/preset-sql/SKILL.md`

- [ ] **Step 1: Create the skill file**

Create `skills/preset-sql/SKILL.md`:

```markdown
---
name: preset-sql
description: "Execute arbitrary SQL queries against Preset databases"
---

# SQL Execution

Execute SQL queries directly against Preset workspace databases via `sup sql`.

## Conversation Principles (MANDATORY)

**NEVER ask about:**
- Config formats, file paths, YAML structure, directory layout
- Which scripts to run, CLI flags, sync modes, technical parameters
- Auth methods, tokens, API endpoints, CSRF handling
- Git branches, merge strategies, commit messages
- Infrastructure, server details, environment setup

**ONLY ask about:**
- Business intent: "What data do you want to query?"
- Data correctness: "The query returned 1,200 rows. Does that look right?"
- Schema specifics: "Which table contains the order data?"
- Approval gates: "Run this query?"

## Prerequisites

` ` `python
from scripts.config import ToolkitConfig
from scripts.sql import execute_sql
from scripts.formatter import format_output

config = ToolkitConfig.discover()
` ` `

## Intent Routing

| User says | Function | Key args |
|-----------|----------|----------|
| "run SELECT * FROM orders", "execute this SQL" | `execute_sql(config, query="SELECT * FROM orders")` | |
| "query the database for active users" | `execute_sql(config, query="SELECT * FROM users WHERE active = 1")` | |
| "run this on database 5: SELECT 1" | `execute_sql(config, query="SELECT 1", database_id=5)` | |
| "show me the first 10 orders" | `execute_sql(config, query="SELECT * FROM orders", limit=10)` | |
| "how many active users?" | `execute_sql(config, query="SELECT COUNT(*) FROM users WHERE active = 1")` | |
| "show me the orders table" | `execute_sql(config, query="SELECT * FROM orders", limit=100)` | |

## Execution

1. Parse user intent and extract SQL query, optional database_id, optional limit
2. Call `execute_sql(config, query=..., database_id=..., limit=...)`
3. Display results using `format_output(result, fmt="table")`
4. For errors, explain what went wrong in business terms

## Output Formatting

Use `format_output()` for all results:

` ` `python
result = execute_sql(config, query="SELECT * FROM orders", limit=10)
print(format_output(result, fmt="table"))
` ` `

The user can request JSON or YAML output:
- "run this SQL as json" -> `format_output(result, fmt="json")`
- "query as yaml" -> `format_output(result, fmt="yaml")`
```

Note: Replace the `` ` ` ` `` with proper triple backticks in the actual file.

- [ ] **Step 2: Commit**

```bash
git add skills/preset-sql/SKILL.md
git commit -m "feat: preset-sql skill for natural language SQL execution"
```

---

### Task 6: Router Update

**Files:**
- Modify: `skills/preset/SKILL.md`

- [ ] **Step 1: Add menu item 11 (sql)**

In the menu block of `skills/preset/SKILL.md`, after line `10. dataset`, add:

```
  11. sql           /preset-toolkit:preset-sql
```

- [ ] **Step 2: Add routing table row**

In the routing table, add:

```
| `sql`, `query`, `run sql`, `execute sql`, `run query` | `preset-toolkit:preset-sql` |
```

- [ ] **Step 3: Add NLP routing examples**

In the Natural Language Routing section, add:

```
- "Run this SQL query" -> `preset-toolkit:preset-sql`
- "Execute SELECT * FROM orders" -> `preset-toolkit:preset-sql`
- "Query the database" -> `preset-toolkit:preset-sql`
- "How many active users?" -> `preset-toolkit:preset-sql`
```

- [ ] **Step 4: Commit**

```bash
git add skills/preset/SKILL.md
git commit -m "feat: add sql routing to preset router skill"
```

---

### Task 7: Version Bump + README

**Files:**
- Modify: `.claude-plugin/marketplace.json`
- Modify: `skills/preset/SKILL.md`
- Modify: `README.md`

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/test_sync.py tests/test_formatter.py tests/test_chart.py tests/test_dataset.py tests/test_sql.py tests/test_config.py tests/test_dedup.py tests/test_fingerprint.py tests/test_ownership.py tests/test_telemetry.py tests/test_logger.py tests/test_deps.py -v`

Record the actual test count from output.

- [ ] **Step 2: Bump marketplace.json version**

In `.claude-plugin/marketplace.json`, change `"version": "0.8.0"` to `"version": "0.9.0"`.

- [ ] **Step 3: Update router version header**

In `skills/preset/SKILL.md`, change `Preset Toolkit v0.8.0` to `Preset Toolkit v0.9.0`.

- [ ] **Step 4: Update README.md**

Apply these changes to `README.md`:
1. Version badge: `0.8.0` → `0.9.0`
2. Test badge: update to actual test count from Step 1
3. Skills section: `## Skills (18)` → `## Skills (19)`
4. Add row to skills table: `| 19 | SQL Execution | /preset-toolkit:preset-sql | Execute SQL queries against Preset databases |`
5. Architecture tree: `18 skills` → `19 skills`
6. Architecture tree: add `│   ├── preset-sql/           SQL query execution` after the dataset skill line
7. Architecture tree: `15 modules` → `16 modules`
8. Architecture tree: add `│   ├── sql.py                SQL execution (execute_sql + database ID resolution)` after `dataset.py` line
9. Test count in "For Contributors" section: update to actual count from Step 1

- [ ] **Step 5: Commit**

```bash
git add .claude-plugin/marketplace.json skills/preset/SKILL.md README.md
git commit -m "chore: bump to v0.9.0 — SQL execution (sub-project 4 of 6)"
```
