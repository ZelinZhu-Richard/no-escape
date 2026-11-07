from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.message import Message
import hashlib
import json
from pathlib import Path

import pytest

from api import live_cameras
from api.live_cameras import LiveCameraService, normalize_catalog, valid_provider_url

NOW = datetime(2026, 11, 7, 17, 15, tzinfo=timezone.utc)
JPEG = b"\xff\xd8\xffsynthetic-jpeg-for-transport-tests\xff\xd9"
URL = "https://cwwp2.dot.ca.gov/data/d4/cctv/image/test/test.jpg"


def raw_record(index=1):
    return {"cctv": {
        "index": str(index), "recordTimestamp": {"recordDate": "2010-01-01"},
        "location": {"district": "4", "locationName": f"Camera {index}", "nearbyPlace": "San Francisco", "latitude": "37.8", "longitude": "-122.4", "county": "San Francisco", "route": "I-80", "direction": "East"},
        "inService": "true", "imageData": {"streamingVideoURL": "https://wzmedia.dot.ca.gov/D4/example.stream/playlist.m3u8", "static": {"currentImageURL": URL, "currentImageUpdateFrequency": "5"}},
    }}


def catalog_file(tmp_path, count=35):
    catalog = normalize_catalog({"data": [raw_record(i) for i in range(1, count+1)]}, NOW.isoformat())
    path = tmp_path / "live.json"
    path.write_text(json.dumps(catalog))
    return path


class Time:
    ticks = 1000.0

    def now(self):
        return NOW + timedelta(seconds=self.ticks-1000)


def test_catalog_is_authentic_location_metadata_not_live_frame_time(tmp_path):
    service = LiveCameraService(catalog_file(tmp_path), clock=lambda: NOW, image_fetcher=lambda *_: pytest.fail("Catalog must never fetch imagery"))
    catalog = service.catalog()
    assert catalog["status"] == "available" and len(catalog["cameras"]) == 35
    camera = catalog["cameras"][0]
    assert camera["source_refresh_seconds"] == 300  # Official source field is minutes.
    assert camera["capture_time"] is None
    assert camera["mode"] == "refreshed_snapshot"
    assert "image_url" not in camera
    assert camera["latitude"] == 37.8
    assert catalog["regions"] == [{"id": "san-francisco", "name": "San Francisco"}]


@pytest.mark.parametrize("url", [
    "http://cwwp2.dot.ca.gov/data/d4/cctv/image/test/test.jpg",
    "https://cwwp2.dot.ca.gov.attacker.test/data/d4/cctv/image/test/test.jpg",
    "https://127.0.0.1/data/d4/cctv/image/test/test.jpg",
    "https://user@cwwp2.dot.ca.gov/data/d4/cctv/image/test/test.jpg",
    "https://cwwp2.dot.ca.gov:443/data/d4/cctv/image/test/test.jpg",
    "https://cwwp2.dot.ca.gov/data/d4/cctv/image/test/../secret.jpg",
    "https://cwwp2.dot.ca.gov/data/d4/cctv/image/test/test.jpg?redirect=https://example.com",
    "https://cwwp2.dot.ca.gov/data/d4/cctv/image/test/previous/test.jpg",
    "https://cwwp2.dot.ca.gov/data/d4/cctv/image/test/test.jpg#fragment",
])
def test_arbitrary_urls_and_archives_are_not_allowed(url):
    assert valid_provider_url(url) is False


def test_only_selected_image_fetched_once_under_concurrency(tmp_path):
    calls = []
    def fetch(url):
        calls.append(url)
        return JPEG, {"Last-Modified": "Sat, 07 Nov 2026 17:14:00 GMT"}
    service = LiveCameraService(catalog_file(tmp_path), image_fetcher=fetch, clock=lambda: NOW)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(service.snapshot, ["caltrans-d4-1"]*4))
    assert calls == [URL]
    assert all(result["status"] == "available" and not result["stale"] for result in results)
    assert results[0]["capture_time"] is None
    assert results[0]["source_last_modified"] == "2026-11-07T17:14:00+00:00"


def test_failure_keeps_previous_image_explicitly_stale_and_backs_off(tmp_path):
    clock = Time()
    calls = []
    def fetch(url):
        calls.append(url)
        if len(calls) > 1:
            raise RuntimeError("upstream-secret-must-not-reflect")
        return JPEG, {}
    service = LiveCameraService(catalog_file(tmp_path), image_fetcher=fetch, clock=clock.now, monotonic=lambda: clock.ticks)
    first = service.snapshot("caltrans-d4-1")
    clock.ticks += 301
    failed = service.snapshot("caltrans-d4-1")
    assert failed["status"] == "unavailable" and failed["stale"] is True
    assert failed["image_data_url"] == first["image_data_url"]
    assert failed["fetched_at"] == first["fetched_at"]
    assert "secret" not in json.dumps(failed)
    assert service.snapshot("caltrans-d4-1")["status"] == "unavailable"
    assert len(calls) == 2


def test_old_source_metadata_is_not_presented_as_fresh(tmp_path):
    service = LiveCameraService(catalog_file(tmp_path), image_fetcher=lambda *_: (JPEG, {"Last-Modified": "Fri, 06 Nov 2026 17:14:00 GMT"}), clock=lambda: NOW)
    result = service.snapshot("caltrans-d4-1")
    assert result["stale"] is True
    assert "may be stale" in result["message"]


