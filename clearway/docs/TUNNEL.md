# Morning phone handoff

This runbook prepares a manual morning test. No tunnel or deployment is started by this document. The overnight target is local workflow verification; cellular access remains unverified until someone performs the steps below.

The commands follow `API-CONTRACT.md`. Before use, check `MORNING_REPORT.md` for the final tested startup commands and any implementation changes. Run commands from `/Users/richardzhu/dev/no_escape/clearway` unless stated otherwise.

## Local prerequisites

Install the project's documented dependencies and build `web/dist` using the main run instructions. Keep the source footage in `data/footage/`; it is not in Git. Confirm that the normal local console works before exposing the responder service.

The intended services are:

- Operator: `api.app:app` on `127.0.0.1:8000`.
- Responder: `api.app:responder_app` on `127.0.0.1:8001`.
- Both processes default to `clearway/data/clearway.sqlite3`. If `CLEARWAY_DATA_DIR` is set, use the same absolute data-directory value in both terminals. Do not point one at a test database or another temporary data directory.
- Only the responder port is used for the public connection. It serves the built phone UI, read-only selected-incident status, and that incident's allowed evidence.

Start the responder in a separate terminal:

If `make serve` is already running, stop that launcher with Ctrl+C first: it owns both ports. The commands below replace that combined launcher so the operator can receive the new public origin without starting duplicate services.

```sh
.venv/bin/python -m uvicorn api.app:responder_app --host 127.0.0.1 --port 8001
```

Before creating the tunnel, verify a selected incident's local responder route on port 8001. Confirm that `/api/state`, `/api/labels`, and operator mutation routes are unavailable there. The incident-specific video and poster should load; no directory listing or generic footage download endpoint should be exposed. Root integration verification and exact status codes belong in `MORNING_REPORT.md`.

## Create the temporary connection manually

If `cloudflared` is already installed, use its documented [Quick Tunnel command](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/):

```sh
cloudflared tunnel --url http://127.0.0.1:8001
```

Copy the HTTPS `trycloudflare.com` origin printed by the command. Keep this terminal open only for the planned phone test/demo. Quick Tunnels have changing hostnames, no uptime guarantee, and no SSE support; Clearway's responder uses two-second polling.

Restart the operator with the actual origin in `PUBLIC_BASE_URL`. The placeholder below must be replaced; it is not a usable tunnel address:

```sh
PUBLIC_BASE_URL='https://REPLACE-WITH-ACTUAL-HOST.trycloudflare.com' \
  .venv/bin/python -m uvicorn api.app:app --host 127.0.0.1 --port 8000
```

Use the configured data directory from the main run instructions for both processes. `PUBLIC_BASE_URL` must be an HTTPS origin without a path, credentials, query, or fragment. It is read at startup, so restart the operator after changing it. Do not add API keys to these commands. The base URL controls link generation; it does not expose operator controls.

Return to the operator console. Refresh its configuration, select the current incident, and verify the generated QR contains the new HTTPS origin, the selected `run_id`, and the selected `incident_id`. A local preview or an unset base URL is not a public phone handoff.

## Cellular acceptance test

1. Turn off Wi-Fi on the phone; leave cellular data on.
2. Start the licensed replay and open the incident on the laptop.
3. Scan its QR. Check that the page shows the same incident, source/analysis modes, simulated placement, evidence, and current review status.
4. Confirm on the laptop. Within the polling interval and normal network delay, the phone should show the confirmed status. The phone must not expose confirm/reset controls.
5. Reset on the laptop. The old phone URL must show expired; it must not switch to a new incident automatically. Old evidence requests must also expire.
6. Start a new replay, select its incident, scan the new QR, and verify that its run ID differs.

Record device, network mode, time, success/failure, observed update delay, and expired-link behavior in `MORNING_REPORT.md`. Do not record the full signed incident URL in public logs if a later implementation adds access tokens.

If the hostname changes, update `PUBLIC_BASE_URL`, restart/refresh the operator configuration, regenerate the QR, and repeat the cellular check. A successful local browser test is not a replacement.

## Shutdown and fallback

Press Ctrl-C in the `cloudflared` terminal when testing ends; its temporary URL should stop responding. Stop the responder process when it is no longer needed. Restart the operator without `PUBLIC_BASE_URL` to return to local-preview mode if desired.

If cellular access fails, keep the local phone-layout preview available on the laptop and state that network handoff is pending. Use a backup recording only if the team has made and labeled one. Do not broaden the tunnel to the operator port or leave it unattended overnight to work around a responder failure.
