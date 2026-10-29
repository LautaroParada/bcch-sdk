from __future__ import annotations

import builtins
from datetime import date

import pytest

from bcch import BancoCentralDeChile, BCCHResponseError, Observation, SeriesResult

from .conftest import FakeResponse, FakeSession, get_series_payload, search_series_payload

TOKEN = "test-token-placeholder"


def _client_with(payloads: list[object]) -> tuple[BancoCentralDeChile, FakeSession]:
    session = FakeSession(payloads)
    client = BancoCentralDeChile(token=TOKEN, session=session, max_retries=0)
    return client, session


def test_get_series_builds_documented_rest_parameters() -> None:
    client, session = _client_with([FakeResponse(get_series_payload())])

    client.get_series(
        "F073.TCO.PRE.Z.D",
        start="2025-01-01",
        end="2025-12-31",
    )

    assert session.calls[0]["params"] == {
        "token": TOKEN,
        "function": "GetSeries",
        "timeseries": "F073.TCO.PRE.Z.D",
        "firstdate": "2025-01-01",
        "lastdate": "2025-12-31",
    }


def test_get_series_historical_parameter_aliases() -> None:
    client, session = _client_with([FakeResponse(get_series_payload())])

    client.get_series(
        serie="F073.TCO.PRE.Z.D",
        from_="2025-01-01",
        to_="2025-01-31",
    )

    params = session.calls[0]["params"]
    assert params["timeseries"] == "F073.TCO.PRE.Z.D"
    assert params["firstdate"] == "2025-01-01"
    assert params["lastdate"] == "2025-01-31"


def test_get_series_success_returns_typed_metadata_and_date() -> None:
    payload = get_series_payload()
    client, _ = _client_with([FakeResponse(payload)])

    result = client.get_series("F073.TCO.PRE.Z.D")

    assert result.series_id == "F073.TCO.PRE.Z.D"
    assert result.title_es == "Dólar observado"
    assert result.title_en == "Observed dollar"
    assert result.observations == (
        Observation(date=date(2024, 10, 1), value=897.68, status_code="OK"),
    )
    assert result.raw == payload


def test_nan_and_nd_are_preserved_as_missing_value_and_status() -> None:
    client, _ = _client_with(
        [FakeResponse(get_series_payload(value="NaN", status_code="ND"))]
    )

    observation = client.get_series("F073.TCO.PRE.Z.D").observations[0]

    assert observation.value is None
    assert observation.status_code == "ND"


@pytest.mark.parametrize(
    "start,end",
    [
        ("2025-1-01", None),
        ("2025/01/01", None),
        ("2025-02-30", None),
        (None, "01-02-2025"),
    ],
)
def test_invalid_dates_fail_before_http(start: str | None, end: str | None) -> None:
    client, session = _client_with([])

    with pytest.raises(ValueError):
        client.get_series("SERIES", start=start, end=end)

    assert session.calls == []


def test_start_after_end_fails_before_http() -> None:
    client, session = _client_with([])

    with pytest.raises(ValueError, match="start cannot be after end"):
        client.get_series("SERIES", start="2025-02-01", end="2025-01-01")

    assert session.calls == []


@pytest.mark.parametrize("series", ["", "   ", None])
def test_empty_series_code_fails_before_http(series: str | None) -> None:
    client, session = _client_with([])

    with pytest.raises(ValueError):
        client.get_series(series)

    assert session.calls == []


@pytest.mark.parametrize(
    "alias,canonical",
    [
        ("daily", "DAILY"),
        ("Diaria", "DAILY"),
        ("MONTHLY", "MONTHLY"),
        ("mensual", "MONTHLY"),
        ("quarterly", "QUARTERLY"),
        ("TRIMESTRAL", "QUARTERLY"),
        ("annual", "ANNUAL"),
        ("anual", "ANNUAL"),
    ],
)
def test_frequency_aliases_are_normalized(alias: str, canonical: str) -> None:
    client, session = _client_with([FakeResponse(search_series_payload())])

    client.search_series(alias)

    assert session.calls[0]["params"] == {
        "token": TOKEN,
        "function": "SearchSeries",
        "frequency": canonical,
    }


def test_frequency_trailing_space_regression() -> None:
    client, session = _client_with([FakeResponse(search_series_payload())])

    client.search_series(frequency="quarterly")

    assert session.calls[0]["params"]["frequency"] == "QUARTERLY"


def test_invalid_frequency_fails_before_http() -> None:
    client, session = _client_with([])

    with pytest.raises(ValueError, match="Unsupported frequency"):
        client.search_series("weekly")

    assert session.calls == []


def test_search_series_success_returns_typed_items_and_dates() -> None:
    client, _ = _client_with([FakeResponse(search_series_payload())])

    results = client.search_series(frecuencia="diaria")

    assert len(results) == 1
    assert results[0].series_id == "F073.TCO.PRE.Z.D"
    assert results[0].frequency == "DAILY"
    assert results[0].first_observation == date(1982, 8, 9)
    assert results[0].raw["spanishTitle"] == "Dólar observado"


@pytest.mark.parametrize("field", ["firstObservation", "lastObservation", "updatedAt", "createdAt"])
def test_search_series_nd_metadata_date_does_not_break_catalog(field: str) -> None:
    payload = search_series_payload()
    payload["SeriesInfos"][0][field] = "ND"
    client, _ = _client_with([FakeResponse(payload)])
    item = client.search_series("DAILY")[0]
    attribute = {"firstObservation": "first_observation", "lastObservation": "last_observation",
                 "updatedAt": "updated_at", "createdAt": "created_at"}[field]
    assert getattr(item, attribute) is None
    assert item.raw[field] == "ND"


