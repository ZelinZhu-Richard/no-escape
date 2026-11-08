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
import re
import threading
import time

from .traffic_detection import (
    DetectorProfile, TrafficDetectionError, TrafficDetector, selected_profiles,
)

MAX_IMAGE_BYTES = 1_000_000
MAX_IMAGE_DIMENSION = 4096
MAX_IMAGE_PIXELS = 8_388_608
MAX_CACHE_ENTRIES = 8
CACHE_TTL_SECONDS = 300
FAILURE_RETRY_SECONDS = 30
SCHEMA_VERSION = "clearway-live-detections-v1"
TRACKING_CONFIDENCE_FLOOR = 0.1
SOF_MARKERS = frozenset({0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF})
# These rectangles cover the observed provider graphics on this camera only.
# They are not a generic road ROI and must not follow other camera selections.
GRAPHICS_CAMERA_ID = "caltrans-d4-689"
GRAPHICS_EXCLUSION_POLICY = "caltrans-d4-689-burned-in-graphics-v1"
GRAPHICS_EXCLUSIONS = (
    ("provider-title", (0.0, 0.0, 0.46, 0.08)),
    ("provider-timestamp", (0.0, 0.93, 0.52, 1.0)),
)
TVA43_GRAPHICS_EXCLUSIONS = (("provider-timestamp", (0.0, 0.0, 0.50, 0.08)),)
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


def _validated_boxes(boxes: object, profile: DetectorProfile, *, confidence_floor: float | None = None) -> list[dict]:
    if not isinstance(boxes, list) or len(boxes) > 300:
        raise ValueError("Invalid detector output.")
    normalized = []
    allowed_classes = set(dict(profile.display_classes).values())
    display_names = dict(profile.display_classes)
    native_mapping = {native: display_names[index] for index, native in profile.native_classes}
    threshold = profile.confidence if confidence_floor is None else confidence_floor
    for item in boxes:
        if not isinstance(item, dict) or item.get("class_name") not in allowed_classes:
            raise ValueError("Invalid detector class.")
        confidence, coords = item.get("confidence"), item.get("xyxy")
        if type(confidence) not in (float, int) or not math.isfinite(confidence) or not threshold <= confidence <= 1:
            raise ValueError("Invalid detector confidence.")
        if (not isinstance(coords, list) or len(coords) != 4
                or any(type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1 for value in coords)
                or coords[0] >= coords[2] or coords[1] >= coords[3]):
            raise ValueError("Invalid detector coordinates.")
        clean = {"class_name": item["class_name"], "confidence": float(confidence),
                 "xyxy": [float(value) for value in coords]}
        if "native_class_name" in item:
            if native_mapping.get(item["native_class_name"]) != item["class_name"]:
                raise ValueError("Invalid detector native class.")
            clean["native_class_name"] = item["native_class_name"]
        normalized.append(clean)
    return normalized


