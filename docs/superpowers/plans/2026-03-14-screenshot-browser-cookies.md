# Screenshot Browser Cookie Authentication Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate manual login for dashboard screenshots by extracting session cookies from installed browsers and injecting them into Playwright.

**Architecture:** New `browser_cookies.py` reads cookie DBs from Chrome/Firefox/Edge/Arc, decrypts Chromium cookies via macOS Keychain + AES-CBC (`cryptography` lib), and returns Playwright-compatible cookie dicts. `screenshot.py` gains a 3-step fallback chain: saved storage_state → browser cookies → manual login.

**Tech Stack:** Python stdlib (`sqlite3`, `subprocess`, `hashlib`), `cryptography>=42.0`, Playwright

**Spec:** `docs/superpowers/specs/2026-03-14-screenshot-browser-cookies-design.md`

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `scripts/browser_cookies.py` | Create | Cookie extraction from Chrome/Firefox/Edge/Arc |
| `scripts/screenshot.py` | Modify | Auth fallback chain (`_try_auth_context`, `_test_context`) |
| `scripts/bootstrap.sh` | Modify | Add `cryptography` to pip install |
| `pyproject.toml` | Modify | Add `cryptography` to dependencies |
| `tests/test_browser_cookies.py` | Create | Unit tests for cookie extraction + decryption |
| `tests/test_screenshot.py` | Modify | Integration tests for auth fallback chain |

---

## Chunk 1: Chromium Cookie Decryption Core

### Task 1: Add `cryptography` dependency

**Files:**
- Modify: `scripts/bootstrap.sh:73`
- Modify: `pyproject.toml:8-13`

- [ ] **Step 1: Add cryptography to bootstrap.sh**

In `scripts/bootstrap.sh`, change the pip install line:

```bash
$VENV_PIP install -q PyYAML Pillow httpx superset-sup playwright cryptography 2>&1 | grep -v "notice" || true
```

Also add `cryptography` to the verification loop. Change the Python verification block to include it:

```python
for mod, name in [('yaml','PyYAML'), ('PIL','Pillow'), ('httpx','httpx'), ('playwright','playwright'), ('cryptography','cryptography')]:
```

And update the for loop:

```bash
for pkg in PyYAML Pillow httpx playwright cryptography; do
```

- [ ] **Step 2: Add cryptography to pyproject.toml**

In `pyproject.toml`, add to the `screenshots` optional dependencies:

```toml
[project.optional-dependencies]
screenshots = ["playwright>=1.40", "cryptography>=42.0"]
dev = ["pytest>=7.0", "pytest-cov>=4.0"]
```

- [ ] **Step 3: Commit**

```bash
git add scripts/bootstrap.sh pyproject.toml
git commit -m "deps: add cryptography for browser cookie decryption"
```

---

### Task 2: Chromium decryption functions (TDD)

**Files:**
- Create: `scripts/browser_cookies.py`
- Create: `tests/test_browser_cookies.py`

- [ ] **Step 1: Write failing test for `_decrypt_chromium_value`**

Create `tests/test_browser_cookies.py`:

```python
"""Tests for browser cookie extraction module."""
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from scripts.browser_cookies import _decrypt_chromium_value


def test_decrypt_chromium_value_known_pair():
    """Encrypt a value with a known key, verify decryption roundtrip."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding

    key = b'\x00' * 16
    iv = b' ' * 16
    plaintext = b"test_cookie_value"

    # Pad
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()

    # Encrypt
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    # Add v10 prefix (Chromium format)
    encrypted_value = b"v10" + ciphertext

    result = _decrypt_chromium_value(encrypted_value, key)
    assert result == "test_cookie_value"


def test_decrypt_handles_v10_prefix():
    """Verify v10 prefix is stripped before decryption."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding

    key = b'\x01' * 16
    iv = b' ' * 16
    plaintext = b"hello"

    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()

    result = _decrypt_chromium_value(b"v10" + ciphertext, key)
    assert result == "hello"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/test_browser_cookies.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.browser_cookies'`

- [ ] **Step 3: Create browser_cookies.py with decryption function**

Create `scripts/browser_cookies.py`:

