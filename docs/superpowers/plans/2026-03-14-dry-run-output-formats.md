# Dry Run + Output Formats Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make dry-run output structured and machine-readable with table/JSON/YAML formatting.

**Architecture:** Add `ChangeAction` enum, `AssetChange` and `DryRunResult` dataclasses to `scripts/sync.py`. Add `_parse_dry_run_output()` to parse sup CLI stdout into structured changes. Create `scripts/formatter.py` for rendering results. Update `validate()` return type while preserving backward compatibility for `push()`.

**Tech Stack:** Python dataclasses, enum (stdlib), json (stdlib), PyYAML (existing dep)

**Spec:** `docs/superpowers/specs/2026-03-14-dry-run-output-formats-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/sync.py` | Modify | Add `ChangeAction`, `AssetChange`, `DryRunResult`, `_parse_dry_run_output()`. Update `validate()` return type. |
| `scripts/formatter.py` | Create | `format_output(data, fmt)` → table/json/yaml string |
| `tests/test_sync.py` | Modify | Add tests for new types, parser, validate return type, push compat |
| `tests/test_formatter.py` | Create | Tests for format_output across all formats |
| `skills/preset-validate/SKILL.md` | Modify | Document `DryRunResult` in Python API section |
| `skills/preset-sync-push/SKILL.md` | Modify | Reference structured output in Step 5 |

---

## Chunk 1: Core Types and Parser

### Task 1: ChangeAction Enum and AssetChange Dataclass

**Files:**
- Modify: `scripts/sync.py:1-10` (imports) and after line 49 (after `SyncResult`)
- Test: `tests/test_sync.py`

- [ ] **Step 1: Write failing tests for ChangeAction and AssetChange**

Add to `tests/test_sync.py`:

```python
from scripts.sync import ChangeAction, AssetChange


def test_change_action_values():
    """ChangeAction enum has expected string values."""
    assert ChangeAction.CREATE == "create"
    assert ChangeAction.UPDATE == "update"
    assert ChangeAction.DELETE == "delete"
    assert ChangeAction.NO_CHANGE == "no_change"


def test_change_action_is_string():
    """ChangeAction values work as plain strings."""
    assert isinstance(ChangeAction.CREATE, str)
    assert f"Action: {ChangeAction.CREATE}" == "Action: create"


def test_asset_change_creation():
    """AssetChange dataclass holds structured change info."""
    change = AssetChange(
        asset_type="chart",
        name="Revenue Chart",
        action=ChangeAction.CREATE,
    )
    assert change.asset_type == "chart"
    assert change.name == "Revenue Chart"
    assert change.action == ChangeAction.CREATE
    assert change.details == ""


def test_asset_change_with_details():
    """AssetChange accepts optional details."""
    change = AssetChange(
        asset_type="dataset",
        name="Main_Dataset",
        action=ChangeAction.UPDATE,
        details="SQL query modified",
    )
    assert change.details == "SQL query modified"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py::test_change_action_values tests/test_sync.py::test_change_action_is_string tests/test_sync.py::test_asset_change_creation tests/test_sync.py::test_asset_change_with_details -v`
Expected: FAIL with `ImportError: cannot import name 'ChangeAction'`

- [ ] **Step 3: Implement ChangeAction and AssetChange**

In `scripts/sync.py`, add `Enum` to imports at the top (line 1 area):

```python
from enum import Enum
```

Then add after the `SyncResult` dataclass (after line 49):

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py::test_change_action_values tests/test_sync.py::test_change_action_is_string tests/test_sync.py::test_asset_change_creation tests/test_sync.py::test_asset_change_with_details -v`
Expected: 4 PASSED

- [ ] **Step 5: Run all existing tests to verify no regressions**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py -v`
Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/sync.py tests/test_sync.py
git commit -m "feat(sync): add ChangeAction enum and AssetChange dataclass"
```

---

### Task 2: DryRunResult Dataclass

**Files:**
- Modify: `scripts/sync.py` (after `AssetChange`)
- Test: `tests/test_sync.py`

- [ ] **Step 1: Write failing tests for DryRunResult**

Add to `tests/test_sync.py`:

```python
from scripts.sync import DryRunResult


