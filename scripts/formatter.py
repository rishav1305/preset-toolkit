"""Output formatter: render result dataclasses as table, JSON, or YAML."""
import dataclasses
import json
from typing import Any

import yaml

from scripts.chart import (
    ChartListResult, ChartInfo, ChartSQL, ChartData,
    ChartPullResult, ChartPushResult,
)
from scripts.dataset import (
    DatasetListResult, DatasetInfo, DatasetSQL, DatasetData,
    DatasetPullResult, DatasetPushResult,
)
from scripts.dashboard import DashboardListResult, DashboardInfo, DashboardPullResult
from scripts.sql import SqlResult
from scripts.sync import ChangeAction, DryRunResult, SyncResult

# ANSI color codes
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_RED = "\033[31m"
_RESET = "\033[0m"

_ACTION_COLORS = {
    ChangeAction.CREATE: _GREEN,
    ChangeAction.UPDATE: _YELLOW,
    ChangeAction.DELETE: _RED,
    ChangeAction.NO_CHANGE: _RESET,
}


def _format_table_dry_run(result: DryRunResult) -> str:
    """Render DryRunResult as a human-readable table."""
    lines = []
    lines.append(f"Validation: {'PASSED' if result.validation_passed else 'FAILED'}")
    lines.append(f"Markers:    {'PASSED' if result.markers_passed else 'FAILED'}")
    lines.append("")

    if result.changes:
        lines.append(f"{'Action':<12} {'Type':<12} Name")
        lines.append("-" * 50)
        for c in result.changes:
            color = _ACTION_COLORS.get(c.action, _RESET)
            lines.append(f"{color}{c.action.value:<12}{_RESET} {c.asset_type:<12} {c.name}")
        lines.append("")
        lines.append(f"{len(result.changes)} change(s) detected.")
    else:
        lines.append("No changes detected.")
        if result.raw_output:
            lines.append("")
            lines.append("Raw output:")
            lines.append(result.raw_output)

    if result.warnings:
        lines.append("")
        for w in result.warnings:
            lines.append(f"WARNING: {w}")

    if result.error:
        lines.append("")
        lines.append(f"ERROR: {result.error}")

    return "\n".join(lines)


def _format_table_sync(result: SyncResult) -> str:
    """Render SyncResult as a human-readable table."""
    lines = []
    lines.append(f"Success: {'YES' if result.success else 'NO'}")
    if result.steps_completed:
        lines.append("")
        lines.append("Steps completed:")
        for step in result.steps_completed:
            lines.append(f"  - {step}")
    if result.warnings:
        lines.append("")
        for w in result.warnings:
            lines.append(f"WARNING: {w}")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_chart_list(result: ChartListResult) -> str:
    """Render ChartListResult as a table."""
    lines = []
    if result.charts:
        lines.append(f"{'ID':<8} {'Name':<30} {'Type':<20} {'Dataset':<20} Modified")
        lines.append("-" * 100)
        for c in result.charts:
            lines.append(f"{c.id:<8} {c.name:<30} {c.viz_type:<20} {c.dataset_name:<20} {c.modified}")
        lines.append("")
        lines.append(f"{result.total} chart(s) found.")
    else:
        lines.append("No charts found.")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_chart_info(result: ChartInfo) -> str:
    """Render ChartInfo as key-value pairs."""
    lines = [
        f"ID:           {result.id}",
        f"Name:         {result.name}",
        f"Type:         {result.viz_type}",
        f"Dataset:      {result.dataset_name}",
    ]
    if result.query_context:
        lines.append(f"Query Context: {result.query_context[:80]}...")
    if result.params:
        lines.append(f"Params:       {result.params[:80]}...")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_chart_sql(result: ChartSQL) -> str:
    """Render ChartSQL as a SQL block."""
    if result.error:
        return f"ERROR: {result.error}"
    return result.sql


