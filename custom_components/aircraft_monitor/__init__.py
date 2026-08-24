"""The Aircraft Monitor integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ALERT_DISTANCE_M,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_MAX_ALTITUDE_FT,
    CONF_MIN_ALTITUDE_FT,
    CONF_MIN_SPEED_KTS,
    CONF_NAME,
    CONF_POLL_INTERVAL_S,
    CONF_PREDICTION_TIME_S,
    CONF_RADIUS_KM,
    DEFAULT_ALERT_DISTANCE_M,
    DEFAULT_MAX_ALTITUDE_FT,
    DEFAULT_MIN_ALTITUDE_FT,
    DEFAULT_MIN_SPEED_KTS,
    DEFAULT_NAME,
    DEFAULT_POLL_INTERVAL_S,
    DEFAULT_PREDICTION_TIME_S,
    DEFAULT_RADIUS_KM,
)
from .coordinator import AircraftMonitorCoordinator
from .processing import MonitorConfig

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]

type AircraftMonitorConfigEntry = ConfigEntry[AircraftMonitorCoordinator]


def resolve_config(entry: ConfigEntry) -> MonitorConfig:
    """Build a MonitorConfig from entry data (identity) and options (tunables)."""
    data = entry.data
    options = entry.options
    return MonitorConfig(
        latitude=float(data[CONF_LATITUDE]),
        longitude=float(data[CONF_LONGITUDE]),
        radius_km=float(options.get(CONF_RADIUS_KM, DEFAULT_RADIUS_KM)),
        alert_distance_m=float(
            options.get(CONF_ALERT_DISTANCE_M, DEFAULT_ALERT_DISTANCE_M)
        ),
        prediction_time_s=float(
            options.get(CONF_PREDICTION_TIME_S, DEFAULT_PREDICTION_TIME_S)
        ),
        poll_interval_s=float(
            options.get(CONF_POLL_INTERVAL_S, DEFAULT_POLL_INTERVAL_S)
        ),
        min_altitude_ft=float(
            options.get(CONF_MIN_ALTITUDE_FT, DEFAULT_MIN_ALTITUDE_FT)
        ),
        max_altitude_ft=float(
            options.get(CONF_MAX_ALTITUDE_FT, DEFAULT_MAX_ALTITUDE_FT)
        ),
        min_speed_kts=float(options.get(CONF_MIN_SPEED_KTS, DEFAULT_MIN_SPEED_KTS)),
    )


async def async_setup_entry(
    hass: HomeAssistant, entry: AircraftMonitorConfigEntry
) -> bool:
    """Set up Aircraft Monitor from a config entry."""
    coordinator = AircraftMonitorCoordinator(
        hass,
        entry_id=entry.entry_id,
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        config=resolve_config(entry),
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: AircraftMonitorConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_entry(
    hass: HomeAssistant, entry: AircraftMonitorConfigEntry
) -> None:
    """Reload the entry when its options change."""
    await hass.config_entries.async_reload(entry.entry_id)