def test_invalid_source_and_unknown_id_never_make_request(tmp_path):
    path = catalog_file(tmp_path)
    service = LiveCameraService(path, image_fetcher=lambda *_: pytest.fail("unexpected fetch"), clock=lambda: NOW)
    assert service.snapshot("../../etc/passwd")["status"] == "unavailable"
    assert service.snapshot("caltrans-d4-999999")["status"] == "unavailable"
    content = json.loads(path.read_text())
    content["cameras"][0]["image_url"] = "http://127.0.0.1/private"
    path.write_text(json.dumps(content))
    assert service.catalog()["status"] == "unavailable"
    assert service.snapshot(content["cameras"][0]["id"])["status"] == "unavailable"


def test_rate_limit_and_bounded_memory_prevent_fleet_polling(tmp_path):
    clock = Time()
    calls = []
    service = LiveCameraService(catalog_file(tmp_path), image_fetcher=lambda url: (calls.append(url) or JPEG, {}), clock=clock.now, monotonic=lambda: clock.ticks)
    assert service.snapshot("caltrans-d4-1")["status"] == "available"
    assert service.snapshot("caltrans-d4-2")["status"] == "throttled"
    for i in range(2, 21):
        clock.ticks += 2
        assert service.snapshot(f"caltrans-d4-{i}")["status"] == "available"
    clock.ticks += 2
    assert service.snapshot("caltrans-d4-21")["status"] == "throttled"
    assert len(calls) == 20 and len(service._cache) == 4


def test_image_eviction_cannot_bypass_published_refresh_cadence(tmp_path):
    clock = Time()
    calls = []
    service = LiveCameraService(catalog_file(tmp_path), image_fetcher=lambda url: (calls.append(url) or JPEG, {}), clock=clock.now, monotonic=lambda: clock.ticks)
    for i in range(1, 6):
        assert service.snapshot(f"caltrans-d4-{i}")["status"] == "available"
        clock.ticks += 2
    assert "caltrans-d4-1" not in service._cache
    again = service.snapshot("caltrans-d4-1")
    assert again["status"] == "throttled"
    assert again["refresh_after_seconds"] == 290
    assert again["image_data_url"] is None
    assert len(calls) == 5


class Response:
    status = 200

    def __init__(self, raw=JPEG, content_type="image/jpeg", content_length=None):
        self.raw = raw
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if content_length is not None:
            self.headers["Content-Length"] = content_length

    def read(self, size):
        return self.raw[:size]

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass


@pytest.mark.parametrize("response", [Response(content_type="text/html"), Response(raw=b"<html>offline</html>"), Response(content_length="1000001"), Response(raw=b"x"*1_000_001)])
def test_transport_rejects_wrong_content_and_oversized_body(monkeypatch, response):
    class Opener:
        def open(self, request, timeout):
            assert timeout == 10
            return response
    monkeypatch.setattr(live_cameras.urllib.request, "build_opener", lambda *_: Opener())
    with pytest.raises(ValueError):
        live_cameras.fetch_image(URL)


def test_transport_disables_redirects_and_unknown_targets():
    assert live_cameras._NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://127.0.0.1/") is None
    with pytest.raises(ValueError):
        live_cameras.fetch_image("https://example.com/camera.jpg")


def test_source_record_timestamp_never_becomes_image_capture_time_and_limit():
    result = normalize_catalog({"data": [raw_record(i) for i in range(1, 130)]}, NOW.isoformat())
    assert len(result["cameras"]) == 100
    assert all(camera["capture_time"] is None for camera in result["cameras"])


def test_catalog_becomes_stale_without_silent_refresh(tmp_path):
    service = LiveCameraService(catalog_file(tmp_path), clock=lambda: NOW+timedelta(days=2))
    assert service.catalog()["stale"] is True


def test_detector_receives_exact_snapshot_once_and_cache_preserves_hash(tmp_path):
    calls = []
    class Detector:
        def analyze_jpeg(self, raw):
            calls.append(raw)
            return {"status": "available", "analysis_mode": "fresh", "image_sha256": hashlib.sha256(raw).hexdigest(), "boxes": [], "vehicle_count": 0, "person_count": 0}
    service = LiveCameraService(catalog_file(tmp_path), detector=Detector(), image_fetcher=lambda *_: (JPEG, {}), clock=lambda: NOW)
    fresh = service.snapshot("caltrans-d4-1")
    cached = service.snapshot("caltrans-d4-1")
    assert calls == [JPEG]
    assert fresh["image_sha256"] == fresh["detections"]["image_sha256"] == hashlib.sha256(JPEG).hexdigest()
    assert fresh["detections"]["analysis_mode"] == "fresh"
    assert cached["detections"]["analysis_mode"] == "cached"
    assert cached["image_sha256"] == fresh["image_sha256"]


@pytest.mark.parametrize("failure", ["raise", "mismatch"])
def test_failed_or_mismatched_detection_never_breaks_image_or_substitutes_boxes(tmp_path, failure):
    class Detector:
        def analyze_jpeg(self, raw):
            if failure == "raise":
                raise RuntimeError("private-provider-error")
            return {"status": "available", "image_sha256": "wrong-image", "boxes": [{"class_name": "person"}]}
    service = LiveCameraService(catalog_file(tmp_path), detector=Detector(), image_fetcher=lambda *_: (JPEG, {}), clock=lambda: NOW)
    result = service.snapshot("caltrans-d4-1")
    assert result["status"] == "available"
    assert result["detections"]["status"] == "unavailable"
    assert "boxes" not in result["detections"]
    assert "private" not in json.dumps(result)


def test_camera_allowlist_lookup_is_offline(tmp_path):
    service = LiveCameraService(catalog_file(tmp_path), image_fetcher=lambda *_: pytest.fail("unexpected network"), clock=lambda: NOW)
    assert service.camera_exists("caltrans-d4-1") is True
    assert service.camera_exists("caltrans-d4-9999") is False
    assert service.camera_exists("https://example.com/camera") is False
