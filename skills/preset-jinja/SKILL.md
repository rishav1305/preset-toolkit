---
name: preset-jinja
description: "Validate Jinja2 expressions in dashboard SQL fields"
---

# Jinja Validation

Validate Jinja2 syntax in SQL fields across all dashboard YAML files.

## Conversation Principles (MANDATORY)

**NEVER ask about:**
- Config formats, file paths, YAML structure, directory layout
- Which scripts to run, CLI flags, sync modes, technical parameters
- Auth methods, tokens, API endpoints, CSRF handling
- Git branches, merge strategies, commit messages
- Infrastructure, server details, environment setup

**ONLY ask about:**
- Business intent: "Do you want to check all files or a specific one?"
- Data correctness: "Found 3 broken Jinja expressions. Want to see details?"
- Approval gates: "Fix these issues before pushing?"

## Prerequisites

```python
from scripts.config import ToolkitConfig
from scripts.jinja_check import scan_yaml_jinja, validate_jinja
from scripts.formatter import format_output

config = ToolkitConfig.discover()
```

## Intent Routing

| User says | Function | Key args |
|-----------|----------|----------|
| "check jinja", "validate jinja", "jinja health" | `scan_yaml_jinja(config)` | |
| "scan for jinja errors" | `scan_yaml_jinja(config)` | |
| "is the jinja syntax valid?" | `scan_yaml_jinja(config)` | |
| "any broken templates?" | `scan_yaml_jinja(config)` | |

## Execution

1. Call `scan_yaml_jinja(config)`
2. Display results using `format_output(result, fmt="table")`
3. If errors found, explain in business terms what's broken and suggest fixes
4. If all valid, confirm "All Jinja expressions are intact."

## Output Formatting

```python
result = scan_yaml_jinja(config)
print(format_output(result, fmt="table"))
```
