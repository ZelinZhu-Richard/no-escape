# Clearway morning handoff

## PR review fixes — November 7, 2026

The user requested the Codex review be checked, all findings fixed, and PR #1 merged. GitHub Codex reported two issues, and a local Codex review of the full PR found one additional provenance issue. All three are addressed:

- **Replay selection:** Start replay mounts and plays the source selected in the replay rail, including when another clip or live incident was open. Later navigation/reset cancels playback intent, and late analysis responses cannot steal the operator's selection.
- **Analysis provenance:** A preview without an associated result says “Not analyzed in this view.” Source/run-bound results replace the unrelated last run-level analysis badge; incident evidence retains its own provenance.
- **Footage setup:** Both restoration scripts load the same local configuration as the API and honor `CLEARWAY_DATA_DIR`, including process-variable precedence. Original media, derivatives, posters and receipts share the configured directory. `make footage` uses the application virtual environment after `make setup`.

Verification: **290 backend tests and 72 frontend tests passed**, plus the production build and emitted assets/license checks. Twelve new regression cases cover replay source selection, live evidence, cancellation/reset races, source provenance, and both scripts' default/.env/process directory behavior. A built-in-browser reproduction selected person evidence while the replay rail selected obstruction; Start replay then played the obstruction video, with advancing playback time. Local screenshot: `clearway/data/verification/pr1-replay-review-fix.jpg`. The two fixture candidates remain available in the current local demo run. No server restart or paid inference was needed.

The user-authorized merge supersedes earlier draft-only instructions. Gemini credentials/validation, the Google 3D token, physical cellular handoff testing, and human evaluation labels remain deferred; merging does not complete those tasks. GitHub CI remains an inactive example, so the reported checks are local.

## Live CCTV → review candidates — November 7, 2026

**Selected playing CCTV now creates reviewable candidates from sustained local detections.** A possible stationary vehicle requires at least 12 seconds; repeated person visibility requires at least 3 seconds. Both require distinct frames, consistent boxes, confidence/size thresholds, and advancing video/server clocks. These are local temporal rules, not calibrated lane, crash, injury, or danger classification. Traffic density alone does not alert.

A candidate appears in the shared queue and on the map at its **camera coordinate**, with one frozen trigger frame, hash-verified boxes, rule duration, source credit, observation time, and explicit unknowns. Confirm/Dismiss and the scoped responder page reuse the retained evidence. Replay browsing and mode changes preserve live items. Each camera creates only one item per run, even after review; reset clears its evidence. Retention is capped at 20 trigger JPEGs per run. There is no continuous camera archive.

### Run and use

The local no-reload server is running at `http://127.0.0.1:8000`. Open **Public traffic CCTV → Open 6th Street live**, or another working video camera. Monitoring is enabled by default for the current run. **Pause alerts** stops candidate monitoring while local box detection can continue. Snapshots, hidden/paused video, camera switches, seeks, and gaps do not accumulate an observation window. Only the selected playing camera is monitored, not the whole catalog. No public tunnel or deployment was started.

If restarting, use `make serve`; fresh-checkout setup remains `make setup`, `make detection-setup`, `make live-detect`, and `make build`. Recorded demo restoration is separate (`make footage`, `make detect`). Rule details and lifecycle limits are in [LIVE-ALERTS.md](clearway/docs/LIVE-ALERTS.md).

### Verification and remaining limits

- **284 backend tests and 66 frontend tests passed; production build and emitted license/Cesium assets passed.** Independent review found no material issues.
- Controlled temporal tests cover stationary/person positives, moving/empty/duplicate frames, confidence and timing limits, gaps, stream/model/run changes, one item per camera, 20-image capacity, review actions, exact image/hash binding, in-flight reset, and operator/responder boundaries. These are test sequences, not human labels or natural-incident accuracy.
- A visibly labeled, isolated **synthetic browser test** verified the camera-position map marker, queue selection, frozen evidence with boxes, confirmation, responder brief, 390×844 image/overlay alignment, and expired handoff after reset. Its local test service was stopped and its state was never placed in the actual demo database. Proof images: `live-alert-synthetic-evidence.jpg` and `live-alert-synthetic-responder-mobile.jpg` under `clearway/data/verification/`.
- The actual 6th Street HLS feed played with genuine YOLO11s detections and the temporal monitor receiving distinct frames, around 6 updates/s in a spot check. Pause alerts left the video playing and genuine boxes updating; re-enabling started a fresh observation window. The 390-pixel layout had no horizontal overflow. It showed ordinary moving traffic and no candidate during the checked interval. No naturally occurring emergency or incident was verified. Real-monitor screenshots: `live-alert-monitor-desktop.jpg` and `live-alert-monitor-mobile.jpg` under `clearway/data/verification/`.
- Five real HTTP replay/confirm/responder/reset cycles passed again with zero cloud calls; receipt: `clearway/data/verification/live-alert-replay-cycles.json`. One announced integration restart loaded the feature; reload remains disabled.
- Provider inference spend remains **$0**. The Gemini key, Google 3D token, physical cellular handoff test, and human evaluation labels remain pending/deferred as previously recorded.

