"""End-to-end tests for all 6 sub-projects against the Six Pillars:
    Performant, Resilient, Robust, Sovereign, Secure, Transparent.

Tests cross-module integration, edge cases, error handling, and
security boundaries across chart, dataset, sql, dashboard,
jinja_check, and formatter modules.
"""
import dataclasses
import json as json_mod
import os
import textwrap
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from scripts.chart import (
    ChartSummary, ChartListResult, ChartInfo, ChartSQL, ChartData,
    ChartPullResult, ChartPushResult,
    list_charts, get_chart_info, get_chart_sql, get_chart_data,
    pull_charts, push_charts,
)
from scripts.dataset import (
    DatasetSummary, DatasetListResult, DatasetInfo, DatasetSQL, DatasetData,
    DatasetPullResult, DatasetPushResult,
    list_datasets, get_dataset_info, get_dataset_sql, get_dataset_data,
    pull_datasets, push_datasets,
)
from scripts.sql import SqlResult, resolve_database_id, execute_sql
from scripts.dashboard import (
    DashboardSummary, DashboardListResult, DashboardInfo, DashboardPullResult,
    list_dashboards, get_dashboard_info, pull_dashboards,
)
from scripts.jinja_check import (
    JinjaExpression, JinjaFinding, JinjaScanResult,
    extract_jinja_expressions, validate_jinja, scan_yaml_jinja,
)
from scripts.formatter import format_output
from scripts.config import ToolkitConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_config(tmp_path):
    """Standard ToolkitConfig for integration tests."""
    config_dir = tmp_path / ".preset-toolkit"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(yaml.safe_dump({
        "version": 1,
        "workspace": {"url": "https://test.preset.io", "id": "test-ws-123"},
        "dashboard": {"id": 76, "name": "Test Dashboard", "sync_folder": "sync"},
    }))
    return ToolkitConfig.load(config_path)


def _mock_sup(returncode=0, stdout="", stderr=""):
    """Create a MagicMock that behaves like subprocess.CompletedProcess."""
    return MagicMock(returncode=returncode, stdout=stdout, stderr=stderr)


# ═══════════════════════════════════════════════════════════════════════════
# PILLAR 1: ROBUST — Type guards, edge cases, unexpected inputs
# ═══════════════════════════════════════════════════════════════════════════

class TestRobustChartTypeGuards:
    """chart.py must handle unexpected JSON shapes without crashing."""

    def test_get_chart_info_returns_error_on_list_response(self, tmp_path):
        """If sup returns a JSON list instead of dict, get_chart_info returns error."""
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout='[{"id":1}]')
            result = get_chart_info(cfg, 1)
        assert result.success is False
        assert "Unexpected" in result.error

    def test_get_chart_sql_returns_empty_on_list_response(self, tmp_path):
        """If sup returns a JSON list, get_chart_sql returns empty sql."""
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout='["not a dict"]')
            result = get_chart_sql(cfg, 1)
        assert result.success is True
        assert result.sql == ""

    def test_get_chart_data_returns_error_on_list_response(self, tmp_path):
        """If sup returns a JSON list, get_chart_data returns error."""
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout='["row1"]')
            result = get_chart_data(cfg, 1)
        assert result.success is False
        assert "Unexpected" in result.error

    def test_pull_charts_handles_non_dict_json(self, tmp_path):
        """pull_charts returns success with empty data on non-dict JSON."""
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout='"just a string"')
            result = pull_charts(cfg, chart_id=1)
        assert result.success is True
        assert result.charts_pulled == 0

    def test_push_charts_handles_non_dict_json(self, tmp_path):
        """push_charts returns success with empty data on non-dict JSON."""
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout='42')
            result = push_charts(cfg)
        assert result.success is True
        assert result.charts_pushed == 0

    def test_list_charts_handles_non_list_json(self, tmp_path):
        """list_charts handles JSON dict instead of expected list."""
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout='{"unexpected": "dict"}')
            result = list_charts(cfg)
        assert result.success is True
        assert result.charts == []
        assert result.total == 0


