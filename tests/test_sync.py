import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import yaml
import scripts.sync as sync_mod
from scripts.sync import _run_sup, SyncResult, SupNotFoundError, CLINotFoundError, pull, validate, push, ChangeAction, AssetChange, DryRunResult, _parse_dry_run_output
from scripts.config import ToolkitConfig


@pytest.fixture(autouse=True)
def _reset_sup_cache():
    """Reset cached sup path between tests."""
    sync_mod._sup_path = None
    yield
    sync_mod._sup_path = None


def test_run_sup_success():
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            result = _run_sup(["sync", "run", "sync", "--pull-only", "--force"])
            assert result.returncode == 0
            mock_run.assert_called_once()


def test_run_sup_retries_on_failure():
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            with patch("scripts.sync.time.sleep"):
                fail = MagicMock(returncode=1, stdout="", stderr="auth error")
                success = MagicMock(returncode=0, stdout="ok", stderr="")
                mock_run.side_effect = [fail, success]
                result = _run_sup(["sync", "run", "sync", "--pull-only", "--force"], retries=3)
                assert result.returncode == 0
                assert mock_run.call_count == 2


def test_run_sup_exhausts_retries():
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            with patch("scripts.sync.time.sleep"):
                fail = MagicMock(returncode=1, stdout="", stderr="error")
                mock_run.return_value = fail
                result = _run_sup(["sync", "run", "sync", "--pull-only", "--force"], retries=2)
                assert result.returncode == 1
                assert mock_run.call_count == 2


def test_run_sup_not_found():
    """When sup can't be found, _run_sup raises SupNotFoundError."""
    with patch("scripts.sync._ensure_sup", side_effect=SupNotFoundError("sup CLI not found")):
        with pytest.raises(SupNotFoundError, match="sup CLI not found"):
            _run_sup(["sync", "run", "sync", "--pull-only", "--force"])


def test_backward_compat_aliases():
    """Old name CLINotFoundError still works."""
    assert CLINotFoundError is SupNotFoundError


def test_find_sup_prefers_venv(tmp_path):
    """_find_sup should prefer .venv/bin/sup over system PATH."""
    from scripts.sync import _find_sup
    import os
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        sup_bin = venv_bin / "sup"
        sup_bin.write_text("#!/bin/sh\necho ok")
        sup_bin.chmod(0o755)
        result = _find_sup()
        assert ".venv/bin/sup" in result
    finally:
        os.chdir(old_cwd)


def _make_config(tmp_path):
    config_dir = tmp_path / ".preset-toolkit"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(yaml.safe_dump({
        "version": 1,
        "workspace": {"url": "https://test.preset.io", "id": "test123"},
        "dashboard": {"id": 1, "name": "Test", "sync_folder": str(tmp_path / "sync")},
        "validation": {
            "markers_file": str(config_dir / "markers.txt"),
            "fingerprint_file": str(config_dir / ".last-push-fingerprint"),
        },
    }))
    return ToolkitConfig.load(config_path)


def test_pull_empty_datasets_no_crash(tmp_path):
    """Pull should succeed when datasets directory is empty."""
    cfg = _make_config(tmp_path)
    sync_dir = tmp_path / "sync" / "assets" / "datasets"
    sync_dir.mkdir(parents=True)
    (tmp_path / "sync" / "assets" / "charts").mkdir(parents=True)
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = pull(cfg)
            assert result.success is True


def test_pull_no_sync_dir_no_crash(tmp_path):
    """Pull should succeed even when sync dir doesn't exist yet."""
    cfg = _make_config(tmp_path)
    (tmp_path / "sync").mkdir(parents=True)
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = pull(cfg)
            assert result.success is True


def test_validate_success(tmp_path):
    """validate() should succeed when markers pass."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("test_marker\n")
    ds_dir = tmp_path / "sync" / "assets" / "datasets" / "db"
    ds_dir.mkdir(parents=True)
    import yaml as _yaml
    with open(ds_dir / "ds.yaml", "w") as f:
        _yaml.safe_dump({"sql": "SELECT test_marker FROM t"}, f)
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = validate(cfg)
            assert result.success is True
            assert "markers: all present" in result.steps_completed


def test_push_dry_run(tmp_path):
    """push(dry_run=True) should validate but not actually push."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("")
    (tmp_path / "sync").mkdir(parents=True)
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = push(cfg, dry_run=True)
            assert result.success is True
            assert any("dry-run" in s for s in result.steps_completed)


# ---------------------------------------------------------------------------
# Task 1: ChangeAction enum and AssetChange dataclass
# ---------------------------------------------------------------------------

