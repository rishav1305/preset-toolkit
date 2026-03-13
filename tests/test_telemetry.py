"""Tests for anonymous telemetry module."""
import time
from unittest.mock import patch, MagicMock
from pathlib import Path

import yaml

from scripts.telemetry import Telemetry


def _make_config(tmp_path, enabled=True):
    """Create a minimal config with telemetry settings."""
    config_dir = tmp_path / ".preset-toolkit"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(yaml.safe_dump({
        "version": 1,
        "workspace": {"url": "https://test.preset.io", "id": "test123"},
        "dashboard": {"id": 1, "name": "Test"},
        "telemetry": {"enabled": enabled, "anonymous_id": "", "debug": False},
    }))
    return config_path


def test_telemetry_disabled_does_not_send(tmp_path):
    config_path = _make_config(tmp_path, enabled=False)
    t = Telemetry(config_path)
    assert t._client is None
    # track() should be a no-op — no exception, no side effects
    t.track("test_event", {"key": "value"})  # Should not raise


def test_telemetry_enabled_generates_anonymous_id(tmp_path):
    config_path = _make_config(tmp_path, enabled=True)
    with patch("scripts.telemetry._create_posthog_client", return_value=MagicMock()):
        t = Telemetry(config_path)
        assert t.anonymous_id != ""
        assert len(t.anonymous_id) == 36  # UUID format


def test_telemetry_track_sends_event(tmp_path):
    config_path = _make_config(tmp_path, enabled=True)
    mock_client = MagicMock()
    with patch("scripts.telemetry._create_posthog_client", return_value=mock_client):
        t = Telemetry(config_path)
        t.track("command_run", {"command": "pull", "duration_ms": 1200})
        mock_client.capture.assert_called_once()
        call_args = mock_client.capture.call_args
        assert call_args[1]["event"] == "command_run"
        assert call_args[1]["properties"]["command"] == "pull"


def test_telemetry_persists_anonymous_id(tmp_path):
    config_dir = tmp_path / ".preset-toolkit"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    # Write config with double quotes to match _save_anonymous_id's replacement target
    config_path.write_text(
        'version: 1\n'
        'workspace:\n  url: "https://test.preset.io"\n  id: "test123"\n'
        'dashboard:\n  id: 1\n  name: "Test"\n'
        'telemetry:\n  enabled: true\n  anonymous_id: ""\n  debug: false\n'
    )
    with patch("scripts.telemetry._create_posthog_client", return_value=MagicMock()):
        t1 = Telemetry(config_path)
        id1 = t1.anonymous_id
    with patch("scripts.telemetry._create_posthog_client", return_value=MagicMock()):
        t2 = Telemetry(config_path)
        assert t2.anonymous_id == id1


def test_telemetry_timed_context_manager(tmp_path):
    config_path = _make_config(tmp_path, enabled=True)
    mock_client = MagicMock()
    with patch("scripts.telemetry._create_posthog_client", return_value=mock_client):
        t = Telemetry(config_path)
        with t.timed("pull"):
            time.sleep(0.01)
        call_args = mock_client.capture.call_args
        assert call_args[1]["properties"]["duration_ms"] >= 10


def test_telemetry_error_event(tmp_path):
    config_path = _make_config(tmp_path, enabled=True)
    mock_client = MagicMock()
    with patch("scripts.telemetry._create_posthog_client", return_value=mock_client):
        t = Telemetry(config_path)
        t.track_error("push", "HTTPStatusError", "HTTP 403: Forbidden")
        call_args = mock_client.capture.call_args
        assert call_args[1]["event"] == "error"
        assert call_args[1]["properties"]["command"] == "push"
        assert call_args[1]["properties"]["error_type"] == "HTTPStatusError"
