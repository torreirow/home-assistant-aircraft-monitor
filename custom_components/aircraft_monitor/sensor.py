"""Sensor platform for Aircraft Monitor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AircraftMonitorConfigEntry
from .entity import AircraftMonitorEntity
from .processing import EvaluatedAircraft


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AircraftMonitorConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            AircraftCountSensor(coordinator),
            NearestAircraftSensor(coordinator),
            ApproachingAircraftSensor(coordinator),
        ]
    )


def _aircraft_attributes(ev: EvaluatedAircraft) -> dict[str, Any]:
    """Common attribute set describing one aircraft."""
    a = ev.aircraft
    return {
        "callsign": a.callsign,
        "icao": a.hex,
        "latitude": a.latitude,
        "longitude": a.longitude,
        "altitude": a.altitude_ft,
        "speed": a.speed_knots,
        "track": a.track,
        "aircraft_type": a.aircraft_type,
    }


class AircraftCountSensor(AircraftMonitorEntity, SensorEntity):
    """Number of relevant aircraft within the search radius."""

    _attr_translation_key = "aircraft_count"
    _attr_name = "Aircraft count"
    _attr_icon = "mdi:airplane"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "aircraft_count")

    @property
    def native_value(self) -> int:
        return self.coordinator.data.count


class NearestAircraftSensor(AircraftMonitorEntity, SensorEntity):
    """Distance to the nearest relevant aircraft."""

    _attr_translation_key = "nearest_aircraft"
    _attr_name = "Nearest aircraft"
    _attr_icon = "mdi:airplane-marker"
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_device_class = "distance"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "nearest_aircraft")

    @property
    def native_value(self) -> float | None:
        nearest = self.coordinator.data.nearest
        if nearest is None:
            return None
        return round(nearest.approach.current_distance_m)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        nearest = self.coordinator.data.nearest
        if nearest is None:
            return {}
        return _aircraft_attributes(nearest)


class ApproachingAircraftSensor(AircraftMonitorEntity, SensorEntity):
    """The aircraft with the nearest predicted closest approach."""

    _attr_translation_key = "approaching_aircraft"
    _attr_name = "Approaching aircraft"
    _attr_icon = "mdi:airplane-alert"
    _attr_native_unit_of_measurement = UnitOfLength.METERS
    _attr_device_class = "distance"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "approaching_aircraft")

    @property
    def native_value(self) -> float | None:
        ev = self.coordinator.data.most_approaching
        if ev is None:
            return None
        return round(ev.approach.closest_distance_m)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ev = self.coordinator.data.most_approaching
        if ev is None:
            return {}
        attrs = _aircraft_attributes(ev)
        eta = ev.approach.time_to_closest_approach_s
        attrs["distance"] = round(ev.approach.closest_distance_m)
        attrs["eta"] = round(eta) if eta is not None else None
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:  # pragma: no cover - passthrough
        super()._handle_coordinator_update()