def _exclusion_context(camera_id: str | None) -> dict:
    if camera_id is not None and (not isinstance(camera_id, str)
                                  or not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", camera_id)):
        raise ValueError("Invalid camera identifier.")
    policy, excluded = "none-v1", ()
    if camera_id == GRAPHICS_CAMERA_ID:
        policy, excluded = GRAPHICS_EXCLUSION_POLICY, GRAPHICS_EXCLUSIONS
    elif camera_id == "caltrans-d4-285":
        policy, excluded = "caltrans-d4-285-timestamp-v1", TVA43_GRAPHICS_EXCLUSIONS
    regions = [{"id": identifier, "xyxy": list(rect)} for identifier, rect in excluded]
    return {"camera_id": camera_id,
            "exclusion_policy": policy,
            "excluded_regions": regions}


def _outside_graphics(box: dict, regions: list[dict]) -> bool:
    x1, y1, x2, y2 = box["xyxy"]
    center_x, center_y = (x1 + x2) / 2, (y1 + y2) / 2
    return not any(rect[0] <= center_x <= rect[2] and rect[1] <= center_y <= rect[3]
                   for rect in (region["xyxy"] for region in regions))


class LiveDetectionService:
    """One inference slot and eight short-lived result entries, with no images.

    Instantiate once in the operator process. Concurrent requests fail quickly
    as busy instead of building a work queue. An unavailable runtime is retried
    after a cooldown so an operator can install the pinned local requirements.
    """
    def __init__(self, data_dir: Path, *, detector_factory=None, image_decoder=None,
                 monotonic=None, clock=None):
        self.data_dir = Path(data_dir)
        try:
            self._profile, self._camera_profiles = selected_profiles(self.data_dir)
        except TrafficDetectionError:
            self._profile = None
            self._camera_profiles = {}
        self._factory = detector_factory
        self._decode = image_decoder or _decode
        self._monotonic = monotonic or time.monotonic
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._slot = threading.Lock()
        self._detectors: dict[str, object] = {}
        self._retry_after: dict[str, float] = {}
        self._cache: OrderedDict[str, dict] = OrderedDict()
        profiles = [self._profile, *self._camera_profiles.values()]
        self._config_shas = {
            profile.id: hashlib.sha256(json.dumps(
                {**profile.configuration(), "schema_version": SCHEMA_VERSION},
                sort_keys=True, separators=(",", ":"),
            ).encode()).hexdigest() for profile in profiles if profile is not None
        }

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

    def analyze_jpeg(self, raw: bytes, camera_id: str | None = None, *, tracking: bool = False) -> dict:
        started = self._monotonic()
        try:
            context = _exclusion_context(camera_id)
        except ValueError:
            return self._unavailable("Camera identifier is invalid; no detection was run.", "invalid_camera")
        try:
            width, height = jpeg_dimensions(raw)
        except (ValueError, TypeError):
            return self._unavailable("Image is not a supported, bounded JPEG; no detection was run.", "invalid_image")
        image_sha = hashlib.sha256(raw).hexdigest()
        if self._profile is None:
            return self._unavailable("The selected local detector configuration is invalid; no fallback was used.",
                                     "configuration_unavailable", image_sha=image_sha)
        profile = self._camera_profiles.get(camera_id, self._profile)
        config_sha = self._config_shas[profile.id]
        selection = "camera_override" if camera_id in self._camera_profiles else "default"
        configuration_sha = hashlib.sha256(json.dumps(
            {"model_configuration_sha256": config_sha, "profile_selection": selection,
             "tracking_confidence_floor": TRACKING_CONFIDENCE_FLOOR if tracking else None, **context},
            sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest()
        cache_key = hashlib.sha256(f"{image_sha}:{configuration_sha}".encode()).hexdigest()
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
            retry_after = self._retry_after.get(profile.id, 0.0)
            if now < retry_after:
                return self._unavailable("Local detector is unavailable; retry after its cooldown.", "runtime_unavailable",
                                         image_sha=image_sha, retry=max(1, math.ceil(retry_after - now)))
            try:
                detector = self._detectors.get(profile.id)
                if detector is None:
                    weights = self.data_dir / "models" / profile.filename
                    detector = self._factory(weights) if self._factory else TrafficDetector(weights, profile)
                    self._detectors[profile.id] = detector
                image = self._decode(detector, raw)
                if image is None or len(image.shape) != 3 or image.shape[2] != 3:
                    return self._unavailable("JPEG could not be decoded; no detection was run.", "invalid_image", image_sha=image_sha)
                decoded_height, decoded_width = map(int, image.shape[:2])
                if ({decoded_width, decoded_height} != {width, height}
                        or decoded_width * decoded_height > MAX_IMAGE_PIXELS):
                    return self._unavailable("Decoded image dimensions do not match the JPEG header.", "invalid_image", image_sha=image_sha)
                inference_started = self._monotonic()
                if tracking:
                    candidates = _validated_boxes(
                        detector.detect(image, confidence_floor=TRACKING_CONFIDENCE_FLOOR),
                        profile, confidence_floor=TRACKING_CONFIDENCE_FLOOR,
                    )
                    # Low-confidence observations are available only to the
                    # tracker. Counts and incident evidence retain the detector's
                    # normal threshold (OpenCV NMS uses a strict score cutoff).
                    boxes = [box for box in candidates if box["confidence"] > profile.confidence]
                    candidates = [box for box in candidates if _outside_graphics(box, context["excluded_regions"])]
                else:
                    boxes = _validated_boxes(detector.detect(image), profile)
                unfiltered_count = len(boxes)
                boxes = [box for box in boxes if _outside_graphics(box, context["excluded_regions"])]
                inference_ms = round(max(0, (self._monotonic() - inference_started) * 1000), 3)
                result = {
                    "schema_version": SCHEMA_VERSION, "status": "available", "analysis_mode": "fresh",
                    "image_sha256": image_sha, "image_width": decoded_width, "image_height": decoded_height,
                    "camera_id": camera_id, "excluded_regions": context["excluded_regions"],
                    "excluded_detection_count": unfiltered_count - len(boxes),
                    "boxes": boxes, "vehicle_count": sum(box["class_name"] != "person" for box in boxes),
                    "person_count": sum(box["class_name"] == "person" for box in boxes),
                    "model": {**profile.metadata(detector.runtime_version), "selection": selection},
                    "provenance": {"kind": "local_yolo_image", "fixture": False,
                                   "image_sha256": image_sha, "configuration_sha256": configuration_sha,
                                   "model_configuration_sha256": config_sha,
                                   "profile_selection": selection,
                                   "camera_id": camera_id, "exclusion_policy": context["exclusion_policy"],
                                   "preprocessing_version": profile.preprocessing_version,
                                   "analyzed_at": self._clock().isoformat()},
                    "confidence_threshold": profile.confidence, "inference_ms": inference_ms,
                    "request_ms": round(max(0, (self._monotonic() - started) * 1000), 3),
                    "limitations": list(LIMITATIONS),
                }
                if tracking:
                    result["tracking_candidates"] = candidates
                    result["tracking_confidence_floor"] = TRACKING_CONFIDENCE_FLOOR
            except Exception:
                # Provider names, paths and native exception strings do not
                # become UI messages. No fake/cached-from-another-image boxes.
                self._detectors.pop(profile.id, None)
                self._retry_after[profile.id] = self._monotonic() + FAILURE_RETRY_SECONDS
                return self._unavailable("Local YOLO inference is unavailable; check the local model and runtime setup.",
                                         "runtime_unavailable", image_sha=image_sha, retry=FAILURE_RETRY_SECONDS)
            self._cache[cache_key] = {"result": deepcopy(result), "expires_at": self._monotonic() + CACHE_TTL_SECONDS}
            self._cache.move_to_end(cache_key)
            while len(self._cache) > MAX_CACHE_ENTRIES:
                self._cache.popitem(last=False)
            return result
        finally:
            self._slot.release()
