"""Pure processing logic: filtering, evaluation and duplicate prevention.

No Home Assistant imports live here so the filtering, approach evaluation and
the duplicate-prevention state machine can be unit-tested directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .api import Aircraft
from .const import (
    EVENT_COOLDOWN_S,
    HYSTERESIS_FACTOR,
    MAX_POSITION_AGE_S,
    STALE_AFTER_MISSED_CYCLES,
)
from .geo import ClosestApproach, predict_closest_approach


@dataclass(frozen=True)
class MonitorConfig:
    """Resolved runtime configuration for a single monitored location."""

    latitude: float
    longitude: float
    radius_km: float
    alert_distance_m: float
    prediction_time_s: float
    poll_interval_s: float
    min_altitude_ft: float
    max_altitude_ft: float
    min_speed_kts: float


@dataclass(frozen=True)
class EvaluatedAircraft:
    """An aircraft enriched with its closest-approach evaluation."""

    aircraft: Aircraft
    approach: ClosestApproach
    is_relevant: bool
    is_alerting: bool

    @property
    def hex(self) -> str:
        return self.aircraft.hex


def _passes_filters(aircraft: Aircraft, config: MonitorConfig) -> bool:
    """Local altitude/speed filtering. Missing values fail the filter."""
    if not aircraft.has_position:
        return False
    if aircraft.speed_knots is None or aircraft.speed_knots < config.min_speed_kts:
        return False
    if aircraft.altitude_ft is None:
        return False
    if not (config.min_altitude_ft <= aircraft.altitude_ft <= config.max_altitude_ft):
        return False
    return True


def evaluate_aircraft(aircraft: Aircraft, config: MonitorConfig) -> EvaluatedAircraft:
    """Evaluate a single aircraft against the configured location."""
    approach = predict_closest_approach(
        aircraft_lat=aircraft.latitude or 0.0,
        aircraft_lon=aircraft.longitude or 0.0,
        speed_knots=aircraft.speed_knots,
        track_degrees=aircraft.track,
        target_lat=config.latitude,
        target_lon=config.longitude,
        prediction_seconds=config.prediction_time_s,
    )

    is_relevant = _passes_filters(aircraft, config)

    # A stale position must not drive an alert, even if it still passes filters.
    position_fresh = (
        aircraft.seen_pos_s is None or aircraft.seen_pos_s <= MAX_POSITION_AGE_S
    )

    is_alerting = (
        is_relevant
        and position_fresh
        and approach.is_approaching
        and approach.time_to_closest_approach_s is not None
        and approach.time_to_closest_approach_s <= config.prediction_time_s
        and approach.closest_distance_m <= config.alert_distance_m
    )

    return EvaluatedAircraft(
        aircraft=aircraft,
        approach=approach,
        is_relevant=is_relevant,
        is_alerting=is_alerting,
    )


def evaluate_all(
    aircraft_list: list[Aircraft], config: MonitorConfig
) -> list[EvaluatedAircraft]:
    """Evaluate every aircraft; keep only those passing the local filters."""
    evaluated = [evaluate_aircraft(a, config) for a in aircraft_list]
    return [e for e in evaluated if e.is_relevant]


@dataclass
class MonitorSummary:
    """A processed poll result ready for entities to consume."""

    aircraft: list[EvaluatedAircraft]
    count: int
    nearest: EvaluatedAircraft | None
    most_approaching: EvaluatedAircraft | None


def build_summary(evaluated: list[EvaluatedAircraft]) -> MonitorSummary:
    """Summarise evaluated aircraft: count, nearest, most-approaching."""
    nearest = None
    if evaluated:
        nearest = min(evaluated, key=lambda e: e.approach.current_distance_m)

    alerting = [e for e in evaluated if e.is_alerting]
    most_approaching = None
    if alerting:
        most_approaching = min(alerting, key=lambda e: e.approach.closest_distance_m)

    return MonitorSummary(
        aircraft=evaluated,
        count=len(evaluated),
        nearest=nearest,
        most_approaching=most_approaching,
    )


@dataclass
class _TrackState:
    """Per-aircraft duplicate-prevention state."""

    armed: bool = False
    last_seen: float = 0.0
    last_event_ts: float | None = None


@dataclass
class ApproachTracker:
    """Edge-triggered duplicate-prevention state machine, keyed by ``hex``.

    An event fires on the rising edge NOT-APPROACHING -> APPROACHING. The same
    aircraft stays "armed" and silent while it keeps approaching. It re-arms
    only once its predicted closest approach grows beyond
    ``alert_distance * hysteresis`` (or it disappears), and a cooldown prevents
    immediate re-firing after a brief drop below the threshold.
    """

    alert_distance_m: float
    poll_interval_s: float
    hysteresis_factor: float = HYSTERESIS_FACTOR
    cooldown_s: float = EVENT_COOLDOWN_S
    stale_cycles: int = STALE_AFTER_MISSED_CYCLES
    _state: dict[str, _TrackState] = field(default_factory=dict)

    def update(
        self, evaluated: list[EvaluatedAircraft], now: float
    ) -> list[EvaluatedAircraft]:
        """Advance the state machine one poll; return aircraft that fire events."""
        events: list[EvaluatedAircraft] = []
        rearm_distance = self.alert_distance_m * self.hysteresis_factor

        for ev in evaluated:
            state = self._state.get(ev.hex)
            if state is None:
                state = _TrackState()
                self._state[ev.hex] = state
            state.last_seen = now

            if ev.is_alerting:
                if not state.armed:
                    cooldown_ok = (
                        state.last_event_ts is None
                        or (now - state.last_event_ts) >= self.cooldown_s
                    )
                    state.armed = True
                    if cooldown_ok:
                        state.last_event_ts = now
                        events.append(ev)
            elif state.armed and ev.approach.closest_distance_m > rearm_distance:
                # Left the zone with hysteresis margin → allow a future event.
                state.armed = False

        self._purge_stale(now)
        return events

    def _purge_stale(self, now: float) -> None:
        """Drop aircraft not seen for several poll cycles.

        A purged aircraft that reappears is treated as new, so a later passage
        fires again.
        """
        timeout = self.poll_interval_s * self.stale_cycles
        stale = [
            hexid
            for hexid, state in self._state.items()
            if now - state.last_seen > timeout
        ]
        for hexid in stale:
            del self._state[hexid]
