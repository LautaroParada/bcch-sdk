from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
import requests


class FakeResponse:
    def __init__(
        self,
        payload: object = None,
        *,
        status_code: int = 200,
        headers: dict[str, str] | None = None,
        json_error: Exception | None = None,
    ) -> None:
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}
        self.json_error = json_error

    def json(self) -> object:
        if self.json_error is not None:
            raise self.json_error
        return self.payload


class FakeSession(requests.Session):
    def __init__(self, responses: list[object] | None = None) -> None:
        super().__init__()
        self.responses = list(responses or [])
        self.calls: list[dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        if not self.responses:
            raise AssertionError("FakeSession has no queued response")
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        assert isinstance(response, FakeResponse)
        return response


def get_series_payload(
    series_id: str = "F073.TCO.PRE.Z.D",
    *,
    value: str = "897.68",
    status_code: str = "OK",
    observation_date: str = "01-10-2024",
) -> dict[str, object]:
    return {
        "Codigo": 0,
        "Descripcion": "Success",
        "Series": {
            "descripEsp": "Dólar observado",
            "descripIng": "Observed dollar",
            "seriesId": series_id,
            "Obs": [
                {
                    "indexDateString": observation_date,
                    "value": value,
                    "statusCode": status_code,
                }
            ],
        },
        "SeriesInfos": [],
    }


def search_series_payload() -> dict[str, object]:
    return {
        "Codigo": 0,
        "Descripcion": "Success",
        "Series": {
            "descripEsp": None,
            "descripIng": None,
            "seriesId": None,
            "Obs": None,
        },
        "SeriesInfos": [
            {
                "seriesId": "F073.TCO.PRE.Z.D",
                "frequencyCode": "DAILY",
                "spanishTitle": "Dólar observado",
                "englishTitle": "Observed dollar",
                "firstObservation": "09-08-1982",
                "lastObservation": "22-10-2025",
                "updatedAt": "21-10-2025",
                "createdAt": "21-10-2025",
            }
        ],
    }


@pytest.fixture
def fake_response() -> type[FakeResponse]:
    return FakeResponse


@pytest.fixture
def fake_session() -> Iterator[FakeSession]:
    session = FakeSession()
    try:
        yield session
    finally:
        session.close()
