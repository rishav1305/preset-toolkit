# Preset REST API Reference

## Base URL

All API calls target the workspace-specific Preset Cloud URL:

```
https://<workspace-slug>.us2a.app.preset.io
```

The workspace slug is a hex string assigned when the workspace is created
(e.g., `834639b2`). Find it in the browser URL bar when viewing any Preset page.

## Authentication Flow

Preset uses a two-step authentication: API token/secret exchange for a JWT.

### Step 1: Obtain API Credentials

From the Preset UI: Settings > API Keys. You get a **token** (username) and
**secret** (password). Store these securely — they do not expire unless revoked.

### Step 2: Exchange for JWT

```http
POST /api/v1/security/login
Content-Type: application/json

{
  "username": "<api-token>",
  "password": "<api-secret>",
  "provider": "db",
  "refresh": true
}
```

Response:

```json
{
  "access_token": "<jwt-string>"
}
```

### Step 3: Use JWT in Requests

```http
Authorization: Bearer <jwt-string>
```

The JWT is short-lived (typically 5-10 minutes). If a request returns 401,
re-authenticate by repeating Step 2.

## CSRF Protection

Mutation requests (PUT, POST, DELETE) require a CSRF token.

### Fetch CSRF Token

```http
GET /api/v1/security/csrf_token/
Authorization: Bearer <jwt>
```

Response:

```json
{
  "result": "<csrf-token-string>"
}
```

### Include in Mutations

```http
X-CSRFToken: <csrf-token-string>
Referer: https://<workspace>.us2a.app.preset.io/
```

The `Referer` header is also required by Superset's CSRF middleware. Without it,
mutation requests may be rejected with a 400 or 403 error.

## Dashboard Endpoints

### Fetch Dashboard

```http
GET /api/v1/dashboard/{id}
Authorization: Bearer <jwt>
```

Returns the full dashboard object including `css`, `position_json`,
`json_metadata` (contains native filter config), and chart references.

The `id` is the numeric dashboard ID (not the UUID). Find it in the URL:
`/superset/dashboard/76/` means `id=76`.

### Update Dashboard

```http
PUT /api/v1/dashboard/{id}
Authorization: Bearer <jwt>
X-CSRFToken: <csrf-token>
Referer: https://<workspace>.us2a.app.preset.io/
Content-Type: application/json

{
  "css": "<css-string>",
  "json_metadata": "<json-string>"
}
```

Only include the fields you want to update. Omitted fields are left unchanged.

Common updatable fields:
- `css` — dashboard custom CSS (string)
- `json_metadata` — native filters, color schemes, cross-filter config (JSON string)
- `position_json` — tile layout grid positions (JSON string)

### Other Useful Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/dashboard/` | GET | List all dashboards |
| `/api/v1/chart/{id}` | GET | Fetch a single chart |
| `/api/v1/chart/data` | POST | Execute chart query and get data |
| `/api/v1/dataset/{id}` | GET | Fetch dataset definition |
| `/api/v1/database/` | GET | List database connections |

## Rate Limiting

Preset Cloud applies soft rate limits. For bulk operations:
- Space requests at least 200ms apart.
- Batch related changes into a single PUT when possible (e.g., push CSS +
  position_json together rather than in separate calls).
- If you receive 429 (Too Many Requests), wait 5 seconds and retry.

## Error Handling

| Status | Meaning | Action |
|---|---|---|
| 401 | JWT expired or invalid | Re-authenticate (POST /login) |
| 403 | CSRF token missing/invalid or insufficient permissions | Fetch new CSRF token; check workspace role |
| 404 | Dashboard/chart/dataset not found | Verify the numeric ID exists |
| 422 | Validation error | Check request body format |
| 429 | Rate limited | Wait and retry |
| 500 | Server error | Retry after a few seconds |

## Example: Full Dashboard CSS Update

```python
import requests

base = "https://834639b2.us2a.app.preset.io"

# 1. Authenticate
auth = requests.post(f"{base}/api/v1/security/login", json={
    "username": API_TOKEN, "password": API_SECRET,
    "provider": "db", "refresh": True
})
jwt = auth.json()["access_token"]
headers = {"Authorization": f"Bearer {jwt}"}

# 2. Get CSRF token
csrf = requests.get(f"{base}/api/v1/security/csrf_token/", headers=headers)
csrf_token = csrf.json()["result"]

# 3. Update dashboard CSS
headers.update({
    "X-CSRFToken": csrf_token,
    "Referer": f"{base}/",
    "Content-Type": "application/json"
})
requests.put(f"{base}/api/v1/dashboard/76", headers=headers, json={
    "css": new_css_string
})
```
