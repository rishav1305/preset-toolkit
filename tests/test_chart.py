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
    list_charts,
    get_chart_info,
    get_chart_sql,
    get_chart_data,
    pull_charts,
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


# ── get_chart_info ────────────────────────────────────────────────

def test_get_chart_info_success(tmp_path):
    """get_chart_info parses JSON dict into ChartInfo fields + raw dict."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({
        "id": 2085,
        "slice_name": "Revenue Overview",
        "viz_type": "big_number_total",
        "datasource_name_text": "Main_Dataset",
        "query_context": '{"datasource":{"id":42}}',
        "params": '{"metric":"sum__revenue"}',
        "extra_field": "should appear in raw",
    })
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = get_chart_info(cfg, 2085)

    assert result.success is True
    assert result.id == 2085
    assert result.name == "Revenue Overview"
    assert result.viz_type == "big_number_total"
    assert result.dataset_name == "Main_Dataset"
    assert result.query_context == '{"datasource":{"id":42}}'
    assert result.params == '{"metric":"sum__revenue"}'
    assert result.raw["extra_field"] == "should appear in raw"
    assert result.raw["id"] == 2085

    args = mock_sup.call_args[0][0]
    assert args == ["chart", "info", "2085", "--json"]


def test_get_chart_info_failure(tmp_path):
    """get_chart_info returns error on sup failure."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="chart not found")
        result = get_chart_info(cfg, 9999)

    assert result.success is False
    assert "chart not found" in result.error


# ── get_chart_sql ─────────────────────────────────────────────────

def test_get_chart_sql_success(tmp_path):
    """get_chart_sql extracts the result field from JSON response."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({
        "result": "SELECT SUM(revenue) FROM sales WHERE date >= '2026-01-01'"
    })
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = get_chart_sql(cfg, 2085)

    assert result.success is True
    assert result.sql == "SELECT SUM(revenue) FROM sales WHERE date >= '2026-01-01'"

    args = mock_sup.call_args[0][0]
    assert args == ["chart", "sql", "2085", "--json"]


def test_get_chart_sql_failure(tmp_path):
    """get_chart_sql returns error on sup failure."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="sql generation failed")
        result = get_chart_sql(cfg, 2085)

    assert result.success is False
    assert "sql generation failed" in result.error


# ── get_chart_data ────────────────────────────────────────────────

def test_get_chart_data_success(tmp_path):
    """get_chart_data parses columns, rows, and row_count from JSON."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({
        "columns": ["date", "revenue", "users"],
        "data": [
            {"date": "2026-01", "revenue": 100, "users": 50},
            {"date": "2026-02", "revenue": 200, "users": 75},
        ],
        "rowcount": 2,
    })
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = get_chart_data(cfg, 2085)

    assert result.success is True
    assert result.columns == ["date", "revenue", "users"]
    assert len(result.rows) == 2
    assert result.rows[0]["revenue"] == 100
    assert result.row_count == 2

    args = mock_sup.call_args[0][0]
    assert args == ["chart", "data", "2085", "--json"]


def test_get_chart_data_with_limit(tmp_path):
    """get_chart_data passes --limit flag when limit is provided."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({
        "columns": ["date"],
        "data": [{"date": "2026-01"}],
        "rowcount": 1,
    })
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        get_chart_data(cfg, 2085, limit=50)

    args = mock_sup.call_args[0][0]
    assert "--limit" in args
    assert "50" in args


def test_get_chart_data_failure(tmp_path):
    """get_chart_data returns error on sup failure."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="data fetch error")
        result = get_chart_data(cfg, 2085)

    assert result.success is False
    assert "data fetch error" in result.error


# ── pull_charts ───────────────────────────────────────────────────

def test_pull_charts_single(tmp_path):
    """pull_charts with a single chart_id passes --chart-id flag."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({
        "charts_pulled": 1,
        "files": ["charts/revenue.yaml"],
    })
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = pull_charts(cfg, chart_id=2085)

    assert result.success is True
    assert result.charts_pulled == 1
    assert result.files == ["charts/revenue.yaml"]

    args = mock_sup.call_args[0][0]
    assert "--chart-id" in args
    assert "2085" in args


def test_pull_charts_multiple(tmp_path):
    """pull_charts with chart_ids passes --chart-ids flag."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({
        "charts_pulled": 2,
        "files": ["charts/a.yaml", "charts/b.yaml"],
    })
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = pull_charts(cfg, chart_ids=[2085, 2088])

    assert result.success is True
    assert result.charts_pulled == 2
    assert len(result.files) == 2

    args = mock_sup.call_args[0][0]
    assert "--chart-ids" in args
    assert "2085,2088" in args


def test_pull_charts_mutual_exclusion(tmp_path):
    """pull_charts raises ValueError if both chart_id and chart_ids provided."""
    cfg = _make_chart_config(tmp_path)
    with pytest.raises(ValueError, match="chart_id.*chart_ids"):
        pull_charts(cfg, chart_id=2085, chart_ids=[2085, 2088])


def test_pull_charts_with_filters(tmp_path):
    """pull_charts passes all filter flags correctly."""
    cfg = _make_chart_config(tmp_path)
    sup_json = json_mod.dumps({"charts_pulled": 0, "files": []})
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        pull_charts(
            cfg,
            name="Revenue",
            mine=True,
            modified_after="2026-01-01",
            limit=5,
            skip_dependencies=True,
            overwrite=False,
            assets_folder="/tmp/assets",
        )

    args = mock_sup.call_args[0][0]
    assert "--name" in args
    assert "Revenue" in args
    assert "--mine" in args
    assert "--modified-after" in args
    assert "2026-01-01" in args
    assert "--limit" in args
    assert "5" in args
    assert "--skip-dependencies" in args
    assert "--no-overwrite" in args
    assert "--assets-folder" in args
    assert "/tmp/assets" in args


def test_pull_charts_failure(tmp_path):
    """pull_charts returns error on sup failure."""
    cfg = _make_chart_config(tmp_path)
    with patch("scripts.chart.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="pull failed")
        result = pull_charts(cfg)

    assert result.success is False
    assert "pull failed" in result.error
