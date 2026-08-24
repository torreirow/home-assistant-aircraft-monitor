"""Shared entity base for Aircraft Monitor."""

from __future__ import annotations

from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AircraftMonitorCoordinator


class AircraftMonitorEntity(CoordinatorEntity[AircraftMonitorCoordinator]):
    """Base entity binding to one location's coordinator/device."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: AircraftMonitorCoordinator, key: str
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.entry_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.entry_id)},
            name=coordinator.location_name,
            manufacturer="ADSB.lol",
            model="Aircraft Monitor",
        )
