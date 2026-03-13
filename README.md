<p align="center">
  <img src="https://img.shields.io/badge/Claude_Code-Plugin-blueviolet?style=for-the-badge" alt="Claude Code Plugin" />
  <img src="https://img.shields.io/badge/Preset-Dashboard_Toolkit-orange?style=for-the-badge" alt="Preset Dashboard Toolkit" />
  <img src="https://img.shields.io/badge/tests-102_passing-brightgreen?style=for-the-badge" alt="102 Tests Passing" />
  <img src="https://img.shields.io/badge/license-BUSL_1.1-blue?style=for-the-badge" alt="License" />
</p>

# preset-toolkit

**Stop breaking dashboards.** A Claude Code plugin that makes Preset/Superset dashboard management safe, collaborative, and mistake-proof.

One command — `/preset` — gives your team pull, push, validation, screenshots, visual regression, and ownership guardrails. No more pushing stale data, overwriting someone's work, or losing CSS.

---

## How It Works

```
You say:                        preset-toolkit does:
─────────────────────────────── ──────────────────────────────────────
/preset pull                    Pull → Dedup → Fingerprint check
/preset push                    Validate → Markers → Push → CSS → Verify
/preset screenshot              Launch browser → Capture → Save PNGs
/preset diff                    Compare screenshots → Flag regressions
/preset "push my revenue edits" NLP routing → Same safe workflow
```

### The Safety Net

```
                    ┌─────────────────────────────────────────┐
                    │            /preset push                  │
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
# Install the plugin
/plugin install preset-toolkit

# Set up a dashboard project
mkdir my-dashboard && cd my-dashboard
/preset setup

# Start working
/preset pull
# ... make your changes ...
/preset push
```

**Prerequisites:** Python 3.8+ and [Claude Code](https://claude.ai/code) with plugin support.

---

## Features

| Feature | What it does |
|---------|-------------|
| **Smart routing** | Say `/preset` + anything — natural language or direct commands |
| **Content fingerprinting** | SHA-256 hash detects stale pulls before you push |
| **Marker validation** | Required strings must exist in SQL — catches accidental deletions |
| **Visual regression** | Pixel-diff screenshots catch layout changes invisible in code |
| **Section ownership** | Advisory warnings when you touch someone else's tiles |
| **Deduplication** | Auto-removes duplicate chart/dataset YAMLs by UUID |
| **Safe YAML** | Never uses `yaml.dump()` — string replacement preserves formatting |
| **Post-push verify** | Automatic pull-back and recheck after every push |

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
/preset screenshot        # Capture baselines
# ... make changes ...
/preset diff              # Compare — flags >1% pixel difference
```

Uses NumPy-accelerated comparison when available, with color tolerance for anti-aliasing.

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
⚠ Chart 2085 belongs to 'revenue' (owned by alice@company.com).
  Notify them before pushing.
```

---

## Commands

```
/preset                         Interactive menu
/preset setup                   First-time project wizard
/preset pull                    Pull + dedup + fingerprint
/preset push                    Full validation pipeline + push
/preset push --css-only         Push only CSS/position via API
/preset screenshot              Capture dashboard screenshots
/preset diff                    Visual regression comparison
/preset check                   Health check (validate + markers)
/preset status                  Show config and last push info
/preset help                    Contextual help
```

Or just describe what you want:

```
/preset I want to push my revenue changes
/preset what's the current state of the dashboard?
/preset something looks wrong with the tiles
```

---

## Auth

**Environment variables** (recommended):
```bash
export PRESET_API_TOKEN="your-token"
export PRESET_API_SECRET="your-secret"
```

**File-based** (set `auth.method: "file"` in config):
```
# .preset-toolkit/.secrets/keys.txt  (auto-gitignored)
PRESET_API_TOKEN=your-token
PRESET_API_SECRET=your-secret
```

> HTTPS is enforced — the toolkit refuses to send credentials over plaintext HTTP.

---

## Configuration

Created by `/preset setup` at `.preset-toolkit/config.yaml`:

```yaml
workspace:
  url: "https://your-workspace.us2a.app.preset.io"
  id: "12345"
dashboard:
  id: 76
  name: "My Dashboard"
screenshots:
  wait_seconds: 15
  navigation_timeout: 60      # seconds
  mask_selectors:
    - ".header-with-actions"   # hide dynamic elements
visual_regression:
  threshold: 0.01              # 1% pixel diff tolerance
css:
  max_length: 30000            # Preset truncates at ~33K
  push_via_api: true
validation:
  markers_file: ".preset-toolkit/markers.txt"
  require_markers_before_push: true
  verify_after_push: true
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
├── .claude-plugin/           Plugin metadata
├── hooks/                    Session auto-detection
├── skills/
│   ├── preset-toolkit/       Router (single /preset entry point)
│   └── _internal/            15 internal skills
├── agents/                   Visual diff + conflict check
├── references/               Preset knowledge base (7 docs)
├── scripts/                  Python automation
│   ├── config.py             Config reader + validation
│   ├── sync.py               Pull/push orchestrator
│   ├── push_dashboard.py     REST API push (CSS/position)
│   ├── screenshot.py         Playwright browser capture
│   ├── visual_diff.py        Pixel comparison (NumPy + Pillow)
│   ├── fingerprint.py        SHA-256 content hashing
│   ├── dedup.py              UUID duplicate removal
│   ├── ownership.py          Section ownership checks
│   ├── http.py               Retry with exponential backoff + jitter
│   ├── telemetry.py          Anonymous opt-in telemetry
│   ├── deps.py               Auto-install missing dependencies
│   └── logger.py             Structured logging
├── templates/                Project scaffolding
└── tests/                    102 tests (unit + integration)
```

---

## For Contributors

### Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### Design Principles

- **Never `yaml.dump()`** — string replacement preserves YAML formatting
- **Two-stage push** — CLI for data, REST API for presentation
- **Advisory ownership** — warns, never blocks
- **Business questions only** — skills never ask technical/infra questions
- **Fail safe** — every external call has retries, timeouts, and error handling

### Adding a skill

1. Create `skills/_internal/your-skill/SKILL.md`
2. Add frontmatter: `name`, `description` (start with "Use when...")
3. Reference relevant `references/*.md` docs
4. Add routing logic to `skills/preset-toolkit/SKILL.md`

---

## License

Business Source License 1.1 — see [LICENSE](LICENSE) for details.
Converts to Apache License 2.0 on 2030-03-13.
