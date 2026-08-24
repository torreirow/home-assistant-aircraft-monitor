"""Async client for the ADSB.lol v2 API.

Kept deliberately thin and injectable so it can be unit-tested with a mock
``aiohttp`` session and without network access.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import aiohttp

from .const import (
    API_BASE_URL,
    DEFAULT_API_TIMEOUT,
    KM_PER_NAUTICAL_MILE,
)

_LOGGER = logging.getLogger(__name__)


class AdsbApiError(Exception):
    """Raised for any recoverable ADSB.lol API failure."""


@dataclass(frozen=True)
class Aircraft:
    """A normalised aircraft record.

    Fields that are missing/invalid in the source are represented as ``None``
    (except altitude, where the string ``"ground"`` is normalised to 0).
    """

    hex: str
    callsign: str | None
    latitude: float | None
    longitude: float | None
    altitude_ft: float | None
    speed_knots: float | None
    track: float | None
    squawk: str | None
    category: str | None
    registration: str | None
    aircraft_type: str | None
    seen_pos_s: float | None

    @property
    def has_position(self) -> bool:
        """Whether this record carries a usable lat/lon position."""
        return self.latitude is not None and self.longitude is not None


def _to_float(value: object) -> float | None:
    """Coerce a value to float, returning ``None`` on missing/invalid input."""
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _to_str(value: object) -> str | None:
    """Coerce to a stripped string, returning ``None`` when empty/missing."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_altitude(value: object) -> float | None:
    """Parse ``alt_baro``, mapping the string ``"ground"`` to 0."""
    if isinstance(value, str) and value.strip().lower() == "ground":
        return 0.0
    return _to_float(value)


def parse_aircraft(raw: dict) -> Aircraft | None:
    """Normalise a single raw aircraft dict into an :class:`Aircraft`.

    Returns ``None`` when the record has no usable ``hex`` identifier.
    """
    hex_id = _to_str(raw.get("hex"))
    if not hex_id:
        return None
    return Aircraft(
        hex=hex_id.lower(),
        callsign=_to_str(raw.get("flight")),
        latitude=_to_float(raw.get("lat")),
        longitude=_to_float(raw.get("lon")),
        altitude_ft=_parse_altitude(raw.get("alt_baro")),
        speed_knots=_to_float(raw.get("gs")),
        track=_to_float(raw.get("track")),
        squawk=_to_str(raw.get("squawk")),
        category=_to_str(raw.get("category")),
        registration=_to_str(raw.get("r")),
        aircraft_type=_to_str(raw.get("t")),
        seen_pos_s=_to_float(raw.get("seen_pos")),
    )


def parse_response(payload: object) -> list[Aircraft]:
    """Turn a raw API payload into a list of normalised aircraft.

    Malformed individual records are skipped rather than raising.
    """
    if not isinstance(payload, dict):
        raise AdsbApiError("Unexpected response payload (not a JSON object)")
    raw_list = payload.get("ac")
    if raw_list is None:
        return []
    if not isinstance(raw_list, list):
        raise AdsbApiError("Unexpected 'ac' field (not a list)")
    aircraft: list[Aircraft] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        parsed = parse_aircraft(item)
        if parsed is not None:
            aircraft.append(parsed)
    return aircraft


class AdsbLolClient:
    """Minimal async client for ADSB.lol."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        *,
        timeout: float = DEFAULT_API_TIMEOUT,
    ) -> None:
        self._session = session
        self._timeout = timeout

    @staticmethod
    def build_url(latitude: float, longitude: float, radius_km: float) -> str:
        """Build the query URL; radius is converted from km to nautical miles."""
        radius_nm = radius_km / KM_PER_NAUTICAL_MILE
        return f"{API_BASE_URL}/lat/{latitude}/lon/{longitude}/dist/{radius_nm:.3f}"

    async def async_get_aircraft(
        self, latitude: float, longitude: float, radius_km: float
    ) -> list[Aircraft]:
        """Fetch and normalise aircraft around a location.

        Raises :class:`AdsbApiError` on any connection, timeout, HTTP or JSON
        error so the coordinator can translate it into ``UpdateFailed``.
        """
        url = self.build_url(latitude, longitude, radius_km)
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.get(
                    url, headers={"Accept": "application/json"}
                ) as response:
                    if response.status != 200:
                        raise AdsbApiError(
                            f"ADSB.lol returned HTTP {response.status}"
                        )
                    payload = await response.json(content_type=None)
        except AdsbApiError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise AdsbApiError(f"ADSB.lol request failed: {err}") from err
        except ValueError as err:  # invalid JSON
            raise AdsbApiError(f"ADSB.lol returned invalid JSON: {err}") from err

        aircraft = parse_response(payload)
        _LOGGER.debug("Fetched %d aircraft from %s", len(aircraft), url)
        return aircraft
