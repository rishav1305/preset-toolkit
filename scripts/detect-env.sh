#!/usr/bin/env bash
# Detect environment for preset-toolkit setup.
# Outputs key=value pairs, one per line. No subshells needed.
set -euo pipefail

git config user.email 2>/dev/null || echo "GIT_EMAIL="
test -n "${PRESET_API_TOKEN:-}" && echo "TOKEN=SET" || echo "TOKEN=UNSET"
test -n "${PRESET_API_SECRET:-}" && echo "SECRET=SET" || echo "SECRET=UNSET"
command -v pip3 >/dev/null 2>&1 && echo "PIP=yes" || echo "PIP=no"
ls -d *-sync/ 2>/dev/null | head -1 || echo "SYNC=sync"
