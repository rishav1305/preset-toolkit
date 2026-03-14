#!/usr/bin/env bash
# Bootstrap script for preset-toolkit setup.
# Creates venv, installs all deps, verifies each one.
# Outputs structured log lines for the setup skill to display.
set -euo pipefail

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BLUE="\033[0;34m"
BOLD="\033[1m"
RESET="\033[0m"

ok()   { printf "  ${GREEN}✓${RESET} %s\n" "$1"; }
warn() { printf "  ${YELLOW}⚠${RESET} %s\n" "$1"; }
fail() { printf "  ${RED}✗${RESET} %s\n" "$1"; }
info() { printf "  ${BLUE}→${RESET} %s\n" "$1"; }
head() { printf "\n${BOLD}%s${RESET}\n" "$1"; }

# ── Phase 1: Environment ──────────────────────────────────────────────

head "Environment"

# Python
if command -v python3 >/dev/null 2>&1; then
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    ok "Python ${PY_VERSION}"
else
    fail "Python 3 not found — install it first"
    exit 1
fi

# Git
if command -v git >/dev/null 2>&1; then
    GIT_EMAIL=$(git config user.email 2>/dev/null || echo "not configured")
    ok "Git (${GIT_EMAIL})"
else
    warn "Git not found — some features won't work"
fi

# ── Phase 2: Virtual Environment ──────────────────────────────────────

head "Virtual Environment"

if [ -d ".venv" ] && [ -f ".venv/bin/python3" ]; then
    ok ".venv/ exists"
else
    info "Creating .venv..."
    python3 -m venv .venv
    ok ".venv/ created"
fi

# ── Phase 3: Dependencies (batched) ──────────────────────────────────

head "Dependencies"

VENV_PIP=".venv/bin/pip"
VENV_PY=".venv/bin/python3"

# Install all packages in one call
info "Installing packages..."
$VENV_PIP install -q PyYAML Pillow httpx preset-cli 2>&1 | grep -v "notice" || true

# Batched verification — single Python call checks all deps at once
DEP_RESULT=$($VENV_PY -c "
import json, importlib, importlib.metadata, shutil
results = {}
for mod, name in [('yaml','PyYAML'), ('PIL','Pillow'), ('httpx','httpx')]:
    try:
        importlib.import_module(mod)
        results[name] = 'ok'
    except ImportError:
        results[name] = 'fail'
# Check preset-cli
try:
    ver = importlib.metadata.version('preset-cli')
    results['preset-cli'] = ver
except Exception:
    results['preset-cli'] = 'missing'
print(json.dumps(results))
" 2>/dev/null || echo '{}')

# Parse results
for pkg in PyYAML Pillow httpx; do
    STATUS=$(echo "$DEP_RESULT" | $VENV_PY -c "import json,sys; d=json.load(sys.stdin); print(d.get('$pkg','fail'))" 2>/dev/null || echo "fail")
    if [ "$STATUS" = "ok" ]; then
        ok "$pkg"
    else
        fail "$pkg — import failed"
    fi
done

# preset-cli check
SUP_STATUS=$(echo "$DEP_RESULT" | $VENV_PY -c "import json,sys; d=json.load(sys.stdin); print(d.get('preset-cli','missing'))" 2>/dev/null || echo "missing")
if [ "$SUP_STATUS" != "missing" ]; then
    if [ -f ".venv/bin/sup" ]; then
        ok "preset-cli v${SUP_STATUS} (.venv/bin/sup)"
    else
        ok "preset-cli v${SUP_STATUS} (installed, sup binary via PATH)"
    fi
else
    warn "preset-cli not installed — trying reinstall..."
    $VENV_PIP install -q --force-reinstall preset-cli 2>&1 | grep -v "notice" || true
    if [ -f ".venv/bin/sup" ]; then
        ok "preset-cli installed on retry"
    else
        fail "preset-cli — sup binary not found"
    fi
fi

# ── Phase 4: Directories ─────────────────────────────────────────────

head "Project Structure"

mkdir -p .preset-toolkit/.secrets .preset-toolkit/baselines .preset-toolkit/screenshots sync
ok ".preset-toolkit/ directories"
ok "sync/ folder"

# ── Phase 5: Auth ─────────────────────────────────────────────────────

head "Authentication"

WORKSPACE_URL="${1:-}"

if [ -n "${PRESET_API_TOKEN:-}" ] && [ -n "${PRESET_API_SECRET:-}" ]; then
    ok "PRESET_API_TOKEN is set"
    ok "PRESET_API_SECRET is set"

    # Validate credentials if workspace URL provided
    if [ -n "$WORKSPACE_URL" ]; then
        info "Validating credentials against ${WORKSPACE_URL}..."
        AUTH_RESULT=$($VENV_PY -c "
import httpx, json, sys
url = sys.argv[1].rstrip('/') + '/api/v1/security/login'
try:
    resp = httpx.post(url, json={
        'token': '${PRESET_API_TOKEN}',
        'secret': '${PRESET_API_SECRET}'
    }, timeout=10)
    if resp.status_code == 200 and resp.json().get('access_token'):
        print('OK')
    else:
        print('FAIL:' + str(resp.status_code))
except Exception as e:
    print('ERROR:' + str(e)[:100])
" "$WORKSPACE_URL" 2>/dev/null || echo "ERROR:python failed")

        case "$AUTH_RESULT" in
            OK)    ok "Authenticated to ${WORKSPACE_URL}" ;;
            FAIL*) warn "Authentication failed (${AUTH_RESULT#FAIL:}) — credentials may be invalid" ;;
            *)     warn "Could not validate credentials (${AUTH_RESULT#ERROR:})" ;;
        esac
    fi
    echo "AUTH=SET"
else
    if [ -z "${PRESET_API_TOKEN:-}" ]; then
        fail "PRESET_API_TOKEN not set"
    else
        ok "PRESET_API_TOKEN is set"
    fi
    if [ -z "${PRESET_API_SECRET:-}" ]; then
        fail "PRESET_API_SECRET not set"
    else
        ok "PRESET_API_SECRET is set"
    fi
    echo "AUTH=UNSET"
fi

echo ""
echo "BOOTSTRAP_DONE"
