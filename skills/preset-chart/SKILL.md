---
name: preset-chart
description: "List, inspect, query, pull, and push individual Preset charts"
---

# Chart Operations

Operate on individual Preset charts: list, inspect metadata, view SQL, get data, pull, and push.

## Conversation Principles (MANDATORY)

**NEVER ask about:**
- Config formats, file paths, YAML structure, directory layout
- Which scripts to run, CLI flags, sync modes, technical parameters
- Auth methods, tokens, API endpoints, CSRF handling
- Git branches, merge strategies, commit messages
- Infrastructure, server details, environment setup

**ONLY ask about:**
- Business intent: "Which chart do you want to inspect?"
- Data correctness: "The chart shows $3M revenue. Does that look right?"
- Visual specifics: "Should the chart type be 'line' or 'bar'?"
- Ownership clarity: "This chart is in Bob's section. Notify him?"
- Approval gates: "Pull these 3 charts?"

## Prerequisites

```python
from scripts.config import ToolkitConfig
from scripts.chart import list_charts, get_chart_info, get_chart_sql, get_chart_data, pull_charts, push_charts
from scripts.formatter import format_output

config = ToolkitConfig.discover()
```

## Intent Routing

| User says | Function | Key args |
|-----------|----------|----------|
| "list charts", "show all charts", "what charts exist" | `list_charts(config)` | |
| "list my charts", "my charts" | `list_charts(config, mine=True)` | |
| "find revenue charts", "search for X" | `list_charts(config, search="revenue")` | |
| "show chart 2085", "chart info 2085", "details for 2085" | `get_chart_info(config, chart_id=2085)` | |
| "what SQL does chart 2085 use?", "sql for 2085" | `get_chart_sql(config, chart_id=2085)` | |
| "get data from chart 2088", "run chart 2088" | `get_chart_data(config, chart_id=2088)` | |
| "pull chart 2085", "download chart 2085" | `pull_charts(config, chart_id=2085)` | |
| "pull charts 2085,2088,2090" | `pull_charts(config, chart_ids="2085,2088,2090")` | |
| "push charts", "upload charts" | `push_charts(config)` | |

## Execution

1. Parse user intent and extract chart IDs if mentioned
2. Call the appropriate function
3. Display results using `format_output(result, fmt="table")`
4. For errors, explain what went wrong in business terms

## Output Formatting

Use `format_output()` for all results:

```python
result = list_charts(config, mine=True)
print(format_output(result, fmt="table"))
```

The user can request JSON or YAML output:
- "show chart 2085 as json" -> `format_output(result, fmt="json")`
- "list charts as yaml" -> `format_output(result, fmt="yaml")`
