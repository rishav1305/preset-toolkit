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

if command -v python3 >/dev/null 2>&1; then
    PY_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    ok "Python ${PY_VERSION}"
else
    fail "Python 3 not found — install it first"
    exit 1
fi

if command -v git >/dev/null 2>&1; then
    GIT_EMAIL=$(git config user.email 2>/dev/null || echo "not configured")
    ok "Git (${GIT_EMAIL})"
else
    warn "Git not found — some features won't work"
fi

if [ -n "${HTTP_PROXY:-}" ] || [ -n "${HTTPS_PROXY:-}" ]; then
    info "Proxy detected: ${HTTPS_PROXY:-$HTTP_PROXY}"
fi
if [ -n "${SSL_CERT_FILE:-}" ]; then
    info "Custom CA bundle: $SSL_CERT_FILE"
elif [ -n "${REQUESTS_CA_BUNDLE:-}" ]; then
    info "Custom CA bundle: $REQUESTS_CA_BUNDLE"
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

# ── Phase 3: Dependencies ─────────────────────────────────────────────

head "Dependencies"

VENV_PIP=".venv/bin/pip"
VENV_PY=".venv/bin/python3"

# Install all packages:
#   superset-sup  → sup CLI (sync run/validate, the actual sync tool)
#   superset-sup handles all sync operations (pull/push/validate)
#   playwright    → browser automation for screenshots
#   PyYAML/Pillow/httpx → core libraries
info "Installing packages..."
$VENV_PIP install -q PyYAML Pillow httpx superset-sup playwright cryptography 2>&1 | grep -v "notice" || true

# Install Chromium browser for Playwright screenshots
info "Installing Chromium browser..."
$VENV_PY -m playwright install chromium 2>&1 | tail -1 || true

# Verify Python packages
DEP_RESULT=$($VENV_PY -c "
import json, importlib
results = {}
for mod, name in [('yaml','PyYAML'), ('PIL','Pillow'), ('httpx','httpx'), ('playwright','playwright'), ('cryptography','cryptography')]:
    try:
        importlib.import_module(mod)
        results[name] = 'ok'
    except ImportError:
        results[name] = 'fail'
print(json.dumps(results))
" 2>/dev/null || echo '{}')

for pkg in PyYAML Pillow httpx playwright cryptography; do
    STATUS=$(echo "$DEP_RESULT" | $VENV_PY -c "import json,sys; d=json.load(sys.stdin); print(d.get('$pkg','fail'))" 2>/dev/null || echo "fail")
    if [ "$STATUS" = "ok" ]; then
        ok "$pkg"
    else
        fail "$pkg — import failed"
    fi
done

# Verify sup CLI (from superset-sup package)
if [ -f ".venv/bin/sup" ] && .venv/bin/sup --version >/dev/null 2>&1; then
    SUP_VER=$(.venv/bin/sup --version 2>&1)
    ok "sup CLI ($SUP_VER) — verified"
else
    warn "sup CLI not found — trying reinstall..."
    $VENV_PIP install -q --force-reinstall superset-sup 2>&1 | grep -v "notice" || true
    if [ -f ".venv/bin/sup" ] && .venv/bin/sup --version >/dev/null 2>&1; then
        ok "sup CLI reinstalled and verified"
    else
        fail "sup CLI not found after install"
    fi
fi


# ── Phase 4: Directories ─────────────────────────────────────────────

head "Project Structure"

mkdir -p .preset-toolkit/.secrets sync
ok ".preset-toolkit/ directory"
ok "sync/ folder"

# ── Phase 5: Auth ─────────────────────────────────────────────────────

head "Authentication"

# Check sup config (stored credentials)
if .venv/bin/sup config show 2>/dev/null | grep -q "Configured"; then
    ok "sup auth configured"
    echo "AUTH=SET"
elif [ -n "${PRESET_API_TOKEN:-}" ] && [ -n "${PRESET_API_SECRET:-}" ]; then
    ok "PRESET_API_TOKEN is set"
    ok "PRESET_API_SECRET is set"
    info "Run 'sup config' to store credentials for the sup CLI"
    echo "AUTH=SET"
else
    fail "No credentials found"
    info "Run '.venv/bin/sup config' to set up authentication"
    echo "AUTH=UNSET"
fi

echo ""
echo "BOOTSTRAP_DONE"
