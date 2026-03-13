"""Sync orchestrator: pull + dedup + validate + push + CSS + verify."""
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from scripts.config import ToolkitConfig
from scripts.dedup import apply_dedup
from scripts.fingerprint import (
    compute_fingerprint, check_markers, save_fingerprint, load_fingerprint,
)
from scripts.logger import get_logger
log = get_logger("sync")


@dataclass
class SyncResult:
    success: bool
    steps_completed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: str = ""


def _ensure_sup() -> bool:
    """Ensure sup CLI is available, installing preset-cli if needed."""
    try:
        r = subprocess.run(["sup", "version"], capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return True
    except FileNotFoundError:
        pass
    from scripts.deps import ensure_sup_cli
    return ensure_sup_cli()


def _run_sup(args: List[str], retries: int = 3, backoff_base: float = 2.0) -> subprocess.CompletedProcess:
    """Run a sup CLI command with retries. Auto-installs sup if missing."""
    if not _ensure_sup():
        return subprocess.CompletedProcess(
            args=["sup"] + args, returncode=1,
            stdout="", stderr="preset-cli (sup) not installed and auto-install failed.",
        )
    last_result = None
    for attempt in range(1, retries + 1):
        last_result = subprocess.run(
            ["sup"] + args,
            capture_output=True, text=True, timeout=120,
        )
        if last_result.returncode == 0:
            return last_result
        if attempt < retries:
            wait = backoff_base * (2 ** (attempt - 1))
            log.warning(
                "sup %s failed (attempt %d/%d), retrying in %.1fs...",
                " ".join(args), attempt, retries, wait,
            )
            time.sleep(wait)
    return last_result


def pull(config: ToolkitConfig) -> SyncResult:
    """Pull latest from Preset + dedup."""
    result = SyncResult(success=False)
    sync_folder = config.sync_folder

    # Pull
    r = _run_sup(["sync", "run", sync_folder, "--pull-only", "--force"])
    if r.returncode != 0:
        result.error = f"sup sync pull failed: {r.stderr}"
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

    # Fingerprint check
    fp_file = Path(config.get("validation.fingerprint_file", ".preset-toolkit/.last-push-fingerprint"))
    last_fp = load_fingerprint(fp_file)

    # Find dataset YAMLs for fingerprinting
    dataset_yamls = list((assets / "datasets").rglob("*.yaml")) if (assets / "datasets").exists() else []
    if dataset_yamls:
        current_fp = compute_fingerprint(dataset_yamls[0])  # Primary dataset
        if last_fp and current_fp.hash != last_fp.hash:
            result.warnings.append(
                f"Fingerprint changed after pull: {last_fp.hash} -> {current_fp.hash}. "
                "Pull may have returned stale data."
            )
        result.steps_completed.append(f"fingerprint: {current_fp}")

    result.success = True
    return result


def validate(config: ToolkitConfig) -> SyncResult:
    """Validate sync folder + check markers."""
    result = SyncResult(success=False)
    sync_folder = config.sync_folder

    # Validate
    r = _run_sup(["sync", "validate", sync_folder])
    if r.returncode != 0:
        result.error = f"Validation failed: {r.stderr}"
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
                return result
        result.steps_completed.append("markers: all present")

    # Dry-run
    r = _run_sup(["sync", "run", sync_folder, "--push-only", "--dry-run", "--force"])
    if r.returncode != 0:
        result.error = f"Dry-run failed: {r.stderr}"
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

    # Push datasets/charts via sup sync
    if not css_only:
        r = _run_sup(["sync", "run", sync_folder, "--push-only", "--force"])
        if r.returncode != 0:
            result.error = f"sup sync push failed: {r.stderr}"
            return result
        result.steps_completed.append("push: datasets/charts")

    # Push CSS via REST API
    if not sync_only and config.get("css.push_via_api", True):
        try:
            from scripts.push_dashboard import push_css_and_position
            # Read CSS from dashboard YAML
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
                    result.warnings.append(f"CSS push failed: {pr.error}. Run /preset push --css-only to retry.")
        except Exception as e:
            result.warnings.append(f"CSS push error: {e}")

    # Save fingerprint
    fp_file = Path(config.get("validation.fingerprint_file", ".preset-toolkit/.last-push-fingerprint"))
    assets = Path(sync_folder) / "assets"
    dataset_yamls = list((assets / "datasets").rglob("*.yaml")) if (assets / "datasets").exists() else []
    if dataset_yamls:
        fp = compute_fingerprint(dataset_yamls[0])
        save_fingerprint(fp, fp_file)
        result.steps_completed.append(f"fingerprint saved: {fp}")

    result.success = True
    return result
