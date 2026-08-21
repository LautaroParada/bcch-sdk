"""Centralized HTTP transport for the Banco Central REST endpoint."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any

import requests

from .auth import TokenAuth
from .exceptions import (
    BCCHAPIError,
    BCCHAuthenticationError,
    BCCHConnectionError,
    BCCHHTTPError,
    BCCHRateLimitError,
    BCCHResponseError,
    BCCHTimeoutError,
)

DEFAULT_ENDPOINT = "https://si3.bcentral.cl/SieteRestWS/SieteRestWS.ashx"
RETRYABLE_HTTP_STATUSES = frozenset({429, 500, 502, 503, 504})


class RestTransport:
    """Small requests.Session-based REST transport with bounded retries."""

    def __init__(
        self,
        auth: TokenAuth,
        *,
        session: requests.Session | None = None,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout: float = 30.0,
        max_retries: int = 2,
        backoff_factor: float = 0.25,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be greater than zero")
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if backoff_factor < 0:
            raise ValueError("backoff_factor cannot be negative")
        self._auth = auth
        self._session = session or requests.Session()
        self.endpoint = endpoint
        self.timeout = float(timeout)
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self._sleep = sleep

    def request(self, params: Mapping[str, object]) -> dict[str, Any]:
        """Perform one logical REST call without mutating caller-owned parameters."""
        request_params = self._auth.add_to(dict(params))
        for attempt in range(self.max_retries + 1):
            try:
                response = self._session.get(
                    self.endpoint,
                    params=request_params,
                    timeout=self.timeout,
                )
            except requests.Timeout:
                if attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                raise BCCHTimeoutError(
                    "Banco Central REST request exceeded the configured timeout"
                ) from None
            except requests.ConnectionError:
                if attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                raise BCCHConnectionError(
                    "Could not connect to the Banco Central REST service"
                ) from None
            except requests.RequestException:
                raise BCCHConnectionError(
                    "Banco Central REST request failed before receiving a response"
                ) from None

            status = response.status_code
            if status in RETRYABLE_HTTP_STATUSES and attempt < self.max_retries:
                self._backoff(attempt, response=response)
                continue
            if status in {401, 403}:
                raise BCCHAuthenticationError(
                    f"Banco Central rejected the API Key Token with HTTP {status}"
                )
            if status == 429:
                raise BCCHRateLimitError("Banco Central REST rate limit exceeded")
            if status < 200 or status >= 300:
                raise BCCHHTTPError(status)

            try:
                payload = response.json()
            except (ValueError, requests.JSONDecodeError):
                raise BCCHResponseError(
                    "Banco Central REST response was not valid JSON"
                ) from None
            return self._validate_api_envelope(payload)

        raise AssertionError("unreachable retry state")

    def _validate_api_envelope(self, payload: object) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise BCCHResponseError("Banco Central REST response must be a JSON object")
        if "Codigo" not in payload or "Descripcion" not in payload:
            raise BCCHResponseError("Banco Central REST response is missing Codigo or Descripcion")
        try:
            code = int(payload["Codigo"])
        except (TypeError, ValueError):
            raise BCCHResponseError("Banco Central REST Codigo must be numeric") from None
        description = self._auth.redact(payload.get("Descripcion", ""))
        if code != 0:
            raise BCCHAPIError(code=code, description=description)
        return payload

    def _backoff(self, attempt: int, *, response: requests.Response | None = None) -> None:
        delay = self.backoff_factor * (2**attempt)
        if response is not None and response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            if retry_after is not None:
                try:
                    delay = max(delay, min(float(retry_after), 60.0))
                except ValueError:
                    pass
        if delay > 0:
            self._sleep(delay)

    def __repr__(self) -> str:
        return (
            f"RestTransport(endpoint={self.endpoint!r}, timeout={self.timeout!r}, "
            "token=<redacted>)"
        )

    __str__ = __repr__
