from datetime import datetime, timezone
import hashlib
import json
import threading

import pytest

from api.live_detection import (
    CACHE_TTL_SECONDS, FAILURE_RETRY_SECONDS, MAX_CACHE_ENTRIES, MAX_IMAGE_BYTES,
    LiveDetectionService, jpeg_dimensions,
)


def jpeg(*, width=640, height=480, nonce=b"test"):
    # Minimal JPEG header fixture. Tests inject a decoder; this is not a real
    # image or an artifact that may be shown as genuine model output.
    comment = b"\xff\xfe" + (len(nonce) + 2).to_bytes(2, "big") + nonce
    sof = b"\xff\xc0\x00\x0b\x08" + height.to_bytes(2, "big") + width.to_bytes(2, "big") + b"\x01\x01\x11\x00"
    return b"\xff\xd8" + comment + sof + b"\xff\xd9"


class Image:
    shape = (480, 640, 3)


class Detector:
    runtime_version = "test-runtime"

    def __init__(self, *_args):
        self.calls = 0

    def detect(self, image):
        self.calls += 1
        return [{"class_name": "car", "confidence": 0.8, "xyxy": [0.1, 0.2, 0.6, 0.7]}]


def service(tmp_path, detector=None, *, ticks=None, factory=None, decoder=None):
    detector = detector or Detector()
    ticks = ticks if ticks is not None else [100.0]
    instance = LiveDetectionService(
        tmp_path, detector_factory=factory or (lambda _: detector),
        image_decoder=decoder or (lambda _detector, _raw: Image()),
        monotonic=lambda: ticks[0], clock=lambda: datetime(2026, 11, 7, tzinfo=timezone.utc),
    )
    return instance, detector, ticks


def test_exact_image_hash_cache_never_reuses_boxes_for_different_bytes(tmp_path):
    instance, detector, _ = service(tmp_path)
    raw = jpeg()
    fresh = instance.analyze_jpeg(raw)
    assert fresh["status"] == "available"
    assert fresh["analysis_mode"] == "fresh"
    assert fresh["image_sha256"] == hashlib.sha256(raw).hexdigest()
    assert fresh["provenance"]["fixture"] is False
    assert fresh["vehicle_count"] == 1 and fresh["person_count"] == 0
    cached = instance.analyze_jpeg(raw)
    assert cached["analysis_mode"] == "cached"
    assert cached["provenance"] == fresh["provenance"]
    assert detector.calls == 1
    changed = instance.analyze_jpeg(jpeg(nonce=b"different-image-bytes"))
    assert changed["analysis_mode"] == "fresh"
    assert changed["image_sha256"] != fresh["image_sha256"]
    assert detector.calls == 2
    assert list(tmp_path.iterdir()) == []  # Neither frames nor results archived.


def test_tracking_pool_is_separate_from_high_confidence_counts_and_cache(tmp_path):
    high = {"class_name": "car", "confidence": .8, "xyxy": [.1, .2, .3, .4]}
    low = {"class_name": "car", "confidence": .2, "xyxy": [.6, .2, .8, .4]}
    class PoolDetector(Detector):
        def detect(self, image, *, confidence_floor=None):
            self.calls += 1
            return [high, low] if confidence_floor == .1 else [high]
    instance, detector, _ = service(tmp_path, detector=PoolDetector())
    still = instance.analyze_jpeg(jpeg(), camera_id="caltrans-d4-49")
    moving = instance.analyze_jpeg(jpeg(), camera_id="caltrans-d4-49", tracking=True)
    assert moving["boxes"] == still["boxes"] == [high]
    assert moving["vehicle_count"] == still["vehicle_count"] == 1
    assert moving["tracking_candidates"] == [high, low]
    assert "tracking_candidates" not in still
    assert moving["provenance"]["configuration_sha256"] != still["provenance"]["configuration_sha256"]
    cached = instance.analyze_jpeg(jpeg(), camera_id="caltrans-d4-49", tracking=True)
    assert cached["analysis_mode"] == "cached" and detector.calls == 2
    cached["tracking_candidates"].clear()
    assert len(instance.analyze_jpeg(jpeg(), camera_id="caltrans-d4-49", tracking=True)["tracking_candidates"]) == 2


