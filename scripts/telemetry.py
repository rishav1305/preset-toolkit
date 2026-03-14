"""Anonymous opt-in telemetry for preset-toolkit."""
import contextlib
import json
import os
import platform
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from scripts.logger import get_logger

log = get_logger("telemetry")


def _read_plugin_version() -> str:
    """Read version from plugin.json (single source of truth)."""
    try:
        plugin_json = Path(__file__).parent.parent / ".claude-plugin" / "plugin.json"
        with open(plugin_json) as f:
            return json.load(f).get("version", "0.0.0")
    except Exception:
        return "0.0.0"


_PLUGIN_VERSION = _read_plugin_version()

# PostHog project key — set via POSTHOG_API_KEY environment variable.
# No default: telemetry is inert until the key is configured.
_POSTHOG_API_KEY = os.environ.get("POSTHOG_API_KEY", "")
_POSTHOG_HOST = os.environ.get("POSTHOG_HOST", "https://us.i.posthog.com")

# Module-level singleton so any module can call get_telemetry()
_instance: Optional["Telemetry"] = None


def get_telemetry(config_path: Optional[Path] = None) -> "Telemetry":
    """Get or create the global Telemetry singleton.

    First call must provide config_path. Subsequent calls return the cached instance.
    """
    global _instance
    if _instance is None:
        if config_path is None:
            return _NullTelemetry()
        _instance = Telemetry(config_path)
    return _instance


def _system_properties() -> Dict[str, Any]:
    """Collect anonymous system properties for user profiling."""
    return {
        "os": platform.system(),
        "os_version": platform.release(),
        "python_version": platform.python_version(),
        "arch": platform.machine(),
        "plugin_version": _PLUGIN_VERSION,
    }


def _create_posthog_client():
    """Create PostHog client, returns None if unavailable."""
    if not _POSTHOG_API_KEY:
        return None
    try:
        from posthog import Posthog
        return Posthog(project_api_key=_POSTHOG_API_KEY, host=_POSTHOG_HOST)
    except ImportError:
        log.debug("posthog package not installed — telemetry disabled")
        return None
    except Exception as e:
        log.debug("Failed to create PostHog client: %s", e)
        return None


class _NullTelemetry:
    """No-op telemetry returned when not initialized."""
    anonymous_id = ""

    def track(self, event, properties=None): pass
    def track_error(self, command, error_type, message): pass
    def identify(self): pass
    @contextlib.contextmanager
    def timed(self, command, **extra): yield
    def shutdown(self): pass


class Telemetry:
    """Anonymous usage telemetry. Opt-in via config (telemetry.enabled: true)."""

    def __init__(self, config_path: Path):
        self._config_path = Path(config_path)
        self._enabled = False
        self._client = None
        self.anonymous_id = ""

        config = self._load_config()
        telem_config = config.get("telemetry", {}) or {}
        self._enabled = bool(telem_config.get("enabled", False))

        if not self._enabled:
            return

        self.anonymous_id = telem_config.get("anonymous_id", "") or ""
        if not self.anonymous_id:
            self.anonymous_id = str(uuid.uuid4())
            self._save_anonymous_id(self.anonymous_id)

        self._client = _create_posthog_client()

    def _load_config(self) -> dict:
        try:
            with open(self._config_path) as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_anonymous_id(self, anon_id: str) -> None:
        """Persist the anonymous ID back into config.yaml."""
        try:
            text = self._config_path.read_text()
            if 'anonymous_id: ""' in text:
                text = text.replace('anonymous_id: ""', f'anonymous_id: "{anon_id}"')
                self._config_path.write_text(text)
        except Exception as e:
            log.debug("Could not persist anonymous_id: %s", e)

    def identify(self) -> None:
        """Send system properties to PostHog as user traits (called once per session)."""
        if not self._enabled or not self._client:
            return
        try:
            self._client.identify(
                distinct_id=self.anonymous_id,
                properties=_system_properties(),
            )
        except Exception as e:
            log.debug("Telemetry identify failed: %s", e)

    def track(self, event: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """Send an anonymous event."""
        if not self._enabled or not self._client:
            return
        try:
            props = _system_properties()
            props.update(properties or {})
            self._client.capture(
                distinct_id=self.anonymous_id,
                event=event,
                properties=props,
            )
        except Exception as e:
            log.debug("Telemetry send failed: %s", e)

    def track_error(self, command: str, error_type: str, message: str) -> None:
        """Track an error event (message is sanitized — no secrets)."""
        self.track("error", {
            "command": command,
            "error_type": error_type,
            "error_message": message[:200],
        })

    @contextlib.contextmanager
    def timed(self, command: str, **extra):
        """Context manager that tracks command duration."""
        start = time.monotonic()
        error = None
        try:
            yield
        except Exception as e:
            error = e
            raise
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            props = {"command": command, "duration_ms": duration_ms, **extra}
            if error:
                props["error"] = type(error).__name__
                self.track("command_error", props)
            else:
                self.track("command_success", props)

    def shutdown(self) -> None:
        """Flush and close the client."""
        if self._client:
            try:
                self._client.shutdown()
            except Exception:
                pass
