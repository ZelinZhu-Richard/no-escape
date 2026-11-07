import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

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


def traffic_report(source_sha="test-sha"):
    from api.detection import replay_profile
    profile = replay_profile("traffic-jam")
    result = report(source_sha)
    result.update(source_id="traffic-jam", model=profile.metadata("test-runtime"),
                  confidence_threshold=profile.confidence, nms_iou=profile.nms_iou)
    result["provenance"]["preprocessing_version"] = profile.preprocessing_version
    for item in result["frames"]:
        for box in item["boxes"]:
            if box["class_name"] == "car":
                box.update(class_name="van", native_class_name="van")
    return result


def test_dense_traffic_requires_traffic_model_while_other_replays_keep_tiny():
    from api.detection import replay_profile
    assert replay_profile("traffic-jam").id == "yolo11s-visdrone640"
    for source in ("road-obstruction", "street-traffic", "person-roadway"):
        assert replay_profile(source) is None
        tiny = report()
        tiny["source_id"] = source
        assert validate_report(tiny, source, "test-sha")
    tiny = report()
    tiny["source_id"] = "traffic-jam"
    assert not validate_report(tiny, "traffic-jam", "test-sha")
    traffic = traffic_report()
    assert validate_report(traffic, "traffic-jam", "test-sha")
    traffic["source_id"] = "road-obstruction"
    assert not validate_report(traffic, "road-obstruction", "test-sha")


@pytest.mark.parametrize("mutation", [
    lambda r: r["model"].update(weights_sha256=MODEL_SHA256),
    lambda r: r["model"].update(profile="yolox-m640"),
    lambda r: r["model"].update(license="Apache-2.0"),
    lambda r: r["model"].update(input_size=[416, 416]),
    lambda r: r["provenance"].update(preprocessing_version=PREPROCESSING_VERSION),
    lambda r: r.update(confidence_threshold=.3),
    lambda r: r["frames"][8]["boxes"][0].update(confidence=.39),
    lambda r: r["frames"][8]["boxes"][0].update(native_class_name="pedestrian"),
])
def test_dense_cache_is_bound_to_actual_profile_license_preprocessing_and_classes(mutation):
    result = traffic_report()
    mutation(result)
    assert not validate_report(result, "traffic-jam", "test-sha")


def test_dense_cache_counts_all_vehicle_classes_and_remains_source_hash_bound(tmp_path):
    footage, cache = tmp_path / "footage", tmp_path / "detections"
    footage.mkdir()
    cache.mkdir()
    video = footage / "traffic-jam.webm"
    video.write_bytes(b"offline-test-source")
    result = traffic_report(sha256_file(video))
    for name in ("tricycle", "awning-tricycle"):
        result["frames"][0]["boxes"].append({"class_name": name, "native_class_name": name, "confidence": .8, "xyxy": [.1, .1, .2, .2]})
    result["frames"][0]["vehicle_count"] = 2
    result["gate"] = shadow_gate(result["frames"], result["duration_seconds"])
    (cache / "traffic-jam.json").write_text(json.dumps(result))
    service = DetectionService(tmp_path)
    assert service.get("traffic-jam") == result
    video.write_bytes(b"different-source")
    assert service.get("traffic-jam")["status"] == "unavailable"


def test_dense_preparation_uses_installed_traffic_model_and_records_actual_provenance(tmp_path, monkeypatch):
    from api import detection
    footage = tmp_path / "footage"
    footage.mkdir()
    video = footage / "traffic-jam.webm"
    video.write_bytes(b"offline-preparation-test")
    calls = []
    class Capture:
        index = -1
        def read(self):
            self.index += 1
            return (self.index < 2, object())
        def get(self, _property):
            return self.index * 250
        def release(self):
            pass
    class Traffic:
        runtime_version = "offline-test-runtime"
        cv2 = SimpleNamespace(VideoCapture=lambda _path: Capture(), CAP_PROP_POS_MSEC=0)
        def __init__(self, path, profile):
            calls.append((path, profile.id))
        def detect(self, _image):
            return [{"class_name": "van", "native_class_name": "van", "confidence": .8, "xyxy": [.1, .2, .3, .4]}]
    metadata = {"streams": [{"r_frame_rate": "4/1", "width": 640, "height": 480, "nb_read_frames": "2"}], "format": {"duration": ".5"}}
    monkeypatch.setattr(detection, "TrafficDetector", Traffic)
    monkeypatch.setattr(detection, "YoloDetector", lambda *_args: pytest.fail("Dense traffic must not fall back to Tiny"))
    monkeypatch.setattr(detection.subprocess, "run", lambda *_args, **_kwargs: SimpleNamespace(stdout=json.dumps(metadata).encode()))
    result = detection.prepare_detections(tmp_path, "traffic-jam", sample_fps=4, dense_strategy="full-frame")
    assert calls == [(tmp_path / "models" / "yolo11s_visdrone.onnx", "yolo11s-visdrone640")]
    assert result["model"]["name"] == "YOLO11s VisDrone" and result["model"]["license"] == "AGPL-3.0"
    assert result["model"]["runtime_version"] == "offline-test-runtime"
    assert result["confidence_threshold"] == .4
    assert [item["vehicle_count"] for item in result["frames"]] == [1, 1]
    assert DetectionService(tmp_path).get("traffic-jam") == result


