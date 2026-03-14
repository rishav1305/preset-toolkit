---
name: preset-sync-pull
description: "Pull latest dashboard state from Preset, deduplicate files, and verify integrity"
---

# Sync Pull

Pull the latest dashboard state from Preset, deduplicate chart/dataset files, and verify content integrity against the last known good push.

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

1. Read `.preset-toolkit/config.yaml` to get workspace_url, workspace_id, dashboard_id, sync_folder.
2. Verify `.venv/bin/python3` and `.venv/bin/sup` both exist. If either is missing, tell the user to run `/preset-toolkit:preset-setup` first. Do NOT attempt to install anything.
3. Auth is configured via `sup config` (stored credentials).

**IMPORTANT:** Always use `.venv/bin/python3` and `.venv/bin/sup` for execution. Never use system Python or system sup. All dependencies were installed in the venv during setup.

## Execution Steps

### Step 1: Preflight Check (1 Bash call)

Verify venv, preset-cli, and key deps are available. Do NOT install anything — just check and fail fast.

```bash
test -f .venv/bin/python3 && test -f .venv/bin/sup && .venv/bin/python3 -c "import yaml, PIL, httpx; print('DEPS_OK')" && .venv/bin/sup --version && echo "PREFLIGHT_OK" || echo "PREFLIGHT_FAILED"
```

If `PREFLIGHT_FAILED`: Stop and tell the user: "Dependencies missing. Run `/preset-toolkit:preset-setup` to install them."

### Step 2: Pull from Preset

Find the plugin root (where `scripts/` lives) — search both cache and marketplace dirs:
```bash
PLUGIN_ROOT=$(find ~/.claude/plugins -path "*/preset-toolkit/*/scripts/sync.py" -print -quit 2>/dev/null | sed 's|/scripts/sync.py||')
```

Then run the pull:
```bash
source .venv/bin/activate && PYTHONPATH="${PLUGIN_ROOT}:${PYTHONPATH:-}" .venv/bin/python3 -c "
from scripts.sync import pull
from scripts.config import ToolkitConfig
config = ToolkitConfig.discover()
result = pull(config)
print('SUCCESS' if result.success else 'FAILED')
for s in result.steps_completed:
    print(f'STEP: {s}')
for w in result.warnings:
    print(f'WARNING: {w}')
if result.error:
    print(f'ERROR: {result.error}')
"
```

If this fails, do NOT attempt any fallback. Report the error clearly and suggest the user check their credentials and network, or run `/preset-toolkit:preset-setup` again.

### Step 3: Summary

Print a summary report:

```
Pull Complete

  Sync folder:        {{sync_folder}}/
  Files pulled:       {{count}}
  Duplicates removed: {{charts + datasets}}
  Fingerprint:        {{hash summary}}
  Markers:            {{All present / X missing}}
```

## Error Recovery

| Symptom | Cause | Fix |
|---|---|---|
| PREFLIGHT_FAILED | Setup not run or incomplete | Run `/preset-toolkit:preset-setup` |
| "sup CLI not found" | sup not in venv | Run `/preset-toolkit:preset-setup` |
| "Failed to auth" | Invalid or expired credentials | Run `.venv/bin/sup config` to reconfigure credentials |
| Timeout on pull | Network or Preset server issue | Retry in 1-2 minutes |
| Markers missing after pull | Stale/cached data | Review the diff before proceeding |
