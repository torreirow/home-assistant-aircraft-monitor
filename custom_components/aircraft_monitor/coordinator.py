"""DataUpdateCoordinator wiring the API client and pure processing logic."""

from __future__ import annotations

import logging
import socket
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import AdsbApiError, AdsbLolClient
from .const import DOMAIN, EVENT_AIRCRAFT_APPROACHING
from .processing import (
    ApproachTracker,
    EvaluatedAircraft,
    MonitorConfig,
    MonitorSummary,
    build_summary,
    evaluate_all,
)

_LOGGER = logging.getLogger(__name__)


class AircraftMonitorCoordinator(DataUpdateCoordinator[MonitorSummary]):
    """Polls ADSB.lol for one location and fires approach events."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry_id: str,
        name: str,
        config: MonitorConfig,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{name}",
            update_interval=timedelta(seconds=config.poll_interval_s),
        )
        self.entry_id = entry_id
        self.location_name = name
        self.config = config
        # Force IPv4: api.adsb.lol advertises AAAA records that are blackholed
        # from some networks, and aiohttp's happy-eyeballs would otherwise hang
        # on IPv6 until the request times out.
        self._client = AdsbLolClient(
            async_get_clientsession(hass, family=socket.AF_INET)
        )
        self._tracker = ApproachTracker(
            alert_distance_m=config.alert_distance_m,
            poll_interval_s=config.poll_interval_s,
        )

    async def _async_update_data(self) -> MonitorSummary:
        """Fetch, evaluate, fire events and return the summary."""
        try:
            aircraft = await self._client.async_get_aircraft(
                self.config.latitude,
                self.config.longitude,
                self.config.radius_km,
            )
        except AdsbApiError as err:
            raise UpdateFailed(str(err)) from err

        evaluated = evaluate_all(aircraft, self.config)

        now = dt_util.utcnow().timestamp()
        for event in self._tracker.update(evaluated, now):
            self._fire_event(event)

        return build_summary(evaluated)

    def _fire_event(self, evaluated: EvaluatedAircraft) -> None:
        """Fire the custom approaching event for one aircraft."""
        aircraft = evaluated.aircraft
        approach = evaluated.approach
        eta = approach.time_to_closest_approach_s
        self.hass.bus.async_fire(
            EVENT_AIRCRAFT_APPROACHING,
            {
                "entry_id": self.entry_id,
                "location": self.location_name,
                "icao": aircraft.hex,
                "callsign": aircraft.callsign,
                "latitude": aircraft.latitude,
                "longitude": aircraft.longitude,
                "altitude_ft": aircraft.altitude_ft,
                "speed_knots": aircraft.speed_knots,
                "track": aircraft.track,
                "current_distance_m": round(approach.current_distance_m),
                "closest_distance_m": round(approach.closest_distance_m),
                "eta_seconds": round(eta) if eta is not None else None,
            },
        )
        _LOGGER.debug(
            "Fired %s for %s (%s)",
            EVENT_AIRCRAFT_APPROACHING,
            aircraft.hex,
            aircraft.callsign,
        )
