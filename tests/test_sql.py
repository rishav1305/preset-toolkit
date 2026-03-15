"""Tests for SQL execution module."""
import json as json_mod
from unittest.mock import patch, MagicMock

import pytest
import yaml

from scripts.sql import SqlResult
from scripts.config import ToolkitConfig


def _make_sql_config(tmp_path):
    """Helper to create a minimal ToolkitConfig for SQL tests."""
    config_dir = tmp_path / ".preset-toolkit"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(yaml.safe_dump({
        "version": 1,
        "workspace": {"url": "https://test.preset.io", "id": "test123"},
        "dashboard": {"id": 1, "name": "Test"},
    }))
    return ToolkitConfig.load(config_path)


# ── Task 1: SqlResult dataclass ───────────────────────────────────

def test_sql_result_creation():
    """SqlResult holds query execution results with all fields populated."""
    result = SqlResult(
        success=True,
        columns=["date", "revenue"],
        rows=[{"date": "2026-01", "revenue": 100}],
        row_count=1,
    )
    assert result.success is True
    assert result.columns == ["date", "revenue"]
    assert len(result.rows) == 1
    assert result.rows[0]["revenue"] == 100
    assert result.row_count == 1
    assert result.error == ""


def test_sql_result_defaults():
    """SqlResult defaults to empty collections and zero row_count."""
    result = SqlResult(success=False, error="something broke")
    assert result.success is False
    assert result.columns == []
    assert result.rows == []
    assert result.row_count == 0
    assert result.error == "something broke"
