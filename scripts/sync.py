"""Sync orchestrator: pull + dedup + validate + push + CSS + verify.

Uses preset-cli (pip package: preset-cli) which installs two binaries:
  - preset-cli: Top-level CLI for Preset Manager API
  - superset-cli: Direct Superset instance commands

Pull = preset-cli superset export-assets <directory>
Push = preset-cli superset sync native <directory>
"""
import os
import random
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from scripts.config import ToolkitConfig
from scripts.dedup import apply_dedup
from scripts.fingerprint import (
    compute_fingerprint, compute_fingerprint_map, check_markers,
    save_fingerprint, save_fingerprint_map, load_fingerprint, load_fingerprint_map,
)
from scripts.logger import get_logger, sanitize
from scripts.telemetry import get_telemetry

log = get_logger("sync")

# Cached path to the preset-cli binary once discovered
_cli_path: Optional[str] = None


class CLINotFoundError(RuntimeError):
    """Raised when preset-cli is not available."""
    pass


# Keep old name as alias for backward compatibility with tests
SupNotFoundError = CLINotFoundError


@dataclass
class SyncResult:
    success: bool
    steps_completed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: str = ""


def _find_cli() -> Optional[str]:
    """Find the preset-cli binary. Checks .venv first, then system PATH."""
    # 1. Check project .venv/bin/preset-cli
    venv_cli = Path(".venv/bin/preset-cli")
    if venv_cli.exists():
        return str(venv_cli.resolve())
    # 2. Check system PATH
    system_cli = shutil.which("preset-cli")
    if system_cli:
        return system_cli
    return None


# Keep old name for backward compatibility with tests
_find_sup = _find_cli


def _ensure_cli() -> str:
    """Find the preset-cli binary and verify it works.

    Returns the path to the preset-cli binary.
    Raises CLINotFoundError if not installed — does NOT auto-install.
    Dependencies should be set up via /preset-toolkit:preset-setup.
    """
    global _cli_path
    if _cli_path:
        return _cli_path

    found = _find_cli()
    if found:
        try:
            r = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                _cli_path = found
                log.debug("Using preset-cli at: %s", found)
                return found
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    raise CLINotFoundError(
        "preset-cli not found. Run /preset-toolkit:preset-setup to install dependencies."
    )


# Keep old name for backward compatibility with tests
_ensure_sup = _ensure_cli


def _build_auth_args(config: ToolkitConfig) -> List[str]:
    """Build auth CLI args from environment or config."""
    args = []
    token = os.environ.get("PRESET_API_TOKEN", "")
    secret = os.environ.get("PRESET_API_SECRET", "")
    if token and secret:
        args.extend(["--api-token", token, "--api-secret", secret])
    return args


