import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import yaml
import scripts.sync as sync_mod
from scripts.sync import _run_cli, _run_sup, SyncResult, CLINotFoundError, SupNotFoundError, pull, validate, push
from scripts.config import ToolkitConfig


@pytest.fixture(autouse=True)
def _reset_cli_cache():
    """Reset cached CLI path between tests."""
    sync_mod._cli_path = None
    yield
    sync_mod._cli_path = None


def test_run_cli_success():
    with patch("scripts.sync._ensure_cli", return_value="/usr/bin/preset-cli"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            result = _run_cli(["superset", "export-assets", "sync"])
            assert result.returncode == 0
            mock_run.assert_called_once()


def test_run_cli_retries_on_failure():
    with patch("scripts.sync._ensure_cli", return_value="/usr/bin/preset-cli"):
        with patch("subprocess.run") as mock_run:
            with patch("scripts.sync.time.sleep"):
                fail = MagicMock(returncode=1, stdout="", stderr="auth error")
                success = MagicMock(returncode=0, stdout="ok", stderr="")
                mock_run.side_effect = [fail, success]
                result = _run_cli(["superset", "export-assets", "sync"], retries=3)
                assert result.returncode == 0
                assert mock_run.call_count == 2


def test_run_cli_exhausts_retries():
    with patch("scripts.sync._ensure_cli", return_value="/usr/bin/preset-cli"):
        with patch("subprocess.run") as mock_run:
            with patch("scripts.sync.time.sleep"):
                fail = MagicMock(returncode=1, stdout="", stderr="error")
                mock_run.return_value = fail
                result = _run_cli(["superset", "export-assets", "sync"], retries=2)
                assert result.returncode == 1
                assert mock_run.call_count == 2


def test_run_cli_not_found():
    """When preset-cli can't be found, _run_cli raises CLINotFoundError."""
    with patch("scripts.sync._ensure_cli", side_effect=CLINotFoundError("preset-cli not found")):
        with pytest.raises(CLINotFoundError, match="preset-cli not found"):
            _run_cli(["superset", "export-assets", "sync"])


def test_backward_compat_aliases():
    """Old names _run_sup and SupNotFoundError still work."""
    assert _run_sup is _run_cli
    assert SupNotFoundError is CLINotFoundError


def test_find_cli_prefers_venv(tmp_path):
    """_find_cli should prefer .venv/bin/preset-cli over system PATH."""
    from scripts.sync import _find_cli
    import os
    old_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        venv_bin = tmp_path / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        cli_bin = venv_bin / "preset-cli"
        cli_bin.write_text("#!/bin/sh\necho ok")
        cli_bin.chmod(0o755)
        result = _find_cli()
        assert ".venv/bin/preset-cli" in result
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
    sync_dir = tmp_path / "sync" / "datasets"
    sync_dir.mkdir(parents=True)
    with patch("scripts.sync._ensure_cli", return_value="/usr/bin/preset-cli"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = pull(cfg)
            assert result.success is True


def test_pull_no_sync_dir_no_crash(tmp_path):
    """Pull should succeed even when sync dir doesn't exist yet."""
    cfg = _make_config(tmp_path)
    (tmp_path / "sync").mkdir(parents=True)
    with patch("scripts.sync._ensure_cli", return_value="/usr/bin/preset-cli"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = pull(cfg)
            assert result.success is True


def test_validate_success(tmp_path):
    """validate() should succeed when markers pass."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("test_marker\n")
    ds_dir = tmp_path / "sync" / "datasets" / "db"
    ds_dir.mkdir(parents=True)
    import yaml as _yaml
    with open(ds_dir / "ds.yaml", "w") as f:
        _yaml.safe_dump({"sql": "SELECT test_marker FROM t"}, f)
    result = validate(cfg)
    assert result.success is True
    assert "markers: all present" in result.steps_completed


def test_push_dry_run(tmp_path):
    """push(dry_run=True) should validate but not actually push."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("")
    (tmp_path / "sync").mkdir(parents=True)
    result = push(cfg, dry_run=True)
    assert result.success is True
    assert any("dry-run" in s for s in result.steps_completed)
