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

# ── Phase 3: Dependencies ─────────────────────────────────────────────

head "Dependencies"

VENV_PIP=".venv/bin/pip"
VENV_PY=".venv/bin/python3"

# Install all packages
info "Installing packages..."
$VENV_PIP install -q PyYAML Pillow httpx preset-cli 2>&1 | grep -v "notice" || true

# Verify each one
for pkg in yaml PIL httpx; do
    if $VENV_PY -c "import ${pkg}" 2>/dev/null; then
        case $pkg in
            yaml) ok "PyYAML" ;;
            PIL)  ok "Pillow" ;;
            httpx) ok "httpx" ;;
        esac
    else
        case $pkg in
            yaml) fail "PyYAML — import failed" ;;
            PIL)  fail "Pillow — import failed" ;;
            httpx) fail "httpx — import failed" ;;
        esac
    fi
done

# Verify preset-cli (sup)
if [ -f ".venv/bin/sup" ]; then
    SUP_VER=$($VENV_PY -c "import importlib.metadata; print(importlib.metadata.version('preset-cli'))" 2>/dev/null || echo "unknown")
    ok "preset-cli v${SUP_VER} (.venv/bin/sup)"
elif command -v sup >/dev/null 2>&1; then
    ok "preset-cli (system: $(which sup))"
else
    warn "preset-cli not in venv — trying reinstall..."
    $VENV_PIP install -q --force-reinstall preset-cli 2>&1 | grep -v "notice" || true
    if [ -f ".venv/bin/sup" ]; then
        ok "preset-cli installed on retry"
    else
        fail "preset-cli — sup binary not found in .venv/bin/"
    fi
fi

# ── Phase 4: Directories ─────────────────────────────────────────────

head "Project Structure"

mkdir -p .preset-toolkit/.secrets .preset-toolkit/baselines .preset-toolkit/screenshots sync
ok ".preset-toolkit/ directories"
ok "sync/ folder"

# ── Phase 5: Auth ─────────────────────────────────────────────────────

head "Authentication"

if [ -n "${PRESET_API_TOKEN:-}" ] && [ -n "${PRESET_API_SECRET:-}" ]; then
    ok "PRESET_API_TOKEN is set"
    ok "PRESET_API_SECRET is set"
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
