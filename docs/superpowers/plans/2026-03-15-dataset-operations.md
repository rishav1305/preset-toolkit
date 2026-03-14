# Dataset Operations Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose all 6 `sup dataset` commands (list, info, sql, data, pull, push) as structured Python functions with typed results, formatter integration, and a natural language skill.

**Architecture:** New `scripts/dataset.py` module with 6 public functions, each wrapping a `sup dataset` subcommand via `run_sup()` with `--json` output parsed into dataclasses. Formatter extended for all dataset result types. New `preset-dataset` skill for NLP routing.

**Tech Stack:** Python 3.8+ stdlib (`json`, `dataclasses`, `typing`), existing `scripts.sync.run_sup`, `scripts.formatter`, `scripts.config.ToolkitConfig`

---

## Chunk 1: Dataset Dataclasses + First Two Functions

### Task 1: Dataset Result Dataclasses

**Files:**
- Create: `scripts/dataset.py`
- Create: `tests/test_dataset.py`

- [ ] **Step 1: Write failing tests for dataclasses**

Create `tests/test_dataset.py`:

```python
"""Tests for dataset operations module."""
import json as json_mod
from unittest.mock import patch, MagicMock

import pytest
import yaml

from scripts.dataset import (
    DatasetSummary,
    DatasetListResult,
    DatasetInfo,
    DatasetSQL,
    DatasetData,
    DatasetPullResult,
    DatasetPushResult,
)
from scripts.config import ToolkitConfig


def _make_dataset_config(tmp_path):
    """Helper to create a minimal ToolkitConfig for dataset tests."""
    config_dir = tmp_path / ".preset-toolkit"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(yaml.safe_dump({
        "version": 1,
        "workspace": {"url": "https://test.preset.io", "id": "test123"},
        "dashboard": {"id": 1, "name": "Test"},
    }))
    return ToolkitConfig.load(config_path)


# ── Dataclass construction ─────────────────────────────────────────

def test_dataset_summary_creation():
    """DatasetSummary holds basic dataset metadata."""
    s = DatasetSummary(id=42, name="Main_Dataset", database="analytics_db")
    assert s.id == 42
    assert s.name == "Main_Dataset"
    assert s.database == "analytics_db"
    assert s.schema == ""
    assert s.modified == ""


def test_dataset_summary_with_all_fields():
    """DatasetSummary accepts optional schema and modified."""
    s = DatasetSummary(
        id=42, name="Main_Dataset", database="analytics_db",
        schema="public", modified="2026-03-15T12:00:00Z",
    )
    assert s.schema == "public"
    assert s.modified == "2026-03-15T12:00:00Z"


def test_dataset_list_result():
    """DatasetListResult wraps a list of DatasetSummary."""
    result = DatasetListResult(
        success=True,
        datasets=[DatasetSummary(id=1, name="A", database="db1")],
        total=1,
    )
    assert result.success is True
    assert len(result.datasets) == 1
    assert result.total == 1
    assert result.error == ""


def test_dataset_info():
    """DatasetInfo holds detailed dataset metadata."""
    info = DatasetInfo(
        success=True, id=42, name="Main_Dataset", database="analytics_db",
        schema="public", sql="SELECT * FROM orders",
        columns=[{"column_name": "id", "type": "INTEGER"}],
        metrics=[{"metric_name": "count", "expression": "COUNT(*)"}],
        raw={"extra": "data"},
    )
    assert info.sql == "SELECT * FROM orders"
    assert len(info.columns) == 1
    assert len(info.metrics) == 1
    assert info.raw == {"extra": "data"}


def test_dataset_sql():
    """DatasetSQL holds SQL definition."""
    sql = DatasetSQL(success=True, sql="SELECT * FROM orders WHERE active = 1")
    assert sql.sql == "SELECT * FROM orders WHERE active = 1"


def test_dataset_data():
    """DatasetData holds query results."""
    data = DatasetData(
        success=True,
        columns=["id", "order_date", "amount"],
        rows=[{"id": 1, "order_date": "2026-01-01", "amount": 100}],
        row_count=1,
    )
    assert len(data.columns) == 3
    assert len(data.rows) == 1
    assert data.row_count == 1


def test_dataset_pull_result():
    """DatasetPullResult holds pull operation results."""
    result = DatasetPullResult(success=True, datasets_pulled=2, files=["a.yaml", "b.yaml"])
    assert result.datasets_pulled == 2
    assert len(result.files) == 2


def test_dataset_push_result():
    """DatasetPushResult holds push operation results."""
    result = DatasetPushResult(success=True, datasets_pushed=3)
    assert result.datasets_pushed == 3
    assert result.errors == []
    assert result.error == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_dataset.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.dataset'`

