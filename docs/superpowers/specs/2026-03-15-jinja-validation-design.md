# Jinja Validation — Design Spec

**Sub-project:** 6 of 6 (sup CLI capabilities expansion)
**Date:** 2026-03-15
**Status:** Approved

---

## Goal

Provide Jinja2 syntax validation and expression extraction for SQL fields in dashboard YAML files. Catches Jinja corruption (from `yaml.dump()` or manual edits) before pushing to Preset.

## Current State

- Preset SQL fields contain Jinja2 syntax: `{{ filter_values('col') }}`, `{% if %}...{% endif %}`
- `yaml.dump()` corrupts Jinja by re-encoding curly braces — the toolkit never uses it, but edits can still break Jinja
- No automated way to validate Jinja syntax in YAML files before pushing
- The `preset-validate` skill runs dry-run + marker checks but does not check Jinja integrity
- `references/sup-cli.md` and `references/yaml-safety.md` document Jinja corruption as a known pitfall

## Architecture

### 1. New Module: `scripts/jinja_check.py`

Three public functions and two dataclasses. Uses Jinja2's own parser for validation (not regex).

```python
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

from scripts.config import ToolkitConfig


@dataclass
class JinjaExpression:
    """A single Jinja expression found in a SQL field."""
    expression: str
    expr_type: str = ""  # "variable" ({{ }}) or "block" ({%  %}) or "comment" ({# #})


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

    Regex patterns:
    - {{ ... }} -> type="variable"
    - {% ... %} -> type="block"
    - {# ... #} -> type="comment"
    """


def validate_jinja(sql: str) -> JinjaFinding:
    """Validate Jinja2 syntax in a SQL string.

    Checks:
    1. Balanced braces: every {{ has a matching }}, every {% has a matching %}
    2. Parseable: Jinja2 Environment can parse the string without error
    3. No common corruption patterns: doubled quotes around filter_values args

    Uses jinja2.Environment(undefined=jinja2.Undefined).parse() for syntax
    validation. This catches syntax errors without requiring actual variable
    values.

    Returns JinjaFinding with valid=True if all checks pass, or
    valid=False with errors listing what's wrong.
    """


def scan_yaml_jinja(config: ToolkitConfig) -> JinjaScanResult:
    """Scan all YAML files in the sync folder for Jinja expressions.

    Walks <config.project_root>/<config.sync_assets_path>/ recursively,
    reads each .yaml file, extracts SQL fields ('sql', 'query', 'metrics'),
    and validates Jinja syntax in each.

    Returns JinjaScanResult with per-file findings.
    """
```

**Implementation notes:**
- `extract_jinja_expressions` uses regex: `r'\{\{.*?\}\}'`, `r'\{%.*?%\}'`, `r'\{#.*?#\}'` with `re.DOTALL` for multi-line expressions
- `validate_jinja` uses `jinja2.Environment().parse(sql)` to check syntax. If `jinja2` is not installed, falls back to regex-only validation (balanced braces check)
- `scan_yaml_jinja` uses `yaml.safe_load()` to read each file, then inspects string fields that commonly contain SQL/Jinja: top-level `sql` key and any nested `sql` keys in the YAML structure

### 2. Jinja2 Dependency

`jinja2` is an optional dependency for full syntax validation. If not installed:
- `extract_jinja_expressions` works fully (regex-only)
- `validate_jinja` falls back to balanced-braces check only (no parse validation)
- `scan_yaml_jinja` works with reduced validation

This follows the existing pattern in `scripts/deps.py` where missing packages degrade gracefully.

### 3. Formatter Extension

Extend `scripts/formatter.py` to handle `JinjaScanResult`:

- Import `JinjaScanResult` from `scripts.jinja_check`
- Add `_format_table_jinja_scan(result: JinjaScanResult) -> str`: summary table showing files scanned, files with Jinja, total expressions, and any errors/warnings per file
- Add `isinstance(data, JinjaScanResult)` branch to `format_output()` dispatch chain

### 4. New Skill: `skills/preset-jinja/SKILL.md`

Routes natural language Jinja operations:
- "check jinja", "validate jinja" → `scan_yaml_jinja(config)`
- "scan for jinja errors" → `scan_yaml_jinja(config)`
- "is the jinja syntax valid?" → `scan_yaml_jinja(config)`

The router skill (`skills/preset/SKILL.md`) will be updated to route Jinja-related intents to this skill.

## What We're NOT Doing

- **Not rendering Jinja templates with actual values** — validation only, no execution
- **Not modifying YAML files** — read-only scanning
- **Not requiring jinja2 as a hard dependency** — graceful fallback to regex-only
- **Not replacing the existing YAML safety patterns** — this adds validation, doesn't change how YAML is written

## Impact on Existing Code

| File | Change | Breaking? |
|------|--------|-----------|
| `scripts/jinja_check.py` | New file | No |
| `scripts/formatter.py` | Add table formatter for JinjaScanResult | No |
| `skills/preset-jinja/SKILL.md` | New skill | No |
| `skills/preset/SKILL.md` | Add jinja routing | No |
| `tests/test_jinja_check.py` | New file | No |
| `tests/test_formatter.py` | Add jinja formatter tests | No |

## Testing Strategy

- **extract_jinja_expressions tests** — SQL with variables, blocks, comments, mixed, none, multi-line
- **validate_jinja tests** — valid SQL, broken braces, corrupted quotes, empty string, no Jinja (should pass)
- **scan_yaml_jinja tests** — create temp sync folder with YAML files containing valid/invalid Jinja, verify findings
- **Fallback tests** — mock jinja2 as unavailable, verify regex-only validation works
- **Formatter tests** — table/json/yaml rendering for JinjaScanResult
- **Integration boundary** — all tests use temp directories, no live Preset calls

## Dependencies

- `jinja2` (optional) — for syntax validation via `Environment().parse()`
- `re` (stdlib) — for expression extraction
- `yaml` — for reading YAML files (already a project dependency)
- `pathlib` (stdlib) — for file scanning
- `dataclasses` (stdlib)