def test_low_tracking_candidates_still_obey_camera_graphics_exclusions(tmp_path):
    class PoolDetector(Detector):
        def detect(self, image, *, confidence_floor=None):
            return [{"class_name": "car", "confidence": .2, "xyxy": [.1, .01, .2, .04]},
                    {"class_name": "car", "confidence": .2, "xyxy": [.6, .2, .8, .4]}]
    instance, _, _ = service(tmp_path, detector=PoolDetector())
    result = instance.analyze_jpeg(jpeg(), camera_id="caltrans-d4-689", tracking=True)
    assert result["boxes"] == [] and result["vehicle_count"] == 0
    assert len(result["tracking_candidates"]) == 1
    assert result["tracking_candidates"][0]["xyxy"] == [.6, .2, .8, .4]


def test_returned_objects_cannot_mutate_cached_results(tmp_path):
    instance, _, _ = service(tmp_path)
    first = instance.analyze_jpeg(jpeg())
    first["boxes"][0]["xyxy"][0] = 0.9
    first["provenance"]["fixture"] = True
    second = instance.analyze_jpeg(jpeg())
    second["boxes"].clear()
    third = instance.analyze_jpeg(jpeg())
    assert third["boxes"][0]["xyxy"][0] == 0.1
    assert third["provenance"]["fixture"] is False


def test_cache_is_bounded_and_expired_images_are_inferred_again(tmp_path):
    instance, detector, ticks = service(tmp_path)
    for index in range(MAX_CACHE_ENTRIES + 1):
        instance.analyze_jpeg(jpeg(nonce=str(index).encode()))
    assert len(instance._cache) == MAX_CACHE_ENTRIES
    assert instance.analyze_jpeg(jpeg(nonce=b"0"))["analysis_mode"] == "fresh"
    calls = detector.calls
    ticks[0] += CACHE_TTL_SECONDS + 1
    assert instance.analyze_jpeg(jpeg(nonce=b"0"))["analysis_mode"] == "fresh"
    assert detector.calls == calls + 1


@pytest.mark.parametrize("raw", [
    b"", "not bytes", bytearray(b"jpeg"), b"\xff\xd8\xffwrong\xff\xd9",
    b"x" * (MAX_IMAGE_BYTES + 1), jpeg(width=0), jpeg(width=4097), jpeg(width=4096, height=4096),
    jpeg()[:-2], b"\xff\xd8\xff\xe0\xff\xff\x00\x00\xff\xd9",
])
def test_invalid_and_oversized_images_do_not_initialize_runtime(tmp_path, raw):
    def forbidden(_weights):
        pytest.fail("Invalid image must be rejected before native runtime")
    instance, _, _ = service(tmp_path, factory=forbidden)
    result = instance.analyze_jpeg(raw)
    assert result["status"] == "unavailable"
    assert result["reason"] == "invalid_image"
    assert result["boxes"] == []
    assert not instance._cache


def test_decoder_failure_returns_unavailable_without_an_inference(tmp_path):
    instance, detector, _ = service(tmp_path, decoder=lambda *_: None)
    result = instance.analyze_jpeg(jpeg())
    assert result["reason"] == "invalid_image"
    assert detector.calls == 0


def test_header_and_decoded_dimensions_must_match(tmp_path):
    class WrongImage:
        shape = (4000, 2000, 3)
    instance, detector, _ = service(tmp_path, decoder=lambda *_: WrongImage())
    result = instance.analyze_jpeg(jpeg())
    assert result["reason"] == "invalid_image"
    assert detector.calls == 0


def test_missing_model_is_sanitized_with_cooldown_and_no_substitution(tmp_path):
    factory_calls = []
    def broken(_weights):
        factory_calls.append(True)
        raise RuntimeError("secret-path-or-provider-error-must-not-leak")
    instance, _, ticks = service(tmp_path, factory=broken)
    first = instance.analyze_jpeg(jpeg())
    assert first["status"] == "unavailable"
    assert first["boxes"] == []
    assert "secret-path" not in str(first)
    assert first["retry_after_seconds"] == FAILURE_RETRY_SECONDS
    second = instance.analyze_jpeg(jpeg(nonce=b"new-frame"))
    assert second["status"] == "unavailable"
    assert len(factory_calls) == 1
    ticks[0] += FAILURE_RETRY_SECONDS + 1
    instance.analyze_jpeg(jpeg())
    assert len(factory_calls) == 2


