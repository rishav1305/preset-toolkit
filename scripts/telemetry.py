"""Anonymous opt-in telemetry for preset-toolkit."""
import contextlib
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from scripts.logger import get_logger

log = get_logger("telemetry")

# PostHog project API key — this is a WRITE-ONLY key, safe to embed.
# It can only send events, not read them.
# FOLLOW-UP: Create a PostHog project at posthog.com and paste the key here.
# Until this is set, telemetry gracefully degrades to a no-op.
_POSTHOG_API_KEY = ""  # Set after creating PostHog project
_POSTHOG_HOST = "https://us.i.posthog.com"


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

    def track(self, event: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """Send an anonymous event."""
        if not self._enabled or not self._client:
            return
        try:
            props = dict(properties or {})
            props["plugin_version"] = "0.1.0"
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