```python
"""Extract browser cookies for Preset authentication.

Reads cookie databases from installed browsers (Chrome, Firefox, Edge, Arc)
on macOS. Chromium cookies are decrypted via Keychain + AES-CBC.
"""
import os
import shutil
import sqlite3
import subprocess
import tempfile
from configparser import ConfigParser
from pathlib import Path
from typing import Dict, List, Optional

from scripts.logger import get_logger

log = get_logger("browser_cookies")


def _decrypt_chromium_value(encrypted_value: bytes, key: bytes) -> str:
    """Decrypt a single Chromium cookie value using AES-128-CBC.

    Chromium cookies on macOS are prefixed with b'v10' followed by
    AES-128-CBC encrypted data. IV is 16 space bytes (0x20).
    """
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding

    # Strip v10 prefix
    if encrypted_value[:3] == b"v10":
        encrypted_value = encrypted_value[3:]

    iv = b" " * 16
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    decrypted_padded = decryptor.update(encrypted_value) + decryptor.finalize()

    # Remove PKCS7 padding
    unpadder = padding.PKCS7(128).unpadder()
    decrypted = unpadder.update(decrypted_padded) + unpadder.finalize()

    return decrypted.decode("utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/test_browser_cookies.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/browser_cookies.py tests/test_browser_cookies.py
git commit -m "feat: add Chromium cookie decryption (AES-128-CBC)"
```

---

### Task 3: Keychain key retrieval (TDD)

**Files:**
- Modify: `scripts/browser_cookies.py`
- Modify: `tests/test_browser_cookies.py`

- [ ] **Step 1: Write failing test for `_get_chromium_key`**

Add to `tests/test_browser_cookies.py`:

```python
from scripts.browser_cookies import _get_chromium_key


def test_get_chromium_key_calls_security_cli():
    """_get_chromium_key should call macOS security CLI and derive AES key."""
    with patch("scripts.browser_cookies.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="fake_keychain_password\n", stderr=""
        )
        key = _get_chromium_key("Chrome Safe Storage", "Chrome")
        assert key is not None
        assert len(key) == 16  # AES-128 key
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert "security" in args
        assert "Chrome Safe Storage" in args


def test_get_chromium_key_returns_none_on_failure():
    """_get_chromium_key should return None if Keychain access fails."""
    with patch("scripts.browser_cookies.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="denied")
        key = _get_chromium_key("Chrome Safe Storage", "Chrome")
        assert key is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/test_browser_cookies.py::test_get_chromium_key_calls_security_cli -v`
Expected: FAIL with `ImportError: cannot import name '_get_chromium_key'`

- [ ] **Step 3: Implement `_get_chromium_key`**

Add to `scripts/browser_cookies.py`:

```python
def _get_chromium_key(keychain_service: str, keychain_account: str) -> Optional[bytes]:
    """Get AES key for Chromium cookie decryption from macOS Keychain.

    Calls `security find-generic-password` to get the raw password, then
    derives the AES-128 key via PBKDF2 (salt=b'saltysalt', iterations=1003).

    Returns 16-byte key on success, None on failure.
    """
    log.info("Requesting Keychain access for %s cookies...", keychain_account)
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-w",
             "-s", keychain_service, "-a", keychain_account],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log.info("Keychain access denied for %s", keychain_account)
            return None

        password = result.stdout.strip()
        import hashlib
        key = hashlib.pbkdf2_hmac(
            "sha1", password.encode("utf-8"), b"saltysalt", 1003, dklen=16,
        )
        return key
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        log.debug("Keychain access failed for %s: %s", keychain_account, e)
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/test_browser_cookies.py -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/browser_cookies.py tests/test_browser_cookies.py
git commit -m "feat: add macOS Keychain key retrieval for Chromium cookies"
```

---

## Chunk 2: Chromium and Firefox Cookie Extraction

### Task 4: Chromium cookie extraction from SQLite (TDD)

**Files:**
- Modify: `scripts/browser_cookies.py`
- Modify: `tests/test_browser_cookies.py`

- [ ] **Step 1: Write failing test for `_extract_chromium_cookies`**

Add to `tests/test_browser_cookies.py`:

```python
from scripts.browser_cookies import _extract_chromium_cookies


def _create_chromium_cookie_db(db_path, cookies, key):
    """Helper: create a mock Chromium Cookies SQLite DB with encrypted values."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as crypto_padding

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE cookies (
            host_key TEXT, name TEXT, encrypted_value BLOB,
            path TEXT, expires_utc INTEGER, is_secure INTEGER, is_httponly INTEGER
        )
    """)
    iv = b" " * 16
    for c in cookies:
        padder = crypto_padding.PKCS7(128).padder()
        padded = padder.update(c["value"].encode()) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        enc = cipher.encryptor()
        encrypted = b"v10" + enc.update(padded) + enc.finalize()
        conn.execute(
            "INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?, ?)",
            (c["domain"], c["name"], encrypted, c.get("path", "/"),
             c.get("expires", 0), c.get("secure", 1), c.get("httponly", 1)),
        )
    conn.commit()
    conn.close()


import sqlite3


def test_extract_chromium_cookies_from_mock_db(tmp_path):
    """Extract and decrypt cookies from a mock Chromium DB."""
    key = b'\x00' * 16
    db_path = tmp_path / "Cookies"
    _create_chromium_cookie_db(db_path, [
        {"domain": ".preset.io", "name": "session", "value": "abc123"},
        {"domain": ".preset.io", "name": "csrf", "value": "token456"},
        {"domain": ".google.com", "name": "NID", "value": "shouldskip"},
    ], key)

    with patch("scripts.browser_cookies._get_chromium_key", return_value=key):
        result = _extract_chromium_cookies(
            db_path, "Chrome Safe Storage", "Chrome", "preset.io",
        )

    assert len(result) == 2
    names = {c["name"] for c in result}
    assert names == {"session", "csrf"}
    assert result[0]["value"] in ("abc123", "token456")


def test_cookie_db_copied_to_temp(tmp_path):
    """Verify the original DB is not opened directly — a temp copy is used."""
    key = b'\x00' * 16
    db_path = tmp_path / "Cookies"
    _create_chromium_cookie_db(db_path, [
        {"domain": ".preset.io", "name": "s", "value": "v"},
    ], key)

    opened_paths = []
    original_connect = sqlite3.connect

    def tracking_connect(path, *args, **kwargs):
        opened_paths.append(str(path))
        return original_connect(path, *args, **kwargs)

    with patch("scripts.browser_cookies._get_chromium_key", return_value=key):
        with patch("scripts.browser_cookies.sqlite3.connect", side_effect=tracking_connect):
            _extract_chromium_cookies(
                db_path, "Chrome Safe Storage", "Chrome", "preset.io",
            )

    # The opened path should NOT be the original db_path
    assert str(db_path) not in opened_paths
    assert len(opened_paths) == 1  # exactly one temp copy opened


def test_domain_filtering(tmp_path):
    """Only cookies matching the target domain should be returned."""
    key = b'\x00' * 16
    db_path = tmp_path / "Cookies"
    _create_chromium_cookie_db(db_path, [
        {"domain": ".preset.io", "name": "good", "value": "yes"},
        {"domain": ".evil.com", "name": "bad", "value": "no"},
        {"domain": "sub.preset.io", "name": "also_good", "value": "yep"},
    ], key)

    with patch("scripts.browser_cookies._get_chromium_key", return_value=key):
        result = _extract_chromium_cookies(
            db_path, "Chrome Safe Storage", "Chrome", "preset.io",
        )

    names = {c["name"] for c in result}
    assert "good" in names
    assert "also_good" in names
    assert "bad" not in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/test_browser_cookies.py::test_extract_chromium_cookies_from_mock_db -v`
Expected: FAIL with `ImportError: cannot import name '_extract_chromium_cookies'`

- [ ] **Step 3: Implement `_extract_chromium_cookies`**

Add to `scripts/browser_cookies.py`:

```python
def _extract_chromium_cookies(
    cookie_db: Path,
    keychain_service: str,
    keychain_account: str,
    domain: str,
) -> List[Dict]:
    """Read and decrypt cookies from a Chromium-based browser.

    Copies the DB to a temp file first (browser holds WAL lock while running).
    """
    if not cookie_db.exists():
        return []

    key = _get_chromium_key(keychain_service, keychain_account)
    if key is None:
        return []

    tmp_path = None
    try:
        # Copy to temp file to avoid WAL lock conflicts
        fd, tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        shutil.copy2(str(cookie_db), tmp_path)

        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT host_key, name, encrypted_value, path, expires_utc, "
            "is_secure, is_httponly FROM cookies WHERE host_key LIKE ?",
            (f"%{domain}%",),
        )

        cookies = []
        for row in cursor:
            try:
                value = _decrypt_chromium_value(row["encrypted_value"], key)
                cookies.append({
                    "name": row["name"],
                    "value": value,
                    "domain": row["host_key"],
                    "path": row["path"],
                    "secure": bool(row["is_secure"]),
                    "httpOnly": bool(row["is_httponly"]),
                })
            except Exception as e:
                log.debug("Failed to decrypt cookie %s: %s", row["name"], e)
        conn.close()
        return cookies
    except Exception as e:
        log.debug("Failed to read Chromium cookies from %s: %s", cookie_db, e)
        return []
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/test_browser_cookies.py -v`
Expected: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/browser_cookies.py tests/test_browser_cookies.py
git commit -m "feat: add Chromium cookie extraction with temp-file copy"
```

---

### Task 5: Firefox cookie extraction (TDD)

**Files:**
- Modify: `scripts/browser_cookies.py`
- Modify: `tests/test_browser_cookies.py`

- [ ] **Step 1: Write failing test for `_extract_firefox_cookies`**

Add to `tests/test_browser_cookies.py`:

```python
from scripts.browser_cookies import _extract_firefox_cookies