def test_dry_run_result_creation():
    """DryRunResult holds structured validate output."""
    result = DryRunResult(
        success=True,
        changes=[],
        validation_passed=True,
        markers_passed=True,
        raw_output="some sup output",
    )
    assert result.success is True
    assert result.changes == []
    assert result.validation_passed is True
    assert result.markers_passed is True
    assert result.raw_output == "some sup output"
    assert result.steps_completed == []
    assert result.warnings == []
    assert result.error == ""


def test_dry_run_result_with_changes():
    """DryRunResult holds a list of AssetChange objects."""
    changes = [
        AssetChange("chart", "Revenue", ChangeAction.UPDATE),
        AssetChange("dataset", "Main", ChangeAction.NO_CHANGE),
    ]
    result = DryRunResult(
        success=True,
        changes=changes,
        validation_passed=True,
        markers_passed=True,
        raw_output="",
    )
    assert len(result.changes) == 2
    assert result.changes[0].action == ChangeAction.UPDATE


def test_dry_run_result_has_steps_completed():
    """DryRunResult preserves steps_completed for backward compat with SyncResult."""
    result = DryRunResult(
        success=True,
        changes=[],
        validation_passed=True,
        markers_passed=True,
        raw_output="",
        steps_completed=["validate", "markers: all present", "dry-run"],
    )
    assert "validate" in result.steps_completed
    assert len(result.steps_completed) == 3


def test_dry_run_result_partial_failure():
    """DryRunResult captures partial failure state."""
    result = DryRunResult(
        success=False,
        changes=[],
        validation_passed=True,
        markers_passed=False,
        raw_output="",
        error="Missing markers in ds.yaml: revenue_total",
    )
    assert result.success is False
    assert result.validation_passed is True
    assert result.markers_passed is False
    assert "Missing markers" in result.error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py::test_dry_run_result_creation tests/test_sync.py::test_dry_run_result_with_changes tests/test_sync.py::test_dry_run_result_has_steps_completed tests/test_sync.py::test_dry_run_result_partial_failure -v`
Expected: FAIL with `ImportError: cannot import name 'DryRunResult'`

- [ ] **Step 3: Implement DryRunResult**

In `scripts/sync.py`, add after `AssetChange`:

```python
@dataclass
class DryRunResult:
    """Structured output from validate() with parsed dry-run diff."""
    success: bool
    changes: List[AssetChange]
    validation_passed: bool
    markers_passed: bool
    raw_output: str
    steps_completed: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: str = ""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py::test_dry_run_result_creation tests/test_sync.py::test_dry_run_result_with_changes tests/test_sync.py::test_dry_run_result_has_steps_completed tests/test_sync.py::test_dry_run_result_partial_failure -v`
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```bash
git add scripts/sync.py tests/test_sync.py
git commit -m "feat(sync): add DryRunResult dataclass with backward-compat fields"
```

---

### Task 3: _parse_dry_run_output() Parser

**Files:**
- Modify: `scripts/sync.py` (add function after DryRunResult)
- Test: `tests/test_sync.py`

- [ ] **Step 1: Write failing tests for the parser**

Add to `tests/test_sync.py`:

```python
from scripts.sync import _parse_dry_run_output


def test_parse_creating_chart():
    """Parser extracts 'Creating chart' lines."""
    output = 'Creating chart "Revenue Overview"'
    changes = _parse_dry_run_output(output)
    assert len(changes) == 1
    assert changes[0].asset_type == "chart"
    assert changes[0].name == "Revenue Overview"
    assert changes[0].action == ChangeAction.CREATE


def test_parse_updating_dataset():
    """Parser extracts 'Updating dataset' lines."""
    output = 'Updating dataset "Main_Dataset"'
    changes = _parse_dry_run_output(output)
    assert len(changes) == 1
    assert changes[0].asset_type == "dataset"
    assert changes[0].name == "Main_Dataset"
    assert changes[0].action == ChangeAction.UPDATE


def test_parse_deleting_dashboard():
    """Parser extracts 'Deleting dashboard' lines."""
    output = 'Deleting dashboard "Old Dashboard"'
    changes = _parse_dry_run_output(output)
    assert len(changes) == 1
    assert changes[0].asset_type == "dashboard"
    assert changes[0].action == ChangeAction.DELETE


