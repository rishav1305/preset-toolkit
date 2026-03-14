"""Extract browser cookies for Preset authentication.

Reads cookie databases from installed browsers (Chrome, Firefox, Edge, Arc)
on macOS. Chromium cookies are decrypted via Keychain + AES-CBC.
"""
import hashlib
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


def _decrypt_chromium_value(encrypted_value: bytes, key: bytes) -> str:
    """Decrypt a single Chromium cookie value using AES-128-CBC.

    Chromium cookies on macOS are prefixed with b'v10' followed by
    AES-128-CBC encrypted data. IV is 16 space bytes (0x20).
    """
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

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


def _get_chromium_key(keychain_service: str, keychain_account: str) -> Optional[bytes]:
    """Get AES key for Chromium cookie decryption from macOS Keychain.

    Calls `security find-generic-password` to get the raw password, then
    derives the AES-128 key via PBKDF2 (salt=b'saltysalt', iterations=1003).

    Returns 16-byte key on success, None on failure.
    """
    log.info("Requesting Keychain access for %s cookies...", keychain_account)
    try:
        result = subprocess.run(
            [
                "security", "find-generic-password", "-w",
                "-s", keychain_service, "-a", keychain_account,
            ],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            log.info("Keychain access denied for %s", keychain_account)
            return None

        password = result.stdout.strip()
        key = hashlib.pbkdf2_hmac(
            "sha1", password.encode("utf-8"), b"saltysalt", 1003, dklen=16,
        )
        return key
    except (subprocess.TimeoutExpired, FileNotFoundError, Exception) as e:
        log.debug("Keychain access failed for %s: %s", keychain_account, e)
        return None


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
        matches = list(profiles_dir.glob(pattern)) if profiles_dir.exists() else []
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


def extract_cookies(domain: str) -> List[Dict]:
    """Extract cookies for domain from installed browsers.

    Returns list of Playwright-compatible cookie dicts:
    [{"name": "session", "value": "abc", "domain": ".preset.io", "path": "/", ...}]

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
