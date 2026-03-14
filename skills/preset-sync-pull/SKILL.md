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
2. Verify `.venv/bin/python3` exists. If not, tell the user to run `/preset setup` first.
3. Load auth from environment (`PRESET_API_TOKEN`, `PRESET_API_SECRET`) or from `.preset-toolkit/.secrets/keys.env`.

**IMPORTANT:** Always use `.venv/bin/python3` and `.venv/bin/sup` for execution. Never use system Python or system sup. All dependencies were installed in the venv during setup.

## Execution Steps

### Step 1: Quick Dependency Check (1 Bash call)

Verify the venv and key deps are available. Do NOT install anything — just check and fail fast if missing.

```bash
test -f .venv/bin/python3 && .venv/bin/python3 -c "import yaml, PIL, httpx; print('DEPS_OK')" && echo "VENV_OK" || echo "VENV_MISSING"
```

If `VENV_MISSING`: Stop and tell the user "Run `/preset setup` first to install dependencies."

### Step 2: Pull from Preset

Use the plugin's Python scripts via the venv. Set PYTHONPATH to the plugin root so `scripts.*` imports work.

Find the plugin root (where `scripts/` lives):
```bash
PLUGIN_ROOT=$(find ~/.claude/plugins/cache -path "*/preset-toolkit/*/scripts/sync.py" -print -quit 2>/dev/null | sed 's|/scripts/sync.py||')
```

Then run the pull:
```bash
source .venv/bin/activate && PYTHONPATH="${PLUGIN_ROOT}:${PYTHONPATH:-}" .venv/bin/python3 -c "
from scripts.sync import pull
from scripts.config import ToolkitConfig
config = ToolkitConfig.discover()
result = pull(config)
print('SUCCESS' if result.success else 'FAILED')
for w in result.warnings:
    print(f'WARNING: {w}')
if result.error:
    print(f'ERROR: {result.error}')
"
```

If `sup` is not found or pull fails with "sup not found", fall back to direct API pull:
```bash
source .venv/bin/activate && PYTHONPATH="${PLUGIN_ROOT}:${PYTHONPATH:-}" .venv/bin/python3 -c "
import httpx, os, json, yaml
from pathlib import Path

config_path = Path('.preset-toolkit/config.yaml')
cfg = yaml.safe_load(config_path.read_text())
workspace_url = cfg['workspace']['url'].rstrip('/')
dashboard_id = cfg['dashboard']['id']
token = os.environ.get('PRESET_API_TOKEN', '')
secret = os.environ.get('PRESET_API_SECRET', '')

# Get JWT
resp = httpx.post(f'{workspace_url}/api/v1/security/login', json={
    'username': token, 'password': secret, 'provider': 'db', 'refresh': True
}, timeout=30)
jwt = resp.json()['access_token']

# Export assets
headers = {'Authorization': f'Bearer {jwt}'}
resp = httpx.get(f'{workspace_url}/api/v1/assets/export/', headers=headers, timeout=120)

import zipfile, io
z = zipfile.ZipFile(io.BytesIO(resp.content))
z.extractall(cfg.get('sync', {}).get('folder', 'sync') + '/assets')
print(f'Exported {len(z.namelist())} files')
"
```

### Step 3: Deduplicate + Fingerprint + Markers

After pull, run all post-pull checks in one call:

```bash
source .venv/bin/activate && PYTHONPATH="${PLUGIN_ROOT}:${PYTHONPATH:-}" .venv/bin/python3 -c "
from scripts.dedup import apply_dedup
from scripts.fingerprint import compute_fingerprint, load_fingerprint, check_markers
from pathlib import Path
import yaml

cfg = yaml.safe_load(Path('.preset-toolkit/config.yaml').read_text())
sync_folder = cfg.get('sync', {}).get('folder', 'sync')
assets = Path(sync_folder) / 'assets'

# Dedup
charts_removed = apply_dedup(assets / 'charts') if (assets / 'charts').exists() else 0
ds_removed = 0
ds_dir = assets / 'datasets'
if ds_dir.exists():
    for sub in ds_dir.iterdir():
        if sub.is_dir():
            ds_removed += apply_dedup(sub)
print(f'Duplicates removed: {charts_removed} charts, {ds_removed} datasets')

# Fingerprint
fp_file = Path('.preset-toolkit/.last-push-fingerprint')
last_fp = load_fingerprint(fp_file)
ds_yamls = list((assets / 'datasets').rglob('*.yaml'))
if ds_yamls:
    current_fp = compute_fingerprint(ds_yamls[0])
    print(f'Fingerprint: {current_fp.hash}  {current_fp.sql_length}')
    if last_fp:
        print('Match: YES' if current_fp.hash == last_fp.hash else 'Match: CHANGED')
    else:
        print('No previous fingerprint (first pull).')

# Markers
markers_file = Path('.preset-toolkit/markers.txt')
if markers_file.exists() and ds_yamls:
    result = check_markers(ds_yamls[0], markers_file)
    print(f'Markers: {\"All present\" if not result.missing else f\"{len(result.missing)} MISSING\"}')
else:
    print('Markers: All present.')
"
```

### Step 4: Summary

Print a summary report:

```
Pull Complete

  Sync folder:        {{sync_folder}}/assets
  Files pulled:       {{count}}
  Duplicates removed: {{charts + datasets}}
  Fingerprint:        {{hash}} ({{length}} chars)
  Fingerprint status: {{Matches / Changed / First pull}}
  Markers:            {{All present / X missing}}
```

## Error Recovery

| Symptom | Cause | Fix |
|---|---|---|
| VENV_MISSING | Setup not run | Run `/preset setup` first |
| "Unable to fetch JWT" | Intermittent Preset auth | Retry in 1-2 minutes |
| Markers missing after pull | Stale/cached data | Restore from git, do not use this pull |
| Fingerprint changed unexpectedly | Someone else pushed | Review the diff before proceeding |
| "sup not found" | preset-cli not in venv | Uses API fallback automatically |
