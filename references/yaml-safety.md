# Safe YAML Editing Patterns

## The Cardinal Rule

**NEVER use `yaml.dump()` to write Preset/Superset YAML files.**

This single rule prevents the majority of corruption issues. Here is why
`yaml.dump()` is dangerous and what to use instead.

## Why yaml.dump() Breaks Things

### Problem 1: Multi-Line String Re-encoding

Superset YAML files often contain SQL queries, JSON blobs, and HTML fragments
stored as single-line strings with embedded newlines (`\n`). `yaml.dump()`
re-encodes these using YAML's block scalar syntax (`|` or `>`), changing the
string representation and sometimes altering the actual content.

```yaml
# Original (correct — single-line with literal \n)
sql: "SELECT id,\n  name,\n  value\nFROM table"

# After yaml.dump() (broken — reformatted)
sql: |
  SELECT id,
    name,
    value
  FROM table
```

The reformatted version may parse differently, especially when trailing
whitespace or blank lines are involved.

### Problem 2: Jinja Template Corruption

Preset SQL commonly uses Jinja2 syntax for dynamic filters:

```sql
SELECT * FROM table
WHERE date = {{ filter_values('as_of_date')[0] }}
```

`yaml.dump()` may quote the curly braces, escape them, or wrap the entire
string in quotes that change how Jinja processes the template:

```yaml
# Original
sql: "...WHERE date = {{ filter_values('as_of_date')[0] }}"

# After yaml.dump() — may produce
sql: '...WHERE date = {{ filter_values(''as_of_date'')[0] }}'
```

The changed quoting can break Jinja parsing on import.

### Problem 3: Key Reordering

`yaml.dump()` sorts keys alphabetically by default. Superset import is
generally order-agnostic, but the diff noise makes it impossible to review
what actually changed. It also breaks any tooling that relies on field
positions (e.g., line-based grep checks).

### Problem 4: Quoting Changes

`yaml.dump()` applies its own quoting rules. A value like `"true"` (string)
might become `true` (boolean). A numeric string like `"2103"` might become
`2103` (integer). These type changes can cause subtle import failures.

## The Safe Pattern

### Step 1: Read Raw Content

```python
with open(filepath, 'r') as f:
    raw = f.read()
```

Always work with the raw string. This preserves exact formatting, quoting,
and whitespace.

### Step 2: Parse for Inspection (Optional)

```python
import yaml
data = yaml.safe_load(raw)
current_sql = data.get('sql', '')
```

Use `yaml.safe_load()` only to READ values — to understand what is in the
file, find the current value of a field, or validate structure. Never use
the parsed data to write back.

### Step 3: Apply Edits via String Replacement

```python
# Verify the target pattern exists
count = raw.count(old_pattern)
if count != 1:
    raise ValueError(f"Expected 1 occurrence, found {count}")

# Replace
new_raw = raw.replace(old_pattern, new_pattern, 1)
```

**Always verify the occurrence count before replacing.** This prevents:
- Replacing the wrong occurrence when a pattern appears multiple times
- Silently doing nothing when the pattern is not found (0 occurrences)

### Step 4: Validate the Result

```python
# Verify it's still valid YAML
result = yaml.safe_load(new_raw)

# Verify the field has the expected new value
assert new_value in result.get('sql', '')
```

### Step 5: Write Back

```python
with open(filepath, 'w') as f:
    f.write(new_raw)
```

## Working with SQL Fields

SQL in dataset YAML is typically stored on a single line with `\n` for
newlines. The `sql:` key value may be very long (thousands of characters).

### Finding the SQL Value

```python
data = yaml.safe_load(raw)
sql = data['sql']
# sql is now a Python string with actual newlines
```

### Modifying SQL

```python
# Find the exact substring to replace in the raw YAML
# The SQL is usually after "sql: " or "sql: |" on a single line
old_fragment = "SUM(revenue) AS total_revenue"
new_fragment = "SUM(revenue) AS total_ad_revenue"

if raw.count(old_fragment) != 1:
    raise ValueError("Pattern not unique or not found")

new_raw = raw.replace(old_fragment, new_fragment)
```

### Preserving Special Characters

Characters that must be preserved exactly:
- **Single quotes** in SQL: `WHERE status = 'active'`
- **Double quotes** in YAML string boundaries
- **Backslash-n** (`\n`): literal newline representation
- **Jinja braces**: `{{ }}` and `{% %}`
- **Backslashes** in regex: `REGEXP '\\d+'`

## Dataset Column Expressions

Dataset YAML files contain column definitions with `expression` fields. These
follow the same rules as SQL — edit via string replacement, not yaml.dump().

```yaml
columns:
- column_name: weekly_change_pct
  expression: "ROUND((curr - prev) / NULLIF(prev, 0) * 100, 1)"
```

## Chart YAML: params and query_context

Chart YAML files contain `params` and `query_context` fields that are JSON
strings. These are especially fragile:

```yaml
params: '{"viz_type": "table", "row_limit": 1000, ...}'
query_context: '{"datasource": {"id": 42}, "queries": [{"row_limit": 1000}]}'
```

When modifying these:
1. Parse the JSON string to understand structure
2. Apply targeted string replacement on the raw YAML
3. Verify the JSON still parses after replacement

```python
import json

data = yaml.safe_load(raw)
params = json.loads(data['params'])
# Inspect params['row_limit'], etc.

# Edit via string replacement on raw YAML
raw = raw.replace('"row_limit": 100', '"row_limit": 1000')
```

## Quick Reference

| Do | Don't |
|---|---|
| `raw = open(f).read()` | `yaml.dump(data, f)` |
| `raw.replace(old, new)` | `data['sql'] = new_sql` then dump |
| `yaml.safe_load(raw)` for reading | `yaml.load()` (unsafe loader) |
| Verify count before replace | Blind `str.replace()` |
| Validate YAML after edit | Assume the edit is correct |
