from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
import threading
import time
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from api.app import create_app


POSITIVE = {
    "mode": "fixture", "status": "complete", "message": "Fixture analysis; not model inference.",
    "candidate": True, "title": "Possible road obstruction / utility work zone",
    "category": "road_obstruction",
    "observations": [{"timestamp_seconds": 1.0, "observation": "Utility trucks occupy the road."}],
    "unknowns": ["Source location and capture time are unknown."],
    "provenance": {"provider": "fixture", "model": None, "prompt_version": "test-v1", "fixture": True, "cache_key": "test-fixture"},
}


class Analyzer:
    def __init__(self):
        self.calls = 0
        self.started = threading.Event()
        self.release = None
        self.failure = False
        self.result_override = None

    def analyze(self, source_id, mode):
        self.calls += 1
        self.started.set()
        if self.release:
            assert self.release.wait(timeout=5)
        if self.failure:
            raise RuntimeError("secret-token-do-not-reflect")
        if self.result_override:
            return deepcopy(self.result_override)
        result = deepcopy(POSITIVE)
        if mode != "fixture":
            result.update(mode="unavailable", status="unavailable", candidate=False, observations=[], message="No genuine cached result.")
            result["provenance"]["fixture"] = False
        if source_id != "road-obstruction":
            result.update(candidate=False, observations=[], title="", category="", message="Fixture no-alert; control awaiting human labels.")
        return result

    def telemetry(self):
        return {"network_inference_calls": 0, "cache_hits": 0, "fixture_runs": self.calls, "estimated_spend_usd": 0}


@pytest.fixture
def services(tmp_path):
    analyzer = Analyzer()
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html><body>Clearway test shell</body></html>")
    (dist / "assets").mkdir()
    (dist / "assets" / "app.js").write_text("console.log('test')")
    data = tmp_path / "data"
    client = TestClient(create_app(data_dir=data, analysis_service=analyzer, web_dist=dist))
    public = TestClient(create_app(data_dir=data, read_only=True, web_dist=dist))
    yield client, public, analyzer, data, dist
    client.close()
    public.close()


def replay(client, run_id, source_id="road-obstruction", mode="fixture"):
    return client.post(f"/api/runs/{run_id}/replay", json={"source_id": source_id, "analysis_mode": mode})


def first_incident(client):
    run_id = client.get("/api/state").json()["run"]["id"]
    response = replay(client, run_id)
    assert response.status_code == 200, response.text
    return response.json()["incidents"][0]


def test_five_complete_cycles_are_clean(services):
    client, public, analyzer, _, _ = services
    run_ids = []
    for _ in range(5):
        incident = first_incident(client)
        run_id, incident_id = incident["run_id"], incident["id"]
        run_ids.append(run_id)
        assert len(replay(client, run_id).json()["incidents"]) == 1
        assert incident["analysis_mode"] == "fixture"
        assert incident["provenance"]["fixture"] is True
        assert incident["location"]["quality"] == "simulated"
        endpoint = f"/api/respond/{run_id}/{incident_id}"
        assert public.get(endpoint).json()["incident"]["review_status"] == "candidate"
        confirm = f"/api/runs/{run_id}/incidents/{incident_id}/confirm"
        confirmed = client.post(confirm, json={}).json()
        assert confirmed["review_status"] == "confirmed"
        assert client.post(confirm, json={}).json()["confirmed_at"] == confirmed["confirmed_at"]
        assert public.get(endpoint).json()["incident"]["review_status"] == "confirmed"
        assert public.get(incident["responder_path"]).status_code == 200
        started = time.monotonic()
        reset = client.post("/api/reset", json={})
        assert reset.status_code == 200
        assert time.monotonic() - started < 15
        assert reset.json()["incidents"] == []
        assert reset.json()["run"]["id"] != run_id
        assert public.get(endpoint).status_code == 410
        assert client.post(confirm, json={}).status_code == 409
        assert replay(client, run_id).status_code == 409
    assert len(set(run_ids)) == 5
    assert analyzer.calls == 5
    assert client.get("/api/state").json()["telemetry"]["network_inference_calls"] == 0