This section supersedes earlier claims that CCTV cannot create candidates or retains no evidence images. Existing footage licenses, AGPL source/model choice, and provider caps remain unchanged.


## Traffic-trained live CCTV upgrade — November 7, 2026

**YOLO11s VisDrone is installed, selected, and verified on actual playing public CCTV**, following the user's explicit AGPL-3.0 approval. Open **Public traffic CCTV → Open 6th Street live** at `http://127.0.0.1:8000`. The no-reload operator/responder server is running locally; no public tunnel is running.

The live player is larger, box labels are optional, and the visible summary reports the actual model, counts, inference time, input resolution, and update rate. Recorded replay keeps its existing YOLOX-Tiny caches. Only Telegraph camera689 excludes the inspected title/timestamp regions; dashed outlines and text disclose that filter, and its identity is included in cache provenance.

### What was verified

- **253 backend tests and 57 frontend tests passed.** The production build and emitted license/Cesium checks passed. Independent review found no material issues.
- Five complete running-service HTTP replay/confirm/reset cycles passed with zero cloud inference calls: `clearway/data/verification/traffic-yolo11-api-cycles.json`.
- Actual browser playback on 6th Street and Telegraph showed YOLO11s boxes directly on moving video at roughly 6–6.5 updates/s. Spot-check inference times were around 45–51 ms. Labels toggled without restarting video. Telegraph showed the graphics exclusions and no boxes on its title/timestamp in the inspected view.
- Desktop and 390×844 video/overlay bounds matched, without mobile horizontal overflow. Local proof: `traffic-yolo11-desktop.jpg`, `traffic-yolo11-mobile.jpg`, and `traffic-yolo11-telegraph.jpg` under `clearway/data/verification/`.
- On the same saved 6th Street development frame, the old detector returned 4 vehicles and the final profile returned 17. Telegraph returned 10 after excluding 10 graphic-centered boxes. These counts are not precision/recall or accuracy measurements; no human labels were fabricated. The blurred distant bridge frame still returned zero, despite visible traffic.

### Run and remaining work

Use the existing server. For a fresh checkout: `make setup`, `make detection-setup`, `make live-detect`, `make build`, then `make serve`. Restore recorded demo media/caches separately with `make footage` and `make detect`. `make live-detect` explicitly downloads and verifies the approved AGPL model; restart after changing profiles. `make live-detect-apache` selects the compared YOLOX-M weights instead, without changing the application license.

AGPL text and public source links are included in the app and repository; model weights and camera images stay out of Git. **Provider inference spend remains $0.** The current server was intentionally restarted to load the approved model, with reload disabled. Camera access remains provider-dependent, and distant/blurred imagery can still miss vehicles. Detection is not danger classification or validated tracking.

Human to-dos remain: add the Gemini key for approved bounded validation; provide the deferred Google 3D token; run the deferred physical cellular handoff test; label evaluation windows; check audible voice and rehearse. See [CCTV-QUALITY.md](clearway/docs/CCTV-QUALITY.md) for model provenance, settings, and limits. This section supersedes the earlier live-detector/model setup and test counts below.


## Live video, map clicks, and camera YOLO — November 7, 2026

**Actual provider video is working.** Select **TVD33 — I-80: Bay Bridge SAS Tower West** in Public traffic CCTV. The built-in browser played its advancing HLS stream and produced real local YOLO detections on sampled frames. Forty catalog entries advertise video URLs; only the selected camera is loaded, and this is not a claim that every advertised stream works. Cameras without reliable video retain the five-minute snapshot fallback.

