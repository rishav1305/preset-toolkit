"""Tests for output formatter module."""
import json

import pytest
import yaml

from scripts.chart import (
    ChartSummary, ChartListResult, ChartInfo, ChartSQL,
    ChartData, ChartPullResult, ChartPushResult,
)
from scripts.dataset import (
    DatasetSummary, DatasetListResult, DatasetInfo, DatasetSQL,
    DatasetData, DatasetPullResult, DatasetPushResult,
)
from scripts.dashboard import (
    DashboardSummary, DashboardListResult, DashboardInfo, DashboardPullResult,
)
from scripts.formatter import format_output
from scripts.sql import SqlResult
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
    """DatasetPullResult table shows summary and files."""
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


# ── SqlResult formats ──────────────────────────────────────────────


def test_format_sql_result_table():
    """SqlResult table shows columnar data with row count."""
    result = SqlResult(
        success=True,
        columns=["id", "name"],
        rows=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
        row_count=2,
    )
    output = format_output(result, fmt="table")
    assert "id" in output
    assert "name" in output
    assert "Alice" in output
    assert "Bob" in output
    assert "2 row(s)" in output


def test_format_sql_result_empty_table():
    """SqlResult table shows 'No rows returned.' when empty."""
    result = SqlResult(success=True, columns=[], rows=[], row_count=0)
    output = format_output(result, fmt="table")
    assert "No rows returned." in output


def test_format_sql_result_error():
    """SqlResult table shows ERROR when success is False."""
    result = SqlResult(success=False, error="Permission denied for table orders")
    output = format_output(result, fmt="table")
    assert "ERROR" in output
    assert "Permission denied" in output


def test_format_sql_result_json():
    """SqlResult JSON is valid and preserves structure."""
    result = SqlResult(
        success=True,
        columns=["id", "amount"],
        rows=[{"id": 1, "amount": 100}],
        row_count=1,
    )
    output = format_output(result, fmt="json")
    parsed = json.loads(output)
    assert parsed["success"] is True
    assert parsed["columns"] == ["id", "amount"]
    assert parsed["row_count"] == 1
    assert len(parsed["rows"]) == 1


def test_format_sql_result_yaml():
    """SqlResult YAML is valid and preserves structure."""
    result = SqlResult(
        success=True,
        columns=["id", "amount"],
        rows=[{"id": 1, "amount": 250}],
        row_count=1,
    )
    output = format_output(result, fmt="yaml")
    parsed = yaml.safe_load(output)
    assert parsed["success"] is True
    assert parsed["columns"] == ["id", "amount"]
    assert parsed["row_count"] == 1
    assert len(parsed["rows"]) == 1


# ── Dashboard table formats ────────────────────────────────────────


def test_format_dashboard_list_table():
    """DashboardListResult table shows ID, Name, Status, URL, Modified columns."""
    result = DashboardListResult(
        success=True,
        dashboards=[
            DashboardSummary(id=76, name="Sales Overview", status="published",
                             url="https://preset.io/d/76", modified="2026-03-15T00:00:00Z"),
            DashboardSummary(id=89, name="Marketing KPIs", status="draft",
                             url="https://preset.io/d/89", modified="2026-03-14T00:00:00Z"),
        ],
        total=2,
    )
    output = format_output(result, fmt="table")
    assert "76" in output
    assert "Sales Overview" in output
    assert "published" in output
    assert "89" in output
    assert "Marketing KPIs" in output
    assert "draft" in output
    assert "2 dashboard(s)" in output


def test_format_dashboard_list_empty_table():
    """DashboardListResult table shows 'No dashboards found.' when empty."""
    result = DashboardListResult(success=True, dashboards=[], total=0)
    output = format_output(result, fmt="table")
    assert "No dashboards found." in output


def test_format_dashboard_info_table():
    """DashboardInfo table shows key-value metadata."""
    result = DashboardInfo(
        success=True, id=76, name="Sales Overview", status="published",
        url="https://preset.io/d/76", slug="sales-overview",
        charts=[{"id": 1}, {"id": 2}, {"id": 3}],
        css=".dashboard { color: red; }",
    )
    output = format_output(result, fmt="table")
    assert "76" in output
    assert "Sales Overview" in output
    assert "published" in output
    assert "sales-overview" in output
    assert "Charts:  3" in output
    assert "26 chars" in output


def test_format_dashboard_pull_table():
    """DashboardPullResult table shows summary and files."""
    result = DashboardPullResult(
        success=True, dashboards_pulled=2,
        files=["dashboards/sales.yaml", "dashboards/marketing.yaml"],
    )
    output = format_output(result, fmt="table")
    assert "Dashboards pulled: 2" in output
    assert "dashboards/sales.yaml" in output
    assert "dashboards/marketing.yaml" in output


def test_format_dashboard_list_json():
    """DashboardListResult JSON is valid and parseable."""
    result = DashboardListResult(
        success=True,
        dashboards=[DashboardSummary(id=76, name="Sales Overview", status="published")],
        total=1,
    )
    output = format_output(result, fmt="json")
    parsed = json.loads(output)
    assert parsed["success"] is True
    assert len(parsed["dashboards"]) == 1
    assert parsed["dashboards"][0]["name"] == "Sales Overview"