def test_extract_firefox_cookies_from_mock_db(tmp_path):
    """Extract plaintext cookies from a mock Firefox DB."""
    profile_dir = tmp_path / "profile.default-release"
    profile_dir.mkdir()
    db_path = profile_dir / "cookies.sqlite"

    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE moz_cookies (
            name TEXT, value TEXT, host TEXT, path TEXT,
            expiry INTEGER, isSecure INTEGER, isHttpOnly INTEGER
        )
    """)
    conn.execute(
        "INSERT INTO moz_cookies VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("session", "firefox_val", ".preset.io", "/", 0, 1, 1),
    )
    conn.execute(
        "INSERT INTO moz_cookies VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("other", "skip", ".other.com", "/", 0, 0, 0),
    )
    conn.commit()
    conn.close()

    result = _extract_firefox_cookies(profile_dir, "preset.io")
    assert len(result) == 1
    assert result[0]["name"] == "session"
    assert result[0]["value"] == "firefox_val"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/test_browser_cookies.py::test_extract_firefox_cookies_from_mock_db -v`
Expected: FAIL with `ImportError: cannot import name '_extract_firefox_cookies'`

- [ ] **Step 3: Implement `_extract_firefox_cookies`**

Add to `scripts/browser_cookies.py`:

```python
def _find_firefox_profile() -> Optional[Path]:
    """Find the default Firefox profile directory on macOS.

    Parses profiles.ini for Default=1, falls back to globbing.
    """
    firefox_dir = Path.home() / "Library" / "Application Support" / "Firefox"
    profiles_ini = firefox_dir / "profiles.ini"

    if profiles_ini.exists():
        try:
            config = ConfigParser()
            config.read(str(profiles_ini))
            for section in config.sections():
                if config.get(section, "Default", fallback="0") == "1":
                    path = config.get(section, "Path", fallback=None)
                    is_relative = config.get(section, "IsRelative", fallback="1")
                    if path:
                        if is_relative == "1":
                            profile_path = firefox_dir / path
                        else:
                            profile_path = Path(path)
                        if profile_path.exists():
                            return profile_path
        except Exception as e:
            log.debug("Failed to parse profiles.ini: %s", e)

    # Fallback: glob for common profile names
    profiles_dir = firefox_dir / "Profiles"
    for pattern in ["*.default-release", "*.default"]:
        matches = list(profiles_dir.glob(pattern))
        if matches:
            return matches[0]

    return None


def _extract_firefox_cookies(profile_dir: Path, domain: str) -> List[Dict]:
    """Read plaintext cookies from a Firefox profile.

    Copies the DB to a temp file first to avoid lock conflicts.
    """
    cookie_db = profile_dir / "cookies.sqlite"
    if not cookie_db.exists():
        return []

    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        shutil.copy2(str(cookie_db), tmp_path)

        conn = sqlite3.connect(tmp_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT name, value, host, path, expiry, isSecure, isHttpOnly "
            "FROM moz_cookies WHERE host LIKE ?",
            (f"%{domain}%",),
        )

        cookies = []
        for row in cursor:
            cookies.append({
                "name": row["name"],
                "value": row["value"],
                "domain": row["host"],
                "path": row["path"],
                "secure": bool(row["isSecure"]),
                "httpOnly": bool(row["isHttpOnly"]),
            })
        conn.close()
        return cookies
    except Exception as e:
        log.debug("Failed to read Firefox cookies: %s", e)
        return []
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/test_browser_cookies.py -v`
Expected: 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/browser_cookies.py tests/test_browser_cookies.py
git commit -m "feat: add Firefox cookie extraction with profiles.ini parsing"
```

---

## Chunk 3: Public API and Error Handling

### Task 6: `extract_cookies()` public API (TDD)

**Files:**
- Modify: `scripts/browser_cookies.py`
- Modify: `tests/test_browser_cookies.py`

- [ ] **Step 1: Write failing tests for `extract_cookies`**

Add to `tests/test_browser_cookies.py`:

```python
from scripts.browser_cookies import extract_cookies


def test_no_browser_installed(tmp_path):
    """extract_cookies should return [] when no browsers are installed."""
    with patch("scripts.browser_cookies.Path.home", return_value=tmp_path):
        result = extract_cookies("preset.io")
    assert result == []


def test_keychain_access_denied():
    """extract_cookies should skip browser and try next on Keychain denial."""
    with patch("scripts.browser_cookies._get_chromium_key", return_value=None):
        with patch("scripts.browser_cookies._find_firefox_profile", return_value=None):
            result = extract_cookies("preset.io")
    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/test_browser_cookies.py::test_no_browser_installed -v`
Expected: FAIL with `ImportError: cannot import name 'extract_cookies'`

- [ ] **Step 3: Implement `extract_cookies` and browser registry**

Add to `scripts/browser_cookies.py`:

```python
# Browser registry — macOS paths
_CHROMIUM_BROWSERS = [
    {
        "name": "Chrome",
        "cookie_path": "Google/Chrome/Default/Cookies",
        "keychain_service": "Chrome Safe Storage",
        "keychain_account": "Chrome",
    },
    {
        "name": "Edge",
        "cookie_path": "Microsoft Edge/Default/Cookies",
        "keychain_service": "Microsoft Edge Safe Storage",
        "keychain_account": "Microsoft Edge",
    },
    {
        "name": "Arc",
        "cookie_path": "Arc/User Data/Default/Cookies",
        "keychain_service": "Arc Safe Storage",
        "keychain_account": "Arc",
    },
]


def extract_cookies(domain: str) -> List[Dict]:
    """Extract cookies for domain from installed browsers.

    Returns list of Playwright-compatible cookie dicts.
    Tries browsers in order: Chrome, Firefox, Edge, Arc.
    Returns first successful non-empty extraction. Returns [] if all fail.
    """
    app_support = Path.home() / "Library" / "Application Support"

    # Try Chrome first (most common)
    chrome_entry = _CHROMIUM_BROWSERS[0]
    cookie_db = app_support / chrome_entry["cookie_path"]
    if cookie_db.exists():
        cookies = _extract_chromium_cookies(
            cookie_db,
            chrome_entry["keychain_service"],
            chrome_entry["keychain_account"],
            domain,
        )
        if cookies:
            log.info("Extracted %d cookies from %s", len(cookies), chrome_entry["name"])
            return cookies

    # Try Firefox
    profile = _find_firefox_profile()
    if profile:
        cookies = _extract_firefox_cookies(profile, domain)
        if cookies:
            log.info("Extracted %d cookies from Firefox", len(cookies))
            return cookies

    # Try remaining Chromium browsers (Edge, Arc)
    for entry in _CHROMIUM_BROWSERS[1:]:
        cookie_db = app_support / entry["cookie_path"]
        if cookie_db.exists():
            cookies = _extract_chromium_cookies(
                cookie_db,
                entry["keychain_service"],
                entry["keychain_account"],
                domain,
            )
            if cookies:
                log.info("Extracted %d cookies from %s", len(cookies), entry["name"])
                return cookies

    log.debug("No browser cookies found for %s", domain)
    return []
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/test_browser_cookies.py -v`
Expected: 10 tests PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/ -v`
Expected: 134+ tests PASS (124 existing + 10 new)

- [ ] **Step 6: Commit**

```bash
git add scripts/browser_cookies.py tests/test_browser_cookies.py
git commit -m "feat: add extract_cookies() public API with browser registry"
```

---

## Chunk 4: Screenshot Auth Fallback Chain

### Task 7: Add `_test_context` and `_try_auth_context` to screenshot.py (TDD)

**Files:**
- Modify: `scripts/screenshot.py:25-89`
- Modify: `tests/test_screenshot.py`

- [ ] **Step 1: Write failing tests for auth fallback**

Add to `tests/test_screenshot.py`:

```python
from scripts.screenshot import _try_auth_context


def test_try_auth_context_uses_storage_state_first(tmp_path):
    """When storage_state.json exists and works, use it."""
    cfg = _make_screenshot_config(tmp_path)
    state_path = tmp_path / ".preset-toolkit" / ".secrets" / "storage_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text('{"cookies": []}')

    mock_page = AsyncMock()
    mock_page.url = "https://test.preset.io/superset/dashboard/42/"  # not a login page
    mock_page.goto = AsyncMock()
    mock_page.wait_for_load_state = AsyncMock()

    mock_context = AsyncMock()
    mock_context.new_page.return_value = mock_page
    mock_context.pages = [mock_page]

    mock_browser = AsyncMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw = AsyncMock()
    mock_pw.chromium.launch.return_value = mock_browser

    dashboard_url = "https://test.preset.io/superset/dashboard/42/"
    result = asyncio.run(_try_auth_context(mock_pw, cfg, state_path, dashboard_url))
    browser, context, page, method = result
    assert method == "storage_state"
    assert context is not None


def test_try_auth_context_falls_through_to_manual(tmp_path):
    """When both storage state and cookies fail, return None."""
    cfg = _make_screenshot_config(tmp_path)
    state_path = tmp_path / "nonexistent_state.json"  # doesn't exist

    with patch("scripts.screenshot.extract_cookies", return_value=[]):
        dashboard_url = "https://test.preset.io/superset/dashboard/42/"
        result = asyncio.run(_try_auth_context(AsyncMock(), cfg, state_path, dashboard_url))
    browser, context, page, method = result
    assert browser is None
    assert method is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/test_screenshot.py::test_try_auth_context_uses_storage_state_first -v`
Expected: FAIL with `ImportError: cannot import name '_try_auth_context'`

- [ ] **Step 3: Implement `_test_context` and `_try_auth_context`**

Add to `scripts/screenshot.py` (after the imports, before `capture_dashboard`):

```python
async def _test_context(playwright, config, dashboard_url, storage_state=None, cookies=None):
    """Create a headless browser + context, navigate, check if authenticated.

    Returns (browser, context, page) if on the dashboard (not login page).
    Closes both browser and context on failure.
    """
    browser = await playwright.chromium.launch(headless=True)
    try:
        context_kwargs = {"viewport": {"width": 1920, "height": 1080}}
        if storage_state:
            context_kwargs["storage_state"] = storage_state
        context = await browser.new_context(**context_kwargs)

        if cookies:
            await context.add_cookies(cookies)

        page = await context.new_page()
        nav_timeout = config.get("screenshots.navigation_timeout", 60) * 1000
        await page.goto(dashboard_url, wait_until="networkidle", timeout=nav_timeout)

        current_url = page.url
        on_login_page = "/login" in current_url or "/superset/welcome" in current_url
        if on_login_page:
            await browser.close()
            return None, None, None

        return browser, context, page
    except Exception as e:
        log.debug("Auth test failed: %s", e)
        await browser.close()
        return None, None, None


async def _try_auth_context(playwright, config, storage_state_path, dashboard_url):
    """Try to get an authenticated Playwright context without user interaction.

    Returns (browser, context, page, method_name) on success.
    Returns (None, None, None, None) on failure.
    Caller is responsible for closing browser on success.
    """
    # Step 1: Try saved storage state
    if storage_state_path and storage_state_path.exists():
        log.debug("Trying saved storage state...")
        browser, context, page = await _test_context(
            playwright, config, dashboard_url,
            storage_state=str(storage_state_path),
        )
        if context:
            return browser, context, page, "storage_state"

    # Step 2: Try browser cookies
    try:
        from scripts.browser_cookies import extract_cookies
        from urllib.parse import urlparse
        domain = urlparse(config.workspace_url).hostname or ""
        cookies = extract_cookies(domain)
        if cookies:
            log.debug("Trying %d browser cookies...", len(cookies))
            browser, context, page = await _test_context(
                playwright, config, dashboard_url, cookies=cookies,
            )
            if context:
                return browser, context, page, "browser_cookies"
    except Exception as e:
        log.debug("Browser cookie extraction failed: %s", e)

    return None, None, None, None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/test_screenshot.py -v`
Expected: 7 tests PASS (5 existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add scripts/screenshot.py tests/test_screenshot.py
git commit -m "feat: add _try_auth_context with storage_state + cookie fallback"
```

---

### Task 8: Integrate fallback chain into `capture_dashboard`

**Files:**
- Modify: `scripts/screenshot.py:25-134`

- [ ] **Step 1: Rewrite `capture_dashboard` to use the fallback chain**

Replace the body of `capture_dashboard` in `scripts/screenshot.py`:

```python
async def capture_dashboard(
    config: ToolkitConfig,
    output_dir: Path,
    storage_state: Optional[Path] = None,
    headless: bool = True,
) -> ScreenshotResult:
    """Capture full-page and per-section screenshots of a Preset dashboard."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        from scripts.deps import ensure_playwright
        ensure_playwright()
        from playwright.async_api import async_playwright

    output_dir.mkdir(parents=True, exist_ok=True)
    result = ScreenshotResult()
    t = get_telemetry(config._path)

    url_pattern = config.get("api.dashboard_url_pattern", "/superset/dashboard/{id}/")
    dashboard_url = f"{config.workspace_url.rstrip('/')}{url_pattern.format(id=config.dashboard_id)}"
    wait_ms = config.get("screenshots.wait_seconds", 15) * 1000
    mask_selectors = config.get("screenshots.mask_selectors", [])

    async with async_playwright() as p:
        # --- Auth fallback chain ---
        storage_state_path = storage_state or (
            config.project_root / ".preset-toolkit" / ".secrets" / "storage_state.json"
        )
        browser, context, page, auth_method = await _try_auth_context(
            p, config, storage_state_path, dashboard_url,
        )

        if context:
            log.info("Authenticated via %s", auth_method)
            # Wait for dashboard to fully render
            await page.wait_for_timeout(wait_ms)
        else:
            # Fall back to manual login (original behavior)
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
            )
            page = await context.new_page()

            try:
                nav_timeout = config.get("screenshots.navigation_timeout", 60) * 1000
                await page.goto(dashboard_url, wait_until="networkidle", timeout=nav_timeout)

                login_timeout = 5 * 60 * 1000
                current_url = page.url
                on_login_page = "/login" in current_url or "/superset/welcome" in current_url
                if on_login_page:
                    log.info("Waiting for login — complete sign-in in the browser...")
                    try:
                        await page.wait_for_url(
                            f"**/dashboard/{config.dashboard_id}/**",
                            timeout=login_timeout,
                        )
                        await page.wait_for_timeout(wait_ms)
                    except Exception:
                        result.error = "Login timed out — browser was closed or login took too long"
                        await browser.close()
                        return result
                else:
                    await page.wait_for_timeout(wait_ms)
            except Exception as e:
                log.error("Dashboard navigation failed: %s", e)
                result.error = f"Navigation failed: {e}"
                await browser.close()
                return result

        try:
            # Mask dynamic elements
            for selector in mask_selectors:
                elements = await page.query_selector_all(selector)
                for el in elements:
                    await el.evaluate("e => { e.style.visibility = 'hidden'; }")

            # Full page screenshot
            full_path = output_dir / "full-page.png"
            await page.screenshot(path=str(full_path), full_page=True)
            result.full_page = full_path

            # Per-section screenshots (by chart ID)
            if config.get("screenshots.sections", True):
                chart_elements = await page.query_selector_all("[data-test-chart-id]")
                for el in chart_elements:
                    chart_id = await el.get_attribute("data-test-chart-id")
                    if chart_id:
                        section_path = output_dir / f"chart-{chart_id}.png"
                        try:
                            await el.screenshot(path=str(section_path))
                            result.sections[chart_id] = section_path
                        except Exception as e:
                            log.debug("Could not capture chart %s: %s", chart_id, e)

            # Save storage state for reuse
            if not result.error:
                try:
                    secrets_dir = config.project_root / ".preset-toolkit" / ".secrets"
                    secrets_dir.mkdir(parents=True, exist_ok=True)
                    state_path = secrets_dir / "storage_state.json"
                    await context.storage_state(path=str(state_path))
                except Exception as e:
                    log.debug("Could not save storage state: %s", e)
        finally:
            await browser.close()

    t.track("screenshot_complete", {
        "sections_captured": len(result.sections),
        "has_full_page": result.full_page is not None,
        "has_error": bool(result.error),
        "auth_method": auth_method or "manual_login",
    })
    if result.error:
        t.track_error("screenshot", "capture_failed", result.error)
    return result
