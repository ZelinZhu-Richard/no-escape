# Public traffic CCTV

Clearway includes **767 official Caltrans District 4 cameras across all nine Bay Area counties**, expanded from the previous 100-camera selection on November 7, 2026. **191 entries advertise official HLS video endpoints; 576 are snapshot-only.** The catalog contains names, roads, counties, published coordinates, source cadence and provider URLs, with no camera images. The NC inventory layer, dataset, API route and refresh command have been removed.

| County | Cameras | Advertised video endpoints |
| --- | ---: | ---: |
| Alameda | 219 | 42 |
| Contra Costa | 174 | 29 |
| Marin | 40 | 10 |
| Napa | 6 | 3 |
| San Francisco | 33 | 26 |
| San Mateo | 64 | 27 |
| Santa Clara | 148 | 24 |
| Solano | 53 | 17 |
| Sonoma | 30 | 13 |

The nine-county scope follows [MTC's Bay Area definition](https://511.org/about). Normalization and saved-catalog validation require these counties, matching county IDs, District 4 source URLs and Bay Area coordinate bounds. Out-of-service records and three publisher rows in Santa Cruz/San Joaquin are excluded. Metadata has a 1,000-camera/2MB bound; only the selected feed loads. These are catalog counts, not measured uptime.

## Use

1. Open the local operator at `http://127.0.0.1:8000`.
2. In **Public traffic CCTV**, **Camera feeds → Live video (191)** is selected by default for both the list and map. Search for a road/camera or filter by county, then select a camera to focus its map location and start its video. Choose **All cameras (767)** to include snapshot-only locations. Blue map pins have enlarged click areas and bring the selected preview into view. The list shows the first 50 matches; use **Show 50 more** to reveal another 50. All matching map pins remain selectable, including cameras not yet shown in the list. If video fails, the preview discloses its snapshot fallback; use **Retry live video** or re-select the list item to try again.
3. Read the source cadence and image timestamps. Close the preview to stop refreshing it. Switching to another application tab or hiding the browser pauses preview polling.
4. To refresh the catalog, run `make live-camera-refresh`. The command skips a catalog less than one day old, updates metadata atomically, and never downloads camera images. Reload the page to use new catalog data. It needs no API key.

## What the labels mean

- **Refreshed snapshot:** the provider publishes still images periodically. The selected cameras generally publish every five minutes. This is not a continuous live-video player.
- **Retrieved:** when Clearway fetched the image. It is not the camera's exposure time.
- **Source modified:** the provider's HTTP Last-Modified timestamp, when supplied. This is origin metadata, not a verified capture timestamp.
- **Capture time unknown:** no reliable structured capture timestamp is supplied by this adapter. A date burned into an image is not automatically read or verified.
- **Stale / unavailable:** old source metadata or a failed refresh is disclosed. A previous image can remain only with its original timestamp and a stale label. No licensed replay image is substituted.
- **In service reported:** the catalog lists the camera as operating. Individual images are checked only when selected; this is not a fleet uptime measurement.

A successful JPEG response can itself be a provider outage card. Of three distinct cameras inspected during development, two showed traffic (one with a heavily obscured lens) and one showed “Temporarily Unavailable.” These spot checks are not a claim that all catalog cameras are currently usable. The UI displays the provider image and this limitation; it does not classify scene content or infer that a road is clear.

## Video and local YOLO

Where the provider publishes HLS, the selected visible camera can play actual video through native HLS or `hls.js`. The verified Bay Bridge example is **TVD33 — Bay Bridge SAS Tower West** (`caltrans-d4-53`): its playlist advanced, and a downloaded segment decoded to actual traffic at 352×240, approximately 30 fps. This is provider-buffered video, not a zero-latency guarantee. Advertised URLs do not establish working streams. Use the snapshot fallback if a camera cannot play reliably.

The player prefers managed `hls.js`/MSE playback where supported, with one bounded native-HLS attempt before falling back to snapshots. This repaired the observed embedded-browser reconnection problem. Camera 53 passed pause/resume and snapshot-to-video switching in the built-in browser after the change. Browser decoding may expose a different frame size than the advertised playlist resolution; detections use the actual decoded image dimensions.

Snapshot responses run the configured camera detector (default: YOLO11s VisDrone at 640 pixels, confidence 0.40; Fremont: YOLOX-M at 640, confidence 0.30) on the exact fetched JPEG. Boxes and counts are bound to its SHA-256; cached results keep their image identity and analysis provenance.

Live video draws its boxes directly over the player. The browser captures a presented frame and its media timestamp, verifies the response hash, and requests local detections about every 140 ms when the previous request has finished. It redraws against the presented playback timestamp using [`requestVideoFrameCallback`](https://developer.mozilla.org/en-US/docs/Web/API/HTMLVideoElement/requestVideoFrameCallback), with a playback-clock fallback. ByteTrack associates high-confidence detections and matched low-confidence observations with ephemeral stream IDs. Only actual current observations are returned; lost predictions stay internal. Stable IDs supply the short display velocity estimate for at most 200 ms. The UI separates raw YOLO counts from low-confidence recoveries; these are not accuracy-validated tracks. See [CCTV-QUALITY.md](CCTV-QUALITY.md) for the implementation and measured Fremont comparison.

Results older than 350 ms of playback or 500 ms since capture are hidden, including late responses. Pause, buffering, seek, hidden page, and camera changes clear the overlay. A fresh empty result removes the previous boxes. CORS/canvas failures, missing model weights, or detector failures show unavailable state rather than substitute detections. Native video fullscreen or picture-in-picture may omit the surrounding SVG overlay; use the in-page player for the annotated view.

For a fresh machine, run `make detection-setup` and `make live-detect` to prepare the pinned live model before using camera detections. `make detect` separately prepares the recorded replay detector. See [CCTV-QUALITY.md](CCTV-QUALITY.md) for same-frame comparisons, source-detail limits, and the approved AGPL model choice. The runtime never automatically downloads weights or calls a cloud model. Images and results use bounded memory caches; individual frame uploads to the loopback operator are limited to one megabyte and eight requests per second, with only one inference at a time. This does not increase the provider's snapshot refresh rate. Small, distant, obscured, or low-resolution objects may be missed. A zero count does not establish that the road is empty or safe.

Selected playing video now creates human-review candidates from sustained local detection signals; it never runs Gemini or confirms incidents automatically. Snapshots remain detection-only. See [LIVE-ALERTS.md](LIVE-ALERTS.md). Existing replay boxes and incident candidates stay attached to their original replay. California imagery cannot corroborate an unrelated historical clip with simulated Durham placement. No facial recognition, license-plate identification, persistent person identity, cross-camera tracking, or public dispatch is performed.

## Provider and access

Source: [Caltrans CCTV documentation](https://cwwp2.dot.ca.gov/closed-circuit-television-cameras.html), [District 4 JSON catalog](https://cwwp2.dot.ca.gov/data/d4/cctv/cctvStatusD04.json), and [Caltrans conditions of use](https://dot.ca.gov/conditions-of-use). The CCTV documentation provides these feeds for application integration without charge and requests fair use. Attribution remains visible; availability is controlled by Caltrans.

Only the selected camera is requested. The snapshot backend uses a fixed public host/path allowlist, blocks redirects, validates JPEG type/signature and size, limits time and request rate, and respects the source cadence. HLS video loads directly from the official provider with its supported CORS headers; no stream proxy or access-control bypass is added. Small in-memory caches are discarded when the server stops. There is no continuous image archive, bulk harvesting, browser credential use, paid provider access, or camera-key bypass. One trigger image per live candidate is retained locally (maximum 20 per run) and removed on reset. Public camera and frame-inference routes are available only on the loopback operator service, not the responder service.

### Traffic model and camera text

The user approved the AGPL-3.0 YOLO11s VisDrone profile. `make live-detect` selects its pinned weights as the default and configures YOLOX-M for Fremont (`caltrans-d4-49`), whose frontal traffic was poorly detected by VisDrone. Restart the operator afterward. The UI identifies camera-specific models. `make live-detect-apache` explicitly selects YOLOX-M as the default and preserves existing camera overrides. These choices do not change replay caches. On camera 689 only, known top-left title and bottom-left timestamp regions are excluded by detection center; dashed outlines and “Camera text regions excluded” disclose the filter. This is a camera-specific graphics filter, not a calibrated road region. Counts and cache provenance include the policy. See [CCTV-QUALITY.md](CCTV-QUALITY.md) for development evidence, configuration commands and limits.
