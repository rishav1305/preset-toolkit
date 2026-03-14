---
name: preset-brainstorming
description: "Dashboard change brainstorming -- understand business intent, map to technical changes, preview impact"
---

# Brainstorming

Help the user brainstorm dashboard changes. Focus exclusively on business-level questions: what label, formula, layout, or visual change they want. Auto-resolve all technical details (file paths, YAML structure, sync mechanics).

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

Read the current dashboard state to understand what exists:
- Dashboard YAML for layout and CSS
- Chart YAMLs for tile configurations
- Dataset YAMLs for SQL and content

## Workflow

### Step 1: Understand the Change

Ask: **"What change do you want to make?"**

Listen for intent categories:
- **Label change:** "Rename X to Y", "Change the title of..."
- **Formula change:** "Revenue should include...", "Calculate X differently"
- **Layout change:** "Move the Audience section...", "Make the tiles bigger"
- **Visual change:** "Change the font size", "Add a border", "Change colors"
- **New content:** "Add a new tile for...", "Show churn data"
- **Remove content:** "Remove the Snow Users tile", "Hide the notes section"

### Step 2: Map to Dashboard Components

Based on the user's intent, automatically determine which files are affected:

| Change Type | Where It Lives | File Pattern |
|---|---|---|
| Tile labels / content | Dataset SQL | `assets/datasets/<db>/*.yaml` -- `sql` field |
| Section headers | Dataset SQL (HTML) | Same as above -- `<div>` elements in SQL |
| Chart titles / descriptions | Chart YAML | `assets/charts/*.yaml` -- `slice_name`, `description` |
| Chart data settings | Chart YAML | `assets/charts/*.yaml` -- `row_limit`, `params` |
| Layout / grid positions | Dashboard YAML | `assets/dashboards/*.yaml` -- `position_json` |
| CSS / visual styling | Dashboard YAML | `assets/dashboards/*.yaml` -- `css` field |
| Filters | Dashboard YAML | `assets/dashboards/*.yaml` -- `json_metadata.native_filter_configuration` |
| Asterisk annotations | Dashboard YAML + Dataset SQL | MARKDOWN component `code` + label `<div>` elements |

Tell the user which components will be affected but **never mention file paths or YAML field names**. Instead say things like:
- "That change affects the Audience tile content."
- "I'll need to update the dashboard CSS for the spacing change."
- "The Revenue card formula lives in the main dataset."

### Step 3: Validate Business Logic

If the change involves formulas or calculated values, confirm the logic:

```
You want Revenue to equal Ads + Subs Sales.
Currently, Revenue = Ads Revenue only.

Is this correct:
  Total Revenue = Ad Revenue + Subscription Sales Revenue?
```

### Step 4: Check for Side Effects

Analyze whether the proposed change affects other parts of the dashboard:

- **Shared datasets:** A dataset SQL change affects ALL charts using that dataset.
- **CSS cascading:** A CSS change might affect other tiles with similar selectors.
- **Label widths:** Longer labels may overflow their containers.
- **Asterisk annotations:** If adding/removing an asterisk, the notes section needs updating too.

Report any side effects:

```
This change will also affect:
  - The Monetization section (uses the same dataset)
  - The notes section at the bottom (needs a new asterisk entry)
```

### Step 5: Preview the Impact

Describe what will change in plain English:

```
Here's what this change involves:

  1. The Audience tile label changes from "WAU" to "Weekly Active Users"
  2. The tile width stays the same (the new label fits)
  3. No other sections are affected

  Files affected: 1 dataset (content change)
  Estimated complexity: Simple (single string replacement)

Ready to create a plan? (yes/no)
```

If the user confirms, hand off to `preset-toolkit:preset-writing-plans` to break the change into safe execution steps.

## Reference: Safe YAML Editing

When discussing changes to YAML files, always assume the safe edit pattern will be used:
1. `yaml.safe_load()` to read
2. Modify the relevant field
3. Raw string replacement to write back (never `yaml.dump()`)

This preserves Jinja templates (`{{ }}`), YAML formatting, and special characters. See `references/sup-cli.md` for details on why `yaml.dump()` is dangerous.

## Reference: CSS Best Practices

When discussing CSS changes:
- Use `[data-test-chart-id="<id>"]` selectors (NOT `[data-chart-id]`).
- Keep total CSS under 30K characters (Preset truncates at ~33K).
- Check for existing selectors before adding new ones to avoid conflicts.

See `references/preset-api.md` for CSS truncation details.
