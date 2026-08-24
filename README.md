# ✈️ Aircraft Monitor for Home Assistant

A Home Assistant custom integration that detects aircraft flying **toward a
location** and predicts whether they will pass within a configurable distance —
using the free, public [ADSB.lol](https://adsb.lol) API (no API key required).

Unlike a simple "is there a plane within X metres" check, this integration
computes a **predicted closest approach**: it uses each aircraft's position,
ground speed and track to work out the minimum distance it will reach to your
location within a prediction window, and only alerts when a plane is genuinely
heading your way.

- Predicts closest approach and time-to-closest-approach per aircraft
- Fires a de-duplicated `aircraft_monitor.aircraft_approaching` event
- Sensors + binary sensor, fully configurable through the UI
- Supports multiple locations (Home, Camping, Work, …) as separate entries

---

## Requirements

- Home Assistant 2024.12 or newer.
- Outbound internet access to `api.adsb.lol`.

> **Note on installation target.** This integration is a standard HA custom
> integration and works on any HA install. It is developed against Home
> Assistant running as the official **Docker container**
> (`ghcr.io/home-assistant/home-assistant`), *not* Home Assistant OS /
> Supervised. Because there is no Supervisor in that setup, it is **not** an
> add-on and is not installed via an add-on repository — it is a custom
> **integration**, installed via [HACS](https://hacs.xyz) or by copying the
> folder into your config directory.

---

## Installation

### Via HACS (recommended)

1. In Home Assistant, open **HACS**.
2. Top-right menu (⋮) → **Custom repositories**.
3. Add the repository URL
   `https://github.com/torreirow/home-assistant-aircraft-monitor`
   and choose category **Integration**.
4. Find **Aircraft Monitor** in HACS, click **Download**.
5. **Restart Home Assistant.**

Updates then appear in HACS whenever a new release is tagged.

### Manual installation

Copy the integration folder into your Home Assistant config directory so that
you end up with:

```
<config>/custom_components/aircraft_monitor/
```

For a Docker install this is the host path mounted as `/config`, e.g.
`/var/lib/homeassistant/custom_components/aircraft_monitor/`. Then restart
Home Assistant.

---

## Configuration

Everything is configured through the UI — no YAML.

**Settings → Devices & services → Add Integration → Aircraft Monitor.**

You first set the location identity:

| Field       | Default   | Notes                          |
|-------------|-----------|--------------------------------|
| Name        | Aircraft Monitor | Shown as the device name |
| Latitude    | 52.2946   | −90 … 90                       |
| Longitude   | 5.5989    | −180 … 180                     |

Then the tunables (editable any time via the entry's **Configure** button):

| Option              | Default | Validation            |
|---------------------|---------|-----------------------|
| Search radius (km)  | 20      | > 0                   |
| Alert distance (m)  | 250     | > 0                   |
| Prediction time (s) | 180     | > 0                   |
| Polling interval (s)| 10      | ≥ 5                   |
| Minimum altitude (ft)| 0      | ≤ maximum altitude    |
| Maximum altitude (ft)| 15000  | ≥ minimum altitude    |
| Minimum speed (kt)  | 25      | ≥ 0                   |

> The default coordinates are just defaults — set any location worldwide. You
> can add the integration multiple times to monitor several locations
> independently.

---

## Entities

Each configured location creates a device with the following entities
(entity IDs are suffixed automatically when you add more than one location):

| Entity                              | Description |
|-------------------------------------|-------------|
| `sensor.<name>_aircraft_count`      | Number of relevant aircraft within the search radius |
| `sensor.<name>_nearest_aircraft`    | Distance (m) to the nearest relevant aircraft; attributes: callsign, icao, latitude, longitude, altitude, speed, track, aircraft_type |
| `sensor.<name>_approaching_aircraft`| Predicted closest-approach distance (m) of the most-approaching aircraft; attributes include distance, eta, and the aircraft details |
| `binary_sensor.<name>_aircraft_approaching` | `on` while at least one aircraft is predicted to enter the alert zone; attributes: callsign, icao, closest_distance, eta, altitude, speed, track |

### Event

A custom event fires once when a new aircraft enters the alert zone:

```text
aircraft_monitor.aircraft_approaching
```

Event data:

```yaml
entry_id: <config entry id>
location: Home
icao: 48667c
callsign: KLM123
latitude: 52.294
longitude: 5.599
altitude_ft: 4200
speed_knots: 214
track: 87
current_distance_m: 1250
closest_distance_m: 187
eta_seconds: 43
```

The same aircraft (identified by its `icao`/`hex`) will **not** fire the event
repeatedly while it keeps approaching. It re-arms only after it has clearly left
the alert zone (with hysteresis) or disappeared, so a later, separate passage
fires a fresh event.

---

## Automation example

```yaml
automation:
  - alias: "Melding vliegtuig over huis"
    triggers:
      - trigger: state
        entity_id: binary_sensor.aircraft_monitor_aircraft_approaching
        to: "on"
    actions:
      - action: notify.mobile_app
        data:
          title: "✈️ Vliegtuig onderweg"
          message: >
            {{ state_attr('binary_sensor.aircraft_monitor_aircraft_approaching',
               'callsign') }} komt binnen
            {{ state_attr('binary_sensor.aircraft_monitor_aircraft_approaching',
               'eta') }} seconden binnen
            {{ state_attr('binary_sensor.aircraft_monitor_aircraft_approaching',
               'closest_distance') }} meter.
```

You can also trigger on the event directly:

```yaml
automation:
  - alias: "Aircraft approaching event"
    triggers:
      - trigger: event
        event_type: aircraft_monitor.aircraft_approaching
    actions:
      - action: notify.mobile_app
        data:
          message: >
            {{ trigger.event.data.callsign }} at
            {{ trigger.event.data.closest_distance_m }} m in
            {{ trigger.event.data.eta_seconds }} s.
```

---

## Troubleshooting

- **No aircraft show up.** Widen the search radius, lower the minimum speed, or
  raise the maximum altitude. Small aircraft below the minimum speed are filtered
  out by design.
- **The binary sensor never turns on.** It only turns on for aircraft predicted
  to pass within the *alert distance* while heading toward you. Increase the
  alert distance or prediction time to make it less strict.
- **`Failed to set up`.** Check Home Assistant can reach `api.adsb.lol`. Enable
  debug logging (below) to see the requests.
- **Temporary API errors** are expected occasionally; the integration keeps the
  last known state and recovers on the next successful poll.

Enable debug logging:

```yaml
logger:
  default: info
  logs:
    custom_components.aircraft_monitor: debug
```

---

## API & fair use

Data comes from the community-run [ADSB.lol](https://adsb.lol) v2 API:

```text
https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{radius_nm}
```

The radius you configure in kilometres is converted to nautical miles
(`nm = km / 1.852`). No API key is used. At the default 10-second polling this
is roughly 8,640 requests per day per location — please be considerate; a larger
interval (e.g. 15 s) is friendlier to a free community service.

## Privacy

Each poll sends your configured latitude/longitude to `api.adsb.lol` as part of
the query URL. No other personal data is transmitted. Only configure locations
you are comfortable querying against a third-party service.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install pytest pytest-asyncio aiohttp voluptuous
python -m pytest -q
```

The core logic (`geo.py`, `api.py`, `processing.py`) is pure Python and tested
without a running Home Assistant.

## License

[MIT](LICENSE)
