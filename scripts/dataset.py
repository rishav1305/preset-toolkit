"""Dataset operations: list, info, sql, data, pull, push.

Wraps sup dataset subcommands as structured Python functions.
Each function calls run_sup() with --json and parses the output
into typed dataclasses.
"""
import json
from dataclasses import dataclass, field
from typing import List, Optional

from scripts.config import ToolkitConfig
from scripts.sync import run_sup


@dataclass
class DatasetSummary:
    """Single dataset in a list result."""
    id: int
    name: str
    database: str = ""
    schema: str = ""
    modified: str = ""


@dataclass
class DatasetListResult:
    """Result from list_datasets()."""
    success: bool
    datasets: List[DatasetSummary] = field(default_factory=list)
    total: int = 0
    error: str = ""


@dataclass
class DatasetInfo:
    """Detailed metadata for a single dataset."""
    success: bool
    id: int = 0
    name: str = ""
    database: str = ""
    schema: str = ""
    sql: str = ""
    columns: List[dict] = field(default_factory=list)
    metrics: List[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)
    error: str = ""


@dataclass
class DatasetSQL:
    """SQL definition for a dataset."""
    success: bool
    sql: str = ""
    error: str = ""


@dataclass
class DatasetData:
    """Sample data results from a dataset query."""
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[dict] = field(default_factory=list)
    row_count: int = 0
    error: str = ""


@dataclass
class DatasetPullResult:
    """Result from pull_datasets()."""
    success: bool
    datasets_pulled: int = 0
    files: List[str] = field(default_factory=list)
    error: str = ""


@dataclass
class DatasetPushResult:
    """Result from push_datasets()."""
    success: bool
    datasets_pushed: int = 0
    errors: List[str] = field(default_factory=list)
    error: str = ""


def _parse_dataset_summary(item: dict) -> DatasetSummary:
    """Parse a single dataset dict from sup JSON into DatasetSummary."""
    return DatasetSummary(
        id=item.get("id", 0),
        name=item.get("table_name", ""),
        database=item.get("database_name", ""),
        schema=item.get("schema", ""),
        modified=item.get("changed_on_utc", ""),
    )


def list_datasets(
    config: ToolkitConfig,
    search: Optional[str] = None,
    database_id: Optional[int] = None,
    mine: bool = False,
    modified_after: Optional[str] = None,
    limit: Optional[int] = None,
    order: Optional[str] = None,
    desc: bool = False,
) -> DatasetListResult:
    """List datasets with optional filtering. Uses sup dataset list --json."""
    args = ["dataset", "list", "--json"]

    if search is not None:
        args.extend(["--search", search])
    if database_id is not None:
        args.extend(["--database-id", str(database_id)])
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
        return DatasetListResult(success=False, error=r.stderr.strip())

    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return DatasetListResult(success=False, error=f"JSON parse error: {e}")

    if isinstance(data, list):
        datasets = [_parse_dataset_summary(item) for item in data]
    else:
        datasets = []

    return DatasetListResult(success=True, datasets=datasets, total=len(datasets))
