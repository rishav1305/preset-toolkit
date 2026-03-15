---
name: preset-dataset
description: "List, inspect, query, pull, and push individual Preset datasets"
---

# Dataset Operations

Operate on individual Preset datasets: list, inspect metadata, view SQL, get data, pull, and push.

## Conversation Principles (MANDATORY)

**NEVER ask about:**
- Config formats, file paths, YAML structure, directory layout
- Which scripts to run, CLI flags, sync modes, technical parameters
- Auth methods, tokens, API endpoints, CSRF handling
- Git branches, merge strategies, commit messages
- Infrastructure, server details, environment setup

**ONLY ask about:**
- Business intent: "Which dataset do you want to inspect?"
- Data correctness: "The dataset has 1.2M rows. Does that look right?"
- Schema specifics: "Should the join be on order_id or customer_id?"
- Ownership clarity: "This dataset is shared. Notify the other owners?"
- Approval gates: "Pull these 2 datasets?"

## Prerequisites

```python
from scripts.config import ToolkitConfig
from scripts.dataset import list_datasets, get_dataset_info, get_dataset_sql, get_dataset_data, pull_datasets, push_datasets
from scripts.formatter import format_output

config = ToolkitConfig.discover()
```

## Intent Routing

| User says | Function | Key args |
|-----------|----------|----------|
| "list datasets", "show all datasets", "what datasets exist" | `list_datasets(config)` | |
| "list my datasets", "my datasets" | `list_datasets(config, mine=True)` | |
| "find orders dataset", "search for X" | `list_datasets(config, search="orders")` | |
| "show dataset 42", "dataset info 42", "details for dataset 42" | `get_dataset_info(config, dataset_id=42)` | |
| "what SQL does dataset 42 use?", "sql for dataset 42" | `get_dataset_sql(config, dataset_id=42)` | |
| "get data from dataset 42", "sample dataset 42" | `get_dataset_data(config, dataset_id=42)` | |
| "pull dataset 42", "download dataset 42" | `pull_datasets(config, dataset_id=42)` | |
| "pull datasets 42,43,44" | `pull_datasets(config, dataset_ids=[42, 43, 44])` | |
| "push datasets", "upload datasets" | `push_datasets(config)` | |

## Execution

1. Parse user intent and extract dataset IDs if mentioned
2. Call the appropriate function
3. Display results using `format_output(result, fmt="table")`
4. For errors, explain what went wrong in business terms

## Output Formatting

Use `format_output()` for all results:

```python
result = list_datasets(config, mine=True)
print(format_output(result, fmt="table"))
```

The user can request JSON or YAML output:
- "show dataset 42 as json" -> `format_output(result, fmt="json")`
- "list datasets as yaml" -> `format_output(result, fmt="yaml")`
