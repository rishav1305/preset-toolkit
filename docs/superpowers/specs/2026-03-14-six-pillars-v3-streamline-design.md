# Six Pillars v3 Streamline — Design Spec

**Date:** 2026-03-14
**Status:** Approved (all sections)
**Scope:** Comprehensive pass across preset-toolkit plugin — 22 issues, 6 pillars

---

## Goal

Streamline the preset-toolkit Claude Code plugin to be fast, robust, secure, resilient, enterprise-ready, and transparent. Consolidate routing, harden setup, improve data integrity, secure secrets, add resilience, and support corporate environments.

## Pillars Mapping

| Pillar | Sections |
|---|---|
| Performant | Section 1 (UX streamline — fewer files, single router) |
| Robust | Section 2 (Setup hardening), Section 3 (Data integrity) |
| Secure | Section 4 (Security hardening) |
| Resilient | Section 5 (Graceful degradation) |
| Sovereign | Section 6 (Enterprise/proxy/TLS support) |
| Transparent | Sections 2, 5 (better logs, warnings, informational output) |

---

## Section 1: UX Streamline (Performant)

### 1a. Delete router skill
- **Delete** `skills/preset/SKILL.md`
- Routing lives exclusively in `commands/preset.md`

### 1b. Delete 6 stub commands
- **Delete** `commands/preset-setup.md`
- **Delete** `commands/preset-pull.md`
- **Delete** `commands/preset-push.md`
- **Delete** `commands/preset-check.md`
- **Delete** `commands/preset-diff.md`
- **Delete** `commands/preset-screenshot.md`
- **Keep** `commands/preset-status.md` (has inline logic, not a stub)

### 1c. Single router in `commands/preset.md`
- Contains full routing table mapping user input to `preset-toolkit:preset-*` skills
- Includes menu display, natural language routing
- Adds **"Preset Mode" context boundary**: once `/preset` is invoked, conversation focuses on Preset operations; guardrails keep context enriched with dashboard details

### 1d. Version single source of truth
- `plugin.json` is the sole source of truth for version
- No version duplication elsewhere

---

## Section 2: Setup Hardening (Robust + Transparent)

### 2a. Credential validation during setup
- `bootstrap.sh` accepts optional workspace URL argument
- After setting `PRESET_API_TOKEN` / `PRESET_API_SECRET`, validate credentials with a real JWT auth endpoint call
- Display `✓ Authenticated to <workspace>` or `✗ Authentication failed — check credentials`

### 2b. Batched dependency check
- Replace sequential dep-by-dep checks with a single Python call that checks all dependencies at once
- Output one summary block: what's installed, what's missing, what was installed

### 2c. Interactive auth prompt
- If `PRESET_API_TOKEN` or `PRESET_API_SECRET` is not set (AUTH=UNSET), ask the user directly in chat
- No `$()` subshell prompts — plain text question, user pastes value
- Set in `.zshrc` / `.bashrc` for persistence

### 2d. Attractive setup logging
- Color-coded progress output:
  - `✓` (green) — already available / installed successfully
  - `⚠` (yellow) — warning, non-blocking issue
  - `✗` (red) — failure, blocking
  - `→` (blue) — informational / action in progress
- Check order: Python → pip → venv → preset-cli → API credentials

---

## Section 3: Data Integrity (Robust)

### 3a. Per-file fingerprint map
- Replace single-hash fingerprint with `{filename: sha256_hash}` JSON map
- **v2 format:** `{"version": 2, "files": {"chart_1.yaml": "abc123...", ...}}`
- Migration: if `.last-push-fingerprint` is a plain string (v1), treat as stale and recompute
- New function: `compute_fingerprint_map(assets_dir) -> dict[str, str]`
- Diff reports: "3 files changed, 1 added, 0 removed" instead of binary "changed/unchanged"

### 3b. Config discovery ambiguity warning
- `scripts/config.py` walks up directories to find `.preset-toolkit/config.yaml`
- If config is found in a **parent** directory (not CWD), emit warning:
  `"⚠ Using config from parent directory: /path/to/parent/.preset-toolkit/"`
- Prevents accidental operations on wrong project

### 3c. Explicit sup CLI errors
- `_ensure_sup()` currently returns `False` silently
- Change to raise `SupNotFoundError` with actionable message:
  `"sup CLI not found. Run /preset setup to install dependencies."`