- [ ] **Step 3: Create scripts/dataset.py with dataclasses**

Create `scripts/dataset.py`:

```python
"""Dataset operations: list, info, sql, data, pull, push.

Wraps sup dataset subcommands as structured Python functions.
Each function calls run_sup() with --json and parses the output
into typed dataclasses.
"""
import json
from dataclasses import dataclass, field
from typing import List, Optional

from scripts.config import ToolkitConfig
from scripts.sync import run_sup


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
    """Result from list_datasets()."""
    success: bool
    datasets: List[DatasetSummary] = field(default_factory=list)
    total: int = 0
    error: str = ""


@dataclass
class DatasetInfo:
    """Detailed metadata for a single dataset."""
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
    """SQL definition for a dataset."""
    success: bool
    sql: str = ""
    error: str = ""


@dataclass
class DatasetData:
    """Sample data results from a dataset query."""
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[dict] = field(default_factory=list)
    row_count: int = 0
    error: str = ""


@dataclass
class DatasetPullResult:
    """Result from pull_datasets()."""
    success: bool
    datasets_pulled: int = 0
    files: List[str] = field(default_factory=list)
    error: str = ""


@dataclass
class DatasetPushResult:
    """Result from push_datasets()."""
    success: bool
    datasets_pushed: int = 0
    errors: List[str] = field(default_factory=list)
    error: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dataset.py -v`
Expected: ALL 8 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/dataset.py tests/test_dataset.py
git commit -m "feat: dataset result dataclasses (DatasetSummary, DatasetListResult, DatasetInfo, DatasetSQL, DatasetData, DatasetPullResult, DatasetPushResult)"
```

---

### Task 2: list_datasets() Function

**Files:**
- Modify: `scripts/dataset.py`
- Modify: `tests/test_dataset.py`

- [ ] **Step 1: Write failing tests for list_datasets**

Add to `tests/test_dataset.py`:

```python
from scripts.dataset import list_datasets

# ── list_datasets ──────────────────────────────────────────────────

def test_list_datasets_success(tmp_path):
    """list_datasets parses JSON output into DatasetListResult."""
    cfg = _make_dataset_config(tmp_path)
    sup_json = json_mod.dumps([
        {"id": 42, "table_name": "Main_Dataset", "database_name": "analytics_db",
         "schema": "public", "changed_on_utc": "2026-03-15T00:00:00Z"},
        {"id": 43, "table_name": "Users", "database_name": "analytics_db",
         "schema": "public", "changed_on_utc": "2026-03-14T00:00:00Z"},
    ])
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = list_datasets(cfg)

    assert result.success is True
    assert len(result.datasets) == 2
    assert result.datasets[0].id == 42
    assert result.datasets[0].name == "Main_Dataset"
    assert result.datasets[0].database == "analytics_db"
    assert result.datasets[0].schema == "public"
    assert result.datasets[1].name == "Users"
    assert result.total == 2


def test_list_datasets_with_filters(tmp_path):
    """list_datasets passes filter kwargs as CLI flags."""
    cfg = _make_dataset_config(tmp_path)
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        list_datasets(cfg, search="orders", mine=True, limit=10, database_id=5)

    args = mock_sup.call_args[0][0]
    assert "dataset" in args
    assert "list" in args
    assert "--json" in args
    assert "--search" in args
    assert "orders" in args
    assert "--mine" in args
    assert "--limit" in args
    assert "10" in args
    assert "--database-id" in args
    assert "5" in args


