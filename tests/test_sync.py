import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from scripts.sync import _run_sup, SyncResult


def test_run_sup_success():
    with patch("scripts.sync._ensure_sup", return_value=True):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
            result = _run_sup(["sync", "validate", "test-sync"])
            assert result.returncode == 0
            mock_run.assert_called_once()


def test_run_sup_retries_on_failure():
    with patch("scripts.sync._ensure_sup", return_value=True):
        with patch("subprocess.run") as mock_run:
            fail = MagicMock(returncode=1, stdout="", stderr="JWT error")
            success = MagicMock(returncode=0, stdout="ok", stderr="")
            mock_run.side_effect = [fail, success]
            result = _run_sup(["sync", "validate", "test"], retries=3)
            assert result.returncode == 0
            assert mock_run.call_count == 2


def test_run_sup_exhausts_retries():
    with patch("scripts.sync._ensure_sup", return_value=True):
        with patch("subprocess.run") as mock_run:
            fail = MagicMock(returncode=1, stdout="", stderr="error")
            mock_run.return_value = fail
            result = _run_sup(["sync", "validate", "test"], retries=2)
            assert result.returncode == 1
            assert mock_run.call_count == 2


def test_run_sup_auto_install_failure():
    """When sup can't be installed, _run_sup returns a failure result."""
    with patch("scripts.sync._ensure_sup", return_value=False):
        result = _run_sup(["sync", "validate", "test"])
        assert result.returncode == 1
        assert "not installed" in result.stderr
