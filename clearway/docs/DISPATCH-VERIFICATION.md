# Dispatch UI and live CCTV verification

Verified November 7, 2026, against the teammate's merged Dispatch UI (`8671380`) and the focused corrections on `fix/dispatch-live-alert-verification`.

## Corrections

- Map/queue selection now focuses and reveals the selected evidence after React commits it, including on desktop where evidence sits above the map. Background polling does not scroll the operator away from the current view.
- The idle heading says “No candidates yet.” It no longer implies all roads are clear or a camera is being monitored.
- Replay savings retain their “replay estimate” and “Shadow gate; no paid calls skipped” disclosures. Detector-unavailable explanations remain visible.
- Frozen live-evidence metadata uses a light surface with readable dark text. The image retains its black letterboxing.

## What passed

**294 backend tests, 78 frontend tests, TypeScript/production build, and emitted Cesium/license asset checks passed.** Independent review verified the first three fixes; the fourth was found and verified visually on the real live-evidence panel. The new desktop selection tests check focus, scrolling after the selected content commits, reduced-motion behavior, and absence of scroll on polling.

The controlled API tests exercise detector observations → temporal candidate → persisted image/evidence → confirm/dismiss → scoped responder → reset expiry. These tests inject offline detections and clocks; they are not natural incident validation or model-accuracy measurements.

The built-in browser played two genuine Caltrans HLS streams with the installed YOLO11s VisDrone detector. Both showed moving boxes at approximately 6–6.5 local updates/s in spot checks. An isolated local instance ran the unchanged monitor with real frames, real clocks and real weights, without seeded alerts or altered thresholds. Neither camera produced a new candidate during its bounded polling window:

| Camera | Check window | New candidates |
| --- | ---: | ---: |
| I-80 at 6th Street | 120.96 seconds | 0 |
| SR-24 at Telegraph | 120.86 seconds | 0 |

The current demo already held a genuine 6th Street candidate, `e3dd8eb1…`, created at **20:12:27 UTC** before this verification session. Its stored provenance reports a truck matched for **12.046 seconds across 75 distinct frames**, with YOLO11s VisDrone and `fixture: false`. This retained candidate was used to verify the updated review interface; it was not presented as a new alert generated during the two live checks.

In the visible browser at 1440 px, clicking its orange camera-location marker revealed the correct frozen evidence, including the source, original observation time, temporal rule and unknowns. Confirm changed the queue, evidence panel and map to confirmed. The read-only responder on port 8001 displayed the same confirmed status and exact evidence image. SHA-256 matched the stored detection and incident provenance. Its global-state route returned 404 and a confirmation POST returned 405.

At 390 px, both the operator evidence and responder had no horizontal overflow. The frozen image and SVG overlay bounds matched and the metadata was readable. This is browser responsive-layout verification, not the deferred physical cellular-phone test.

## Local state and evidence

The actual demo run remains intact: two recorded fixture candidates and the **confirmed retained live candidate**. No reset removed its evidence. A camera can create only one candidate per run, including after confirmation; starting a new observation cycle for the same camera requires the normal Reset demo action.

The isolated live-check server was stopped and its tab closed. No public tunnel, deployment, paid inference or automatic dispatch was performed. Provider request count and inference spend remain zero. Genuine natural-incident recall and danger classification are still unvalidated.

Local ignored artifacts under `clearway/data/verification/`:

- `dispatch-verification.json`: measured checks and retained-alert provenance.
- `dispatch-live-yolo.jpg`: real playing feed with local detections.
- `dispatch-live-map.jpg`: retained candidate at its camera location.
- `dispatch-live-confirmed-desktop.jpg`: confirmed evidence in Dispatch.
- `dispatch-live-mobile.jpg` and `dispatch-live-responder-mobile.jpg`: 390 px checks.

Use the running app at `http://127.0.0.1:8000/`; reload an older open page to load the rebuilt UI. The local server continues without reload watching. Startup remains `make serve` after the usual setup/build commands.
