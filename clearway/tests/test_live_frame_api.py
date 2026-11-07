"""The local frame endpoint stays bounded, rate limited, and operator-only."""
import hashlib

from fastapi.testclient import TestClient
import pytest

from api.app import create_app


class Cameras:
    def catalog(self):
        return {"cameras": [{"id": "caltrans-d4-53"}]}


class Detector:
    def __init__(self):
        self.calls = []

    def analyze_jpeg(self, raw):
        self.calls.append(raw)
        return {"image_sha256": hashlib.sha256(raw).hexdigest(), "status": "unavailable", "boxes": []}


@pytest.fixture
def service(tmp_path):
    detector = Detector()
    with TestClient(create_app(data_dir=tmp_path, live_camera_service=Cameras(), live_detection_service=detector)) as client:
        yield client, detector


URL = "/api/live-cameras/caltrans-d4-53/detect-frame"
JPEG_HEADERS = {"Content-Type": "image/jpeg"}


def test_exact_frame_bytes_rate_limit_and_no_incident_mutation(service):
    client, detector = service
    before = client.get("/api/state").json()
    frame = b"bounded-test-frame"
    response = client.post(URL, content=frame, headers=JPEG_HEADERS)
    assert response.status_code == 200
    assert response.json()["image_sha256"] == hashlib.sha256(frame).hexdigest()
    assert detector.calls == [frame]
    assert client.post(URL, content=frame, headers=JPEG_HEADERS).status_code == 429
    assert detector.calls == [frame]
    assert client.get("/api/state").json() == before


def test_unknown_camera_and_wrong_types_never_reach_detector(service):
    client, detector = service
    assert client.post("/api/live-cameras/unknown/detect-frame", content=b"x", headers=JPEG_HEADERS).status_code == 404
    assert client.post(URL, json={"image": "anything"}).status_code == 415
    assert client.post("/api/reset", content=b"x", headers=JPEG_HEADERS).status_code == 415
    assert detector.calls == []


@pytest.mark.parametrize("streamed", [False, True])
def test_oversized_or_chunked_upload_never_reaches_detector(service, streamed):
    client, detector = service
    content = iter([b"x" * 600_000, b"y" * 600_000]) if streamed else b"x" * 1_000_001
    assert client.post(URL, content=content, headers=JPEG_HEADERS).status_code == 413
    assert detector.calls == []


def test_cross_origin_and_public_responder_cannot_run_frame_inference(service, tmp_path):
    client, detector = service
    response = client.post(URL, content=b"x", headers={**JPEG_HEADERS, "Origin": "https://unrelated.example"})
    assert response.status_code == 403
    with TestClient(create_app(data_dir=tmp_path, read_only=True, live_camera_service=Cameras(), live_detection_service=detector)) as public:
        assert public.post(URL, content=b"x", headers=JPEG_HEADERS).status_code == 405
        assert public.get(URL).status_code == 404
    assert detector.calls == []