def test_parse_mixed_output():
    """Parser handles mixed create/update/delete in one output."""
    output = """sup sync v0.5.0
Validating sync folder...
Creating chart "New Chart"
Updating dataset "Main_Dataset"
Updating chart "Revenue Overview"
Deleting chart "Old Chart"
Done. 4 changes detected."""
    changes = _parse_dry_run_output(output)
    assert len(changes) == 4
    actions = [c.action for c in changes]
    assert actions.count(ChangeAction.CREATE) == 1
    assert actions.count(ChangeAction.UPDATE) == 2
    assert actions.count(ChangeAction.DELETE) == 1


def test_parse_empty_output():
    """Parser returns empty list for empty output."""
    assert _parse_dry_run_output("") == []


def test_parse_no_matching_lines():
    """Parser returns empty list when no lines match the pattern."""
    output = """sup sync v0.5.0
Validating sync folder...
All assets up to date.
Done."""
    assert _parse_dry_run_output(output) == []


def test_parse_case_insensitive():
    """Parser handles case variations in sup output."""
    output = 'creating chart "Test"'
    changes = _parse_dry_run_output(output)
    assert len(changes) == 1
    assert changes[0].action == ChangeAction.CREATE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py::test_parse_creating_chart tests/test_sync.py::test_parse_updating_dataset tests/test_sync.py::test_parse_deleting_dashboard tests/test_sync.py::test_parse_mixed_output tests/test_sync.py::test_parse_empty_output tests/test_sync.py::test_parse_no_matching_lines tests/test_sync.py::test_parse_case_insensitive -v`
Expected: FAIL with `ImportError: cannot import name '_parse_dry_run_output'`

- [ ] **Step 3: Implement _parse_dry_run_output**

In `scripts/sync.py`, add `re` to imports at the top:

```python
import re
```

Add after `DryRunResult`:

```python
# Pattern: "Creating|Updating|Deleting <type> "<name>""
_DRY_RUN_PATTERN = re.compile(
    r"(creating|updating|deleting)\s+(chart|dataset|dashboard)\s+\"([^\"]+)\"",
    re.IGNORECASE,
)

_ACTION_MAP = {
    "creating": ChangeAction.CREATE,
    "updating": ChangeAction.UPDATE,
    "deleting": ChangeAction.DELETE,
}


def _parse_dry_run_output(stdout: str) -> List[AssetChange]:
    """Parse sup CLI dry-run stdout into structured AssetChange objects.

    Looks for lines matching: Creating|Updating|Deleting <type> "<name>"
    Returns empty list if no lines match (graceful degradation).
    """
    changes = []
    for line in stdout.splitlines():
        match = _DRY_RUN_PATTERN.search(line)
        if match:
            action_str, asset_type, name = match.groups()
            changes.append(AssetChange(
                asset_type=asset_type.lower(),
                name=name,
                action=_ACTION_MAP[action_str.lower()],
            ))
    return changes
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py::test_parse_creating_chart tests/test_sync.py::test_parse_updating_dataset tests/test_sync.py::test_parse_deleting_dashboard tests/test_sync.py::test_parse_mixed_output tests/test_sync.py::test_parse_empty_output tests/test_sync.py::test_parse_no_matching_lines tests/test_sync.py::test_parse_case_insensitive -v`
Expected: 7 PASSED

- [ ] **Step 5: Run all existing sync tests**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/sync.py tests/test_sync.py
git commit -m "feat(sync): add _parse_dry_run_output parser for sup CLI stdout"
```

---

## Chunk 2: validate() Enhancement and Formatter

### Task 4: Update validate() to Return DryRunResult

**Files:**
- Modify: `scripts/sync.py:166-202` (the `validate()` function)
- Test: `tests/test_sync.py`

**Context:** The current `validate()` function (lines 166-202 of `scripts/sync.py`) returns `SyncResult`. It runs three sequential checks: (1) `sup sync validate`, (2) marker check, (3) `sup sync run --dry-run`. Each can early-return on failure. We change the return type to `DryRunResult` while preserving `steps_completed` population for backward compatibility with `push()`.

- [ ] **Step 1: Write failing tests for enhanced validate()**