def _format_table_chart_data(result: ChartData) -> str:
    """Render ChartData as a columnar table."""
    lines = []
    if result.columns:
        header = " | ".join(f"{col:<15}" for col in result.columns)
        lines.append(header)
        lines.append("-" * len(header))
        for row in result.rows:
            line = " | ".join(f"{str(row.get(col, '')):<15}" for col in result.columns)
            lines.append(line)
        lines.append("")
        lines.append(f"{result.row_count} row(s) returned.")
    else:
        lines.append("No data returned.")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_chart_pull(result: ChartPullResult) -> str:
    """Render ChartPullResult as a summary."""
    lines = [f"Charts pulled: {result.charts_pulled}"]
    if result.files:
        lines.append("Files:")
        for f in result.files:
            lines.append(f"  - {f}")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_chart_push(result: ChartPushResult) -> str:
    """Render ChartPushResult as a summary."""
    lines = [f"Charts pushed: {result.charts_pushed}"]
    if result.errors:
        lines.append("Errors:")
        for e in result.errors:
            lines.append(f"  - {e}")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_dataset_list(result: DatasetListResult) -> str:
    """Render DatasetListResult as a table."""
    lines = []
    if result.datasets:
        lines.append(f"{'ID':<8} {'Name':<30} {'Database':<20} {'Schema':<15} Modified")
        lines.append("-" * 100)
        for d in result.datasets:
            lines.append(f"{d.id:<8} {d.name:<30} {d.database:<20} {d.schema:<15} {d.modified}")
        lines.append("")
        lines.append(f"{result.total} dataset(s) found.")
    else:
        lines.append("No datasets found.")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_dataset_info(result: DatasetInfo) -> str:
    """Render DatasetInfo as key-value pairs."""
    lines = [
        f"ID:       {result.id}",
        f"Name:     {result.name}",
        f"Database: {result.database}",
        f"Schema:   {result.schema}",
    ]
    if result.sql:
        lines.append(f"SQL:      {result.sql}")
    if result.columns:
        lines.append(f"Columns:  {len(result.columns)}")
    if result.metrics:
        lines.append(f"Metrics:  {len(result.metrics)}")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_dataset_sql(result: DatasetSQL) -> str:
    """Render DatasetSQL as a SQL block."""
    if result.error:
        return f"ERROR: {result.error}"
    return result.sql


def _format_table_dataset_data(result: DatasetData) -> str:
    """Render DatasetData as a columnar table."""
    lines = []
    if result.columns:
        header = " | ".join(f"{col:<15}" for col in result.columns)
        lines.append(header)
        lines.append("-" * len(header))
        for row in result.rows:
            line = " | ".join(f"{str(row.get(col, '')):<15}" for col in result.columns)
            lines.append(line)
        lines.append("")
        lines.append(f"{result.row_count} row(s) returned.")
    else:
        lines.append("No data returned.")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_dataset_pull(result: DatasetPullResult) -> str:
    """Render DatasetPullResult as a summary."""
    lines = [f"Datasets pulled: {result.datasets_pulled}"]
    if result.files:
        lines.append("Files:")
        for f in result.files:
            lines.append(f"  - {f}")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_dataset_push(result: DatasetPushResult) -> str:
    """Render DatasetPushResult as a summary."""
    lines = [f"Datasets pushed: {result.datasets_pushed}"]
    if result.errors:
        lines.append("Errors:")
        for e in result.errors:
            lines.append(f"  - {e}")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_sql_result(result: SqlResult) -> str:
    """Render SqlResult as a columnar table."""
    if result.error:
        return f"ERROR: {result.error}"
    lines = []
    if result.columns:
        header = " | ".join(f"{col:<15}" for col in result.columns)
        lines.append(header)
        lines.append("-" * len(header))
        for row in result.rows:
            line = " | ".join(f"{str(row.get(col, '')):<15}" for col in result.columns)
            lines.append(line)
        lines.append("")
        lines.append(f"{result.row_count} row(s) returned.")
    else:
        lines.append("No rows returned.")
    return "\n".join(lines)


