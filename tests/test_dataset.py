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
