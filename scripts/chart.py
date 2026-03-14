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


def _parse_chart_summary(item: dict) -> ChartSummary:
    """Parse a single chart dict from sup JSON into ChartSummary."""
    return ChartSummary(
        id=item.get("id", 0),
        name=item.get("slice_name", ""),
        viz_type=item.get("viz_type", ""),
        dataset_name=item.get("datasource_name_text", ""),
        modified=item.get("changed_on_utc", ""),
    )


def list_charts(
    config: ToolkitConfig,
    search: Optional[str] = None,
    dashboard_id: Optional[int] = None,
    viz_type: Optional[str] = None,
    dataset_id: Optional[int] = None,
    mine: bool = False,
    modified_after: Optional[str] = None,
    limit: Optional[int] = None,
    order: Optional[str] = None,
    desc: bool = False,
) -> ChartListResult:
    """List charts with optional filtering. Uses sup chart list --json."""
    args = ["chart", "list", "--json"]

    if search is not None:
        args.extend(["--search", search])
    if dashboard_id is not None:
        args.extend(["--dashboard-id", str(dashboard_id)])
    if viz_type is not None:
        args.extend(["--viz-type", viz_type])
    if dataset_id is not None:
        args.extend(["--dataset-id", str(dataset_id)])
    if mine:
        args.append("--mine")
    if modified_after is not None:
        args.extend(["--modified-after", modified_after])
    if limit is not None:
        args.extend(["--limit", str(limit)])
    if order is not None:
        args.extend(["--order", order])
    if desc:
        args.append("--desc")

    r = run_sup(args)
    if r.returncode != 0:
        return ChartListResult(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return ChartListResult(success=False, error=f"JSON parse error: {e}")

    if isinstance(data, list):
        charts = [_parse_chart_summary(item) for item in data]
    else:
        charts = []

    return ChartListResult(success=True, charts=charts, total=len(charts))


def get_chart_info(
    config: ToolkitConfig,
    chart_id: int,
) -> ChartInfo:
    """Get detailed metadata for a single chart. Uses sup chart info --json."""
    args = ["chart", "info", str(chart_id), "--json"]

    r = run_sup(args)
    if r.returncode != 0:
        return ChartInfo(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return ChartInfo(success=False, error=f"JSON parse error: {e}")

    return ChartInfo(
        success=True,
        id=data.get("id", 0),
        name=data.get("slice_name", ""),
        viz_type=data.get("viz_type", ""),
        dataset_name=data.get("datasource_name_text", ""),
        query_context=data.get("query_context", ""),
        params=data.get("params", ""),
        raw=data,
    )


def get_chart_sql(
    config: ToolkitConfig,
    chart_id: int,
) -> ChartSQL:
    """Get compiled SQL for a chart. Uses sup chart sql --json."""
    args = ["chart", "sql", str(chart_id), "--json"]

    r = run_sup(args)
    if r.returncode != 0:
        return ChartSQL(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return ChartSQL(success=False, error=f"JSON parse error: {e}")

    return ChartSQL(
        success=True,
        sql=data.get("result", ""),
    )