def test_change_action_values():
    """ChangeAction enum has expected string values."""
    assert ChangeAction.CREATE == "create"
    assert ChangeAction.UPDATE == "update"
    assert ChangeAction.DELETE == "delete"
    assert ChangeAction.NO_CHANGE == "no_change"


def test_change_action_is_string():
    """ChangeAction values work as plain strings."""
    assert isinstance(ChangeAction.CREATE, str)
    assert f"Action: {ChangeAction.CREATE}" == "Action: create"


def test_asset_change_creation():
    """AssetChange dataclass holds structured change info."""
    change = AssetChange(
        asset_type="chart",
        name="Revenue Chart",
        action=ChangeAction.CREATE,
    )
    assert change.asset_type == "chart"
    assert change.name == "Revenue Chart"
    assert change.action == ChangeAction.CREATE
    assert change.details == ""


def test_asset_change_with_details():
    """AssetChange accepts optional details."""
    change = AssetChange(
        asset_type="dataset",
        name="Main_Dataset",
        action=ChangeAction.UPDATE,
        details="SQL query modified",
    )
    assert change.details == "SQL query modified"


# ---------------------------------------------------------------------------
# Task 2: DryRunResult dataclass
# ---------------------------------------------------------------------------

def test_dry_run_result_creation():
    """DryRunResult holds structured validate output."""
    result = DryRunResult(
        success=True,
        changes=[],
        validation_passed=True,
        markers_passed=True,
        raw_output="some sup output",
    )
    assert result.success is True
    assert result.changes == []
    assert result.validation_passed is True
    assert result.markers_passed is True
    assert result.raw_output == "some sup output"
    assert result.steps_completed == []
    assert result.warnings == []
    assert result.error == ""


def test_dry_run_result_with_changes():
    """DryRunResult holds a list of AssetChange objects."""
    changes = [
        AssetChange("chart", "Revenue", ChangeAction.UPDATE),
        AssetChange("dataset", "Main", ChangeAction.NO_CHANGE),
    ]
    result = DryRunResult(
        success=True,
        changes=changes,
        validation_passed=True,
        markers_passed=True,
        raw_output="",
    )
    assert len(result.changes) == 2
    assert result.changes[0].action == ChangeAction.UPDATE


def test_dry_run_result_has_steps_completed():
    """DryRunResult preserves steps_completed for backward compat with SyncResult."""
    result = DryRunResult(
        success=True,
        changes=[],
        validation_passed=True,
        markers_passed=True,
        raw_output="",
        steps_completed=["validate", "markers: all present", "dry-run"],
    )
    assert "validate" in result.steps_completed
    assert len(result.steps_completed) == 3


def test_dry_run_result_partial_failure():
    """DryRunResult captures partial failure state."""
    result = DryRunResult(
        success=False,
        changes=[],
        validation_passed=True,
        markers_passed=False,
        raw_output="",
        error="Missing markers in ds.yaml: revenue_total",
    )
    assert result.success is False
    assert result.validation_passed is True
    assert result.markers_passed is False
    assert "Missing markers" in result.error


# ---------------------------------------------------------------------------
# Task 3: _parse_dry_run_output parser
# ---------------------------------------------------------------------------

def test_parse_creating_chart():
    """Parser extracts 'Creating chart' lines."""
    output = 'Creating chart "Revenue Overview"'
    changes = _parse_dry_run_output(output)
    assert len(changes) == 1
    assert changes[0].asset_type == "chart"
    assert changes[0].name == "Revenue Overview"
    assert changes[0].action == ChangeAction.CREATE


def test_parse_updating_dataset():
    """Parser extracts 'Updating dataset' lines."""
    output = 'Updating dataset "Main_Dataset"'
    changes = _parse_dry_run_output(output)
    assert len(changes) == 1
    assert changes[0].asset_type == "dataset"
    assert changes[0].name == "Main_Dataset"
    assert changes[0].action == ChangeAction.UPDATE


def test_parse_deleting_dashboard():
    """Parser extracts 'Deleting dashboard' lines."""
    output = 'Deleting dashboard "Old Dashboard"'
    changes = _parse_dry_run_output(output)
    assert len(changes) == 1
    assert changes[0].asset_type == "dashboard"
    assert changes[0].action == ChangeAction.DELETE


