"""Tests for the pure geographic closest-approach maths."""

from __future__ import annotations

import math

import pytest

from aircraft_monitor.geo import (
    haversine_distance_m,
    predict_closest_approach,
)

# A convenient target near the default location.
TARGET_LAT = 52.2946
TARGET_LON = 5.5989


def _offset(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    """Return a lat/lon offset by the given metres north/east of (lat, lon)."""
    earth = 6_371_000.0
    dlat = math.degrees(north_m / earth)
    dlon = math.degrees(east_m / (earth * math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


def test_heading_toward_target_gives_near_zero_closest() -> None:
    """Aircraft flying straight at the target → closest ≈ 0."""
    # Place aircraft 5 km due south, flying north (track 0°) toward the target.
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=-5000, east_m=0)
    result = predict_closest_approach(
        ac_lat, ac_lon, speed_knots=250, track_degrees=0,
        target_lat=TARGET_LAT, target_lon=TARGET_LON, prediction_seconds=180,
    )
    assert result.is_approaching is True
    assert result.closest_distance_m < 50  # essentially over the target
    assert result.time_to_closest_approach_s is not None


def test_heading_away_gives_current_distance() -> None:
    """Aircraft flying away → closest ≈ current distance, not approaching."""
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=-5000, east_m=0)
    # Flying south (track 180°), i.e. away from the target.
    result = predict_closest_approach(
        ac_lat, ac_lon, speed_knots=250, track_degrees=180,
        target_lat=TARGET_LAT, target_lon=TARGET_LON, prediction_seconds=180,
    )
    assert result.is_approaching is False
    assert result.time_to_closest_approach_s is None
    assert result.closest_distance_m == pytest.approx(result.current_distance_m, rel=1e-6)


def test_parallel_gives_perpendicular_distance() -> None:
    """Aircraft passing parallel → closest ≈ perpendicular offset."""
    # 2 km north of the target, flying due east (track 90°). The perpendicular
    # foot is directly above the target and well within the window.
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=2000, east_m=-3000)
    result = predict_closest_approach(
        ac_lat, ac_lon, speed_knots=300, track_degrees=90,
        target_lat=TARGET_LAT, target_lon=TARGET_LON, prediction_seconds=180,
    )
    assert result.is_approaching is True
    assert result.closest_distance_m == pytest.approx(2000, abs=50)


def test_directly_over_target() -> None:
    """Aircraft heading straight over the target passes within a few metres."""
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=0, east_m=-4000)
    result = predict_closest_approach(
        ac_lat, ac_lon, speed_knots=280, track_degrees=90,
        target_lat=TARGET_LAT, target_lon=TARGET_LON, prediction_seconds=180,
    )
    assert result.closest_distance_m < 30


def test_track_wraparound_359_to_0() -> None:
    """A track near 359° must not raise or misbehave vs. 0°/1°."""
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=-5000, east_m=0)
    r359 = predict_closest_approach(
        ac_lat, ac_lon, 250, 359, TARGET_LAT, TARGET_LON, 180
    )
    r1 = predict_closest_approach(
        ac_lat, ac_lon, 250, 1, TARGET_LAT, TARGET_LON, 180
    )
    # 359° and 1° are symmetric about north → same closest distance.
    assert r359.closest_distance_m == pytest.approx(r1.closest_distance_m, abs=1)
    assert r359.is_approaching is True


def test_very_low_speed_does_not_crash() -> None:
    """Near-zero speed yields a finite result, treated as current distance."""
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=-1000, east_m=0)
    result = predict_closest_approach(
        ac_lat, ac_lon, speed_knots=0.0001, track_degrees=0,
        target_lat=TARGET_LAT, target_lon=TARGET_LON, prediction_seconds=180,
    )
    assert math.isfinite(result.closest_distance_m)


def test_missing_track() -> None:
    """Missing track → no prediction, current distance returned."""
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=-3000, east_m=0)
    result = predict_closest_approach(
        ac_lat, ac_lon, speed_knots=250, track_degrees=None,
        target_lat=TARGET_LAT, target_lon=TARGET_LON, prediction_seconds=180,
    )
    assert result.is_approaching is False
    assert result.time_to_closest_approach_s is None
    assert result.closest_distance_m == pytest.approx(result.current_distance_m)


def test_missing_speed() -> None:
    """Missing speed → no prediction, current distance returned."""
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=-3000, east_m=0)
    result = predict_closest_approach(
        ac_lat, ac_lon, speed_knots=None, track_degrees=0,
        target_lat=TARGET_LAT, target_lon=TARGET_LON, prediction_seconds=180,
    )
    assert result.is_approaching is False
    assert result.time_to_closest_approach_s is None


def test_outside_prediction_window() -> None:
    """Aircraft too far/slow to reach the target within the window.

    Flying toward the target but only for a short window → the closest distance
    within the window is bounded away from zero (it never gets there in time).
    """
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=-50000, east_m=0)
    result = predict_closest_approach(
        ac_lat, ac_lon, speed_knots=200, track_degrees=0,
        target_lat=TARGET_LAT, target_lon=TARGET_LON, prediction_seconds=30,
    )
    assert result.is_approaching is True
    # 200 kt ≈ 103 m/s * 30 s ≈ 3.1 km travelled; still ~47 km away.
    assert result.closest_distance_m > 40000


def test_within_alert_distance() -> None:
    """An aircraft heading in passes within 250 m at some point in the window."""
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=-6000, east_m=100)
    result = predict_closest_approach(
        ac_lat, ac_lon, speed_knots=250, track_degrees=0,
        target_lat=TARGET_LAT, target_lon=TARGET_LON, prediction_seconds=180,
    )
    assert result.closest_distance_m <= 250


def test_haversine_sanity() -> None:
    """Haversine distance matches a known small offset."""
    lat2, lon2 = _offset(TARGET_LAT, TARGET_LON, north_m=1000, east_m=0)
    assert haversine_distance_m(TARGET_LAT, TARGET_LON, lat2, lon2) == pytest.approx(
        1000, abs=1
    )
