"""Offline temporal-rule fixtures, not model accuracy or human labels."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from uuid import uuid4

import pytest

from api.live_monitor import LiveAlertMonitor, MAX_STREAMS, parse_monitor_headers
from api.store import Store
from test_live_detection import jpeg


CAMERA = {"id": "caltrans-d4-37", "name": "Test road camera", "latitude": 37.77, "longitude": -122.40}
CAR = {"class_name": "car", "confidence": 0.8, "xyxy": [0.2, 0.3, 0.35, 0.45]}
PERSON = {"class_name": "person", "confidence": 0.8, "xyxy": [0.5, 0.4, 0.55, 0.6]}


def detection(raw, camera_id=CAMERA["id"], boxes=None):
    digest = hashlib.sha256(raw).hexdigest()
    return {"schema_version": "clearway-live-detections-v1", "status": "available", "analysis_mode": "fresh",
            "camera_id": camera_id, "image_sha256": digest, "image_width": 640, "image_height": 480,
            "boxes": deepcopy([CAR] if boxes is None else boxes),
            "model": {"name": "offline-test-detector", "weights_sha256": "a" * 64},
            "provenance": {"kind": "local_yolo_image", "fixture": False, "image_sha256": digest,
                           "configuration_sha256": "b" * 64}, "inference_ms": 1.0}


@pytest.fixture
def setup(tmp_path):
    store = Store(tmp_path)
    ticks = [100.0]
    monitor = LiveAlertMonitor(store, monotonic=lambda: ticks[0], clock=lambda: datetime(2026, 11, 7, tzinfo=timezone.utc))
    run, stream = store.snapshot()["run"]["id"], str(uuid4())
    return store, monitor, ticks, run, stream


def sample(setup, second, *, wall=None, raw=None, boxes=None, camera=None, stream=None, mutate=None):
    store, monitor, ticks, run, default_stream = setup
    camera = camera or CAMERA
    ticks[0] = 100 + (second if wall is None else wall)
    raw = raw or jpeg(nonce=f"{camera['id']}:{second}:{stream or default_stream}".encode())
    result = detection(raw, camera["id"], boxes)
    if mutate:
        mutate(result)
    return monitor.observe(run, camera, stream or default_stream, second, raw, result)


def test_stationary_candidate_needs_both_duration_and_distinct_frame_count(setup):
    store, _, _, run, _ = setup
    for second in range(12):
        status = sample(setup, second)
        assert status["incident_id"] is None
    status = sample(setup, 12)
    assert status["phase"] == "candidate" and status["observed_seconds"] == 12
    incident = store.snapshot()["incidents"][0]
    assert incident["category"] == "possible_stationary_vehicle"
    assert incident["provenance"]["distinct_frames"] == 13
    assert incident["location"]["quality"] == "known_camera"
    assert incident["provenance"]["fixture"] is False
    assert incident["analysis_mode"] == "fresh" and incident["source_mode"] == "live"
    assert incident["live_source"]["duration_seconds"] == 0
    assert incident["live_source"]["media_available"] is False
    assert incident["live_source"]["poster_available"] is True
    assert "not object location" in incident["location"]["label"]
    image = store.evidence(run, incident["id"])
    assert hashlib.sha256(image).hexdigest() == incident["live_evidence"]["detections"]["image_sha256"]


def test_long_sparse_sequence_still_requires_twelve_frames(setup):
    for second in range(0, 22, 2):
        assert sample(setup, second)["incident_id"] is None
    assert sample(setup, 22)["phase"] == "candidate"


def test_person_is_visibility_only_and_needs_five_frames_and_three_seconds(setup):
    for second in (0, 1, 2, 3):
        assert sample(setup, second, boxes=[PERSON])["incident_id"] is None
    assert sample(setup, 3.5, boxes=[PERSON])["phase"] == "candidate"
    incident = setup[0].snapshot()["incidents"][0]
    assert incident["category"] == "sustained_person_visible"
    assert "danger" not in incident["title"].lower()
    assert "injury" in " ".join(incident["unknowns"])
    assert incident["live_evidence"]["window_seconds"] == 3.5


def test_moving_traffic_and_high_count_alone_do_not_alert(setup):
    for second in range(30):
        box = deepcopy(CAR)
        box["xyxy"] = [0.05 + second * .02, .3, .15 + second * .02, .4]
        assert sample(setup, second, boxes=[box])["incident_id"] is None
    dense = [{**deepcopy(CAR), "xyxy": [.001 * i, .2, .001 * i + .05, .3]} for i in range(100)]
    assert sample(setup, 30, boxes=dense)["incident_id"] is None
    assert sample(setup, 31, boxes=[])["phase"] == "watching"
    assert setup[0].snapshot()["incidents"] == []


@pytest.mark.parametrize("box", [
    {**CAR, "confidence": .49}, {**PERSON, "confidence": .54},
    {**CAR, "xyxy": [.1, .1, .11, .11]},
])
def test_weak_or_tiny_boxes_do_not_accumulate(setup, box):
    for second in range(15):
        assert sample(setup, second, boxes=[box])["phase"] == "watching"
    assert setup[0].snapshot()["incidents"] == []


@pytest.mark.parametrize("break_kind", ["missing", "unavailable", "fixture", "wrong_hash", "wrong_camera", "duplicate"])
def test_missing_or_non_genuine_or_duplicate_frame_breaks_continuity(setup, break_kind):
    for second in range(11):
        sample(setup, second)
    kwargs = {}
    if break_kind == "missing":
        kwargs["boxes"] = []
    elif break_kind == "unavailable":
        kwargs["mutate"] = lambda result: result.update(status="unavailable")
    elif break_kind == "fixture":
        kwargs["mutate"] = lambda result: result["provenance"].update(fixture=True)
    elif break_kind == "wrong_hash":
        kwargs["mutate"] = lambda result: result.update(image_sha256="c" * 64)
    elif break_kind == "wrong_camera":
        kwargs["mutate"] = lambda result: result.update(camera_id="caltrans-d4-689")
    else:
        kwargs["raw"] = jpeg(nonce=f"{CAMERA['id']}:10:{setup[4]}".encode())
    assert sample(setup, 11, **kwargs)["incident_id"] is None
    for second in range(12, 24):
        assert sample(setup, second)["incident_id"] is None
    assert sample(setup, 24)["phase"] == "candidate"


@pytest.mark.parametrize("media,wall", [(4, 11), (13, 13), (11, 10.1), (11, 13)])
def test_seek_gap_and_clock_discontinuity_restart_observation(setup, media, wall):
    for second in range(11):
        sample(setup, second)
    status = sample(setup, media, wall=wall)
    assert status["phase"] == "warming" and status["observed_seconds"] == 0
    assert status["incident_id"] is None and setup[0].snapshot()["incidents"] == []


def test_stream_switch_and_camera_switch_do_not_share_track_history(setup):
    for second in range(11):
        sample(setup, second)
    other_stream = str(uuid4())
    assert sample(setup, 11, stream=other_stream)["observed_seconds"] == 0
    assert sample(setup, 12)["observed_seconds"] == 0
    assert sample(setup, 13, camera={**CAMERA, "id": "caltrans-d4-689"})["observed_seconds"] == 0
    assert setup[0].snapshot()["incidents"] == []


def test_model_configuration_change_restarts_observation(setup):
    for second in range(11):
        sample(setup, second)
    result = sample(setup, 11, mutate=lambda d: d["provenance"].update(configuration_sha256="c" * 64))
    assert result["observed_seconds"] == 0 and result["incident_id"] is None


@pytest.mark.parametrize("action", ["confirm", "dismiss"])
def test_one_candidate_per_camera_even_after_review(setup, action):
    store, _, _, run, _ = setup
    for second in range(13):
        status = sample(setup, second)
    incident_id = status["incident_id"]
    reviewed = store.review(run, incident_id, action)
    again = sample(setup, 14, stream=str(uuid4()))
    assert again["incident_id"] == incident_id
    assert reviewed["review_status"] in again["message"]
    assert len(store.snapshot()["incidents"]) == 1
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM live_evidence").fetchone()[0] == 1


def test_max_twenty_images_and_bounded_stream_state(setup):
    store, monitor, _, _, _ = setup
    for index in range(21):
        camera = {**CAMERA, "id": f"caltrans-d4-{index}"}
        for second in range(13):
            status = sample(setup, second, wall=index * 20 + second, camera=camera)
        assert status["phase"] == ("candidate" if index < 20 else "unavailable")
    assert "20" in status["message"]
    assert len(store.snapshot()["incidents"]) == 20
    assert len(monitor._streams) <= MAX_STREAMS
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM live_evidence").fetchone()[0] == 20
    store.reset()
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM live_evidence").fetchone()[0] == 0


def test_atomic_current_run_check_rejects_reset_during_candidate_write(setup, monkeypatch):
    store, _, _, run, _ = setup
    for second in range(12):
        sample(setup, second)
    original = store.add_live_candidate
    def reset_before_insert(*args):
        store.reset()
        return original(*args)
    monkeypatch.setattr(store, "add_live_candidate", reset_before_insert)
    status = sample(setup, 12)
    assert status["phase"] == "unavailable" and status["incident_id"] is None
    assert store.snapshot()["run"]["id"] != run and store.snapshot()["incidents"] == []
    with store.connect() as db:
        assert db.execute("SELECT count(*) FROM live_evidence").fetchone()[0] == 0


def test_partial_bad_or_nonfinite_headers_cannot_enable_monitor():
    assert parse_monitor_headers({}) is None
    run, stream = str(uuid4()), str(uuid4())
    headers = {"x-clearway-run-id": run, "x-clearway-stream-id": stream, "x-clearway-media-time": "12.5"}
    assert parse_monitor_headers(headers) == (run, stream, 12.5)
    for bad in ({"x-clearway-run-id": run}, {**headers, "x-clearway-stream-id": "not-uuid"},
                *({**headers, "x-clearway-media-time": value} for value in ("nan", "inf", "-1", "1e1000"))):
        with pytest.raises(ValueError):
            parse_monitor_headers(bad)
