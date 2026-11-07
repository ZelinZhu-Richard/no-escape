# Public traffic CCTV

Clearway includes 100 official Caltrans District 4 camera locations nearest San Francisco/Oakland. The catalog stores names, roads, counties, authentic coordinates, source cadence, and provider URLs. It does not store camera images. The existing twenty Durham-area NCDOT inventory points remain a separate metadata-only layer.

## Use

1. Open the local operator at `http://127.0.0.1:8000`.
2. In **Public traffic CCTV**, search for a road/camera or filter by county. Select a camera to focus its map location and request its current snapshot. Map pins can also select the preview.
3. Read the source cadence and image timestamps. Close the preview to stop refreshing it. Switching to another application tab or hiding the browser pauses preview polling.
4. To refresh the catalog, run `make live-camera-refresh`. The command skips a catalog less than one day old, updates metadata atomically, and never downloads camera images. Reload the page to use new catalog data. It needs no API key.

## What the labels mean

- **Refreshed snapshot:** the provider publishes still images periodically. The selected cameras generally publish every five minutes. This is not a continuous live-video player.
- **Retrieved:** when Clearway fetched the image. It is not the camera's exposure time.
- **Source modified:** the provider's HTTP Last-Modified timestamp, when supplied. This is origin metadata, not a verified capture timestamp.
- **Capture time unknown:** no reliable structured capture timestamp is supplied by this adapter. A date burned into an image is not automatically read or verified.
- **Stale / unavailable:** old source metadata or a failed refresh is disclosed. A previous image can remain only with its original timestamp and a stale label. No licensed replay image is substituted.
- **In service reported:** the catalog lists the camera as operating. Individual images are checked only when selected; this is not a fleet uptime measurement.

A successful JPEG response can itself be a provider outage card. Of three distinct cameras inspected during development, two showed traffic (one with a heavily obscured lens) and one showed “Temporarily Unavailable.” These spot checks are not a claim that all 100 cameras are currently usable. The UI displays the provider image and this limitation; it does not classify scene content or infer that a road is clear.

Viewing a public snapshot does not run YOLO, Gemini, or the incident workflow. Existing replay boxes and incident candidates stay attached to their original replay. California imagery cannot corroborate an unrelated historical clip with simulated Durham placement. No facial recognition, license-plate identification, personal tracking, or public dispatch is performed.

## Provider and access

Source: [Caltrans CCTV documentation](https://cwwp2.dot.ca.gov/closed-circuit-television-cameras.html), [District 4 JSON catalog](https://cwwp2.dot.ca.gov/data/d4/cctv/cctvStatusD04.json), and [Caltrans conditions of use](https://dot.ca.gov/conditions-of-use). The CCTV documentation provides these feeds for application integration without charge and requests fair use. Attribution remains visible; availability is controlled by Caltrans.

Only the selected camera is requested. The backend uses a fixed public host/path allowlist, blocks redirects, validates JPEG type/signature and size, limits time and request rate, and respects the source cadence. A small in-memory image cache is discarded when the server stops. No image archive, bulk image harvesting, browser credentials, paid provider access, or camera-key bypass is used. Public camera routes are available only on the loopback operator service, not the responder service.

[DriveNC's developer documentation](https://www.drivenc.gov/developers/doc) requires a developer key for its [camera API](https://www.drivenc.gov/help/endpoint/cameras). No such key is configured. Do not relabel NCDOT inventory pins as working North Carolina streams. A future authenticated adapter should keep the key server-side and follow the provider's rate and usage requirements.