def test_list_datasets_empty(tmp_path):
    """list_datasets handles empty result."""
    cfg = _make_dataset_config(tmp_path)
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        result = list_datasets(cfg)

    assert result.success is True
    assert result.datasets == []
    assert result.total == 0


def test_list_datasets_sup_failure(tmp_path):
    """list_datasets returns error on sup failure."""
    cfg = _make_dataset_config(tmp_path)
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="auth error")
        result = list_datasets(cfg)

    assert result.success is False
    assert "auth error" in result.error


def test_list_datasets_malformed_json(tmp_path):
    """list_datasets handles malformed JSON gracefully."""
    cfg = _make_dataset_config(tmp_path)
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
        result = list_datasets(cfg)

    assert result.success is False
    assert "parse" in result.error.lower() or "json" in result.error.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_dataset.py::test_list_datasets_success -v`
Expected: FAIL with `ImportError: cannot import name 'list_datasets'`

- [ ] **Step 3: Implement list_datasets**

Add to `scripts/dataset.py`:

```python
def _parse_dataset_summary(item: dict) -> DatasetSummary:
    """Parse a single dataset dict from sup JSON into DatasetSummary."""
    return DatasetSummary(
        id=item.get("id", 0),
        name=item.get("table_name", ""),
        database=item.get("database_name", ""),
        schema=item.get("schema", ""),
        modified=item.get("changed_on_utc", ""),
    )


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
    args = ["dataset", "list", "--json"]

    if search is not None:
        args.extend(["--search", search])
    if database_id is not None:
        args.extend(["--database-id", str(database_id)])
    if mine:
        args.append("--mine")
    if modified_after is not None:
        args.extend(["--modified-after", modified_after])
    if limit is not None:
        args.extend(["--limit", str(limit)])
    if order is not None:
        args.extend(["--order", order])
    if desc:
        args.append("--desc")

    r = run_sup(args)
    if r.returncode != 0:
        return DatasetListResult(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return DatasetListResult(success=False, error=f"JSON parse error: {e}")

    if isinstance(data, list):
        datasets = [_parse_dataset_summary(item) for item in data]
    else:
        datasets = []

    return DatasetListResult(success=True, datasets=datasets, total=len(datasets))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dataset.py -v`
Expected: ALL 13 PASS (8 dataclass + 5 list_datasets)

- [ ] **Step 5: Commit**

```bash
git add scripts/dataset.py tests/test_dataset.py
git commit -m "feat: list_datasets() with filtering, JSON parsing, and error handling"
```

---

## Chunk 2: Remaining Dataset Functions (info, sql, data, pull, push)

### Task 3: get_dataset_info() Function

**Files:**
- Modify: `scripts/dataset.py`
- Modify: `tests/test_dataset.py`

- [ ] **Step 1: Write failing tests**

```python
from scripts.dataset import get_dataset_info

def test_get_dataset_info_success(tmp_path):
    """get_dataset_info parses JSON into DatasetInfo."""
    cfg = _make_dataset_config(tmp_path)
    sup_json = json_mod.dumps({
        "id": 42, "table_name": "Main_Dataset", "database_name": "analytics_db",
        "schema": "public", "sql": "SELECT * FROM orders",
        "columns": [{"column_name": "id", "type": "INTEGER"}],
        "metrics": [{"metric_name": "count", "expression": "COUNT(*)"}],
        "extra_field": "preserved",
    })
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = get_dataset_info(cfg, dataset_id=42)

    assert result.success is True
    assert result.id == 42
    assert result.name == "Main_Dataset"
    assert result.database == "analytics_db"
    assert result.schema == "public"
    assert result.sql == "SELECT * FROM orders"
    assert len(result.columns) == 1
    assert len(result.metrics) == 1
    assert result.raw["extra_field"] == "preserved"
    assert "42" in mock_sup.call_args[0][0]


def test_get_dataset_info_failure(tmp_path):
    """get_dataset_info returns error on sup failure."""
    cfg = _make_dataset_config(tmp_path)
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
        result = get_dataset_info(cfg, dataset_id=9999)

    assert result.success is False
    assert "not found" in result.error
```

- [ ] **Step 2: Implement get_dataset_info**

```python
def get_dataset_info(config: ToolkitConfig, dataset_id: int) -> DatasetInfo:
    """Get detailed metadata for a dataset. Uses sup dataset info <id> --json."""
    r = run_sup(["dataset", "info", str(dataset_id), "--json"])
    if r.returncode != 0:
        return DatasetInfo(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return DatasetInfo(success=False, error=f"JSON parse error: {e}")

    if not isinstance(data, dict):
        return DatasetInfo(success=False, error="Unexpected response format")

    return DatasetInfo(
        success=True,
        id=data.get("id", 0),
        name=data.get("table_name", ""),
        database=data.get("database_name", ""),
        schema=data.get("schema", ""),
        sql=data.get("sql", ""),
        columns=data.get("columns", []),
        metrics=data.get("metrics", []),
        raw=data,
    )
```

- [ ] **Step 3: Run tests, commit**

Run: `python3 -m pytest tests/test_dataset.py -v` — ALL 15 PASS

```bash
git add scripts/dataset.py tests/test_dataset.py
git commit -m "feat: get_dataset_info() with JSON parsing and raw dict preservation"
```

---

### Task 4: get_dataset_sql() Function

**Files:**
- Modify: `scripts/dataset.py`
- Modify: `tests/test_dataset.py`

- [ ] **Step 1: Write failing tests**

```python
from scripts.dataset import get_dataset_sql

def test_get_dataset_sql_success(tmp_path):
    """get_dataset_sql extracts SQL from result field."""
    cfg = _make_dataset_config(tmp_path)
    sup_json = json_mod.dumps({"result": "SELECT * FROM orders WHERE date > '2026-01-01'"})
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = get_dataset_sql(cfg, dataset_id=42)

    assert result.success is True
    assert "SELECT * FROM orders" in result.sql
    assert "42" in mock_sup.call_args[0][0]


def test_get_dataset_sql_failure(tmp_path):
    """get_dataset_sql returns error on sup failure."""
    cfg = _make_dataset_config(tmp_path)
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="dataset not found")
        result = get_dataset_sql(cfg, dataset_id=9999)

    assert result.success is False
    assert "dataset not found" in result.error
```

- [ ] **Step 2: Implement get_dataset_sql**

```python
def get_dataset_sql(config: ToolkitConfig, dataset_id: int) -> DatasetSQL:
    """Get the SQL definition for a dataset. Uses sup dataset sql <id> --json."""
    r = run_sup(["dataset", "sql", str(dataset_id), "--json"])
    if r.returncode != 0:
        return DatasetSQL(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return DatasetSQL(success=False, error=f"JSON parse error: {e}")

    sql = data.get("result", "") if isinstance(data, dict) else ""
    return DatasetSQL(success=True, sql=sql)
```

- [ ] **Step 3: Run tests, commit**

Run: `python3 -m pytest tests/test_dataset.py -v` — ALL 17 PASS

```bash
git add scripts/dataset.py tests/test_dataset.py
git commit -m "feat: get_dataset_sql() with result field extraction"
```

---

### Task 5: get_dataset_data() Function

**Files:**
- Modify: `scripts/dataset.py`
- Modify: `tests/test_dataset.py`

- [ ] **Step 1: Write failing tests**

```python
from scripts.dataset import get_dataset_data

def test_get_dataset_data_success(tmp_path):
    """get_dataset_data parses columns, rows, and row_count."""
    cfg = _make_dataset_config(tmp_path)
    sup_json = json_mod.dumps({
        "columns": ["id", "order_date", "amount"],
        "data": [
            {"id": 1, "order_date": "2026-01", "amount": 100},
            {"id": 2, "order_date": "2026-02", "amount": 200},
        ],
        "rowcount": 2,
    })
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = get_dataset_data(cfg, dataset_id=42)

    assert result.success is True
    assert result.columns == ["id", "order_date", "amount"]
    assert len(result.rows) == 2
    assert result.rows[0]["amount"] == 100
    assert result.row_count == 2


def test_get_dataset_data_with_limit(tmp_path):
    """get_dataset_data passes --limit flag when specified."""
    cfg = _make_dataset_config(tmp_path)
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout='{"columns":[],"data":[],"rowcount":0}', stderr="")
        get_dataset_data(cfg, dataset_id=42, limit=5)

    args = mock_sup.call_args[0][0]
    assert "--limit" in args
    assert "5" in args


def test_get_dataset_data_failure(tmp_path):
    """get_dataset_data returns error on sup failure."""
    cfg = _make_dataset_config(tmp_path)
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="timeout")
        result = get_dataset_data(cfg, dataset_id=42)

    assert result.success is False
    assert "timeout" in result.error
