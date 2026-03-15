<p align="center">
  <img src="https://img.shields.io/badge/Claude_Code-Plugin-blueviolet?style=for-the-badge" alt="Claude Code Plugin" />
  <img src="https://img.shields.io/badge/Preset-Dashboard_Toolkit-orange?style=for-the-badge" alt="Preset Dashboard Toolkit" />
  <img src="https://img.shields.io/badge/version-0.8.0-green?style=for-the-badge" alt="Version 0.8.0" />
  <img src="https://img.shields.io/badge/tests-196_passing-brightgreen?style=for-the-badge" alt="196 Tests Passing" />
  <img src="https://img.shields.io/badge/license-BUSL_1.1-blue?style=for-the-badge" alt="License" />
</p>

# preset-toolkit

**Stop breaking dashboards.** A Claude Code plugin that makes Preset/Superset dashboard management safe, collaborative, and mistake-proof.

One command — `/preset-toolkit:preset` — gives your team pull, push, validation, screenshots, visual regression, and ownership guardrails. No more pushing stale data, overwriting someone's work, or losing CSS.

---

## Install

```bash
# From the Claude Code official marketplace
/plugin install preset-toolkit

# Or install directly from GitHub
/plugin install github:rishav1305/preset-toolkit
```

**Prerequisites:** Python 3.8+ and [Claude Code](https://claude.ai/code) with plugin support.

---

## How It Works

```
You say:                              preset-toolkit does:
───────────────────────────────────── ──────────────────────────────────────
/preset-toolkit:preset pull           Pull → Dedup → Fingerprint check
/preset-toolkit:preset push           Validate → Markers → Push → CSS → Verify
/preset-toolkit:preset screenshot     Launch browser → Capture → Save PNGs
/preset-toolkit:preset diff           Compare screenshots → Flag regressions
/preset-toolkit:preset "push my       NLP routing → Same safe workflow
  revenue edits"
```

### The Safety Net

```
                    ┌─────────────────────────────────────────┐
                    │         /preset-toolkit:preset push      │
                    └────────────────┬────────────────────────┘
                                     │
                    ┌────────────────▼────────────────────────┐
                    │  1. Validate (sup sync --dry-run)        │
                    │  2. Check markers in SQL                 │
                    │  3. Fingerprint check (stale data?)      │
                    │  4. Ownership warnings                   │
                    └────────────────┬────────────────────────┘
                                     │ All clear?
                          ┌──────────┴──────────┐
                          │                     │
                    ┌─────▼──────┐       ┌──────▼─────┐
                    │ sup sync   │       │  REST API  │
                    │ (charts +  │       │  (CSS +    │
                    │  datasets) │       │  position) │
                    └─────┬──────┘       └──────┬─────┘
                          │                     │
                    ┌─────▼─────────────────────▼─────┐
                    │  5. Post-push verify              │
                    │     (pull-back + marker recheck)  │
                    └──────────────────────────────────┘
```

> **Why two-stage push?** `sup sync` overwrites dashboard CSS. preset-toolkit pushes charts/datasets via CLI, then CSS/position via REST API separately — so your styles are never lost.

---

## Quick Start

```bash
# 1. Install the plugin
/plugin install preset-toolkit

# 2. Create a project folder and set up
mkdir my-dashboard && cd my-dashboard
/preset-toolkit:preset-setup

# 3. Pull, edit, push
/preset-toolkit:preset pull
# ... make your changes ...
/preset-toolkit:preset push
```

Setup handles everything: virtual environment, dependencies (`superset-sup`, Playwright + Chromium), auth configuration, and `sync_config.yml` creation.

---

## Features

| Feature | What it does |
|---------|-------------|
| **Smart routing** | `/preset-toolkit:preset` + anything — natural language or direct commands |
| **Content fingerprinting** | Per-file SHA-256 map detects stale pulls before you push |
| **Marker validation** | Required strings must exist in SQL — catches accidental deletions |
| **Visual regression** | Pixel-diff screenshots catch layout changes invisible in code |
| **Section ownership** | Advisory warnings when you touch someone else's tiles |
| **Deduplication** | Auto-removes duplicate chart/dataset YAMLs by UUID |
| **Safe YAML** | Never uses `yaml.dump()` — string replacement preserves formatting |
| **Post-push verify** | Automatic pull-back and recheck after every push |
| **Zero-login screenshots** | Auto-extracts cookies from Chrome/Firefox/Edge/Arc — falls back to interactive login |

---

## Skills (18)

| # | Skill | Invoke with | Purpose |
|---|-------|-------------|---------|
| 1 | Router | `/preset-toolkit:preset` | Interactive menu + NLP routing |
| 2 | Setup | `/preset-toolkit:preset-setup` | First-time project wizard |
| 3 | Pull | `/preset-toolkit:preset-sync-pull` | Pull + dedup + fingerprint |
| 4 | Push | `/preset-toolkit:preset-sync-push` | Validate + push + CSS + verify |
| 5 | Validate | `/preset-toolkit:preset-validate` | Health check (markers + dry-run) |
| 6 | Screenshot | `/preset-toolkit:preset-screenshot` | Capture dashboard screenshots |
| 7 | Visual Diff | `/preset-toolkit:preset-visual-regression` | Pixel-level regression comparison |
| 8 | Code Review | `/preset-toolkit:preset-code-review` | Change review checklist |
| 9 | Ownership | `/preset-toolkit:preset-ownership` | Section ownership warnings |
| 10 | Troubleshoot | `/preset-toolkit:preset-troubleshoot` | Decision tree for common issues |
| 11 | Checkpoint | `/preset-toolkit:preset-checkpoint` | Daily pull + validate + screenshot + diff |
| 12 | Brainstorm | `/preset-toolkit:preset-brainstorming` | Plan dashboard changes conversationally |
| 13 | Write Plans | `/preset-toolkit:preset-writing-plans` | Break changes into safe execution steps |
| 14 | Execute Plans | `/preset-toolkit:preset-executing-plans` | Execute plans with validation checkpoints |
| 15 | Testing | `/preset-toolkit:preset-testing` | TDD loop: change → validate → push → verify |
| 16 | Debugging | `/preset-toolkit:preset-debugging` | Systematic debugging with known failure modes |
| 17 | Chart Ops | `/preset-toolkit:preset-chart` | List, inspect, query, pull, push charts |
| 18 | Dataset Ops | `/preset-toolkit:preset-dataset` | List, inspect, query, pull, push datasets |

Or just describe what you want:

```
/preset-toolkit:preset I want to push my revenue changes
/preset-toolkit:preset what's the current state of the dashboard?
/preset-toolkit:preset something looks wrong with the tiles
```

---

## Visual Regression

Catch what code review can't — visual changes to your dashboard layout.

```
  Baseline (last push)          Current (after changes)         Diff (auto-generated)
┌──────────────────────┐    ┌──────────────────────┐    ┌──────────────────────┐
│  ┌──────┐ ┌──────┐   │    │  ┌──────┐ ┌──────┐   │    │  ┌──────┐ ┌──────┐   │
│  │ Rev  │ │ DAU  │   │    │  │ Rev  │ │ DAU  │   │    │  │      │ │      │   │
│  └──────┘ └──────┘   │    │  └──────┘ └──────┘   │    │  └──────┘ └──────┘   │
│  ┌────────────────┐   │    │  ┌─────┐ ┌────────┐  │    │  ┌─────┐ ┌────────┐  │
│  │    Chart A     │   │    │  │  A  │ │   B    │  │    │  │█████│ │████████│  │
│  └────────────────┘   │    │  └─────┘ └────────┘  │    │  └─────┘ └────────┘  │
└──────────────────────┘    └──────────────────────┘    └──────────────────────┘
                                                          █ = changed pixels
```

```bash
/preset-toolkit:preset screenshot   # Capture baselines
# ... make changes ...
/preset-toolkit:preset diff         # Compare — flags >1% pixel difference
```

Uses Pillow for pixel comparison with configurable color tolerance for anti-aliasing.

---

## Section Ownership

Define who owns what. Get warnings — never blocks.

```yaml
# .preset-toolkit/ownership.yaml
sections:
  revenue:
    owner: "alice@company.com"
    charts: [2085, 2088]
  audience:
    owner: "bob@company.com"
    charts: [2084]
shared_datasets:
  - name: "Main_Dataset"
    owners: ["alice@company.com", "bob@company.com"]
    advisory: "Notify all owners before editing."
```

```
  Chart 2085 belongs to 'revenue' (owned by alice@company.com).
  Notify them before pushing.
```

---

## Auth

The plugin uses two CLIs with separate auth:

**sup CLI** (for all sync operations — pull/push/validate/CSS):
```bash
# Interactive setup — stores credentials locally
.venv/bin/sup config
```

**Environment variables** (for REST API CSS push):
```bash
export PRESET_API_TOKEN="your-token"
export PRESET_API_SECRET="your-secret"
```

Get API keys from **Preset > Settings > API Keys**.

> HTTPS is enforced — the toolkit refuses to send credentials over plaintext HTTP.

---

## Configuration

Created by `/preset-toolkit:preset-setup` at `.preset-toolkit/config.yaml`:

```yaml
version: 1

workspace:
  url: "https://your-workspace.us2a.app.preset.io"
  id: "your-workspace-id"

dashboard:
  id: 76
  name: "My Dashboard"

sync:
  folder: "sync"

screenshots:
  folder: "screenshots"
  navigation_timeout: 60

validation:
  markers_file: ".preset-toolkit/markers.txt"

css:
  max_length: 30000        # Preset truncates at ~33K
  push_via_api: true
```

Setup also creates `sync/sync_config.yml` (required by the `sup` CLI):

```yaml
source:
  workspace_id: 2194154     # Numeric workspace ID
  assets:
    dashboards:
      selection: ids
      ids: [76]
      include_dependencies: true
target_defaults:
  overwrite: true
targets:
- workspace_id: 2194154
  name: my_dashboard
```

<details>
<summary><strong>Telemetry (optional)</strong></summary>

Anonymous, opt-in usage telemetry via PostHog. Inert unless configured:

```bash
export POSTHOG_API_KEY="your-posthog-project-key"
```

Also requires `telemetry.enabled: true` in config. No data is ever sent without both conditions met.

</details>

---

## Architecture

```
preset-toolkit/
├── .claude-plugin/           Plugin metadata (plugin.json, marketplace.json)
├── hooks/                    Session auto-detection
├── skills/                   18 skills (each with SKILL.md)
│   ├── preset/               Router — single entry point
│   ├── preset-setup/         First-time wizard
│   ├── preset-sync-pull/     Pull + dedup + fingerprint
│   ├── preset-sync-push/     Validate + push + CSS + verify
│   ├── preset-validate/      Health checks
│   ├── preset-screenshot/    Playwright browser capture
│   ├── preset-visual-regression/  Pixel-diff comparison
│   ├── preset-chart/         Individual chart operations
│   ├── preset-dataset/       Individual dataset operations
│   ├── preset-code-review/   Change review checklist
│   ├── preset-ownership/     Section ownership warnings
│   ├── preset-troubleshoot/  Diagnostic decision tree
│   ├── preset-checkpoint/    Daily pull + validate + screenshot
│   ├── preset-brainstorming/ Change planning
│   ├── preset-writing-plans/ Execution step breakdown
│   ├── preset-executing-plans/  Plan execution with checkpoints
│   ├── preset-testing/       TDD loop
│   └── preset-debugging/     Systematic debugging
├── agents/                   Visual diff + conflict check agents
├── references/               Preset knowledge base (7 docs)
├── scripts/                  Python automation (15 modules)
│   ├── sync.py               Pull/push orchestrator (uses sup CLI)
│   ├── chart.py              Chart operations (list/info/sql/data/pull/push)
│   ├── dataset.py            Dataset operations (list/info/sql/data/pull/push)
│   ├── push_dashboard.py     REST API push (CSS/position)
│   ├── screenshot.py         Playwright browser capture + auth fallback
│   ├── browser_cookies.py    Cookie extraction from Chrome/Firefox/Edge/Arc
│   ├── visual_diff.py        Pixel comparison (Pillow)
│   ├── fingerprint.py        Per-file SHA-256 content hashing
│   ├── dedup.py              UUID duplicate removal
│   ├── ownership.py          Section ownership checks
│   ├── config.py             Config reader + validation
│   ├── http.py               Retry with exponential backoff + jitter
│   ├── deps.py               Dependency management
│   ├── telemetry.py          Anonymous opt-in telemetry
│   ├── logger.py             Structured logging + secret sanitization
│   └── bootstrap.sh          Venv + dependency installer
├── templates/                Project scaffolding files
└── tests/                    156 tests (unit + integration)
```

### Dependencies

Installed automatically by setup into a project-local `.venv/`:

| Package | Purpose |
|---------|---------|
| `superset-sup` | `sup` CLI — sync pull/push/validate |
| `playwright` + Chromium | Browser-based screenshot capture |
| `PyYAML` | YAML parsing |
| `Pillow` | Image comparison for visual regression |
| `httpx` | HTTP client with retry support |
| `cryptography` | AES decryption for Chromium cookie extraction |

---

## For Contributors

### Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

All 196 tests pass in ~9 seconds.

### Design Principles

- **Never `yaml.dump()`** — string replacement preserves YAML formatting
- **Two-stage push** — CLI for data, REST API for presentation
- **Advisory ownership** — warns, never blocks
- **Business questions only** — skills never ask technical/infra questions
- **Fail safe** — every external call has retries, timeouts, and error handling
- **No auto-install outside setup** — pull/push/screenshot fail fast if deps are missing

### Adding a skill

1. Create `skills/your-skill/SKILL.md` with `name` and `description` frontmatter
2. Follow the Conversation Principles (never ask technical questions)
3. Add routing logic to `skills/preset/SKILL.md`
4. Reference relevant `references/*.md` docs

---

## License

Business Source License 1.1 — see [LICENSE](LICENSE) for details.
Converts to Apache License 2.0 on 2030-03-13.
