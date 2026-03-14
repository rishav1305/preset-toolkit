"""Sync orchestrator: pull + dedup + validate + push + CSS + verify.

Uses the sup CLI (pip package: superset-sup) for sync operations:
  sup sync run <folder> --pull-only --force    (pull)
  sup sync validate <folder>                   (validate)
  sup sync run <folder> --push-only --force    (push)

Requires sync_config.yml in the sync folder.
"""
import os
import random
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
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

# Cached path to the sup binary once discovered
_sup_path: Optional[str] = None


class SupNotFoundError(RuntimeError):
    """Raised when sup CLI is not available."""
    pass


# Aliases for backward compatibility
CLINotFoundError = SupNotFoundError


@dataclass
class SyncResult:
    success: bool
    steps_completed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: str = ""


class ChangeAction(str, Enum):
    """Valid actions for an asset change."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    NO_CHANGE = "no_change"

    def __str__(self) -> str:
        return self.value


@dataclass
class AssetChange:
    """A single asset that would be created, updated, deleted, or unchanged."""
    asset_type: str         # "chart", "dataset", "dashboard"
    name: str
    action: ChangeAction
    details: str = ""       # optional human-readable context


@dataclass
class DryRunResult:
    """Structured output from validate() with parsed dry-run diff."""
    success: bool
    changes: List[AssetChange]
    validation_passed: bool
    markers_passed: bool
    raw_output: str
    steps_completed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: str = ""


def _find_sup() -> Optional[str]:
    """Find the sup CLI binary. Checks .venv first, then system PATH."""
    venv_sup = Path(".venv/bin/sup")
    if venv_sup.exists():
        return str(venv_sup.resolve())
    system_sup = shutil.which("sup")
    if system_sup:
        return system_sup
    return None


def _ensure_sup() -> str:
    """Find the sup CLI binary and verify it works.

    Returns the path to the sup binary.
    Raises SupNotFoundError if not installed — does NOT auto-install.
    """
    global _sup_path
    if _sup_path:
        return _sup_path

    found = _find_sup()
    if found:
        try:
            r = subprocess.run([found, "--version"], capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                _sup_path = found
                log.debug("Using sup at: %s", found)
                return found
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    raise SupNotFoundError(
        "sup CLI not found. Run /preset-toolkit:preset-setup to install dependencies."
    )


def _run_sup(args: List[str], retries: int = 3, backoff_base: float = 2.0) -> subprocess.CompletedProcess:
    """Run a sup CLI command with retries. Raises SupNotFoundError if missing."""
    sup = _ensure_sup()
    last_result = None
    for attempt in range(1, retries + 1):
        try:
            last_result = subprocess.run(
                [sup] + args,
                capture_output=True, text=True, timeout=120,
            )
        except subprocess.TimeoutExpired:
            log.warning("sup %s timed out (attempt %d/%d)", " ".join(args[:3]), attempt, retries)
            last_result = subprocess.CompletedProcess(
                args=[sup] + args, returncode=1,
                stdout="", stderr="Command timed out after 120s",
            )
        if last_result.returncode == 0:
            return last_result
        if attempt < retries:
            wait = backoff_base * (2 ** (attempt - 1)) * (0.5 + random.random())
            log.warning(
                "sup failed (attempt %d/%d), retrying in %.1fs...",
                attempt, retries, wait,
            )
            time.sleep(wait)
    return last_result


def pull(config: ToolkitConfig) -> SyncResult:
    """Pull latest from Preset via sup sync run --pull-only."""
    t = get_telemetry(config._path)
    result = SyncResult(success=False)
    sync_folder = config.sync_folder

    with t.timed("pull"):
        r = _run_sup(["sync", "run", sync_folder, "--pull-only", "--force"])
        if r.returncode != 0:
            result.error = f"sup sync pull failed: {sanitize(r.stderr)}"
            t.track_error("pull", "sup_failed", sanitize(r.stderr))
            return result
        result.steps_completed.append("pull")

        # Dedup charts
        assets = Path(sync_folder) / "assets"
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
    """Validate sync folder via sup sync validate + check markers."""
    t = get_telemetry(config._path)
    result = SyncResult(success=False)
    sync_folder = config.sync_folder

    with t.timed("validate"):
        r = _run_sup(["sync", "validate", sync_folder])
        if r.returncode != 0:
            result.error = f"Validation failed: {sanitize(r.stderr)}"
            t.track_error("validate", "sup_validate_failed", sanitize(r.stderr))
            return result
        result.steps_completed.append("validate")

        # Marker check
        markers_file = Path(config.get("validation.markers_file", ".preset-toolkit/markers.txt"))
        if markers_file.exists():
            assets = Path(sync_folder) / "assets"
            dataset_yamls = list((assets / "datasets").rglob("*.yaml")) if (assets / "datasets").exists() else []
            for ds in dataset_yamls:
                mr = check_markers(ds, markers_file)
                if not mr.all_present:
                    result.error = f"Missing markers in {ds.name}: {', '.join(mr.missing)}"
                    t.track_error("validate", "missing_markers", result.error)
                    return result
            result.steps_completed.append("markers: all present")

        # Dry-run push
        r = _run_sup(["sync", "run", sync_folder, "--push-only", "--dry-run", "--force"])
        if r.returncode != 0:
            result.error = f"Dry-run failed: {sanitize(r.stderr)}"
            t.track_error("validate", "dry_run_failed", sanitize(r.stderr))
            return result
        result.steps_completed.append("dry-run")

        result.success = True
    return result


def push(
    config: ToolkitConfig,
    css_only: bool = False,
    sync_only: bool = False,
    dry_run: bool = False,
) -> SyncResult:
    """Full push: validate + sup sync push + CSS push + verify."""
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
        if not css_only:
            r = _run_sup(["sync", "run", sync_folder, "--push-only", "--force"])
            if r.returncode != 0:
                result.error = f"sup sync push failed: {sanitize(r.stderr)}"
                t.track_error("push", "sup_push_failed", sanitize(r.stderr))
                return result
            result.steps_completed.append("push: datasets/charts")

        # Push CSS via REST API
        if not sync_only and config.get("css.push_via_api", True):
            try:
                from scripts.push_dashboard import push_css_and_position
                dash_dir = Path(sync_folder) / "assets" / "dashboards"
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
                        result.warnings.append(f"CSS push failed: {pr.error}.")
            except Exception as e:
                log.warning("CSS push error: %s", e)
                result.warnings.append(f"CSS push error: {e}")

        # Save fingerprint (v2 per-file map)
        fp_file = Path(config.get("validation.fingerprint_file", ".preset-toolkit/.last-push-fingerprint"))
        assets = Path(sync_folder) / "assets"
        try:
            fp_map = compute_fingerprint_map(assets)
            save_fingerprint_map(fp_map, fp_file)
            result.steps_completed.append(f"fingerprint saved: {fp_map.summary()}")
        except (OSError, Exception) as e:
            log.warning("Could not save fingerprint: %s", e)

    result.success = True
    return result
