# Dashboard CSS Selectors and Limits

## How Dashboard CSS Works

Superset dashboards have a `css` field that accepts arbitrary CSS. This CSS is
injected into the page when the dashboard renders, after all default component
styles have loaded. This means dashboard CSS has naturally high specificity for
overriding built-in styles.

CSS can be set in two ways:
1. **Dashboard YAML** `css:` key — pushed via import bundle (`sup sync push`)
2. **REST API** `PUT /api/v1/dashboard/{id}` with `{"css": "..."}` body

Since import bundles overwrite the CSS field, always push CSS via REST API
after any `sup sync push`. See `superset-import-export.md` for details.

## DOM Selectors

### Chart Container: `[data-test-chart-id="XXXX"]`

This is the **primary and most reliable** selector for targeting individual
charts. It appears on the `.chart-slice` element wrapping each chart.

```css
[data-test-chart-id="2103"] {
  background: #f8f9fa;
  border-radius: 8px;
}
```

The XXXX is the numeric chart ID (same as in the chart YAML filename, e.g.,
`2103.yaml` corresponds to `data-test-chart-id="2103"`).

### Inner Container: `#slice-container-XXXX`

Targets the inner container div within a chart tile. Useful for padding and
overflow control.

```css
#slice-container-2103 {
  padding: 0 !important;
  overflow: hidden;
}
```

### Chart Wrapper: `.dashboard-chart-id-XXXX`

Targets the dashboard grid wrapper around a chart. Useful for borders and
shadows on the tile itself.

```css
.dashboard-chart-id-2103 {
  border: 1px solid #e0e0e0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
```

### Parent Grid Column: `.grid-column:has(...)`

For styling that needs to target the grid column containing a chart. Useful
for top-row tile borders where `.dashboard-chart-id` may not provide enough
layout control.

```css
.grid-column:has([data-test-chart-id="2103"]) {
  border-right: 1px solid #e0e0e0;
}
```

**Browser support note:** `:has()` is supported in all modern browsers (Chrome
105+, Safari 15.4+, Firefox 121+). Preset dashboards are viewed in modern
browsers, so this is safe to use.

### WRONG: `[data-chart-id]`

**This attribute does NOT exist in the Superset DOM.** It is a common mistake.
Always use `data-test-chart-id` (with the `test` prefix), never `data-chart-id`.

```css
/* WRONG - will not match anything */
[data-chart-id="2103"] { ... }

/* CORRECT */
[data-test-chart-id="2103"] { ... }
```

## CSS Size Limits

### Truncation Threshold

Preset Cloud truncates the CSS field at approximately **33,345 characters**. Any
CSS beyond this point is silently dropped — no error, no warning. The dashboard
simply renders with incomplete styles.

### Safe Limit

Keep total CSS under **30,000 characters** to leave margin for:
- Preset's internal CSS processing
- Minor expansions from encoding
- Future additions without hitting the wall

### Measuring CSS Size

```bash
# Check character count of CSS in dashboard YAML
python3 -c "
import yaml
with open('assets/dashboards/Dashboard_76.yaml') as f:
    d = yaml.safe_load(f)
print(f'CSS length: {len(d.get(\"css\", \"\"))} chars')
"
```

### Staying Under the Limit

Strategies to reduce CSS size:

1. **Remove comments.** Strip all `/* ... */` blocks.
2. **Collapse whitespace.** Replace multi-line formatting with single-line rules.
3. **Combine selectors.** Group charts with identical styles:
   ```css
   /* Instead of repeating for each chart */
   [data-test-chart-id="2103"],
   [data-test-chart-id="2104"],
   [data-test-chart-id="2105"] {
     background: #fff;
   }
   ```
4. **Remove unused selectors.** After deleting charts, remove their CSS rules.
5. **Use shorthand properties.** `margin: 0 4px` instead of separate margin rules.

## Common CSS Patterns

### Hide Chart Header

```css
[data-test-chart-id="2103"] .header-with-actions {
  display: none !important;
}
```

### Remove Chart Padding

```css
#slice-container-2103 .chart-container {
  padding: 0 !important;
  margin: 0 !important;
}
```

### Section Divider Border

```css
.dashboard-chart-id-2103 {
  border-bottom: 2px solid #1a1a2e;
}
```

### Full-Width Markdown Tile

```css
[data-test-chart-id="2103"] .markdown-container {
  width: 100%;
  padding: 0;
}
```

### Tile Background Color

```css
[data-test-chart-id="2103"] {
  background-color: #f0f4f8 !important;
}
```

## Specificity Tips

- Dashboard CSS loads last, so simple selectors usually win.
- Use `!important` sparingly — only when Superset inline styles override you.
- Avoid `*` selectors — they can cause performance issues on large dashboards.
- Test in Chrome DevTools by injecting CSS in the Elements panel before pushing.
- Chart IDs are stable — they do not change when charts are renamed or moved.
