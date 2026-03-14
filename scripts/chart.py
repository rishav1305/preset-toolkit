"""Chart operations: list, info, sql, data, pull, push.

Wraps sup chart subcommands as structured Python functions.
Each function calls run_sup() with --json and parses the output
into typed dataclasses.
"""
import json
from dataclasses import dataclass, field
from typing import List, Optional

from scripts.config import ToolkitConfig
from scripts.sync import run_sup


@dataclass
class ChartSummary:
    """Single chart in a list result."""
    id: int
    name: str
    viz_type: str
    dataset_name: str = ""
    modified: str = ""


@dataclass
class ChartListResult:
    """Result from list_charts()."""
    success: bool
    charts: List[ChartSummary] = field(default_factory=list)
    total: int = 0
    error: str = ""


@dataclass
class ChartInfo:
    """Detailed metadata for a single chart."""
    success: bool
    id: int = 0
    name: str = ""
    viz_type: str = ""
    dataset_name: str = ""
    query_context: str = ""
    params: str = ""
    raw: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class ChartSQL:
    """Compiled SQL query for a chart."""
    success: bool
    sql: str = ""
    error: str = ""


@dataclass
class ChartData:
    """Actual data results from a chart query."""
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[dict] = field(default_factory=list)
    row_count: int = 0
    error: str = ""


@dataclass
class ChartPullResult:
    """Result from pull_charts()."""
    success: bool
    charts_pulled: int = 0
    files: List[str] = field(default_factory=list)
    error: str = ""


@dataclass
class ChartPushResult:
    """Result from push_charts()."""
    success: bool
    charts_pushed: int = 0
    errors: List[str] = field(default_factory=list)
    error: str = ""
