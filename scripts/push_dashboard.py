"""Push dashboard CSS + position_json via Preset REST API."""
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_SECRET_PATTERNS = re.compile(
    r'(token|secret|password|authorization|bearer|jwt)\s*[=:]\s*\S+',
    re.IGNORECASE,
)


def _sanitize(text: str) -> str:
    """Remove potential secrets from error text."""
    return _SECRET_PATTERNS.sub("[REDACTED]", text)[:500]

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
from scripts.http import resilient_request
from scripts.logger import get_logger

log = get_logger("push_dashboard")

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
            # Check file permissions
            mode = keys_path.stat().st_mode
            if mode & (stat.S_IRGRP | stat.S_IROTH):
                log.warning(
                    "keys.txt has loose permissions (%o). Run: chmod 600 %s",
                    stat.S_IMODE(mode), keys_path,
                )
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
    login_path = config.get("api.login_path", "/api/v1/security/login")
    auth_url = f"{config.workspace_url.rstrip('/')}{login_path}"
    resp = resilient_request("POST", auth_url, json={
        "username": token,
        "password": secret,
        "provider": "db",
    })
    jwt = resp.json().get("access_token", "")
    if not jwt:
        log.error("Auth exchange returned empty JWT")
        return {}
    if jwt.count(".") != 2:
        log.error("Auth exchange returned malformed JWT")
        return {}
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
    dash_path = config.get("api.dashboard_path", "/api/v1/dashboard/{id}")
    url = f"{config.workspace_url.rstrip('/')}{dash_path.format(id=config.dashboard_id)}"
    headers = _get_auth_headers(config)
    resp = resilient_request("GET", url, headers=headers)
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

    dash_path = config.get("api.dashboard_path", "/api/v1/dashboard/{id}")
    url = f"{config.workspace_url.rstrip('/')}{dash_path.format(id=config.dashboard_id)}"
    headers = _get_auth_headers(config)

    # Fetch CSRF token
    csrf_path = config.get("api.csrf_path", "/api/v1/security/csrf_token/")
    csrf_url = f"{config.workspace_url.rstrip('/')}{csrf_path}"
    try:
        csrf_resp = resilient_request("GET", csrf_url, headers=headers, retries=1)
        csrf_token = csrf_resp.json().get("result", "")
        headers["X-CSRFToken"] = csrf_token
    except (httpx.HTTPError, KeyError) as e:
        log.debug("CSRF token fetch skipped: %s", e)

    payload = {"css": css}
    if position_json is not None:
        payload["position_json"] = position_json

    try:
        resp = resilient_request("PUT", url, headers=headers, json=payload)
        return PushResult(success=True, css_changed=True, position_changed=position_json is not None)
    except httpx.HTTPStatusError as e:
        return PushResult(success=False, error=f"HTTP {e.response.status_code}: {_sanitize(e.response.text)}")
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        return PushResult(success=False, error=f"{type(e).__name__}: {e}")
