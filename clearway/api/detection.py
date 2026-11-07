"""Pinned local detections for honest, video-synchronized replay overlays.

Preprocessing/grid decoding follows Megvii YOLOX's ONNX example (Apache-2.0,
Copyright (c) Megvii, Inc. and its affiliates). Clearway's implementation adds
normalized output, strict cache provenance and a shadow-only call gate. See
licenses/YOLOX-APACHE-2.0.txt. No provider calls or auto-download happen on reads.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import time
import urllib.request

from .sources import SOURCES, media_path
from .traffic_detection import PROFILES, TrafficDetectionError, TrafficDetector
from .tiled_detection import TiledDetector, TilingConfig, TilingError, tile_regions

MODEL_NAME = "YOLOX-Tiny"
MODEL_VERSION = "0.1.1rc0"
MODEL_URL = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx"
MODEL_SHA256 = "427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7"
PREPROCESSING_VERSION = "yolox-tiny-bgr-top-left-pad-416-nms-v1"
SCHEMA_VERSION = "clearway-detections-v1"
CLASS_NAMES = {0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 5: "bus", 7: "truck"}
VEHICLE_NAMES = frozenset(CLASS_NAMES.values()) - {"person"}
CONFIDENCE = 0.30
NMS_IOU = 0.45
WINDOW_SECONDS = 2.0
MAX_CACHE_BYTES = 20_000_000
# The aerial dense-traffic clip needs the approved traffic-trained detector.
# Other replay sources retain their existing Tiny model and cache contract.
REPLAY_PROFILE_BY_SOURCE = {"traffic-jam": "yolo11s-visdrone640"}
FULL_FRAME_STRATEGY = {"mode": "full_frame", "version": "full-frame-v1"}
DENSE_TILE_SIZES = (640, 768, 960)


def requested_replay_strategy(source_id: str, dense_strategy: str = "tiled", dense_tile_size: int = 768):
    if source_id != "traffic-jam":
        return None
    if dense_strategy == "full-frame":
        return dict(FULL_FRAME_STRATEGY)
    if dense_strategy != "tiled" or dense_tile_size not in DENSE_TILE_SIZES:
        raise DetectionError("Select Dense traffic tiled preparation (640/768/960px) or the full-frame fallback.")
    return TilingConfig(tile_size=dense_tile_size).metadata()


def strategy_digest(strategy: dict) -> str:
    return hashlib.sha256(json.dumps(strategy, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _validated_strategy(provenance: dict, source_id: str) -> TilingConfig | None:
    strategy = provenance.get("inference_strategy")
    if strategy is None:
        return None  # Existing verified full-frame caches remain readable.
    if source_id != "traffic-jam" or provenance.get("inference_strategy_sha256") != strategy_digest(strategy):
        raise ValueError("Replay inference strategy does not match this source.")
    if strategy == FULL_FRAME_STRATEGY:
        return None
    if not isinstance(strategy, dict) or strategy.get("tile_size") not in DENSE_TILE_SIZES:
        raise ValueError("Unsupported replay tiling configuration.")
    config = TilingConfig(tile_size=strategy["tile_size"])
    if strategy != config.metadata():
        raise ValueError("Replay tiling parameters differ from the validated strategy.")
    return config


def replay_profile(source_id: str):
    identifier = REPLAY_PROFILE_BY_SOURCE.get(source_id)
    return PROFILES[identifier] if identifier else None


class DetectionError(ValueError):
    """Authored, safe error for local preparation failures."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_model(data_dir: Path) -> Path:
    """Explicit setup only; fixed official release and verified digest."""
    folder = Path(data_dir) / "models"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "yolox_tiny.onnx"
    if target.is_symlink():
        raise DetectionError("Detector weights must be a regular local file.")
    if target.is_file() and sha256_file(target) == MODEL_SHA256:
        return target
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=folder, suffix=".tmp", delete=False) as output:
            temporary = Path(output.name)
            with urllib.request.urlopen(MODEL_URL, timeout=60) as response:
                size = 0
                while chunk := response.read(1024 * 1024):
                    size += len(chunk)
                    if size > 25_000_000:
                        raise DetectionError("Detector download exceeds its expected size.")
                    output.write(chunk)
        if sha256_file(temporary) != MODEL_SHA256:
            raise DetectionError("Detector checksum does not match the pinned official release.")
        temporary.replace(target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return target


def shadow_gate(frames: list[dict], duration: float) -> dict:
    """Compare a deterministic gate with one VLM request per 2-second window.

    First/heartbeat windows, person presence, and changed vehicle counts pass.
    No road ROI/calibration or congestion baseline is claimed. This diagnostic
    never suppresses the operator's independent Gemini analysis path.
    """
    windows = []
    previous_vehicle_count = None
    for index in range(math.ceil(duration / WINDOW_SECONDS)):
        start, end = index * WINDOW_SECONDS, min((index + 1) * WINDOW_SECONDS, duration)
        samples = [frame for frame in frames if start <= frame["time_seconds"] < end]
        if not samples:
            continue
        vehicles = int(statistics.median(frame["vehicle_count"] for frame in samples))
        people = max(frame["person_count"] for frame in samples)
        if previous_vehicle_count is None:
            reason = "initial sample"
        elif people:
            reason = "person present; review context"
        elif index % 5 == 0:
            reason = "10-second safety heartbeat"
        elif abs(vehicles - previous_vehicle_count) >= 2:
            reason = "vehicle count changed by at least two"
        else:
            reason = "stable vehicle count with no detected person"
        passed = reason != "stable vehicle count with no detected person"
        windows.append({"start_seconds": start, "end_seconds": end, "passed": passed,
                        "reason": reason, "median_vehicle_count": vehicles,
                        "max_person_count": people, "sample_count": len(samples)})
        previous_vehicle_count = vehicles
    passed = sum(window["passed"] for window in windows)
    suppressed = len(windows) - passed
    return {
        "mode": "shadow", "policy": "presence-change-v1", "window_seconds": WINDOW_SECONDS,
        "baseline": "one model call per 2-second window", "evaluated_windows": len(windows),
        "passed_windows": passed, "suppressed_windows": suppressed,
        "estimated_calls_avoided": suppressed, "actual_model_calls": 0,
        "note": "Hypothetical avoided calls against the stated baseline. This gate does not suppress manual Gemini analysis; it is not validated incident recall.",
        "windows": windows,
    }


def _number(value, *, low=0, high=1) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def validate_report(report: dict, source_id: str, source_sha: str) -> bool:
    """Reject malformed/stale/fixture outputs before they reach a video overlay."""
    try:
        if source_id not in SOURCES or report["schema_version"] != SCHEMA_VERSION or report["status"] != "available" or report["source_id"] != source_id:
            return False
        provenance, model = report["provenance"], report["model"]
        tiling = _validated_strategy(provenance, source_id)
        profile = replay_profile(source_id)
        expected_model = ((profile.name, profile.version, profile.sha256) if profile
                          else (MODEL_NAME, MODEL_VERSION, MODEL_SHA256))
        preprocessing = profile.preprocessing_version if profile else PREPROCESSING_VERSION
        confidence = tiling.confidence_floor if tiling else profile.confidence if profile else CONFIDENCE
        nms_iou = profile.nms_iou if profile else NMS_IOU
        classes = set(dict(profile.display_classes).values()) if profile else set(CLASS_NAMES.values())
        vehicle_names = classes - {"person"}
        native_map = ({name: dict(profile.display_classes)[index] for index, name in profile.native_classes}
                      if profile else {})
        if (provenance["kind"] != "local_yolo_cached" or provenance["fixture"] is not False
                or provenance["source_sha256"] != source_sha or provenance["preprocessing_version"] != preprocessing
                or (model["name"], model["version"], model["weights_sha256"]) != expected_model):
            return False
        if profile and (model.get("profile") != profile.id or model.get("license") != profile.license
                        or model.get("input_size") != [profile.input_size, profile.input_size]):
            return False
        if report["confidence_threshold"] != confidence or report["nms_iou"] != nms_iou:
            return False
        duration, fps = report["duration_seconds"], report["sample_fps"]
        if not _number(duration, high=600) or duration <= 0 or not _number(fps, low=1, high=30):
            return False
        if any(type(report[key]) is not int or not 1 <= report[key] <= 16384 for key in ("video_width", "video_height")):
            return False
        if tiling:
            regions = tile_regions(report["video_width"], report["video_height"], tiling)
            if report["processing"]["model_passes_per_sample"] != len(regions) + 1:
                return False
        frames = report["frames"]
        if not isinstance(frames, list) or not frames or len(frames) > 18000:
            return False
        if abs(len(frames) - duration * fps) > 2:
            return False
        if tiling and report["processing"]["model_passes_total"] != (len(regions) + 1) * len(frames):
            return False
        previous = -1
        for frame in frames:
            timestamp, boxes = frame["time_seconds"], frame["boxes"]
            if not _number(timestamp, high=duration) or timestamp <= previous or not isinstance(boxes, list) or len(boxes) > 300:
                return False
            if previous >= 0 and timestamp - previous > 2 / fps:
                return False
            previous = timestamp
            for box in boxes:
                coords = box["xyxy"]
                if (box["class_name"] not in classes or not _number(box["confidence"], low=confidence)
                        or not isinstance(coords, list) or len(coords) != 4 or not all(_number(v) for v in coords)
                        or coords[0] >= coords[2] or coords[1] >= coords[3]):
                    return False
                if profile and "native_class_name" in box:
                    if native_map.get(box["native_class_name"]) != box["class_name"]:
                        return False
            if frame["vehicle_count"] != sum(box["class_name"] in vehicle_names for box in boxes):
                return False
            if frame["person_count"] != sum(box["class_name"] == "person" for box in boxes):
                return False
        return (frames[0]["time_seconds"] < 1 / fps and frames[-1]["time_seconds"] >= duration - 2 / fps
                and report["gate"] == shadow_gate(frames, duration))
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


class DetectionService:
    """Read-only cache service; runtime serving needs only the standard library."""
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self._hashes: dict[tuple, str] = {}

    def get(self, source_id: str) -> dict:
        unavailable = {"status": "unavailable", "source_id": source_id,
                       "message": "Local YOLO detections are not prepared for this footage.",
                       "frames": [], "gate": None}
        media = media_path(self.data_dir, source_id, "video")
        if media is None:
            return unavailable
        cache = self.data_dir / "detections" / f"{source_id}.json"
        if cache.is_symlink() or not cache.is_file() or cache.stat().st_size > MAX_CACHE_BYTES:
            return unavailable
        try:
            stat = media.stat()
            identity = (str(media), stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
            if identity not in self._hashes:
                self._hashes = {identity: sha256_file(media)}
            report = json.loads(cache.read_text())
            if not validate_report(report, source_id, self._hashes[identity]):
                return {**unavailable, "message": "Local YOLO cache does not match this footage or detector configuration."}
            return report
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError):
            return unavailable


class YoloDetector:
    def __init__(self, weights: Path):
        # Recent ONNX wheels initialize their uploader during import. Disable
        # before import, not merely after session creation (official Privacy.md).
        os.environ["ORT_DISABLE_TELEMETRY"] = "1"
        try:
            import cv2
            import numpy as np
            import onnxruntime as ort
        except ImportError:
            raise DetectionError("Install clearway/detection-requirements.txt before preparing detections.") from None
        if weights.is_symlink() or not weights.is_file() or sha256_file(weights) != MODEL_SHA256:
            raise DetectionError("Pinned YOLO weights are missing or invalid; run preparation with --download-model.")
        self.cv2, self.np = cv2, np
        ort.disable_telemetry_events()
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(weights), sess_options=options, providers=["CPUExecutionProvider"])
        self.runtime_version = ort.__version__
        self.input_name = self.session.get_inputs()[0].name
        self.grids, self.strides = [], []
        for stride in (8, 16, 32):
            xs, ys = np.meshgrid(np.arange(416 // stride), np.arange(416 // stride))
            self.grids.append(np.stack((xs, ys), axis=-1).reshape(-1, 2))
            self.strides.append(np.full(((416 // stride) ** 2, 1), stride))
        self.grids = np.concatenate(self.grids)
        self.strides = np.concatenate(self.strides)

    def detect(self, image) -> list[dict]:
        cv2, np = self.cv2, self.np
        height, width = image.shape[:2]
        ratio = min(416 / height, 416 / width)
        resized = cv2.resize(image, (int(width * ratio), int(height * ratio)), interpolation=cv2.INTER_LINEAR)
        padded = np.full((416, 416, 3), 114, dtype=np.uint8)
        padded[:resized.shape[0], :resized.shape[1]] = resized
        tensor = np.ascontiguousarray(padded.transpose(2, 0, 1)[None], dtype=np.float32)
        rows = self.session.run(None, {self.input_name: tensor})[0][0]
        rows[:, :2] = (rows[:, :2] + self.grids) * self.strides
        rows[:, 2:4] = np.exp(rows[:, 2:4]) * self.strides
        all_scores = rows[:, 4:5] * rows[:, 5:]
        class_ids = np.argmax(all_scores, axis=1)
        scores = all_scores[np.arange(len(rows)), class_ids]
        mask = (scores >= CONFIDENCE) & np.isin(class_ids, list(CLASS_NAMES))
        selected, scores, class_ids = rows[mask], scores[mask], class_ids[mask]
        candidates = []
        for row in selected:
            cx, cy, w, h = row[:4] / ratio
            candidates.append([float(cx - w/2), float(cy - h/2), float(w), float(h)])
        if not candidates:
            return []
        # Class-agnostic NMS avoids counting one vehicle as both bus and truck.
        indices = cv2.dnn.NMSBoxes(candidates, scores.tolist(), CONFIDENCE, NMS_IOU)
        boxes = []
        for index in np.asarray(indices).reshape(-1):
            x, y, w, h = candidates[index]
            coords = [max(0, min(1, x / width)), max(0, min(1, y / height)),
                      max(0, min(1, (x+w) / width)), max(0, min(1, (y+h) / height))]
            if coords[0] < coords[2] and coords[1] < coords[3]:
                boxes.append({"class_name": CLASS_NAMES[int(class_ids[index])], "confidence": round(float(scores[index]), 6),
                              "xyxy": [round(value, 6) for value in coords]})
        return sorted(boxes, key=lambda box: -box["confidence"])[:300]


def prepare_detections(data_dir: Path, source_id: str, *, sample_fps: float = 4.0,
                       dense_strategy: str = "tiled", dense_tile_size: int = 768) -> dict:
    if source_id not in SOURCES or not _number(sample_fps, low=1, high=30):
        raise DetectionError("Select a registered source and a sample rate between 1 and 30 fps.")
    media = media_path(data_dir, source_id, "video")
    if media is None:
        raise DetectionError("The registered source footage is not available.")
    profile = replay_profile(source_id)
    strategy = requested_replay_strategy(source_id, dense_strategy, dense_tile_size)
    tiling = TilingConfig(tile_size=dense_tile_size) if strategy and strategy["mode"] == "tiled" else None
    try:
        detector = (TrafficDetector(Path(data_dir) / "models" / profile.filename, profile) if profile
                    else YoloDetector(Path(data_dir) / "models" / "yolox_tiny.onnx"))
    except TrafficDetectionError as error:
        raise DetectionError("Dense traffic requires the pinned local YOLO11s VisDrone weights. "
                             "Install them explicitly before preparing this replay; no download, Tiny fallback, "
                             "or live-camera configuration change was performed. "
                             "setup_live_detector.py --profile yolo11s-visdrone640 --download --accept-agpl "
                             f"also selects the live-camera default. {error}") from None
    if tiling:
        detector = TiledDetector(detector, tiling)
    vehicle_names = (set(dict(profile.display_classes).values()) - {"person"}) if profile else VEHICLE_NAMES
    capture = detector.cv2.VideoCapture(str(media))
    # WebM can advertise a 1000fps time base as avg_frame_rate. Read actual
    # decoded timestamps below and count frames instead of trusting that field.
    try:
        metadata = json.loads(subprocess.run([
            "ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
            "-show_entries", "stream=width,height,r_frame_rate,nb_read_frames:format=duration",
            "-of", "json", str(media),
        ], check=True, capture_output=True, timeout=120).stdout)
        stream = metadata["streams"][0]
        numerator, denominator = stream["r_frame_rate"].split("/")
        fps = float(numerator) / float(denominator)
        width, height = int(stream["width"]), int(stream["height"])
        frame_count, duration = int(stream["nb_read_frames"]), float(metadata["format"]["duration"])
    except (OSError, subprocess.SubprocessError, KeyError, ValueError, IndexError, ZeroDivisionError):
        capture.release()
        raise DetectionError("Cannot probe the registered video metadata with ffprobe.") from None
    if not math.isfinite(fps) or fps <= 0 or min(width, height, frame_count) <= 0:
        capture.release()
        raise DetectionError("Cannot decode the registered video metadata.")
    if not _number(duration, low=0.001, high=600):
        capture.release()
        raise DetectionError("Replay preparation is limited to ten-minute clips.")
    try:
        model_passes = 1 + len(tile_regions(width, height, tiling)) if tiling else 1
    except TilingError as error:
        capture.release()
        raise DetectionError(str(error)) from None
    sample_fps = min(sample_fps, fps)
    source_sha = sha256_file(media)
    started = time.perf_counter()
    frames, latencies = [], []
    frame_index, next_sample_index, previous_timestamp = 0, 0, -1.0
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            timestamp = capture.get(detector.cv2.CAP_PROP_POS_MSEC) / 1000
            if not _number(timestamp, high=duration) or timestamp <= previous_timestamp:
                raise DetectionError("Video timestamps are invalid; detections were not saved.")
            previous_timestamp = timestamp
            if timestamp >= next_sample_index / sample_fps - 0.5 / fps:
                infer_start = time.perf_counter()
                boxes = detector.detect(frame)
                latencies.append((time.perf_counter() - infer_start) * 1000)
                frames.append({"time_seconds": round(timestamp, 6), "boxes": boxes,
                               "vehicle_count": sum(box["class_name"] in vehicle_names for box in boxes),
                               "person_count": sum(box["class_name"] == "person" for box in boxes)})
                next_sample_index += 1
            frame_index += 1
    except (TilingError, TrafficDetectionError) as error:
        raise DetectionError(str(error)) from None
    finally:
        capture.release()
    if frame_index < frame_count - 1 or not frames:
        raise DetectionError("Video decoding ended early; incomplete detections were not saved.")
    if sha256_file(media) != source_sha:
        raise DetectionError("Footage changed during preparation; detections were not saved.")
    report = {
        "schema_version": SCHEMA_VERSION, "status": "available", "source_id": source_id,
        "model": profile.metadata(detector.runtime_version) if profile else {"name": MODEL_NAME, "version": MODEL_VERSION, "weights_sha256": MODEL_SHA256,
                  "license": "Apache-2.0", "source_url": "https://github.com/Megvii-BaseDetection/YOLOX",
                  "runtime": "ONNX Runtime CPU", "runtime_version": detector.runtime_version},
        "provenance": {"kind": "local_yolo_cached", "fixture": False, "generated_at": datetime.now(timezone.utc).isoformat(),
                       "source_sha256": source_sha, "preprocessing_version": profile.preprocessing_version if profile else PREPROCESSING_VERSION},
        "sample_fps": sample_fps, "duration_seconds": duration, "video_width": width, "video_height": height,
        "confidence_threshold": tiling.confidence_floor if tiling else profile.confidence if profile else CONFIDENCE,
        "nms_iou": profile.nms_iou if profile else NMS_IOU, "frames": frames,
        "gate": shadow_gate(frames, duration),
        "processing": {"frame_count": len(frames), "decoded_frames": frame_index,
                       "wall_seconds": round(time.perf_counter() - started, 4),
                       "inference_median_ms": round(statistics.median(latencies), 3),
                       "inference_max_ms": round(max(latencies), 3), "latency_n": len(latencies)},
        "limitations": ["Cached local detections replay at their sampled video timestamps; this is not live camera inference.",
                        "Object detections can be wrong and do not establish injury, obstruction, or road-lane membership.",
                        "No calibrated road ROI or normal-traffic baseline; gate savings are a shadow comparison, not billed savings."],
    }
    if strategy:
        report["provenance"].update(inference_strategy=strategy, inference_strategy_sha256=strategy_digest(strategy))
        report["processing"].update(model_passes_per_sample=model_passes, model_passes_total=model_passes * len(frames))
        if tiling:
            report["limitations"].append("Full-frame plus overlapping original-pixel crops are merged offline. Tiles can add false detections; markings, occlusion and adjacent vehicles remain ambiguous.")
    if not validate_report(report, source_id, source_sha):
        raise DetectionError("Generated detector output failed validation; it was not saved.")
    folder = Path(data_dir) / "detections"
    folder.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=folder, suffix=".tmp", delete=False) as stream:
        json.dump(report, stream, separators=(",", ":"), allow_nan=False)
        temporary = Path(stream.name)
    temporary.replace(folder / f"{source_id}.json")
    return report