Purple map pins now have larger visible markers and a 24-pixel hit area. Clicking one focuses and scrolls its preview into view. A browser click approximately eleven pixels from a settled pin selected **TV113 — SR-24: AT TELEGRAPH** and brought the preview onto the screen. Cyan NCDOT inventory points still provide metadata only.

The snapshot view draws genuine YOLO boxes on its exact JPEG. **Live video now carries boxes directly over the playing feed**, replacing the separate analyzed-frame panel. Frequent local detections are tied to captured-frame hashes and media timestamps, with short motion estimates between results. The browser targets a new sample about every 140 ms, only after the previous request finishes. Extrapolation stops at 200 ms; boxes expire after 350 ms of media time or 500 ms since capture. Pause, buffering, seek, camera changes, and fresh empty results clear old boxes. This is local CPU detection with approximate motion compensation, not validated tracking or danger classification. Small vehicles may be missed; capture time and provider delay remain unknown.

### Current verification

- **218 backend tests and 55 frontend tests passed.** Production build and dependency/Cesium notices passed; `hls.js` 1.7.4 is pinned and its Apache-2.0 attribution retained.
- Five running-service HTTP replay/confirm/reset cycles passed again with no cloud inference calls: `clearway/data/verification/live-overlay-api-cycles.json`.
- Browser verification: the Bay Bridge stream played with boxes directly in the video container and no analyzed-frame image. The visible sampling rate was 6–6.5 updates/s in this spot check; observed overlay ages included 33, 66, and 101 ms. Video and overlay bounds matched at desktop and 390×844, with no mobile horizontal overflow. Pause YOLO cleared boxes while playback continued; Pause updates cleared the source and overlay; Resume updates played and restored detections. Two other cameras (T250N and TVD32) failed to start and used the snapshot fallback; camera 53 also encountered a provider/player interruption during the longer check. These are spot checks, not an uptime or tracking-accuracy benchmark. Current screenshots: `clearway/data/verification/live-direct-overlay-desktop.jpg` and `live-direct-overlay-mobile.jpg`. Earlier map-click and snapshot checks remain recorded below.
- Local-only detector: one inference slot, eight numeric-result cache entries, bounded JPEG dimensions/size, no automatic model download, no image archive or cloud model calls. The frame endpoint caps uploads at one megabyte and eight requests per second and remains unavailable on the responder service.
- The local server was intentionally restarted once to load the new endpoint. No reload watcher or public tunnel is running. The Gemini key, Google 3D token, and physical phone test remain deferred/pending as previously recorded.

Use the existing `make serve` session at `http://127.0.0.1:8000`. On a fresh machine, prepare `make detection-setup` and `make detect`, then `make build` and `make serve`. See [LIVE-CAMERAS.md](clearway/docs/LIVE-CAMERAS.md) for video/fallback behavior and detection limits. This section supersedes older snapshot-only and no-local-inference descriptions below.

## Public CCTV expansion — November 7, 2026

Added **100 authentic Caltrans District 4 traffic-camera points** across San Francisco, Alameda, and San Mateo counties, in addition to the twenty metadata-only NCDOT points. The public camera browser has road/name search, county filtering, map selection, a network-overview shortcut, and a selected-camera preview. Selecting a public camera preserves the separate incident/replay workflow.

The preview fetches actual public provider imagery. All selected catalog entries publish a **five-minute snapshot cadence**; this is not continuous live video. Retrieval time, provider Last-Modified, unknown capture time, pause controls, and stale/error states are visible. A catalog entry or successful JPEG download does not prove the camera is online: **three distinct cameras were inspected, two showing traffic and one returning a provider outage card**. One traffic view has an obscured lens. The browser independently displayed the bridge and San Mateo previews. No fleet-wide availability or live incident-detection claim is made.

### Run and use

The no-reload local server is running on `http://127.0.0.1:8000`; the responder tunnel remains stopped. Select **Public CCTV · 100** on the map to see the network, then select a camera in **Public traffic CCTV** or a purple map pin. The first listed camera, **TVD31 — Before YBI Tunnel**, displayed bridge traffic during verification. Provider conditions may change.

For a new session, use `make build` and `make serve`. `make live-camera-refresh` refreshes the metadata catalog at most daily by default, without downloading images; reload the page afterward. No camera key is required for this Caltrans adapter. DriveNC's documented API does require a developer key, so North Carolina locations remain inventory only. Full source/access notes are in [LIVE-CAMERAS.md](clearway/docs/LIVE-CAMERAS.md).

