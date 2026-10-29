"""Lightweight typed models for REST responses."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from .exceptions import BCCHResponseError

_OBSERVATION_DATE = re.compile(r"^\d{2}-\d{2}-\d{4}$")


def parse_response_date(value: object, *, field: str) -> date:
    """Parse the documented ``DD-MM-YYYY`` response format."""
    if not isinstance(value, str) or not _OBSERVATION_DATE.fullmatch(value):
        raise BCCHResponseError(f"Invalid {field} date in Banco Central response")
    try:
        return datetime.strptime(value, "%d-%m-%Y").date()
    except ValueError as exc:
        raise BCCHResponseError(f"Invalid {field} date in Banco Central response") from exc


def parse_optional_response_date(value: object, *, field: str) -> date | None:
    # SearchSeries uses ND for dates of series without observations.
    # Observation dates remain mandatory and continue to use the strict parser.
    if value is None or value in ("", "ND"):
        return None
    return parse_response_date(value, field=field)


@dataclass(frozen=True, slots=True)
class Observation:
    """One observation returned by ``GetSeries``."""

    date: date
    value: float | None
    status_code: str | None

    @classmethod
    def from_payload(cls, payload: object) -> Observation:
        if not isinstance(payload, dict):
            raise BCCHResponseError("Each Series.Obs item must be a JSON object")
        observation_date = parse_response_date(
            payload.get("indexDateString"), field="observation"
        )
        raw_value = payload.get("value")
        if raw_value is None or (isinstance(raw_value, str) and raw_value.casefold() == "nan"):
            value = None
        else:
            try:
                value = float(raw_value)
            except (TypeError, ValueError) as exc:
                raise BCCHResponseError("Invalid numeric value in Series.Obs") from exc
            if math.isnan(value):
                value = None
        status_code = payload.get("statusCode")
        if status_code is not None and not isinstance(status_code, str):
            raise BCCHResponseError("Invalid statusCode in Series.Obs")
        return cls(date=observation_date, value=value, status_code=status_code)


@dataclass(frozen=True, slots=True)
class SeriesResult:
    """Typed result from ``GetSeries`` with the unmodified JSON retained."""

    series_id: str
    title_es: str | None
    title_en: str | None
    observations: tuple[Observation, ...]
    raw: dict[str, Any]

    def to_dataframe(self) -> Any:
        """Return observations as a pandas DataFrame when the optional extra exists."""
        try:
            import pandas as pd
        except ImportError as exc:
            raise ImportError(
                'pandas is optional; install it with: pip install "bcch[dataframe]"'
            ) from exc

        frame = pd.DataFrame(
            {
                "date": [item.date for item in self.observations],
                "value": [item.value for item in self.observations],
                "status_code": [item.status_code for item in self.observations],
            }
        )
        return frame.set_index("date")


@dataclass(frozen=True, slots=True)
class SeriesInfo:
    """Typed metadata item returned by ``SearchSeries``."""

    series_id: str
    frequency: str | None
    title_es: str | None
    title_en: str | None
    first_observation: date | None
    last_observation: date | None
    updated_at: date | None
    created_at: date | None
    raw: dict[str, Any]

    @classmethod
    def from_payload(cls, payload: object) -> SeriesInfo:
        if not isinstance(payload, dict):
            raise BCCHResponseError("Each SeriesInfos item must be a JSON object")
        series_id = payload.get("seriesId")
        if not isinstance(series_id, str) or not series_id:
            raise BCCHResponseError("SeriesInfos item has no valid seriesId")
        return cls(
            series_id=series_id,
            frequency=_optional_string(payload.get("frequencyCode"), "frequencyCode"),
            title_es=_optional_string(payload.get("spanishTitle"), "spanishTitle"),
            title_en=_optional_string(payload.get("englishTitle"), "englishTitle"),
            first_observation=parse_optional_response_date(
                payload.get("firstObservation"), field="firstObservation"
            ),
            last_observation=parse_optional_response_date(
                payload.get("lastObservation"), field="lastObservation"
            ),
            updated_at=parse_optional_response_date(payload.get("updatedAt"), field="updatedAt"),
            created_at=parse_optional_response_date(payload.get("createdAt"), field="createdAt"),
            raw=dict(payload),
        )


def _optional_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise BCCHResponseError(f"Invalid {field} in Banco Central response")
    return value
