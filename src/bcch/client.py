"""Public client composed from authentication, transport, and local catalog."""

from __future__ import annotations

import re
import threading
import time
import unicodedata
import warnings
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from datetime import date
from typing import Any

import requests

from .auth import TokenAuth
from .catalog import SeriesCatalog
from .exceptions import BCCHLegacyAuthenticationError, BCCHResponseError
from .models import Observation, SeriesInfo, SeriesResult
from .transport import DEFAULT_ENDPOINT, RestTransport

_REQUEST_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_FREQUENCIES = {
    "daily": "DAILY",
    "diaria": "DAILY",
    "monthly": "MONTHLY",
    "mensual": "MONTHLY",
    "quarterly": "QUARTERLY",
    "trimestral": "QUARTERLY",
    "annual": "ANNUAL",
    "anual": "ANNUAL",
}


class _SeriesRateLimiter:
    """Sliding-window limiter for the documented five-series/second maximum."""

    def __init__(
        self,
        *,
        limit: int = 5,
        window: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.limit = limit
        self.window = window
        self._clock = clock
        self._sleep = sleep
        self._calls: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            while True:
                now = self._clock()
                while self._calls and now - self._calls[0] >= self.window:
                    self._calls.popleft()
                if len(self._calls) < self.limit:
                    self._calls.append(now)
                    return
                wait_for = self.window - (now - self._calls[0])
                self._sleep(max(wait_for, 0.0))


class BancoCentralDeChile:
    """Unofficial client for the Banco Central de Chile BDE REST API."""

    def __init__(
        self,
        *args: str,
        token: str | None = None,
        timeout: float = 30.0,
        usuario: str | None = None,
        clave: str | None = None,
        session: requests.Session | None = None,
        max_retries: int = 2,
        backoff_factor: float = 0.25,
        _clock: Callable[[], float] = time.monotonic,
        _sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if usuario is not None or clave is not None or len(args) >= 2:
            raise BCCHLegacyAuthenticationError(
                "Username/password authentication is not supported by this REST client. "
                'Migrate to BancoCentralDeChile(token="...").'
            )
        if len(args) == 1:
            if token is not None:
                raise TypeError("token was supplied both positionally and by keyword")
            token = args[0]
        if token is None:
            token = ""
        self._auth = TokenAuth.create(token)
        self._transport = RestTransport(
            self._auth,
            session=session,
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
            sleep=_sleep,
        )
        self._rate_limiter = _SeriesRateLimiter(clock=_clock, sleep=_sleep)
        self.catalog = SeriesCatalog()

    def get_series(
        self,
        series: str | None = None,
        *,
        start: str | None = None,
        end: str | None = None,
        **aliases: str,
    ) -> SeriesResult:
        """Retrieve one BDE series through the live GetSeries REST operation."""
        series = _resolve_alias(series, aliases, "serie", "timeseries")
        start = _resolve_alias(start, aliases, "from_", "firstdate")
        end = _resolve_alias(end, aliases, "to_", "lastdate")
        _raise_unexpected(aliases)
        series_code = _validate_series(series)
        start_date = _validate_request_date(start, "start")
        end_date = _validate_request_date(end, "end")
        if start_date is not None and end_date is not None and start_date > end_date:
            raise ValueError("start cannot be after end")

        params: dict[str, object] = {"function": "GetSeries", "timeseries": series_code}
        if start is not None:
            params["firstdate"] = start
        if end is not None:
            params["lastdate"] = end
        self._rate_limiter.acquire()
        payload = self._transport.request(params)
        series_payload = payload.get("Series")
        if not isinstance(series_payload, dict):
            raise BCCHResponseError("GetSeries response has no valid Series object")
        observations_payload = series_payload.get("Obs")
        if not isinstance(observations_payload, list):
            raise BCCHResponseError("GetSeries response has no valid Series.Obs list")
        returned_id = series_payload.get("seriesId")
        if not isinstance(returned_id, str) or not returned_id:
            raise BCCHResponseError("GetSeries response has no valid Series.seriesId")
        title_es = _optional_response_string(series_payload.get("descripEsp"), "descripEsp")
        title_en = _optional_response_string(series_payload.get("descripIng"), "descripIng")
        observations = tuple(Observation.from_payload(item) for item in observations_payload)
        return SeriesResult(
            series_id=returned_id,
            title_es=title_es,
            title_en=title_en,
            observations=observations,
            raw=dict(payload),
        )

    def search_series(
        self, frequency: str | None = None, **aliases: str
    ) -> list[SeriesInfo]:
        """Retrieve live series metadata through the SearchSeries operation."""
        frequency = _resolve_alias(frequency, aliases, "frecuencia")
        _raise_unexpected(aliases)
        normalized = _normalize_frequency(frequency)
        payload = self._transport.request(
            {"function": "SearchSeries", "frequency": normalized}
        )
        items = payload.get("SeriesInfos")
        if not isinstance(items, list):
            raise BCCHResponseError("SearchSeries response has no valid SeriesInfos list")
        return [SeriesInfo.from_payload(item) for item in items]

    def get_many(
        self,
        series: Sequence[str] | Mapping[str, str],
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> dict[str, SeriesResult]:
        """Retrieve multiple series serially; the REST API has no bulk operation."""
        if isinstance(series, Mapping):
            items = series.items()
        elif isinstance(series, Sequence) and not isinstance(series, (str, bytes)):
            items = ((code, code) for code in series)
        else:
            raise TypeError("series must be a sequence of codes or a mapping of aliases to codes")
        return {
            alias: self.get_series(code, start=start, end=end) for alias, code in items
        }

    def get_many_dataframe(
        self,
        series: Sequence[str] | Mapping[str, str],
        *,
        start: str | None = None,
        end: str | None = None,
    ) -> Any:
        """Return values from get_many as an outer-joined pandas DataFrame."""
        results = self.get_many(series, start=start, end=end)
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                'pandas is optional; install it with: pip install "bcch[dataframe]"'
            ) from exc
        columns = {alias: result.to_dataframe()["value"] for alias, result in results.items()}
        return pd.DataFrame(columns)

    def get_macro(self, **query_params: str) -> list[dict[str, Any]]:
        """Deprecated compatibility wrapper preserving the historical return shape."""
        warnings.warn(
            "get_macro() is deprecated; use get_series(), which returns SeriesResult",
            DeprecationWarning,
            stacklevel=2,
        )
        result = self.get_series(**query_params)
        raw_observations = result.raw["Series"]["Obs"]
        return [dict(item) for item in raw_observations]

    def get_busqueda(self, **query_params: str) -> list[dict[str, Any]]:
        """Deprecated compatibility wrapper preserving the historical return shape."""
        warnings.warn(
            "get_busqueda() is deprecated; use search_series(), which returns SeriesInfo items",
            DeprecationWarning,
            stacklevel=2,
        )
        return [dict(item.raw) for item in self.search_series(**query_params)]

    def __repr__(self) -> str:
        return (
            f"BancoCentralDeChile(endpoint={DEFAULT_ENDPOINT!r}, "
            f"timeout={self._transport.timeout!r}, token=<redacted>)"
        )

    __str__ = __repr__


def _resolve_alias(
    current: str | None, aliases: dict[str, str], *names: str
) -> str | None:
    for name in names:
        if name not in aliases:
            continue
        candidate = aliases.pop(name)
        if current is not None and candidate != current:
            raise TypeError(f"Conflicting values for {name}")
        current = candidate
    return current


def _raise_unexpected(aliases: dict[str, str]) -> None:
    if aliases:
        unexpected = ", ".join(sorted(aliases))
        raise TypeError(f"Unexpected parameter(s): {unexpected}")


def _validate_series(series: str | None) -> str:
    if not isinstance(series, str) or not series.strip():
        raise ValueError("series must be a non-empty string")
    return series.strip()


def _validate_request_date(value: str | None, name: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _REQUEST_DATE.fullmatch(value):
        raise ValueError(f"{name} must use the exact YYYY-MM-DD format")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid YYYY-MM-DD date") from exc


def _normalize_frequency(value: str | None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("frequency is required")
    normalized = unicodedata.normalize("NFKD", value.strip())
    folded = "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).casefold()
    try:
        return _FREQUENCIES[folded]
    except KeyError as exc:
        accepted = "DAILY, MONTHLY, QUARTERLY, ANNUAL"
        raise ValueError(f"Unsupported frequency; use one of: {accepted}") from exc


def _optional_response_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BCCHResponseError(f"GetSeries response has an invalid {field}")
    return value
