"""Token authentication configuration."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote_plus

from .exceptions import BCCHAuthenticationError


@dataclass(frozen=True, repr=False)
class TokenAuth:
    """Validated REST API token that never reveals its value in representations."""

    _token: str

    @classmethod
    def create(cls, token: str) -> TokenAuth:
        if not isinstance(token, str) or not token.strip():
            raise BCCHAuthenticationError("A non-empty Banco Central API Key Token is required")
        return cls(token.strip())

    def add_to(self, params: dict[str, object]) -> dict[str, object]:
        """Return a new parameter mapping containing the configured token."""
        safe_params = {
            key: value
            for key, value in params.items()
            if key not in {"token", "user", "pass"}
        }
        return {**safe_params, "token": self._token}

    def redact(self, text: object) -> str:
        """Redact raw and URL-encoded forms of this token from arbitrary text."""
        rendered = str(text)
        for secret in (self._token, quote_plus(self._token)):
            if secret:
                rendered = rendered.replace(secret, "<redacted>")
        return rendered

    def __repr__(self) -> str:
        return "TokenAuth(token=<redacted>)"

    __str__ = __repr__
