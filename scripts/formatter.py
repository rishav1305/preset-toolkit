"""Output formatter: render result dataclasses as table, JSON, or YAML."""
import dataclasses
import json
from typing import Any

import yaml

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
        else:
            return str(dataclasses.asdict(data))
    elif fmt == "json":
        return json.dumps(_to_dict(data), indent=2)
    elif fmt == "yaml":
        return yaml.dump(_to_dict(data), default_flow_style=False, sort_keys=False)
    else:
        raise ValueError(f"Unknown format: {fmt!r}. Supported: table, json, yaml")
