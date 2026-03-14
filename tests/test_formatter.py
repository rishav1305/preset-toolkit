"""Tests for output formatter module."""
import json

import pytest
import yaml

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
