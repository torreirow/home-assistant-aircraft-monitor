"""Tests for the ADSB.lol API client and record normalisation (no network)."""

from __future__ import annotations

import asyncio

import aiohttp
import pytest

from aircraft_monitor.api import (
    AdsbApiError,
    AdsbLolClient,
    parse_aircraft,
    parse_response,
)


def test_build_url_converts_km_to_nm() -> None:
    url = AdsbLolClient.build_url(52.2946, 5.5989, 20)
    # 20 km / 1.852 ≈ 10.799 nm
    assert url == "https://api.adsb.lol/v2/lat/52.2946/lon/5.5989/dist/10.799"


def test_parse_aircraft_strips_and_coerces() -> None:
    raw = {
        "hex": "48667C",
        "flight": "PHAHJ   ",
        "lat": 52.37,
        "lon": 5.36,
        "alt_baro": 1100,
        "gs": 44.0,
        "track": 59.0,
        "squawk": "7000",
        "category": "A1",
        "r": "PH-AHJ",
        "t": "C172",
        "seen_pos": 0.4,
    }
    ac = parse_aircraft(raw)
    assert ac is not None
    assert ac.hex == "48667c"  # lowercased
    assert ac.callsign == "PHAHJ"  # stripped
    assert ac.altitude_ft == 1100
    assert ac.speed_knots == 44.0
    assert ac.aircraft_type == "C172"


def test_parse_aircraft_ground_altitude() -> None:
    ac = parse_aircraft({"hex": "abc123", "alt_baro": "ground", "lat": 1, "lon": 2})
    assert ac is not None
    assert ac.altitude_ft == 0.0


def test_parse_aircraft_missing_and_null_fields() -> None:
    ac = parse_aircraft(
        {"hex": "abc123", "flight": "   ", "gs": None, "track": None, "lat": None}
    )
    assert ac is not None
    assert ac.callsign is None  # whitespace-only → None
    assert ac.speed_knots is None
    assert ac.track is None
    assert ac.latitude is None
    assert ac.has_position is False


def test_parse_aircraft_without_hex_is_dropped() -> None:
    assert parse_aircraft({"flight": "NOHEX"}) is None


def test_parse_response_empty_and_missing_ac() -> None:
    assert parse_response({"ac": []}) == []
    assert parse_response({"now": 123}) == []  # no 'ac' key


def test_parse_response_skips_malformed_records() -> None:
    payload = {"ac": [{"hex": "aaa"}, "not-a-dict", {"no_hex": 1}, {"hex": "bbb"}]}
    result = parse_response(payload)
    assert [a.hex for a in result] == ["aaa", "bbb"]


def test_parse_response_rejects_non_object() -> None:
    with pytest.raises(AdsbApiError):
        parse_response(["not", "a", "dict"])


# --- Client HTTP behaviour with a fake session ----------------------------


class _FakeResponse:
    def __init__(self, status: int, payload: object, *, raise_json: bool = False) -> None:
        self.status = status
        self._payload = payload
        self._raise_json = raise_json

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def json(self, content_type: object = None) -> object:
        if self._raise_json:
            raise ValueError("invalid json")
        return self._payload


class _FakeSession:
    def __init__(self, response: object = None, *, exc: Exception | None = None) -> None:
        self._response = response
        self._exc = exc

    def get(self, url: str, headers: dict | None = None) -> object:
        if self._exc is not None:
            raise self._exc
        return self._response


async def test_client_returns_aircraft_on_success() -> None:
    session = _FakeSession(
        _FakeResponse(200, {"ac": [{"hex": "aaa", "lat": 1, "lon": 2, "gs": 100}]})
    )
    client = AdsbLolClient(session)  # type: ignore[arg-type]
    aircraft = await client.async_get_aircraft(52.0, 5.0, 20)
    assert len(aircraft) == 1
    assert aircraft[0].hex == "aaa"


async def test_client_empty_response() -> None:
    session = _FakeSession(_FakeResponse(200, {"ac": []}))
    client = AdsbLolClient(session)  # type: ignore[arg-type]
    assert await client.async_get_aircraft(52.0, 5.0, 20) == []


async def test_client_http_error_raises() -> None:
    session = _FakeSession(_FakeResponse(503, {}))
    client = AdsbLolClient(session)  # type: ignore[arg-type]
    with pytest.raises(AdsbApiError):
        await client.async_get_aircraft(52.0, 5.0, 20)


async def test_client_invalid_json_raises() -> None:
    session = _FakeSession(_FakeResponse(200, None, raise_json=True))
    client = AdsbLolClient(session)  # type: ignore[arg-type]
    with pytest.raises(AdsbApiError):
        await client.async_get_aircraft(52.0, 5.0, 20)


async def test_client_connection_error_raises() -> None:
    session = _FakeSession(exc=aiohttp.ClientError("boom"))
    client = AdsbLolClient(session)  # type: ignore[arg-type]
    with pytest.raises(AdsbApiError):
        await client.async_get_aircraft(52.0, 5.0, 20)


async def test_client_timeout_raises() -> None:
    session = _FakeSession(exc=asyncio.TimeoutError())
    client = AdsbLolClient(session)  # type: ignore[arg-type]
    with pytest.raises(AdsbApiError):
        await client.async_get_aircraft(52.0, 5.0, 20)
