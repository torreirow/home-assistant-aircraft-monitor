"""Tests for filtering, approach evaluation and duplicate prevention.

These exercise the pure ``processing`` module (no Home Assistant required),
which is exactly the logic the coordinator drives.
"""

from __future__ import annotations

import math

from aircraft_monitor.api import Aircraft
from aircraft_monitor.geo import ClosestApproach
from aircraft_monitor.processing import (
    ApproachTracker,
    EvaluatedAircraft,
    MonitorConfig,
    build_summary,
    evaluate_aircraft,
    evaluate_all,
)

TARGET_LAT = 52.2946
TARGET_LON = 5.5989


def make_config(**over) -> MonitorConfig:
    base = dict(
        latitude=TARGET_LAT,
        longitude=TARGET_LON,
        radius_km=20.0,
        alert_distance_m=250.0,
        prediction_time_s=180.0,
        poll_interval_s=10.0,
        min_altitude_ft=0.0,
        max_altitude_ft=15000.0,
        min_speed_kts=25.0,
    )
    base.update(over)
    return MonitorConfig(**base)


def make_aircraft(**over) -> Aircraft:
    base = dict(
        hex="abc123",
        callsign="KLM123",
        latitude=TARGET_LAT,
        longitude=TARGET_LON,
        altitude_ft=4000.0,
        speed_knots=250.0,
        track=0.0,
        squawk="1000",
        category="A3",
        registration="PH-ABC",
        aircraft_type="B738",
        seen_pos_s=1.0,
    )
    base.update(over)
    return Aircraft(**base)


def _offset(lat: float, lon: float, north_m: float, east_m: float) -> tuple[float, float]:
    earth = 6_371_000.0
    dlat = math.degrees(north_m / earth)
    dlon = math.degrees(east_m / (earth * math.cos(math.radians(lat))))
    return lat + dlat, lon + dlon


def make_evaluated(hexid: str, *, alerting: bool, closest: float) -> EvaluatedAircraft:
    """Build an EvaluatedAircraft with a hand-made approach for tracker tests."""
    approach = ClosestApproach(
        current_distance_m=closest + 100,
        closest_distance_m=closest,
        time_to_closest_approach_s=30.0 if alerting else None,
        predicted_lat=TARGET_LAT,
        predicted_lon=TARGET_LON,
        is_approaching=alerting,
    )
    return EvaluatedAircraft(
        aircraft=make_aircraft(hex=hexid),
        approach=approach,
        is_relevant=True,
        is_alerting=alerting,
    )


# --- Filtering ------------------------------------------------------------


def test_filter_rejects_below_min_speed() -> None:
    config = make_config()
    slow = make_aircraft(speed_knots=20.0)
    assert evaluate_aircraft(slow, config).is_relevant is False


def test_filter_rejects_outside_altitude() -> None:
    config = make_config(max_altitude_ft=15000)
    high = make_aircraft(altitude_ft=30000.0)
    low_ok = make_aircraft(altitude_ft=5000.0)
    assert evaluate_aircraft(high, config).is_relevant is False
    assert evaluate_aircraft(low_ok, config).is_relevant is True


def test_filter_rejects_missing_position() -> None:
    config = make_config()
    assert evaluate_aircraft(make_aircraft(latitude=None), config).is_relevant is False


def test_evaluate_all_drops_irrelevant() -> None:
    config = make_config()
    relevant = make_aircraft(hex="aaa", altitude_ft=4000.0)
    irrelevant = make_aircraft(hex="bbb", speed_knots=5.0)
    out = evaluate_all([relevant, irrelevant], config)
    assert {e.hex for e in out} == {"aaa"}


# --- Approaching determination -------------------------------------------


def test_incoming_aircraft_is_alerting() -> None:
    config = make_config()
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=-6000, east_m=50)
    incoming = make_aircraft(latitude=ac_lat, longitude=ac_lon, track=0.0)
    ev = evaluate_aircraft(incoming, config)
    assert ev.is_alerting is True


def test_within_distance_but_departing_not_alerting() -> None:
    config = make_config()
    # 100 m north of target but flying north (away).
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=100, east_m=0)
    departing = make_aircraft(latitude=ac_lat, longitude=ac_lon, track=0.0)
    ev = evaluate_aircraft(departing, config)
    assert ev.is_alerting is False


def test_stale_position_not_alerting() -> None:
    config = make_config()
    ac_lat, ac_lon = _offset(TARGET_LAT, TARGET_LON, north_m=-6000, east_m=50)
    stale = make_aircraft(latitude=ac_lat, longitude=ac_lon, track=0.0, seen_pos_s=120.0)
    assert evaluate_aircraft(stale, config).is_alerting is False


def test_summary_counts_nearest_and_approaching() -> None:
    config = make_config()
    near_lat, near_lon = _offset(TARGET_LAT, TARGET_LON, north_m=-6000, east_m=50)
    far_lat, far_lon = _offset(TARGET_LAT, TARGET_LON, north_m=-15000, east_m=9000)
    incoming = make_aircraft(hex="aaa", latitude=near_lat, longitude=near_lon, track=0.0)
    passing = make_aircraft(hex="bbb", latitude=far_lat, longitude=far_lon, track=270.0)
    summary = build_summary(evaluate_all([incoming, passing], config))
    assert summary.count == 2
    assert summary.nearest is not None
    assert summary.most_approaching is not None
    assert summary.most_approaching.hex == "aaa"


# --- Duplicate prevention -------------------------------------------------


def test_first_approach_fires_single_event() -> None:
    tracker = ApproachTracker(alert_distance_m=250, poll_interval_s=10)
    ev = make_evaluated("aaa", alerting=True, closest=150)
    fired = tracker.update([ev], now=0.0)
    assert [e.hex for e in fired] == ["aaa"]


def test_sustained_approach_no_repeat() -> None:
    tracker = ApproachTracker(alert_distance_m=250, poll_interval_s=10)
    ev = make_evaluated("aaa", alerting=True, closest=150)
    assert tracker.update([ev], now=0.0)  # fires
    assert tracker.update([ev], now=10.0) == []  # silent
    assert tracker.update([ev], now=20.0) == []  # silent


def test_hysteresis_prevents_reflap() -> None:
    tracker = ApproachTracker(alert_distance_m=250, poll_interval_s=10)
    incoming = make_evaluated("aaa", alerting=True, closest=150)
    # Drops just above alert distance but within hysteresis band → stays armed.
    marginal = make_evaluated("aaa", alerting=False, closest=260)
    assert tracker.update([incoming], now=0.0)  # fires
    assert tracker.update([marginal], now=10.0) == []  # no de-arm
    assert tracker.update([incoming], now=20.0) == []  # still armed, no re-fire


def test_reapproach_after_leaving_zone_fires_again() -> None:
    tracker = ApproachTracker(alert_distance_m=250, poll_interval_s=10)
    ev = make_evaluated("aaa", alerting=True, closest=150)
    assert tracker.update([ev], now=0.0)  # first event
    # Aircraft disappears long enough to be purged (timeout = 10 * 3 = 30 s).
    assert tracker.update([], now=40.0) == []
    # Re-appears and approaches again → new event.
    fired = tracker.update([ev], now=100.0)
    assert [e.hex for e in fired] == ["aaa"]
