"""Pure geographic helpers for aircraft approach prediction.

This module contains only pure functions (no Home Assistant imports) so the
maths can be unit-tested in isolation without a running Home Assistant.

The approach uses a local tangent-plane (equirectangular) projection centred on
the target location. Over the short distances involved (a few tens of km) this
is accurate enough, and it turns the closest-approach problem into simple 2-D
vector maths with a closed-form solution.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .const import KNOTS_TO_MS

EARTH_RADIUS_M = 6_371_000.0


@dataclass(frozen=True)
class ClosestApproach:
    """Result of a closest-approach prediction.

    Attributes:
        current_distance_m: Current distance from aircraft to target (m).
        closest_distance_m: Minimum distance reached within the prediction
            window (m).
        time_to_closest_approach_s: Seconds until the closest approach within
            the window, or ``None`` when it cannot be determined (e.g. missing
            track/speed).
        predicted_lat: Latitude of the aircraft at closest approach.
        predicted_lon: Longitude of the aircraft at closest approach.
        is_approaching: Whether the aircraft is actually moving toward the
            target (independent of the alert-distance threshold).
    """

    current_distance_m: float
    closest_distance_m: float
    time_to_closest_approach_s: float | None
    predicted_lat: float
    predicted_lon: float
    is_approaching: bool


def _local_xy(
    lat: float, lon: float, target_lat: float, target_lon: float
) -> tuple[float, float]:
    """Project ``(lat, lon)`` onto local ENU metres around the target origin.

    Returns ``(east, north)`` in metres relative to the target.
    """
    lat_rad = math.radians(target_lat)
    x = math.radians(lon - target_lon) * math.cos(lat_rad) * EARTH_RADIUS_M
    y = math.radians(lat - target_lat) * EARTH_RADIUS_M
    return x, y


def _latlon_from_xy(
    x: float, y: float, target_lat: float, target_lon: float
) -> tuple[float, float]:
    """Inverse of :func:`_local_xy` — ENU metres back to ``(lat, lon)``."""
    lat_rad = math.radians(target_lat)
    lat = target_lat + math.degrees(y / EARTH_RADIUS_M)
    lon = target_lon + math.degrees(x / (EARTH_RADIUS_M * math.cos(lat_rad)))
    return lat, lon


def haversine_distance_m(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Great-circle distance between two points in metres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))


def predict_closest_approach(
    aircraft_lat: float,
    aircraft_lon: float,
    speed_knots: float | None,
    track_degrees: float | None,
    target_lat: float,
    target_lon: float,
    prediction_seconds: float,
) -> ClosestApproach:
    """Predict the closest approach of an aircraft to a target location.

    The aircraft is assumed to travel in a straight line at constant ground
    speed on the given track for ``prediction_seconds``. The closest distance
    is the minimum over the window ``[0, prediction_seconds]`` (not the
    infinite line), so an aircraft whose perpendicular foot lies beyond the
    window yields the distance at the end of the window.

    ``track_degrees`` is measured clockwise from north, so the velocity is
    ``(east, north) = v * (sin(track), cos(track))``. Using sin/cos directly
    means a track near 359°/0° introduces no discontinuity.

    When ``speed_knots`` or ``track_degrees`` is missing (or speed is ~0), no
    motion can be predicted: the closest distance equals the current distance,
    the ETA is ``None`` and ``is_approaching`` is ``False``.
    """
    x0, y0 = _local_xy(aircraft_lat, aircraft_lon, target_lat, target_lon)
    current_distance = math.hypot(x0, y0)

    # No usable motion → cannot predict an approach.
    if speed_knots is None or track_degrees is None or speed_knots <= 0:
        return ClosestApproach(
            current_distance_m=current_distance,
            closest_distance_m=current_distance,
            time_to_closest_approach_s=None,
            predicted_lat=aircraft_lat,
            predicted_lon=aircraft_lon,
            is_approaching=False,
        )

    speed_ms = speed_knots * KNOTS_TO_MS
    track_rad = math.radians(track_degrees)
    vx = speed_ms * math.sin(track_rad)  # east component
    vy = speed_ms * math.cos(track_rad)  # north component

    v_dot_v = vx * vx + vy * vy
    if v_dot_v == 0:  # defensive; speed_ms > 0 already guards this
        return ClosestApproach(
            current_distance_m=current_distance,
            closest_distance_m=current_distance,
            time_to_closest_approach_s=None,
            predicted_lat=aircraft_lat,
            predicted_lon=aircraft_lon,
            is_approaching=False,
        )

    # Unclamped time of minimum distance to the origin.
    t_star = -(x0 * vx + y0 * vy) / v_dot_v
    # Aircraft is moving toward the target iff the unclamped minimum is in the
    # future (position and velocity point "against" each other).
    is_approaching = t_star > 0

    # Minimum distance is evaluated within the prediction window only.
    t_clamped = max(0.0, min(t_star, prediction_seconds))
    px = x0 + t_clamped * vx
    py = y0 + t_clamped * vy
    closest_distance = math.hypot(px, py)

    predicted_lat, predicted_lon = _latlon_from_xy(px, py, target_lat, target_lon)

    return ClosestApproach(
        current_distance_m=current_distance,
        closest_distance_m=closest_distance,
        time_to_closest_approach_s=t_clamped if is_approaching else None,
        predicted_lat=predicted_lat,
        predicted_lon=predicted_lon,
        is_approaching=is_approaching,
    )
