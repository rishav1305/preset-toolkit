"""Tests for HTTP retry wrapper."""
import httpx
import pytest
from unittest.mock import patch, MagicMock
from scripts.http import resilient_request


def test_success_on_first_try():
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    with patch("httpx.request", return_value=mock_resp):
        resp = resilient_request("GET", "https://example.com/api")
        assert resp.status_code == 200


def test_retries_on_500():
    fail_resp = MagicMock(spec=httpx.Response)
    fail_resp.status_code = 500
    fail_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=fail_resp
    )
    ok_resp = MagicMock(spec=httpx.Response)
    ok_resp.status_code = 200
    ok_resp.raise_for_status = MagicMock()
    with patch("httpx.request", side_effect=[fail_resp, ok_resp]):
        resp = resilient_request("GET", "https://example.com/api", retries=3, backoff_base=0.01)
        assert resp.status_code == 200


def test_retries_on_connect_error():
    ok_resp = MagicMock(spec=httpx.Response)
    ok_resp.status_code = 200
    ok_resp.raise_for_status = MagicMock()
    with patch("httpx.request", side_effect=[httpx.ConnectError("down"), ok_resp]):
        resp = resilient_request("GET", "https://example.com/api", retries=2, backoff_base=0.01)
        assert resp.status_code == 200


def test_raises_after_exhausted_retries():
    fail_resp = MagicMock(spec=httpx.Response)
    fail_resp.status_code = 503
    fail_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "503", request=MagicMock(), response=fail_resp
    )
    with patch("httpx.request", return_value=fail_resp):
        with pytest.raises(httpx.HTTPStatusError):
            resilient_request("GET", "https://example.com/api", retries=2, backoff_base=0.01)


def test_no_retry_on_4xx():
    fail_resp = MagicMock(spec=httpx.Response)
    fail_resp.status_code = 403
    fail_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=MagicMock(), response=fail_resp
    )
    with patch("httpx.request", return_value=fail_resp) as mock_req:
        with pytest.raises(httpx.HTTPStatusError):
            resilient_request("GET", "https://example.com/api", retries=3, backoff_base=0.01)
        assert mock_req.call_count == 1


def test_429_retry_has_jitter():
    """HTTPStatusError retries (429) should include jitter, not fixed delays."""
    fail_resp = MagicMock(spec=httpx.Response)
    fail_resp.status_code = 429
    fail_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=fail_resp
    )
    ok_resp = MagicMock(spec=httpx.Response)
    ok_resp.status_code = 200
    ok_resp.raise_for_status = MagicMock()
    sleep_times = []
    with patch("httpx.request", side_effect=[fail_resp, ok_resp]):
        with patch("scripts.http.time.sleep", side_effect=lambda t: sleep_times.append(t)):
            resp = resilient_request("GET", "https://example.com/api", retries=3, backoff_base=1.0)
            assert resp.status_code == 200
    # Jitter means sleep time > base (1.0) — it includes random.uniform(0, 0.5)
    assert len(sleep_times) == 1
    assert sleep_times[0] >= 1.0  # base_wait
    assert sleep_times[0] <= 1.5  # base_wait + max jitter


def test_tls_verify_from_env():
    """Should honor SSL_CERT_FILE env var."""
    from scripts.http import _get_verify
    with patch.dict("os.environ", {"SSL_CERT_FILE": "/custom/ca.pem"}):
        assert _get_verify() == "/custom/ca.pem"


def test_tls_verify_fallback_requests_ca():
    """Should fall back to REQUESTS_CA_BUNDLE."""
    from scripts.http import _get_verify
    with patch.dict("os.environ", {"REQUESTS_CA_BUNDLE": "/corp/ca.pem"}, clear=False):
        # Remove SSL_CERT_FILE if present
        import os
        env = os.environ.copy()
        env.pop("SSL_CERT_FILE", None)
        with patch.dict("os.environ", env, clear=True):
            with patch.dict("os.environ", {"REQUESTS_CA_BUNDLE": "/corp/ca.pem"}):
                assert _get_verify() == "/corp/ca.pem"


def test_tls_verify_default():
    """Without env vars, verify defaults to True."""
    from scripts.http import _get_verify
    with patch.dict("os.environ", {}, clear=True):
        assert _get_verify() is True
