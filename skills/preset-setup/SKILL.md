---
name: preset-setup
description: "First-time project wizard for preset-toolkit -- creates config, sets up auth, installs deps in venv"
---

# Setup Wizard

You are the first-time setup wizard for preset-toolkit. Walk the user through project initialization with minimal questions -- auto-resolve everything technical.

**SPEED MANDATE:** Complete setup in ≤ 4 tool calls after gathering user input. Use the bootstrap script for all dependency work. No `$()` subshells in your own Bash commands.

## Conversation Principles (MANDATORY)

**NEVER ask about:**
- Config formats, file paths, YAML structure, directory layout
- Which scripts to run, CLI flags, sync modes, technical parameters
- Auth methods, tokens, API endpoints, CSRF handling (except when AUTH=UNSET — see Step 3)
- Git branches, merge strategies, commit messages
- Infrastructure, server details, environment setup

**ONLY ask about:**
- "What dashboard are you working on?" (name)
- "What's your Preset workspace URL?" (or full dashboard URL)
- Dashboard ID (only if not extractable from the URL)
- API credentials (only if bootstrap reports AUTH=UNSET)

## Step 1: Gather Business Context (1 message)

Ask exactly two questions in a single message:

1. **"What dashboard are you working on?"** -- Get the name.
2. **"What's your Preset workspace URL?"** -- If the user provides a full dashboard URL like `https://xxx.us2a.app.preset.io/superset/dashboard/76/`, extract workspace URL AND dashboard ID from it (skip the ID question).

Extract workspace ID from the URL subdomain (e.g., `834639b2` from `https://834639b2.us2a.app.preset.io`).

## Step 2: Bootstrap (1 Bash call)

Run the bootstrap script which handles everything: venv, deps, directories, auth check.

Find and run the script — the install location varies, so search both cache and marketplace dirs:

```bash
BOOT=$(find ~/.claude/plugins -name "bootstrap.sh" -path "*/preset-toolkit/*" -print -quit 2>/dev/null) && bash "$BOOT"
```

If the find returns nothing, fall back to inline setup (see Error Recovery).

The script outputs color-coded status lines:
- `✓` = available/installed
- `⚠` = warning (non-fatal)
- `✗` = missing/failed
- `→` = action in progress

Check the last lines for:
- `AUTH=SET` or `AUTH=UNSET`
- `BOOTSTRAP_DONE` (success)

## Step 3: Handle Auth (only if AUTH=UNSET)

If bootstrap reported `AUTH=UNSET`, ask the user directly:

> Your Preset API credentials aren't configured. You can get them from **Preset > Settings > API Keys**.
>
> Paste your token and secret and I'll set them up:
> ```
> PRESET_API_TOKEN=your-token-here
> PRESET_API_SECRET=your-secret-here
> ```

When the user provides them, write to `.preset-toolkit/.secrets/keys.env`:
```bash
PRESET_API_TOKEN="<token>"
PRESET_API_SECRET="<secret>"
```

Then add to `.preset-toolkit/.secrets/.gitignore`:
```
*
```

And tell the user to source it or export in their shell:
```
To make these permanent, add to your ~/.zshrc:
  export PRESET_API_TOKEN="<token>"
  export PRESET_API_SECRET="<secret>"
```

If AUTH=SET, skip this step entirely.

## Step 4: Write Config Files

**IMPORTANT:** Before writing any file, you MUST first Read it if it already exists. The Write tool requires a prior Read on existing files. Use this approach:

1. First, check which files already exist using Bash: `ls .preset-toolkit/config.yaml .preset-toolkit/markers.txt .preset-toolkit/ownership.yaml .preset-toolkit/smoke.json .gitignore 2>/dev/null`
2. Read ALL existing files in parallel (so Write won't fail)
3. Then Write all files in parallel

If a file already exists with correct content, skip writing it. Only write files that are missing or need updating.

### `.preset-toolkit/config.yaml`
```yaml
version: 1

workspace:
  url: "{{workspace_url}}"
  id: "{{workspace_id}}"

dashboard:
  id: {{dashboard_id}}
  name: "{{dashboard_name}}"

sync:
  folder: "sync"

screenshots:
  folder: "screenshots"
  navigation_timeout: 60

validation:
  markers_file: ".preset-toolkit/markers.txt"
```

### `.preset-toolkit/markers.txt`
```
# Required content markers — one per line.
# Push is blocked if any marker is missing from the dataset SQL.
# Add key labels that MUST be present in the dashboard.
```

### `.preset-toolkit/ownership.yaml`
```yaml
# Section ownership — advisory warnings when editing outside your sections.
sections: {}
```

### `.preset-toolkit/smoke.json`
```json
{"workspace_id": "{{workspace_id}}", "sync_folder": "sync", "files": [], "charts": []}
```

### `sync/sync_config.yml`

This is required by the `sup` CLI for sync operations. The setup skill MUST create this file.

**IMPORTANT:** The `workspace_id` here must be the NUMERIC workspace ID (e.g., `2194154`), not the alphanumeric one from the URL (e.g., `834639b2`). To get the numeric ID, run:
```bash
.venv/bin/sup workspace list 2>/dev/null | head -20
```
Find the workspace matching the user's URL and use its numeric ID. If `sup workspace list` fails or the workspace isn't found, ask the user for the numeric workspace ID.

```yaml
source:
  workspace_id: {{workspace_numeric_id}}
  assets:
    dashboards:
      selection: ids
      ids: [{{dashboard_id}}]
      include_dependencies: true
target_defaults:
  overwrite: true
  include_dependencies: true
targets:
- workspace_id: {{workspace_numeric_id}}
  name: {{dashboard_name_slug}}
```

Replace `{{dashboard_name_slug}}` with the dashboard name in lowercase with spaces replaced by underscores (e.g., "WCBM Dashboard" → "wcbm_dashboard").

### `.gitignore` (append or create)
```
.preset-toolkit/.secrets/
.preset-toolkit/.last-push-fingerprint
screenshots/
*.pyc
__pycache__/
.venv/
```

## Step 5: Print Summary (no tool call — just output text)

```
Setup complete!

  Dashboard:    {{dashboard_name}} (ID: {{dashboard_id}})
  Workspace:    {{workspace_url}}
  Workspace ID: {{workspace_id}}
  Sync folder:  sync/
  Auth:         {{Configured ✓ | Set up in .preset-toolkit/.secrets/keys.env}}
  Venv:         .venv/ with all dependencies

  Files created:
    .preset-toolkit/config.yaml
    .preset-toolkit/markers.txt
    .preset-toolkit/ownership.yaml
    .preset-toolkit/smoke.json
    sync/sync_config.yml
    .gitignore

  Next steps:
    /preset-toolkit:preset pull         — Pull latest from Preset
    /preset-toolkit:preset check        — Run health checks
    /preset-toolkit:preset push         — Validate and push changes

  Or invoke directly:
    /preset-toolkit:preset-sync-pull    — Pull
    /preset-toolkit:preset-validate     — Check
    /preset-toolkit:preset-sync-push    — Push
```

Do NOT attempt an initial pull during setup. Setup only creates config files.

## Error Recovery

- If bootstrap script not found: Fall back to manual mkdir + venv creation.
- If venv creation fails: Report the error, suggest `python3 -m venv .venv` manually.
- If pip install partially fails: Report what failed, continue with config files.
- Never retry installs with different methods. Report once and move on.
