# Public traffic CCTV

Clearway includes 100 official Caltrans District 4 camera locations nearest San Francisco/Oakland. Forty entries advertise an official HLS video URL; other cameras use refreshed snapshots. The catalog stores names, roads, counties, authentic coordinates, source cadence, and provider URLs. It does not store camera images. The existing twenty Durham-area NCDOT inventory points remain a separate metadata-only layer.

## Use

1. Open the local operator at `http://127.0.0.1:8000`.
2. In **Public traffic CCTV**, search for a road/camera or filter by county. Select a camera to focus its map location. Purple map pins have enlarged click areas and bring the selected preview into view. Cyan North Carolina inventory pins have metadata only.
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

## Video and local YOLO

Where the provider publishes HLS, the selected visible camera can play actual video through native HLS or `hls.js`. The verified Bay Bridge example is **TVD33 — Bay Bridge SAS Tower West** (`caltrans-d4-53`): its playlist advanced, and a downloaded segment decoded to actual traffic at 352×240, approximately 30 fps. This is provider-buffered video, not a zero-latency guarantee. Forty advertised URLs do not establish forty working streams. Use the snapshot fallback if a camera cannot play reliably.

The player prefers managed `hls.js`/MSE playback where supported, with one bounded native-HLS attempt before falling back to snapshots. This repaired the observed embedded-browser reconnection problem. Camera 53 passed pause/resume and snapshot-to-video switching in the built-in browser after the change. Browser decoding may expose a different frame size than the advertised playlist resolution; detections use the actual decoded image dimensions.

Snapshot responses run the configured live detector (selected: YOLO11s VisDrone at 640 pixels, confidence 0.40) on the exact fetched JPEG. Boxes and counts are bound to its SHA-256; cached results keep their image identity and analysis provenance.

Live video draws its boxes directly over the player. The browser captures a presented frame and its media timestamp, verifies the response hash, and requests local detections about every 140 ms when the previous request has finished. It redraws against the presented playback timestamp using [`requestVideoFrameCallback`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback), with a playback-clock fallback. Adjacent same-class detections can supply a bounded velocity estimate for at most 200 ms. This reduces lag between genuine detections; it is approximate motion compensation, not an accuracy-validated tracker.

Results older than 350 ms of playback or 500 ms since capture are hidden, including late responses. Pause, buffering, seek, hidden page, and camera changes clear the overlay. A fresh empty result removes the previous boxes. CORS/canvas failures, missing model weights, or detector failures show unavailable state rather than substitute detections. Native video fullscreen or picture-in-picture may omit the surrounding SVG overlay; use the in-page player for the annotated view.

For a fresh machine, run `make detection-setup` and `make live-detect` to prepare the pinned live model before using camera detections. `make detect` separately prepares the recorded replay detector. See [CCTV-QUALITY.md](CCTV-QUALITY.md) for same-frame comparisons, source-detail limits, and the approved AGPL model choice. The runtime never automatically downloads weights or calls a cloud model. Images and results use bounded memory caches; individual frame uploads to the loopback operator are limited to one megabyte and eight requests per second, with only one inference at a time. This does not increase the provider's snapshot refresh rate. Small, distant, obscured, or low-resolution objects may be missed. A zero count does not establish that the road is empty or safe.

Selected playing video now creates human-review candidates from sustained local detection signals; it never runs Gemini or confirms incidents automatically. Snapshots remain detection-only. See [LIVE-ALERTS.md](LIVE-ALERTS.md). Existing replay boxes and incident candidates stay attached to their original replay. California imagery cannot corroborate an unrelated historical clip with simulated Durham placement. No facial recognition, license-plate identification, personal tracking, or public dispatch is performed.

## Provider and access

Source: [Caltrans CCTV documentation](https://cwwp2.dot.ca.gov/closed-circuit-television-cameras.html), [District 4 JSON catalog](https://cwwp2.dot.ca.gov/data/d4/cctv/cctvStatusD04.json), and [Caltrans conditions of use](https://dot.ca.gov/conditions-of-use). The CCTV documentation provides these feeds for application integration without charge and requests fair use. Attribution remains visible; availability is controlled by Caltrans.

Only the selected camera is requested. The snapshot backend uses a fixed public host/path allowlist, blocks redirects, validates JPEG type/signature and size, limits time and request rate, and respects the source cadence. HLS video loads directly from the official provider with its supported CORS headers; no stream proxy or access-control bypass is added. Small in-memory caches are discarded when the server stops. There is no continuous image archive, bulk harvesting, browser credential use, paid provider access, or camera-key bypass. One trigger image per live candidate is retained locally (maximum 20 per run) and removed on reset. Public camera and frame-inference routes are available only on the loopback operator service, not the responder service.

[DriveNC's developer documentation](https://www.drivenc.gov/developers/doc) requires a developer key for its [camera API](https://www.drivenc.gov/help/endpoint/cameras). No such key is configured. Do not relabel NCDOT inventory pins as working North Carolina streams. A future authenticated adapter should keep the key server-side and follow the provider's rate and usage requirements.

### Traffic model and camera text

The user approved the AGPL-3.0 YOLO11s VisDrone profile. `make live-detect` selects its pinned weights; restart the operator afterward. `make live-detect-apache` explicitly selects YOLOX-M instead. This does not change the replay detector. On camera 689 only, known top-left title and bottom-left timestamp regions are excluded by detection center; dashed outlines and “Camera text regions excluded” disclose the filter. This is a camera-specific graphics filter, not a calibrated road region. Counts and cache provenance include the policy. See [CCTV-QUALITY.md](CCTV-QUALITY.md) for development evidence and limits.