### Verification and limits

- **186 backend tests and 33 frontend tests passed**, including URL/redirect and response bounds, failure/staleness handling, request limits surviving image-cache eviction, selected-camera identity, rapid camera switching, hidden-tab cancellation, filtering, stable map entities, and responder isolation.
- Production build and emitted Cesium/license checks passed. One announced local server restart loaded the new routes; reload watching remains disabled.
- Five actual HTTP replay/confirm/reset cycles passed again with **zero network inference calls**. Report: `clearway/data/verification/cctv-api-cycles.json`. The final run is empty and ready for a new replay.
- Built-in-browser checks passed at desktop width and **390×844**: actual images, county/search filtering, geographic focus, no horizontal overflow, and footer below the expanded content. Screenshots: `clearway/data/verification/cctv-network-desktop.jpg` and `cctv-network-mobile.jpg`.
- Only the selected camera refreshes. Images are cached briefly in memory; no archive, paid inference, generated incident, deployment, or new public tunnel was created. New camera routes return 404 on the responder service. Existing Gemini/3D/physical-phone deferrals remain unchanged.

This follow-up is included in [draft PR #1](https://github.com/ZelinZhu-Richard/no-escape/pull/1). The earlier upgrade notes below remain useful history; the new section supersedes their camera-count and current-test-count statements.

## Current expo upgrade — November 7, 2026

The app now shows **genuine YOLOX-Tiny vehicle/person boxes on playing video**, synced to seeks and portrait letterboxing. All four available clips have source-bound local detection caches. Incident narratives still use explicit fixtures because the Gemini key is pending. This is real object detection plus a demonstrated review workflow, not a validated danger classifier.

- Added a licensed **person-in-roadway** clip (10.63 s); the upright pedestrian is clearest at 3–4 s. The actual detector reports 0.82 confidence on that person at 4 s. No injury, person down, collision, or confirmed danger is established. It is roadside stock footage, not verified municipal CCTV.
- Added a **shadow gate** counter with an explicit one-call-per-two-second baseline: obstruction 4/6 hypothetical requests avoided; person 0/6, street traffic 0/18, dense traffic 4/6. These are not actual billed savings or incident recall. Actual Gemini/Claude/OpenAI application requests remain zero; provider spend remains $0.
- Replaced the corrupt Cesium glyph label with a stable HTML label. Added 20 official, dated NCDOT camera inventory points, selectable details, and network overview. They are not live camera claims or corroboration for stock footage.
- Prepared Google photorealistic 3D with explicit loading/failure states. **The user deferred the token; basic mapping remains active.** Follow [MAP-SETUP.md](clearway/docs/MAP-SETUP.md) when it arrives.
- Added **Listen to brief** on operator/responder pages. It reads the current evidence, provenance, review status, and unknowns; stops on reset/change. Speaking/stop UI was observed in the built-in browser. A human should confirm audible output on the expo machine.
- The expo launcher uses no reload watcher. It now records service health/exits to dated local logs. SIGINT/SIGTERM/SIGHUP clean up owned processes. The historical eight-second interruption has no established cause; intentional integration restarts are distinct from crashes.
- A temporary Cloudflare tunnel was verified for **responder port 8001 only** and then stopped after the user deferred the physical phone test. The operator stays loopback-only. The QR updates from a fresh runtime heartbeat without a server restart; stale/inactive state removes it. Public HTTPS page/API loaded, six operator/detector/context endpoints returned 404, and public writes returned 405. **Physical cellular confirmation is deferred by the user, not passed.**
- God's Eye View is cloned under ignored `.local/references/gods-eye-view`, revision `ca6eace79e60f29770597ea26871d5427b504b2b`, for reference. Clearway was not replaced; no GEV code or bundled data was copied.

### Exact commands

The local server is running; the temporary responder tunnel is stopped. Shutdown was verified through the foreground process exit, `tunnel-status: stopped`, and an empty operator public origin. Do not launch a duplicate server. Use `make tunnel` when ready for the deferred phone test; it creates a new hostname and QR. For a new session:

```sh
make serve                # terminal 1: operator 8000, read-only responder 8001
make tunnel               # terminal 2: temporary responder-only HTTPS origin
make tunnel-status
make tunnel-stop          # close public access, remove the managed QR origin
```

For a fresh checkout, prepare `make setup`, `make footage`, `make detection-setup`, `make detect`, and `make build` before serving. Media and detector weights are intentionally absent from Git. Optional dense-traffic media may be unavailable; detection preparation skips missing optional footage.

### Verified in this upgrade

- **162 backend tests passed**, including detector provenance, malformed/incomplete cache rejection, person-category sample validation, responder isolation, and actual hangup signals against isolated fake children. After the sandbox PID-probe repair, all **16 affected integration/operations tests passed** again.
- **20 frontend tests passed** and the production build plus Cesium/license asset check passed.
- Five complete HTTP replay/evidence/confirm/reset cycles passed. Thirty consecutive HTTP health samples succeeded over one minute; this does not establish long-term uptime.
- Built-in-browser checks: actual playback/seek updates the boxes and counts; map label is readable; NCDOT point selection/network overview works; voice enters speaking state and stops; the public QR appears; the HTTPS read-only brief loads. At 390×844, operator and public responder had no horizontal page overflow; the responder had no operator controls.
- Public confirmation propagation was checked separately on an obstruction fixture: the HTTPS status changed from candidate to confirmed after a local confirmation. An expired earlier brief and its video both returned HTTP 410 through the public tunnel. The current person-scene link and state were preserved for the human cellular test; none of these HTTP checks establishes cellular operation.
- Screenshots and receipts remain local under `clearway/data/verification/`: `expo-person-overlay.jpg`, `expo-public-responder.jpg`, `expo-health.json`, `public-handoff.json`, `api-cycles.json`. These are not human evaluation labels.

### Remaining human work

1. **Deferred by the user:** when ready, run `make tunnel`, scan the newly generated QR on a phone with Wi-Fi off, confirm on the laptop, and observe the phone update. Then verify old-link expiry after reset. The previous public hostname is no longer active. A laptop/public HTTP check is not a cellular test.
2. Add the Gemini key privately and run the bounded real semantic analysis. The $5/five-attempt ceiling persists; no provider substitution is enabled.
3. Add the deferred Cesium token and rebuild/visually validate Google 3D. Native provider credits must remain visible.
4. Check audible voice output, label development windows, and rehearse the 90-second story with explicit replay/fixture distinctions. Do not claim medical diagnosis, live dispatch, calibrated lane location, or natural-incident accuracy.

## Historical overnight handoff

The remainder records the earlier build before the expo additions above. Its zero-tunnel and deferred-YOLO/voice statements describe that earlier run only.

November 7, 2026. The local review-to-handoff workflow is implemented. **The working demonstration uses explicit fixture analysis on real licensed footage. Genuine model detection and cellular phone handoff are not yet validated.**

**Gemini follow-up:** the user has now authorized **$5 total / at most five inference attempts**. Private `clearway/.env` loading, the selected `gemini-3.5-flash-lite` model, bounded cost accounting, offline readiness, and `make gemini-smoke` / `make gemini-replay` are implemented. **107 backend/setup/budget/smoke tests and five frontend tests pass.** The user confirmed the key is not yet available; the smoke command stops at that check and has made zero provider requests. See [MODEL-SETUP.md](clearway/docs/MODEL-SETUP.md) for the teammate handoff. The overnight results below remain historical verification, not a claim of real inference.

Implementation branch: `feat/clearway-overnight-demo`. [Draft PR #1](https://github.com/ZelinZhu-Richard/no-escape/pull/1) is open for review and has not been merged. Nothing has been deployed, no public tunnel was started, and no organizer was contacted.

## Start the demo

On this machine, dependencies, licensed footage, and the frontend build are already present. From `/Users/richardzhu/dev/no_escape`:

```sh
make serve
```

Open **http://127.0.0.1:8000**. The launcher also starts the read-only responder on **http://127.0.0.1:8001**. Ctrl+C stops both. If they are already running, use the existing preview or stop that launcher before starting another; do not launch duplicate services on the same ports.

For a fresh checkout:

```sh
make setup
make footage
make build
make serve
```

Prerequisites: Python 3.11+ (local tests used 3.14.6), Node 22.12+ (local build used 22.21.1), npm, and ffmpeg/ffprobe. `make footage` restores the positive and control, verifies the original checksums, and generates the 1080p replay. Media is intentionally absent from Git. The dense-traffic development candidate is optional and may show unavailable on a new checkout.

Demo sequence: click **Reset demo** if the saved preview already has an incident, choose **Road obstruction**, keep **Fixture walkthrough**, click **Start replay**, open its map marker/card, seek **00:01 / 00:04 / 00:08**, click **Confirm incident**, and open the local responder preview. **Reset demo** clears the queue and expires old handoffs. A public QR appears only when an intentional HTTPS `PUBLIC_BASE_URL` is configured; an unset URL produces a clearly labeled local preview.

## What works

- Real licensed Pexels video playback, linked source/license credit, timestamp seeking, explicit recorded-replay and fixture badges, and visible unknowns.
- Source selection, map marker/card selection, incident evidence, human confirmation/dismissal, repeated replay deduplication, and run-safe reset.
- Separate read-only responder application, shared state, polling, scoped video/poster routes, and expired-run handling. It has no operator mutation routes.
- Local source/configuration validation, SQLite persistence, genuine-result cache provenance, sanitized request/spend ledger, and enforced Gemini authorization limits (the follow-up permits $5/five attempts). Frozen cache misses make no inference calls.
- A human-labeling page and evaluation script. No human labels were fabricated or submitted. The evaluation report says **awaiting labels**.
- Startup, asset restoration, five-cycle HTTP verification, draft pitch/commercial assumptions, reference attribution, and manual morning tunnel instructions.

## Partial or deliberately deferred

| Area | Current limit |
| --- | --- |
| Computer Vision inference | Gemini Developer API adapter and the selected model defaults are implemented and tested against mocks. The $5 follow-up is authorized, but the key is pending; no actual provider call or genuine cache entry exists. Fixture observations are not AI results. |
| Cloud credits | Google Cloud billing credit has not been verified for the selected service. This adapter is not Vertex AI. The approved $5 ceiling allows bounded billed validation without assuming credit eligibility. |
| Mapping | Basic Cesium/OpenStreetMap with an illustrative fallback. Photorealistic 3D requires eligible service access/token and remains unverified. The positive's coordinates are unknown, so Durham placement is simulated. |
| QR / phone | URL composition and responder code exist. Local phone layout is tested; a real phone over cellular has not been tested. No public connection is running. |
| Evaluation | No human labels or real predictions; no accuracy, natural-incident recall, or gate savings can be claimed. Thirty adjacent windows are not thirty independent incidents. |
| Other features | YOLO gating, voice, weather, external-source corroboration, live camera collection, lane projection, Claude summarization, and OpenAI integration were not built overnight. |

## Verification and spend

The following commands were exercised locally:

```sh
cd /Users/richardzhu/dev/no_escape
make test
make verify                 # while make serve is running
python3 clearway/scripts/evaluate.py
python3 clearway/scripts/fetch_footage.py --with-control
```

- Backend/evaluation/media tests: **61 passed**, with one non-failing Starlette warning about the HTTPX test client.
- Five HTTP cycles against the operator and separate responder: **5/5 passed**, zero duplicate incidents, zero inference requests, stale mutation rejection, and old media/link expiration. Reset median **0.0022 s**, max **0.0039 s**, `n=5`; these measure local HTTP reset, not browser rendering or model latency.
- Browser inspection used Codex's visible built-in browser. Licensed video decoded and sought to 4 seconds; confirmation, read-only responder, and expired handoff were observed. The responder at 390×844 had no horizontal overflow or operator controls. The control fixture produced no candidate; missing genuine cache stayed unavailable.
- Frontend final build and emitted Cesium/license asset check passed. **5/5 frontend regression tests passed**, covering stale polling across reset/confirmation, reset during pending replay, late initialization, and unavailable-cache labels.
- Five full browser cycles passed with licensed video, evidence seeking, duplicate replay checks, confirmation, separate responder, and expired handoff. Visible-reset median **302 ms**, max **305 ms**, `n=5`, including automation/state-capture overhead. Repeated cycles used the offline diagram; the default Cesium/OpenStreetMap map and native credits were inspected separately.
- Operator layout was inspected at 1440×1000 and 390×844; the narrow layout had no horizontal page overflow. QR SVG rendering and the selected run/incident URL were checked using a temporary **local** operator configured with a reserved invalid HTTPS origin. That process was stopped. This verifies rendering/composition, not scanning or cellular reachability.
- Actual direct model-provider requests: **Gemini 0 / Claude 0 / OpenAI 0**. Direct application API spend: **$0**. Google Cloud deployment spend: **$0**. This does not estimate the Codex session's own usage or ordinary dependency downloads.
- Local evidence: `clearway/data/verification/api-cycles.json`, `clearway/data/verification/browser-cycles.json`, `clearway/data/verification/clearway-demo.jpg`, `clearway/data/evaluation/report.json`, `clearway/data/spend-ledger.jsonl`. These remain ignored. Tests use synthetic temporary records; none becomes human evaluation ground truth.

## Morning priorities

1. **Run the local demo and inspect the draft PR.** Keep the known-good fixture fallback available. Start with the 90-second [table script](clearway/docs/PITCH.md); humans finalize claims and delivery.
2. **Make the CV component real.** Add the teammate's key to ignored `clearway/.env`, run `make gemini-check` and `make gemini-smoke` within the now-authorized $5/five-attempt limit, inspect output, and rehearse `make gemini-replay`. Restart the backend after adding the key. Follow [MODEL-SETUP.md](clearway/docs/MODEL-SETUP.md). Do not present fixture observations as model output.
3. **Validate the phone handoff.** Follow [TUNNEL.md](clearway/docs/TUNNEL.md), expose only responder port 8001 intentionally, configure the HTTPS origin, refresh the operator, and scan on a phone with Wi-Fi off. Check confirmation updates and expiration after reset. Stop the tunnel after use.
4. **Label and evaluate.** One person labels roughly thirty useful windows with scene/event counts. Freeze settings before running final predictions. Use [EVALUATION.md](clearway/docs/EVALUATION.md); report actual denominators and development-only limitations. Without natural events, say recall is not measurable on natural data.
5. **Resolve event/reuse and map access.** Check organizer announcements and source-use eligibility; no clarification has been obtained. Credit both inspirations. Verify Cesium/Google photorealistic access and native credits if enabling it.
6. **Projection only after the core path is healthy.** Use the reserved Person A hours 10–16 if feasible. Calibrate on a fixed, known-location live camera and ordinary traffic; stop at hour 16 if independent landmark checks fail. Unknown-location stock footage cannot validate lane placement.

## Known expo risks

- A fixture-only demonstration does not substantiate Computer Vision performance. Genuine, reviewed model results are the highest-value unfinished work.
- An unset/changing tunnel hostname, venue connectivity, a sleeping laptop, or stale QR can break phone access. The old URL must expire, not silently redirect.
- Initial Cesium download is large (about 4.2 MB minified / 1.1 MB gzip in this build). Basic map tiles need network access; pre-load the app and retain the labeled offline fallback. Do not claim photorealistic coverage or quota verification from the basic-map test.
- The positive clip is about 11 seconds and shows a utility work zone/obstruction; it does not establish a vehicle stall, crash, injuries, or incident onset. Its camera location/time are unknown.
- Third-party footage downloads can change. The restoration command stops on a checksum mismatch; do not silently substitute different footage or licenses.

## Repairs during verification and PR

Independent review found and resolved gate-evaluation denominator loss, partially written video derivatives, frontend stale-poll races, reset being disabled during analysis, and misleading genuine-negative labels. Browser inspection found Cesium runtime assets under the wrong copied prefix; the copy configuration is corrected and the production build now checks required emitted files. No unresolved test failure remains in the local checks above.

The default production map is restored after offline testing. The local operator/responder launcher is left running for the preview, with a confirmed fixture incident. Reset before the next fresh walkthrough. No temporary QR-test service or public tunnel remains running.

The GitHub connection rejected creating `.github/workflows/checks.yml` because its OAuth authorization lacks the `workflow` scope. No permissions were expanded. The optional configuration is retained as [ci-checks.example.yml](clearway/docs/ci-checks.example.yml), which does not run as a workflow. All reported checks above were run locally; there is no hosted CI result. A maintainer with the appropriate repository authorization can later install that template under `.github/workflows/`.

GitHub confirmed [draft PR #1 — Build Clearway's replay-to-responder demo](https://github.com/ZelinZhu-Richard/no-escape/pull/1). The implementation and this handoff are committed to its feature branch; `main` retains the documentation baseline. Keep the PR in draft while the morning model, labeling, and cellular checks remain open.