def test_parse_mixed_output():
    """Parser handles mixed create/update/delete in one output."""
    output = """sup sync v0.5.0
Validating sync folder...
Creating chart "New Chart"
Updating dataset "Main_Dataset"
Updating chart "Revenue Overview"
Deleting chart "Old Chart"
Done. 4 changes detected."""
    changes = _parse_dry_run_output(output)
    assert len(changes) == 4
    actions = [c.action for c in changes]
    assert actions.count(ChangeAction.CREATE) == 1
    assert actions.count(ChangeAction.UPDATE) == 2
    assert actions.count(ChangeAction.DELETE) == 1


def test_parse_empty_output():
    """Parser returns empty list for empty output."""
    assert _parse_dry_run_output("") == []


def test_parse_no_matching_lines():
    """Parser returns empty list when no lines match the pattern."""
    output = """sup sync v0.5.0
Validating sync folder...
All assets up to date.
Done."""
    assert _parse_dry_run_output(output) == []


def test_parse_case_insensitive():
    """Parser handles case variations in sup output."""
    output = 'creating chart "Test"'
    changes = _parse_dry_run_output(output)
    assert len(changes) == 1
    assert changes[0].action == ChangeAction.CREATE


# ---------------------------------------------------------------------------
# Task 4: validate() returns DryRunResult
# ---------------------------------------------------------------------------

def test_validate_returns_dry_run_result(tmp_path):
    """validate() now returns DryRunResult instead of SyncResult."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("test_marker\n")
    ds_dir = tmp_path / "sync" / "assets" / "datasets" / "db"
    ds_dir.mkdir(parents=True)
    import yaml as _yaml
    with open(ds_dir / "ds.yaml", "w") as f:
        _yaml.safe_dump({"sql": "SELECT test_marker FROM t"}, f)

    dry_run_output = 'Updating chart "Revenue Overview"\nUpdating dataset "Main_Dataset"'
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            validate_result = MagicMock(returncode=0, stdout="", stderr="")
            dry_run_result_mock = MagicMock(returncode=0, stdout=dry_run_output, stderr="")
            mock_run.side_effect = [validate_result, dry_run_result_mock]
            result = validate(cfg)

    assert isinstance(result, DryRunResult)
    assert result.success is True
    assert result.validation_passed is True
    assert result.markers_passed is True
    assert len(result.changes) == 2
    assert result.raw_output == dry_run_output
    assert "validate" in result.steps_completed
    assert "dry-run" in result.steps_completed


def test_validate_sup_validate_fails(tmp_path):
    """validate() returns validation_passed=False when sup validate fails."""
    cfg = _make_config(tmp_path)
    (tmp_path / "sync").mkdir(parents=True)
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="YAML error")
            result = validate(cfg)

    assert isinstance(result, DryRunResult)
    assert result.success is False
    assert result.validation_passed is False
    assert result.markers_passed is False
    assert result.changes == []


def test_validate_markers_fail(tmp_path):
    """validate() returns markers_passed=False when markers are missing."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("required_marker\n")
    ds_dir = tmp_path / "sync" / "assets" / "datasets" / "db"
    ds_dir.mkdir(parents=True)
    import yaml as _yaml
    with open(ds_dir / "ds.yaml", "w") as f:
        _yaml.safe_dump({"sql": "SELECT something_else FROM t"}, f)

    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = validate(cfg)

    assert isinstance(result, DryRunResult)
    assert result.success is False
    assert result.validation_passed is True
    assert result.markers_passed is False
    assert "Missing markers" in result.error


def test_validate_dry_run_command_fails(tmp_path):
    """validate() handles dry-run command failure after validation and markers pass."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("")
    (tmp_path / "sync").mkdir(parents=True)
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            with patch("scripts.sync.time.sleep"):
                validate_ok = MagicMock(returncode=0, stdout="", stderr="")
                dry_run_fail = MagicMock(returncode=1, stdout="", stderr="dry-run error")
                # _run_sup retries up to 3 times; provide enough fail mocks
                mock_run.side_effect = [validate_ok, dry_run_fail, dry_run_fail, dry_run_fail]
                result = validate(cfg)

    assert isinstance(result, DryRunResult)
    assert result.success is False
    assert result.validation_passed is True
    assert result.markers_passed is True
    assert "Dry-run failed" in result.error


# ---------------------------------------------------------------------------
# Task 5: push() backward compatibility with DryRunResult from validate()
# ---------------------------------------------------------------------------

def test_push_extends_steps_from_dry_run_result(tmp_path):
    """push() correctly extends steps_completed from DryRunResult returned by validate()."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("")
    sync_dir = tmp_path / "sync" / "assets"
    sync_dir.mkdir(parents=True)
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = push(cfg, dry_run=True)
            assert result.success is True
            assert "validate" in result.steps_completed
            assert any("dry-run" in s for s in result.steps_completed)
