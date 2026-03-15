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


def execute_sql(
    config: ToolkitConfig,
    query: str,
    database_id: Optional[int] = None,
    limit: Optional[int] = None,
) -> SqlResult:
    """Execute a SQL query against a Preset database. Uses sup sql --json."""
    args = ["sql", query, "--json"]
    resolved_db_id = database_id if database_id is not None else resolve_database_id(config)
    if resolved_db_id is not None:
        args.extend(["--database-id", str(resolved_db_id)])
    if limit is not None:
        args.extend(["--limit", str(limit)])
    r = run_sup(args)
    if r.returncode != 0:
        return SqlResult(success=False, error=r.stderr.strip())
    try:
        data = json.loads(r.stdout)
    except (json.JSONDecodeError, ValueError) as e:
        return SqlResult(success=False, error=f"JSON parse error: {e}")
    return SqlResult(
        success=True,
        columns=data.get("columns", []),
        rows=data.get("data", []),
        row_count=data.get("rowcount", 0),
    )
