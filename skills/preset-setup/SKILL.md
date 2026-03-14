---
name: preset-setup
description: "First-time project wizard for preset-toolkit -- creates config, sets up auth, runs initial pull"
---

# Setup Wizard

You are the first-time setup wizard for preset-toolkit. Walk the user through project initialization with minimal questions -- auto-resolve everything technical.

**SPEED MANDATE:** Complete setup in ≤ 5 tool calls after gathering user input. Never retry failed installs. No `$()` subshells in Bash commands (triggers permission prompts).

## Conversation Principles (MANDATORY)

**NEVER ask about:**
- Config formats, file paths, YAML structure, directory layout
- Which scripts to run, CLI flags, sync modes, technical parameters
- Auth methods, tokens, API endpoints, CSRF handling
- Git branches, merge strategies, commit messages
- Infrastructure, server details, environment setup

**ONLY ask about:**
- "What dashboard are you working on?" (name)
- "What's your Preset workspace URL?" (or full dashboard URL)
- Dashboard ID (only if not extractable from the URL)

## Step 1: Gather Business Context (1 message)

Ask exactly two questions in a single message:

1. **"What dashboard are you working on?"** -- Get the name.
2. **"What's your Preset workspace URL?"** -- If the user provides a full dashboard URL like `https://xxx.us2a.app.preset.io/superset/dashboard/76/`, extract workspace URL AND dashboard ID from it (skip the ID question).

Extract workspace ID from the URL subdomain (e.g., `834639b2` from `https://834639b2.us2a.app.preset.io`).

## Step 2: Create Directories (1 Bash call — no subshells)

```bash
mkdir -p .preset-toolkit/.secrets .preset-toolkit/baselines .preset-toolkit/screenshots sync
```

## Step 3: Detect Environment (1 Bash call — no subshells)

Use a simple script that avoids `$()` substitution:

```bash
bash -c 'git config user.email 2>/dev/null || echo ""; echo "TOKEN=$PRESET_API_TOKEN"; echo "SECRET=$PRESET_API_SECRET"; which pip3 2>/dev/null && echo "PIP=yes" || echo "PIP=no"; ls -d *-sync/ 2>/dev/null || echo "NO_SYNC"'
```

Parse the output to determine: git email, token/secret status (SET/UNSET based on non-empty), pip availability, existing sync folder.

## Step 4: Write Config Files (parallel Write calls)

Write ALL config files in parallel using the Write tool. Use the detected values from previous steps. You already know the workspace_url, workspace_id, dashboard_id, dashboard_name from the user's input.

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
  folder: "{{sync_folder}}"

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
{"workspace_id": "{{workspace_id}}", "sync_folder": "{{sync_folder}}", "files": [], "charts": []}
```

### `.gitignore` (append or create)
```
.preset-toolkit/.secrets/
.preset-toolkit/.last-push-fingerprint
screenshots/
*.pyc
__pycache__/
.venv/
```

## Step 5: Install Dependencies (only if pip available)

**If PIP=yes from Step 3:**
```bash
pip3 install -q PyYAML Pillow httpx preset-cli 2>&1 | tail -3
```

**If PIP=no:** Skip entirely. Report missing deps in the summary.

## Step 6: Print Summary (immediately, no tool call)

```
Setup complete!

  Dashboard:    {{dashboard_name}} (ID: {{dashboard_id}})
  Workspace:    {{workspace_url}}
  Workspace ID: {{workspace_id}}
  Sync folder:  {{sync_folder}}
  Auth:         {{Configured via environment variables ✓ | NOT SET — see below}}

  Files created:
    .preset-toolkit/config.yaml
    .preset-toolkit/markers.txt
    .preset-toolkit/ownership.yaml
    .preset-toolkit/smoke.json
    .gitignore

  {{if deps missing: ⚠ Dependencies needed: pip install PyYAML Pillow httpx preset-cli}}

  Next steps:
    /preset pull      — Pull latest dashboard state from Preset
    /preset check     — Run health checks
    /preset push      — Validate and push changes
```

Do NOT attempt an initial pull during setup. Setup only creates config files.

## Error Recovery

- If directory creation fails: Check permissions, suggest running from the project root.
- If pip install partially fails: Report what failed, continue.
- Never retry installs with different methods. Report once and move on.
