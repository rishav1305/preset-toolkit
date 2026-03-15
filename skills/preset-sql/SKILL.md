---
name: preset-sql
description: "Execute arbitrary SQL queries against Preset databases"
---

# SQL Execution

Execute SQL queries directly against Preset workspace databases via `sup sql`.

## Conversation Principles (MANDATORY)

**NEVER ask about:**
- Config formats, file paths, YAML structure, directory layout
- Which scripts to run, CLI flags, sync modes, technical parameters
- Auth methods, tokens, API endpoints, CSRF handling
- Git branches, merge strategies, commit messages
- Infrastructure, server details, environment setup

**ONLY ask about:**
- Business intent: "What data do you want to query?"
- Data correctness: "The query returned 1,200 rows. Does that look right?"
- Schema specifics: "Which table contains the order data?"
- Approval gates: "Run this query?"

## Prerequisites

```python
from scripts.config import ToolkitConfig
from scripts.sql import execute_sql
from scripts.formatter import format_output

config = ToolkitConfig.discover()
```

## Intent Routing

| User says | Function | Key args |
|-----------|----------|----------|
| "run SELECT * FROM orders", "execute this SQL" | `execute_sql(config, query="SELECT * FROM orders")` | |
| "query the database for active users" | `execute_sql(config, query="SELECT * FROM users WHERE active = 1")` | |
| "run this on database 5: SELECT 1" | `execute_sql(config, query="SELECT 1", database_id=5)` | |
| "show me the first 10 orders" | `execute_sql(config, query="SELECT * FROM orders", limit=10)` | |
| "how many active users?" | `execute_sql(config, query="SELECT COUNT(*) FROM users WHERE active = 1")` | |
| "show me the orders table" | `execute_sql(config, query="SELECT * FROM orders", limit=100)` | |

## Execution

1. Parse user intent and extract SQL query, optional database_id, optional limit
2. Call `execute_sql(config, query=..., database_id=..., limit=...)`
3. Display results using `format_output(result, fmt="table")`
4. For errors, explain what went wrong in business terms

## Output Formatting

Use `format_output()` for all results:

```python
result = execute_sql(config, query="SELECT * FROM orders", limit=10)
print(format_output(result, fmt="table"))
```

The user can request JSON or YAML output:
- "run this SQL as json" -> `format_output(result, fmt="json")`
- "query as yaml" -> `format_output(result, fmt="yaml")`
