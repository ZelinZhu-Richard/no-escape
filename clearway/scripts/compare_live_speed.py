#!/usr/bin/env python3
"""Bounded offline TVA43 diagnostic, not a ground-truth speed accuracy test.

Uses an already permitted local <=12s clip, installed detector weights, the
actual ByteTrack service and TypeScript speed estimator. No network calls,
model downloads, app database, alerts, or paid inference. Node22+ is required.
--compare-baseline replays the EXACT same detector results with the TVA43
geometry recovery disabled. --replay-observations skips model inference by
reusing a previous observations.json (including its full high/low pool).
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import sys
import time
from unittest.mock import patch
from uuid import uuid4

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))
CAMERA_ID = "caltrans-d4-285"


def collect_observations(args):
    import cv2
    from api.live_detection import LiveDetectionService

    detector = LiveDetectionService(args.data_dir)
    identity = {"cameraId": CAMERA_ID, "runId": str(uuid4()), "streamId": str(uuid4())}
    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise SystemExit("Could not decode the local TVA43 sample.")
    rows, next_time, first_time = [], 0.0, None
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
            if position + .00001 < next_time:
                continue
            next_time += 1 / args.fps
            height, width = source.shape[:2]
            if abs(width / height / 1.5 - 1) > .02:
                raise SystemExit("This diagnostic requires TVA43's observed square-pixel 3:2 view.")
            scale = min(1, 640 / width, 480 / height)
            image = cv2.resize(source, (round(width * scale), round(height * scale)))
            ok, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ok:
                raise RuntimeError("Frame encoding failed")
            result = detector.analyze_jpeg(encoded.tobytes(), CAMERA_ID, tracking=True)
            if result["status"] != "available":
                raise RuntimeError("Installed local detector unavailable; no fallback model downloaded.")
            frame = {
                **identity, "configurationHash": result["provenance"]["configuration_sha256"],
                "imageHash": result["image_sha256"], "mediaTime": position,
                "imageWidth": result["image_width"], "imageHeight": result["image_height"],
            }
            rows.append({"frame": frame, "raw_boxes": len(result["boxes"]),
                         "inference_ms": result["inference_ms"], "detector_result": result})
    finally:
        capture.release()
    return rows


def replay_tracking(rows, *, baseline=False):
    import api.live_tracking as tracking_module

    tick = [100.0]
    tracker = tracking_module.LiveTrackingService(monotonic=lambda: tick[0])
    output = []
    # This standalone diagnostic process patches only the camera eligibility,
    # preserving the actual validation/reset/high/low/tentative ByteTrack path.
    # The normal and baseline passes both consume the entire identical pool.
    context = patch.object(tracking_module, "GEOMETRY_CAMERA_ID", "diagnostic-disabled") if baseline else nullcontext()
    with context:
        for row in rows:
            frame = row["frame"]
            tick[0] = 100 + frame["mediaTime"]
            context = {"run_id": frame["runId"], "camera_id": frame["cameraId"],
                       "stream_id": frame["streamId"], "media_time_seconds": frame["mediaTime"]}
            start = time.perf_counter()
            result = tracker.process(context, row["detector_result"])
            elapsed = (time.perf_counter() - start) * 1000
            if result["status"] != "available":
                raise RuntimeError("Cached detector input failed tracking validation")
            output.append({**row, "frame": {**frame, "tracks": result["tracks"], "resetReason": result["reset_reason"]},
                           "tracking_ms": round(elapsed, 3), "association_policy": result["association_policy"],
                           "geometry_recoveries": result["geometry_recoveries"]})
    return output


def estimate_speed(frame_path):
    script = """
import fs from 'node:fs';
import {pathToFileURL} from 'node:url';
const [source, preset, frames] = process.argv.slice(1);
const {RoadSpeedEstimator, projectRoadPoint} = await import(pathToFileURL(source).href);
const {TVA43_CALIBRATION} = await import(pathToFileURL(preset).href);
const estimator = new RoadSpeedEstimator(TVA43_CALIBRATION);
const rows = JSON.parse(fs.readFileSync(frames, 'utf8'));
const reasons = {}, speeds = [], ids = new Set(), output = [], zoneIds = new Set(), confirmedIds = new Set();
let zone = 0, confirmed = 0;
for (const row of rows) {
  const result = estimator.update(row.frame);
  for (const [id, value] of Object.entries(result)) {
    reasons[value.reason] = (reasons[value.reason] ?? 0) + 1;
    if (value.mph !== null) { speeds.push(value.mph); ids.add(id); }
  }
  for (const track of row.frame.tracks) {
    const b = track.xyxy;
    if (track.observation !== 'high' || !projectRoadPoint(TVA43_CALIBRATION, [(b[0]+b[2])/2,b[3]])) continue;
    zone++; zoneIds.add(track.track_id);
    if (track.confirmed) { confirmed++; confirmedIds.add(track.track_id); }
  }
  output.push({mediaTime:row.frame.mediaTime, estimates:result});
}
console.log(JSON.stringify({calibration:TVA43_CALIBRATION, reasons,
  estimate_observations:speeds.length, ids_with_estimates:ids.size,
  mph_range:speeds.length ? [Math.min(...speeds),Math.max(...speeds)] : null,
  in_zone_high_observations:zone, in_zone_ids:zoneIds.size,
  in_zone_confirmed_observations:confirmed, in_zone_confirmed_ids:confirmedIds.size,
  rows:output}));