def test_nd_is_not_accepted_as_an_observation_date() -> None:
    client, _ = _client_with([FakeResponse(get_series_payload(observation_date="ND"))])
    with pytest.raises(BCCHResponseError, match="observation"):
        client.get_series("F073.TCO.PRE.Z.D")


@pytest.mark.parametrize(
    "payload",
    [
        {"Codigo": 0, "Descripcion": "Success", "Series": None},
        {
            "Codigo": 0,
            "Descripcion": "Success",
            "Series": {"seriesId": "SERIES", "Obs": None},
        },
        {
            "Codigo": 0,
            "Descripcion": "Success",
            "Series": {"seriesId": None, "Obs": []},
        },
    ],
)
def test_unexpected_get_series_shape(payload: dict[str, object]) -> None:
    client, _ = _client_with([FakeResponse(payload)])

    with pytest.raises(BCCHResponseError):
        client.get_series("SERIES")


def test_unexpected_search_series_shape() -> None:
    client, _ = _client_with(
        [FakeResponse({"Codigo": 0, "Descripcion": "Success", "SeriesInfos": None})]
    )

    with pytest.raises(BCCHResponseError):
        client.search_series("daily")


def test_malformed_observation_date_raises_response_error() -> None:
    client, _ = _client_with(
        [FakeResponse(get_series_payload(observation_date="2024-10-01"))]
    )

    with pytest.raises(BCCHResponseError, match="observation date"):
        client.get_series("SERIES")


def test_get_many_sequence_uses_codes_as_keys_and_preserves_order() -> None:
    codes = ["SERIES_B", "SERIES_A", "SERIES_C"]
    payloads = [FakeResponse(get_series_payload(code)) for code in codes]
    client, _ = _client_with(payloads)

    results = client.get_many(codes)

    assert list(results) == codes
    assert [result.series_id for result in results.values()] == codes


def test_get_many_mapping_uses_aliases_and_preserves_order() -> None:
    mapping = {"usd": "SERIES_A", "uf": "SERIES_B"}
    payloads = [FakeResponse(get_series_payload(code)) for code in mapping.values()]
    client, _ = _client_with(payloads)

    results = client.get_many(mapping)

    assert list(results) == ["usd", "uf"]
    assert results["usd"].series_id == "SERIES_A"
    assert results["uf"].series_id == "SERIES_B"


def test_get_many_rejects_a_string() -> None:
    client, session = _client_with([])

    with pytest.raises(TypeError):
        client.get_many("SERIES")

    assert session.calls == []


def test_rate_limiter_waits_before_sixth_retrieval() -> None:
    now = [0.0]
    sleeps: list[float] = []

    def clock() -> float:
        return now[0]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        now[0] += seconds

    payloads = [FakeResponse(get_series_payload(f"SERIES_{index}")) for index in range(6)]
    session = FakeSession(payloads)
    client = BancoCentralDeChile(
        token=TOKEN,
        session=session,
        max_retries=0,
        _clock=clock,
        _sleep=sleep,
    )

    client.get_many([f"SERIES_{index}" for index in range(6)])

    assert sleeps == [1.0]
    assert len(session.calls) == 6


def test_get_macro_preserves_historical_list_of_dicts_shape() -> None:
    payload = get_series_payload(value="NaN", status_code="ND")
    client, _ = _client_with([FakeResponse(payload)])

    with pytest.warns(DeprecationWarning, match="get_series"):
        result = client.get_macro(serie="F073.TCO.PRE.Z.D")

    assert result == payload["Series"]["Obs"]
    assert isinstance(result[0], dict)
    assert result[0]["value"] == "NaN"


def test_get_busqueda_preserves_historical_list_of_dicts_shape() -> None:
    payload = search_series_payload()
    client, _ = _client_with([FakeResponse(payload)])

    with pytest.warns(DeprecationWarning, match="search_series"):
        result = client.get_busqueda(frecuencia="quarterly")

    assert result == payload["SeriesInfos"]
    assert isinstance(result[0], dict)


def test_optional_pandas_absence_has_install_instruction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = SeriesResult(
        series_id="SERIES",
        title_es=None,
        title_en=None,
        observations=(),
        raw={},
    )
    original_import = builtins.__import__

    def blocked_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "pandas":
            raise ImportError("blocked for test")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    with pytest.raises(ImportError, match=r'pip install "bcch\[dataframe\]"'):
        result.to_dataframe()


def test_optional_pandas_dataframe_conversion() -> None:
    pandas = pytest.importorskip("pandas")
    result = SeriesResult(
        series_id="SERIES",
        title_es=None,
        title_en=None,
        observations=(
            Observation(date=date(2025, 1, 1), value=1.25, status_code="OK"),
            Observation(date=date(2025, 1, 2), value=None, status_code="ND"),
        ),
        raw={},
    )

    frame = result.to_dataframe()

    assert isinstance(frame, pandas.DataFrame)
    assert frame.index.name == "date"
    assert frame.loc[date(2025, 1, 1), "value"] == 1.25
    assert pandas.isna(frame.loc[date(2025, 1, 2), "value"])
    assert frame.loc[date(2025, 1, 2), "status_code"] == "ND"
