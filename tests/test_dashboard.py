"""Tests for dashboard operations module."""
import json as json_mod
from unittest.mock import patch, MagicMock

import pytest
import yaml

from scripts.dashboard import (
    DashboardSummary,
    DashboardListResult,
    DashboardInfo,
    DashboardPullResult,
    list_dashboards,
    get_dashboard_info,
    pull_dashboards,
)
from scripts.config import ToolkitConfig


def _make_dashboard_config(tmp_path):
    """Helper to create a minimal ToolkitConfig for dashboard tests."""
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

def test_dashboard_summary_creation():
    """DashboardSummary holds basic dashboard metadata."""
    s = DashboardSummary(id=76, name="Sales Overview", status="published")
    assert s.id == 76
    assert s.name == "Sales Overview"
    assert s.status == "published"
    assert s.url == ""
    assert s.modified == ""


def test_dashboard_summary_with_all_fields():
    """DashboardSummary accepts optional url and modified."""
    s = DashboardSummary(
        id=76, name="Sales Overview", status="published",
        url="https://app.preset.io/superset/dashboard/76/",
        modified="2026-03-15T12:00:00Z",
    )
    assert s.url == "https://app.preset.io/superset/dashboard/76/"
    assert s.modified == "2026-03-15T12:00:00Z"


def test_dashboard_list_result():
    """DashboardListResult wraps a list of DashboardSummary."""
    result = DashboardListResult(
        success=True,
        dashboards=[DashboardSummary(id=1, name="A", status="published")],
        total=1,
    )
    assert result.success is True
    assert len(result.dashboards) == 1
    assert result.total == 1
    assert result.error == ""


def test_dashboard_info():
    """DashboardInfo holds detailed dashboard metadata."""
    info = DashboardInfo(
        success=True, id=76, name="Sales Overview", status="published",
        url="https://app.preset.io/superset/dashboard/76/",
        slug="sales-overview",
        charts=[{"id": 101, "slice_name": "Revenue"}],
        css=".dashboard { color: red; }",
        raw={"extra": "data"},
    )
    assert info.slug == "sales-overview"
    assert len(info.charts) == 1
    assert info.css == ".dashboard { color: red; }"
    assert info.raw == {"extra": "data"}


def test_dashboard_pull_result():
    """DashboardPullResult holds pull operation results."""
    result = DashboardPullResult(
        success=True, dashboards_pulled=2,
        files=["dashboards/sales.yaml", "dashboards/ops.yaml"],
    )
    assert result.dashboards_pulled == 2
    assert len(result.files) == 2


# ── list_dashboards ────────────────────────────────────────────────

