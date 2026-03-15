"""Dashboard operations: list, info, pull.

Wraps sup dashboard subcommands as structured Python functions.
Each function calls run_sup() with --json and parses the output
into typed dataclasses.
"""
import json
from dataclasses import dataclass, field
from typing import List, Optional

from scripts.config import ToolkitConfig
from scripts.sync import run_sup


@dataclass
class DashboardSummary:
    """Single dashboard in a list result."""
    id: int
    name: str
    status: str = ""
    url: str = ""
    modified: str = ""


@dataclass
class DashboardListResult:
    """Result from list_dashboards()."""
    success: bool
    dashboards: List[DashboardSummary] = field(default_factory=list)
    total: int = 0
    error: str = ""


@dataclass
class DashboardInfo:
    """Detailed metadata for a single dashboard."""
    success: bool
    id: int = 0
    name: str = ""
    status: str = ""
    url: str = ""
    slug: str = ""
    charts: List[dict] = field(default_factory=list)
    css: str = ""
    raw: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class DashboardPullResult:
    """Result from pull_dashboards()."""
    success: bool
    dashboards_pulled: int = 0
    files: List[str] = field(default_factory=list)
    error: str = ""


def _parse_dashboard_summary(item: dict) -> DashboardSummary:
    """Parse a single dashboard dict from sup JSON into DashboardSummary."""
    return DashboardSummary(
        id=item.get("id", 0),
        name=item.get("dashboard_title", ""),
        status=item.get("status", ""),
        url=item.get("url", ""),
        modified=item.get("changed_on_utc", ""),
    )


def list_dashboards(
    config: ToolkitConfig,
    search: Optional[str] = None,
    mine: bool = False,
    published: bool = False,
    draft: bool = False,
    folder: Optional[str] = None,
    limit: Optional[int] = None,
) -> DashboardListResult:
    """List dashboards with optional filtering. Uses sup dashboard list --json."""
    args = ["dashboard", "list", "--json"]

    if search is not None:
        args.extend(["--search", search])
    if mine:
        args.append("--mine")
    if published:
        args.append("--published")
    if draft:
        args.append("--draft")
    if folder is not None:
        args.extend(["--folder", folder])
    if limit is not None:
        args.extend(["--limit", str(limit)])

    r = run_sup(args)
    if r.returncode != 0:
        return DashboardListResult(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return DashboardListResult(success=False, error=f"JSON parse error: {e}")

    if isinstance(data, list):
        dashboards = [_parse_dashboard_summary(item) for item in data]
    else:
        dashboards = []

    return DashboardListResult(success=True, dashboards=dashboards, total=len(dashboards))


def get_dashboard_info(
    config: ToolkitConfig,
    dashboard_id: int,
) -> DashboardInfo:
    """Get detailed metadata for a single dashboard. Uses sup dashboard info --json."""
    args = ["dashboard", "info", str(dashboard_id), "--json"]

    r = run_sup(args)
    if r.returncode != 0:
        return DashboardInfo(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return DashboardInfo(success=False, error=f"JSON parse error: {e}")

    if not isinstance(data, dict):
        return DashboardInfo(success=False, error="Unexpected response format")

    return DashboardInfo(
        success=True,
        id=data.get("id", 0),
        name=data.get("dashboard_title", ""),
        status=data.get("status", ""),
        url=data.get("url", ""),
        slug=data.get("slug", ""),
        charts=data.get("charts", []),
        css=data.get("css", ""),
        raw=data,
    )


def pull_dashboards(
    config: ToolkitConfig,
    dashboard_id: Optional[int] = None,
    dashboard_ids: Optional[List[int]] = None,
    search: Optional[str] = None,
    mine: bool = False,
    limit: Optional[int] = None,
    skip_dependencies: bool = False,
    overwrite: bool = True,
    assets_folder: Optional[str] = None,
) -> DashboardPullResult:
    """Pull dashboard definitions to local filesystem. Uses sup dashboard pull --json.

    dashboard_id and dashboard_ids are mutually exclusive.
    Raises ValueError if both are provided.
    """
    if dashboard_id is not None and dashboard_ids is not None:
        raise ValueError("dashboard_id and dashboard_ids are mutually exclusive")

    args = ["dashboard", "pull", "--json"]

    if dashboard_id is not None:
        args.extend(["--id", str(dashboard_id)])
    if dashboard_ids is not None:
        args.extend(["--ids", ",".join(str(did) for did in dashboard_ids)])
    if search is not None:
        args.extend(["--search", search])
    if mine:
        args.append("--mine")
    if limit is not None:
        args.extend(["--limit", str(limit)])
    if skip_dependencies:
        args.append("--skip-dependencies")
    if not overwrite:
        args.append("--no-overwrite")
    if assets_folder is not None:
        args.extend(["--assets-folder", assets_folder])

    r = run_sup(args)
    if r.returncode != 0:
        return DashboardPullResult(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return DashboardPullResult(success=False, error=f"JSON parse error: {e}")

    if not isinstance(data, dict):
        return DashboardPullResult(success=True)

    return DashboardPullResult(
        success=True,
        dashboards_pulled=data.get("dashboards_pulled", 0),
        files=data.get("files", []),
    )
