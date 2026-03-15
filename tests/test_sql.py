"""Tests for SQL execution module."""
import json as json_mod
from unittest.mock import patch, MagicMock

import pytest
import yaml

from scripts.sql import SqlResult, resolve_database_id, execute_sql
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


# ── Task 3: execute_sql ───────────────────────────────────────────

def test_execute_sql_success(tmp_path):
    """execute_sql parses JSON output into SqlResult on success."""
    cfg = _make_sql_config(tmp_path)
    sup_json = json_mod.dumps({
        "columns": ["date", "revenue"],
        "data": [
            {"date": "2026-01", "revenue": 100},
            {"date": "2026-02", "revenue": 200},
        ],
        "rowcount": 2,
    })
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = execute_sql(cfg, "SELECT date, revenue FROM sales")

    assert result.success is True
    assert result.columns == ["date", "revenue"]
    assert len(result.rows) == 2
    assert result.rows[0]["revenue"] == 100
    assert result.row_count == 2

    args = mock_sup.call_args[0][0]
    assert args[0] == "sql"
    assert "SELECT date, revenue FROM sales" in args
    assert "--json" in args


def test_execute_sql_with_database_id(tmp_path):
    """execute_sql passes --database-id when explicitly provided."""
    cfg = _make_sql_config(tmp_path)
    sup_json = json_mod.dumps({"columns": [], "data": [], "rowcount": 0})
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        execute_sql(cfg, "SELECT 1", database_id=42)

    args = mock_sup.call_args[0][0]
    assert "--database-id" in args
    assert "42" in args


def test_execute_sql_with_limit(tmp_path):
    """execute_sql passes --limit flag when limit is provided."""
    cfg = _make_sql_config(tmp_path)
    sup_json = json_mod.dumps({"columns": ["x"], "data": [{"x": 1}], "rowcount": 1})
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        execute_sql(cfg, "SELECT 1", limit=100)

    args = mock_sup.call_args[0][0]
    assert "--limit" in args
    assert "100" in args


def test_execute_sql_auto_resolves_database_id(tmp_path):
    """execute_sql auto-resolves database_id from YAML when not provided."""
    cfg = _make_sql_config(tmp_path)
    db_dir = tmp_path / "sync" / "assets" / "databases"
    db_dir.mkdir(parents=True)
    (db_dir / "main.yaml").write_text(yaml.safe_dump({"id": 77, "name": "main_db"}))

    sup_json = json_mod.dumps({"columns": [], "data": [], "rowcount": 0})
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        execute_sql(cfg, "SELECT 1")

    args = mock_sup.call_args[0][0]
    assert "--database-id" in args
    assert "77" in args


def test_execute_sql_no_database_id_available(tmp_path):
    """execute_sql omits --database-id when none is provided and none can be resolved."""
    cfg = _make_sql_config(tmp_path)
    sup_json = json_mod.dumps({"columns": [], "data": [], "rowcount": 0})
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        execute_sql(cfg, "SELECT 1")

    args = mock_sup.call_args[0][0]
    assert "--database-id" not in args


def test_execute_sql_sup_failure(tmp_path):
    """execute_sql returns error result when sup exits non-zero."""
    cfg = _make_sql_config(tmp_path)
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="auth error")
        result = execute_sql(cfg, "SELECT 1")

    assert result.success is False
    assert "auth error" in result.error


def test_execute_sql_malformed_json(tmp_path):
    """execute_sql handles malformed JSON gracefully."""
    cfg = _make_sql_config(tmp_path)
    with patch("scripts.sql.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout="not json at all", stderr="")
        result = execute_sql(cfg, "SELECT 1")

    assert result.success is False
    assert "parse" in result.error.lower() or "json" in result.error.lower()
