# Chart Operations Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose all 6 `sup chart` commands (list, info, sql, data, pull, push) as structured Python functions with typed results, formatter integration, and a natural language skill.

**Architecture:** New `scripts/chart.py` module with 6 public functions, each wrapping a `sup chart` subcommand via `run_sup()` with `--json` output parsed into dataclasses. Formatter extended for all chart result types. New `preset-chart` skill for NLP routing.

**Tech Stack:** Python 3.8+ stdlib (`json`, `dataclasses`, `typing`), existing `scripts.sync.run_sup`, `scripts.formatter`, `scripts.config.ToolkitConfig`

---

## Chunk 1: Foundation — Public API Rename + Chart Dataclasses + First Function

### Task 1: Rename `_run_sup` and `_ensure_sup` to Public API

**Files:**
- Modify: `scripts/sync.py:119-181` (rename functions, add aliases)
- Modify: `tests/test_sync.py` (update mock targets)

- [ ] **Step 1: Write failing test for public API names**

```python
# In tests/test_sync.py, add after existing imports:
from scripts.sync import run_sup, ensure_sup

def test_public_api_run_sup():
    """run_sup is the public name for the CLI runner."""
    with patch("scripts.sync.ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            result = run_sup(["chart", "list", "--json"])
            assert result.returncode == 0

def test_public_api_ensure_sup():
    """ensure_sup is importable as public API."""
    assert callable(ensure_sup)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_sync.py::test_public_api_run_sup tests/test_sync.py::test_public_api_ensure_sup -v`
Expected: FAIL with `ImportError: cannot import name 'run_sup'`

- [ ] **Step 3: Rename functions in sync.py**

In `scripts/sync.py`, rename `_ensure_sup` to `ensure_sup` and `_run_sup` to `run_sup`. Add backward-compat aliases:

```python
def ensure_sup() -> str:
    """Find the sup CLI binary and verify it works.

    Returns the path to the sup binary.
    Raises SupNotFoundError if not installed — does NOT auto-install.
    """
    global _sup_path
    if _sup_path:
        return _sup_path

    found = _find_sup()
    if found:
        try:
            r = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                _sup_path = found
                log.debug("Using sup at: %s", found)
                return found
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    raise SupNotFoundError(
        "sup CLI not found. Run /preset-toolkit:preset-setup to install dependencies."
    )

# Backward-compat aliases
_ensure_sup = ensure_sup


def run_sup(args: List[str], retries: int = 3, backoff_base: float = 2.0) -> subprocess.CompletedProcess:
    """Run a sup CLI command with retries. Raises SupNotFoundError if missing."""
    sup = ensure_sup()
    last_result = None
    for attempt in range(1, retries + 1):
        try:
            last_result = subprocess.run(
                [sup] + args,
                capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            log.warning("sup %s timed out (attempt %d/%d)", " ".join(args[:3]), attempt, retries)
            last_result = subprocess.CompletedProcess(
                args=[sup] + args, returncode=1,
                stdout="", stderr="Command timed out after 120s",
            )
        if last_result.returncode == 0:
            return last_result
        if attempt < retries:
            wait = backoff_base * (2 ** (attempt - 1)) * (0.5 + random.random())
            log.warning(
                "sup failed (attempt %d/%d), retrying in %.1fs...",
                attempt, retries, wait,
            )
            time.sleep(wait)
    return last_result

# Backward-compat alias
_run_sup = run_sup
```

Do NOT update internal callers in `pull()`, `validate()`, `push()` — the backward-compat aliases (`_run_sup = run_sup`, `_ensure_sup = ensure_sup`) ensure all existing call sites continue to work. This avoids unnecessary churn.

- [ ] **Step 4: Update test imports only**

In `tests/test_sync.py`, add the new public names to the import line. The existing mock targets (`patch("scripts.sync._ensure_sup", ...)`) still work via the aliases, so **do not change the 14+ existing `patch()` calls** — only add the import:

```python
from scripts.sync import run_sup, ensure_sup, _run_sup, SyncResult, SupNotFoundError, CLINotFoundError, pull, validate, push, ChangeAction, AssetChange, DryRunResult, _parse_dry_run_output
```

- [ ] **Step 5: Run all sync tests**

Run: `python3 -m pytest tests/test_sync.py -v`
Expected: ALL PASS (including both new tests and all existing tests)

- [ ] **Step 6: Commit**

```bash
git add scripts/sync.py tests/test_sync.py
git commit -m "refactor: make run_sup/ensure_sup public API with backward-compat aliases"
```

---

### Task 2: Chart Result Dataclasses

**Files:**
- Create: `scripts/chart.py`
- Create: `tests/test_chart.py`

- [ ] **Step 1: Write failing tests for dataclasses**

Create `tests/test_chart.py`:

```python
"""Tests for chart operations module."""
import json as json_mod
from unittest.mock import patch, MagicMock

import pytest
import yaml

from scripts.chart import (
    ChartSummary,
    ChartListResult,
    ChartInfo,
    ChartSQL,
    ChartData,
    ChartPullResult,
    ChartPushResult,
)
from scripts.config import ToolkitConfig


def _make_chart_config(tmp_path):
    """Helper to create a minimal ToolkitConfig for chart tests."""
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

def test_chart_summary_creation():
    """ChartSummary holds basic chart metadata."""
    s = ChartSummary(id=2085, name="Revenue Overview", viz_type="big_number_total")
    assert s.id == 2085
    assert s.name == "Revenue Overview"
    assert s.viz_type == "big_number_total"
    assert s.dataset_name == ""
    assert s.modified == ""


def test_chart_summary_with_all_fields():
    """ChartSummary accepts optional dataset_name and modified."""
    s = ChartSummary(
        id=2085, name="Revenue", viz_type="table",
        dataset_name="Main_Dataset", modified="2026-03-15T12:00:00Z",
    )
    assert s.dataset_name == "Main_Dataset"
    assert s.modified == "2026-03-15T12:00:00Z"


def test_chart_list_result():
    """ChartListResult wraps a list of ChartSummary."""
    result = ChartListResult(
        success=True,
        charts=[ChartSummary(id=1, name="A", viz_type="table")],
        total=1,
    )
    assert result.success is True
    assert len(result.charts) == 1
    assert result.total == 1
    assert result.error == ""


def test_chart_info():
    """ChartInfo holds detailed chart metadata."""
    info = ChartInfo(
        success=True, id=2085, name="Revenue", viz_type="big_number_total",
        dataset_name="Main_Dataset", query_context='{"datasource":{}}',
        params='{"metric":"sum"}', raw={"extra": "data"},
    )
    assert info.query_context == '{"datasource":{}}'
    assert info.params == '{"metric":"sum"}'
    assert info.raw == {"extra": "data"}


def test_chart_sql():
    """ChartSQL holds compiled SQL."""
    sql = ChartSQL(success=True, sql="SELECT COUNT(*) FROM table")
    assert sql.sql == "SELECT COUNT(*) FROM table"


def test_chart_data():
    """ChartData holds query results."""
    data = ChartData(
        success=True,
        columns=["date", "revenue"],
        rows=[{"date": "2026-01", "revenue": 100}],
        row_count=1,
    )
    assert len(data.columns) == 2
    assert len(data.rows) == 1
    assert data.row_count == 1


def test_chart_pull_result():
    """ChartPullResult holds pull operation results."""
    result = ChartPullResult(success=True, charts_pulled=3, files=["a.yaml", "b.yaml", "c.yaml"])
    assert result.charts_pulled == 3
    assert len(result.files) == 3


def test_chart_push_result():
    """ChartPushResult holds push operation results."""
    result = ChartPushResult(success=True, charts_pushed=2)
    assert result.charts_pushed == 2
    assert result.errors == []
    assert result.error == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_chart.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.chart'`

- [ ] **Step 3: Create scripts/chart.py with dataclasses**

Create `scripts/chart.py`:

```python
"""Chart operations: list, info, sql, data, pull, push.

Wraps sup chart subcommands as structured Python functions.
Each function calls run_sup() with --json and parses the output
into typed dataclasses.
"""
import json
from dataclasses import dataclass, field
from typing import List, Optional

from scripts.config import ToolkitConfig
from scripts.sync import run_sup


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
    """Result from list_charts()."""
    success: bool
    charts: List[ChartSummary] = field(default_factory=list)
    total: int = 0
    error: str = ""


@dataclass
class ChartInfo:
    """Detailed metadata for a single chart."""
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
    """Compiled SQL query for a chart."""
    success: bool
    sql: str = ""
    error: str = ""


@dataclass
class ChartData:
    """Actual data results from a chart query."""
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[dict] = field(default_factory=list)
    row_count: int = 0
    error: str = ""


@dataclass
class ChartPullResult:
    """Result from pull_charts()."""
    success: bool
    charts_pulled: int = 0
    files: List[str] = field(default_factory=list)
    error: str = ""


@dataclass
class ChartPushResult:
    """Result from push_charts()."""
    success: bool
    charts_pushed: int = 0
    errors: List[str] = field(default_factory=list)
    error: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chart.py -v`
Expected: ALL 8 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/chart.py tests/test_chart.py
git commit -m "feat: chart result dataclasses (ChartSummary, ChartListResult, ChartInfo, ChartSQL, ChartData, ChartPullResult, ChartPushResult)"
```

---

### Task 3: list_charts() Function

**Files:**
- Modify: `scripts/chart.py` (add `list_charts`)
- Modify: `tests/test_chart.py` (add tests)

- [ ] **Step 1: Write failing tests for list_charts**

Add to `tests/test_chart.py`:

```python
# Add to imports at top of tests/test_chart.py (already present from Task 2):
from scripts.chart import list_charts

