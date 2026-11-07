# Clearway

A local road-incident review desk: replay licensed footage, inspect a candidate on the map, review timestamped evidence, confirm it, and open a run-specific responder brief.

The default demonstration uses **explicit fixture analysis** on real licensed footage. It is not live detection. The selected clip's map placement is simulated. Fresh Gemini access and billing have not been verified; the default build makes no model-provider requests. See [PLAN.md](PLAN.md) and the final [morning report](MORNING_REPORT.md) for status and remaining work.

## Run locally

Requirements: Python 3.11+ (tested on 3.14), Node 22.12+ (tested on 22.21), npm, and ffmpeg for restoring/processing footage.

From the repository root:

```sh
make setup
make footage
make build
make serve
```

Open **http://127.0.0.1:8000** for the operator console. `make serve` runs the operator on port 8000 and the separate read-only responder on port 8001; Ctrl+C stops both. No tunnel or deployment is started. If the current machine already has the media and dependencies, only `make build` and `make serve` are needed.

1. Leave analysis on **Fixture** and select the road-obstruction replay.
2. Start replay, select its marker/card, and inspect the timestamped observations.
3. Confirm the candidate and open its local responder preview.
4. Reset. Old run/incident links expire instead of showing the latest incident.

No keys are required for the fixture workflow. Frozen cached mode uses only genuine saved model results; an empty cache is shown as unavailable. A fixture never becomes a genuine cached result.

## Footage

Media is intentionally absent from Git. `make footage` downloads the selected original and the street-traffic control from their documented sources, verifies source SHA-256 hashes, and creates the local 1080p replay. Licenses and modifications are in [ATTRIBUTION.md](clearway/docs/ATTRIBUTION.md). The current development machine already has these files.

The additional dense-traffic clip is a development candidate and is optional. Missing media is visible in the UI. None of the clips establishes natural-scene accuracy or a real-time North Carolina incident.

## Checks

```sh
make test
# With make serve running in another terminal:
make verify
python3 clearway/scripts/evaluate.py
```

`make verify` exercises five real HTTP replay/evidence/confirm/responder/reset cycles and checks stale-link rejection, deduplication, and zero inference requests. Browser rendering is checked separately in Codex's built-in browser; results belong in the morning report. The evaluation report remains **awaiting labels** until human submissions exist. Fixture test cases are not added to that label database.

For frontend iteration, run `npm run dev` inside `clearway/web` with the backend on 8000. The development server is at `http://127.0.0.1:5173` and proxies `/api` to the local operator.

## Configuration

- `CLEARWAY_DATA_DIR`: optional absolute local directory for SQLite, cache, ledger, and `footage/`. Both services must use the same directory. Default: `clearway/data`.
- `PUBLIC_BASE_URL`: optional HTTPS origin for the deliberately exposed read-only responder. Without it, the UI provides a local preview, not a public phone QR. See [TUNNEL.md](clearway/docs/TUNNEL.md) for the manual morning procedure.
- Map settings are build-time Vite variables; see `clearway/web/.env.example`. No Cesium token is required for the basic-map/illustrative fallback.
- Gemini configuration and the zero-charge gate are documented in [MODEL-SETUP.md](clearway/docs/MODEL-SETUP.md). A Cloud credit does not satisfy the $0 billable cap.

Never put keys in command logs, source files, or a committed environment file. Local data, `.env` files, media, and the unrelated ECC installations are ignored.

## References

[God's Eye View](https://github.com/bilawalsidhu/gods-eye-view) informs the map-to-detail interaction; [HawkWatch](https://github.com/Grace-Shao/Treehacks2025) informs timestamped video evidence. Clearway is a fresh implementation. See [REFERENCES.md](clearway/docs/REFERENCES.md) for inspected source patterns and [PITCH.md](clearway/docs/PITCH.md) for the draft table script.
