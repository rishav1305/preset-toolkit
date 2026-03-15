"""Jinja2 expression extraction and validation for SQL fields in YAML files.

Extracts Jinja expressions ({{ }}, {% %}, {# #}) from SQL strings,
validates syntax via balanced-braces check and optional jinja2 parsing,
and scans sync-folder YAML files for Jinja health.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

try:
    import yaml
except ImportError:
    from scripts.deps import ensure_package
    ensure_package("yaml")
    import yaml

from scripts.config import ToolkitConfig
from scripts.logger import get_logger

log = get_logger("jinja_check")

# Regex patterns for Jinja delimiters (re.DOTALL for multi-line)
_VAR_RE = re.compile(r'\{\{.*?\}\}', re.DOTALL)
_BLOCK_RE = re.compile(r'\{%.*?%\}', re.DOTALL)
_COMMENT_RE = re.compile(r'\{#.*?#\}', re.DOTALL)


@dataclass
class JinjaExpression:
    """A single Jinja expression found in a SQL field."""
    expression: str
    expr_type: str = ""  # "variable" ({{ }}), "block" ({% %}), "comment" ({# #})


@dataclass
class JinjaFinding:
    """Result of validating Jinja in a single file."""
    file_path: str
    field_name: str = ""
    expressions: List[JinjaExpression] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    valid: bool = True


@dataclass
class JinjaScanResult:
    """Result of scanning all YAML files for Jinja expressions."""
    success: bool
    files_scanned: int = 0
    files_with_jinja: int = 0
    total_expressions: int = 0
    findings: List[JinjaFinding] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    error: str = ""


def extract_jinja_expressions(sql: str) -> List[JinjaExpression]:
    """Extract all Jinja expressions ({{ }}, {% %}, {# #}) from a SQL string.

    Uses regex to find Jinja delimiters. Returns list of JinjaExpression
    with the expression text and type.
    """
    results: List[JinjaExpression] = []

    for match in _VAR_RE.finditer(sql):
        results.append(JinjaExpression(expression=match.group(), expr_type="variable"))

    for match in _BLOCK_RE.finditer(sql):
        results.append(JinjaExpression(expression=match.group(), expr_type="block"))

    for match in _COMMENT_RE.finditer(sql):
        results.append(JinjaExpression(expression=match.group(), expr_type="comment"))

    return results


def validate_jinja(sql: str) -> JinjaFinding:
    """Validate Jinja2 syntax in a SQL string.

    Checks:
    1. Balanced braces: every {{ has a matching }}, every {%% has a matching %%}
    2. Parseable: Jinja2 Environment can parse the string without error
       (falls back to balanced-braces only if jinja2 is not installed)

    Returns JinjaFinding with valid=True if all checks pass, or
    valid=False with errors listing what's wrong.
    """
    finding = JinjaFinding(file_path="", expressions=extract_jinja_expressions(sql))
    errors: List[str] = []

    # Balanced braces check
    open_var = sql.count("{{")
    close_var = sql.count("}}")
    if open_var != close_var:
        errors.append(
            f"Unbalanced variable braces: {open_var} opening '{{{{' vs "
            f"{close_var} closing '}}}}'"
        )

    open_block = sql.count("{%")
    close_block = sql.count("%}")
    if open_block != close_block:
        errors.append(
            f"Unbalanced block braces: {open_block} opening '{{% ' vs "
            f"{close_block} closing ' %}}'"
        )

    # jinja2 parse check (optional dependency)
    try:
        import jinja2
        try:
            jinja2.Environment().parse(sql)
        except jinja2.TemplateSyntaxError as exc:
            errors.append(f"Jinja2 syntax error: {exc}")
    except ImportError:
        log.debug("jinja2 not installed; skipping parse validation")

    if errors:
        finding.valid = False
        finding.errors = errors

    return finding


def _extract_sql_fields(data, prefix: str = "") -> List[tuple]:
    """Recursively extract (field_name, sql_string) pairs from parsed YAML data."""
    pairs: List[tuple] = []
    if isinstance(data, dict):
        for key, value in data.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if key == "sql" and isinstance(value, str):
                pairs.append((full_key, value))
            elif isinstance(value, (dict, list)):
                pairs.extend(_extract_sql_fields(value, full_key))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            pairs.extend(_extract_sql_fields(item, f"{prefix}[{idx}]"))
    return pairs


def scan_yaml_jinja(config: ToolkitConfig) -> JinjaScanResult:
    """Scan all YAML files in the sync folder for Jinja expressions.

    Walks <config.project_root>/<config.sync_assets_path>/ recursively,
    reads each .yaml file, extracts SQL fields, and validates Jinja
    syntax in each.

    Returns JinjaScanResult with per-file findings.
    """
    scan_dir = config.project_root / config.sync_assets_path
    result = JinjaScanResult(success=True)

    if not scan_dir.exists():
        result.error = f"Sync assets directory not found: {scan_dir}"
        result.success = False
        return result

    yaml_files = sorted(scan_dir.rglob("*.yaml"))
    result.files_scanned = len(yaml_files)

    for yaml_path in yaml_files:
        try:
            text = yaml_path.read_text(encoding="utf-8")
        except OSError as exc:
            result.errors.append(f"Could not read {yaml_path}: {exc}")
            continue

        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            result.errors.append(f"YAML parse error in {yaml_path}: {exc}")
            continue

        sql_fields = _extract_sql_fields(data)
        for field_name, sql_value in sql_fields:
            finding = validate_jinja(sql_value)
            finding.file_path = str(yaml_path)
            finding.field_name = field_name

            if finding.expressions:
                result.files_with_jinja += 1
                result.total_expressions += len(finding.expressions)
                result.findings.append(finding)

            if not finding.valid:
                result.findings.append(finding) if finding not in result.findings else None

    return result