# ── list_charts ────────────────────────────────────────────────────

def test_list_charts_success(tmp_path):
    """list_charts parses JSON output into ChartListResult."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps([
        {"id": 2085, "slice_name": "Revenue", "viz_type": "big_number_total",
         "datasource_name_text": "Main_Dataset", "changed_on_utc": "2026-03-15T00:00:00Z"},
        {"id": 2088, "slice_name": "DAU", "viz_type": "line",
         "datasource_name_text": "Users", "changed_on_utc": "2026-03-14T00:00:00Z"},
    ])
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = list_charts(cfg)

    assert result.success is True
    assert len(result.charts) == 2
    assert result.charts[0].id == 2085
    assert result.charts[0].name == "Revenue"
    assert result.charts[0].viz_type == "big_number_total"
    assert result.charts[0].dataset_name == "Main_Dataset"
    assert result.charts[1].name == "DAU"
    assert result.total == 2


def test_list_charts_with_filters(tmp_path):
    """list_charts passes filter kwargs as CLI flags."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        list_charts(cfg, search="revenue", mine=True, limit=10, viz_type="table")

    args = mock_sup.call_args[0][0]
    assert "chart" in args
    assert "list" in args
    assert "--json" in args
    assert "--search" in args
    assert "revenue" in args
    assert "--mine" in args
    assert "--limit" in args
    assert "10" in args
    assert "--viz-type" in args
    assert "table" in args


def test_list_charts_empty(tmp_path):
    """list_charts handles empty result."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        result = list_charts(cfg)

    assert result.success is True
    assert result.charts == []
    assert result.total == 0


def test_list_charts_sup_failure(tmp_path):
    """list_charts returns error on sup failure."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="auth error")
        result = list_charts(cfg)

    assert result.success is False
    assert "auth error" in result.error


def test_list_charts_malformed_json(tmp_path):
    """list_charts handles malformed JSON gracefully."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
        result = list_charts(cfg)

    assert result.success is False
    assert "parse" in result.error.lower() or "json" in result.error.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_chart.py::test_list_charts_success -v`
Expected: FAIL with `ImportError: cannot import name 'list_charts'`

- [ ] **Step 3: Implement list_charts**

Add to `scripts/chart.py`:

```python
def _parse_chart_summary(item: dict) -> ChartSummary:
    """Parse a single chart dict from sup JSON into ChartSummary."""
    return ChartSummary(
        id=item.get("id", 0),
        name=item.get("slice_name", ""),
        viz_type=item.get("viz_type", ""),
        dataset_name=item.get("datasource_name_text", ""),
        modified=item.get("changed_on_utc", ""),
    )


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
    args = ["chart", "list", "--json"]

    if search is not None:
        args.extend(["--search", search])
    if dashboard_id is not None:
        args.extend(["--dashboard-id", str(dashboard_id)])
    if viz_type is not None:
        args.extend(["--viz-type", viz_type])
    if dataset_id is not None:
        args.extend(["--dataset-id", str(dataset_id)])
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
        return ChartListResult(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return ChartListResult(success=False, error=f"JSON parse error: {e}")

    if isinstance(data, list):
        charts = [_parse_chart_summary(item) for item in data]
    else:
        charts = []

    return ChartListResult(success=True, charts=charts, total=len(charts))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chart.py -v`
Expected: ALL 13 PASS (8 dataclass + 5 list_charts)

- [ ] **Step 5: Commit**

```bash
git add scripts/chart.py tests/test_chart.py
git commit -m "feat: list_charts() with filtering, JSON parsing, and error handling"
```

---

## Chunk 2: Remaining Chart Functions (info, sql, data, pull, push)

### Task 4: get_chart_info() Function

**Files:**
- Modify: `scripts/chart.py`
- Modify: `tests/test_chart.py`

- [ ] **Step 1: Write failing tests for get_chart_info**

Add to `tests/test_chart.py`:

```python
from scripts.chart import get_chart_info

def test_get_chart_info_success(tmp_path):
    """get_chart_info parses JSON into ChartInfo."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({
        "id": 2085, "slice_name": "Revenue", "viz_type": "big_number_total",
        "datasource_name_text": "Main_Dataset",
        "query_context": '{"datasource":{"id":1}}',
        "params": '{"metric":"sum__revenue"}',
        "extra_field": "preserved",
    })
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = get_chart_info(cfg, chart_id=2085)

    assert result.success is True
    assert result.id == 2085
    assert result.name == "Revenue"
    assert result.viz_type == "big_number_total"
    assert result.dataset_name == "Main_Dataset"
    assert result.query_context == '{"datasource":{"id":1}}'
    assert result.params == '{"metric":"sum__revenue"}'
    assert result.raw["extra_field"] == "preserved"
    mock_sup.assert_called_once()
    assert "2085" in mock_sup.call_args[0][0]