def test_concurrent_frame_is_rejected_as_busy_instead_of_queued(tmp_path):
    entered, release = threading.Event(), threading.Event()
    class Blocking(Detector):
        def detect(self, image):
            entered.set()
            assert release.wait(2)
            return super().detect(image)
    detector = Blocking()
    instance, _, _ = service(tmp_path, detector)
    first = []
    worker = threading.Thread(target=lambda: first.append(instance.analyze_jpeg(jpeg())))
    worker.start()
    try:
        assert entered.wait(1)
        busy = instance.analyze_jpeg(jpeg(nonce=b"other-frame"))
        assert busy["status"] == "unavailable"
        assert busy["reason"] == "busy"
        assert busy["retry_after_seconds"] == 1
        assert detector.calls == 0
    finally:
        release.set()
        worker.join(2)
    assert first[0]["status"] == "available"
    assert detector.calls == 1


@pytest.mark.parametrize("boxes", [
    [{"class_name": "person identity", "confidence": 0.9, "xyxy": [0, 0, 1, 1]}],
    [{"class_name": "person", "confidence": float("nan"), "xyxy": [0, 0, 1, 1]}],
    [{"class_name": "person", "confidence": 0.9, "xyxy": [0, 0, 1.01, 1]}],
    [{"class_name": "person", "confidence": 0.9, "xyxy": [0.9, 0, 0.1, 1]}],
])
def test_malformed_detector_output_is_not_displayed(tmp_path, boxes):
    detector = Detector()
    detector.detect = lambda _: boxes
    instance, _, _ = service(tmp_path, detector)
    result = instance.analyze_jpeg(jpeg())
    assert result["status"] == "unavailable"
    assert result["boxes"] == []
    assert not instance._cache


def test_jpeg_header_parser_accepts_baseline_and_progressive():
    raw = jpeg()
    assert jpeg_dimensions(raw) == (640, 480)
    assert jpeg_dimensions(raw.replace(b"\xff\xc0", b"\xff\xc2")) == (640, 480)


@pytest.mark.parametrize("config", [
    "{broken json",
    json.dumps({"schema_version": 1, "profile": "not-supported"}),
    json.dumps({"schema_version": 1, "profile": "yolo11s-visdrone640"}),
])
def test_bad_profile_does_not_prevent_service_startup_or_silently_use_tiny(tmp_path, config):
    folder = tmp_path / "models"
    folder.mkdir()
    (folder / "live-detector.json").write_text(config)
    instance, detector, _ = service(tmp_path)
    result = instance.analyze_jpeg(jpeg())
    assert result["status"] == "unavailable"
    assert result["reason"] == "configuration_unavailable"
    assert detector.calls == 0


def test_selected_model_metadata_and_cache_identity_change_with_profile(tmp_path):
    from api.traffic_detection import PROFILES
    medium, _, _ = service(tmp_path)
    first = medium.analyze_jpeg(jpeg())
    assert first["model"]["name"] == "YOLOX-M"
    assert first["model"]["weights_sha256"] == PROFILES["yolox-m640"].sha256
    assert first["model"]["input_size"] == [640, 640]
    folder = tmp_path / "models"
    folder.mkdir()
    (folder / "live-detector.json").write_text(json.dumps({"schema_version": 1, "profile": "yolo11s-visdrone640", "agpl_choice_accepted": True}))
    detector = Detector()
    detector.detect = lambda _: [
        {"class_name": "van", "native_class_name": "van", "confidence": 0.8, "xyxy": [0.1, 0.2, 0.6, 0.7]},
        {"class_name": "person", "native_class_name": "people", "confidence": 0.7, "xyxy": [0.7, 0.2, 0.8, 0.8]},
    ]
    optional, _, _ = service(tmp_path, detector)
    second = optional.analyze_jpeg(jpeg())
    assert second["model"]["name"] == "YOLO11s VisDrone" and second["model"]["license"] == "AGPL-3.0"
    assert second["model"]["weights_sha256"] == PROFILES["yolo11s-visdrone640"].sha256
    assert second["vehicle_count"] == second["person_count"] == 1
    assert second["boxes"][0]["native_class_name"] == "van"
    assert second["provenance"]["configuration_sha256"] != first["provenance"]["configuration_sha256"]
    assert second["image_sha256"] == first["image_sha256"]
    # Selection is startup-scoped; no hidden runtime model switch occurs.
    assert medium.analyze_jpeg(jpeg())["model"]["name"] == "YOLOX-M"


