"""Config and options flow for Aircraft Monitor."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

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
    DEFAULT_LATITUDE,
    DEFAULT_LONGITUDE,
    DEFAULT_MAX_ALTITUDE_FT,
    DEFAULT_MIN_ALTITUDE_FT,
    DEFAULT_MIN_SPEED_KTS,
    DEFAULT_NAME,
    DEFAULT_POLL_INTERVAL_S,
    DEFAULT_PREDICTION_TIME_S,
    DEFAULT_RADIUS_KM,
    DOMAIN,
    MIN_POLL_INTERVAL_S,
)


def validate_identity(data: dict[str, Any]) -> dict[str, str]:
    """Validate latitude/longitude. Returns a mapping of field -> error key."""
    errors: dict[str, str] = {}
    if not -90 <= float(data[CONF_LATITUDE]) <= 90:
        errors[CONF_LATITUDE] = "invalid_latitude"
    if not -180 <= float(data[CONF_LONGITUDE]) <= 180:
        errors[CONF_LONGITUDE] = "invalid_longitude"
    return errors


def validate_options(data: dict[str, Any]) -> dict[str, str]:
    """Validate the tunable options. Returns field -> error key mapping."""
    errors: dict[str, str] = {}
    if float(data[CONF_RADIUS_KM]) <= 0:
        errors[CONF_RADIUS_KM] = "invalid_radius"
    if float(data[CONF_ALERT_DISTANCE_M]) <= 0:
        errors[CONF_ALERT_DISTANCE_M] = "invalid_alert_distance"
    if float(data[CONF_PREDICTION_TIME_S]) <= 0:
        errors[CONF_PREDICTION_TIME_S] = "invalid_prediction_time"
    if float(data[CONF_POLL_INTERVAL_S]) < MIN_POLL_INTERVAL_S:
        errors[CONF_POLL_INTERVAL_S] = "invalid_poll_interval"
    if float(data[CONF_MIN_ALTITUDE_FT]) > float(data[CONF_MAX_ALTITUDE_FT]):
        errors[CONF_MIN_ALTITUDE_FT] = "invalid_altitude_range"
    if float(data[CONF_MIN_SPEED_KTS]) < 0:
        errors[CONF_MIN_SPEED_KTS] = "invalid_min_speed"
    return errors


def _identity_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME, DEFAULT_NAME)
            ): str,
            vol.Required(
                CONF_LATITUDE, default=defaults.get(CONF_LATITUDE, DEFAULT_LATITUDE)
            ): vol.Coerce(float),
            vol.Required(
                CONF_LONGITUDE,
                default=defaults.get(CONF_LONGITUDE, DEFAULT_LONGITUDE),
            ): vol.Coerce(float),
        }
    )


def _options_schema(defaults: dict[str, Any]) -> vol.Schema:
    def _d(key: str, fallback: Any) -> Any:
        return defaults.get(key, fallback)

    return vol.Schema(
        {
            vol.Required(
                CONF_RADIUS_KM, default=_d(CONF_RADIUS_KM, DEFAULT_RADIUS_KM)
            ): vol.Coerce(float),
            vol.Required(
                CONF_ALERT_DISTANCE_M,
                default=_d(CONF_ALERT_DISTANCE_M, DEFAULT_ALERT_DISTANCE_M),
            ): vol.Coerce(float),
            vol.Required(
                CONF_PREDICTION_TIME_S,
                default=_d(CONF_PREDICTION_TIME_S, DEFAULT_PREDICTION_TIME_S),
            ): vol.Coerce(float),
            vol.Required(
                CONF_POLL_INTERVAL_S,
                default=_d(CONF_POLL_INTERVAL_S, DEFAULT_POLL_INTERVAL_S),
            ): vol.Coerce(float),
            vol.Required(
                CONF_MIN_ALTITUDE_FT,
                default=_d(CONF_MIN_ALTITUDE_FT, DEFAULT_MIN_ALTITUDE_FT),
            ): vol.Coerce(float),
            vol.Required(
                CONF_MAX_ALTITUDE_FT,
                default=_d(CONF_MAX_ALTITUDE_FT, DEFAULT_MAX_ALTITUDE_FT),
            ): vol.Coerce(float),
            vol.Required(
                CONF_MIN_SPEED_KTS,
                default=_d(CONF_MIN_SPEED_KTS, DEFAULT_MIN_SPEED_KTS),
            ): vol.Coerce(float),
        }
    )


class AircraftMonitorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial config flow (location identity)."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the identity step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_identity(user_input)
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_identity_schema(user_input or {}),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> AircraftMonitorOptionsFlow:
        """Return the options flow handler."""
        return AircraftMonitorOptionsFlow()


class AircraftMonitorOptionsFlow(OptionsFlow):
    """Handle the options flow (tunables)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the tunable options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = validate_options(user_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        defaults = user_input if user_input is not None else dict(self.config_entry.options)
        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(defaults),
            errors=errors,
        )