def test_get_chart_info_failure(tmp_path):
    """get_chart_info returns error on sup failure."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="not found")
        result = get_chart_info(cfg, chart_id=9999)

    assert result.success is False
    assert "not found" in result.error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_chart.py::test_get_chart_info_success -v`
Expected: FAIL

- [ ] **Step 3: Implement get_chart_info**

Add to `scripts/chart.py`:

```python
def get_chart_info(config: ToolkitConfig, chart_id: int) -> ChartInfo:
    """Get detailed metadata for a chart. Uses sup chart info <id> --json."""
    r = run_sup(["chart", "info", str(chart_id), "--json"])
    if r.returncode != 0:
        return ChartInfo(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return ChartInfo(success=False, error=f"JSON parse error: {e}")

    if not isinstance(data, dict):
        return ChartInfo(success=False, error="Unexpected response format")

    return ChartInfo(
        success=True,
        id=data.get("id", 0),
        name=data.get("slice_name", ""),
        viz_type=data.get("viz_type", ""),
        dataset_name=data.get("datasource_name_text", ""),
        query_context=data.get("query_context", ""),
        params=data.get("params", ""),
        raw=data,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chart.py -v`
Expected: ALL 15 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/chart.py tests/test_chart.py
git commit -m "feat: get_chart_info() with JSON parsing and raw dict preservation"
```

---

### Task 5: get_chart_sql() Function

**Files:**
- Modify: `scripts/chart.py`
- Modify: `tests/test_chart.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_chart.py`:

```python
from scripts.chart import get_chart_sql

def test_get_chart_sql_success(tmp_path):
    """get_chart_sql extracts SQL from result field."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({"result": "SELECT COUNT(*) FROM orders WHERE date > '2026-01-01'"})
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = get_chart_sql(cfg, chart_id=2085)

    assert result.success is True
    assert "SELECT COUNT(*)" in result.sql
    assert "2085" in mock_sup.call_args[0][0]


def test_get_chart_sql_failure(tmp_path):
    """get_chart_sql returns error on sup failure."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="chart not found")
        result = get_chart_sql(cfg, chart_id=9999)

    assert result.success is False
    assert "chart not found" in result.error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_chart.py::test_get_chart_sql_success -v`
Expected: FAIL

- [ ] **Step 3: Implement get_chart_sql**

Add to `scripts/chart.py`:

```python
def get_chart_sql(config: ToolkitConfig, chart_id: int) -> ChartSQL:
    """Get the compiled SQL query for a chart. Uses sup chart sql <id> --json."""
    r = run_sup(["chart", "sql", str(chart_id), "--json"])
    if r.returncode != 0:
        return ChartSQL(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return ChartSQL(success=False, error=f"JSON parse error: {e}")

    sql = data.get("result", "") if isinstance(data, dict) else ""
    return ChartSQL(success=True, sql=sql)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chart.py -v`
Expected: ALL 17 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/chart.py tests/test_chart.py
git commit -m "feat: get_chart_sql() with result field extraction"
```

---

### Task 6: get_chart_data() Function

**Files:**
- Modify: `scripts/chart.py`
- Modify: `tests/test_chart.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_chart.py`:

```python
from scripts.chart import get_chart_data

def test_get_chart_data_success(tmp_path):
    """get_chart_data parses columns, rows, and row_count."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({
        "columns": ["date", "revenue"],
        "data": [
            {"date": "2026-01", "revenue": 100},
            {"date": "2026-02", "revenue": 200},
        ],
        "rowcount": 2,
    })
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = get_chart_data(cfg, chart_id=2088)

    assert result.success is True
    assert result.columns == ["date", "revenue"]
    assert len(result.rows) == 2
    assert result.rows[0]["revenue"] == 100
    assert result.row_count == 2


