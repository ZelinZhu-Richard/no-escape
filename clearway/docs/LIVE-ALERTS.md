# Live CCTV review candidates

Open a public camera with working live video. Local YOLO observations from that selected, visible, playing video automatically feed a temporal monitor. A persistent signal creates a **candidate**, adds its camera-location marker to the map and a card to the review queue, and retains the triggering frame for the evidence panel. Choose Confirm or Dismiss after inspecting it. The responder brief uses that same frozen evidence, not a later live image.

**Pause alerts** stops candidate monitoring while YOLO boxes can continue. Pause YOLO, pause video, switch to snapshots, close the camera, or hide the tab to stop observations. Only the selected video is monitored; this is not continuous monitoring of all 100 cameras. Five-minute snapshots do not provide the timing evidence needed by these rules and do not create candidates.

## Rules and limits

| Review cue | Required observations | What it does not establish |
| --- | --- | --- |
| Possible stationary vehicle | Same vehicle class, confidence ≥0.50, box area ≥0.1% of image, at least 12 seconds on both media/server clocks and 12 distinct frames. Adjacent and first-box overlap ≥0.70; center displacement from first box ≤1.5% of normalized image units. | A breakdown, obstruction, exact lane, or emergency. Normal queues, traffic signals, parking, slow distant traffic, or false detections can trigger review. |
| Sustained person visible | Person confidence ≥0.55, area ≥0.05%, at least 3 seconds on both clocks and 5 distinct frames. Adjacent overlap ≥0.30 and center step ≤0.06 normalized units. | A person in a travel lane, injury, danger, or identity. Ordinary pedestrian activity or a false detection can trigger review. |

These are development heuristics in image space, not validated tracking, speed estimates, or incident classification. There is no calibrated road/lane region. High vehicle count alone does not alert. No human-label evaluation or natural-incident recall is claimed.

Each observation is bound to camera ID, current run, stream session, exact JPEG SHA-256, detector configuration and playback time. Both clocks must advance; gaps over two seconds, discontinuities, missing matches, repeated image bytes, or configuration changes restart continuity. The client creates a fresh stream session on seek, pause/buffering, source/run changes, or monitoring restart. Input sequence limits prevent stitching separate clips into one duration.

## Evidence and review lifecycle

- Map placement is the official **camera coordinate**, explicitly not the detected object's position. Provider capture time and stream delay remain unknown. Observation time is when the local server processed the frame.
- The panel shows the saved trigger JPEG, genuine local detections, model name, measured window duration, the rule's observation summary, source credit, review status, and unknowns. No replay footage is substituted.
- Each camera creates at most one item per run, even after confirmation/dismissal. Reset begins a new run. The run holds at most 20 live candidates and 20 bounded JPEGs (one megabyte maximum each), not a continuous video archive.
- State and image insertion happen in one transaction that rechecks the current run. Reset removes retained live images; old evidence/brief links expire, and late inference cannot recreate old-run candidates.
- Public responder access remains scoped to a selected run/incident. It serves the retained evidence and review status, with no camera control, frame inference, operator mutation, or automatic dispatch. The previously deferred phone test and stopped tunnel remain unchanged.

All inference and temporal monitoring run locally. No Gemini, Claude, or OpenAI calls are made by this feature. The existing approved model license and provider caps remain unchanged.

## Verification

Tests use controlled detector sequences and fake clocks to cover both positive rules, moving/empty frames, repeats, time gaps, stream/run changes, malformed provenance, deduplication, capacity, review actions, evidence binding, reset races, and responder scope. These test sequences are not natural incidents or human evaluation labels. Browser/live-feed verification and exact test totals are recorded in the root MORNING_REPORT.md.