"""
    node = subprocess.run(["node", "--experimental-strip-types", "--input-type=module", "-e", script,
                           str(APP_ROOT / "web/src/liveSpeed.ts"), str(APP_ROOT / "web/src/trafficSpeedCalibration.ts"),
                           str(frame_path.resolve())], check=True, text=True, capture_output=True)
    return json.loads(node.stdout)


def summarize(rows, speed):
    return {
        "frames": len(rows), "raw_high_observations": sum(row["raw_boxes"] for row in rows),
        "tracked_observations": sum(len(row["frame"]["tracks"]) for row in rows),
        "geometry_recoveries": sum(row["geometry_recoveries"] for row in rows),
        "association_policy": rows[0]["association_policy"],
        **{key: speed[key] for key in ("estimate_observations", "ids_with_estimates", "mph_range",
             "in_zone_high_observations", "in_zone_ids", "in_zone_confirmed_observations", "in_zone_confirmed_ids")},
        "unknown_and_estimate_reasons": speed["reasons"],
        "tracking_ms": {"median": statistics.median(row["tracking_ms"] for row in rows),
                        "max": max(row["tracking_ms"] for row in rows)},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=12)
    parser.add_argument("--fps", type=float, default=6)
    parser.add_argument("--data-dir", type=Path, default=APP_ROOT / "data")
    parser.add_argument("--replay-observations", type=Path)
    parser.add_argument("--compare-baseline", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.seconds <= 12:
        parser.error("Use a bounded sample from 1 to 12 seconds.")
    if not 1 <= args.fps <= 8:
        parser.error("Sample within the runtime limit of 1 to 8 frames per second.")
    args.output.mkdir(parents=True, exist_ok=True)
    rows = json.loads(args.replay_observations.read_text()) if args.replay_observations else collect_observations(args)
    if not isinstance(rows, list) or not 1 <= len(rows) <= 96:
        raise SystemExit("Use 1–96 bounded sample observations")
    if (rows[0]["frame"]["mediaTime"] < 0 or rows[-1]["frame"]["mediaTime"] >= args.seconds
            or any(row["frame"]["cameraId"] != CAMERA_ID for row in rows)
            or any(a["frame"]["mediaTime"] >= b["frame"]["mediaTime"] for a, b in zip(rows, rows[1:]))):
        raise SystemExit("Expected bounded, ordered TVA43 sample timestamps")
    rows = replay_tracking(rows)
    frame_path = args.output / "observations.json"
    frame_path.write_text(json.dumps(rows, indent=2) + "\n")
    speed = estimate_speed(frame_path)
    (args.output / "speed-estimates.json").write_text(json.dumps(speed, indent=2) + "\n")
    summary = {
        **summarize(rows, speed), "camera_id": CAMERA_ID, "sample_fps": args.fps,
        "last_media_time_seconds": rows[-1]["frame"]["mediaTime"],
        "video_sha256": hashlib.sha256(args.video.read_bytes()).hexdigest(),
        "detector_input": [rows[0]["frame"]["imageWidth"], rows[0]["frame"]["imageHeight"]],
        "model": rows[0]["detector_result"]["model"],
        "inference_mode": "saved_observations_no_inference" if args.replay_observations else "local_model",
        "recorded_inference_ms": {"median": statistics.median(row["inference_ms"] for row in rows),
                                  "max": max(row["inference_ms"] for row in rows)},
        "calibration_revision": speed["calibration"]["revision"], "calibration_basis": speed["calibration"]["basis"],
        "limitations": "One short development clip; assumed road scale and no surveyed calibration or known vehicle speeds. Estimate counts/range are not accuracy, recall, unique-vehicle counts, or proof of correct speed.",
    }
    if args.compare_baseline:
        baseline = replay_tracking(rows, baseline=True)
        baseline_path = args.output / "baseline-observations.json"
        baseline_path.write_text(json.dumps(baseline, indent=2) + "\n")
        baseline_speed = estimate_speed(baseline_path)
        (args.output / "baseline-speed-estimates.json").write_text(json.dumps(baseline_speed, indent=2) + "\n")
        summary["baseline_geometry_disabled"] = summarize(baseline, baseline_speed)
        summary["comparison"] = "Same image hashes, timestamps, configuration, threshold and full detector high/low pool; only TVA43 geometric recovery eligibility differs."
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
