"""SQL execution: run arbitrary queries against Preset databases.

Wraps sup sql command as a structured Python function.
Calls run_sup() with --json and parses the output into a typed dataclass.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

from scripts.config import ToolkitConfig
from scripts.sync import run_sup


@dataclass
class SqlResult:
    """Result of executing a SQL query."""
    success: bool
    columns: List[str] = field(default_factory=list)
    rows: List[dict] = field(default_factory=list)
    row_count: int = 0
    error: str = ""