```

- [ ] **Step 2: Implement get_dataset_data**

```python
def get_dataset_data(
    config: ToolkitConfig, dataset_id: int, limit: Optional[int] = None,
) -> DatasetData:
    """Get sample data from a dataset. Uses sup dataset data <id> --json."""
    args = ["dataset", "data", str(dataset_id), "--json"]
    if limit is not None:
        args.extend(["--limit", str(limit)])

    r = run_sup(args)
    if r.returncode != 0:
        return DatasetData(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return DatasetData(success=False, error=f"JSON parse error: {e}")

    if not isinstance(data, dict):
        return DatasetData(success=False, error="Unexpected response format")

    return DatasetData(
        success=True,
        columns=data.get("columns", []),
        rows=data.get("data", []),
        row_count=data.get("rowcount", 0),
    )
```

- [ ] **Step 3: Run tests, commit**

Run: `python3 -m pytest tests/test_dataset.py -v` — ALL 20 PASS

```bash
git add scripts/dataset.py tests/test_dataset.py
git commit -m "feat: get_dataset_data() with columns, rows, row_count parsing"
```

---

### Task 6: pull_datasets() Function

**Files:**
- Modify: `scripts/dataset.py`
- Modify: `tests/test_dataset.py`

- [ ] **Step 1: Write failing tests**

```python
from scripts.dataset import pull_datasets

def test_pull_datasets_single(tmp_path):
    """pull_datasets with dataset_id pulls a single dataset."""
    cfg = _make_dataset_config(tmp_path)
    sup_json = json_mod.dumps({"datasets_pulled": 1, "files": ["datasets/Main_Dataset.yaml"]})
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = pull_datasets(cfg, dataset_id=42)

    assert result.success is True
    assert result.datasets_pulled == 1
    args = mock_sup.call_args[0][0]
    assert "--dataset-id" in args
    assert "42" in args


def test_pull_datasets_multiple(tmp_path):
    """pull_datasets with dataset_ids pulls multiple datasets."""
    cfg = _make_dataset_config(tmp_path)
    sup_json = json_mod.dumps({"datasets_pulled": 2, "files": ["a.yaml", "b.yaml"]})
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = pull_datasets(cfg, dataset_ids=[42, 43])

    args = mock_sup.call_args[0][0]
    assert "--dataset-ids" in args
    assert "42,43" in args


def test_pull_datasets_mutual_exclusion(tmp_path):
    """pull_datasets raises ValueError if both dataset_id and dataset_ids given."""
    cfg = _make_dataset_config(tmp_path)
    with pytest.raises(ValueError, match="mutually exclusive"):
        pull_datasets(cfg, dataset_id=42, dataset_ids=[42, 43])


def test_pull_datasets_with_filters(tmp_path):
    """pull_datasets passes filter kwargs as CLI flags."""
    cfg = _make_dataset_config(tmp_path)
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout='{"datasets_pulled":0,"files":[]}', stderr="")
        pull_datasets(cfg, mine=True, skip_dependencies=True, overwrite=False)

    args = mock_sup.call_args[0][0]
    assert "--mine" in args
    assert "--skip-dependencies" in args
    assert "--no-overwrite" in args