Add to `tests/test_sync.py`:

```python
def test_validate_returns_dry_run_result(tmp_path):
    """validate() now returns DryRunResult instead of SyncResult."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("test_marker\n")
    ds_dir = tmp_path / "sync" / "assets" / "datasets" / "db"
    ds_dir.mkdir(parents=True)
    import yaml as _yaml
    with open(ds_dir / "ds.yaml", "w") as f:
        _yaml.safe_dump({"sql": "SELECT test_marker FROM t"}, f)

    dry_run_output = 'Updating chart "Revenue Overview"\nUpdating dataset "Main_Dataset"'
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            # First call: sup sync validate (success)
            # Second call: sup sync run --dry-run (success with output)
            validate_result = MagicMock(returncode=0, stdout="", stderr="")
            dry_run_result_mock = MagicMock(returncode=0, stdout=dry_run_output, stderr="")
            mock_run.side_effect = [validate_result, dry_run_result_mock]
            result = validate(cfg)

    assert isinstance(result, DryRunResult)
    assert result.success is True
    assert result.validation_passed is True
    assert result.markers_passed is True
    assert len(result.changes) == 2
    assert result.raw_output == dry_run_output
    assert "validate" in result.steps_completed
    assert "dry-run" in result.steps_completed


def test_validate_sup_validate_fails(tmp_path):
    """validate() returns validation_passed=False when sup validate fails."""
    cfg = _make_config(tmp_path)
    (tmp_path / "sync").mkdir(parents=True)
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="YAML error")
            result = validate(cfg)

    assert isinstance(result, DryRunResult)
    assert result.success is False
    assert result.validation_passed is False
    assert result.markers_passed is False
    assert result.changes == []


def test_validate_markers_fail(tmp_path):
    """validate() returns markers_passed=False when markers are missing."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("required_marker\n")
    ds_dir = tmp_path / "sync" / "assets" / "datasets" / "db"
    ds_dir.mkdir(parents=True)
    import yaml as _yaml
    with open(ds_dir / "ds.yaml", "w") as f:
        _yaml.safe_dump({"sql": "SELECT something_else FROM t"}, f)

    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = validate(cfg)

    assert isinstance(result, DryRunResult)
    assert result.success is False
    assert result.validation_passed is True
    assert result.markers_passed is False
    assert "Missing markers" in result.error


def test_validate_dry_run_command_fails(tmp_path):
    """validate() handles dry-run command failure after validation and markers pass."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("")
    (tmp_path / "sync").mkdir(parents=True)
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            # First call: sup sync validate (success)
            # Second call: sup sync run --dry-run (failure)
            validate_ok = MagicMock(returncode=0, stdout="", stderr="")
            dry_run_fail = MagicMock(returncode=1, stdout="", stderr="dry-run error")
            mock_run.side_effect = [validate_ok, dry_run_fail]
            result = validate(cfg)

    assert isinstance(result, DryRunResult)
    assert result.success is False
    assert result.validation_passed is True
    assert result.markers_passed is True
    assert "Dry-run failed" in result.error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py::test_validate_returns_dry_run_result tests/test_sync.py::test_validate_sup_validate_fails tests/test_sync.py::test_validate_markers_fail tests/test_sync.py::test_validate_dry_run_command_fails -v`
Expected: FAIL (validate returns SyncResult, not DryRunResult)

- [ ] **Step 3: Rewrite validate() to return DryRunResult**

Replace the entire `validate()` function in `scripts/sync.py` (lines 166-202) with:

```python
def validate(config: ToolkitConfig) -> DryRunResult:
    """Validate sync folder via sup sync validate + check markers + dry-run.

    Returns DryRunResult with structured changes from dry-run output.
    Preserves steps_completed for backward compatibility with push().
    """
    t = get_telemetry(config._path)
    result = DryRunResult(
        success=False,
        changes=[],
        validation_passed=False,
        markers_passed=False,
        raw_output="",
    )
    sync_folder = config.sync_folder

    with t.timed("validate"):
        # Step 1: sup sync validate
        r = _run_sup(["sync", "validate", sync_folder])
        if r.returncode != 0:
            result.error = f"Validation failed: {sanitize(r.stderr)}"
            t.track_error("validate", "sup_validate_failed", sanitize(r.stderr))
            return result
        result.validation_passed = True
        result.steps_completed.append("validate")

        # Step 2: Marker check
        markers_file = Path(config.get("validation.markers_file", ".preset-toolkit/markers.txt"))
        if markers_file.exists():
            assets = Path(sync_folder) / "assets"
            dataset_yamls = list((assets / "datasets").rglob("*.yaml")) if (assets / "datasets").exists() else []
            for ds in dataset_yamls:
                mr = check_markers(ds, markers_file)
                if not mr.all_present:
                    result.error = f"Missing markers in {ds.name}: {', '.join(mr.missing)}"
                    t.track_error("validate", "missing_markers", result.error)
                    return result
            result.steps_completed.append("markers: all present")
        result.markers_passed = True

        # Step 3: Dry-run push
        r = _run_sup(["sync", "run", sync_folder, "--push-only", "--dry-run", "--force"])
        if r.returncode != 0:
            result.error = f"Dry-run failed: {sanitize(r.stderr)}"
            t.track_error("validate", "dry_run_failed", sanitize(r.stderr))
            return result
        result.raw_output = r.stdout
        result.changes = _parse_dry_run_output(r.stdout)
        result.steps_completed.append("dry-run")

        result.success = True
    return result
```

- [ ] **Step 4: Run new tests to verify they pass**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py::test_validate_returns_dry_run_result tests/test_sync.py::test_validate_sup_validate_fails tests/test_sync.py::test_validate_markers_fail tests/test_sync.py::test_validate_dry_run_command_fails -v`
Expected: 4 PASSED

- [ ] **Step 5: Fix existing test mocks for new validate() behavior**

The rewritten `validate()` now reads `r.stdout` to parse dry-run output. Existing mocks that use `MagicMock(returncode=0)` without `stdout`/`stderr` will crash because `MagicMock().stdout.splitlines()` raises `AttributeError`. Update **both** existing tests:

Update `test_validate_success` (line 120) — add `stdout=""`, `stderr=""`:

```python
def test_validate_success(tmp_path):
    """validate() should succeed when markers pass."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("test_marker\n")
    ds_dir = tmp_path / "sync" / "assets" / "datasets" / "db"
    ds_dir.mkdir(parents=True)
    import yaml as _yaml
    with open(ds_dir / "ds.yaml", "w") as f:
        _yaml.safe_dump({"sql": "SELECT test_marker FROM t"}, f)
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = validate(cfg)
            assert result.success is True
            assert "markers: all present" in result.steps_completed
```

Update `test_push_dry_run` (line 138) — add `stdout=""`, `stderr=""`:

```python
def test_push_dry_run(tmp_path):
    """push(dry_run=True) should validate but not actually push."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("")
    (tmp_path / "sync").mkdir(parents=True)
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = push(cfg, dry_run=True)
            assert result.success is True
            assert any("dry-run" in s for s in result.steps_completed)
```

- [ ] **Step 6: Run ALL sync tests**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/sync.py tests/test_sync.py
git commit -m "feat(sync): validate() now returns DryRunResult with parsed changes"
```

---

### Task 5: Verify push() Backward Compatibility

**Files:**
- Test: `tests/test_sync.py`

**Context:** `push()` at line 220 of `scripts/sync.py` does `result.steps_completed.extend(val.steps_completed)`. Since `DryRunResult` has `steps_completed`, this should work without code changes. We verify with a dedicated test.

- [ ] **Step 1: Write backward compat test**

Add to `tests/test_sync.py`:

```python
def test_push_extends_steps_from_dry_run_result(tmp_path):
    """push() correctly extends steps_completed from DryRunResult returned by validate()."""
    cfg = _make_config(tmp_path)
    markers = tmp_path / ".preset-toolkit" / "markers.txt"
    markers.write_text("")
    sync_dir = tmp_path / "sync" / "assets"
    sync_dir.mkdir(parents=True)
    with patch("scripts.sync._ensure_sup", return_value="/usr/bin/sup"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            result = push(cfg, dry_run=True)
            assert result.success is True
            # validate steps should be in push result
            assert "validate" in result.steps_completed
            assert any("dry-run" in s for s in result.steps_completed)
```

