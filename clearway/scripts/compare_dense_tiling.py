#!/usr/bin/env python3
"""Compare local full-frame and tiled Dense traffic detections; no cloud calls.

Writes development diagnostics under ignored .local by default, never labels
or accuracy measurements. Uses the exact same decoded frames for every mode.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from api.configuration import load_local_environment
from api.detection import sha256_file
from api.tiled_detection import TiledDetector, TilingConfig
from api.traffic_detection import PROFILES, TrafficDetector


class FullFrameFloor:
    def __init__(self, detector, floor):
        self.detector, self.floor = detector, floor

    def detect(self, image):
        return [box for box in self.detector.detect(image) if box["confidence"] >= self.floor]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT.parent / ".local/cctv-quality/dense-tiling")
    parser.add_argument("--tile-sizes", nargs="+", type=int, default=[640, 768, 960])
    args = parser.parse_args()
    load_local_environment()
    data = Path(os.environ.get("CLEARWAY_DATA_DIR", ROOT / "data"))
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    baseline = data / "detections/traffic-jam.json"
    preserved = output / "baseline-full-frame-cache.json"
    if baseline.is_file() and not preserved.exists():
        shutil.copyfile(baseline, preserved)
    profile = PROFILES["yolo11s-visdrone640"]
    detector = TrafficDetector(data / "models" / profile.filename, profile)
    cv2 = detector.cv2
    media = data / "footage/traffic-jam.webm"
    capture = cv2.VideoCapture(str(media))
    frames = []
    targets = iter((1, 4, 8))
    target = next(targets)
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        stamp = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
        if stamp >= target:
            frames.append((stamp, frame))
            target = next(targets, None)
            if target is None:
                break
    capture.release()
    if len(frames) != 3:
        raise RuntimeError("Cannot decode the three fixed comparison frames.")
    strategies = {"full_frame_040": detector, "full_frame_050": FullFrameFloor(detector, .5),
                  **{f"tiled_{size}_050": TiledDetector(detector, TilingConfig(tile_size=size)) for size in args.tile_sizes}}
    detector.detect(frames[0][1])  # One shared warmup before measured runs.
    results = []
    for name, method in strategies.items():
        for stamp, frame in frames:
            started = time.perf_counter()
            boxes = method.detect(frame)
            elapsed = (time.perf_counter() - started) * 1000
            result = {"strategy": name, "timestamp_seconds": stamp, "box_count": len(boxes),
                      "vehicle_count": sum(box["class_name"] != "person" for box in boxes),
                      "person_count": sum(box["class_name"] == "person" for box in boxes),
                      "inference_ms": round(elapsed, 3), "model_passes": getattr(method, "last_passes", 1),
                      "boxes": boxes}
            results.append(result)
            annotated = frame.copy()
            h, w = annotated.shape[:2]
            for box in boxes:
                x1, y1, x2, y2 = box["xyxy"]
                color = (235, 180, 60) if box["class_name"] == "person" else (40, 220, 100)
                cv2.rectangle(annotated, (int(x1*w), int(y1*h)), (int(x2*w), int(y2*h)), color, 2)
            title = f"{name} | {stamp:.3f}s | {len(boxes)} boxes | {elapsed:.0f}ms | development diagnostic"
            cv2.putText(annotated, title, (20, 38), cv2.FONT_HERSHEY_SIMPLEX, .8, (40, 220, 100), 2)
            cv2.imwrite(str(output / f"{round(stamp)}s-{name}.jpg"), annotated)
    metadata = {"source_sha256": sha256_file(media), "model": profile.metadata(detector.runtime_version),
                "configurations": {name: method.config.metadata() if isinstance(method, TiledDetector)
                                   else {"mode": "full_frame", "confidence_threshold": getattr(method, "floor", profile.confidence)}
                                   for name, method in strategies.items()},
                "results": results,
                "note": "Three shared development frames after one warmup. Counts are predictions, not labels, unique vehicles, or accuracy. Inspect false markings, overlaps and missed objects."}
    (output / "comparison.json").write_text(json.dumps(metadata, indent=2) + "\n")
    for name in strategies:
        selected = [item for item in results if item["strategy"] == name]
        print(json.dumps({"strategy": name, "box_counts": [item["box_count"] for item in selected],
                          "median_ms": round(statistics.median(item["inference_ms"] for item in selected), 3),
                          "max_ms": max(item["inference_ms"] for item in selected), "n": len(selected)}))


if __name__ == "__main__":
    main()