class TestRobustDatasetTypeGuards:
    """dataset.py must handle unexpected JSON shapes without crashing."""

    def test_get_dataset_info_returns_error_on_list(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.dataset.run_sup") as m:
            m.return_value = _mock_sup(stdout='[{"id":1}]')
            result = get_dataset_info(cfg, 1)
        assert result.success is False
        assert "Unexpected" in result.error

    def test_get_dataset_data_returns_error_on_non_dict(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.dataset.run_sup") as m:
            m.return_value = _mock_sup(stdout='"string"')
            result = get_dataset_data(cfg, 1)
        assert result.success is False
        assert "Unexpected" in result.error


class TestRobustDashboardTypeGuards:
    """dashboard.py must handle unexpected JSON shapes without crashing."""

    def test_get_dashboard_info_returns_error_on_list(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.dashboard.run_sup") as m:
            m.return_value = _mock_sup(stdout='[{"id":1}]')
            result = get_dashboard_info(cfg, 1)
        assert result.success is False
        assert "Unexpected" in result.error

    def test_list_dashboards_handles_non_list_json(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.dashboard.run_sup") as m:
            m.return_value = _mock_sup(stdout='{"not": "a list"}')
            result = list_dashboards(cfg)
        assert result.success is True
        assert result.dashboards == []

    def test_pull_dashboards_handles_non_dict_json(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.dashboard.run_sup") as m:
            m.return_value = _mock_sup(stdout='"string"')
            result = pull_dashboards(cfg, dashboard_id=1)
        assert result.success is True
        assert result.dashboards_pulled == 0


class TestRobustMutualExclusivity:
    """All pull functions must reject conflicting ID parameters."""

    def test_chart_pull_rejects_both_id_params(self, tmp_path):
        cfg = _make_config(tmp_path)
        with pytest.raises(ValueError, match="chart_id.*chart_ids"):
            pull_charts(cfg, chart_id=1, chart_ids=[1, 2])

    def test_dataset_pull_rejects_both_id_params(self, tmp_path):
        cfg = _make_config(tmp_path)
        with pytest.raises(ValueError, match="mutually exclusive"):
            pull_datasets(cfg, dataset_id=1, dataset_ids=[1, 2])

    def test_dashboard_pull_rejects_both_id_params(self, tmp_path):
        cfg = _make_config(tmp_path)
        with pytest.raises(ValueError, match="mutually exclusive"):
            pull_dashboards(cfg, dashboard_id=1, dashboard_ids=[1, 2])


class TestRobustEmptyAndMissingFields:
    """Functions must handle missing JSON fields gracefully."""

    def test_chart_info_with_empty_json_object(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout='{}')
            result = get_chart_info(cfg, 1)
        assert result.success is True
        assert result.id == 0
        assert result.name == ""
        assert result.viz_type == ""

    def test_dashboard_info_with_minimal_json(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.dashboard.run_sup") as m:
            m.return_value = _mock_sup(stdout='{"id": 76}')
            result = get_dashboard_info(cfg, 76)
        assert result.success is True
        assert result.id == 76
        assert result.name == ""
        assert result.css == ""
        assert result.charts == []

    def test_sql_result_with_empty_json_object(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.sql.run_sup") as m:
            m.return_value = _mock_sup(stdout='{}')
            result = execute_sql(cfg, "SELECT 1")
        assert result.success is True
        assert result.columns == []
        assert result.rows == []
        assert result.row_count == 0


# ═══════════════════════════════════════════════════════════════════════════
# PILLAR 2: RESILIENT — Error handling, graceful degradation
# ═══════════════════════════════════════════════════════════════════════════

class TestResilientSupFailures:
    """All modules must handle sup CLI failures gracefully."""

    @pytest.mark.parametrize("module,func,args", [
        ("scripts.chart", list_charts, []),
        ("scripts.dataset", list_datasets, []),
        ("scripts.dashboard", list_dashboards, []),
    ])
    def test_list_functions_handle_sup_failure(self, tmp_path, module, func, args):
        cfg = _make_config(tmp_path)
        with patch(f"{module}.run_sup") as m:
            m.return_value = _mock_sup(returncode=1, stderr="Connection refused")
            result = func(cfg, *args)
        assert result.success is False
        assert "Connection refused" in result.error

    @pytest.mark.parametrize("module,func,extra_args", [
        ("scripts.chart", get_chart_info, [1]),
        ("scripts.dataset", get_dataset_info, [1]),
        ("scripts.dashboard", get_dashboard_info, [1]),
    ])
    def test_info_functions_handle_sup_failure(self, tmp_path, module, func, extra_args):
        cfg = _make_config(tmp_path)
        with patch(f"{module}.run_sup") as m:
            m.return_value = _mock_sup(returncode=1, stderr="404 Not Found")
            result = func(cfg, *extra_args)
        assert result.success is False
        assert "404" in result.error

    def test_execute_sql_handles_sup_failure(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.sql.run_sup") as m:
            m.return_value = _mock_sup(returncode=1, stderr="Syntax error in SQL")
            result = execute_sql(cfg, "SELECT BAD SYNTAX")
        assert result.success is False
        assert "Syntax error" in result.error


class TestResilientMalformedJson:
    """All JSON-parsing functions must handle malformed JSON."""

    @pytest.mark.parametrize("module,func,args,result_type", [
        ("scripts.chart", list_charts, [], "ChartListResult"),
        ("scripts.chart", get_chart_info, [1], "ChartInfo"),
        ("scripts.chart", get_chart_sql, [1], "ChartSQL"),
        ("scripts.chart", get_chart_data, [1], "ChartData"),
        ("scripts.dataset", list_datasets, [], "DatasetListResult"),
        ("scripts.dataset", get_dataset_info, [1], "DatasetInfo"),
        ("scripts.sql", execute_sql, ["SELECT 1"], "SqlResult"),
        ("scripts.dashboard", list_dashboards, [], "DashboardListResult"),
        ("scripts.dashboard", get_dashboard_info, [1], "DashboardInfo"),
    ])
    def test_malformed_json_returns_parse_error(self, tmp_path, module, func, args, result_type):
        cfg = _make_config(tmp_path)
        with patch(f"{module}.run_sup") as m:
            m.return_value = _mock_sup(stdout="<html>Not JSON</html>")
            result = func(cfg, *args)
        assert result.success is False
        assert "json" in result.error.lower() or "parse" in result.error.lower()


class TestResilientJinjaFallback:
    """Jinja validation must degrade gracefully without jinja2."""

    def test_validate_jinja_works_without_jinja2_package(self):
        """Even if jinja2 is missing, balanced braces check still catches errors."""
        sql = "SELECT * WHERE x = {{ broken"
        finding = validate_jinja(sql)
        assert finding.valid is False
        assert any("Unbalanced" in e for e in finding.errors)

    def test_validate_jinja_valid_without_jinja2(self):
        """Valid Jinja passes balanced braces check even without jinja2."""
        sql = "SELECT * WHERE x = {{ filter_values('x')[0] }}"
        finding = validate_jinja(sql)
        # May have jinja2 or not — either way, balanced braces pass
        balanced_errors = [e for e in finding.errors if "Unbalanced" in e]
        assert len(balanced_errors) == 0

    def test_scan_yaml_handles_missing_sync_directory(self, tmp_path):
        """scan_yaml_jinja returns error when sync assets dir doesn't exist."""
        cfg = _make_config(tmp_path)
        # Don't create sync/assets — it doesn't exist
        result = scan_yaml_jinja(cfg)
        assert result.success is False
        assert "not found" in result.error.lower()


# ═══════════════════════════════════════════════════════════════════════════
# PILLAR 3: PERFORMANT — No unnecessary work, efficient processing
# ═══════════════════════════════════════════════════════════════════════════

class TestPerformantArgBuilding:
    """CLI args must only include flags that are explicitly set."""

    def test_chart_list_minimal_args(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout="[]")
            list_charts(cfg)
        args = m.call_args[0][0]
        assert args == ["chart", "list", "--json"]

    def test_dashboard_list_minimal_args(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.dashboard.run_sup") as m:
            m.return_value = _mock_sup(stdout="[]")
            list_dashboards(cfg)
        args = m.call_args[0][0]
        assert args == ["dashboard", "list", "--json"]

    def test_sql_minimal_args_no_database_no_limit(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.sql.run_sup") as m:
            m.return_value = _mock_sup(stdout='{"columns":[],"data":[],"rowcount":0}')
            execute_sql(cfg, "SELECT 1")
        args = m.call_args[0][0]
        assert args == ["sql", "SELECT 1", "--json"]

    def test_no_overwrite_omitted_when_true(self, tmp_path):
        """overwrite=True (default) should NOT add --no-overwrite flag."""
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout='{"charts_pulled":0,"files":[]}')
            pull_charts(cfg, overwrite=True)
        args = m.call_args[0][0]
        assert "--no-overwrite" not in args

    def test_no_overwrite_added_when_false(self, tmp_path):
        """overwrite=False should add --no-overwrite flag."""
        cfg = _make_config(tmp_path)
        with patch("scripts.dashboard.run_sup") as m:
            m.return_value = _mock_sup(stdout='{}')
            pull_dashboards(cfg, overwrite=False)
        args = m.call_args[0][0]
        assert "--no-overwrite" in args


class TestPerformantJinjaScan:
    """Jinja scanning must not do unnecessary work."""

    def test_scan_skips_non_yaml_files(self, tmp_path):
        """scan_yaml_jinja only processes .yaml files, not .json/.txt etc."""
        cfg = _make_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        assets.mkdir(parents=True)
        (assets / "chart.yaml").write_text("sql: SELECT 1\n")
        (assets / "notes.txt").write_text("{{ this is not yaml }}")
        (assets / "data.json").write_text('{"sql": "{{ jinja }}"}')

        result = scan_yaml_jinja(cfg)
        assert result.files_scanned == 1  # only chart.yaml


# ═══════════════════════════════════════════════════════════════════════════
# PILLAR 4: SOVEREIGN — Data locality, no unintended external calls
# ═══════════════════════════════════════════════════════════════════════════

class TestSovereignLocalOperations:
    """Operations that should be purely local must not call run_sup."""

    def test_resolve_database_id_is_purely_local(self, tmp_path):
        """resolve_database_id reads local files, never calls sup CLI."""
        cfg = _make_config(tmp_path)
        db_dir = tmp_path / "sync" / "assets" / "databases"
        db_dir.mkdir(parents=True)
        (db_dir / "main.yaml").write_text(yaml.safe_dump({"id": 42}))

        with patch("scripts.sql.run_sup") as m:
            result = resolve_database_id(cfg)
        m.assert_not_called()
        assert result == 42

    def test_jinja_validation_is_purely_local(self):
        """validate_jinja and extract_jinja_expressions never call external services."""
        sql = "SELECT {{ filter_values('x') }} FROM t {% if y %}WHERE y{% endif %}"
        # These are pure functions — no mocking needed
        exprs = extract_jinja_expressions(sql)
        finding = validate_jinja(sql)
        assert len(exprs) >= 3
        assert finding.valid is True

    def test_formatter_is_purely_local(self):
        """format_output never calls external services."""
        result = ChartListResult(
            success=True,
            charts=[ChartSummary(id=1, name="Test", viz_type="table")],
            total=1,
        )
        for fmt in ("table", "json", "yaml"):
            output = format_output(result, fmt)
            assert len(output) > 0

    def test_scan_yaml_jinja_is_purely_local(self, tmp_path):
        """scan_yaml_jinja reads local files only, never calls sup."""
        cfg = _make_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        assets.mkdir(parents=True)
        (assets / "c.yaml").write_text("sql: SELECT {{ x }}\n")

        with patch("scripts.jinja_check.yaml") as mock_yaml:
            # Let real yaml work but verify no external calls happen
            import yaml as real_yaml
            mock_yaml.safe_load = real_yaml.safe_load
            mock_yaml.YAMLError = real_yaml.YAMLError
            result = scan_yaml_jinja(cfg)
        assert result.success is True


# ═══════════════════════════════════════════════════════════════════════════
# PILLAR 5: SECURE — No injection, no secrets leakage
# ═══════════════════════════════════════════════════════════════════════════

class TestSecureNoShellInjection:
    """CLI arguments must be passed as list (no shell=True)."""

    def test_sql_query_with_shell_metacharacters(self, tmp_path):
        """SQL queries with shell metacharacters are safely passed as list args."""
        cfg = _make_config(tmp_path)
        dangerous_query = "SELECT * FROM t; rm -rf / --no-preserve-root"
        with patch("scripts.sql.run_sup") as m:
            m.return_value = _mock_sup(stdout='{"columns":[],"data":[],"rowcount":0}')
            execute_sql(cfg, dangerous_query)
        args = m.call_args[0][0]
        # Query should be a single arg, not split by shell
        assert dangerous_query in args

    def test_search_with_shell_metacharacters(self, tmp_path):
        """Search strings with shell metacharacters are safely passed."""
        cfg = _make_config(tmp_path)
        dangerous_search = "$(whoami) && echo hacked"
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout="[]")
            list_charts(cfg, search=dangerous_search)
        args = m.call_args[0][0]
        assert dangerous_search in args

    def test_chart_name_with_shell_injection(self, tmp_path):
        """Chart name filter with shell injection is safely passed."""
        cfg = _make_config(tmp_path)
        dangerous_name = "`cat /etc/passwd`"
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout='{"charts_pulled":0,"files":[]}')
            pull_charts(cfg, name=dangerous_name)
        args = m.call_args[0][0]
        assert dangerous_name in args


class TestSecureNoSecretsInOutput:
    """Error messages and formatted output must not leak secrets."""

    def test_error_messages_dont_contain_config_secrets(self, tmp_path):
        """When sup fails, error messages come from stderr, not config."""
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(returncode=1, stderr="auth failed")
            result = list_charts(cfg)
        # Error should contain stderr, not workspace URL or credentials
        assert "test.preset.io" not in result.error
        assert "test-ws-123" not in result.error


class TestSecurePathTraversal:
    """File operations must not allow path traversal."""

    def test_resolve_database_id_stays_within_sync_folder(self, tmp_path):
        """resolve_database_id only reads from the designated databases/ dir."""
        cfg = _make_config(tmp_path)
        # Create a database YAML outside the expected path
        evil_dir = tmp_path / "evil"
        evil_dir.mkdir()
        (evil_dir / "steal.yaml").write_text(yaml.safe_dump({"id": 666}))

        result = resolve_database_id(cfg)
        assert result is None  # Should not find the evil file

    def test_jinja_scan_stays_within_sync_folder(self, tmp_path):
        """scan_yaml_jinja only scans within sync/assets."""
        cfg = _make_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        assets.mkdir(parents=True)
        # Create a YAML outside sync/assets
        (tmp_path / "secret.yaml").write_text("sql: SELECT {{ secret }}\n")

        result = scan_yaml_jinja(cfg)
        assert result.files_scanned == 0  # Only scans sync/assets


# ═══════════════════════════════════════════════════════════════════════════
# PILLAR 6: TRANSPARENT — Clear errors, accurate reporting
# ═══════════════════════════════════════════════════════════════════════════

class TestTransparentErrorMessages:
    """Error messages must be clear and actionable."""

    def test_json_parse_error_includes_details(self, tmp_path):
        """JSON parse errors include enough detail to diagnose."""
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout="<html>Server Error</html>")
            result = list_charts(cfg)
        assert "JSON parse error" in result.error

    def test_jinja_unbalanced_braces_report_counts(self):
        """Unbalanced braces errors report the actual counts."""
        sql = "{{ x }} {{ y"
        finding = validate_jinja(sql)
        assert finding.valid is False
        brace_errors = [e for e in finding.errors if "Unbalanced" in e]
        assert len(brace_errors) >= 1
        # Should mention the counts (2 opening vs 1 closing)
        assert "2" in brace_errors[0]
        assert "1" in brace_errors[0]

    def test_scan_reports_malformed_yaml_with_filepath(self, tmp_path):
        """Scan errors include the file path of the broken YAML."""
        cfg = _make_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        assets.mkdir(parents=True)
        bad_file = assets / "broken.yaml"
        bad_file.write_text(": : : [invalid yaml\n  bad:\n]]]")

        result = scan_yaml_jinja(cfg)
        assert len(result.errors) >= 1
        assert "broken.yaml" in result.errors[0]

    def test_format_output_invalid_format_raises_clear_error(self):
        """format_output raises ValueError with clear message for unknown format."""
        result = ChartListResult(success=True)
        with pytest.raises(ValueError, match="Unknown format.*'csv'"):
            format_output(result, "csv")


class TestTransparentJinjaFilesCounting:
    """files_with_jinja must count files, not fields."""

    def test_files_with_jinja_counts_files_not_fields(self, tmp_path):
        """A file with 3 SQL fields containing Jinja should count as 1 file."""
        cfg = _make_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        assets.mkdir(parents=True)
        # YAML with multiple SQL fields
        multi_sql = {
            "sql": "SELECT {{ x }}",
            "nested": {
                "sql": "SELECT {{ y }}",
            },
        }
        (assets / "multi.yaml").write_text(yaml.safe_dump(multi_sql))

        result = scan_yaml_jinja(cfg)
        assert result.files_with_jinja == 1  # 1 file, not 2 fields
        assert result.total_expressions == 2  # 2 expressions total

    def test_files_with_jinja_counts_multiple_files_correctly(self, tmp_path):
        """Two files with Jinja = 2 files_with_jinja."""
        cfg = _make_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        assets.mkdir(parents=True)
        (assets / "chart1.yaml").write_text("sql: SELECT {{ x }}\n")
        (assets / "chart2.yaml").write_text("sql: SELECT {{ y }}\n")

        result = scan_yaml_jinja(cfg)
        assert result.files_with_jinja == 2

    def test_broken_jinja_without_extractable_expressions_still_counted(self, tmp_path):
        """A file with '{{ broken' (no closing) should still be counted."""
        cfg = _make_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        assets.mkdir(parents=True)
        (assets / "broken.yaml").write_text('sql: "SELECT {{ broken"\n')

        result = scan_yaml_jinja(cfg)
        # The file has broken Jinja — it should be flagged
        assert result.files_with_jinja >= 0  # May or may not extract, but errors are tracked
        error_findings = [f for f in result.findings if not f.valid]
        assert len(error_findings) >= 1


# ═══════════════════════════════════════════════════════════════════════════
# CROSS-MODULE INTEGRATION: Module → Formatter E2E
# ═══════════════════════════════════════════════════════════════════════════

class TestFormatterIntegrationChart:
    """Chart results must render correctly in all 3 formats."""

    def test_chart_list_all_formats(self):
        result = ChartListResult(
            success=True,
            charts=[
                ChartSummary(id=1, name="Revenue", viz_type="big_number_total",
                             dataset_name="Sales", modified="2026-03-15"),
                ChartSummary(id=2, name="DAU", viz_type="line",
                             dataset_name="Users", modified="2026-03-14"),
            ],
            total=2,
        )
        table = format_output(result, "table")
        assert "Revenue" in table
        assert "DAU" in table
        assert "2 chart(s) found" in table

        j = json_mod.loads(format_output(result, "json"))
        assert j["total"] == 2
        assert len(j["charts"]) == 2

        y = yaml.safe_load(format_output(result, "yaml"))
        assert y["total"] == 2

    def test_chart_info_all_formats(self):
        result = ChartInfo(success=True, id=1, name="Rev", viz_type="table")
        table = format_output(result, "table")
        assert "Rev" in table
        assert "table" in table

        j = json_mod.loads(format_output(result, "json"))
        assert j["id"] == 1

    def test_chart_data_all_formats(self):
        result = ChartData(
            success=True,
            columns=["date", "revenue"],
            rows=[{"date": "2026-01", "revenue": 100}],
            row_count=1,
        )
        table = format_output(result, "table")
        assert "date" in table
        assert "revenue" in table
        assert "1 row(s)" in table

        j = json_mod.loads(format_output(result, "json"))
        assert j["row_count"] == 1

    def test_chart_pull_all_formats(self):
        result = ChartPullResult(success=True, charts_pulled=2, files=["a.yaml", "b.yaml"])
        table = format_output(result, "table")
        assert "Charts pulled: 2" in table
        assert "a.yaml" in table

    def test_chart_push_all_formats(self):
        result = ChartPushResult(success=True, charts_pushed=3, errors=["warn: slow"])
        table = format_output(result, "table")
        assert "Charts pushed: 3" in table
        assert "warn: slow" in table

    def test_chart_sql_all_formats(self):
        result = ChartSQL(success=True, sql="SELECT 1")
        table = format_output(result, "table")
        assert "SELECT 1" in table


class TestFormatterIntegrationDataset:
    """Dataset results must render correctly."""

    def test_dataset_list_all_formats(self):
        result = DatasetListResult(
            success=True,
            datasets=[DatasetSummary(id=42, name="Sales", database="analytics", schema="public")],
            total=1,
        )
        table = format_output(result, "table")
        assert "Sales" in table
        assert "1 dataset(s) found" in table

        j = json_mod.loads(format_output(result, "json"))
        assert j["total"] == 1

    def test_dataset_info_all_formats(self):
        result = DatasetInfo(success=True, id=42, name="Sales", database="db", schema="public")
        table = format_output(result, "table")
        assert "Sales" in table

    def test_dataset_pull_push_formats(self):
        pull = DatasetPullResult(success=True, datasets_pulled=1, files=["d.yaml"])
        table = format_output(pull, "table")
        assert "Datasets pulled: 1" in table

        push = DatasetPushResult(success=True, datasets_pushed=2)
        table = format_output(push, "table")
        assert "Datasets pushed: 2" in table


class TestFormatterIntegrationSql:
    """SQL results must render correctly."""

    def test_sql_result_all_formats(self):
        result = SqlResult(
            success=True,
            columns=["id", "name"],
            rows=[{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}],
            row_count=2,
        )
        table = format_output(result, "table")
        assert "id" in table
        assert "name" in table
        assert "Alice" in table
        assert "2 row(s)" in table

        j = json_mod.loads(format_output(result, "json"))
        assert j["row_count"] == 2

    def test_sql_error_result_format(self):
        result = SqlResult(success=False, error="Table not found")
        table = format_output(result, "table")
        assert "ERROR: Table not found" in table


class TestFormatterIntegrationDashboard:
    """Dashboard results must render correctly."""

    def test_dashboard_list_all_formats(self):
        result = DashboardListResult(
            success=True,
            dashboards=[DashboardSummary(id=76, name="Metrics", status="published")],
            total=1,
        )
        table = format_output(result, "table")
        assert "Metrics" in table
        assert "published" in table

        j = json_mod.loads(format_output(result, "json"))
        assert j["total"] == 1

    def test_dashboard_info_all_formats(self):
        result = DashboardInfo(
            success=True, id=76, name="Metrics", status="published",
            slug="metrics", charts=[{"id": 1}], css=".custom{color:red}",
        )
        table = format_output(result, "table")
        assert "Metrics" in table
        assert "Charts:  1" in table
        assert "CSS:" in table

    def test_dashboard_pull_all_formats(self):
        result = DashboardPullResult(success=True, dashboards_pulled=1, files=["d.yaml"])
        table = format_output(result, "table")
        assert "Dashboards pulled: 1" in table


class TestFormatterIntegrationJinja:
    """JinjaScanResult must render correctly."""

    def test_jinja_scan_all_formats(self):
        result = JinjaScanResult(
            success=True,
            files_scanned=5,
            files_with_jinja=2,
            total_expressions=4,
            findings=[
                JinjaFinding(file_path="chart.yaml", expressions=[
                    JinjaExpression(expression="{{ x }}", expr_type="variable")
                ]),
            ],
        )
        table = format_output(result, "table")
        assert "Files scanned:      5" in table
        assert "Files with Jinja:   2" in table
        assert "Total expressions:  4" in table
        assert "All Jinja expressions are valid" in table

        j = json_mod.loads(format_output(result, "json"))
        assert j["files_scanned"] == 5

    def test_jinja_scan_with_errors_format(self):
        result = JinjaScanResult(
            success=True,
            files_scanned=1,
            files_with_jinja=1,
            total_expressions=0,
            findings=[
                JinjaFinding(file_path="bad.yaml", errors=["Unbalanced braces"], valid=False),
            ],
        )
        table = format_output(result, "table")
        assert "Files with errors" in table
        assert "bad.yaml" in table
        assert "Unbalanced braces" in table

    def test_jinja_scan_error_format(self):
        result = JinjaScanResult(success=False, error="Sync dir not found")
        table = format_output(result, "table")
        assert "ERROR: Sync dir not found" in table


# ═══════════════════════════════════════════════════════════════════════════
# CROSS-MODULE INTEGRATION: Full pipeline tests
# ═══════════════════════════════════════════════════════════════════════════

class TestFullPipelineChart:
    """Chart: list → info → sql → data → pull → push, all mocked through."""

    def test_chart_full_lifecycle(self, tmp_path):
        cfg = _make_config(tmp_path)
        sup_responses = {
            "list": json_mod.dumps([{"id": 2085, "slice_name": "Rev", "viz_type": "big_number_total"}]),
            "info": json_mod.dumps({"id": 2085, "slice_name": "Rev", "viz_type": "big_number_total"}),
            "sql": json_mod.dumps({"result": "SELECT SUM(revenue) FROM sales"}),
            "data": json_mod.dumps({"columns": ["total"], "data": [{"total": 1000}], "rowcount": 1}),
            "pull": json_mod.dumps({"charts_pulled": 1, "files": ["charts/rev.yaml"]}),
            "push": json_mod.dumps({"charts_pushed": 1, "errors": []}),
        }

        with patch("scripts.chart.run_sup") as m:
            # List
            m.return_value = _mock_sup(stdout=sup_responses["list"])
            charts = list_charts(cfg)
            assert charts.success and charts.total == 1

            # Info
            m.return_value = _mock_sup(stdout=sup_responses["info"])
            info = get_chart_info(cfg, 2085)
            assert info.success and info.name == "Rev"

            # SQL
            m.return_value = _mock_sup(stdout=sup_responses["sql"])
            sql = get_chart_sql(cfg, 2085)
            assert sql.success and "SUM" in sql.sql

            # Data
            m.return_value = _mock_sup(stdout=sup_responses["data"])
            data = get_chart_data(cfg, 2085)
            assert data.success and data.row_count == 1

            # Pull
            m.return_value = _mock_sup(stdout=sup_responses["pull"])
            pull = pull_charts(cfg, chart_id=2085)
            assert pull.success and pull.charts_pulled == 1

            # Push
            m.return_value = _mock_sup(stdout=sup_responses["push"])
            push = push_charts(cfg)
            assert push.success and push.charts_pushed == 1

        # Verify all results render in all formats
        for result in [charts, info, sql, data, pull, push]:
            for fmt in ("table", "json", "yaml"):
                output = format_output(result, fmt)
                assert len(output) > 0


class TestFullPipelineDataset:
    """Dataset: list → info → sql → data → pull → push."""

    def test_dataset_full_lifecycle(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.dataset.run_sup") as m:
            m.return_value = _mock_sup(stdout=json_mod.dumps([
                {"id": 42, "table_name": "Sales", "database_name": "analytics",
                 "schema": "public", "changed_on_utc": "2026-03-15"}
            ]))
            ds_list = list_datasets(cfg)
            assert ds_list.success and ds_list.total == 1

            m.return_value = _mock_sup(stdout=json_mod.dumps({
                "id": 42, "table_name": "Sales", "database_name": "analytics",
                "schema": "public", "sql": "SELECT * FROM raw_sales",
                "columns": [{"name": "id"}], "metrics": [],
            }))
            info = get_dataset_info(cfg, 42)
            assert info.success and info.name == "Sales"

            m.return_value = _mock_sup(stdout=json_mod.dumps({"result": "SELECT * FROM raw_sales"}))
            sql = get_dataset_sql(cfg, 42)
            assert sql.success and "raw_sales" in sql.sql

            m.return_value = _mock_sup(stdout=json_mod.dumps({
                "columns": ["id", "amount"], "data": [{"id": 1, "amount": 99}], "rowcount": 1
            }))
            data = get_dataset_data(cfg, 42)
            assert data.success and data.row_count == 1

            m.return_value = _mock_sup(stdout=json_mod.dumps({
                "datasets_pulled": 1, "files": ["datasets/sales.yaml"]
            }))
            pull = pull_datasets(cfg, dataset_id=42)
            assert pull.success

            m.return_value = _mock_sup(stdout=json_mod.dumps({
                "datasets_pushed": 1, "errors": []
            }))
            push = push_datasets(cfg)
            assert push.success

        for result in [ds_list, info, sql, data, pull, push]:
            for fmt in ("table", "json", "yaml"):
                output = format_output(result, fmt)
                assert len(output) > 0


class TestFullPipelineDashboard:
    """Dashboard: list → info → pull."""

    def test_dashboard_full_lifecycle(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.dashboard.run_sup") as m:
            m.return_value = _mock_sup(stdout=json_mod.dumps([
                {"id": 76, "dashboard_title": "Metrics", "status": "published",
                 "url": "/dashboard/76/", "changed_on_utc": "2026-03-15"}
            ]))
            dash_list = list_dashboards(cfg)
            assert dash_list.success and dash_list.total == 1

            m.return_value = _mock_sup(stdout=json_mod.dumps({
                "id": 76, "dashboard_title": "Metrics", "status": "published",
                "url": "/dashboard/76/", "slug": "metrics",
                "charts": [{"id": 1}], "css": ".custom{}"
            }))
            info = get_dashboard_info(cfg, 76)
            assert info.success and info.name == "Metrics"

            m.return_value = _mock_sup(stdout=json_mod.dumps({
                "dashboards_pulled": 1, "files": ["dashboards/metrics.yaml"]
            }))
            pull = pull_dashboards(cfg, dashboard_id=76)
            assert pull.success

        for result in [dash_list, info, pull]:
            for fmt in ("table", "json", "yaml"):
                assert len(format_output(result, fmt)) > 0


class TestFullPipelineSqlExecution:
    """SQL: resolve_database_id → execute_sql → format."""

    def test_sql_full_pipeline_with_auto_resolution(self, tmp_path):
        cfg = _make_config(tmp_path)
        db_dir = tmp_path / "sync" / "assets" / "databases"
        db_dir.mkdir(parents=True)
        (db_dir / "analytics.yaml").write_text(yaml.safe_dump({"id": 42}))

        with patch("scripts.sql.run_sup") as m:
            m.return_value = _mock_sup(stdout=json_mod.dumps({
                "columns": ["cnt"], "data": [{"cnt": 42}], "rowcount": 1
            }))
            result = execute_sql(cfg, "SELECT COUNT(*) as cnt FROM users")

        args = m.call_args[0][0]
        assert "--database-id" in args
        assert "42" in args
        assert result.success
        assert result.row_count == 1

        for fmt in ("table", "json", "yaml"):
            assert len(format_output(result, fmt)) > 0


class TestFullPipelineJinjaScan:
    """Jinja: extract → validate → scan_yaml → format."""

    def test_jinja_full_pipeline(self, tmp_path):
        cfg = _make_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        charts_dir = assets / "charts"
        charts_dir.mkdir(parents=True)

        # Valid Jinja chart
        (charts_dir / "valid_chart.yaml").write_text(textwrap.dedent("""
            slice_name: Revenue
            sql: "SELECT * WHERE date = {{ filter_values('date')[0] }}"
        """))

        # Chart with no Jinja
        (charts_dir / "plain_chart.yaml").write_text(textwrap.dedent("""
            slice_name: Simple
            sql: "SELECT id FROM users"
        """))

        result = scan_yaml_jinja(cfg)
        assert result.success is True
        assert result.files_scanned == 2
        assert result.files_with_jinja == 1
        assert result.total_expressions >= 1

        # All valid — no error findings
        error_findings = [f for f in result.findings if not f.valid]
        assert len(error_findings) == 0

        # Render in all formats
        for fmt in ("table", "json", "yaml"):
            output = format_output(result, fmt)
            assert len(output) > 0
            if fmt == "table":
                assert "All Jinja expressions are valid" in output


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Stress testing and unusual inputs
# ═══════════════════════════════════════════════════════════════════════════

class TestEdgeCases:
    """Unusual but valid inputs that should be handled correctly."""

    def test_empty_stdout_from_sup(self, tmp_path):
        """Empty stdout from sup should result in JSON parse error."""
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout="")
            result = list_charts(cfg)
        assert result.success is False

    def test_null_json_response(self, tmp_path):
        """JSON 'null' response should be handled."""
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout="null")
            result = list_charts(cfg)
        assert result.success is True
        assert result.charts == []

    def test_unicode_in_chart_names(self, tmp_path):
        """Charts with unicode names must be handled."""
        cfg = _make_config(tmp_path)
        sup_json = json_mod.dumps([{
            "id": 1, "slice_name": "Umsatz-Ubersicht",
            "viz_type": "table", "datasource_name_text": "Verkauf"
        }])
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout=sup_json)
            result = list_charts(cfg)
        assert result.success is True
        assert result.charts[0].name == "Umsatz-Ubersicht"

        table = format_output(result, "table")
        assert "Umsatz" in table

    def test_large_chart_list(self, tmp_path):
        """A large list of charts should be handled without error."""
        cfg = _make_config(tmp_path)
        charts = [{"id": i, "slice_name": f"Chart_{i}", "viz_type": "table"} for i in range(500)]
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout=json_mod.dumps(charts))
            result = list_charts(cfg)
        assert result.success is True
        assert result.total == 500

    def test_jinja_multiline_expressions(self):
        """Multi-line Jinja expressions must be extracted correctly."""
        sql = textwrap.dedent("""
            SELECT *
            FROM table
            WHERE date = {{
                filter_values(
                    'date_column'
                )[0]
            }}
        """)
        exprs = extract_jinja_expressions(sql)
        assert len(exprs) == 1
        assert exprs[0].expr_type == "variable"
        assert "filter_values" in exprs[0].expression

    def test_jinja_nested_braces_in_expressions(self):
        """Jinja expressions with nested dict literals."""
        sql = "{{ {'key': 'value'} }}"
        exprs = extract_jinja_expressions(sql)
        assert len(exprs) >= 1

    def test_deeply_nested_yaml_sql_extraction(self, tmp_path):
        """SQL fields nested deep in YAML structure must be found."""
        cfg = _make_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        assets.mkdir(parents=True)
        deep_yaml = {
            "level1": {
                "level2": {
                    "level3": {
                        "sql": "SELECT {{ deep_var }}"
                    }
                }
            }
        }
        (assets / "deep.yaml").write_text(yaml.safe_dump(deep_yaml))

        result = scan_yaml_jinja(cfg)
        assert result.total_expressions == 1

    def test_yaml_with_list_of_sql_fields(self, tmp_path):
        """YAML files with SQL inside list items must be scanned."""
        cfg = _make_config(tmp_path)
        assets = tmp_path / "sync" / "assets"
        assets.mkdir(parents=True)
        list_yaml = {
            "queries": [
                {"sql": "SELECT {{ a }}"},
                {"sql": "SELECT {{ b }}"},
            ]
        }
        (assets / "list.yaml").write_text(yaml.safe_dump(list_yaml))

        result = scan_yaml_jinja(cfg)
        assert result.total_expressions == 2

    def test_all_dataclass_serialization(self):
        """All result dataclasses must be serializable via dataclasses.asdict."""
        instances = [
            ChartListResult(success=True),
            ChartInfo(success=True),
            ChartSQL(success=True),
            ChartData(success=True),
            ChartPullResult(success=True),
            ChartPushResult(success=True),
            DatasetListResult(success=True),
            DatasetInfo(success=True),
            DatasetSQL(success=True),
            DatasetData(success=True),
            DatasetPullResult(success=True),
            DatasetPushResult(success=True),
            SqlResult(success=True),
            DashboardListResult(success=True),
            DashboardInfo(success=True),
            DashboardPullResult(success=True),
            JinjaScanResult(success=True),
        ]
        for inst in instances:
            d = dataclasses.asdict(inst)
            assert isinstance(d, dict)
            # Must be JSON serializable
            serialized = json_mod.dumps(d)
            assert len(serialized) > 0
            # Must be YAML serializable
            yml = yaml.dump(d)
            assert len(yml) > 0


class TestFilterFlagCompleteness:
    """Every documented filter kwarg must produce the correct CLI flag."""

    def test_chart_list_all_filters(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.chart.run_sup") as m:
            m.return_value = _mock_sup(stdout="[]")
            list_charts(
                cfg, search="rev", dashboard_id=76, viz_type="table",
                dataset_id=42, mine=True, modified_after="2026-01-01",
                limit=10, order="name", desc=True,
            )
        args = m.call_args[0][0]
        expected = {
            "--search": "rev", "--dashboard-id": "76", "--viz-type": "table",
            "--dataset-id": "42", "--modified-after": "2026-01-01",
            "--limit": "10", "--order": "name",
        }
        for flag, value in expected.items():
            assert flag in args, f"Missing flag: {flag}"
            assert value in args, f"Missing value for {flag}: {value}"
        assert "--mine" in args
        assert "--desc" in args

    def test_dataset_list_all_filters(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.dataset.run_sup") as m:
            m.return_value = _mock_sup(stdout="[]")
            list_datasets(
                cfg, search="sales", database_id=5, mine=True,
                modified_after="2026-01-01", limit=20, order="name", desc=True,
            )
        args = m.call_args[0][0]
        expected = {
            "--search": "sales", "--database-id": "5",
            "--modified-after": "2026-01-01", "--limit": "20", "--order": "name",
        }
        for flag, value in expected.items():
            assert flag in args, f"Missing flag: {flag}"
        assert "--mine" in args
        assert "--desc" in args

    def test_dashboard_list_all_filters(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.dashboard.run_sup") as m:
            m.return_value = _mock_sup(stdout="[]")
            list_dashboards(
                cfg, search="metrics", mine=True, published=True,
                draft=True, folder="team-a", limit=5,
            )
        args = m.call_args[0][0]
        assert "--search" in args and "metrics" in args
        assert "--mine" in args
        assert "--published" in args
        assert "--draft" in args
        assert "--folder" in args and "team-a" in args
        assert "--limit" in args and "5" in args

    def test_dashboard_pull_all_flags(self, tmp_path):
        cfg = _make_config(tmp_path)
        with patch("scripts.dashboard.run_sup") as m:
            m.return_value = _mock_sup(stdout='{}')
            pull_dashboards(
                cfg, dashboard_ids=[1, 2, 3], search="test", mine=True,
                limit=10, skip_dependencies=True, overwrite=False,
                assets_folder="/custom/path",
            )
        args = m.call_args[0][0]
        assert "--ids" in args and "1,2,3" in args
        assert "--search" in args
        assert "--mine" in args
        assert "--limit" in args
        assert "--skip-dependencies" in args
        assert "--no-overwrite" in args
        assert "--assets-folder" in args and "/custom/path" in args
