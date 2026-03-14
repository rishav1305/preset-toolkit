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
