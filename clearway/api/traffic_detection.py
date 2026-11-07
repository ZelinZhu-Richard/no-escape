"""Explicit, checksum-pinned detector profiles for public CCTV images.

The replay detector stays independent. Loading this module performs no model
download or inference. The default live profile is Apache-2.0 YOLOX-M at 640;
the separately licensed VisDrone profile requires explicit local selection.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import urllib.request


class TrafficDetectionError(ValueError):
    """Safe local setup/runtime error without credentials or native errors."""


@dataclass(frozen=True)
class DetectorProfile:
    id: str
    name: str
    version: str
    filename: str
    sha256: str
    download_url: str
    source_url: str
    license: str
    architecture: str
    preprocessing_version: str
    class_count: int
    display_classes: tuple[tuple[int, str], ...]
    native_classes: tuple[tuple[int, str], ...]
    input_size: int = 640
    confidence: float = 0.30
    nms_iou: float = 0.45
    requires_agpl_choice: bool = False

    def configuration(self) -> dict:
        return {
            "profile": self.id, "model": self.name, "model_version": self.version,
            "weights_sha256": self.sha256, "input_size": self.input_size,
            "architecture": self.architecture, "preprocessing_version": self.preprocessing_version,
            "confidence_threshold": self.confidence, "nms_iou": self.nms_iou,
            "display_classes": dict(self.display_classes), "native_classes": dict(self.native_classes),
        }

    def metadata(self, runtime_version: str) -> dict:
        return {
            "name": self.name, "version": self.version, "profile": self.id,
            "weights_sha256": self.sha256, "input_size": [self.input_size, self.input_size],
            "license": self.license, "source_url": self.source_url,
            "runtime": "ONNX Runtime CPU", "runtime_version": runtime_version,
        }


COCO_ROAD_CLASSES = ((0, "person"), (1, "bicycle"), (2, "car"), (3, "motorcycle"), (5, "bus"), (7, "truck"))
VISDRONE_NATIVE_CLASSES = tuple(enumerate(("pedestrian", "people", "bicycle", "car", "van", "truck", "tricycle", "awning-tricycle", "bus", "motor")))
VISDRONE_DISPLAY_CLASSES = tuple(enumerate(("person", "person", "bicycle", "car", "van", "truck", "tricycle", "awning-tricycle", "bus", "motorcycle")))
PROFILES = {
    "yolox-m640": DetectorProfile(
        id="yolox-m640", name="YOLOX-M", version="0.1.1rc0", filename="yolox_m.onnx",
        sha256="21ff6cfdeb53b013bac2249599e55f00bff3cfdfdab37ed7a4620818c1d15b3f",
        download_url="https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_m.onnx",
        source_url="https://github.com/Megvii-BaseDetection/YOLOX", license="Apache-2.0",
        architecture="yolox-raw-grid", preprocessing_version="yolox-m-bgr-raw-top-left-floor-640-v1",
        class_count=80, display_classes=COCO_ROAD_CLASSES, native_classes=COCO_ROAD_CLASSES,
    ),
    "yolo11s-visdrone640": DetectorProfile(
        id="yolo11s-visdrone640", name="YOLO11s VisDrone", version="16d8d1709ae6fd7a9920398fbed5612e6208e0f0",
        filename="yolo11s_visdrone.onnx",
        sha256="5abd18e5b630c330e68fe56b2bdc3875b10fbea07fe6912bde3cb9e68b58ca23",
        download_url="https://huggingface.co/RISEF/yolov11s-visdrone/resolve/16d8d1709ae6fd7a9920398fbed5612e6208e0f0/weights/best.onnx",
        source_url="https://huggingface.co/RISEF/yolov11s-visdrone/tree/16d8d1709ae6fd7a9920398fbed5612e6208e0f0",
        license="AGPL-3.0", architecture="yolo11-decoded-channels",
        preprocessing_version="yolo11s-visdrone-rgb-01-center-round-640-v1", class_count=10,
        display_classes=VISDRONE_DISPLAY_CLASSES, native_classes=VISDRONE_NATIVE_CLASSES,
        confidence=0.40, requires_agpl_choice=True,
    ),
}
DEFAULT_PROFILE = "yolox-m640"
MAX_MODEL_BYTES = 200_000_000
CONFIG_FILENAME = "live-detector.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _profile_from_record(raw: dict) -> DetectorProfile:
    if not isinstance(raw, dict) or not isinstance(raw.get("profile"), str) or raw["profile"] not in PROFILES:
        raise TrafficDetectionError("Live detector profile is unsupported.")
    profile = PROFILES[raw["profile"]]
    if raw.get("weights_sha256", profile.sha256) != profile.sha256:
        raise TrafficDetectionError("Live detector configuration does not match the pinned weights.")
    if profile.requires_agpl_choice and raw.get("agpl_choice_accepted") is not True:
        raise TrafficDetectionError("This optional live detector requires an explicit AGPL-3.0 selection.")
    return profile


def _read_selection(data_dir: Path) -> dict:
    """Read a bounded explicit selector; invalid overrides fail closed too."""
    path = Path(data_dir) / "models" / CONFIG_FILENAME
    try:
        if path.is_symlink():
            raise TrafficDetectionError("Live detector configuration must be a regular file.")
        if not path.exists():
            return {"schema_version": 1, "profile": DEFAULT_PROFILE}
        if not path.is_file() or path.stat().st_size > 4096:
            raise TrafficDetectionError("Live detector configuration is invalid.")
        raw = json.loads(path.read_text())
        if not isinstance(raw, dict) or type(raw.get("schema_version")) is not int or raw.get("schema_version") != 1:
            raise TrafficDetectionError("Live detector profile is unsupported.")
        _profile_from_record(raw)
        overrides = raw.get("camera_profiles", {})
        if not isinstance(overrides, dict) or len(overrides) > 16:
            raise TrafficDetectionError("Camera detector selections are invalid.")
        for camera_id, choice in overrides.items():
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", camera_id):
                raise TrafficDetectionError("Camera detector identifier is invalid.")
            _profile_from_record(choice)
        return raw
    except TrafficDetectionError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError):
        raise TrafficDetectionError("Cannot read the local live detector configuration.") from None


def selected_profiles(data_dir: Path) -> tuple[DetectorProfile, dict[str, DetectorProfile]]:
    """Resolve default and explicit camera selections once at startup."""
    raw = _read_selection(data_dir)
    return _profile_from_record(raw), {
        camera_id: _profile_from_record(choice)
        for camera_id, choice in raw.get("camera_profiles", {}).items()
    }


def selected_profile(data_dir: Path) -> DetectorProfile:
    return selected_profiles(data_dir)[0]


def install_profile(data_dir: Path, profile_id: str, *, from_file: Path | None = None,
                    download: bool = False, accept_agpl: bool = False,
                    camera_id: str | None = None) -> DetectorProfile:
    """Explicit CLI setup only: fixed source, size bound and digest before use."""
    if profile_id not in PROFILES or (from_file is not None and download):
        raise TrafficDetectionError("Select one supported profile and one weight source.")
    profile = PROFILES[profile_id]
    if profile.requires_agpl_choice and not accept_agpl:
        raise TrafficDetectionError("The optional VisDrone weights require an explicit --accept-agpl selection.")
    if camera_id is not None and not re.fullmatch(r"[A-Za-z0-9_-]{1,120}", camera_id):
        raise TrafficDetectionError("Camera detector identifier is invalid.")
    folder = Path(data_dir) / "models"
    if folder.is_symlink():
        raise TrafficDetectionError("Model storage must be a regular local directory.")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / profile.filename
    config = folder / CONFIG_FILENAME
    if target.is_symlink() or config.is_symlink():
        raise TrafficDetectionError("Live detector files must not be symlinks.")
    previous = _read_selection(data_dir)
    choice = {"profile": profile.id, "weights_sha256": profile.sha256,
              "license": profile.license, "agpl_choice_accepted": bool(profile.requires_agpl_choice and accept_agpl)}
    if camera_id is not None:
        overrides = {**previous.get("camera_profiles", {}), camera_id: choice}
        if len(overrides) > 16:
            raise TrafficDetectionError("At most 16 explicit camera detector selections are supported.")
        record = {**previous, "camera_profiles": overrides}
    else:
        record = {"schema_version": 1, **choice,
                  **({"camera_profiles": previous["camera_profiles"]} if previous.get("camera_profiles") else {})}
    encoded = json.dumps(record, indent=2) + "\n"
    if len(encoded.encode()) > 4096:
        raise TrafficDetectionError("Camera detector selections exceed the configuration size limit.")
    valid_existing = target.is_file() and target.stat().st_size <= MAX_MODEL_BYTES and sha256_file(target) == profile.sha256
    temporary = None
    try:
        if not valid_existing:
            if from_file is None and not download:
                raise TrafficDetectionError("Pinned live weights are missing; use --from-file or explicit --download.")
            if from_file is not None and (from_file.is_symlink() or not from_file.is_file() or from_file.stat().st_size > MAX_MODEL_BYTES):
                raise TrafficDetectionError("The supplied live model must be a bounded regular file.")
            with tempfile.NamedTemporaryFile(dir=folder, suffix=".tmp", delete=False) as output:
                temporary = Path(output.name)
                source = from_file.open("rb") if from_file is not None else urllib.request.urlopen(profile.download_url, timeout=120)
                with source:
                    size = 0
                    while chunk := source.read(1024 * 1024):
                        size += len(chunk)
                        if size > MAX_MODEL_BYTES:
                            raise TrafficDetectionError("Live model download exceeds its size limit.")
                        output.write(chunk)
            if sha256_file(temporary) != profile.sha256:
                raise TrafficDetectionError("Live model checksum does not match the pinned profile.")
            temporary.replace(target)
            temporary = None
        with tempfile.NamedTemporaryFile("w", dir=folder, suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            output.write(encoded)
        temporary.replace(config)
        temporary = None
        return profile
    except TrafficDetectionError:
        raise
    except (OSError, ValueError):
        raise TrafficDetectionError("Could not prepare the selected live detector; the previous configuration was retained.") from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _compatible_dimension(value, expected: int, dynamic: bool) -> bool:
    return (type(value) is int and value == expected) or (dynamic and (value is None or isinstance(value, str) and bool(value)))


def validate_model_io(session, profile: DetectorProfile) -> None:
    inputs, outputs = session.get_inputs(), session.get_outputs()
    if len(inputs) != 1 or len(outputs) != 1 or inputs[0].type != "tensor(float)" or outputs[0].type != "tensor(float)":
        raise TrafficDetectionError("The selected live model has an unsupported tensor interface.")
    input_shape, output_shape = inputs[0].shape, outputs[0].shape
    dynamic = profile.architecture == "yolo11-decoded-channels"
    expected_input = [1, 3, profile.input_size, profile.input_size]
    expected_output = ([1, 8400, 5 + profile.class_count] if not dynamic else [1, 4 + profile.class_count, 8400])
    if (len(input_shape) != 4 or len(output_shape) != 3
            or any(not _compatible_dimension(value, expected, dynamic and index != 1)
                   for index, (value, expected) in enumerate(zip(input_shape, expected_input)))
            or any(not _compatible_dimension(value, expected, dynamic and index != 1)
                   for index, (value, expected) in enumerate(zip(output_shape, expected_output)))):
        raise TrafficDetectionError("The selected live model tensor shape does not match its pinned profile.")


def prepare_input(image, profile: DetectorProfile, cv2, np):
    """Return a model-specific tensor and exact source-to-tensor transform."""
    height, width = image.shape[:2]
    side = profile.input_size
    ratio = min(side / height, side / width)
    centered = profile.architecture == "yolo11-decoded-channels"
    resize = round if centered else int
    resized_width, resized_height = max(1, resize(width * ratio)), max(1, resize(height * ratio))
    offset_x = (side - resized_width) // 2 if centered else 0
    offset_y = (side - resized_height) // 2 if centered else 0
    padded = np.full((side, side, 3), 114, dtype=np.uint8)
    padded[offset_y:offset_y + resized_height, offset_x:offset_x + resized_width] = cv2.resize(
        image, (resized_width, resized_height), interpolation=cv2.INTER_LINEAR)
    if centered:
        padded = padded[:, :, ::-1]
    tensor = np.ascontiguousarray(padded.transpose(2, 0, 1)[None], dtype=np.float32)
    if centered:
        tensor /= 255.0
    return tensor, (ratio, offset_x, offset_y)


class TrafficDetector:
    def __init__(self, weights: Path, profile: DetectorProfile):
        if weights.is_symlink() or not weights.is_file() or weights.stat().st_size > MAX_MODEL_BYTES or sha256_file(weights) != profile.sha256:
            raise TrafficDetectionError("Pinned live weights are missing or invalid; run explicit live detector setup.")
        os.environ["ORT_DISABLE_TELEMETRY"] = "1"
        try:
            import cv2
            import numpy as np
            import onnxruntime as ort
        except ImportError:
            raise TrafficDetectionError("Install the pinned local detection requirements first.") from None
        ort.disable_telemetry_events()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(weights), sess_options=options, providers=["CPUExecutionProvider"])
        validate_model_io(self.session, profile)
        self.profile, self.cv2, self.np = profile, cv2, np
        self.runtime_version = ort.__version__
        self.input_name = self.session.get_inputs()[0].name
        self.grids = np.concatenate([
            np.stack(np.meshgrid(np.arange(profile.input_size // stride), np.arange(profile.input_size // stride)), axis=-1).reshape(-1, 2)
            for stride in (8, 16, 32)
        ])
        self.strides = np.concatenate([np.full(((profile.input_size // stride) ** 2, 1), stride) for stride in (8, 16, 32)])

    def detect(self, image, *, confidence_floor: float | None = None) -> list[dict]:
        np, cv2, profile = self.np, self.cv2, self.profile
        threshold = profile.confidence if confidence_floor is None else confidence_floor
        if (type(threshold) not in (int, float) or not math.isfinite(threshold)
                or not 0.1 <= threshold <= profile.confidence):
            raise TrafficDetectionError("Invalid detector confidence floor.")
        tensor, (ratio, offset_x, offset_y) = prepare_input(image, profile, cv2, np)
        output = self.session.run(None, {self.input_name: tensor})[0]
        expected_shape = ((1, 8400, 5 + profile.class_count) if profile.architecture == "yolox-raw-grid"
                          else (1, 4 + profile.class_count, 8400))
        if output.shape != expected_shape or not np.isfinite(output).all():
            raise TrafficDetectionError("Live model output shape or values are invalid.")
        if profile.architecture == "yolox-raw-grid":
            rows = output[0].copy()
            if np.any(np.abs(rows[:, 2:4]) > 20):
                raise TrafficDetectionError("Live model grid output is invalid.")
            rows[:, :2] = (rows[:, :2] + self.grids) * self.strides
            rows[:, 2:4] = np.exp(rows[:, 2:4]) * self.strides
            probabilities = rows[:, 4:]
            scores = rows[:, 4:5] * rows[:, 5:]
        else:
            rows = output[0].T.copy()
            probabilities = scores = rows[:, 4:]
        if np.any(probabilities < 0) or np.any(probabilities > 1):
            raise TrafficDetectionError("Live model class scores are invalid.")
        display, native = dict(profile.display_classes), dict(profile.native_classes)
        class_ids = np.argmax(scores, axis=1)
        confidence = scores[np.arange(len(rows)), class_ids]
        keep = (confidence >= threshold) & np.isin(class_ids, list(display))
        rows, confidence, class_ids = rows[keep], confidence[keep], class_ids[keep]
        if not len(rows):
            return []
        if np.any(rows[:, 2:4] <= 0):
            raise TrafficDetectionError("Live model box dimensions are invalid.")
        candidates = []
        for row in rows:
            cx, cy, width, height = row[:4]
            candidates.append([float((cx - width / 2 - offset_x) / ratio),
                               float((cy - height / 2 - offset_y) / ratio),
                               float(width / ratio), float(height / ratio)])
        indices = cv2.dnn.NMSBoxes(candidates, confidence.tolist(), threshold, profile.nms_iou)
        image_height, image_width = image.shape[:2]
        boxes = []
        for index in np.asarray(indices).reshape(-1):
            x, y, width, height = candidates[index]
            coordinates = [max(0, min(1, x / image_width)), max(0, min(1, y / image_height)),
                           max(0, min(1, (x + width) / image_width)), max(0, min(1, (y + height) / image_height))]
            if coordinates[0] >= coordinates[2] or coordinates[1] >= coordinates[3]:
                continue
            class_id = int(class_ids[index])
            boxes.append({"class_name": display[class_id], "native_class_name": native[class_id],
                          "confidence": float(confidence[index]),
                          "xyxy": [round(value, 6) for value in coordinates]})
        return sorted(boxes, key=lambda box: -box["confidence"])[:300]
