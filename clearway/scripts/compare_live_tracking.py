#!/usr/bin/env python3
"""Bounded offline development comparison; no downloads, alerts, or labels.

Use an already permitted short CCTV segment. The benchmark samples the same
640x480/JPEG80 input used for Fremont in the browser and compares raw detections
with ByteTrack's current observed boxes. Track continuity is diagnostic only;
this script does not calculate accuracy/IDF1 without ground-truth annotations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--camera-id", default="caltrans-d4-49")
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).resolve().parents[1] / "data")
    parser.add_argument("--seconds", type=float, default=10)
    args = parser.parse_args()
    if not 0 < args.seconds <= 30:
        parser.error("Use a bounded segment of at most 30 seconds.")
    import cv2
    from api.live_detection import LiveDetectionService
    from api.live_tracking import LiveTrackingService

    args.output.mkdir(parents=True, exist_ok=True)
    ticks = [100.0]
    detector = LiveDetectionService(args.data_dir)
    tracker = LiveTrackingService(monotonic=lambda: ticks[0])
    high_only_tracker = LiveTrackingService(monotonic=lambda: ticks[0])
    context = {"run_id": str(uuid4()), "camera_id": args.camera_id, "stream_id": str(uuid4())}
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise SystemExit("Could not decode the selected local segment.")
    rows, next_time, first_time = [], 0.0, None
    video = cv2.VideoWriter(str(args.output / "comparison.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 6, (1280, 510))
    snapshots = {1, 3, 5, 7, 9}
    try:
        while True:
            ok, source = capture.read()
            if not ok:
                break
            position = capture.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if first_time is None:
                first_time = position
            position -= first_time
            if position >= args.seconds:
                break
            if position + 0.00001 < next_time:
                continue
            next_time += 1 / 6
            # Fremont's 704x480 coded frame has 10:11 SAR: the browser's
            # maximum-640x480 capture becomes exactly 640x480 display pixels.
            image = cv2.resize(source, (640, 480))
            ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                raise RuntimeError("Frame encoding failed")
            raw = encoded.tobytes()
            baseline = detector.analyze_jpeg(raw, args.camera_id)
            result = detector.analyze_jpeg(raw, args.camera_id, tracking=True)
            if result["status"] != "available" or baseline["boxes"] != result["boxes"]:
                raise AssertionError("Tracking changed the high-confidence detector result")
            ticks[0] = 100 + position
            current_context = {**context, "media_time_seconds": position}
            start = time.perf_counter()
            tracked = tracker.process(current_context, result)
            tracking_ms = (time.perf_counter() - start) * 1000
            ablation = high_only_tracker.process(current_context, {**result, "tracking_candidates": result["boxes"]})
            if tracked["status"] != "available":
                raise RuntimeError(f"Tracking unavailable: {tracked}")
            tracks = tracked["tracks"]
            # Every returned box must be an actual observation in this image.
            for track in tracks:
                if not any(all(track[key] == candidate[key] for key in ("class_name", "confidence", "xyxy"))
                           for candidate in result["tracking_candidates"]):
                    raise AssertionError("Tracker emitted a prediction-only observation")
            rows.append({"media_time_seconds": round(position, 6), "image_sha256": result["image_sha256"],
                         "raw_boxes": result["boxes"], "tracks": tracks, "high_only_tracks": ablation["tracks"],
                         "inference_ms": result["inference_ms"], "tracking_ms": round(tracking_ms, 3),
                         "reset_reason": tracked.get("reset_reason")})
            left, right = image.copy(), image.copy()
            for canvas, boxes in ((left, result["boxes"]), (right, tracks)):
                for box in boxes:
                    x1, y1, x2, y2 = [round(value * scale) for value, scale in zip(box["xyxy"], (640, 480, 640, 480))]
                    recovered = box.get("observation") == "low_recovery"
                    color = (0, 210, 255) if recovered else (70, 230, 90)
                    cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 1)
                    if "track_id" in box:
                        cv2.putText(canvas, box["track_id"].rsplit("-", 1)[-1], (x1, max(10, y1 - 2)), cv2.FONT_HERSHEY_SIMPLEX, .3, color, 1)
            comparison = cv2.hconcat([left, right])
            comparison = cv2.copyMakeBorder(comparison, 30, 0, 0, 0, cv2.BORDER_CONSTANT, value=(25, 25, 25))
            cv2.putText(comparison, f"Fremont {position:.2f}s | Raw high-confidence: {len(result['boxes'])}", (8, 20), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)
            cv2.putText(comparison, f"ByteTrack: {len(tracks)} current observations | yellow = low recovery", (650, 20), cv2.FONT_HERSHEY_SIMPLEX, .4, (255, 255, 255), 1)
            video.write(comparison)
            bucket = int(position)
            if bucket in snapshots:
                cv2.imwrite(str(args.output / f"frame-{bucket}s.jpg"), comparison)
                snapshots.remove(bucket)
    finally:
        capture.release()
        video.release()
    histories = {}
    for index, row in enumerate(rows):
        for track in row["tracks"]:
            histories.setdefault(track["track_id"], []).append((index, track["observation"]))
    recovered_ids = {key for key, history in histories.items() if any(kind == "low_recovery" for _, kind in history)}
    bridged = sum(any(kind == "low_recovery" and any(k == "high" for _, k in history[:i])
                      and any(k == "high" for _, k in history[i + 1:]) for i, (_, kind) in enumerate(history))
                  for history in histories.values())
    summary = {"camera_id": args.camera_id, "segment_sha256": hashlib.sha256(args.video.read_bytes()).hexdigest(),
               "frames": len(rows), "sample_fps": 6, "capture": "640x480 JPEG quality80; Fremont SAR corrected",
               "raw_high_observations": sum(len(row["raw_boxes"]) for row in rows),
               "tracked_observations": sum(len(row["tracks"]) for row in rows),
               "low_recovered_observations": sum(track["observation"] == "low_recovery" for row in rows for track in row["tracks"]),
               "ids_with_low_recovery": len(recovered_ids), "ids_with_high_low_high_sequence": bridged,
               "raw_high_boxes_unchanged_every_frame": True, "prediction_only_boxes": 0,
               "inference_ms": {"median": statistics.median(row["inference_ms"] for row in rows), "max": max(row["inference_ms"] for row in rows)},
               "tracking_ms": {"median": statistics.median(row["tracking_ms"] for row in rows), "max": max(row["tracking_ms"] for row in rows)},
               "limitations": "Development diagnostics on one short segment. No human identity labels; not accuracy, recall, IDF1, or unique-vehicle counts."}
    (args.output / "results.json").write_text(json.dumps({"summary": summary, "frames": rows}, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