def test_missing_dense_weights_fail_without_download_or_tiny_fallback(tmp_path, monkeypatch):
    from api import detection
    (tmp_path / "footage").mkdir()
    (tmp_path / "footage" / "traffic-jam.webm").write_bytes(b"offline-source")
    monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: pytest.fail("No implicit model download"))
    monkeypatch.setattr(detection, "YoloDetector", lambda *_args: pytest.fail("No Tiny fallback"))
    with pytest.raises(detection.DetectionError, match="YOLO11s VisDrone"):
        detection.prepare_detections(tmp_path, "traffic-jam")
    assert not (tmp_path / "detections" / "traffic-jam.json").exists()


def test_dense_only_cli_does_not_fetch_unrelated_tiny_weights(tmp_path, monkeypatch, capsys):
    import importlib.util
    import sys
    path = Path(__file__).parents[1] / "scripts" / "run_detection.py"
    spec = importlib.util.spec_from_file_location("dense_detection_cli_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    prepared = traffic_report()
    prepared["processing"] = {"frame_count": len(prepared["frames"])}
    monkeypatch.setattr(module, "load_local_environment", lambda: None)
    monkeypatch.setenv("CLEARWAY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", [str(path), "--source", "traffic-jam", "--download-model", "--dense-strategy", "full-frame"])
    monkeypatch.setattr(module, "download_model", lambda *_: pytest.fail("Dense-only setup must not download Tiny"))
    monkeypatch.setattr(module, "DetectionService", lambda _: SimpleNamespace(get=lambda _source: deepcopy(prepared)))
    assert module.main() == 0
    assert json.loads(capsys.readouterr().out)["model"]["name"] == "YOLO11s VisDrone"


def tiled_traffic_report():
    from api.detection import requested_replay_strategy, strategy_digest
    from api.tiled_detection import TilingConfig, tile_regions
    result = traffic_report()
    strategy = requested_replay_strategy("traffic-jam")
    result["provenance"].update(inference_strategy=strategy, inference_strategy_sha256=strategy_digest(strategy))
    result["confidence_threshold"] = strategy["confidence_floor"]
    passes = 1 + len(tile_regions(result["video_width"], result["video_height"], TilingConfig()))
    result["processing"] = {"model_passes_per_sample": passes, "model_passes_total": passes * len(result["frames"])}
    return result


def test_tiled_and_full_frame_fallback_caches_both_preserve_actual_strategy():
    from api.detection import FULL_FRAME_STRATEGY, strategy_digest
    tiled = tiled_traffic_report()
    assert validate_report(tiled, "traffic-jam", "test-sha")
    assert tiled["processing"]["model_passes_per_sample"] == 7
    assert validate_report(traffic_report(), "traffic-jam", "test-sha")  # legacy full frame
    explicit_full = traffic_report()
    explicit_full["provenance"].update(inference_strategy=FULL_FRAME_STRATEGY, inference_strategy_sha256=strategy_digest(FULL_FRAME_STRATEGY))
    assert validate_report(explicit_full, "traffic-jam", "test-sha")


@pytest.mark.parametrize("mutation", [
    lambda r: r["provenance"].update(inference_strategy_sha256="wrong"),
    lambda r: r["provenance"]["inference_strategy"].update(tile_size=640),
    lambda r: r["provenance"]["inference_strategy"].update(overlap=.5),
    lambda r: r["provenance"]["inference_strategy"].update(merge_containment=.5),
    lambda r: r["processing"].update(model_passes_total=1),
    lambda r: r["processing"].update(model_passes_per_sample=1),
    lambda r: r.update(confidence_threshold=.4),
    lambda r: r["frames"][8]["boxes"][0].update(confidence=.49),
])
def test_tiled_cache_rejects_strategy_or_counts_or_score_mismatch(mutation):
    result = tiled_traffic_report()
    mutation(result)
    assert not validate_report(result, "traffic-jam", "test-sha")


def test_even_rehashed_unvalidated_tiling_parameters_are_not_accepted():
    from api.detection import strategy_digest
    result = tiled_traffic_report()
    result["provenance"]["inference_strategy"]["merge_containment"] = .5
    result["provenance"]["inference_strategy_sha256"] = strategy_digest(result["provenance"]["inference_strategy"])
    assert not validate_report(result, "traffic-jam", "test-sha")


def test_cli_changes_strategy_without_force_and_does_not_recompute_matching_cache(tmp_path, monkeypatch, capsys):
    import importlib.util
    import sys
    from api.detection import requested_replay_strategy
    path = Path(__file__).parents[1] / "scripts" / "run_detection.py"
    spec = importlib.util.spec_from_file_location("dense_tiling_cli_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    old = traffic_report()
    old["processing"] = {"frame_count": 24}
    stored = [old]
    calls = []
    monkeypatch.setattr(module, "load_local_environment", lambda: None)
    monkeypatch.setenv("CLEARWAY_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(sys, "argv", [str(path), "--source", "traffic-jam"])
    monkeypatch.setattr(module, "DetectionService", lambda _: SimpleNamespace(get=lambda _source: deepcopy(stored[0])))
    def prepare(data, source, **kwargs):
        calls.append((data, source, kwargs))
        stored[0] = tiled_traffic_report()
        return deepcopy(stored[0])
    monkeypatch.setattr(module, "prepare_detections", prepare)
    assert module.main() == 0 and len(calls) == 1
    assert calls[0][2] == {"sample_fps": 4.0, "dense_strategy": "tiled", "dense_tile_size": 768}
    assert json.loads(capsys.readouterr().out)["inference_strategy"] == requested_replay_strategy("traffic-jam")
    assert module.main() == 0 and len(calls) == 1
