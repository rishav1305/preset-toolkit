# preset-toolkit

A Claude Code plugin for safe, collaborative Preset/Superset dashboard management. One command (`/preset`) gives you pull, push, validation, screenshots, visual regression testing, and section ownership — designed so anyone on your team can manage dashboards without making mistakes.

## Quick Start

```bash
# 1. Install the plugin
/plugin install preset-toolkit

# 2. Create a project folder and set up
mkdir my-dashboard && cd my-dashboard
/preset setup

# 3. Start working
/preset pull          # Pull latest from Preset
# ... make changes ...
/preset push          # Validate + push (with approval gate)
```

## What It Does

preset-toolkit wraps the Preset CLI (`sup`) and REST API into a safe, guided workflow. It prevents the most common mistakes teams make when collaborating on dashboards: pushing stale data, overwriting someone else's work, losing CSS changes, and breaking visual layouts.

## Features

- **Single entry point** — `/preset` routes to the right action based on what you say
- **One folder per dashboard** — no cross-contamination between dashboards
- **Content fingerprinting** — detects stale pulls and regressions before you push
- **Marker validation** — required strings must exist in dataset SQL before any push
- **Visual regression** — pixel-diff screenshots against baselines to catch layout changes
- **Section ownership** — advisory warnings when editing tiles owned by someone else
- **Two-stage push** — datasets/charts via `sup sync`, CSS/position via REST API (because `sup sync` overwrites CSS)
- **Safe YAML editing** — built-in guardrails against `yaml.dump()` corruption
- **Post-push verification** — automatic pull-back and marker check after every push
- **Built-in reference docs** — Preset CLI, API, CSS, and common pitfalls bundled as knowledge base

## Prerequisites

- Python 3.8+
- [Preset CLI](https://github.com/preset-io/preset-cli) (`pip install preset-cli`)
- Claude Code with plugin support

For screenshots and visual regression:
```bash
pip install playwright && playwright install chromium
```

## Installation

```bash
/plugin install preset-toolkit
```

## Usage

### Interactive Menu
```
/preset                     → Show menu with all options
```

### Direct Commands
```
/preset setup               → First-time project wizard
/preset pull                → Pull latest from Preset + dedup + fingerprint check
/preset push                → Validate + markers + push + CSS + verify
/preset screenshot          → Capture dashboard screenshots
/preset check               → Health check (validate + markers + fingerprint)
/preset diff                → Visual regression diff against baselines
/preset status              → Show config, ownership, last push info
/preset help                → Contextual help
```

### Natural Language
```
/preset I want to push my revenue changes
/preset what's the current state of the dashboard?
/preset something looks wrong with the tiles
```

## Configuration

### `.preset-toolkit/config.yaml`

Created by `/preset setup`. Key settings:

```yaml
version: 1
workspace:
  url: "https://your-workspace.us2a.app.preset.io"
  id: "12345"
dashboard:
  id: 76
  name: "My Dashboard"
  sync_folder: "sync"
auth:
  method: "env"              # or "file" for .secrets/keys.txt
screenshots:
  wait_seconds: 15
  mask_selectors:
    - ".header-with-actions"
visual_regression:
  threshold: 0.01            # 1% pixel diff tolerance
css:
  max_length: 30000          # Preset truncates at ~33K
  push_via_api: true
validation:
  markers_file: ".preset-toolkit/markers.txt"
  require_markers_before_push: true
  verify_after_push: true
user:
  email: "you@company.com"
```

### `.preset-toolkit/ownership.yaml`

Maps dashboard sections to owners:

```yaml
sections:
  revenue:
    owner: "alice@company.com"
    charts: [2085, 2088]
    description: "Revenue tiles and cards"
  audience:
    owner: "bob@company.com"
    charts: [2084]
    description: "WAU, DAU metrics"
shared_datasets:
  - name: "Main_Dataset"
    owners: ["alice@company.com", "bob@company.com"]
    advisory: "Shared dataset — notify all owners before editing."
```

### `.preset-toolkit/markers.txt`

Required strings that must exist in dataset SQL before push:

```
# One marker per line. Comments and blanks are ignored.
Revenue - Ads | Subs Sales
weekly_total_revenue_curr
wcbm-section__hdr
```

## Visual Regression Testing

```bash
# 1. Capture baselines (first time)
/preset screenshot

# 2. Make changes and push

# 3. Compare against baselines
/preset diff

# 4. If changes are intentional, approve to update baselines
```

The diff uses pixel-level comparison with Euclidean RGB color tolerance (handles anti-aliasing). Default threshold: 1% of pixels may differ before flagging a regression.

## Auth

Set your Preset API credentials:

```bash
export PRESET_API_TOKEN="your-token"
export PRESET_API_SECRET="your-secret"
```

Or use file-based auth (set `auth.method: "file"` in config):
```
# .preset-toolkit/.secrets/keys.txt
PRESET_API_TOKEN=your-token
PRESET_API_SECRET=your-secret
```

The `.secrets/` directory is gitignored by default.

## Project Structure

```
preset-toolkit/
├── .claude-plugin/plugin.json     # Plugin metadata
├── hooks/                         # Session auto-detection
├── skills/
│   ├── preset-toolkit/SKILL.md    # Router (single entry point)
│   └── _internal/                 # 15 internal skills
├── agents/                        # Visual diff + conflict check agents
├── references/                    # Preset knowledge base (7 docs)
├── scripts/                       # Python automation modules
│   ├── config.py                  # Config reader
│   ├── sync.py                    # Pull/push orchestrator
│   ├── dedup.py                   # UUID-based duplicate removal
│   ├── fingerprint.py             # SHA-256 hash + marker checks
│   ├── screenshot.py              # Playwright capture
│   ├── visual_diff.py             # Pixel comparison
│   ├── push_dashboard.py          # REST API push (CSS/position)
│   └── ownership.py               # Section ownership checking
├── templates/                     # Project scaffolding templates
└── tests/                         # 44 tests (unit + integration)
```

## For Contributors

### Adding a new skill

1. Create `skills/_internal/your-skill/SKILL.md`
2. Add frontmatter: `name`, `description` (start with "Use when...")
3. Include the Conversation Principles (never ask tech questions)
4. Reference relevant `references/*.md` docs
5. Add routing logic to `skills/preset-toolkit/SKILL.md`

### Running tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

### Key design decisions

- **Never `yaml.dump()`** — always use string replacement for YAML editing
- **Two-stage push** — `sup sync` for charts/datasets, REST API for CSS/position
- **Advisory-only ownership** — warnings, never blocks
- **Business questions only** — skills never ask tech/infra questions

## License

Business Source License 1.1 — see [LICENSE](LICENSE) for details. Converts to Apache License 2.0 on 2030-03-13.