- [ ] **Step 2: Run test**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py::test_push_extends_steps_from_dry_run_result -v`
Expected: PASS (no code changes needed — DryRunResult has steps_completed)

- [ ] **Step 3: Also verify existing push dry-run test**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_sync.py::test_push_dry_run -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_sync.py
git commit -m "test(sync): add backward compat test for push() with DryRunResult"
```

---

### Task 6: Output Formatter

**Files:**
- Create: `scripts/formatter.py`
- Create: `tests/test_formatter.py`

- [ ] **Step 1: Write failing tests for format_output**

Create `tests/test_formatter.py`:

```python
"""Tests for output formatter module."""
import json

import pytest
import yaml

from scripts.formatter import format_output
from scripts.sync import AssetChange, ChangeAction, DryRunResult, SyncResult


# ── Table format ────────────────────────────────────────────────────


def test_format_dry_run_result_table():
    """Table format renders changes as human-readable lines."""
    result = DryRunResult(
        success=True,
        changes=[
            AssetChange("chart", "Revenue Overview", ChangeAction.CREATE),
            AssetChange("dataset", "Main_Dataset", ChangeAction.UPDATE),
            AssetChange("chart", "Old Chart", ChangeAction.DELETE),
        ],
        validation_passed=True,
        markers_passed=True,
        raw_output="",
    )
    output = format_output(result, fmt="table")
    assert "Revenue Overview" in output
    assert "Main_Dataset" in output
    assert "Old Chart" in output
    assert "create" in output.lower()
    assert "update" in output.lower()
    assert "delete" in output.lower()


def test_format_dry_run_result_table_no_changes():
    """Table format shows 'no changes' when changes list is empty."""
    result = DryRunResult(
        success=True,
        changes=[],
        validation_passed=True,
        markers_passed=True,
        raw_output="All up to date",
    )
    output = format_output(result, fmt="table")
    assert "no changes" in output.lower()


def test_format_sync_result_table():
    """Table format works with SyncResult too."""
    result = SyncResult(
        success=True,
        steps_completed=["pull", "dedup: removed 2 chart duplicates"],
    )
    output = format_output(result, fmt="table")
    assert "pull" in output
    assert "dedup" in output


# ── JSON format ─────────────────────────────────────────────────────


def test_format_dry_run_result_json():
    """JSON format produces valid parseable JSON."""
    result = DryRunResult(
        success=True,
        changes=[
            AssetChange("chart", "Revenue", ChangeAction.CREATE),
        ],
        validation_passed=True,
        markers_passed=True,
        raw_output="Creating chart \"Revenue\"",
    )
    output = format_output(result, fmt="json")
    parsed = json.loads(output)
    assert parsed["success"] is True
    assert parsed["validation_passed"] is True
    assert len(parsed["changes"]) == 1
    assert parsed["changes"][0]["name"] == "Revenue"
    assert parsed["changes"][0]["action"] == "create"


def test_format_sync_result_json():
    """JSON format works with SyncResult."""
    result = SyncResult(success=True, steps_completed=["pull"])
    output = format_output(result, fmt="json")
    parsed = json.loads(output)
    assert parsed["success"] is True
    assert "pull" in parsed["steps_completed"]


# ── YAML format ─────────────────────────────────────────────────────


def test_format_dry_run_result_yaml():
    """YAML format produces valid parseable YAML."""
    result = DryRunResult(
        success=True,
        changes=[
            AssetChange("dataset", "Main", ChangeAction.UPDATE),
        ],
        validation_passed=True,
        markers_passed=True,
        raw_output="Updating dataset \"Main\"",
    )
    output = format_output(result, fmt="yaml")
    parsed = yaml.safe_load(output)
    assert parsed["success"] is True
    assert len(parsed["changes"]) == 1
    assert parsed["changes"][0]["action"] == "update"


# ── Error handling ──────────────────────────────────────────────────


def test_format_invalid_format_raises():
    """Unknown format raises ValueError."""
    result = SyncResult(success=True)
    with pytest.raises(ValueError, match="Unknown format"):
        format_output(result, fmt="xml")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_formatter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.formatter'`

- [ ] **Step 3: Implement scripts/formatter.py**

Create `scripts/formatter.py`:

```python
"""Output formatter: render result dataclasses as table, JSON, or YAML."""
import dataclasses
import json
from typing import Any

import yaml

from scripts.sync import AssetChange, ChangeAction, DryRunResult, SyncResult

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


def _to_dict(data: Any) -> dict:
    """Convert a dataclass to a plain dict.

    ChangeAction(str, Enum) values serialize as plain strings via
    dataclasses.asdict() because they inherit from str.
    """
    return dataclasses.asdict(data)


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
            # Generic fallback for any dataclass
            return str(dataclasses.asdict(data))
    elif fmt == "json":
        return json.dumps(_to_dict(data), indent=2)
    elif fmt == "yaml":
        return yaml.dump(_to_dict(data), default_flow_style=False, sort_keys=False)
    else:
        raise ValueError(f"Unknown format: {fmt!r}. Supported: table, json, yaml")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/test_formatter.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/formatter.py tests/test_formatter.py
git commit -m "feat: add output formatter with table/json/yaml support"
```

---

## Chunk 3: Skill Docs and Final Verification

### Task 7: Update Skill Documentation

**Files:**
- Modify: `skills/preset-validate/SKILL.md:116-128` (Python API section)
- Modify: `skills/preset-sync-push/SKILL.md:98-127` (Step 5 approval gate)

- [ ] **Step 1: Update preset-validate skill's Python API section**

In `skills/preset-validate/SKILL.md`, replace lines 116-128 (the "Using the Python API" section) with:

```markdown
## Using the Python API

```python
from scripts.sync import validate, DryRunResult
from scripts.formatter import format_output
from scripts.config import ToolkitConfig

config = ToolkitConfig.discover()
result = validate(config)

# result is a DryRunResult:
# result.success -- bool (True only if all checks pass)
# result.validation_passed -- bool (sup sync validate passed)
# result.markers_passed -- bool (all markers found)
# result.changes -- List[AssetChange] (parsed from dry-run output)
# result.raw_output -- str (original sup dry-run stdout)
# result.steps_completed -- List[str] (step descriptions)
# result.error -- str (error message if failed)

# Format output as table, json, or yaml:
print(format_output(result, fmt="table"))
```
```

- [ ] **Step 2: Update preset-sync-push skill's Step 5**

In `skills/preset-sync-push/SKILL.md`, replace the Step 5 approval gate section (lines 108-127) with:

```markdown
### Step 5: Approval Gate

Present a structured summary using `DryRunResult`:

```python
from scripts.formatter import format_output

# result is the DryRunResult from validate()
print(format_output(result, fmt="table"))
```

This renders:

```
Validation: PASSED
Markers:    PASSED

Action       Type         Name
--------------------------------------------------
create       chart        New Revenue Chart
update       dataset      Main_Dataset

2 change(s) detected.
```

If no structured changes are parsed, the raw sup output is shown as fallback.

**This is the only approval question in the push flow.** Wait for explicit "yes" before proceeding.

If `--dry-run` was specified, stop here and report the summary without asking.
```

- [ ] **Step 3: Commit**

```bash
git add skills/preset-validate/SKILL.md skills/preset-sync-push/SKILL.md
git commit -m "docs: update validate and push skills with DryRunResult API"
```

---

### Task 8: Final Full Test Suite Run

- [ ] **Step 1: Run entire test suite**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -m pytest tests/ -v`
Expected: All tests PASS (existing 140 + new ~20 = ~160 total)

- [ ] **Step 2: Verify imports work cleanly**

Run: `cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit" && python -c "from scripts.sync import ChangeAction, AssetChange, DryRunResult, _parse_dry_run_output; from scripts.formatter import format_output; print('All imports OK')" `
Expected: `All imports OK`

- [ ] **Step 3: Final commit with version bump (if all green)**

Update `.claude-plugin/marketplace.json` — change `"version": "0.5.0"` to `"version": "0.6.0"` (line 12).

Update `README.md` — change the test count badge from `136` to the actual count shown by pytest (line 5), and version badge from `0.5.0` to `0.6.0` (line 4).

```bash
git add .claude-plugin/marketplace.json README.md
git commit -m "chore: bump to v0.6.0 with dry-run output formats"
```