```

- [ ] **Step 2: Run all tests to verify nothing broke**

Run: `/Applications/Xcode.app/Contents/Developer/usr/bin/python3 -m pytest tests/ -v`
Expected: 134+ tests PASS

- [ ] **Step 3: Commit**

```bash
git add scripts/screenshot.py
git commit -m "feat: integrate auth fallback chain into capture_dashboard"
```

---

### Task 9: E2E manual verification

- [ ] **Step 1: Run bootstrap in clean test folder**

```bash
rm -rf /tmp/preset-e2e-cookie && mkdir -p /tmp/preset-e2e-cookie
cd /tmp/preset-e2e-cookie
bash "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit/scripts/bootstrap.sh"
```

Verify: `cryptography` appears in the verification output.

- [ ] **Step 2: Set up config and sync_config.yml**

Create `.preset-toolkit/config.yaml` and `sync/sync_config.yml` with the WCBM dashboard details (workspace_id 2194154, dashboard_id 76).

- [ ] **Step 3: Test screenshot with cookie extraction**

```bash
cd /tmp/preset-e2e-cookie
PLUGIN_ROOT="/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit"
source .venv/bin/activate
PYTHONPATH="${PLUGIN_ROOT}" .venv/bin/python3 -c "
from scripts.screenshot import capture_dashboard
from scripts.config import ToolkitConfig
from pathlib import Path
import asyncio

config = ToolkitConfig.discover()
result = asyncio.run(capture_dashboard(config, Path('screenshots')))
print('SUCCESS' if result.success else 'FAILED')
if result.full_page:
    print(f'FULL_PAGE: {result.full_page}')
if result.error:
    print(f'ERROR: {result.error}')
"
```

Expected: If Chrome has a Preset session, screenshot should capture WITHOUT opening a browser window.

- [ ] **Step 4: Commit final version bump**

```bash
cd "/Users/rishavchatterjee/Desktop/TWC Projects/preset-toolkit"
# Update version in plugin.json and marketplace.json to 0.5.0
git add -A
git commit -m "feat: screenshot browser cookie auth v0.5.0 — zero-login screenshots"
git push
```

- [ ] **Step 5: Update plugin cache**

```bash
CACHE_DIR=~/.claude/plugins/cache/preset-toolkit/preset-toolkit
rm -rf "$CACHE_DIR/0.4.1"
mkdir -p "$CACHE_DIR/0.5.0"
rsync -a --exclude='.git' --exclude='.venv' --exclude='__pycache__' --exclude='*.egg-info' --exclude='.preset-toolkit' --exclude='sync/' --exclude='screenshots/' . "$CACHE_DIR/0.5.0/"
```