def test_get_chart_data_with_limit(tmp_path):
    """get_chart_data passes --limit flag when specified."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout='{"columns":[],"data":[],"rowcount":0}', stderr="")
        get_chart_data(cfg, chart_id=2088, limit=5)

    args = mock_sup.call_args[0][0]
    assert "--limit" in args
    assert "5" in args


def test_get_chart_data_failure(tmp_path):
    """get_chart_data returns error on sup failure."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="timeout")
        result = get_chart_data(cfg, chart_id=2088)

    assert result.success is False
    assert "timeout" in result.error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_chart.py::test_get_chart_data_success -v`
Expected: FAIL

- [ ] **Step 3: Implement get_chart_data**

Add to `scripts/chart.py`:

```python
def get_chart_data(
    config: ToolkitConfig, chart_id: int, limit: Optional[int] = None,
) -> ChartData:
    """Get actual data results from a chart. Uses sup chart data <id> --json."""
    args = ["chart", "data", str(chart_id), "--json"]
    if limit is not None:
        args.extend(["--limit", str(limit)])

    r = run_sup(args)
    if r.returncode != 0:
        return ChartData(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return ChartData(success=False, error=f"JSON parse error: {e}")

    if not isinstance(data, dict):
        return ChartData(success=False, error="Unexpected response format")

    return ChartData(
        success=True,
        columns=data.get("columns", []),
        rows=data.get("data", []),
        row_count=data.get("rowcount", 0),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chart.py -v`
Expected: ALL 20 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/chart.py tests/test_chart.py
git commit -m "feat: get_chart_data() with columns, rows, row_count parsing"
```

---

### Task 7: pull_charts() Function

**Files:**
- Modify: `scripts/chart.py`
- Modify: `tests/test_chart.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_chart.py`:

```python
from scripts.chart import pull_charts

def test_pull_charts_single(tmp_path):
    """pull_charts with chart_id pulls a single chart."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({"charts_pulled": 1, "files": ["charts/Revenue.yaml"]})
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = pull_charts(cfg, chart_id=2085)

    assert result.success is True
    assert result.charts_pulled == 1
    assert "charts/Revenue.yaml" in result.files
    args = mock_sup.call_args[0][0]
    assert "--chart-id" in args
    assert "2085" in args


def test_pull_charts_multiple(tmp_path):
    """pull_charts with chart_ids pulls multiple charts."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({"charts_pulled": 2, "files": ["a.yaml", "b.yaml"]})
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = pull_charts(cfg, chart_ids="2085,2088")

    args = mock_sup.call_args[0][0]
    assert "--chart-ids" in args
    assert "2085,2088" in args


def test_pull_charts_mutual_exclusion(tmp_path):
    """pull_charts raises ValueError if both chart_id and chart_ids given."""
    cfg = _make_chart_config(tmp_path)
    with pytest.raises(ValueError, match="mutually exclusive"):
        pull_charts(cfg, chart_id=2085, chart_ids="2085,2088")


def test_pull_charts_with_filters(tmp_path):
    """pull_charts passes filter kwargs as CLI flags."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout='{"charts_pulled":0,"files":[]}', stderr="")
        pull_charts(cfg, mine=True, skip_dependencies=True, overwrite=False)

    args = mock_sup.call_args[0][0]
    assert "--mine" in args
    assert "--skip-dependencies" in args
    assert "--no-overwrite" in args


def test_pull_charts_failure(tmp_path):
    """pull_charts returns error on sup failure."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="connection error")
        result = pull_charts(cfg, chart_id=2085)

    assert result.success is False
    assert "connection error" in result.error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_chart.py::test_pull_charts_single -v`
Expected: FAIL

- [ ] **Step 3: Implement pull_charts**

Add to `scripts/chart.py`:

```python
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
    if chart_id is not None and chart_ids is not None:
        raise ValueError("chart_id and chart_ids are mutually exclusive")

    args = ["chart", "pull", "--json"]

    if chart_id is not None:
        args.extend(["--chart-id", str(chart_id)])
    if chart_ids is not None:
        args.extend(["--chart-ids", chart_ids])
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
        return ChartPullResult(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return ChartPullResult(success=False, error=f"JSON parse error: {e}")

    if not isinstance(data, dict):
        return ChartPullResult(success=True)

    return ChartPullResult(
        success=True,
        charts_pulled=data.get("charts_pulled", 0),
        files=data.get("files", []),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chart.py -v`
Expected: ALL 25 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/chart.py tests/test_chart.py
git commit -m "feat: pull_charts() with mutual exclusion, filters, and JSON parsing"
```

---

### Task 8: push_charts() Function

**Files:**
- Modify: `scripts/chart.py`
- Modify: `tests/test_chart.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_chart.py`:

```python
from scripts.chart import push_charts

def test_push_charts_success(tmp_path):
    """push_charts parses push result."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({"charts_pushed": 3, "errors": []})
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = push_charts(cfg)

    assert result.success is True
    assert result.charts_pushed == 3
    assert result.errors == []


def test_push_charts_with_flags(tmp_path):
    """push_charts passes flag kwargs correctly."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout='{"charts_pushed":0,"errors":[]}', stderr="")
        push_charts(cfg, overwrite=False, force=False, continue_on_error=True, load_env=True)

    args = mock_sup.call_args[0][0]
    assert "--no-overwrite" in args
    assert "--continue-on-error" in args
    assert "--load-env" in args
    assert "--force" not in args


def test_push_charts_failure(tmp_path):
    """push_charts returns error on sup failure."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="push failed")
        result = push_charts(cfg)

    assert result.success is False
    assert "push failed" in result.error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_chart.py::test_push_charts_success -v`
Expected: FAIL

- [ ] **Step 3: Implement push_charts**

Add to `scripts/chart.py`:

```python
def push_charts(
    config: ToolkitConfig,
    assets_folder: Optional[str] = None,
    overwrite: bool = True,
    force: bool = True,
    continue_on_error: bool = False,
    load_env: bool = False,
) -> ChartPushResult:
    """Push chart definitions to workspace. Uses sup chart push."""
    args = ["chart", "push", "--json"]

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
        return ChartPushResult(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return ChartPushResult(success=False, error=f"JSON parse error: {e}")

    if not isinstance(data, dict):
        return ChartPushResult(success=True)

    return ChartPushResult(
        success=True,
        charts_pushed=data.get("charts_pushed", 0),
        errors=data.get("errors", []),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_chart.py -v`
Expected: ALL 28 PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/chart.py tests/test_chart.py
git commit -m "feat: push_charts() with flag mapping and JSON parsing"
```

---

## Chunk 3: Formatter Extension + Skill + Finalization

### Task 9: Formatter Extension for Chart Types

**Files:**
- Modify: `scripts/formatter.py`
- Modify: `tests/test_formatter.py`

- [ ] **Step 1: Write failing tests for chart formatters**

Add to `tests/test_formatter.py`:

```python
from scripts.chart import (
    ChartSummary, ChartListResult, ChartInfo, ChartSQL,
    ChartData, ChartPullResult, ChartPushResult,
)

# ── Chart table formats ────────────────────────────────────────────

def test_format_chart_list_table():
    """ChartListResult table shows ID, Name, Type, Dataset, Modified columns."""
    result = ChartListResult(
        success=True,
        charts=[
            ChartSummary(id=2085, name="Revenue", viz_type="big_number_total",
                         dataset_name="Main", modified="2026-03-15T00:00:00Z"),
            ChartSummary(id=2088, name="DAU", viz_type="line",
                         dataset_name="Users", modified="2026-03-14T00:00:00Z"),
        ],
        total=2,
    )
    output = format_output(result, fmt="table")
    assert "2085" in output
    assert "Revenue" in output
    assert "big_number_total" in output
    assert "Main" in output
    assert "2088" in output
    assert "DAU" in output
    assert "2 chart(s)" in output


def test_format_chart_list_empty_table():
    """ChartListResult table shows 'no charts' when empty."""
    result = ChartListResult(success=True, charts=[], total=0)
    output = format_output(result, fmt="table")
    assert "no charts" in output.lower()


def test_format_chart_info_table():
    """ChartInfo table shows key-value metadata."""
    result = ChartInfo(
        success=True, id=2085, name="Revenue", viz_type="big_number_total",
        dataset_name="Main_Dataset",
    )
    output = format_output(result, fmt="table")
    assert "2085" in output
    assert "Revenue" in output
    assert "big_number_total" in output
    assert "Main_Dataset" in output


def test_format_chart_sql_table():
    """ChartSQL table displays SQL text."""
    result = ChartSQL(success=True, sql="SELECT COUNT(*) FROM orders")
    output = format_output(result, fmt="table")
    assert "SELECT COUNT(*)" in output


def test_format_chart_data_table():
    """ChartData table shows columnar data with row count."""
    result = ChartData(
        success=True,
        columns=["date", "revenue"],
        rows=[{"date": "2026-01", "revenue": 100}],
        row_count=1,
    )
    output = format_output(result, fmt="table")
    assert "date" in output
    assert "revenue" in output
    assert "100" in output
    assert "1 row(s)" in output


def test_format_chart_pull_result_table():
    """ChartPullResult table shows summary."""
    result = ChartPullResult(success=True, charts_pulled=3, files=["a.yaml", "b.yaml", "c.yaml"])
    output = format_output(result, fmt="table")
    assert "3" in output
    assert "a.yaml" in output


def test_format_chart_push_result_table():
    """ChartPushResult table shows summary."""
    result = ChartPushResult(success=True, charts_pushed=2)
    output = format_output(result, fmt="table")
    assert "2" in output


# ── Chart JSON/YAML formats ────────────────────────────────────────

def test_format_chart_list_json():
    """ChartListResult JSON is valid and parseable."""
    result = ChartListResult(
        success=True,
        charts=[ChartSummary(id=1, name="A", viz_type="table")],
        total=1,
    )
    output = format_output(result, fmt="json")
    parsed = json.loads(output)
    assert parsed["success"] is True
    assert len(parsed["charts"]) == 1


def test_format_chart_info_yaml():
    """ChartInfo YAML is valid."""
    result = ChartInfo(success=True, id=2085, name="Revenue", viz_type="big_number_total")
    output = format_output(result, fmt="yaml")
    parsed = yaml.safe_load(output)
    assert parsed["id"] == 2085
    assert parsed["name"] == "Revenue"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_formatter.py::test_format_chart_list_table -v`
Expected: FAIL (formatter doesn't know about chart types yet)

- [ ] **Step 3: Implement chart table formatters**

Update `scripts/formatter.py` — add imports and table formatters:

```python
# Add to imports at top:
from scripts.chart import (
    ChartListResult, ChartInfo, ChartSQL, ChartData,
    ChartPullResult, ChartPushResult,
)


def _format_table_chart_list(result: ChartListResult) -> str:
    """Render ChartListResult as a table."""
    lines = []
    if result.charts:
        lines.append(f"{'ID':<8} {'Name':<30} {'Type':<20} {'Dataset':<20} Modified")
        lines.append("-" * 100)
        for c in result.charts:
            lines.append(f"{c.id:<8} {c.name:<30} {c.viz_type:<20} {c.dataset_name:<20} {c.modified}")
        lines.append("")
        lines.append(f"{result.total} chart(s) found.")
    else:
        lines.append("No charts found.")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_chart_info(result: ChartInfo) -> str:
    """Render ChartInfo as key-value pairs."""
    lines = [
        f"ID:           {result.id}",
        f"Name:         {result.name}",
        f"Type:         {result.viz_type}",
        f"Dataset:      {result.dataset_name}",
    ]
    if result.query_context:
        lines.append(f"Query Context: {result.query_context[:80]}...")
    if result.params:
        lines.append(f"Params:       {result.params[:80]}...")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_chart_sql(result: ChartSQL) -> str:
    """Render ChartSQL as a SQL block."""
    if result.error:
        return f"ERROR: {result.error}"
    return result.sql


def _format_table_chart_data(result: ChartData) -> str:
    """Render ChartData as a columnar table."""
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
        lines.append("No data returned.")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_chart_pull(result: ChartPullResult) -> str:
    """Render ChartPullResult as a summary."""
    lines = [f"Charts pulled: {result.charts_pulled}"]
    if result.files:
        lines.append("Files:")
        for f in result.files:
            lines.append(f"  - {f}")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_chart_push(result: ChartPushResult) -> str:
    """Render ChartPushResult as a summary."""
    lines = [f"Charts pushed: {result.charts_pushed}"]
    if result.errors:
        lines.append("Errors:")
        for e in result.errors:
            lines.append(f"  - {e}")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)
```

Then update `format_output()` table branch to add chart type dispatch:

```python
    if fmt == "table":
        if isinstance(data, DryRunResult):
            return _format_table_dry_run(data)
        elif isinstance(data, SyncResult):
            return _format_table_sync(data)
        elif isinstance(data, ChartListResult):
            return _format_table_chart_list(data)
        elif isinstance(data, ChartInfo):
            return _format_table_chart_info(data)
        elif isinstance(data, ChartSQL):
            return _format_table_chart_sql(data)
        elif isinstance(data, ChartData):
            return _format_table_chart_data(data)
        elif isinstance(data, ChartPullResult):
            return _format_table_chart_pull(data)
        elif isinstance(data, ChartPushResult):
            return _format_table_chart_push(data)
        else:
            return str(dataclasses.asdict(data))
```

- [ ] **Step 4: Run all formatter tests**

Run: `python3 -m pytest tests/test_formatter.py -v`
Expected: ALL PASS (7 existing + 10 new = 17 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/formatter.py tests/test_formatter.py
git commit -m "feat: formatter table/json/yaml support for all chart result types"
```

---

### Task 10: New Skill — `skills/preset-chart/SKILL.md`

**Files:**
- Create: `skills/preset-chart/SKILL.md`
- Modify: `skills/preset/SKILL.md` (add chart routing)

- [ ] **Step 1: Create preset-chart skill**

Create `skills/preset-chart/SKILL.md`:

```markdown
---
name: preset-chart
description: "List, inspect, query, pull, and push individual Preset charts"
---

# Chart Operations

Operate on individual Preset charts: list, inspect metadata, view SQL, get data, pull, and push.

## Conversation Principles (MANDATORY)

**NEVER ask about:**
- Config formats, file paths, YAML structure, directory layout
- Which scripts to run, CLI flags, sync modes, technical parameters
- Auth methods, tokens, API endpoints, CSRF handling
- Git branches, merge strategies, commit messages
- Infrastructure, server details, environment setup

**ONLY ask about:**
- Business intent: "Which chart do you want to inspect?"
- Data correctness: "The chart shows $3M revenue. Does that look right?"
- Visual specifics: "Should the chart type be 'line' or 'bar'?"
- Ownership clarity: "This chart is in Bob's section. Notify him?"
- Approval gates: "Pull these 3 charts?"

## Prerequisites

```python
from scripts.config import ToolkitConfig
from scripts.chart import list_charts, get_chart_info, get_chart_sql, get_chart_data, pull_charts, push_charts
from scripts.formatter import format_output

config = ToolkitConfig.discover()
```

## Intent Routing

| User says | Function | Key args |
|-----------|----------|----------|
| "list charts", "show all charts", "what charts exist" | `list_charts(config)` | |
| "list my charts", "my charts" | `list_charts(config, mine=True)` | |
| "find revenue charts", "search for X" | `list_charts(config, search="revenue")` | |
| "show chart 2085", "chart info 2085", "details for 2085" | `get_chart_info(config, chart_id=2085)` | |
| "what SQL does chart 2085 use?", "sql for 2085" | `get_chart_sql(config, chart_id=2085)` | |
| "get data from chart 2088", "run chart 2088" | `get_chart_data(config, chart_id=2088)` | |
| "pull chart 2085", "download chart 2085" | `pull_charts(config, chart_id=2085)` | |
| "pull charts 2085,2088,2090" | `pull_charts(config, chart_ids="2085,2088,2090")` | |
| "push charts", "upload charts" | `push_charts(config)` | |

## Execution

1. Parse user intent and extract chart IDs if mentioned
2. Call the appropriate function
3. Display results using `format_output(result, fmt="table")`
4. For errors, explain what went wrong in business terms

## Output Formatting

Use `format_output()` for all results:

```python
result = list_charts(config, mine=True)
print(format_output(result, fmt="table"))
```

The user can request JSON or YAML output:
- "show chart 2085 as json" -> `format_output(result, fmt="json")`
- "list charts as yaml" -> `format_output(result, fmt="yaml")`
```

- [ ] **Step 2: Update router skill with chart routing**

In `skills/preset/SKILL.md`:

**a) Update menu version (line 26):** Change `Preset Toolkit v0.5.0` to `Preset Toolkit v0.7.0`.

**b) Add chart to menu (after item 8):**
```
  9.  chart         /preset-toolkit:preset-chart
```

**c) Add to routing table (after the `review` row, around line 61):**
```markdown
| `chart`, `charts`, `list charts`, `chart info`, `chart sql`, `chart data` | `preset-toolkit:preset-chart` |
```

**d) Add to NLP routing section (after "Review my changes" bullet, around line 81):**
```markdown
- "List my charts" -> `preset-toolkit:preset-chart`
- "Show chart 2085" -> `preset-toolkit:preset-chart`
- "What SQL does chart 2085 use?" -> `preset-toolkit:preset-chart`
- "Get data from chart 2088" -> `preset-toolkit:preset-chart`
- "Pull chart 2085" -> `preset-toolkit:preset-chart`
```

- [ ] **Step 3: Commit**

```bash
git add skills/preset-chart/SKILL.md skills/preset/SKILL.md
git commit -m "feat: preset-chart skill with NLP routing for chart operations"
```

---

### Task 11: Version Bump + README Update + Full Test Run

**Files:**
- Modify: `.claude-plugin/marketplace.json`
- Modify: `README.md`

- [ ] **Step 1: Update version to 0.7.0**

In `.claude-plugin/marketplace.json`, bump `"version": "0.6.0"` to `"version": "0.7.0"`.

- [ ] **Step 2: Run full test suite first (to get actual count)**

Run: `python3 -m pytest tests/test_sync.py tests/test_formatter.py tests/test_chart.py tests/test_config.py tests/test_dedup.py tests/test_fingerprint.py tests/test_ownership.py tests/test_telemetry.py tests/test_logger.py tests/test_deps.py -v`
Expected: ALL PASS. Note the exact total from the summary line (e.g., "N passed").

If any tests fail, stop and fix before proceeding.

- [ ] **Step 3: Update README with actual test count**

In `README.md`:
- Update version badge from `0.6.0` to `0.7.0`
- Update test count badge and text to the exact number from Step 2
- Update `## Skills (16)` heading to `## Skills (17)`
- Add chart skill to the skills table (after row 16):

```markdown
| 17 | Chart Ops | `/preset-toolkit:preset-chart` | List, inspect, query, pull, push charts |
```

- Update architecture tree — add `scripts/chart.py` and the chart skill:

In the `scripts/` section (after `│   ├── config.py`):
```
│   ├── chart.py              Chart operations (list/info/sql/data/pull/push)
```

In the `skills/` section (after `│   ├── preset-code-review/`):
```
│   ├── preset-chart/         Individual chart operations
```

- Update `scripts/` module count from "13 modules" to "14 modules"

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/marketplace.json README.md
git commit -m "chore: bump to v0.7.0 — chart operations (sub-project 2 of 6)"
```
