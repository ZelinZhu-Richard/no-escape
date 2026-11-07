"""Bounded local YOLO inference on one explicitly selected camera image.

Only numeric detections are cached in memory. Images are neither archived nor
sent to a provider. Results identify the exact encoded JPEG that was analyzed;
the caller must display those bytes, rather than overlaying boxes on a later
snapshot or moving video frame. No incident or person identity is inferred.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import threading
import time

from .detection import (
    CLASS_NAMES, CONFIDENCE, MODEL_NAME, MODEL_SHA256, MODEL_VERSION, NMS_IOU,
    PREPROCESSING_VERSION, VEHICLE_NAMES, YoloDetector,
)

MAX_IMAGE_BYTES = 1_000_000
MAX_IMAGE_DIMENSION = 4096
MAX_IMAGE_PIXELS = 8_388_608
MAX_CACHE_ENTRIES = 8
CACHE_TTL_SECONDS = 300
FAILURE_RETRY_SECONDS = 30
SCHEMA_VERSION = "clearway-live-detections-v1"
SOF_MARKERS = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})
LIMITATIONS = [
    "Boxes describe this exact image, not a later video frame or continuous tracking.",
    "Detections may miss or misclassify objects; no injury, danger, identity, or calibrated lane membership is inferred.",
    "Image retrieval time and analysis time do not establish the camera capture time.",
]


def jpeg_dimensions(raw: bytes) -> tuple[int, int]:
    """Check JPEG dimensions before allocating a decoded image.

    The decoder still validates the full bitstream. Reject malformed segments,
    dimensions and unsupported precision before entering native image code.
    """
    if type(raw) is not bytes or not 12 <= len(raw) <= MAX_IMAGE_BYTES:
        raise ValueError("JPEG size exceeds the supported range.")
    if not raw.startswith(b"\xff\xd8\xff") or not raw.endswith(b"\xff\xd9"):
        raise ValueError("A complete JPEG image is required.")
    position = 2
    while position < len(raw) - 2:
        if raw[position] != 0xFF:
            raise ValueError("Malformed JPEG header.")
        while position < len(raw) and raw[position] == 0xFF:
            position += 1
        if position >= len(raw):
            break
        marker = raw[position]
        position += 1
        if marker in {0x01, 0xD8, *range(0xD0, 0xD8)}:
            continue
        if marker in {0x00, 0xDA, 0xD9} or position + 2 > len(raw):
            break
        length = int.from_bytes(raw[position:position + 2], "big")
        if length < 2 or position + length > len(raw):
            raise ValueError("Malformed JPEG segment.")
        if marker in SOF_MARKERS:
            if length < 8 or raw[position + 2] != 8:
                raise ValueError("Unsupported JPEG image format.")
            height = int.from_bytes(raw[position + 3:position + 5], "big")
            width = int.from_bytes(raw[position + 5:position + 7], "big")
            if (not 1 <= width <= MAX_IMAGE_DIMENSION or not 1 <= height <= MAX_IMAGE_DIMENSION
                    or width * height > MAX_IMAGE_PIXELS):
                raise ValueError("JPEG dimensions exceed the supported range.")
            return width, height
        position += length
    raise ValueError("JPEG dimensions are unavailable.")


def _decode(detector, raw: bytes):
    # OpenCV applies normal JPEG orientation. Return the resulting dimensions
    # with detections; the client must fit the corresponding original image.
    return detector.cv2.imdecode(detector.np.frombuffer(raw, dtype=detector.np.uint8), detector.cv2.IMREAD_COLOR)


def _validated_boxes(boxes: object) -> list[dict]:
    if not isinstance(boxes, list) or len(boxes) > 300:
        raise ValueError("Invalid detector output.")
    normalized = []
    for item in boxes:
        if not isinstance(item, dict) or item.get("class_name") not in CLASS_NAMES.values():
            raise ValueError("Invalid detector class.")
        confidence, coords = item.get("confidence"), item.get("xyxy")
        if type(confidence) not in (float, int) or not math.isfinite(confidence) or not CONFIDENCE <= confidence <= 1:
            raise ValueError("Invalid detector confidence.")
        if (not isinstance(coords, list) or len(coords) != 4
                or any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1 for value in coords)
                or coords[0] >= coords[2] or coords[1] >= coords[3]):
            raise ValueError("Invalid detector coordinates.")
        normalized.append({"class_name": item["class_name"], "confidence": float(confidence),
                           "xyxy": [float(value) for value in coords]})
    return normalized


class LiveDetectionService:
    """One inference slot and eight short-lived result entries, with no images.

    Instantiate once in the operator process. Concurrent requests fail quickly
    as busy instead of building a work queue. An unavailable runtime is retried
    after a cooldown so an operator can install the pinned local requirements.
    """
    def __init__(self, data_dir: Path, *, detector_factory=None, image_decoder=None,
                 monotonic=None, clock=None):
        self.data_dir = Path(data_dir)
        self._factory = detector_factory or YoloDetector
        self._decode = image_decoder or _decode
        self._monotonic = monotonic or time.monotonic
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._slot = threading.Lock()
        self._detector = None
        self._retry_after = 0.0
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._config = {
            "model": MODEL_NAME, "model_version": MODEL_VERSION, "weights_sha256": MODEL_SHA256,
            "preprocessing_version": PREPROCESSING_VERSION,
            "confidence_threshold": CONFIDENCE, "nms_iou": NMS_IOU,
            "classes": CLASS_NAMES, "schema_version": SCHEMA_VERSION,
        }
        self._config_sha = hashlib.sha256(json.dumps(self._config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _unavailable(self, message: str, reason: str, *, image_sha: str | None = None, retry: int | None = None) -> dict:
        result = {
            "schema_version": SCHEMA_VERSION, "status": "unavailable", "analysis_mode": "unavailable",
            "image_sha256": image_sha, "image_width": None, "image_height": None,
            "boxes": [], "vehicle_count": None, "person_count": None,
            "inference_ms": None, "request_ms": None,
            "message": message, "reason": reason, "limitations": list(LIMITATIONS),
        }
        if retry is not None:
            result["retry_after_seconds"] = retry
        return result

    def analyze_jpeg(self, raw: bytes) -> dict:
        started = self._monotonic()
        try:
            width, height = jpeg_dimensions(raw)
        except (ValueError, TypeError):
            return self._unavailable("Image is not a supported, bounded JPEG; no detection was run.", "invalid_image")
        image_sha = hashlib.sha256(raw).hexdigest()
        cache_key = hashlib.sha256(f"{image_sha}:{self._config_sha}".encode()).hexdigest()
        if not self._slot.acquire(blocking=False):
            return self._unavailable("Local detector is busy; retry with the next selected frame.", "busy", image_sha=image_sha, retry=1)
        try:
            now = self._monotonic()
            cached = self._cache.get(cache_key)
            if cached and now < cached["expires_at"]:
                self._cache.move_to_end(cache_key)
                result = deepcopy(cached["result"])
                result["analysis_mode"] = "cached"
                result["request_ms"] = round(max(0, (self._monotonic() - started) * 1000), 3)
                return result
            self._cache.pop(cache_key, None)
            if now < self._retry_after:
                return self._unavailable("Local detector is unavailable; retry after its cooldown.", "runtime_unavailable",
                                         image_sha=image_sha, retry=max(1, math.ceil(self._retry_after - now)))
            try:
                if self._detector is None:
                    self._detector = self._factory(self.data_dir / "models" / "yolox_tiny.onnx")
                image = self._decode(self._detector, raw)
                if image is None or len(image.shape) != 3 or image.shape[2] != 3:
                    return self._unavailable("JPEG could not be decoded; no detection was run.", "invalid_image", image_sha=image_sha)
                decoded_height, decoded_width = map(int, image.shape[:2])
                if ({decoded_width, decoded_height} != {width, height}
                        or decoded_width * decoded_height > MAX_IMAGE_PIXELS):
                    return self._unavailable("Decoded image dimensions do not match the JPEG header.", "invalid_image", image_sha=image_sha)
                inference_started = self._monotonic()
                boxes = _validated_boxes(self._detector.detect(image))
                inference_ms = round(max(0, (self._monotonic() - inference_started) * 1000), 3)
                result = {
                    "schema_version": SCHEMA_VERSION, "status": "available", "analysis_mode": "fresh",
                    "image_sha256": image_sha, "image_width": decoded_width, "image_height": decoded_height,
                    "boxes": boxes, "vehicle_count": sum(box["class_name"] in VEHICLE_NAMES for box in boxes),
                    "person_count": sum(box["class_name"] == "person" for box in boxes),
                    "model": {"name": MODEL_NAME, "version": MODEL_VERSION, "weights_sha256": MODEL_SHA256,
                              "license": "Apache-2.0", "runtime": "ONNX Runtime CPU",
                              "runtime_version": self._detector.runtime_version},
                    "provenance": {"kind": "local_yolo_image", "fixture": False,
                                   "image_sha256": image_sha, "configuration_sha256": self._config_sha,
                                   "preprocessing_version": PREPROCESSING_VERSION,
                                   "analyzed_at": self._clock().isoformat()},
                    "confidence_threshold": CONFIDENCE, "inference_ms": inference_ms,
                    "request_ms": round(max(0, (self._monotonic() - started) * 1000), 3),
                    "limitations": list(LIMITATIONS),
                }
            except Exception:
                # Provider names, paths and native exception strings do not
                # become UI messages. No fake/cached-from-another-image boxes.
                self._detector = None
                self._retry_after = self._monotonic() + FAILURE_RETRY_SECONDS
                return self._unavailable("Local YOLO inference is unavailable; check the local model and runtime setup.",
                                         "runtime_unavailable", image_sha=image_sha, retry=FAILURE_RETRY_SECONDS)
            self._cache[cache_key] = {"result": deepcopy(result), "expires_at": self._monotonic() + CACHE_TTL_SECONDS}
            self._cache.move_to_end(cache_key)
            while len(self._cache) > MAX_CACHE_ENTRIES:
                self._cache.popitem(last=False)
            return result
        finally:
            self._slot.release()
