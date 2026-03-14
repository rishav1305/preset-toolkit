import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import yaml
import scripts.sync as sync_mod
from scripts.sync import _run_sup, SyncResult, SupNotFoundError, CLINotFoundError, pull, validate, push
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
            mock_run.return_value = MagicMock(returncode=0)
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
            mock_run.return_value = MagicMock(returncode=0)
            result = push(cfg, dry_run=True)
            assert result.success is True
            assert any("dry-run" in s for s in result.steps_completed)
