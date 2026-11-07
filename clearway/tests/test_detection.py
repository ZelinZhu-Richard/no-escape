import json

import pytest

from api.detection import (
    CONFIDENCE, MODEL_NAME, MODEL_SHA256, MODEL_VERSION, NMS_IOU,
    PREPROCESSING_VERSION, SCHEMA_VERSION, DetectionService, sha256_file,
    shadow_gate, validate_report,
)


def frame(time, vehicles=0, people=0):
    boxes = ([{"class_name": "car", "confidence": 0.8, "xyxy": [0.1, 0.2, 0.3, 0.4]}] * vehicles
             + [{"class_name": "person", "confidence": 0.7, "xyxy": [0.5, 0.2, 0.6, 0.7]}] * people)
    return {"time_seconds": time, "vehicle_count": vehicles, "person_count": people, "boxes": boxes}


def report(source_sha="test-sha"):
    frames = [frame(index / 4, vehicles=int(index >= 8), people=int(index >= 16)) for index in range(24)]
    return {
        "schema_version": SCHEMA_VERSION, "status": "available", "source_id": "road-obstruction",
        "model": {"name": MODEL_NAME, "version": MODEL_VERSION, "weights_sha256": MODEL_SHA256},
        "provenance": {"kind": "local_yolo_cached", "fixture": False, "source_sha256": source_sha,
                       "preprocessing_version": PREPROCESSING_VERSION},
        "confidence_threshold": CONFIDENCE, "nms_iou": NMS_IOU,
        "sample_fps": 4, "duration_seconds": 6, "video_width": 1920, "video_height": 1080,
        "frames": frames, "gate": shadow_gate(frames, 6),
    }


def test_gate_counts_every_window_and_does_not_claim_paid_savings():
    gate = shadow_gate([frame(0, 3), frame(2, 3), frame(4, 3), frame(6, 5), frame(8, 5), frame(10, 5)], 12)
    assert gate["evaluated_windows"] == 6
    assert gate["passed_windows"] == 3  # first, changed, heartbeat
    assert gate["estimated_calls_avoided"] == gate["suppressed_windows"] == 3
    assert gate["actual_model_calls"] == 0
    assert gate["mode"] == "shadow"
    assert "Hypothetical" in gate["note"]


def test_gate_passes_a_person_despite_stable_vehicle_count():
    gate = shadow_gate([frame(0, 2), frame(2, 2, 1)], 4)
    assert gate["passed_windows"] == 2
    assert gate["windows"][1]["reason"] == "person present; review context"


def test_empty_windows_are_not_counted_as_saved_calls():
    gate = shadow_gate([frame(0)], 6)
    assert gate["evaluated_windows"] == 1
    assert gate["estimated_calls_avoided"] == 0


@pytest.mark.parametrize("mutation", [
    lambda r: r["provenance"].update(fixture=True),
    lambda r: r["provenance"].update(source_sha256="wrong"),
    lambda r: r["model"].update(weights_sha256="wrong"),
    lambda r: r["gate"].update(estimated_calls_avoided=999),
    lambda r: r["frames"][8]["boxes"][0].update(xyxy=[0.8, 0.2, 0.3, 0.4]),
    lambda r: r["frames"][8]["boxes"][0].update(confidence=float("nan")),
    lambda r: r["frames"][1].update(vehicle_count=900),
    lambda r: r["frames"][1].update(time_seconds=0),
    lambda r: r.update(confidence_threshold=0.1),
    lambda r: r.update(frames=r["frames"][:3]),
])
def test_malformed_and_fixture_outputs_never_overlay_real_video(mutation):
    result = report()
    mutation(result)
    assert not validate_report(result, "road-obstruction", "test-sha")


def test_valid_report_can_be_served_without_detector_runtime(tmp_path, monkeypatch):
    footage = tmp_path / "footage"
    footage.mkdir()
    media = footage / "road-obstruction-demo.mp4"
    media.write_bytes(b"local test source identity")
    cache = tmp_path / "detections"
    cache.mkdir()
    expected = report(sha256_file(media))
    (cache / "road-obstruction.json").write_text(json.dumps(expected))
    service = DetectionService(tmp_path)
    assert service.get("road-obstruction") == expected
    media.write_bytes(b"replaced footage")
    assert service.get("road-obstruction")["status"] == "unavailable"


def test_cache_miss_and_unknown_source_do_not_fetch_model(tmp_path, monkeypatch):
    def network_forbidden(*args, **kwargs):
        raise AssertionError("Read-only overlay serving must not download or infer")
    monkeypatch.setattr("urllib.request.urlopen", network_forbidden)
    service = DetectionService(tmp_path)
    assert service.get("road-obstruction")["status"] == "unavailable"
    assert service.get("../../unknown")["status"] == "unavailable"


def test_symlink_cache_is_not_read(tmp_path):
    footage = tmp_path / "footage"
    footage.mkdir()
    (footage / "road-obstruction-demo.mp4").write_bytes(b"source")
    cache = tmp_path / "detections"
    cache.mkdir()
    other = tmp_path / "other.json"
    other.write_text(json.dumps(report()))
    (cache / "road-obstruction.json").symlink_to(other)
    assert DetectionService(tmp_path).get("road-obstruction")["status"] == "unavailable"


def test_yolo_grid_decode_uses_class_scores_and_suppresses_duplicate_vehicle_boxes():
    np = pytest.importorskip("numpy")
    cv2 = pytest.importorskip("cv2")
    from api.detection import YoloDetector

    detector = YoloDetector.__new__(YoloDetector)
    detector.np, detector.cv2, detector.input_name = np, cv2, "images"
    # Three synthetic output rows at stride eight: two overlapping vehicles and
    # one non-target class. These are tensor-level test fixtures, never real cache.
    detector.grids = np.array([[0, 0], [1, 0], [2, 0]])
    detector.strides = np.full((3, 1), 8)
    rows = np.zeros((1, 3, 85), dtype=np.float32)
    rows[0, :, 0] = [26, 25, 24]
    rows[0, :, 1] = 26
    rows[0, :, 2:4] = np.log(100 / 8)
    rows[0, :, 4] = 0.9
    rows[0, 0, 5 + 2] = 0.9  # car, confidence .81
    rows[0, 0, 5 + 5] = 0.8  # bus score on same anchor must not become another box
    rows[0, 1, 5 + 7] = 0.8  # overlapping truck suppressed by class-agnostic NMS
    rows[0, 2, 5 + 16] = 0.99  # dog: not one of the supported displayed classes
    rows[0, 2, 5 + 2] = 0.8

    class Session:
        def run(self, _, payload):
            assert payload["images"].shape == (1, 3, 416, 416)
            return [rows]

    detector.session = Session()
    boxes = detector.detect(np.zeros((400, 400, 3), dtype=np.uint8))
    assert len(boxes) == 1
    assert boxes[0]["class_name"] == "car"
    assert boxes[0]["confidence"] == pytest.approx(0.81)
    assert boxes[0]["xyxy"] == pytest.approx([158 / 416, 158 / 416, 258 / 416, 258 / 416], abs=1e-6)
