"""Exceptions raised by the bcch package."""

from __future__ import annotations


class BCCHError(Exception):
    """Base class for all package-specific errors."""


class BCCHAuthenticationError(BCCHError):
    """Raised when REST authentication cannot be used."""


class BCCHLegacyAuthenticationError(BCCHAuthenticationError):
    """Raised for the historical username/password constructor."""


class BCCHConnectionError(BCCHError):
    """Raised when the Banco Central service cannot be reached."""


class BCCHTimeoutError(BCCHConnectionError):
    """Raised when a REST request exceeds the configured timeout."""


class BCCHAPIError(BCCHError):
    """Raised when Banco Central returns a nonzero API result code."""

    def __init__(self, code: int, description: str) -> None:
        self.code = code
        self.description = description
        super().__init__(f"Banco Central API error {code}: {description}")


class BCCHResponseError(BCCHError):
    """Raised when a response is malformed or has an unexpected shape."""


class BCCHRateLimitError(BCCHError):
    """Raised when the REST endpoint continues to return HTTP 429."""


class BCCHHTTPError(BCCHError):
    """Raised for an unsuccessful HTTP response."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code
        super().__init__(f"Banco Central REST request failed with HTTP {status_code}")
