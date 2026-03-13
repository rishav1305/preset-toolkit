"""Tests for dependency checker module."""
import subprocess
from unittest.mock import patch, MagicMock
from scripts.deps import ensure_package, ensure_sup_cli, _is_importable, _pip_name


def test_pip_name_mapping():
    assert _pip_name("yaml") == "PyYAML"
    assert _pip_name("PIL") == "Pillow"
    assert _pip_name("httpx") == "httpx"


def test_is_importable_stdlib():
    assert _is_importable("os") is True
    assert _is_importable("nonexistent_pkg_xyz") is False


def test_ensure_package_already_installed():
    assert ensure_package("os") is True


def test_ensure_package_installs_missing():
    with patch("scripts.deps._is_importable", side_effect=[False, True]):
        with patch("scripts.deps._pip_install", return_value=True):
            assert ensure_package("fake_pkg") is True


def test_ensure_sup_cli_already_installed():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert ensure_sup_cli() is True


def test_ensure_sup_cli_installs_when_missing():
    fail = MagicMock(returncode=1)
    success = MagicMock(returncode=0)
    with patch("subprocess.run", side_effect=[fail, success]):
        with patch("scripts.deps._pip_install", return_value=True):
            assert ensure_sup_cli() is True


def test_pip_install_timeout_returns_false():
    """_pip_install should return False on subprocess timeout, not crash."""
    from scripts.deps import _pip_install
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pip", timeout=120)):
        assert _pip_install("fake_pkg") is False


def test_ensure_sup_cli_timeout_returns_false():
    """ensure_sup_cli should return False on subprocess timeout."""
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="sup", timeout=30)):
        assert ensure_sup_cli() is False