- Callers catch and display, no more silent fallthrough

---

## Section 4: Security Hardening (Secure)

### 4a. Shared secret sanitization
- Move `_SECRET_PATTERNS` regex from `scripts/sync.py` to `scripts/logger.py`
- New exported function: `sanitize(text: str) -> str`
- Pattern matches: API keys, tokens, secrets, passwords, bearer tokens
- Used by: telemetry (`track_error`), logging, any outbound data

### 4b. Atomic config writes
- All config file writes use: write to temp file → `os.replace()` to final path
- Prevents half-written configs on crash or interrupt
- Applies to: `config.yaml`, `.last-push-fingerprint`, `ownership.yaml`, telemetry anonymous ID

### 4c. Hashed anonymous telemetry ID
- Currently: plain UUID stored via brittle string replacement
- Change to: `hashlib.sha256(machine_id.encode()).hexdigest()[:16]`
- Store/read via proper YAML `safe_load` / `safe_dump` (not string replace)
- Atomic write for the ID file

---

## Section 5: Resilience

### 5a. HTTP retry jitter consistency
- `scripts/http.py`: Add jitter to HTTPStatusError retries (429, 503), not just connection errors
- Formula: `random.uniform(0, backoff_delay * 0.5)` added to both paths
- Prevents thundering herd when multiple requests hit rate limits simultaneously

### 5b. Session-start hook graceful failure
- `hooks/session-start.sh`: Wrap Python YAML parse in try/except
- On any error, output: `"⚠ preset-toolkit: could not read config (run /preset setup)"`
- Hook must NEVER block session start — all errors become one-line warnings

### 5c. Telemetry fire-and-forget cleanup
- `scripts/telemetry.py`: Add 5-second timeout on HTTP calls
- Catch ALL exceptions (network down, DNS failure, PostHog unreachable) and silently discard
- Telemetry must never degrade user experience

---

## Section 6: Enterprise / Sovereign

### 6a. HTTP proxy support
- `scripts/http.py`: Honor `HTTP_PROXY` / `HTTPS_PROXY` / `NO_PROXY` environment variables
- httpx supports these natively — ensure we don't override with `proxies=None`
- Zero config for environments where IT already sets these vars

### 6b. TLS/CA bundle support
- `scripts/http.py`: Honor `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` env vars
- Pass to httpx client: `verify=os.environ.get("SSL_CERT_FILE", True)`
- Fixes TLS errors behind corporate MITM proxies

### 6c. Enterprise environment detection
- `scripts/bootstrap.sh`: During setup, detect and report:
  - Proxy variables set → `→ Proxy detected: <value>`
  - Custom CA bundle → `→ Custom CA bundle: <path>`
  - Managed Python install (paths like `/opt/`, `/usr/local/Cellar/`) → `→ System Python: <path>`
- Purely informational — helps debug connectivity issues

---

## Files Changed Summary

| Action | File | Section |
|---|---|---|
| Delete | `skills/preset/SKILL.md` | 1a |
| Delete | `commands/preset-setup.md` | 1b |
| Delete | `commands/preset-pull.md` | 1b |
| Delete | `commands/preset-push.md` | 1b |
| Delete | `commands/preset-check.md` | 1b |
| Delete | `commands/preset-diff.md` | 1b |
| Delete | `commands/preset-screenshot.md` | 1b |
| Modify | `commands/preset.md` | 1c, 1d |
| Modify | `scripts/bootstrap.sh` | 2a, 2b, 2d, 6c |
| Modify | `skills/preset-setup/SKILL.md` | 2c |
| Modify | `scripts/fingerprint.py` | 3a |
| Modify | `scripts/config.py` | 3b |
| Modify | `scripts/sync.py` | 3c, 4a |
| Modify | `scripts/logger.py` | 4a |
| Modify | `scripts/telemetry.py` | 4b, 4c, 5c |
| Modify | `hooks/session-start.sh` | 5b |
| Modify | `scripts/http.py` | 5a, 6a, 6b |
| Modify | `.claude-plugin/plugin.json` | 1d |

---

## Out of Scope

- New features (screenshots, visual regression, ownership) — existing functionality only
- UI/frontend changes — CLI plugin only
- Breaking API changes to scripts — internal refactors preserve function signatures where possible
- Unrelated refactoring — only touch files listed above
