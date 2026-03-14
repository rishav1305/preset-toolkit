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
