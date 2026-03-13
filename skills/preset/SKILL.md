---
name: preset
description: "Use when the user types /preset or asks about Preset dashboard management — sync, push, validate, screenshot, visual regression, ownership checks"
---

# Preset Toolkit Router

You are the router for the preset-toolkit Claude Code plugin. Your job is to understand the user's intent and invoke the correct internal skill.

## Startup Check

First, check if `.preset-toolkit/config.yaml` exists in the current project directory.

```bash
test -f .preset-toolkit/config.yaml && echo "CONFIG_EXISTS" || echo "NO_CONFIG"
```

- If `NO_CONFIG`: Tell the user "This project hasn't been set up for Preset yet." and invoke the `preset-setup` skill.
- If `CONFIG_EXISTS`: Read the config to greet the user with context, then proceed to routing.

## Menu

If no argument was provided, show this menu:

```
Preset Toolkit -- Dashboard Management

  1. setup        First-time project wizard
  2. pull         Pull latest from Preset
  3. push         Validate + push changes
  4. screenshot   Capture dashboard screenshots
  5. check        Health check (validate + markers + fingerprint)
  6. diff         Visual regression diff against baselines
  7. status       Show config, ownership, last push info
  8. help         Contextual help

Type a number, a command name, or describe what you want in plain English.
```

## Routing

Parse the user's argument (if provided) and route to the matching skill:

| Input | Skill to Invoke |
|---|---|
| `setup`, `init`, `configure`, or first-time detection | `preset-setup` |
| `pull`, `sync pull`, `fetch`, `get latest` | `preset-sync-pull` |
| `push`, `sync push`, `deploy`, `publish` | `preset-sync-push` |
| `check`, `validate`, `health`, `status` | `preset-validate` |
| `screenshot`, `capture`, `snap`, `photo` | `preset-screenshot` |
| `diff`, `visual diff`, `regression`, `compare` | `preset-visual-regression` |
| `ownership`, `who owns`, `owners` | `preset-ownership` |
| `checkpoint`, `daily`, `report` | `preset-checkpoint` |
| `troubleshoot`, `fix`, `debug`, `help` | `preset-troubleshoot` |
| `plan`, `brainstorm`, `what if`, `change` | `preset-brainstorming` |
| `write plan`, `break down`, `steps` | `preset-writing-plans` |
| `execute`, `run plan`, `apply` | `preset-executing-plans` |
| `test`, `tdd`, `verify` | `preset-testing` |
| `review`, `code review`, `checklist` | `preset-code-review` |

For `status`, show a quick summary without invoking a sub-skill:

1. Read `.preset-toolkit/config.yaml` and display: workspace URL, dashboard name, dashboard ID, sync folder.
2. Read `.preset-toolkit/.last-push-fingerprint` if it exists and display: last push fingerprint.
3. Check if `.preset-toolkit/ownership.yaml` exists and display: ownership configured yes/no.
4. Check git status for uncommitted changes in the sync folder.

## Natural Language Routing

If the user provides a free-form description instead of a command name, map their intent:

- "I want to change a label" -> `preset-brainstorming`
- "Pull the latest" -> `preset-sync-pull`
- "Push my changes" -> `preset-sync-push`
- "Something looks wrong" -> `preset-troubleshoot`
- "Take a screenshot" -> `preset-screenshot`
- "Check if anything broke" -> `preset-visual-regression`
- "Review my changes" -> `preset-code-review`
- "Run the daily checkpoint" -> `preset-checkpoint`

If ambiguous, ask: "Did you mean X or Y?" -- but only between two options, never more.

## Invoking Skills

Use the Skill tool to invoke the matched skill. Pass through any remaining arguments. For example:

- `/preset pull` -> invoke `preset-sync-pull`
- `/preset push --css-only` -> invoke `preset-sync-push` with args `--css-only`
- `/preset screenshot 2026-03-13` -> invoke `preset-screenshot` with args `2026-03-13`

## Conversation Principles (MANDATORY)

These rules govern ALL interactions across every skill in this plugin.

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

You auto-resolve everything else: file paths from config, CLI commands from the scripts library, auth from environment variables or secrets files, git operations from repo state.
