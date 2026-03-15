"""Tests for SQL execution module."""
import json as json_mod
from unittest.mock import patch, MagicMock

import pytest
import yaml

from scripts.sql import SqlResult, resolve_database_id
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


# ── Task 2: resolve_database_id ───────────────────────────────────

def test_resolve_database_id_from_yaml(tmp_path):
    """resolve_database_id reads the first YAML file's id field."""
    cfg = _make_sql_config(tmp_path)
    db_dir = tmp_path / "sync" / "assets" / "databases"
    db_dir.mkdir(parents=True)
    (db_dir / "analytics.yaml").write_text(yaml.safe_dump({"id": 42, "name": "analytics_db"}))

    result = resolve_database_id(cfg)
    assert result == 42


def test_resolve_database_id_no_directory(tmp_path):
    """resolve_database_id returns None when databases/ dir does not exist."""
    cfg = _make_sql_config(tmp_path)
    result = resolve_database_id(cfg)
    assert result is None


def test_resolve_database_id_empty_directory(tmp_path):
    """resolve_database_id returns None when databases/ dir has no YAML files."""
    cfg = _make_sql_config(tmp_path)
    db_dir = tmp_path / "sync" / "assets" / "databases"
    db_dir.mkdir(parents=True)

    result = resolve_database_id(cfg)
    assert result is None


def test_resolve_database_id_no_id_field(tmp_path):
    """resolve_database_id skips YAML files without an id field."""
    cfg = _make_sql_config(tmp_path)
    db_dir = tmp_path / "sync" / "assets" / "databases"
    db_dir.mkdir(parents=True)
    (db_dir / "no_id.yaml").write_text(yaml.safe_dump({"name": "analytics_db"}))

    result = resolve_database_id(cfg)
    assert result is None


def test_resolve_database_id_malformed_yaml(tmp_path):
    """resolve_database_id skips malformed YAML and continues to next file."""
    cfg = _make_sql_config(tmp_path)
    db_dir = tmp_path / "sync" / "assets" / "databases"
    db_dir.mkdir(parents=True)
    (db_dir / "bad.yaml").write_text(":::not valid yaml{{{")
    (db_dir / "good.yaml").write_text(yaml.safe_dump({"id": 99, "name": "good_db"}))

    result = resolve_database_id(cfg)
    assert result == 99


def test_resolve_database_id_sorted_determinism(tmp_path):
    """resolve_database_id picks the first file alphabetically."""
    cfg = _make_sql_config(tmp_path)
    db_dir = tmp_path / "sync" / "assets" / "databases"
    db_dir.mkdir(parents=True)
    (db_dir / "b_second.yaml").write_text(yaml.safe_dump({"id": 200}))
    (db_dir / "a_first.yaml").write_text(yaml.safe_dump({"id": 100}))

    result = resolve_database_id(cfg)
    assert result == 100
