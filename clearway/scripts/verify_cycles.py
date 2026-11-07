#!/usr/bin/env python3
"""Exercise the running operator API and responder lifecycle without model calls.

This checks the real HTTP service, not the browser's map rendering. The companion
in-app-browser verification covers marker selection and visual state.
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--responder-url", default="http://127.0.0.1:8001")
    parser.add_argument("--cycles", type=int, default=5)
    parser.add_argument("--report", type=Path, default=Path(__file__).resolve().parents[1] / "data/verification/api-cycles.json")
    args = parser.parse_args()
    if args.cycles < 5:
        parser.error("At least five cycles are required for the overnight acceptance check.")
    base = args.base_url.rstrip("/")
    responder_base = args.responder_url.rstrip("/")

    def request(path: str, body: dict | None = None, expected: int = 200, *, responder: bool = False):
        payload = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request((responder_base if responder else base) + path, data=payload, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                status, content = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, content = error.code, error.read()
        assert status == expected, f"{path}: expected {expected}, got {status}: {content[:300]!r}"
        return json.loads(content) if content else None

    request("/api/health")
    for private_path in ("/api/state", "/api/labels", "/api/config", "/docs", "/openapi.json"):
        request(private_path, expected=404, responder=True)
    request("/api/reset", {}, expected=405, responder=True)
    sources = request("/api/sources")["sources"]
    assert any(source["id"] == "road-obstruction" for source in sources)
    starting = request("/api/state")["telemetry"]["network_inference_calls"]
    cycles = []
    for index in range(args.cycles):
        state = request("/api/reset", {})
        run_id = state["run"]["id"]
        assert not state["incidents"], "Reset retained old incidents"
        tick = time.perf_counter()
        state = request(f"/api/runs/{run_id}/replay", {"source_id": "road-obstruction", "analysis_mode": "fixture"})
        assert len(state["incidents"]) == 1, "Positive fixture must produce one workflow candidate"
        incident = state["incidents"][0]
        incident_id = incident["id"]
        assert incident["run_id"] == run_id
        assert incident["analysis_mode"] == "fixture"
        assert incident["source_mode"] == "recorded_replay"
        assert incident["provenance"]["fixture"] is True
        assert incident["evidence"] and incident["location"]["quality"] == "simulated"
        assert incident["review_status"] == "candidate"
        repeated = request(f"/api/runs/{run_id}/replay", {"source_id": "road-obstruction", "analysis_mode": "fixture"})
        assert [item["id"] for item in repeated["incidents"]] == [incident_id], "Replay duplicated the incident"
        route = f"/api/respond/{run_id}/{incident_id}"
        assert request(route)["incident"]["review_status"] == "candidate"
        assert request(route, responder=True)["incident"]["review_status"] == "candidate"
        confirmed = request(f"/api/runs/{run_id}/incidents/{incident_id}/confirm", {})
        again = request(f"/api/runs/{run_id}/incidents/{incident_id}/confirm", {})
        assert confirmed["review_status"] == "confirmed"
        assert confirmed["confirmed_at"] == again["confirmed_at"], "Confirmation was not idempotent"
        assert request(route)["incident"]["review_status"] == "confirmed"
        assert request(route, responder=True)["incident"]["review_status"] == "confirmed"
        flow_seconds = time.perf_counter() - tick
        tick = time.perf_counter()
        reset = request("/api/reset", {})
        reset_seconds = time.perf_counter() - tick
        assert reset_seconds < 15, "Reset exceeded the expo limit"
        assert reset["run"]["id"] != run_id and not reset["incidents"]
        request(route, expected=410)
        request(route, expected=410, responder=True)
        request(route + "/media/video", expected=410, responder=True)
        request(f"/api/runs/{run_id}/incidents/{incident_id}/confirm", {}, expected=409)
        request(f"/api/runs/{run_id}/replay", {"source_id": "road-obstruction", "analysis_mode": "fixture"}, expected=409)
        cycles.append({"cycle": index + 1, "flow_seconds": round(flow_seconds, 4), "reset_seconds": round(reset_seconds, 4), "duplicate_incidents": 0})
        print(f"Cycle {index + 1}: replay, evidence, idempotent confirm, responder, reset, expired run PASS", flush=True)

    state = request("/api/reset", {})
    run_id = state["run"]["id"]
    cache = request(f"/api/runs/{run_id}/replay", {"source_id": "road-obstruction", "analysis_mode": "cached"})
    assert cache["analysis"]["mode"] in {"cached", "unavailable"}
    assert cache["telemetry"]["network_inference_calls"] == starting, "Frozen replay made an inference call"
    for incident in cache["incidents"]:
        assert incident["analysis_mode"] == "cached" and incident["provenance"]["fixture"] is False
    end = request("/api/reset", {})
    assert end["telemetry"]["network_inference_calls"] == starting
    report = {
        "verified_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Running HTTP API lifecycle with explicit fixtures; browser rendering and real model accuracy are separate checks.",
        "separate_read_only_responder_checked": True,
        "passed": True,
        "cycle_count": len(cycles),
        "cycles": cycles,
        "reset_median_seconds": statistics.median(row["reset_seconds"] for row in cycles),
        "reset_max_seconds": max(row["reset_seconds"] for row in cycles),
        "network_inference_calls_during_check": end["telemetry"]["network_inference_calls"] - starting,
        "final_state": "fresh empty run",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"PASS: {len(cycles)} cycles; report {args.report}")


if __name__ == "__main__":
    main()
