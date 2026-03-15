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
