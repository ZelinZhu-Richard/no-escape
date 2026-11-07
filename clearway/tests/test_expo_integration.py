"""Integration boundaries for local detections, person review, and tunnel URLs."""
from datetime import datetime, timedelta, timezone
import json
import os

from fastapi.testclient import TestClient
import pytest

from api.app import create_app
from api.analysis import AnalysisService, FIXTURES


def test_public_camera_browsing_never_changes_replay_or_invokes_inference(tmp_path):
    class Cameras:
        calls = []

        def catalog(self):
            return {"status": "available", "cameras": [{"id": "camera-1"}]}

        def snapshot(self, camera_id):
            self.calls.append(camera_id)
            return {"status": "unavailable", "message": "Provider temporarily unavailable."}

    cameras = Cameras()
    with TestClient(create_app(data_dir=tmp_path, live_camera_service=cameras)) as client:
        before = client.get("/api/state").json()
        assert client.get("/api/live-cameras").json()["status"] == "available"
        response = client.get("/api/live-cameras/camera-1/snapshot")
        assert response.status_code == 200
        assert response.json()["status"] == "unavailable"
        assert client.get("/api/state").json() == before
        assert cameras.calls == ["camera-1"]
    with TestClient(create_app(data_dir=tmp_path, read_only=True, live_camera_service=cameras)) as public:
        assert public.get("/api/live-cameras").status_code == 404
        assert public.get("/api/live-cameras/camera-1/snapshot").status_code == 404
        assert cameras.calls == ["camera-1"]


def test_detection_read_is_local_and_not_on_public_surface(tmp_path):
    class Detector:
        calls = []

        def get(self, source_id):
            self.calls.append(source_id)
            return {"status": "unavailable", "frames": [], "gate": None}

    detector = Detector()
    with TestClient(create_app(data_dir=tmp_path, detection_service=detector)) as client:
        response = client.get("/api/sources/person-roadway/detections")
        assert response.status_code == 200
        assert response.json()["status"] == "unavailable"
        assert client.get("/api/sources/unknown/detections").status_code == 404
        assert detector.calls == ["person-roadway"]
        assert client.get("/api/state").json()["telemetry"]["network_inference_calls"] == 0
    with TestClient(create_app(data_dir=tmp_path, read_only=True)) as public:
        assert public.get("/api/sources/person-roadway/detections").status_code == 404
        assert public.get("/api/camera-context").status_code == 404


def test_tunnel_url_changes_without_restart_and_stale_origin_disappears(tmp_path, monkeypatch):
    monkeypatch.delenv("PUBLIC_BASE_URL", raising=False)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    path = runtime / "tunnel.json"
    record = {"active": True, "pid": os.getpid(), "public_base_url": "https://one.example",
              "updated_at": datetime.now(timezone.utc).isoformat()}
    with TestClient(create_app(data_dir=tmp_path)) as client:
        assert client.get("/api/config").json()["public_base_url"] is None
        path.write_text(json.dumps(record))
        assert client.get("/api/config").json()["public_base_url"] == "https://one.example"
        with monkeypatch.context() as restricted:
            def denied_signal(*args):
                raise PermissionError("Sibling process probes are sandboxed")
            restricted.setattr(os, "kill", denied_signal)
            assert client.get("/api/config").json()["public_base_url"] == "https://one.example"
        path.write_text(json.dumps({**record, "public_base_url": "https://two.example"}))
        assert client.get("/api/config").json()["public_base_url"] == "https://two.example"
        path.write_text(json.dumps({**record, "updated_at": (datetime.now(timezone.utc) - timedelta(seconds=16)).isoformat()}))
        assert client.get("/api/config").json()["public_base_url"] is None
        path.write_text(json.dumps({**record, "active": False}))
        assert client.get("/api/config").json()["public_base_url"] is None
        path.write_text(json.dumps({**record, "public_base_url": "https://secret:password@bad.example/?key=private"}))
        response = client.get("/api/config")
        assert response.json()["public_base_url"] is None
        assert "password" not in response.text and "private" not in response.text


def test_person_fixture_preserves_review_unknowns_and_expires_handoff(tmp_path):
    with TestClient(create_app(data_dir=tmp_path)) as client, TestClient(create_app(data_dir=tmp_path, read_only=True)) as public:
        run = client.get("/api/state").json()["run"]["id"]
        response = client.post(f"/api/runs/{run}/replay", json={"source_id": "person-roadway", "analysis_mode": "fixture"})
        assert response.status_code == 200
        incident = response.json()["incidents"][0]
        assert incident["category"] == "person_in_roadway"
        assert incident["provenance"]["fixture"] is True
        assert incident["review_status"] == "candidate"
        assert "No person down" in " ".join(incident["unknowns"])
        endpoint = f"/api/respond/{run}/{incident['id']}"
        assert public.get(endpoint).json()["source"]["id"] == "person-roadway"
        client.post("/api/reset", json={})
        assert public.get(endpoint).status_code == 410
        assert client.get("/api/evaluation").json()["label_count"] == 0


def test_person_response_cannot_cite_an_unsupplied_frame(tmp_path):
    service = AnalysisService(tmp_path)
    payload = FIXTURES["person-roadway"]
    assert service._validate_response(payload, (3., 4., 5.))["category"] == "person_in_roadway"
    with pytest.raises(ValueError, match="outside the supplied sample"):
        service._validate_response(payload, (1., 4., 8.))
