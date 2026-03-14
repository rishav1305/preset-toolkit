"""Tests for browser cookie extraction module."""
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from scripts.browser_cookies import (
    _decrypt_chromium_value,
    _extract_chromium_cookies,
    _extract_firefox_cookies,
    _get_chromium_key,
    extract_cookies,
)


# ── Decryption tests ─────────────────────────────────────────────────


def _encrypt_value(plaintext: bytes, key: bytes) -> bytes:
    """Helper: encrypt a value the way Chromium does (v10 + AES-CBC)."""
    from cryptography.hazmat.primitives import padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    iv = b" " * 16
    padder = padding.PKCS7(128).padder()
    padded = padder.update(plaintext) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return b"v10" + ciphertext


def test_decrypt_chromium_value_known_pair():
    """Encrypt a value with a known key, verify decryption roundtrip."""
    key = b"\x00" * 16
    encrypted = _encrypt_value(b"test_cookie_value", key)
    result = _decrypt_chromium_value(encrypted, key)
    assert result == "test_cookie_value"


def test_decrypt_handles_v10_prefix():
    """Verify v10 prefix is stripped before decryption."""
    key = b"\x01" * 16
    encrypted = _encrypt_value(b"hello", key)
    result = _decrypt_chromium_value(encrypted, key)
    assert result == "hello"


# ── Keychain tests ───────────────────────────────────────────────────


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


# ── Chromium extraction tests ────────────────────────────────────────


def _create_chromium_cookie_db(db_path, cookies, key):
    """Helper: create a mock Chromium Cookies SQLite DB with encrypted values."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE cookies (
            host_key TEXT, name TEXT, encrypted_value BLOB,
            path TEXT, expires_utc INTEGER, is_secure INTEGER, is_httponly INTEGER
        )
    """)
    for c in cookies:
        encrypted = _encrypt_value(c["value"].encode(), key)
        conn.execute(
            "INSERT INTO cookies VALUES (?, ?, ?, ?, ?, ?, ?)",
            (c["domain"], c["name"], encrypted, c.get("path", "/"),
             c.get("expires", 0), c.get("secure", 1), c.get("httponly", 1)),
        )
    conn.commit()
    conn.close()


def test_extract_chromium_cookies_from_mock_db(tmp_path):
    """Extract and decrypt cookies from a mock Chromium DB."""
    key = b"\x00" * 16
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


def test_cookie_db_copied_to_temp(tmp_path):
    """Verify the original DB is not opened directly — a temp copy is used."""
    key = b"\x00" * 16
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
    key = b"\x00" * 16
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


# ── Firefox extraction tests ─────────────────────────────────────────


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


# ── Public API tests ─────────────────────────────────────────────────


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
