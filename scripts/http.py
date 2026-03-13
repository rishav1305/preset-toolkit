"""HTTP retry wrapper with exponential backoff and jitter."""
import random
import time
from typing import Any, Optional

import httpx

from scripts.logger import get_logger

log = get_logger("http")

_RETRYABLE_STATUS = {500, 502, 503, 504, 429}


def resilient_request(
    method: str,
    url: str,
    *,
    retries: int = 3,
    backoff_base: float = 1.0,
    timeout: float = 30.0,
    **kwargs: Any,
) -> httpx.Response:
    """Make an HTTP request with exponential backoff on transient failures.

    Retries on: connection errors, timeouts, and 5xx/429 status codes.
    Does NOT retry on 4xx client errors (except 429).
    """
    last_exc: Optional[Exception] = None

    for attempt in range(1, retries + 1):
        try:
            resp = httpx.request(method, url, timeout=timeout, **kwargs)
            resp.raise_for_status()
            return resp
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_exc = e
            if attempt < retries:
                wait = backoff_base * (2 ** (attempt - 1)) * (0.5 + random.random())
                log.warning(
                    "%s %s failed (attempt %d/%d): %s. Retrying in %.1fs...",
                    method, url, attempt, retries, type(e).__name__, wait,
                )
                time.sleep(wait)
            else:
                log.error("%s %s failed after %d attempts: %s", method, url, retries, e)
                raise
        except httpx.HTTPStatusError as e:
            if e.response.status_code not in _RETRYABLE_STATUS:
                raise
            last_exc = e
            if attempt < retries:
                wait = backoff_base * (2 ** (attempt - 1))
                log.warning(
                    "%s %s returned %d (attempt %d/%d). Retrying in %.1fs...",
                    method, url, e.response.status_code, attempt, retries, wait,
                )
                time.sleep(wait)
            else:
                log.error("%s %s failed after %d attempts: HTTP %d", method, url, retries, e.response.status_code)
                raise

    raise last_exc
