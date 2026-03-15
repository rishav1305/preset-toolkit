"""Tests for scripts/jinja_check.py — Jinja extraction, validation, and YAML scanning."""
from pathlib import Path

import pytest

from scripts.jinja_check import (
    JinjaExpression,
    JinjaFinding,
    JinjaScanResult,
    extract_jinja_expressions,
    validate_jinja,
    scan_yaml_jinja,
)
from scripts.config import ToolkitConfig


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_jinja_config(tmp_path: Path) -> ToolkitConfig:
    """Create a ToolkitConfig whose sync folder lives under tmp_path."""
    toolkit_dir = tmp_path / ".preset-toolkit"
    toolkit_dir.mkdir()
    config_path = toolkit_dir / "config.yaml"
    config_path.write_text(
        "version: 1\n"
        "workspace:\n"
        "  url: https://test.preset.io\n"
        "  id: '1'\n"
        "dashboard:\n"
        "  id: 1\n"
        "  name: test\n"
        "  sync_folder: sync\n"
    )
    # Create the sync/assets directory
    assets_dir = tmp_path / "sync" / "assets"
    assets_dir.mkdir(parents=True)
    return ToolkitConfig.load(config_path)


# ---------------------------------------------------------------------------
# Dataclass tests
# ---------------------------------------------------------------------------

class TestDataclasses:
    def test_jinja_expression_creation(self):
        expr = JinjaExpression(expression="{{ x }}", expr_type="variable")
        assert expr.expression == "{{ x }}"
        assert expr.expr_type == "variable"

    def test_jinja_finding_defaults(self):
        finding = JinjaFinding(file_path="test.yaml")
        assert finding.file_path == "test.yaml"
        assert finding.field_name == ""
        assert finding.expressions == []
        assert finding.errors == []
        assert finding.valid is True

    def test_jinja_scan_result_defaults(self):
        result = JinjaScanResult(success=True)
        assert result.success is True
        assert result.files_scanned == 0
        assert result.files_with_jinja == 0
        assert result.total_expressions == 0
        assert result.findings == []
        assert result.errors == []
        assert result.error == ""


# ---------------------------------------------------------------------------
# extract_jinja_expressions tests
# ---------------------------------------------------------------------------

class TestExtract:
    def test_extract_variable_expression(self):
        sql = "SELECT * WHERE col = {{ filter_values('col') }}"
        exprs = extract_jinja_expressions(sql)
        assert len(exprs) == 1
        assert exprs[0].expression == "{{ filter_values('col') }}"
        assert exprs[0].expr_type == "variable"

    def test_extract_block_expression(self):
        sql = "{% if true %}SELECT 1{% endif %}"
        exprs = extract_jinja_expressions(sql)
        assert len(exprs) == 2
        assert exprs[0].expr_type == "block"
        assert exprs[1].expr_type == "block"
        assert "{% if true %}" in exprs[0].expression
        assert "{% endif %}" in exprs[1].expression

    def test_extract_comment_expression(self):
        sql = "SELECT 1 {# this is a comment #}"
        exprs = extract_jinja_expressions(sql)
        assert len(exprs) == 1
        assert exprs[0].expression == "{# this is a comment #}"
        assert exprs[0].expr_type == "comment"

    def test_extract_mixed_expressions(self):
        sql = (
            "{% if x %}"
            "SELECT {{ col }} FROM t "
            "{# note #}"
            "{% endif %}"
        )
        exprs = extract_jinja_expressions(sql)
        types = {e.expr_type for e in exprs}
        assert types == {"variable", "block", "comment"}

    def test_extract_no_jinja(self):
        sql = "SELECT id, name FROM users WHERE active = 1"
        exprs = extract_jinja_expressions(sql)
        assert exprs == []


# ---------------------------------------------------------------------------
# validate_jinja tests
# ---------------------------------------------------------------------------

class TestValidate:
    def test_validate_valid_jinja(self):
        sql = "SELECT * WHERE date = {{ filter_values('x') }}"
        finding = validate_jinja(sql)
        assert finding.valid is True
        assert finding.errors == []
        assert len(finding.expressions) == 1

    def test_validate_unbalanced_braces(self):
        sql = "SELECT * WHERE date = {{ filter_values('x')"
        finding = validate_jinja(sql)
        assert finding.valid is False
        assert len(finding.errors) >= 1
        assert any("Unbalanced" in e or "syntax error" in e.lower() for e in finding.errors)

    def test_validate_no_jinja_is_valid(self):
        sql = "SELECT id FROM users"
        finding = validate_jinja(sql)
        assert finding.valid is True
        assert finding.errors == []
        assert finding.expressions == []

    def test_validate_empty_string(self):
        finding = validate_jinja("")
        assert finding.valid is True
        assert finding.errors == []


# ---------------------------------------------------------------------------
# scan_yaml_jinja tests
# ---------------------------------------------------------------------------

class TestScan:
    def test_scan_yaml_with_jinja(self, tmp_path):
        config = _make_jinja_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        chart_yaml = assets / "chart.yaml"
        chart_yaml.write_text(
            "slice_name: My Chart\n"
            "sql: \"SELECT * WHERE date = {{ filter_values('d')[0] }}\"\n"
        )

        result = scan_yaml_jinja(config)
        assert result.success is True
        assert result.files_scanned == 1
        assert result.files_with_jinja == 1
        assert result.total_expressions >= 1
        assert len(result.findings) >= 1
        assert result.findings[0].expressions[0].expr_type == "variable"

    def test_scan_yaml_no_jinja(self, tmp_path):
        config = _make_jinja_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        chart_yaml = assets / "chart.yaml"
        chart_yaml.write_text(
            "slice_name: Plain Chart\n"
            "sql: \"SELECT id FROM users\"\n"
        )

        result = scan_yaml_jinja(config)
        assert result.success is True
        assert result.files_scanned == 1
        assert result.files_with_jinja == 0
        assert result.total_expressions == 0
        assert result.findings == []

    def test_scan_yaml_empty_directory(self, tmp_path):
        config = _make_jinja_config(tmp_path)

        result = scan_yaml_jinja(config)
        assert result.success is True
        assert result.files_scanned == 0
        assert result.files_with_jinja == 0

    def test_scan_yaml_malformed_yaml(self, tmp_path):
        config = _make_jinja_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        bad_yaml = assets / "broken.yaml"
        bad_yaml.write_text(": : : [invalid yaml\n  bad:\n]]]")

        result = scan_yaml_jinja(config)
        assert result.success is True
        assert result.files_scanned == 1
        assert len(result.errors) >= 1
        assert any("YAML parse error" in e for e in result.errors)
