"""Binary sensor platform for Aircraft Monitor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AircraftMonitorConfigEntry
from .entity import AircraftMonitorEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AircraftMonitorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    async_add_entities([AircraftApproachingBinarySensor(entry.runtime_data)])


class AircraftApproachingBinarySensor(AircraftMonitorEntity, BinarySensorEntity):
    """On while at least one aircraft is predicted to enter the alert zone."""

    _attr_translation_key = "aircraft_approaching"
    _attr_name = "Aircraft approaching"
    _attr_device_class = BinarySensorDeviceClass.MOTION
    _attr_icon = "mdi:airplane-alert"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "aircraft_approaching")

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.most_approaching is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ev = self.coordinator.data.most_approaching
        if ev is None:
            return {}
        a = ev.aircraft
        eta = ev.approach.time_to_closest_approach_s
        return {
            "callsign": a.callsign,
            "icao": a.hex,
            "closest_distance": round(ev.approach.closest_distance_m),
            "eta": round(eta) if eta is not None else None,
            "altitude": a.altitude_ft,
            "speed": a.speed_knots,
            "track": a.track,
        }