def graphics_and_road_boxes():
    return [
        {"class_name": "car", "confidence": 0.8, "xyxy": [0.05, 0.02, 0.2, 0.06]},  # title digits
        {"class_name": "car", "confidence": 0.8, "xyxy": [0.1, 0.94, 0.3, 0.98]},  # timestamp digits
        {"class_name": "car", "confidence": 0.8, "xyxy": [0.2, 0.4, 0.35, 0.55]},  # roadway
        {"class_name": "person", "confidence": 0.8, "xyxy": [0.3, 0.06, 0.4, 0.14]},  # overlaps title, center outside
    ]


def test_known_camera_graphics_exclusion_uses_centers_and_preserves_roadway(tmp_path):
    detector = Detector()
    detector.detect = lambda _: graphics_and_road_boxes()
    instance, _, _ = service(tmp_path, detector)
    result = instance.analyze_jpeg(jpeg(), camera_id="caltrans-d4-689")
    assert result["status"] == "available"
    assert result["boxes"] == graphics_and_road_boxes()[2:]
    assert result["vehicle_count"] == result["person_count"] == 1
    assert result["excluded_detection_count"] == 2
    assert result["excluded_regions"] == [
        {"id": "provider-title", "xyxy": [0, 0, 0.46, 0.08]},
        {"id": "provider-timestamp", "xyxy": [0, 0.93, 0.52, 1]},
    ]
    assert result["camera_id"] == result["provenance"]["camera_id"] == "caltrans-d4-689"
    assert result["provenance"]["exclusion_policy"] == "caltrans-d4-689-burned-in-graphics-v1"
    assert result["image_sha256"] == hashlib.sha256(jpeg()).hexdigest()


@pytest.mark.parametrize("camera_id", [None, "caltrans-d4-37", "caltrans-d4-689-2"])
def test_graphics_exclusion_is_not_applied_to_other_or_unknown_cameras(tmp_path, camera_id):
    detector = Detector()
    detector.detect = lambda _: graphics_and_road_boxes()
    instance, _, _ = service(tmp_path, detector)
    result = instance.analyze_jpeg(jpeg(), camera_id=camera_id)
    assert result["boxes"] == graphics_and_road_boxes()
    assert result["excluded_detection_count"] == 0
    assert result["excluded_regions"] == []
    assert result["provenance"]["exclusion_policy"] == "none-v1"


def test_identical_jpeg_from_different_cameras_has_isolated_cache_and_policy(tmp_path):
    class GraphicsDetector(Detector):
        def detect(self, image):
            self.calls += 1
            return graphics_and_road_boxes()
    instance, detector, _ = service(tmp_path, GraphicsDetector())
    masked = instance.analyze_jpeg(jpeg(), camera_id="caltrans-d4-689")
    other = instance.analyze_jpeg(jpeg(), camera_id="caltrans-d4-37")
    unspecified = instance.analyze_jpeg(jpeg())
    assert detector.calls == 3
    assert masked["analysis_mode"] == other["analysis_mode"] == unspecified["analysis_mode"] == "fresh"
    assert len(masked["boxes"]) == 2 and len(other["boxes"]) == len(unspecified["boxes"]) == 4
    assert len({r["provenance"]["configuration_sha256"] for r in (masked, other, unspecified)}) == 3
    assert len({r["provenance"]["model_configuration_sha256"] for r in (masked, other, unspecified)}) == 1
    masked["excluded_regions"][0]["xyxy"][2] = 1  # returned data cannot alter cached policy
    cached = instance.analyze_jpeg(jpeg(), camera_id="caltrans-d4-689")
    assert cached["analysis_mode"] == "cached" and detector.calls == 3
    assert cached["excluded_regions"][0]["xyxy"] == [0, 0, 0.46, 0.08]
    assert len(cached["boxes"]) == 2


