# Dry Run + Output Formats — Design Spec

**Sub-project:** 1 of 6 (sup CLI capabilities expansion)
**Date:** 2026-03-14
**Status:** Approved

---

## Goal

Make dry-run output structured and machine-readable so the push approval gate shows a clean diff table instead of raw CLI output, and external tools/CI can consume results as JSON or YAML.

## Current State

- `sync.py:validate()` runs two sup commands sequentially: (1) `sup sync validate <folder>` for structural validation, then (2) `sup sync run <folder> --push-only --dry-run --force` for a dry-run push simulation. Both outputs are checked only via return code — stdout is discarded.
- `sync.py:push(dry_run=True)` short-circuits after validation with a flat string message
- `SyncResult` stores steps as `List[str]` — no typed diff objects
- `push()` calls `validate()` and does `result.steps_completed.extend(val.steps_completed)` — any new return type must preserve this field
- The push skill (Step 5) describes an approval gate but has no structured data to render

## Architecture

Three deliverables, all additive (no breaking changes to existing APIs):

### 1. Structured Result Types (`scripts/sync.py`)

```python
class ChangeAction(str, Enum):
    """Valid actions for an asset change."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    NO_CHANGE = "no_change"

@dataclass
class AssetChange:
    """A single asset that would be created, updated, deleted, or unchanged."""
    asset_type: str         # "chart", "dataset", "dashboard"
    name: str
    action: ChangeAction
    details: str = ""       # optional human-readable context

@dataclass
class DryRunResult:
    """Structured output from validate() with parsed dry-run diff."""
    success: bool
    changes: List[AssetChange]
    validation_passed: bool     # True if `sup sync validate` passed
    markers_passed: bool        # True if all markers found; False if check failed; True if no markers file exists
    raw_output: str             # original sup dry-run stdout preserved
    steps_completed: List[str] = field(default_factory=list)  # backward compat with SyncResult
    warnings: List[str] = field(default_factory=list)
    error: str = ""
```

`DryRunResult` includes `steps_completed` for backward compatibility — `push()` does `result.steps_completed.extend(val.steps_completed)` and this must continue to work.

**Population logic for boolean fields:**
- `validation_passed` is set to `True` after `sup sync validate` returns 0. If validate fails, the function early-returns with `validation_passed=False`, `markers_passed=False`.
- `markers_passed` is set to `True` after all markers are confirmed present (or if no markers file exists). If markers fail, early-return with `validation_passed=True`, `markers_passed=False`.
- `success` is `True` only when all three checks pass (validate + markers + dry-run).

`push()` continues to call `validate()` internally. The approval gate in the push skill uses `DryRunResult.changes` to render a table.

### 2. Output Formatter (`scripts/formatter.py`)

New module with a single public function:

```python
def format_output(data, fmt: str = "table") -> str:
    """Render a result dataclass as table, json, or yaml.

    Supports DryRunResult, SyncResult, and any dataclass with
    asdict() compatibility.
    """
```

**Formats:**
- `table` — Human-readable, ANSI color-coded (green=create, yellow=update, red=delete). Default for terminal use.
- `json` — Machine-readable dict. Uses `dataclasses.asdict()`.
- `yaml` — YAML serialization via `yaml.dump()` (safe for output — the "never yaml.dump" rule applies to editing sync YAML files, not to rendering output).

The formatter is stateless and has no side effects. It takes a dataclass, returns a string.

### 3. Enhanced `validate()` Parse Logic

`validate()` gains a `_parse_dry_run_output(stdout: str) -> List[AssetChange]` helper that parses the stdout from the **dry-run push command** (`sup sync run <folder> --push-only --dry-run --force`) — not from `sup sync validate`, which only checks structural validity.

**Parsing strategy:** sup's output format is line-based. The parser looks for patterns like:
- `Creating <type> "<name>"` → action=ChangeAction.CREATE
- `Updating <type> "<name>"` → action=ChangeAction.UPDATE
- `Deleting <type> "<name>"` → action=ChangeAction.DELETE
- Lines that don't match are ignored (version info, progress bars, etc.)

If parsing produces zero results (format changed or unrecognized), `DryRunResult.changes` is empty and `raw_output` is still available as fallback. The approval gate shows raw output when no structured changes are parsed.

**Note:** The parser is tested against sup CLI v0.x output format. If sup changes its output format in a future version, the parser gracefully degrades to empty `changes` with `raw_output` preserved.

## What We're NOT Doing

- **Not adding `sup sync create`** — scaffolding is handled by the setup skill
- **Not changing the push flow** — dry-run is already integrated; we're making output structured
- **Not adding a standalone dry-run skill** — validate skill + push `--dry-run` flag is sufficient
- **Not adding `--porcelain` flag to sup calls** — sup doesn't support it; we parse regular stdout
- **Not adding local fingerprint enrichment** — comparing fingerprint maps against sup's diff is useful but adds complexity; defer to a future sub-project if needed

## Impact on Existing Code

| File | Change | Breaking? |
|------|--------|-----------|
| `scripts/sync.py` | Add `ChangeAction`, `AssetChange`, `DryRunResult`, `_parse_dry_run_output()`. Change `validate()` return type. `push()` updated to use `DryRunResult` fields. | No — `DryRunResult` preserves `.success`, `.error`, `.steps_completed` fields from `SyncResult` |
| `scripts/formatter.py` | New file | No |
| `skills/preset-sync-push/SKILL.md` | Update Step 5 to reference structured output | No |
| `skills/preset-validate/SKILL.md` | Update to mention output format options | No |
| `tests/test_sync.py` | Add tests for parsing and formatting | No |

## Testing Strategy

- **Unit tests for `_parse_dry_run_output()`** — feed known sup output strings, verify `AssetChange` list with correct `ChangeAction` values
- **Unit tests for `format_output()`** — verify table/json/yaml rendering for each result type
- **Integration test** — `validate()` with a mock sup binary returns a properly populated `DryRunResult`
- **Backward compat test** — `push()` calling `validate()` successfully extends `steps_completed` from the returned `DryRunResult`
- **Partial failure tests** — validate passes but markers fail → `validation_passed=True`, `markers_passed=False`; validate fails → both False
- **Edge cases** — empty sup output, unrecognized format, mixed create/update/delete

## Dependencies

No new dependencies. Uses only:
- `dataclasses` (stdlib)
- `json` (stdlib)
- `yaml` (already a dependency — PyYAML)
