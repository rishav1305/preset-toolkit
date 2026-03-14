# Screenshot Browser Cookie Authentication

**Goal:** Eliminate manual login for dashboard screenshots by extracting session cookies from the user's installed browsers.

**Architecture:** A new `browser_cookies.py` module reads cookie databases from installed browsers (Chrome, Firefox, Edge, Arc), decrypts Chromium cookies via macOS Keychain, and injects them into a Playwright context. The existing `screenshot.py` gains a 3-step auth fallback chain that tries saved state first, then browser cookies, then manual login.

**Tech Stack:** Python stdlib (`sqlite3`, `subprocess`, `hashlib`, `struct`), `cryptography` (AES decryption for Chromium cookies), Playwright.

---

## Auth Fallback Chain

```
capture_dashboard() called
  │
  ├─ 1. Try storage_state.json (already saved from last successful run)
  │     → Load into Playwright context, navigate headless
  │     → If dashboard loads (not redirected to login): DONE
  │
  ├─ 2. Try browser cookie extraction
  │     → Detect installed browsers on this OS
  │     → For each browser (Chrome, Firefox, Edge, Arc):
  │         → Read cookie DB, extract *.preset.io cookies
  │         → Inject into Playwright context, navigate headless
  │         → If dashboard loads: save storage_state.json, DONE
  │
  └─ 3. Fall back to manual login (current behavior)
        → Launch headless=False, wait for user to log in (5 min timeout)
        → Save storage_state.json for next time
```

Each step is tried in order. First success wins. Repeat screenshots are instant (step 1), first-time screenshots try to be automatic (step 2), worst case is the current behavior (step 3).

---

## New Module: `scripts/browser_cookies.py`

### Public Interface

```python
from typing import List, Dict

def extract_cookies(domain: str) -> List[Dict]:
    """Extract cookies for domain from installed browsers.

    Returns list of Playwright-compatible cookie dicts:
    [{"name": "session", "value": "abc", "domain": ".preset.io", "path": "/", ...}]

    Tries browsers in order: Chrome, Firefox, Edge, Arc.
    Returns first successful non-empty extraction. Returns [] if all fail.
    """
```

### Browser Support Matrix (macOS)

| Browser | Cookie DB Path | Encryption |
|---|---|---|
| Chrome | `~/Library/Application Support/Google/Chrome/Default/Cookies` | AES-CBC, key from Keychain |
| Firefox | `~/Library/Application Support/Firefox/Profiles/*/cookies.sqlite` | None (plaintext) |
| Edge | `~/Library/Application Support/Microsoft Edge/Default/Cookies` | Same as Chrome |
| Arc | `~/Library/Application Support/Arc/User Data/Default/Cookies` | Same as Chrome |

### Chromium Cookie Decryption (macOS)

1. Retrieve encryption key from Keychain:
   ```bash
   security find-generic-password -w -s "Chrome Safe Storage" -a "Chrome"
   ```
   (Edge uses `"Microsoft Edge Safe Storage"` / `"Microsoft Edge"`, Arc uses `"Arc Safe Storage"` / `"Arc"`)

2. Derive AES key via PBKDF2:
   - Password: the Keychain password from step 1
   - Salt: `b"saltysalt"`
   - Iterations: 1003
   - Key length: 16 bytes

3. Decrypt each cookie value:
   - Strip the `v10` prefix (3 bytes)
   - IV: `b' ' * 16` (16 space bytes, 0x20)
   - Decrypt with AES-128-CBC
   - Remove PKCS7 padding

### Firefox Cookie Extraction

Direct SQLite read — no decryption. The `moz_cookies` table has `name`, `value`, `host`, `path`, `expiry`, `isSecure`, `isHttpOnly`.

Firefox profiles are at `~/Library/Application Support/Firefox/Profiles/`. To find the active profile, parse `profiles.ini` in the Firefox directory and look for the profile with `Default=1`. Fall back to globbing `*.default-release` or `*.default` if `profiles.ini` is missing or unparseable.

### Internal Structure

```python
# Browser registry — each entry knows how to find and read its cookies
_BROWSERS = [
    {"name": "Chrome", "cookie_path": "...", "keychain_service": "Chrome Safe Storage", "keychain_account": "Chrome"},
    {"name": "Firefox", "cookie_path": "...", "encrypted": False},
    {"name": "Edge", "cookie_path": "...", "keychain_service": "Microsoft Edge Safe Storage", "keychain_account": "Microsoft Edge"},
    {"name": "Arc", "cookie_path": "...", "keychain_service": "Arc Safe Storage", "keychain_account": "Arc"},
]

def _extract_chromium_cookies(cookie_db: Path, keychain_service: str, keychain_account: str, domain: str) -> List[Dict]:
    """Read and decrypt cookies from a Chromium-based browser."""

def _extract_firefox_cookies(profile_dir: Path, domain: str) -> List[Dict]:
    """Read plaintext cookies from Firefox."""

def _decrypt_chromium_value(encrypted_value: bytes, key: bytes) -> str:
    """Decrypt a single Chromium cookie value using AES-CBC."""

def _get_chromium_key(service: str, account: str) -> bytes:
    """Get the AES key from macOS Keychain via security CLI."""
```

### Cookie DB Read Strategy

Chromium-based browsers hold a WAL-mode lock on the Cookies SQLite file while running. To avoid `database is locked` errors, **always copy the cookie DB to a temp file before reading**, then clean up the temp copy after extraction. This ensures reads succeed even when the browser is open.