def _format_table_dashboard_list(result: DashboardListResult) -> str:
    """Render DashboardListResult as a table."""
    lines = []
    if result.dashboards:
        lines.append(f"{'ID':<8} {'Name':<30} {'Status':<12} {'URL':<30} Modified")
        lines.append("-" * 100)
        for d in result.dashboards:
            lines.append(f"{d.id:<8} {d.name:<30} {d.status:<12} {d.url:<30} {d.modified}")
        lines.append("")
        lines.append(f"{result.total} dashboard(s) found.")
    else:
        lines.append("No dashboards found.")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_dashboard_info(result: DashboardInfo) -> str:
    """Render DashboardInfo as key-value pairs."""
    lines = [
        f"ID:      {result.id}",
        f"Name:    {result.name}",
        f"Status:  {result.status}",
        f"URL:     {result.url}",
        f"Slug:    {result.slug}",
        f"Charts:  {len(result.charts)}",
        f"CSS:     {len(result.css)} chars",
    ]
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _format_table_dashboard_pull(result: DashboardPullResult) -> str:
    """Render DashboardPullResult as a summary."""
    lines = [f"Dashboards pulled: {result.dashboards_pulled}"]
    if result.files:
        lines.append("Files:")
        for f in result.files:
            lines.append(f"  - {f}")
    if result.error:
        lines.append(f"ERROR: {result.error}")
    return "\n".join(lines)


def _coerce_enums(obj: Any) -> Any:
    """Recursively convert Enum instances to their plain string/value form.

    dataclasses.asdict() preserves the Enum subclass type, which causes
    PyYAML to emit python-object tags instead of plain scalars.  This
    function walks the resulting structure and replaces every Enum with
    its .value so that both json.dumps and yaml.dump produce plain strings.
    """
    from enum import Enum as _Enum

    if isinstance(obj, _Enum):
        return obj.value
    if isinstance(obj, dict):
        return {k: _coerce_enums(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce_enums(item) for item in obj]
    return obj


def _to_dict(data: Any) -> dict:
    """Convert a dataclass to a serialization-safe plain dict.

    Calls dataclasses.asdict() then walks the result with _coerce_enums()
    so that ChangeAction (and any other Enum fields) become plain strings
    rather than Python-tagged YAML objects.
    """
    return _coerce_enums(dataclasses.asdict(data))


def format_output(data: Any, fmt: str = "table") -> str:
    """Render a result dataclass as table, json, or yaml.

    Supports DryRunResult, SyncResult, and any dataclass with
    dataclasses.asdict() compatibility.

    Args:
        data: A dataclass instance to format.
        fmt: Output format — "table", "json", or "yaml".

    Returns:
        Formatted string.

    Raises:
        ValueError: If fmt is not one of the supported formats.
    """
    if fmt == "table":
        if isinstance(data, DryRunResult):
            return _format_table_dry_run(data)
        elif isinstance(data, SyncResult):
            return _format_table_sync(data)
        elif isinstance(data, ChartListResult):
            return _format_table_chart_list(data)
        elif isinstance(data, ChartInfo):
            return _format_table_chart_info(data)
        elif isinstance(data, ChartSQL):
            return _format_table_chart_sql(data)
        elif isinstance(data, ChartData):
            return _format_table_chart_data(data)
        elif isinstance(data, ChartPullResult):
            return _format_table_chart_pull(data)
        elif isinstance(data, ChartPushResult):
            return _format_table_chart_push(data)
        elif isinstance(data, DatasetListResult):
            return _format_table_dataset_list(data)
        elif isinstance(data, DatasetInfo):
            return _format_table_dataset_info(data)
        elif isinstance(data, DatasetSQL):
            return _format_table_dataset_sql(data)
        elif isinstance(data, DatasetData):
            return _format_table_dataset_data(data)
        elif isinstance(data, DatasetPullResult):
            return _format_table_dataset_pull(data)
        elif isinstance(data, DatasetPushResult):
            return _format_table_dataset_push(data)
        elif isinstance(data, SqlResult):
            return _format_table_sql_result(data)
        elif isinstance(data, DashboardListResult):
            return _format_table_dashboard_list(data)
        elif isinstance(data, DashboardInfo):
            return _format_table_dashboard_info(data)
        elif isinstance(data, DashboardPullResult):
            return _format_table_dashboard_pull(data)
        else:
            return str(dataclasses.asdict(data))
    elif fmt == "json":
        return json.dumps(_to_dict(data), indent=2)
    elif fmt == "yaml":
        return yaml.dump(_to_dict(data), default_flow_style=False, sort_keys=False)
    else:
        raise ValueError(f"Unknown format: {fmt!r}. Supported: table, json, yaml")
