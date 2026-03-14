#!/usr/bin/env bash
# Session-start hook for preset-toolkit.
# Checks if the current project is a preset-toolkit project and outputs
# context for the Claude session.

set -euo pipefail

# Walk up from CWD looking for .preset-toolkit/config.yaml
find_config() {
    local dir="$PWD"
    while [ "$dir" != "/" ]; do
        if [ -f "$dir/.preset-toolkit/config.yaml" ]; then
            echo "$dir/.preset-toolkit/config.yaml"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    return 1
}

CONFIG_PATH=$(find_config) || exit 0  # Not a preset-toolkit project — silent exit

PROJECT_ROOT="$(dirname "$(dirname "$CONFIG_PATH")")"

# Ensure PyYAML is available for config parsing
python3 -c "import yaml" 2>/dev/null || {
    echo "[preset-toolkit] Installing PyYAML..."
    python3 -m pip install PyYAML -q 2>/dev/null || true
}

# Parse config values using Python (handles YAML safely)
read_config() {
    python3 -c "
import yaml, sys
with open(sys.argv[1]) as f:
    cfg = yaml.safe_load(f)
dashboard = cfg.get('dashboard', {})
workspace = cfg.get('workspace', {})
user = cfg.get('user', {})
print(dashboard.get('name', ''))
print(dashboard.get('id', ''))
print(workspace.get('url', ''))
print(user.get('email', ''))
" "$CONFIG_PATH" 2>/dev/null
}

CONFIG_VALUES=$(read_config) || exit 0  # YAML parse failed — silent exit

DASH_NAME=$(echo "$CONFIG_VALUES" | sed -n '1p')
DASH_ID=$(echo "$CONFIG_VALUES" | sed -n '2p')
WORKSPACE_URL=$(echo "$CONFIG_VALUES" | sed -n '3p')
USER_EMAIL=$(echo "$CONFIG_VALUES" | sed -n '4p')

# Read last push fingerprint if available (v2 JSON or v1 plain text)
FINGERPRINT=""
FINGERPRINT_FILE="$PROJECT_ROOT/.preset-toolkit/.last-push-fingerprint"
if [ -f "$FINGERPRINT_FILE" ]; then
    FINGERPRINT=$(python3 -c "
import json, sys
try:
    with open(sys.argv[1]) as f:
        data = json.load(f)
    if isinstance(data, dict) and data.get('version') == 2:
        files = data.get('files', {})
        print(f'{len(files)} files tracked')
    else:
        print(f.read().strip())
except (json.JSONDecodeError, Exception):
    with open(sys.argv[1]) as f:
        print(f.read().strip())
" "$FINGERPRINT_FILE" 2>/dev/null || cat "$FINGERPRINT_FILE" 2>/dev/null || true)
fi

# Build the context message
MSG="[preset-toolkit] Dashboard project detected."
MSG="$MSG\n  Dashboard: ${DASH_NAME:-unknown}"

if [ -n "$DASH_ID" ]; then
    MSG="$MSG (ID: $DASH_ID)"
fi

if [ -n "$WORKSPACE_URL" ]; then
    MSG="$MSG\n  Workspace: $WORKSPACE_URL"
    if [ -n "$DASH_ID" ]; then
        MSG="$MSG\n  URL: ${WORKSPACE_URL}/superset/dashboard/${DASH_ID}/"
    fi
fi

if [ -n "$USER_EMAIL" ]; then
    MSG="$MSG\n  User: $USER_EMAIL"
fi

if [ -n "$FINGERPRINT" ]; then
    MSG="$MSG\n  Last push fingerprint: $FINGERPRINT"
fi

MSG="$MSG\n  Use /preset for all dashboard operations."

printf "%b\n" "$MSG"

# Fire telemetry: plugin_loaded (non-blocking, fail-silent)
python3 -c "
import sys; sys.path.insert(0, '$PROJECT_ROOT')
try:
    from scripts.telemetry import get_telemetry
    from pathlib import Path
    t = get_telemetry(Path('$CONFIG_PATH'))
    t.identify()
    t.track('plugin_loaded', {'dashboard_id': int('${DASH_ID:-0}' or 0)})
    t.shutdown()
except Exception:
    pass
" 2>/dev/null &