```python
import shutil, tempfile
with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
    shutil.copy2(cookie_db_path, tmp.name)
    # read from tmp.name
# os.unlink(tmp.name) in finally block
```

### Keychain Access UX

On macOS, `security find-generic-password -w` triggers a system dialog asking the user to allow access to the Keychain item (e.g., "Terminal wants to use your confidential information stored in 'Chrome Safe Storage'"). This is a one-time prompt per browser.

Before calling the subprocess, log an INFO message: `"Requesting Keychain access for {browser} cookies..."` so the user understands why the popup appeared.

### Error Handling

- If a browser is not installed (cookie path doesn't exist): skip silently
- If Keychain access fails (user denies prompt): log at INFO, skip that browser, try next
- If SQLite DB copy or read fails: skip that browser, try next
- If decryption fails for a cookie: skip that cookie, continue with others
- All other errors logged at DEBUG level — never surfaces to user unless all browsers fail

### Platform Extensibility

The module only handles macOS for now. The browser registry structure makes adding Linux/Windows support straightforward later:
- Linux: Chrome uses `secretstorage` (GNOME Keyring), Firefox is plaintext
- Windows: Chrome uses DPAPI, Firefox is plaintext

---

## Changes to `scripts/screenshot.py`

### New Helper: `_try_auth_context()`

```python
async def _try_auth_context(playwright, config, storage_state_path, dashboard_url):
    """Try to get an authenticated Playwright context without user interaction.

    Returns (browser, context, page, method_name) on success.
    Returns (None, None, None, None) on failure.
    Caller is responsible for closing browser on success.
    On failure, all resources are cleaned up internally.
    """
```

### New Helper: `_test_context()`

```python
async def _test_context(playwright, config, dashboard_url, storage_state=None, cookies=None):
    """Create a headless browser + context, navigate to dashboard, check if authenticated.

    Returns (browser, context, page) if authenticated (not on login page).
    Closes BOTH browser and context on failure — caller owns them on success.
    """
```

Authentication check: after navigation, inspect `page.url` — if it contains `/login` or `/superset/welcome`, the cookies are stale/invalid.

### Modified Flow in `capture_dashboard()`

```python
async def capture_dashboard(config, output_dir, storage_state=None, headless=True):
    async with async_playwright() as p:
        # Try automatic auth first
        storage_state_path = config.project_root / ".preset-toolkit" / ".secrets" / "storage_state.json"
        browser, context, page, method = await _try_auth_context(p, config, storage_state_path, dashboard_url)

        if context:
            log.info("Authenticated via %s", method)
        else:
            # Fall back to manual login (existing code, unchanged)
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(viewport={"width": 1920, "height": 1080})
            page = await context.new_page()
            # ... existing login wait logic ...

        try:
            # ... rest of screenshot capture unchanged ...
        finally:
            await browser.close()
```

### What Doesn't Change

- `ScreenshotResult` dataclass
- Masking, per-section screenshots, telemetry
- `storage_state.json` saving on success
- `capture_sync()` wrapper
- The skill file (`skills/preset-screenshot/SKILL.md`)

---

## New Dependency

`cryptography` — added to `bootstrap.sh` install line and `pyproject.toml`.

This is the standard Python cryptography library. Used only for AES-CBC decryption of Chromium cookies. No other crypto operations needed.

---

## Testing

### New File: `tests/test_browser_cookies.py`

**Cookie parsing tests:**
- `test_extract_chromium_cookies_from_mock_db` — Create temp SQLite DB with Chromium schema, insert encrypted cookies with known key, verify extraction
- `test_extract_firefox_cookies_from_mock_db` — Create temp SQLite DB with Firefox schema, insert plaintext cookies, verify extraction
- `test_domain_filtering` — Insert cookies for multiple domains, verify only target domain returned
- `test_no_browser_installed` — Cookie paths don't exist, returns `[]`
- `test_keychain_access_denied` — Mock subprocess to simulate Keychain denial, returns `[]`
- `test_locked_sqlite_db` — Simulate locked DB, returns `[]`
- `test_cookie_db_copied_to_temp` — Verify original DB is not opened directly, temp copy is used and cleaned up

**Decryption tests:**
- `test_decrypt_chromium_value_known_pair` — Encrypt a value with known key, verify decryption roundtrip
- `test_decrypt_handles_v10_prefix` — Verify `v10` prefix stripping

**Integration tests (in `tests/test_screenshot.py`):**
- `test_try_auth_context_uses_storage_state_first` — Mock storage state exists and is valid
- `test_try_auth_context_falls_through_to_cookies` — Storage state stale, browser cookies work
- `test_try_auth_context_falls_through_to_manual` — Both fail, returns None

**Estimated: 11-12 new tests**, all fast (mock DBs, no real browser).

---

## File Summary

| File | Action |
|---|---|
| `scripts/browser_cookies.py` | Create — cookie extraction module |
| `scripts/screenshot.py` | Modify — add `_try_auth_context()`, `_test_context()`, update `capture_dashboard()` |
| `scripts/bootstrap.sh` | Modify — add `cryptography` to pip install line |
| `pyproject.toml` | Modify — add `cryptography` to dependencies |
| `tests/test_browser_cookies.py` | Create — 8 unit tests |
| `tests/test_screenshot.py` | Modify — 3 new integration tests |
