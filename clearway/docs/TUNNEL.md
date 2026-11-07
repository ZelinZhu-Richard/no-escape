# Expo server and phone handoff

The November 7 expo follow-up explicitly authorizes a temporary responder-only public tunnel. The original overnight run did not. A successful public HTTP check is separate from a real phone test over cellular; record both honestly in `MORNING_REPORT.md`.

Run the commands below from `/Users/richardzhu/dev/no_escape`. Only the read-only responder on **127.0.0.1:8001** is exposed. The local operator remains on **127.0.0.1:8000**.

## Stable expo serving

```sh
make build
make serve
```

The launcher starts the production frontend and both Uvicorn services **without `--reload`**. It does not restart a failed service automatically. Do not run a second launcher on the same ports, rebuild the frontend mid-pitch, or restart the backend while someone is demonstrating it. Stop the old launcher with Ctrl+C before intentionally loading a new build or private environment settings.

The original launcher already omitted reload. An observed interruption therefore does not by itself establish an auto-reload problem; intentional restarts and process failures must be distinguished using terminal evidence.

Each launcher session now writes timestamped operator, responder, and launcher logs under ignored `clearway/data/runtime/logs/`. It records child PIDs, HTTP health transitions, and the exact exit code if a service stops. Access logs are disabled so incident URLs are not copied into ordinary server logs. Provider credentials and raw provider errors are not part of logging. A process exit stops its peer and prints which service log to inspect; there is no hidden restart loop.

Both processes and the tunnel command must use the same `CLEARWAY_DATA_DIR` if configured. The tunnel uses the same private configuration loader as the operator. Its heartbeat is under that data directory's `runtime/` subfolder; the default is `clearway/data/runtime/`. No server is exposed on all interfaces.

## Start the temporary public connection

```sh
clearway/.venv/bin/python clearway/scripts/tunnel.py install
clearway/.venv/bin/python clearway/scripts/tunnel.py start
```

`install` prepares the official Cloudflare **2026.10.7** macOS ARM64 release in ignored `.local/bin/`. It checks the archive SHA-256 published by the official GitHub release metadata and the executable SHA-256 before running it. No global installation, account login, personal Cloudflare configuration, or service registration occurs. On other operating systems, this automatic installer stops; use the [official downloads](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) and adapt the pinned platform asset before running it.

The start command first verifies that port 8001 serves the responder HTML and returns 404 for operator state, configuration, sources, and labels. It then starts a [Cloudflare Quick Tunnel](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) targeting only `http://127.0.0.1:8001`, with a deliberately empty configuration file, auto-update disabled, and loopback-only metrics. It never inherits provider keys or `TUNNEL_*` overrides. The command remains in the foreground; keep its terminal open for the agreed demo/test period.

When the connection is registered, it prints the temporary HTTPS origin and writes ignored `clearway/data/runtime/tunnel.json`. The operator reads this managed origin when `PUBLIC_BASE_URL` is unset, so the tunnel can be configured without restarting the demo server. A deliberately configured `PUBLIC_BASE_URL` takes precedence; clear an old manual value before using automatic tunnel discovery. Refresh the operator configuration after starting or stopping the tunnel.

The runtime record includes the origin, active status, child PID, wrapper PID, session ID, and a three-second heartbeat. Expired/inactive records must not produce a public QR. It is local runtime state, not a deployable credential or a committed default URL.

Check status from another terminal:

```sh
clearway/.venv/bin/python clearway/scripts/tunnel.py status
```

The hostname changes each time. Quick Tunnels have no uptime guarantee and no SSE support; the responder uses polling. Anyone with a current incident link can view that brief and its licensed evidence until the run expires or the connection stops. This is a temporary expo connection, not a production dispatch service.

## Public and cellular acceptance

First check from an external HTTP client that the current responder page and its status endpoint load, while `/api/state`, `/api/config`, `/api/labels`, and `/api/sources` are unavailable on the public origin. Confirm/reset/write requests must remain blocked. Check selected evidence and old-run expiration. A public HTTP response proves public reachability, not cellular operation on a judge's phone.

Then perform the human phone test:

1. Turn off Wi-Fi on the phone; leave cellular data enabled.
2. Start the licensed replay and select its incident on the laptop.
3. Scan the generated QR. Check matching incident, source/analysis modes, simulated placement, evidence, and review status.
4. Confirm on the laptop. The phone should update after its polling interval and network delay, with no operator controls.
5. Reset on the laptop. The old phone link must show expired; its evidence must expire too. It must not jump to a newer incident.
6. Start a new replay and scan the new QR; its run ID must differ.

Record device, cellular mode, time, result, observed update delay, and expiration behavior. Do not claim cellular verification from a laptop browser or an HTTP request. If no person has performed this test, the report must retain **cellular phone test pending**.

## Stop and return to local mode

Press Ctrl+C in the tunnel terminal, or run:

```sh
clearway/.venv/bin/python clearway/scripts/tunnel.py stop
clearway/.venv/bin/python clearway/scripts/tunnel.py status
```

The stop command immediately marks the managed origin inactive, and the foreground owner terminates and waits for its `cloudflared` child. Normal exit, Ctrl+C, termination, and POSIX terminal hangup (`SIGHUP`) perform the same cleanup. The expo service launcher also cleans up both of its children on terminal hangup. The status should become `stopped`. Refresh the operator configuration; it should return to a clearly labeled local responder preview. The temporary public URL should stop serving the brief.

Do not force-kill the wrapper: an operating-system SIGKILL cannot run cleanup. If a wrapper was forcibly killed, the heartbeat expires and hides the managed QR, but an orphaned child may need deliberate process cleanup. `stop` does not blindly send signals to a stale, potentially reused PID. Service/session terminal ownership should be retained throughout the expo.

If public connectivity fails, preserve the local phone-layout preview and report the failed network step. Never point the tunnel at the operator port to bypass a responder failure.
