from datetime import datetime, timezone
import hashlib
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
