---
name: ownership
description: "Check section ownership for changed charts/datasets and display advisory warnings"
---

# Ownership Check

Check which dashboard sections are affected by current changes and display advisory warnings when editing outside your assigned sections. Ownership checks are advisory only -- they never block operations.

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

## Execution Steps

### Step 1: Load Ownership Map

```python
from scripts.ownership import OwnershipMap
from pathlib import Path

ownership_file = Path(".preset-toolkit/ownership.yaml")
if not ownership_file.exists():
    print("No ownership.yaml found. Ownership checking is not configured.")
    print("Create .preset-toolkit/ownership.yaml to enable section ownership warnings.")
    return

omap = OwnershipMap.load(ownership_file)
```

### Step 2: Detect Changed Files

Determine which charts and datasets have been modified. Use git diff if available, otherwise use file modification times:

```bash
# Git-based detection (preferred)
git diff --name-only HEAD -- <sync_folder>/assets/charts/
git diff --name-only HEAD -- <sync_folder>/assets/datasets/
```

Parse the changed chart YAMLs to extract chart IDs:

```python
import yaml

changed_chart_ids = []
changed_dataset_names = []

for chart_file in changed_chart_files:
    with open(chart_file) as f:
        data = yaml.safe_load(f)
    chart_id = data.get("slice_id") or data.get("id")
    if chart_id:
        changed_chart_ids.append(int(chart_id))

for ds_file in changed_dataset_files:
    changed_dataset_names.append(ds_file.stem)
```

### Step 3: Run Ownership Check

```python
check = omap.check(
    user_email=config.user_email,
    changed_charts=changed_chart_ids,
    changed_datasets=changed_dataset_names,
)
```

### Step 4: Display Results

If there are warnings:

```
Ownership Check (Advisory)

  Your email: you@company.com

  Section Warnings:
    - Chart 2087 belongs to 'Activation' (owned by alice@company.com). Notify them before pushing.
    - Chart 2090 belongs to 'Monetization' (owned by bob@company.com). Notify them before pushing.

  Shared Dataset Warnings:
    - Dataset 'My_Dataset' is shared. Notify all owners before editing. Owners: alice@company.com, bob@company.com

  These warnings are advisory only. They do not block your push.
```

If no warnings:

```
Ownership Check: No warnings.
All changed files are in sections you own or in unassigned sections.
```

### Step 5: Suggest Notifications

If there are warnings, suggest notifying the affected owners:

```
Would you like to notify the affected section owners?
  - alice@company.com (Activation section)
  - bob@company.com (Monetization section)
```

This is purely advisory. The user decides whether to notify.

## Using the Agent

For detailed conflict analysis, you can delegate to the `conflict-check-agent`:

```
Invoke agents/conflict-check-agent with:
  ownership_path: .preset-toolkit/ownership.yaml
  changed_files: [list of changed file paths]
```

See `agents/conflict-check-agent.md` for the agent specification.

## Ownership YAML Format

The ownership map is defined in `.preset-toolkit/ownership.yaml`:

```yaml
sections:
  audience:
    owner: "alice@company.com"
    charts: [2084]
    datasets: ["WCBM_Audience_Tile_Source"]
    description: "WAU, Avg DAU tiles"
  activation:
    owner: "alice@company.com"
    charts: [2087]
    description: "Activation funnel"

shared_datasets:
  - name: "WCBM_Audience_Tile_Source"
    owners: ["alice@company.com", "bob@company.com"]
    advisory: "This dataset powers multiple sections."
```

Key rules:
- `owner: null` means anyone can edit without warnings.
- Charts are identified by their numeric Preset chart ID.
- Shared datasets generate warnings for all owners except the current user.
