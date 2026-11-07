"""Full operator/responder lifecycle with explicitly injected offline boxes."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib
from types import SimpleNamespace
import threading
import time
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from api.app import create_app
from api.live_cameras import LiveCameraService
from api.live_monitor import LiveAlertMonitor
from api.store import Store
from test_live_cameras import NOW, catalog_file
from test_live_detection import jpeg
from test_live_monitor import CAR, PERSON, detection


CAMERA_ID = "caltrans-d4-37"
FRAME_URL = f"/api/live-cameras/{CAMERA_ID}/detect-frame"


class Detector:
    def __init__(self):
        self.boxes = [CAR]
        self.release = None
        self.entered = threading.Event()

    def analyze_jpeg(self, raw, camera_id=None, *, tracking=False):
        self.entered.set()
        if self.release:
            assert self.release.wait(3)
        result = detection(raw, camera_id, self.boxes)
        if tracking:
            result.update(confidence_threshold=0.3, tracking_candidates=list(self.boxes))
        return result


@pytest.fixture
def services(tmp_path, monkeypatch):
    ticks = [100.0]
    monkeypatch.setattr(importlib.import_module("api.app"), "time", SimpleNamespace(monotonic=lambda: ticks[0]))
    data = tmp_path / "data"
    store, detector = Store(data), Detector()
    monitor = LiveAlertMonitor(store, monotonic=lambda: ticks[0])
    cameras = LiveCameraService(catalog_file(tmp_path, count=40), detector=detector,
                                image_fetcher=lambda *_: (jpeg(), {}), clock=lambda: NOW)
    app = create_app(data_dir=data, live_camera_service=cameras, live_detection_service=detector, live_monitor_service=monitor)
    with TestClient(app) as local, TestClient(create_app(data_dir=data, read_only=True)) as public:
        yield SimpleNamespace(local=local, public=public, store=store, detector=detector, monitor=monitor,
                              ticks=ticks, run=store.snapshot()["run"]["id"], stream=str(uuid4()))


def send(services, second, *, monitored=True, headers=None):
    services.ticks[0] = 100 + second
    raw = jpeg(nonce=f"frame-{second}".encode())
    context = {"Content-Type": "image/jpeg"}
    if monitored:
        context.update({"X-Clearway-Run-ID": services.run, "X-Clearway-Stream-ID": services.stream,
                        "X-Clearway-Media-Time": str(second)})
    context.update(headers or {})
    response = services.local.post(FRAME_URL, headers=context, content=raw)
    assert response.status_code == 200, response.text
    assert response.json()["image_sha256"] == hashlib.sha256(raw).hexdigest()
    return response.json(), raw


@pytest.mark.parametrize("action", ["confirm", "dismiss"])
def test_live_candidate_review_scoped_exact_image_and_reset_expiry(services, action):
    for second in range(13):
        detection_result, trigger = send(services, second)
    monitor = detection_result["alert_monitor"]
    assert monitor["phase"] == "candidate"
    state = services.local.get("/api/state").json()
    assert len(state["incidents"]) == 1
    incident = state["incidents"][0]
    assert incident["id"] == monitor["incident_id"]
    assert incident["review_status"] == "candidate"
    assert incident["source_mode"] == "live" and incident["analysis_mode"] == "fresh"
    assert incident["source_id"] == CAMERA_ID
    assert incident["location"]["quality"] == "known_camera"
    assert incident["live_evidence"]["detections"]["image_sha256"] == hashlib.sha256(trigger).hexdigest()
    operator_image = services.local.get(incident["live_evidence"]["image_url"])
    assert operator_image.status_code == 200 and operator_image.content == trigger
    assert operator_image.headers["content-type"] == "image/jpeg"
    assert operator_image.headers["cache-control"] == "no-store"
    path = f"/api/respond/{services.run}/{incident['id']}"
    brief = services.public.get(path).json()
    assert brief["source"]["source_mode"] == "live"
    assert brief["source"]["video_url"] == "" and brief["source"]["duration_seconds"] == 0
    image_url = path + "/media/evidence"
    assert brief["source"]["poster_url"] == brief["incident"]["live_evidence"]["image_url"] == image_url
    assert services.public.get(image_url).content == trigger
    assert services.public.get(path + "/media/video").status_code == 404
    assert services.public.get(path + "/media/arbitrary").status_code == 404
    assert services.public.get(f"/api/respond/{services.run}/{uuid4()}/media/evidence").status_code == 404
    assert services.public.get(f"/api/respond/{uuid4()}/{incident['id']}/media/evidence").status_code == 404
    review_url = f"/api/runs/{services.run}/incidents/{incident['id']}/{action}"
    reviewed = services.local.post(review_url, json={})
    assert reviewed.status_code == 200
    expected = "confirmed" if action == "confirm" else "dismissed"
    assert reviewed.json()["review_status"] == expected
    assert services.local.post(review_url, json={}).json() == reviewed.json()
    assert services.public.get(path).json()["incident"]["review_status"] == expected
    again, _ = send(services, 14)
    assert again["alert_monitor"]["incident_id"] == incident["id"]
    assert expected in again["alert_monitor"]["message"]
    assert len(services.local.get("/api/state").json()["incidents"]) == 1
    reset = services.local.post("/api/reset", json={}).json()
    assert reset["run"]["id"] != services.run and reset["incidents"] == []
    assert services.monitor._streams == {}
    assert services.public.get(path).status_code == services.public.get(image_url).status_code == 410
    assert services.local.get(incident["live_evidence"]["image_url"]).status_code == 409
    with services.store.connect() as db:
        assert db.execute("SELECT count(*) FROM live_evidence").fetchone()[0] == 0
    stale, _ = send(services, 15)
    assert stale["status"] == "available" and stale["alert_monitor"]["phase"] == "unavailable"
    assert services.local.get("/api/state").json()["incidents"] == []


def test_sustained_person_goes_through_same_review_flow(services):
    services.detector.boxes = [PERSON]
    for second in (0, .6, 1.2, 1.8, 2.4, 3):
        result, _ = send(services, second)
    assert result["alert_monitor"]["phase"] == "candidate"
    incident = services.local.get("/api/state").json()["incidents"][0]
    assert incident["category"] == "sustained_person_visible"
    assert "injury" in " ".join(incident["unknowns"])
    assert "danger" not in incident["title"].lower()


def test_paused_alerts_keep_tracking_context_but_break_alert_observation(services):
    calls = []
    class Tracker:
        def process(self, context, result):
            calls.append((context, result))
            return {"status": "available", "algorithm": "ByteTrack", "tracks": []}
    # The route's injected service is used, so spy on that instance.
    tracker = services.local.app.state.live_tracking_service
    original = tracker.process
    tracker.process = Tracker().process
    try:
        for second in range(12):
            send(services, second)
        paused, _ = send(services, 12, headers={"X-Clearway-Alert-Monitor": "paused"})
        assert paused["tracking"]["status"] == "available"
        assert paused["alert_monitor"]["phase"] == "paused"
        assert services.monitor._streams == {}
        assert "tracking_candidates" not in paused
        assert calls[-1][0] == {"run_id": services.run, "camera_id": CAMERA_ID,
                                "stream_id": services.stream, "media_time_seconds": 12.0}
        assert calls[-1][1]["tracking_candidates"] == [CAR]
        resumed, _ = send(services, 13)
        assert resumed["alert_monitor"]["observed_seconds"] == 0
        assert services.store.snapshot()["incidents"] == []
    finally:
        tracker.process = original


def test_recovered_low_boxes_never_enter_incident_monitor_or_evidence(services):
    services.detector.boxes = []
    detector = services.detector.analyze_jpeg
    def candidates_only(raw, camera_id=None, *, tracking=False):
        result = detector(raw, camera_id, tracking=tracking)
        result["tracking_candidates"] = [{**CAR, "confidence": .2}]
        return result
    services.detector.analyze_jpeg = candidates_only
    for second in range(14):
        result, _ = send(services, second)
        assert result["boxes"] == []
        assert "tracking_candidates" not in result
    assert services.store.snapshot()["incidents"] == []
    assert result["alert_monitor"]["observed_seconds"] == 0


def test_no_header_frames_and_real_snapshot_route_never_create_candidates(services):
    for second in range(20):
        result, _ = send(services, second, monitored=False)
        assert "alert_monitor" not in result
        snapshot = services.local.get(f"/api/live-cameras/{CAMERA_ID}/snapshot").json()
        assert snapshot["status"] == "available" and snapshot["detections"]["status"] == "available"
    assert services.local.get("/api/state").json()["incidents"] == []
    with services.store.connect() as db:
        assert db.execute("SELECT count(*) FROM live_evidence").fetchone()[0] == 0


def test_bad_monitor_headers_or_monitor_failure_preserve_detection_overlay(services, monkeypatch):
    partial, _ = send(services, 0, monitored=False, headers={"X-Clearway-Run-ID": services.run})
    assert partial["status"] == "available" and partial["boxes"] == [CAR]
    assert partial["alert_monitor"]["phase"] == "unavailable"
    def fail(*_args):
        raise RuntimeError("private-native-detail-not-returned")
    monkeypatch.setattr(services.monitor, "observe", fail)
    result, _ = send(services, 1)
    assert result["status"] == "available" and result["boxes"] == [CAR]
    assert result["alert_monitor"]["phase"] == "unavailable"
    assert "private-native" not in str(result)


def test_reset_while_frame_inference_is_pending_cannot_write_old_candidate(services):
    for second in range(12):
        send(services, second)
    services.detector.entered.clear()
    services.detector.release = threading.Event()
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(send, services, 12)
        assert services.detector.entered.wait(1)
        started = time.monotonic()
        reset = services.local.post("/api/reset", json={})
        assert reset.status_code == 200 and time.monotonic() - started < 1
        services.detector.release.set()
        result, _ = pending.result(timeout=3)
    assert result["status"] == "available" and result["alert_monitor"]["phase"] == "unavailable"
    assert services.local.get("/api/state").json()["incidents"] == []


def test_live_monitor_and_operator_images_are_not_public_routes(services):
    for path in ("/api/live-cameras", FRAME_URL, "/api/live-monitor", "/api/state", "/api/config",
                 f"/api/runs/{services.run}/incidents/{uuid4()}/evidence"):
        assert services.public.get(path).status_code == 404
    assert services.public.post(FRAME_URL, headers={"Content-Type": "image/jpeg"}, content=jpeg()).status_code == 405
