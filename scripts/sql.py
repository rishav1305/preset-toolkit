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


def resolve_database_id(config: ToolkitConfig) -> Optional[int]:
    """Scan sync folder's databases/ dir for the first database YAML and extract its ID."""
    db_dir = config.project_root / config.sync_assets_path / "databases"
    if not db_dir.is_dir():
        return None
    for db_file in sorted(db_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(db_file.read_text())
        except (yaml.YAMLError, OSError):
            continue
        if isinstance(data, dict) and "id" in data:
            return int(data["id"])
    return None
