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
