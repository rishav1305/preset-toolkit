---
name: preset-writing-plans
description: "Break dashboard changes into safe, validated execution steps with checkpoints"
---

# Writing Plans

Break a proposed dashboard change into a sequence of safe, validated execution steps. Each step includes what changes, which file is affected, and a validation checkpoint.

## Conversation Principles (MANDATORY)

**NEVER ask about:**
- Config formats, file paths, YAML structure, directory layout
- Which scripts to run, CLI flags, sync modes, technical parameters
- Auth methods, tokens, API endpoints, CSRF handling
- Git branches, merge strategies, commit messages
- Infrastructure, server details, environment setup

**ONLY ask about:**
- Business intent: "What change do you want to make?"
- Logic validation: "Revenue = Ads + Subs. Is that correct?"
- Data correctness: "The current value is $3M. Does that look right?"
- Visual specifics: "Should the label say 'X' or 'Y'?"
- Ownership clarity: "This tile is in Bob's section. Notify him?"
- Approval gates: "Here's what changes. Push it?"

## Prerequisites

```python
from scripts.config import ToolkitConfig
config = ToolkitConfig.discover()
```

The change description should come from a brainstorming session (`preset-brainstorming`) or the user's direct request.

## Plan Structure

Every plan follows this template:

```
Plan: <Change Title>
Created: YYYY-MM-DD
Estimated steps: X
Estimated complexity: Simple / Medium / Complex

Pre-conditions:
  - [ ] Current state is clean (no uncommitted changes)
  - [ ] Last push fingerprint is saved
  - [ ] Markers all present

Steps:

  Step 1: <Description>
    Change: <What changes in business terms>
    Validation: <How to verify this step>

  Step 2: <Description>
    Change: <What changes in business terms>
    Validation: <How to verify this step>

  ...

  Step N: Push
    Pre-push: Validate + markers + dry-run
    Push: Full push (datasets/charts + CSS)
    Post-push: Pull-back verify + screenshot

Post-conditions:
  - [ ] All markers present
  - [ ] Fingerprint saved
  - [ ] Screenshots captured
  - [ ] Git committed
```

## Mandatory Steps

Every plan MUST include these steps. They are non-negotiable:

### Before any edits:
1. **Check clean state:** Verify no uncommitted changes or stash them.
2. **Record baseline:** Save current fingerprint for comparison.

### After each file edit:
3. **YAML validity check:** Verify the edited file still parses with `yaml.safe_load()`.
4. **Marker check:** Verify all required markers are still present.

### Before push:
5. **Full validate:** `sup sync validate <sync_folder>`
6. **Marker check:** All markers present.
7. **Dry-run:** `sup sync run <sync_folder> --push-only --dry-run --force`

### After push:
8. **Save fingerprint.**
9. **Pull-back verify:** Pull from Preset and check markers.
10. **Screenshot:** Capture and compare against baseline.
11. **Git commit:** Commit the pushed state.

## Safe YAML Edit Pattern

All dataset SQL edits MUST use this pattern (referenced from `references/preset-cli.md`):

```python
import yaml

# 1. Read
with open(yaml_path) as f:
    raw = f.read()
    data = yaml.safe_load(raw)

# 2. Get current SQL
sql = data.get("sql", "")

# 3. Verify the pattern exists
old_pattern = "Revenue</div>"
count = sql.count(old_pattern)
assert count == 1, f"Expected 1 occurrence, found {count}"

# 4. Replace
new_sql = sql.replace(old_pattern, "Total Revenue</div>")

# 5. Write back using raw string replacement (NEVER yaml.dump)
new_raw = raw.replace(sql, new_sql)
with open(yaml_path, "w") as f:
    f.write(new_raw)
```

This preserves Jinja templates, YAML formatting, and all special characters.

## Plan Complexity Guidelines

### Simple (1-2 steps + push)
- Single label rename
- CSS color or font change
- Toggle a chart setting (e.g., `allow_render_html`)

### Medium (3-5 steps + push)
- Formula change affecting one tile
- Add/remove an asterisk annotation (label + notes)
- Layout adjustment (move or resize tiles)

### Complex (6+ steps + push)
- Add a new tile or section
- Restructure a card (change formula + labels + layout)
- Cross-section changes affecting multiple owners

## Ownership Awareness

If the plan touches multiple sections, include an ownership check step:

```
Step X: Ownership Check
  Sections affected: Audience (alice@), Monetization (bob@)
  Advisory: Notify alice@ and bob@ before proceeding.
```

## Example Plan

```
Plan: Rename "Revenue" card to "Revenue - Ads | Subs Sales"
Created: 2026-03-13
Estimated steps: 3
Estimated complexity: Simple

Pre-conditions:
  - [ ] Current state is clean
  - [ ] Fingerprint: a4243a090424bcdd

Steps:

  Step 1: Update card title
    Change: The Revenue section header changes from "Revenue" to "Revenue - Ads | Subs Sales"
    Validation: Search for "Revenue - Ads | Subs Sales" in dataset content

  Step 2: Verify no side effects
    Change: None -- verify other labels are unchanged
    Validation: Run markers check (all present)

  Step 3: Push
    Pre-push: Validate + markers + dry-run
    Push: Full push
    Post-push: Pull-back verify + screenshot + git commit

Post-conditions:
  - [ ] All markers present
  - [ ] Fingerprint saved
  - [ ] Screenshot shows new title
  - [ ] Git committed
```

When the plan is approved by the user, hand off to `preset-executing-plans` for execution.
