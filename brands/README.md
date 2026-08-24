# Brand assets

Icon for the Aircraft Monitor integration.

| File | Size | Notes |
|------|------|-------|
| `icon.png` | 256×256 | transparent PNG |
| `icon@2x.png` | 512×512 | transparent PNG |

## Why the icon shows as "unavailable" in Home Assistant / HACS

Home Assistant and HACS load integration icons from the central
[`home-assistant/brands`](https://github.com/home-assistant/brands) repository,
**not** from this repo. Until the brand is added there, the integration shows
"icon unavailable". There is no way to serve the icon from this repository alone.

## How to publish the icon (later)

1. Fork [`home-assistant/brands`](https://github.com/home-assistant/brands).
2. Add these files as:
   ```
   custom_integrations/aircraft_monitor/icon.png     (256×256)
   custom_integrations/aircraft_monitor/icon@2x.png  (512×512)
   ```
3. Open a pull request. The brands repo CI checks that images are trimmed,
   transparent, correctly sized and optimized.
4. After the PR is merged, Home Assistant and HACS will display the icon
   (allow some time for CDN/cache refresh).
