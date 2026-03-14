"""Tests for output formatter module."""
import json

import pytest
import yaml

from scripts.chart import (
    ChartSummary, ChartListResult, ChartInfo, ChartSQL,
    ChartData, ChartPullResult, ChartPushResult,
)
from scripts.formatter import format_output
from scripts.sync import AssetChange, ChangeAction, DryRunResult, SyncResult


# ── Table format ────────────────────────────────────────────────────


def test_format_dry_run_result_table():
    """Table format renders changes as human-readable lines."""
    result = DryRunResult(
        success=True,
        changes=[
            AssetChange("chart", "Revenue Overview", ChangeAction.CREATE),
            AssetChange("dataset", "Main_Dataset", ChangeAction.UPDATE),
            AssetChange("chart", "Old Chart", ChangeAction.DELETE),
        ],
        validation_passed=True,
        markers_passed=True,
        raw_output="",
    )
    output = format_output(result, fmt="table")
    assert "Revenue Overview" in output
    assert "Main_Dataset" in output
    assert "Old Chart" in output
    assert "create" in output.lower()
    assert "update" in output.lower()
    assert "delete" in output.lower()


def test_format_dry_run_result_table_no_changes():
    """Table format shows 'no changes' when changes list is empty."""
    result = DryRunResult(
        success=True,
        changes=[],
        validation_passed=True,
        markers_passed=True,
        raw_output="All up to date",
    )
    output = format_output(result, fmt="table")
    assert "no changes" in output.lower()


def test_format_sync_result_table():
    """Table format works with SyncResult too."""
    result = SyncResult(
        success=True,
        steps_completed=["pull", "dedup: removed 2 chart duplicates"],
    )
    output = format_output(result, fmt="table")
    assert "pull" in output
    assert "dedup" in output


# ── JSON format ─────────────────────────────────────────────────────


def test_format_dry_run_result_json():
    """JSON format produces valid parseable JSON."""
    result = DryRunResult(
        success=True,
        changes=[
            AssetChange("chart", "Revenue", ChangeAction.CREATE),
        ],
        validation_passed=True,
        markers_passed=True,
        raw_output='Creating chart "Revenue"',
    )
    output = format_output(result, fmt="json")
    parsed = json.loads(output)
    assert parsed["success"] is True
    assert parsed["validation_passed"] is True
    assert len(parsed["changes"]) == 1
    assert parsed["changes"][0]["name"] == "Revenue"
    assert parsed["changes"][0]["action"] == "create"


def test_format_sync_result_json():
    """JSON format works with SyncResult."""
    result = SyncResult(success=True, steps_completed=["pull"])
    output = format_output(result, fmt="json")
    parsed = json.loads(output)
    assert parsed["success"] is True
    assert "pull" in parsed["steps_completed"]


# ── YAML format ─────────────────────────────────────────────────────


def test_format_dry_run_result_yaml():
    """YAML format produces valid parseable YAML."""
    result = DryRunResult(
        success=True,
        changes=[
            AssetChange("dataset", "Main", ChangeAction.UPDATE),
        ],
        validation_passed=True,
        markers_passed=True,
        raw_output='Updating dataset "Main"',
    )
    output = format_output(result, fmt="yaml")
    parsed = yaml.safe_load(output)
    assert parsed["success"] is True
    assert len(parsed["changes"]) == 1
    assert parsed["changes"][0]["action"] == "update"


# ── Error handling ──────────────────────────────────────────────────


def test_format_invalid_format_raises():
    """Unknown format raises ValueError."""
    result = SyncResult(success=True)
    with pytest.raises(ValueError, match="Unknown format"):
        format_output(result, fmt="xml")


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


def test_format_chart_data_json():
    """ChartData JSON is valid and preserves rows."""
    result = ChartData(
        success=True,
        columns=["date", "revenue"],
        rows=[{"date": "2026-01", "revenue": 100}],
        row_count=1,
    )
    output = format_output(result, fmt="json")
    parsed = json.loads(output)
    assert parsed["success"] is True
    assert parsed["columns"] == ["date", "revenue"]
    assert parsed["row_count"] == 1


def test_format_chart_info_yaml():
    """ChartInfo YAML is valid."""
    result = ChartInfo(success=True, id=2085, name="Revenue", viz_type="big_number_total")
    output = format_output(result, fmt="yaml")
    parsed = yaml.safe_load(output)
    assert parsed["id"] == 2085
    assert parsed["name"] == "Revenue"
