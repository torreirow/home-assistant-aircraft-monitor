"""Constants for the Aircraft Monitor integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "aircraft_monitor"

# Custom event fired when a new aircraft enters the alert zone.
EVENT_AIRCRAFT_APPROACHING: Final = f"{DOMAIN}.aircraft_approaching"

# ADSB.lol v2 API.
API_BASE_URL: Final = "https://api.adsb.lol/v2"
KM_PER_NAUTICAL_MILE: Final = 1.852
KNOTS_TO_MS: Final = 0.514444
FEET_TO_METERS: Final = 0.3048
DEFAULT_API_TIMEOUT: Final = 15  # seconds

# --- Configuration keys ---------------------------------------------------
CONF_NAME: Final = "name"
CONF_LATITUDE: Final = "latitude"
CONF_LONGITUDE: Final = "longitude"
CONF_RADIUS_KM: Final = "radius_km"
CONF_ALERT_DISTANCE_M: Final = "alert_distance_m"
CONF_PREDICTION_TIME_S: Final = "prediction_time_s"
CONF_POLL_INTERVAL_S: Final = "poll_interval_s"
CONF_MIN_ALTITUDE_FT: Final = "min_altitude_ft"
CONF_MAX_ALTITUDE_FT: Final = "max_altitude_ft"
CONF_MIN_SPEED_KTS: Final = "min_speed_kts"

# --- Defaults (never hardcoded in logic; only proposed in the UI) ---------
DEFAULT_NAME: Final = "Aircraft Monitor"
DEFAULT_LATITUDE: Final = 52.2946
DEFAULT_LONGITUDE: Final = 5.5989
DEFAULT_RADIUS_KM: Final = 20.0
DEFAULT_ALERT_DISTANCE_M: Final = 250.0
DEFAULT_PREDICTION_TIME_S: Final = 180
DEFAULT_POLL_INTERVAL_S: Final = 30
DEFAULT_MIN_ALTITUDE_FT: Final = 0
DEFAULT_MAX_ALTITUDE_FT: Final = 15000
DEFAULT_MIN_SPEED_KTS: Final = 25.0

# --- Validation bounds ----------------------------------------------------
MIN_POLL_INTERVAL_S: Final = 5

# --- Duplicate-prevention / freshness tuning ------------------------------
# Re-arm an aircraft only once its predicted closest approach exceeds
# alert_distance * HYSTERESIS_FACTOR, to avoid flapping around the threshold.
HYSTERESIS_FACTOR: Final = 1.3
# Minimum time before the same hex may fire again after it stopped approaching.
EVENT_COOLDOWN_S: Final = 60
# Drop an aircraft from internal state after this many missed poll cycles.
STALE_AFTER_MISSED_CYCLES: Final = 3
# Ignore positions older than this many seconds for approach prediction.
MAX_POSITION_AGE_S: Final = 15.0