def test_list_dashboards_success(tmp_path):
    """list_dashboards parses JSON output into DashboardListResult."""
    cfg = _make_dashboard_config(tmp_path)
    sup_json = json_mod.dumps([
        {"id": 76, "dashboard_title": "Sales Overview", "status": "published",
         "url": "https://app.preset.io/superset/dashboard/76/",
         "changed_on_utc": "2026-03-15T00:00:00Z"},
        {"id": 77, "dashboard_title": "Ops Dashboard", "status": "draft",
         "url": "https://app.preset.io/superset/dashboard/77/",
         "changed_on_utc": "2026-03-14T00:00:00Z"},
    ])
    with patch("scripts.dashboard.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = list_dashboards(cfg)

    assert result.success is True
    assert len(result.dashboards) == 2
    assert result.dashboards[0].id == 76
    assert result.dashboards[0].name == "Sales Overview"
    assert result.dashboards[0].status == "published"
    assert result.dashboards[0].url == "https://app.preset.io/superset/dashboard/76/"
    assert result.dashboards[1].name == "Ops Dashboard"
    assert result.total == 2


def test_list_dashboards_with_filters(tmp_path):
    """list_dashboards passes filter kwargs as CLI flags."""
    cfg = _make_dashboard_config(tmp_path)
    with patch("scripts.dashboard.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        list_dashboards(
            cfg, search="sales", mine=True, published=True,
            draft=True, folder="Marketing", limit=10,
        )

    args = mock_sup.call_args[0][0]
    assert "dashboard" in args
    assert "list" in args
    assert "--json" in args
    assert "--search" in args
    assert "sales" in args
    assert "--mine" in args
    assert "--published" in args
    assert "--draft" in args
    assert "--folder" in args
    assert "Marketing" in args
    assert "--limit" in args
    assert "10" in args


def test_list_dashboards_empty(tmp_path):
    """list_dashboards handles empty result."""
    cfg = _make_dashboard_config(tmp_path)
    with patch("scripts.dashboard.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout="[]", stderr="")
        result = list_dashboards(cfg)

    assert result.success is True
    assert result.dashboards == []
    assert result.total == 0


def test_list_dashboards_sup_failure(tmp_path):
    """list_dashboards returns error on sup failure."""
    cfg = _make_dashboard_config(tmp_path)
    with patch("scripts.dashboard.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="auth error")
        result = list_dashboards(cfg)

    assert result.success is False
    assert "auth error" in result.error


def test_list_dashboards_malformed_json(tmp_path):
    """list_dashboards handles malformed JSON gracefully."""
    cfg = _make_dashboard_config(tmp_path)
    with patch("scripts.dashboard.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
        result = list_dashboards(cfg)

    assert result.success is False
    assert "parse" in result.error.lower() or "json" in result.error.lower()


# ── get_dashboard_info ─────────────────────────────────────────────

def test_get_dashboard_info_success(tmp_path):
    """get_dashboard_info parses JSON dict into DashboardInfo fields + raw dict."""
    cfg = _make_dashboard_config(tmp_path)
    sup_json = json_mod.dumps({
        "id": 76,
        "dashboard_title": "Sales Overview",
        "status": "published",
        "url": "https://app.preset.io/superset/dashboard/76/",
        "slug": "sales-overview",
        "charts": [{"id": 101, "slice_name": "Revenue"}],
        "css": ".dashboard { color: red; }",
        "extra_field": "should appear in raw",
    })
    with patch("scripts.dashboard.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = get_dashboard_info(cfg, 76)

    assert result.success is True
    assert result.id == 76
    assert result.name == "Sales Overview"
    assert result.status == "published"
    assert result.url == "https://app.preset.io/superset/dashboard/76/"
    assert result.slug == "sales-overview"
    assert len(result.charts) == 1
    assert result.charts[0]["slice_name"] == "Revenue"
    assert result.css == ".dashboard { color: red; }"
    assert result.raw["extra_field"] == "should appear in raw"
    assert result.raw["id"] == 76

    args = mock_sup.call_args[0][0]
    assert args == ["dashboard", "info", "76", "--json"]


def test_get_dashboard_info_failure(tmp_path):
    """get_dashboard_info returns error on sup failure."""
    cfg = _make_dashboard_config(tmp_path)
    with patch("scripts.dashboard.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="dashboard not found")
        result = get_dashboard_info(cfg, 9999)

    assert result.success is False
    assert "dashboard not found" in result.error


# ── pull_dashboards ────────────────────────────────────────────────

def test_pull_dashboards_single(tmp_path):
    """pull_dashboards with a single dashboard_id passes --id flag."""
    cfg = _make_dashboard_config(tmp_path)
    sup_json = json_mod.dumps({
        "dashboards_pulled": 1,
        "files": ["dashboards/sales.yaml"],
    })
    with patch("scripts.dashboard.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = pull_dashboards(cfg, dashboard_id=76)

    assert result.success is True
    assert result.dashboards_pulled == 1
    assert result.files == ["dashboards/sales.yaml"]

    args = mock_sup.call_args[0][0]
    assert "--id" in args
    assert "76" in args


def test_pull_dashboards_multiple(tmp_path):
    """pull_dashboards with dashboard_ids passes --ids flag."""
    cfg = _make_dashboard_config(tmp_path)
    sup_json = json_mod.dumps({
        "dashboards_pulled": 2,
        "files": ["dashboards/a.yaml", "dashboards/b.yaml"],
    })
    with patch("scripts.dashboard.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        result = pull_dashboards(cfg, dashboard_ids=[76, 77])

    assert result.success is True
    assert result.dashboards_pulled == 2
    assert len(result.files) == 2

    args = mock_sup.call_args[0][0]
    assert "--ids" in args
    assert "76,77" in args


def test_pull_dashboards_mutual_exclusion(tmp_path):
    """pull_dashboards raises ValueError if both dashboard_id and dashboard_ids provided."""
    cfg = _make_dashboard_config(tmp_path)
    with pytest.raises(ValueError, match="mutually exclusive"):
        pull_dashboards(cfg, dashboard_id=76, dashboard_ids=[76, 77])


def test_pull_dashboards_with_filters(tmp_path):
    """pull_dashboards passes all filter flags correctly."""
    cfg = _make_dashboard_config(tmp_path)
    sup_json = json_mod.dumps({"dashboards_pulled": 0, "files": []})
    with patch("scripts.dashboard.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=0, stdout=sup_json, stderr="")
        pull_dashboards(
            cfg,
            search="sales",
            mine=True,
            limit=5,
            skip_dependencies=True,
            overwrite=False,
            assets_folder="/tmp/assets",
        )

    args = mock_sup.call_args[0][0]
    assert "--search" in args
    assert "sales" in args
    assert "--mine" in args
    assert "--limit" in args
    assert "5" in args
    assert "--skip-dependencies" in args
    assert "--no-overwrite" in args
    assert "--assets-folder" in args
    assert "/tmp/assets" in args


def test_pull_dashboards_failure(tmp_path):
    """pull_dashboards returns error on sup failure."""
    cfg = _make_dashboard_config(tmp_path)
    with patch("scripts.dashboard.run_sup") as mock_sup:
        mock_sup.return_value = MagicMock(returncode=1, stdout="", stderr="pull failed")
        result = pull_dashboards(cfg)

    assert result.success is False
    assert "pull failed" in result.error