def camera_selection(tmp_path):
    folder = tmp_path / "models"
    folder.mkdir()
    path = folder / "live-detector.json"
    path.write_text(json.dumps({"schema_version": 1, "profile": "yolo11s-visdrone640",
        "agpl_choice_accepted": True, "camera_profiles": {"caltrans-d4-49": {"profile": "yolox-m640"}}}))
    return path


def test_camera_profile_uses_its_own_runtime_threshold_taxonomy_and_provenance(tmp_path):
    path = camera_selection(tmp_path)
    factories = []
    medium, drone = Detector(), Detector()
    medium.detect = lambda _: [{"class_name": "car", "native_class_name": "car",
                               "confidence": 0.35, "xyxy": [0.1, 0.2, 0.6, 0.7]}]
    drone.detect = lambda _: [{"class_name": "van", "native_class_name": "van",
                              "confidence": 0.8, "xyxy": [0.1, 0.2, 0.6, 0.7]}]
    def factory(weights):
        factories.append(weights.name)
        return medium if weights.name == "yolox_m.onnx" else drone
    instance, _, _ = service(tmp_path, factory=factory)
    fremont = instance.analyze_jpeg(jpeg(), "caltrans-d4-49")
    other = instance.analyze_jpeg(jpeg(), "caltrans-d4-37")
    assert fremont["status"] == other["status"] == "available"
    assert fremont["model"]["name"] == "YOLOX-M"
    assert other["model"]["name"] == "YOLO11s VisDrone"
    assert fremont["confidence_threshold"] == 0.3 and other["confidence_threshold"] == 0.4
    assert fremont["provenance"]["profile_selection"] == fremont["model"]["selection"] == "camera_override"
    assert other["model"]["selection"] == "default"
    assert fremont["provenance"]["model_configuration_sha256"] != other["provenance"]["model_configuration_sha256"]
    assert fremont["provenance"]["configuration_sha256"] != other["provenance"]["configuration_sha256"]
    assert fremont["image_sha256"] == other["image_sha256"]
    assert instance.analyze_jpeg(jpeg(), "caltrans-d4-49")["analysis_mode"] == "cached"
    assert factories == ["yolox_m.onnx", "yolo11s_visdrone.onnx"]
    # Edits only apply after restart; a fresh service must not reuse the old model identity.
    raw = json.loads(path.read_text()); raw.pop("camera_profiles"); path.write_text(json.dumps(raw))
    assert instance.analyze_jpeg(jpeg(nonce=b"later"), "caltrans-d4-49")["model"]["name"] == "YOLOX-M"
    restarted, _, _ = service(tmp_path, factory=factory)
    new = restarted.analyze_jpeg(jpeg(), "caltrans-d4-49")
    assert new["model"]["name"] == "YOLO11s VisDrone"
    assert new["provenance"]["configuration_sha256"] != fremont["provenance"]["configuration_sha256"]


def test_missing_camera_model_does_not_substitute_or_block_default_model(tmp_path):
    camera_selection(tmp_path)
    attempts = []
    def factory(weights):
        attempts.append(weights.name)
        if weights.name == "yolox_m.onnx":
            raise RuntimeError("private-native-error")
        return Detector()
    instance, _, ticks = service(tmp_path, factory=factory)
    missing = instance.analyze_jpeg(jpeg(), "caltrans-d4-49")
    assert missing["reason"] == "runtime_unavailable" and not missing["boxes"]
    assert "private-native" not in str(missing)
    assert instance.analyze_jpeg(jpeg(), "caltrans-d4-37")["model"]["name"] == "YOLO11s VisDrone"
    assert instance.analyze_jpeg(jpeg(), "caltrans-d4-49")["status"] == "unavailable"
    assert attempts == ["yolox_m.onnx", "yolo11s_visdrone.onnx"]
    ticks[0] += FAILURE_RETRY_SECONDS + 1
    instance.analyze_jpeg(jpeg(), "caltrans-d4-49")
    assert attempts == ["yolox_m.onnx", "yolo11s_visdrone.onnx", "yolox_m.onnx"]