def _run_cli(args: List[str], retries: int = 3, backoff_base: float = 2.0) -> subprocess.CompletedProcess:
    """Run a preset-cli command with retries. Raises CLINotFoundError if missing."""
    cli = _ensure_cli()
    last_result = None
    for attempt in range(1, retries + 1):
        try:
            last_result = subprocess.run(
                [cli] + args,
                capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            log.warning("preset-cli %s timed out (attempt %d/%d)", " ".join(args[:3]), attempt, retries)
            last_result = subprocess.CompletedProcess(
                args=[cli] + args, returncode=1,
                stdout="", stderr="Command timed out after 120s",
            )
        if last_result.returncode == 0:
            return last_result
        if attempt < retries:
            wait = backoff_base * (2 ** (attempt - 1)) * (0.5 + random.random())
            log.warning(
                "preset-cli failed (attempt %d/%d), retrying in %.1fs...",
                attempt, retries, wait,
            )
            time.sleep(wait)
    return last_result


# Keep old name for backward compatibility with tests
_run_sup = _run_cli


def pull(config: ToolkitConfig) -> SyncResult:
    """Pull latest from Preset via preset-cli export-assets + dedup."""
    t = get_telemetry(config._path)
    result = SyncResult(success=False)
    sync_folder = config.sync_folder

    with t.timed("pull"):
        # Build command: preset-cli --api-token ... --api-secret ... superset export-assets <dir> --overwrite
        auth_args = _build_auth_args(config)
        export_args = auth_args + [
            "superset", "export-assets", sync_folder,
            "--overwrite",
            "--dashboard-ids", str(config.dashboard_id),
        ]

        r = _run_cli(export_args)
        if r.returncode != 0:
            result.error = f"export-assets failed: {sanitize(r.stderr)}"
            t.track_error("pull", "export_failed", sanitize(r.stderr))
            return result
        result.steps_completed.append("pull")

        # Dedup charts
        assets = Path(sync_folder)
        charts_dir = assets / "charts"
        if charts_dir.exists():
            removed = apply_dedup(charts_dir)
            if removed:
                result.steps_completed.append(f"dedup: removed {removed} chart duplicates")

        # Dedup datasets
        datasets_dir = assets / "datasets"
        if datasets_dir.exists():
            for subdir in datasets_dir.iterdir():
                if subdir.is_dir():
                    removed = apply_dedup(subdir)
                    if removed:
                        result.steps_completed.append(f"dedup: removed {removed} dataset duplicates in {subdir.name}")

        # Fingerprint check (v2 per-file map)
        fp_file = Path(config.get("validation.fingerprint_file", ".preset-toolkit/.last-push-fingerprint"))
        last_map = load_fingerprint_map(fp_file)
        current_map = compute_fingerprint_map(assets)
        if last_map:
            changes = current_map.diff(last_map)
            if changes:
                summary = current_map.summary(last_map)
                result.warnings.append(
                    f"Fingerprint changed after pull: {summary}. "
                    "Pull may have returned stale data."
                )
        result.steps_completed.append(f"fingerprint: {current_map.summary()}")

        result.success = True
    return result


def validate(config: ToolkitConfig) -> SyncResult:
    """Validate sync folder — check markers and structure."""
    t = get_telemetry(config._path)
    result = SyncResult(success=False)
    sync_folder = config.sync_folder

    with t.timed("validate"):
        # Check sync folder exists and has content
        assets = Path(sync_folder)
        if not assets.exists():
            result.error = f"Sync folder '{sync_folder}' does not exist. Run pull first."
            t.track_error("validate", "no_sync_folder", result.error)
            return result
        result.steps_completed.append("validate: sync folder exists")

        # Marker check
        markers_file = Path(config.get("validation.markers_file", ".preset-toolkit/markers.txt"))
        if markers_file.exists():
            dataset_yamls = list((assets / "datasets").rglob("*.yaml")) if (assets / "datasets").exists() else []
            for ds in dataset_yamls:
                mr = check_markers(ds, markers_file)
                if not mr.all_present:
                    result.error = f"Missing markers in {ds.name}: {', '.join(mr.missing)}"
                    t.track_error("validate", "missing_markers", result.error)
                    return result
            result.steps_completed.append("markers: all present")

        result.success = True
    return result


def push(
    config: ToolkitConfig,
    css_only: bool = False,
    sync_only: bool = False,
    dry_run: bool = False,
) -> SyncResult:
    """Full push: validate + preset-cli sync native + CSS push."""
    t = get_telemetry(config._path)
    result = SyncResult(success=False)

    # Validate first
    val = validate(config)
    if not val.success:
        result.error = val.error
        return result
    result.steps_completed.extend(val.steps_completed)

    if dry_run:
        result.steps_completed.append("dry-run mode — skipping actual push")
        result.success = True
        return result

    sync_folder = config.sync_folder

    with t.timed("push", css_only=css_only, sync_only=sync_only):
        # Push via preset-cli superset sync native
        if not css_only:
            auth_args = _build_auth_args(config)
            push_args = auth_args + [
                "superset", "sync", "native", sync_folder,
                "--overwrite",
            ]
            r = _run_cli(push_args)
            if r.returncode != 0:
                result.error = f"sync native push failed: {sanitize(r.stderr)}"
                t.track_error("push", "sync_native_failed", sanitize(r.stderr))
                return result
            result.steps_completed.append("push: datasets/charts")

        # Push CSS via REST API
        if not sync_only and config.get("css.push_via_api", True):
            try:
                from scripts.push_dashboard import push_css_and_position
                dash_dir = Path(sync_folder) / "dashboards"
                dash_yamls = list(dash_dir.glob("*.yaml")) if dash_dir.exists() else []
                if dash_yamls:
                    import yaml
                    with open(dash_yamls[0]) as f:
                        dash_data = yaml.safe_load(f)
                    if not isinstance(dash_data, dict):
                        dash_data = {}
                    css = dash_data.get("css", "")
                    pos = dash_data.get("position_json", None)
                    pr = push_css_and_position(config, css, pos)
                    if pr.success:
                        result.steps_completed.append("push: CSS/position via API")
                    else:
                        log.warning("CSS push failed: %s", pr.error)
                        result.warnings.append(f"CSS push failed: {pr.error}. Run /preset push --css-only to retry.")
            except Exception as e:
                log.warning("CSS push error: %s", e)
                result.warnings.append(f"CSS push error: {e}")

        # Save fingerprint (v2 per-file map)
        fp_file = Path(config.get("validation.fingerprint_file", ".preset-toolkit/.last-push-fingerprint"))
        assets = Path(sync_folder)
        try:
            fp_map = compute_fingerprint_map(assets)
            save_fingerprint_map(fp_map, fp_file)
            result.steps_completed.append(f"fingerprint saved: {fp_map.summary()}")
        except (OSError, Exception) as e:
            log.warning("Could not save fingerprint: %s", e)

    result.success = True
    return result