def test_concurrent_replay_is_reserved_once(services):
    client, _, analyzer, _, _ = services
    analyzer.release = threading.Event()
    run_id = client.get("/api/state").json()["run"]["id"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(replay, client, run_id)
        assert analyzer.started.wait(2)
        second = pool.submit(replay, client, run_id)
        assert second.result(timeout=2).status_code == 200
        analyzer.release.set()
        assert first.result(timeout=2).status_code == 200
    assert analyzer.calls == 1
    assert len(client.get("/api/state").json()["incidents"]) == 1


def test_reset_does_not_wait_for_analysis_or_accept_late_result(services):
    client, _, analyzer, _, _ = services
    analyzer.release = threading.Event()
    old = client.get("/api/state").json()["run"]["id"]
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(replay, client, old)
        assert analyzer.started.wait(2)
        started = time.monotonic()
        state = client.post("/api/reset", json={}).json()
        assert time.monotonic() - started < 2
        analyzer.release.set()
        assert pending.result(timeout=2).status_code == 409
    current = client.get("/api/state").json()
    assert current["run"]["id"] == state["run"]["id"]
    assert current["incidents"] == []
    assert current["analysis"]["status"] == "idle"


def test_restart_shares_run_instead_of_resetting(services):
    client, _, analyzer, data, dist = services
    incident = first_incident(client)
    with TestClient(create_app(data_dir=data, analysis_service=analyzer, web_dist=dist)) as restarted:
        state = restarted.get("/api/state").json()
        assert state["run"]["id"] == incident["run_id"]
        assert state["incidents"][0]["id"] == incident["id"]


def test_mode_change_requires_reset_and_cache_miss_stays_unavailable(services):
    client, _, _, _, _ = services
    incident = first_incident(client)
    assert replay(client, incident["run_id"], mode="cached").status_code == 409
    run_id = client.post("/api/reset", json={}).json()["run"]["id"]
    result = replay(client, run_id, mode="cached").json()
    assert result["analysis"]["mode"] == "unavailable"
    assert result["incidents"] == []


def test_control_does_not_claim_human_ground_truth(services):
    client, _, _, _, _ = services
    run_id = client.get("/api/state").json()["run"]["id"]
    state = replay(client, run_id, source_id="street-traffic").json()
    assert state["incidents"] == []
    assert "awaiting human labels" in state["analysis"]["message"]
    assert client.get("/api/evaluation").json()["status"] == "awaiting_labels"


def test_public_surface_is_scoped_and_read_only(services):
    client, public, _, _, _ = services
    incident = first_incident(client)
    for path in ("/api/state", "/api/config", "/api/sources", "/api/labels", "/api/evaluation", "/api/media/road-obstruction/video", "/api/live-cameras", "/api/live-cameras/example/snapshot", "/docs", "/openapi.json", "/", "/labels"):
        assert public.get(path).status_code == 404, path
    for path in ("/api/reset", f"/api/runs/{incident['run_id']}/incidents/{incident['id']}/confirm", "/api/labels"):
        assert public.post(path, json={}).status_code == 405
    assert public.get(f"/api/respond/{incident['run_id']}/{uuid4()}").status_code == 404
    assert public.get(f"/api/respond/{uuid4()}/{incident['id']}").status_code == 404
    assert public.get("/api/respond/not-a-uuid/also-invalid").status_code == 422


def test_media_is_allowlisted_supports_range_and_expires(services):
    client, public, _, data, _ = services
    media = data / "footage"
    media.mkdir()
    payload = b"synthetic-media-for-http-range-test" * 100
    (media / "road-obstruction-demo.mp4").write_bytes(payload)
    incident = first_incident(client)
    endpoint = f"/api/respond/{incident['run_id']}/{incident['id']}"
    source = public.get(endpoint).json()["source"]
    assert source["video_url"].startswith(endpoint)
    response = public.get(source["video_url"], headers={"Range": "bytes=0-31"})
    assert response.status_code == 206
    assert response.content == payload[:32]
    assert response.headers["content-range"] == f"bytes 0-31/{len(payload)}"
    assert response.headers["cache-control"] == "no-store"
    assert public.get(endpoint + "/media/arbitrary.json").status_code == 404
    assert client.get("/api/media/no-source/video").status_code == 404
    client.post("/api/reset", json={})
    assert public.get(source["video_url"]).status_code == 410


def test_missing_media_and_symlink_escape_are_not_exposed(services):
    client, _, _, data, _ = services
    assert client.get("/api/media/road-obstruction/video").status_code == 404
    assert client.get("/api/sources").json()["sources"][0]["media_available"] is False
    media = data / "footage"
    media.mkdir()
    target = data / "private-example.txt"
    target.write_text("must not serve")
    (media / "road-obstruction-demo.mp4").symlink_to(target)
    assert client.get("/api/media/road-obstruction/video").status_code == 404


def test_operator_host_origin_and_content_type_boundaries(services):
    client, _, _, _, _ = services
    assert client.post("/api/reset", json={}, headers={"Origin": "https://malicious.example"}).status_code == 403
    assert client.post("/api/reset", content="{}").status_code == 415
    assert client.get("/api/state", headers={"Host": "attacker.example"}).status_code == 403
    assert client.post("/api/reset", json={}, headers={"Origin": "http://localhost:5173"}).status_code == 200


def test_operator_map_referrer_and_responder_privacy(services):
    client, public, _, _, _ = services
    assert client.get("/").headers["referrer-policy"] == "strict-origin-when-cross-origin"
    incident = first_incident(client)
    assert public.get(incident["responder_path"]).headers["referrer-policy"] == "no-referrer"


def test_label_validation_and_human_submission(services):
    client, public, _, _, _ = services
    assert client.get("/api/labels").json() == {"labels": []}
    assert client.get("/api/evaluation").json()["metrics"] is None
    label = {"source_id": "road-obstruction", "start_seconds": 0, "end_seconds": 5, "label": "road_obstruction", "reviewer": "Test reviewer", "note": "Synthetic test of submission only"}
    response = client.post("/api/labels", json=label)
    assert response.status_code == 201
    assert client.get("/api/evaluation").json()["label_count"] == 1
    assert client.get("/api/evaluation").json()["metrics"] is None
    for changed in ({"end_seconds": 12}, {"start_seconds": 6}, {"reviewer": " "}, {"source_id": "unknown"}, {"label": "invented"}):
        assert client.post("/api/labels", json={**label, **changed}).status_code == 422
    assert public.get("/api/labels").status_code == 404


def test_bad_adapter_results_fail_closed_without_error_secrets(services):
    client, _, analyzer, _, _ = services
    analyzer.failure = True
    run_id = client.get("/api/state").json()["run"]["id"]
    response = replay(client, run_id)
    assert response.status_code == 200
    assert "secret-token" not in response.text
    assert response.json()["analysis"]["status"] == "unavailable"
    assert response.json()["incidents"] == []
    analyzer.failure = False
    analyzer.result_override = {**POSITIVE, "mode": "cached"}
    run_id = client.post("/api/reset", json={}).json()["run"]["id"]
    assert replay(client, run_id).json()["incidents"] == []


def test_public_base_url_validation(monkeypatch, tmp_path):
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://demo.example")
    with TestClient(create_app(data_dir=tmp_path, analysis_service=Analyzer())) as client:
        assert client.get("/api/config").json()["public_base_url"] == "https://demo.example"
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://secret:password@demo.example/?token=secret")
    with TestClient(create_app(data_dir=tmp_path, analysis_service=Analyzer())) as client:
        response = client.get("/api/config")
        assert response.json()["public_base_url"] is None
        assert "password" not in response.text
        assert "token=secret" not in response.text


def test_static_assets_do_not_escape_build_folder(services):
    client, public, _, _, dist = services
    assert public.get("/assets/app.js").status_code == 200
    private = dist / "private.txt"
    private.write_text("not an asset")
    (dist / "assets" / "linked.txt").symlink_to(private)
    assert public.get("/assets/linked.txt").status_code == 404
    assert public.get("/assets/%2e%2e/private.txt").status_code == 404
    assert client.get("/missing").status_code == 404
