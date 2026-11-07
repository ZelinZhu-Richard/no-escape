# Clearway

A local road-incident review desk: replay licensed footage, inspect a candidate on the map, review timestamped evidence, confirm it, and open a run-specific responder brief.

The replay now shows **genuine local YOLOX detections** synchronized to licensed video. Incident narratives remain **explicit fixtures** until Gemini is configured and validated; boxes alone do not diagnose danger. Map placement for the obstruction/person clips is simulated. Fresh Gemini access and billing have not been verified. See [PLAN.md](PLAN.md) and the [morning report](MORNING_REPORT.md) for tested behavior and remaining work.

## Run locally

Requirements: Python 3.11+ (tested on 3.14), Node 22.12+ (tested on 22.21), npm, and ffmpeg for restoring/processing footage.

From the repository root:

```sh
make setup
make footage
make detection-setup
make detect
make build
make serve
```

Open **http://127.0.0.1:8000** for the operator console. `make serve` runs the operator on port 8000 and the separate read-only responder on port 8001; Ctrl+C stops both. No tunnel or deployment is started. If the current machine already has the media and dependencies, only `make build` and `make serve` are needed.

1. Leave analysis on **Fixture walkthrough** and select **Road obstruction** or **Person in roadway**.
2. Start replay, watch saved YOLO boxes, select its marker/card, and inspect the timestamped observations. The person is clearest at 3–4 seconds.
3. Try **Listen to brief**, confirm the candidate, and open its responder preview.
4. Reset. Old run/incident links expire instead of showing the latest incident.

No keys are required for the fixture workflow. Frozen cached mode uses only genuine saved model results; an empty cache is shown as unavailable. A fixture never becomes a genuine cached result.

`make detect` prepares actual local YOLOX boxes at four samples per second using a checksum-pinned Apache-2.0 model. Playback uses the saved detections, so no cloud inference is needed for boxes. The counter compares a shadow gate with one request per two-second window: it is an estimate of requests avoided, not actual bill savings or measured incident recall. See [VISION.md](clearway/docs/VISION.md).

`make tunnel` explicitly starts a temporary public connection to the read-only responder. The QR origin updates automatically; `make tunnel-stop` closes it. Follow [TUNNEL.md](clearway/docs/TUNNEL.md), including the human phone test with Wi-Fi off. `make serve` itself never starts a tunnel and uses no reload watcher.

The map includes **100 public Caltrans traffic-camera points** around San Francisco/Oakland, with county/search filters and selected-camera previews. Click a purple pin to open its preview; enlarged hit areas and automatic scrolling make the selection visible. Forty catalog entries advertise **HLS video**, including the verified **TVD33 — Bay Bridge SAS Tower West**. Supported cameras play the provider's live video; other cameras and failed streams use the labeled five-minute snapshot fallback.

The existing local YOLOX model draws boxes **directly over the playing live video**, using frequent sampled detections and short motion estimates between them. Boxes follow the playback clock and disappear when results become stale or playback pauses. Snapshot boxes remain bound to their exact image. Missing detection resources show unavailable state. Only the selected visible camera loads, with no cloud inference, camera archive, or automatic incident claims. Availability and image quality remain provider-controlled. See [LIVE-CAMERAS.md](clearway/docs/LIVE-CAMERAS.md).

The separate 20 dated NCDOT camera inventory locations remain metadata only; DriveNC's camera API needs a developer key. `make camera-refresh` refreshes that inventory, and `make live-camera-refresh` refreshes the Caltrans catalog (at most daily by default, without fetching images). Both networks are unrelated to the recorded incident evidence. Google photorealistic 3D is prepared but awaits the team's Cesium token; activation steps are in [MAP-SETUP.md](clearway/docs/MAP-SETUP.md).

## Footage

Media is intentionally absent from Git. `make footage` restores the obstruction, street-traffic control, and person-roadway clips from documented sources, verifies original SHA-256 hashes, and creates the local replay derivatives. Licenses and modifications are in [ATTRIBUTION.md](clearway/docs/ATTRIBUTION.md). The current development machine already has these files.

The additional dense-traffic clip is a development candidate and is optional. Missing media is visible in the UI. None of the clips establishes natural-scene accuracy or a real-time North Carolina incident.

## Checks

```sh
make test
# With make serve running in another terminal:
make verify
python3 clearway/scripts/evaluate.py
```

`make verify` exercises five real HTTP replay/evidence/confirm/responder/reset cycles and checks stale-link rejection, deduplication, and zero inference requests. Browser rendering is checked separately in Codex's built-in browser; results belong in the morning report. The evaluation report remains **awaiting labels** until human submissions exist. Fixture test cases are not added to that label database.

For real Gemini validation, the user has approved a $5/five-attempt limit. Have the teammate add `GEMINI_API_KEY` to ignored `clearway/.env`, then run `make gemini-check`, `make gemini-smoke`, and `make gemini-replay`. See [MODEL-SETUP.md](clearway/docs/MODEL-SETUP.md). Restart `make serve` after changing backend environment settings. Account access and actual inference remain unverified until that smoke command succeeds.

For frontend iteration, run `npm run dev` inside `clearway/web` with the backend on 8000. The development server is at `http://127.0.0.1:5173` and proxies `/api` to the local operator.

## Configuration

- `CLEARWAY_DATA_DIR`: optional absolute local directory for SQLite, cache, ledger, and `footage/`. Both services must use the same directory. Default: `clearway/data`.
- `PUBLIC_BASE_URL`: optional HTTPS origin overriding the managed tunnel origin. Without either an explicit origin or a fresh active tunnel heartbeat, the UI provides a local preview. See [TUNNEL.md](clearway/docs/TUNNEL.md).
- Map settings are build-time Vite variables; see `clearway/web/.env.example`. No Cesium token is required for the basic-map/illustrative fallback.
- Gemini configuration and the bounded $5 follow-up authorization are documented in [MODEL-SETUP.md](clearway/docs/MODEL-SETUP.md). Cloud credit eligibility is still unverified.

Never put keys in command logs, source files, or a committed environment file. Local data, `.env` files, media, and the unrelated ECC installations are ignored.

## References

[God's Eye View](https://github.com/bilawalsidhu/gods-eye-view) informs the map-to-detail interaction; [HawkWatch](https://github.com/Grace-Shao/Treehacks2025) informs timestamped video evidence. Clearway is a fresh implementation. See [REFERENCES.md](clearway/docs/REFERENCES.md) for inspected source patterns and [PITCH.md](clearway/docs/PITCH.md) for the draft table script.