def test_pull_datasets_failure(tmp_path):
    """pull_datasets returns error on sup failure."""
    cfg = _make_dataset_config(tmp_path)
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="connection error")
        result = pull_datasets(cfg, dataset_id=42)

    assert result.success is False
    assert "connection error" in result.error
```

- [ ] **Step 2: Implement pull_datasets**

```python
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

    dataset_id and dataset_ids are mutually exclusive.
    Raises ValueError if both are provided.
    """
    if dataset_id is not None and dataset_ids is not None:
        raise ValueError("dataset_id and dataset_ids are mutually exclusive")

    args = ["dataset", "pull", "--json"]

    if dataset_id is not None:
        args.extend(["--dataset-id", str(dataset_id)])
    if dataset_ids is not None:
        args.extend(["--dataset-ids", ",".join(str(did) for did in dataset_ids)])
    if name is not None:
        args.extend(["--name", name])
    if mine:
        args.append("--mine")
    if modified_after is not None:
        args.extend(["--modified-after", modified_after])
    if limit is not None:
        args.extend(["--limit", str(limit)])
    if skip_dependencies:
        args.append("--skip-dependencies")
    if not overwrite:
        args.append("--no-overwrite")
    if assets_folder is not None:
        args.extend(["--assets-folder", assets_folder])

    r = run_sup(args)
    if r.returncode != 0:
        return DatasetPullResult(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return DatasetPullResult(success=False, error=f"JSON parse error: {e}")

    if not isinstance(data, dict):
        return DatasetPullResult(success=True)

    return DatasetPullResult(
        success=True,
        datasets_pulled=data.get("datasets_pulled", 0),
        files=data.get("files", []),
    )
```

- [ ] **Step 3: Run tests, commit**

Run: `python3 -m pytest tests/test_dataset.py -v` — ALL 25 PASS

```bash
git add scripts/dataset.py tests/test_dataset.py
git commit -m "feat: pull_datasets() with mutual exclusion, filters, and JSON parsing"
```

---

### Task 7: push_datasets() Function

**Files:**
- Modify: `scripts/dataset.py`
- Modify: `tests/test_dataset.py`

- [ ] **Step 1: Write failing tests**

```python
from scripts.dataset import push_datasets

def test_push_datasets_success(tmp_path):
    """push_datasets parses push result."""
    cfg = _make_dataset_config(tmp_path)
    sup_json = json_mod.dumps({"datasets_pushed": 3, "errors": []})
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = push_datasets(cfg)

    assert result.success is True
    assert result.datasets_pushed == 3
    assert result.errors == []


def test_push_datasets_with_flags(tmp_path):
    """push_datasets passes flag kwargs correctly."""
    cfg = _make_dataset_config(tmp_path)
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout='{"datasets_pushed":0,"errors":[]}', stderr="")
        push_datasets(cfg, overwrite=False, force=False, continue_on_error=True, load_env=True)

    args = mock_sup.call_args[0][0]
    assert "--no-overwrite" in args
    assert "--continue-on-error" in args
    assert "--load-env" in args
    assert "--force" not in args


def test_push_datasets_failure(tmp_path):
    """push_datasets returns error on sup failure."""
    cfg = _make_dataset_config(tmp_path)
    with patch("scripts.dataset.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="push failed")
        result = push_datasets(cfg)

    assert result.success is False
    assert "push failed" in result.error
```

- [ ] **Step 2: Implement push_datasets**

```python
def push_datasets(
    config: ToolkitConfig,
    assets_folder: Optional[str] = None,
    overwrite: bool = True,
    force: bool = True,
    continue_on_error: bool = False,
    load_env: bool = False,
) -> DatasetPushResult:
    """Push dataset definitions to workspace. Uses sup dataset push."""
    args = ["dataset", "push", "--json"]

    if assets_folder is not None:
        args.extend(["--assets-folder", assets_folder])
    if not overwrite:
        args.append("--no-overwrite")
    if force:
        args.append("--force")
    if continue_on_error:
        args.append("--continue-on-error")
    if load_env:
        args.append("--load-env")

    r = run_sup(args)
    if r.returncode != 0:
        return DatasetPushResult(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return DatasetPushResult(success=False, error=f"JSON parse error: {e}")

    if not isinstance(data, dict):
        return DatasetPushResult(success=True)

    return DatasetPushResult(
        success=True,
        datasets_pushed=data.get("datasets_pushed", 0),
        errors=data.get("errors", []),
    )
```

- [ ] **Step 3: Run tests, commit**

Run: `python3 -m pytest tests/test_dataset.py -v` — ALL 28 PASS

```bash
git add scripts/dataset.py tests/test_dataset.py
git commit -m "feat: push_datasets() with flag mapping and JSON parsing"
```

---

## Chunk 3: Formatter Extension + Skill + Finalization

### Task 8: Formatter Extension for Dataset Types

**Files:**
- Modify: `scripts/formatter.py`
- Modify: `tests/test_formatter.py`

- [ ] **Step 1: Write failing tests for dataset formatters**

Add to `tests/test_formatter.py`:

```python
from scripts.dataset import (
    DatasetSummary, DatasetListResult, DatasetInfo, DatasetSQL,
    DatasetData, DatasetPullResult, DatasetPushResult,
)

# ── Dataset table formats ──────────────────────────────────────────

def test_format_dataset_list_table():
    """DatasetListResult table shows ID, Name, Database, Schema, Modified columns."""
    result = DatasetListResult(
        success=True,
        datasets=[
            DatasetSummary(id=42, name="Main_Dataset", database="analytics_db",
                           schema="public", modified="2026-03-15T00:00:00Z"),
            DatasetSummary(id=43, name="Users", database="analytics_db",
                           schema="public", modified="2026-03-14T00:00:00Z"),
        ],
        total=2,
    )
    output = format_output(result, fmt="table")
    assert "42" in output
    assert "Main_Dataset" in output
    assert "analytics_db" in output
    assert "public" in output
    assert "43" in output
    assert "Users" in output
    assert "2 dataset(s)" in output


def test_format_dataset_list_empty_table():
    """DatasetListResult table shows 'no datasets' when empty."""
    result = DatasetListResult(success=True, datasets=[], total=0)
    output = format_output(result, fmt="table")
    assert "no datasets" in output.lower()


def test_format_dataset_info_table():
    """DatasetInfo table shows key-value metadata."""
    result = DatasetInfo(
        success=True, id=42, name="Main_Dataset", database="analytics_db",
        schema="public", sql="SELECT * FROM orders",
    )
    output = format_output(result, fmt="table")
    assert "42" in output
    assert "Main_Dataset" in output
    assert "analytics_db" in output
    assert "public" in output


def test_format_dataset_sql_table():
    """DatasetSQL table displays SQL text."""
    result = DatasetSQL(success=True, sql="SELECT * FROM orders WHERE active = 1")
    output = format_output(result, fmt="table")
    assert "SELECT * FROM orders" in output


def test_format_dataset_data_table():
    """DatasetData table shows columnar data with row count."""
    result = DatasetData(
        success=True,
        columns=["id", "amount"],
        rows=[{"id": 1, "amount": 100}],
        row_count=1,
    )
    output = format_output(result, fmt="table")
    assert "id" in output
    assert "amount" in output
    assert "100" in output
    assert "1 row(s)" in output


def test_format_dataset_pull_result_table():
    """DatasetPullResult table shows summary."""
    result = DatasetPullResult(success=True, datasets_pulled=2, files=["a.yaml", "b.yaml"])
    output = format_output(result, fmt="table")
    assert "2" in output
    assert "a.yaml" in output


def test_format_dataset_push_result_table():
    """DatasetPushResult table shows summary."""
    result = DatasetPushResult(success=True, datasets_pushed=3)
    output = format_output(result, fmt="table")
    assert "3" in output


# ── Dataset JSON/YAML formats ──────────────────────────────────────

def test_format_dataset_list_json():
    """DatasetListResult JSON is valid and parseable."""
    result = DatasetListResult(
        success=True,
        datasets=[DatasetSummary(id=1, name="A", database="db1")],
        total=1,
    )
    output = format_output(result, fmt="json")
    parsed = json.loads(output)
    assert parsed["success"] is True
    assert len(parsed["datasets"]) == 1


def test_format_dataset_info_yaml():
    """DatasetInfo YAML is valid."""
    result = DatasetInfo(success=True, id=42, name="Main_Dataset", database="analytics_db")
    output = format_output(result, fmt="yaml")
    parsed = yaml.safe_load(output)
    assert parsed["id"] == 42
    assert parsed["name"] == "Main_Dataset"
```

- [ ] **Step 2: Implement dataset table formatters**

Add to `scripts/formatter.py`:

Import:
```python
from scripts.dataset import (
    DatasetListResult, DatasetInfo, DatasetSQL, DatasetData,
    DatasetPullResult, DatasetPushResult,
)
```

Add 6 table formatters:
- `_format_table_dataset_list(result)` — ID/Name/Database/Schema/Modified columns
- `_format_table_dataset_info(result)` — key-value pairs
- `_format_table_dataset_sql(result)` — raw SQL text
- `_format_table_dataset_data(result)` — columnar data with row count footer
- `_format_table_dataset_pull(result)` — summary with file list
- `_format_table_dataset_push(result)` — summary with count

Update `format_output()` table branch with dataset type dispatch.

- [ ] **Step 3: Run tests, commit**

Run: `python3 -m pytest tests/test_formatter.py -v` — ALL PASS (17 existing + 9 new = 26)

```bash
git add scripts/formatter.py tests/test_formatter.py
git commit -m "feat: formatter table/json/yaml support for all dataset result types"
```

---

### Task 9: New Skill — `skills/preset-dataset/SKILL.md`

**Files:**
- Create: `skills/preset-dataset/SKILL.md`
- Modify: `skills/preset/SKILL.md` (add dataset routing)

- [ ] **Step 1: Create preset-dataset skill**

Create `skills/preset-dataset/SKILL.md` with intent routing table for all 6 dataset operations, conversation principles, prerequisites, and output formatting guidance. Follow the same structure as `skills/preset-chart/SKILL.md`.

- [ ] **Step 2: Update router skill**

In `skills/preset/SKILL.md`:
- Add menu item `10. dataset /preset-toolkit:preset-dataset`
- Add routing row: `dataset`, `datasets`, `list datasets`, `dataset info`, `dataset sql`, `dataset data` → `preset-toolkit:preset-dataset`
- Add NLP routing examples for dataset intents

- [ ] **Step 3: Commit**

```bash
git add skills/preset-dataset/SKILL.md skills/preset/SKILL.md
git commit -m "feat: preset-dataset skill with NLP routing for dataset operations"
```

---

### Task 10: Version Bump + README Update + Full Test Run

**Files:**
- Modify: `.claude-plugin/marketplace.json`
- Modify: `README.md`

- [ ] **Step 1: Bump version to 0.8.0**

- [ ] **Step 2: Run full test suite**

Run: `python3 -m pytest tests/test_sync.py tests/test_formatter.py tests/test_chart.py tests/test_dataset.py tests/test_config.py tests/test_dedup.py tests/test_fingerprint.py tests/test_ownership.py tests/test_telemetry.py tests/test_logger.py tests/test_deps.py -v`
Expected: ALL PASS. Note exact count.

- [ ] **Step 3: Update README with actual test count**

Update version badge, test count, skills table (add Dataset Ops row #18), skill count to 18, architecture tree (add `scripts/dataset.py` and `skills/preset-dataset/`), module count to 15.

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/marketplace.json README.md
git commit -m "chore: bump to v0.8.0 — dataset operations (sub-project 3 of 6)"
```
