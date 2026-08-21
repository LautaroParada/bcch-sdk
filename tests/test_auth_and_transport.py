from __future__ import annotations

from urllib.parse import quote_plus

import pytest
import requests

from bcch import (
    BancoCentralDeChile,
    BCCHAPIError,
    BCCHAuthenticationError,
    BCCHConnectionError,
    BCCHHTTPError,
    BCCHLegacyAuthenticationError,
    BCCHRateLimitError,
    BCCHResponseError,
    BCCHTimeoutError,
)
from bcch.auth import TokenAuth
from bcch.transport import RestTransport

from .conftest import FakeResponse, FakeSession

TOKEN = "test-token-placeholder"


def test_token_constructor_and_redacted_representations() -> None:
    client = BancoCentralDeChile(token=TOKEN)

    assert TOKEN not in repr(client)
    assert TOKEN not in str(client)
    assert "<redacted>" in repr(client)
    assert TOKEN not in repr(client._transport)
    assert TOKEN not in repr(client._auth)


@pytest.mark.parametrize("token", ["", "   ", None])
def test_empty_token_rejected(token: str | None) -> None:
    with pytest.raises(BCCHAuthenticationError):
        BancoCentralDeChile(token=token)


def test_legacy_positional_constructor_fails_before_network() -> None:
    session = FakeSession()

    with pytest.raises(BCCHLegacyAuthenticationError, match="token"):
        BancoCentralDeChile("historical-user", "historical-password", session=session)

    assert session.calls == []


def test_legacy_keyword_constructor_fails_before_network() -> None:
    session = FakeSession()

    with pytest.raises(BCCHLegacyAuthenticationError):
        BancoCentralDeChile(usuario="historical-user", clave="historical-password", session=session)

    assert session.calls == []


def test_transport_adds_token_without_mutating_caller_dictionary() -> None:
    params = {
        "function": "GetSeries",
        "timeseries": "SERIES",
        "token": "caller-override",
        "user": "must-not-be-sent",
        "pass": "must-not-be-sent",
    }
    session = FakeSession(
        [FakeResponse({"Codigo": 0, "Descripcion": "Success", "Series": {}})]
    )
    transport = RestTransport(TokenAuth.create(TOKEN), session=session, max_retries=0)

    transport.request(params)

    assert params == {
        "function": "GetSeries",
        "timeseries": "SERIES",
        "token": "caller-override",
        "user": "must-not-be-sent",
        "pass": "must-not-be-sent",
    }
    assert session.calls[0]["params"] == {
        "function": "GetSeries",
        "timeseries": "SERIES",
        "token": TOKEN,
    }


def test_api_error_preserves_code_description_and_redacts_token() -> None:
    secret = "token with/slash"
    encoded = quote_plus(secret)
    session = FakeSession(
        [
            FakeResponse(
                {
                    "Codigo": 17,
                    "Descripcion": f"Rejected {secret} and {encoded}",
                }
            )
        ]
    )
    transport = RestTransport(TokenAuth.create(secret), session=session, max_retries=0)

    with pytest.raises(BCCHAPIError) as captured:
        transport.request({"function": "GetSeries"})

    assert captured.value.code == 17
    assert secret not in str(captured.value)
    assert encoded not in str(captured.value)
    assert "<redacted>" in captured.value.description


def test_malformed_json_raises_response_error() -> None:
    session = FakeSession([FakeResponse(json_error=ValueError("not json"))])
    transport = RestTransport(TokenAuth.create(TOKEN), session=session, max_retries=0)

    with pytest.raises(BCCHResponseError, match="valid JSON"):
        transport.request({"function": "GetSeries"})


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"Codigo": 0},
        {"Codigo": "not-numeric", "Descripcion": "bad"},
    ],
)
def test_unexpected_api_envelope_raises_response_error(payload: object) -> None:
    session = FakeSession([FakeResponse(payload)])
    transport = RestTransport(TokenAuth.create(TOKEN), session=session, max_retries=0)

    with pytest.raises(BCCHResponseError):
        transport.request({"function": "GetSeries"})


def test_timeout_is_retried_then_raised_without_secret() -> None:
    session = FakeSession([requests.Timeout(TOKEN), requests.Timeout(TOKEN)])
    sleeps: list[float] = []
    transport = RestTransport(
        TokenAuth.create(TOKEN),
        session=session,
        max_retries=1,
        backoff_factor=0.1,
        sleep=sleeps.append,
    )

    with pytest.raises(BCCHTimeoutError) as captured:
        transport.request({"function": "GetSeries"})

    assert len(session.calls) == 2
    assert sleeps == [0.1]
    assert TOKEN not in str(captured.value)


def test_connection_error_is_retried_then_raised_without_secret() -> None:
    session = FakeSession(
        [requests.ConnectionError(TOKEN), requests.ConnectionError(TOKEN)]
    )
    transport = RestTransport(
        TokenAuth.create(TOKEN),
        session=session,
        max_retries=1,
        backoff_factor=0,
    )

    with pytest.raises(BCCHConnectionError) as captured:
        transport.request({"function": "GetSeries"})

    assert len(session.calls) == 2
    assert TOKEN not in str(captured.value)


def test_retryable_http_failure_can_recover() -> None:
    session = FakeSession(
        [
            FakeResponse(status_code=503),
            FakeResponse({"Codigo": 0, "Descripcion": "Success"}),
        ]
    )
    transport = RestTransport(
        TokenAuth.create(TOKEN),
        session=session,
        max_retries=1,
        backoff_factor=0,
    )

    result = transport.request({"function": "SearchSeries"})

    assert result["Codigo"] == 0
    assert len(session.calls) == 2


def test_non_retryable_http_failure_is_not_retried() -> None:
    session = FakeSession([FakeResponse(status_code=400)])
    transport = RestTransport(TokenAuth.create(TOKEN), session=session, max_retries=3)

    with pytest.raises(BCCHHTTPError) as captured:
        transport.request({"function": "GetSeries"})

    assert captured.value.status_code == 400
    assert len(session.calls) == 1
    assert TOKEN not in str(captured.value)


@pytest.mark.parametrize("status", [401, 403])
def test_http_authentication_failures_are_not_retried(status: int) -> None:
    session = FakeSession([FakeResponse(status_code=status)])
    transport = RestTransport(TokenAuth.create(TOKEN), session=session, max_retries=3)

    with pytest.raises(BCCHAuthenticationError):
        transport.request({"function": "GetSeries"})

    assert len(session.calls) == 1


def test_http_429_retries_then_raises_rate_limit_error() -> None:
    session = FakeSession(
        [
            FakeResponse(status_code=429, headers={"Retry-After": "0"}),
            FakeResponse(status_code=429),
        ]
    )
    transport = RestTransport(
        TokenAuth.create(TOKEN),
        session=session,
        max_retries=1,
        backoff_factor=0,
    )

    with pytest.raises(BCCHRateLimitError):
        transport.request({"function": "GetSeries"})

    assert len(session.calls) == 2
