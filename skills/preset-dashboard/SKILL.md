---
name: preset-dashboard
description: "List, inspect, and pull individual Preset dashboards"
---

# Dashboard Operations

Operate on individual Preset dashboards: list, inspect metadata, and pull.

## Conversation Principles (MANDATORY)

**NEVER ask about:**
- Config formats, file paths, YAML structure, directory layout
- Which scripts to run, CLI flags, sync modes, technical parameters
- Auth methods, tokens, API endpoints, CSRF handling
- Git branches, merge strategies, commit messages
- Infrastructure, server details, environment setup

**ONLY ask about:**
- Business intent: "Which dashboard do you want to inspect?"
- Data correctness: "The dashboard has 12 charts. Does that look right?"
- Visual specifics: "Should the dashboard include the marketing section?"
- Ownership clarity: "This dashboard is shared. Notify the other owners?"
- Approval gates: "Pull these 2 dashboards?"

## Prerequisites

```python
from scripts.config import ToolkitConfig
from scripts.dashboard import list_dashboards, get_dashboard_info, pull_dashboards
from scripts.formatter import format_output

config = ToolkitConfig.discover()
```

## Intent Routing

| User says | Function | Key args |
|-----------|----------|----------|
| "list dashboards", "show all dashboards", "what dashboards exist" | `list_dashboards(config)` | |
| "list my dashboards", "my dashboards" | `list_dashboards(config, mine=True)` | |
| "find sales dashboards", "search for X" | `list_dashboards(config, search="sales")` | |
| "show dashboard 76", "dashboard info 76", "details for dashboard 76" | `get_dashboard_info(config, dashboard_id=76)` | |
| "pull dashboard 76", "download dashboard 76" | `pull_dashboards(config, dashboard_id=76)` | |
| "pull dashboards 76,89,102" | `pull_dashboards(config, dashboard_ids=[76, 89, 102])` | |

## Execution

1. Parse user intent and extract dashboard IDs if mentioned
2. Call the appropriate function
3. Display results using `format_output(result, fmt="table")`
4. For errors, explain what went wrong in business terms

## Output Formatting

Use `format_output()` for all results:

```python
result = list_dashboards(config, mine=True)
print(format_output(result, fmt="table"))
```

The user can request JSON or YAML output:
- "show dashboard 76 as json" -> `format_output(result, fmt="json")`
- "list dashboards as yaml" -> `format_output(result, fmt="yaml")`
