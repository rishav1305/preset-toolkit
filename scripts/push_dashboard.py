"""Push dashboard CSS + position_json via Preset REST API."""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import httpx
except ImportError:
    from scripts.deps import ensure_package
    ensure_package("httpx")
    import httpx

try:
    import yaml
except ImportError:
    from scripts.deps import ensure_package as _ep
    _ep("yaml")
    import yaml

from scripts.config import ToolkitConfig

CSS_MAX_DEFAULT = 30000


@dataclass
class CssComparison:
    changed: bool
    local_length: int
    remote_length: int
    length_warning: bool = False


@dataclass
class PushResult:
    success: bool
    css_changed: bool = False
    position_changed: bool = False
    error: str = ""


def _get_credentials(config: ToolkitConfig) -> tuple:
    """Get API token + secret from env or file."""
    token = os.environ.get("PRESET_API_TOKEN", "")
    secret = os.environ.get("PRESET_API_SECRET", "")
    if not token and config.get("auth.method") == "file":
        keys_path = Path(".preset-toolkit/.secrets/keys.txt")
        if keys_path.exists():
            for line in keys_path.read_text().splitlines():
                if line.startswith("PRESET_API_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip("'\"")
                elif line.startswith("PRESET_API_SECRET="):
                    secret = line.split("=", 1)[1].strip().strip("'\"")
    return token, secret


def _get_auth_headers(config: ToolkitConfig) -> dict:
    """Exchange API token+secret for JWT, return auth headers."""
    token, secret = _get_credentials(config)
    if not token:
        return {}
    # Exchange API token for JWT via Preset's auth endpoint
    auth_url = f"{config.workspace_url.rstrip('/')}/api/v1/security/login"
    resp = httpx.post(auth_url, json={
        "username": token,
        "password": secret,
        "provider": "db",
    }, timeout=30)
    resp.raise_for_status()
    jwt = resp.json().get("access_token", "")
    return {"Authorization": f"Bearer {jwt}"}


def compare_css(local_css: str, remote_css: str) -> CssComparison:
    """Compare local vs remote CSS."""
    return CssComparison(
        changed=local_css != remote_css,
        local_length=len(local_css),
        remote_length=len(remote_css),
        length_warning=len(local_css) > CSS_MAX_DEFAULT,
    )


def fetch_dashboard(config: ToolkitConfig) -> dict:
    """GET /api/v1/dashboard/{id}"""
    url = f"{config.workspace_url.rstrip('/')}/api/v1/dashboard/{config.dashboard_id}"
    headers = _get_auth_headers(config)
    resp = httpx.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json().get("result", {})


def push_css_and_position(
    config: ToolkitConfig,
    css: str,
    position_json: Optional[str] = None,
    dry_run: bool = False,
) -> PushResult:
    """PUT /api/v1/dashboard/{id} with CSS and optionally position_json."""
    if dry_run:
        remote = fetch_dashboard(config)
        cmp = compare_css(css, remote.get("css", ""))
        return PushResult(
            success=True,
            css_changed=cmp.changed,
            position_changed=position_json is not None
            and position_json != remote.get("position_json", ""),
        )

    url = f"{config.workspace_url.rstrip('/')}/api/v1/dashboard/{config.dashboard_id}"
    headers = _get_auth_headers(config)

    # Fetch CSRF token
    csrf_url = f"{config.workspace_url.rstrip('/')}/api/v1/security/csrf_token/"
    try:
        csrf_resp = httpx.get(csrf_url, headers=headers, timeout=30)
        csrf_token = csrf_resp.json().get("result", "")
        headers["X-CSRFToken"] = csrf_token
    except Exception:
        pass  # CSRF not always required on Preset Cloud

    payload = {"css": css}
    if position_json is not None:
        payload["position_json"] = position_json

    try:
        resp = httpx.put(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return PushResult(success=True, css_changed=True, position_changed=position_json is not None)
    except httpx.HTTPStatusError as e:
        return PushResult(success=False, error=f"HTTP {e.response.status_code}: {e.response.text}")
