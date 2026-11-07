# Clearway morning handoff

## Current expo upgrade — November 7, 2026

The app now shows **genuine YOLOX-Tiny vehicle/person boxes on playing video**, synced to seeks and portrait letterboxing. All four available clips have source-bound local detection caches. Incident narratives still use explicit fixtures because the Gemini key is pending. This is real object detection plus a demonstrated review workflow, not a validated danger classifier.

- Added a licensed **person-in-roadway** clip (10.63 s); the upright pedestrian is clearest at 3–4 s. The actual detector reports 0.82 confidence on that person at 4 s. No injury, person down, collision, or confirmed danger is established. It is roadside stock footage, not verified municipal CCTV.
- Added a **shadow gate** counter with an explicit one-call-per-two-second baseline: obstruction 4/6 hypothetical requests avoided; person 0/6, street traffic 0/18, dense traffic 4/6. These are not actual billed savings or incident recall. Actual Gemini/Claude/OpenAI application requests remain zero; provider spend remains $0.
- Replaced the corrupt Cesium glyph label with a stable HTML label. Added 20 official, dated NCDOT camera inventory points, selectable details, and network overview. They are not live camera claims or corroboration for stock footage.
- Prepared Google photorealistic 3D with explicit loading/failure states. **The user deferred the token; basic mapping remains active.** Follow [MAP-SETUP.md](clearway/docs/MAP-SETUP.md) when it arrives.
- Added **Listen to brief** on operator/responder pages. It reads the current evidence, provenance, review status, and unknowns; stops on reset/change. Speaking/stop UI was observed in the built-in browser. A human should confirm audible output on the expo machine.
- The expo launcher uses no reload watcher. It now records service health/exits to dated local logs. SIGINT/SIGTERM/SIGHUP clean up owned processes. The historical eight-second interruption has no established cause; intentional integration restarts are distinct from crashes.
- A temporary Cloudflare tunnel is now **running for responder port 8001 only**, as explicitly authorized. The operator stays loopback-only. The QR updates from a fresh runtime heartbeat without a server restart; stale/inactive state removes it. Public HTTPS page/API loaded, six operator/detector/context endpoints returned 404, and public writes returned 405. **Physical cellular confirmation remains pending.**
- God's Eye View is cloned under ignored `.local/references/gods-eye-view`, revision `ca6eace79e60f29770597ea26871d5427b504b2b`, for reference. Clearway was not replaced; no GEV code or bundled data was copied.

### Exact commands

The local server and temporary responder tunnel are currently running. Do not launch duplicates. For a new session:

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
- Screenshots and receipts remain local under `clearway/data/verification/`: `expo-person-overlay.jpg`, `expo-public-responder.jpg`, `expo-health.json`, `public-handoff.json`, `api-cycles.json`. These are not human evaluation labels.

### Remaining human work

1. Test the current QR on a phone with Wi-Fi off; confirm on the laptop and observe the phone update. Then verify old-link expiry after reset. A laptop/public HTTP check is not a cellular test.
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
