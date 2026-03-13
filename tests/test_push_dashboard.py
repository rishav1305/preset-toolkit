import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import yaml
from scripts.push_dashboard import compare_css, CssComparison, _get_credentials, PushResult, push_css_and_position
from scripts.config import ToolkitConfig


def test_compare_css_identical():
    result = compare_css("body { color: red; }", "body { color: red; }")
    assert result.changed is False


def test_compare_css_different():
    result = compare_css("body { color: red; }", "body { color: blue; }")
    assert result.changed is True
    assert result.local_length > 0
    assert result.remote_length > 0


def test_compare_css_length_warning():
    long_css = "x" * 31000
    result = compare_css(long_css, "short")
    assert result.length_warning is True


def test_compare_css_no_warning():
    short_css = "body { color: red; }"
    result = compare_css(short_css, "body { color: blue; }")
    assert result.length_warning is False


def _make_push_config(tmp_path, auth_method="env"):
    config_dir = tmp_path / ".preset-toolkit"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(yaml.safe_dump({
        "version": 1,
        "workspace": {"url": "https://test.preset.io", "id": "test123"},
        "dashboard": {"id": 1, "name": "Test"},
        "auth": {"method": auth_method},
    }))
    return ToolkitConfig.load(config_path)


def test_get_credentials_from_env(tmp_path):
    cfg = _make_push_config(tmp_path)
    with patch.dict(os.environ, {"PRESET_API_TOKEN": "tok", "PRESET_API_SECRET": "sec"}):
        token, secret = _get_credentials(cfg)
        assert token == "tok"
        assert secret == "sec"


def test_get_credentials_empty_when_nothing_set(tmp_path):
    cfg = _make_push_config(tmp_path)
    with patch.dict(os.environ, {}, clear=True):
        token, secret = _get_credentials(cfg)
        assert token == ""
        assert secret == ""


def test_push_catches_connect_error(tmp_path):
    import httpx
    cfg = _make_push_config(tmp_path)
    with patch("scripts.push_dashboard._get_auth_headers", return_value={"Authorization": "Bearer x"}):
        with patch("scripts.push_dashboard.resilient_request", side_effect=httpx.ConnectError("offline")):
            result = push_css_and_position(cfg, "body{}", dry_run=False)
            assert result.success is False
            assert "ConnectError" in result.error or "offline" in result.error
