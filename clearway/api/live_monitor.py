"""Conservative, image-space live review candidates; never an emergency verdict.

No frames are retained here. Each selected stream keeps at most 100 short-lived
box tracks and 256 hashes. Missing matches end a track. Vehicles must stay near
their first box (IoU >= .70 and center drift <= .015 normalized image units) for
12 seconds and 12 distinct frames. People need adjacent IoU >= .30, center step
<= .06, 3 seconds and 5 distinct frames. Counts/density alone never trigger.
Both media time and server monotonic time must reach the duration threshold.
These development rules are not calibrated lane, injury, or hazard detection.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import math
import threading
import time
from uuid import UUID

from .live_cameras import PROVIDER_URL, TERMS_URL
from .live_detection import jpeg_dimensions
from .store import StateError

MAX_STREAMS = 20
MAX_TRACKS = 100
MAX_HASHES = 256
MAX_GAP_SECONDS = 2.0
MAX_CLOCK_STEP_DIFFERENCE = 0.75
RULE_VERSION = "clearway-live-temporal-v1"
VEHICLES = frozenset({"bicycle", "car", "motorcycle", "bus", "truck", "van", "tricycle", "awning-tricycle"})
RULES = {
    "possible_stationary_vehicle": {"seconds": 12.0, "frames": 12, "confidence": 0.50,
                                    "min_area": 0.001, "min_iou": 0.70, "max_center_drift": 0.015},
    "sustained_person_visible": {"seconds": 3.0, "frames": 5, "confidence": 0.55,
                                 "min_area": 0.0005, "min_iou": 0.30, "max_center_step": 0.06},
}


def monitor_status(phase: str, message: str, seconds: float = 0, incident_id: str | None = None) -> dict:
    return {"phase": phase, "observed_seconds": round(max(0.0, seconds), 3),
            "incident_id": incident_id, "message": message}


def parse_monitor_headers(headers) -> tuple[str, str, float] | None:
    values = [headers.get(name) for name in ("x-clearway-run-id", "x-clearway-stream-id", "x-clearway-media-time")]
    if all(value is None for value in values):
        return None
    if any(value is None or len(value) > 80 for value in values):
        raise ValueError("All three live-monitor headers are required.")
    try:
        run, stream = str(UUID(values[0])), str(UUID(values[1]))
        media = float(values[2])
        if not math.isfinite(media) or not 0 <= media <= 1_000_000_000:
            raise ValueError()
        return run, stream, media
    except (ValueError, TypeError, AttributeError):
        raise ValueError("Live-monitor headers must contain two UUIDs and a finite, nonnegative media time.") from None


def _iou(first, second) -> float:
    intersection = max(0, min(first[2], second[2]) - max(first[0], second[0])) * max(0, min(first[3], second[3]) - max(first[1], second[1]))
    union = (first[2] - first[0]) * (first[3] - first[1]) + (second[2] - second[0]) * (second[3] - second[1]) - intersection
    return intersection / union if union > 0 else 0


def _distance(first, second) -> float:
    return math.hypot((first[0] + first[2] - second[0] - second[2]) / 2,
                      (first[1] + first[3] - second[1] - second[3]) / 2)


def _eligible_boxes(result: dict) -> list[dict]:
    output = []
    boxes = result.get("boxes")
    if not isinstance(boxes, list) or len(boxes) > 300:
        raise ValueError("Invalid detector boxes")
    for box in boxes:
        name = box.get("class_name")
        rule = "sustained_person_visible" if name == "person" else "possible_stationary_vehicle" if name in VEHICLES else None
        if rule is None:
            continue
        coords, confidence = box.get("xyxy"), box.get("confidence")
        if (not isinstance(coords, list) or len(coords) != 4
                or any(type(x) not in (int, float) or not math.isfinite(x) or not 0 <= x <= 1 for x in coords)
                or coords[0] >= coords[2] or coords[1] >= coords[3]
                or type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise ValueError("Invalid detector boxes")
        limits = RULES[rule]
        area = (coords[2] - coords[0]) * (coords[3] - coords[1])
        if confidence >= limits["confidence"] and area >= limits["min_area"]:
            output.append({"rule": rule, "class_name": name, "xyxy": list(coords), "confidence": confidence})
    return sorted(output, key=lambda b: -b["confidence"])[:MAX_TRACKS]


class LiveAlertMonitor:
    def __init__(self, store, *, monotonic=None, clock=None):
        self.store = store
        self._monotonic = monotonic or time.monotonic
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()
        self._streams: OrderedDict[tuple[str, str, str], dict] = OrderedDict()

    def reset(self):
        with self._lock:
            self._streams.clear()

    def observe(self, run_id: str, camera: dict, stream_id: str, media_time: float,
                raw: bytes, detections: dict) -> dict:
        """Never let monitoring failures interrupt genuine detection overlays."""
        try:
            with self._lock:
                return self._observe(run_id, camera, stream_id, media_time, raw, detections)
        except StateError as error:
            with self._lock:
                self._streams.pop((run_id, camera.get("id"), stream_id), None)
            return monitor_status("unavailable", error.detail)
        except Exception:
            with self._lock:
                self._streams.pop((run_id, camera.get("id"), stream_id), None)
            return monitor_status("unavailable", "Live review monitoring is unavailable; detection boxes remain separate.")

    def _observe(self, run_id, camera, stream_id, media_time, raw, detections):
        camera_id = camera["id"]
        existing = self.store.live_candidate(run_id, camera_id)
        if existing:
            status = existing["review_status"]
            return monitor_status("candidate", f"This camera already has a {status} review item in this run; reset to monitor again.",
                                  existing["live_evidence"]["window_seconds"], existing["id"])
        key = (run_id, camera_id, stream_id)
        # A camera/stream switch cannot stitch observations together. Old runs
        # and alternate streams for the same camera are not retained.
        for other in list(self._streams):
            if other[0] != run_id or (other[1] == camera_id and other != key):
                del self._streams[other]
        tick = self._monotonic()
        image_hash = hashlib.sha256(raw).hexdigest()
        provenance = detections.get("provenance", {})
        genuine = (detections.get("status") == "available" and detections.get("analysis_mode") in ("fresh", "cached")
                   and detections.get("image_sha256") == image_hash and detections.get("camera_id") == camera_id
                   and provenance.get("fixture") is False and provenance.get("kind") == "local_yolo_image"
                   and provenance.get("image_sha256") == image_hash)
        if not genuine:
            self._streams.pop(key, None)
            return monitor_status("unavailable", "A genuine detection for this exact camera frame is required; monitoring restarts.")
        jpeg_dimensions(raw)
        if not math.isfinite(media_time) or media_time < 0:
            raise ValueError("Invalid media time")
        configuration = provenance.get("configuration_sha256")
        if not isinstance(configuration, str) or len(configuration) != 64:
            raise ValueError("Missing detector configuration")
        model = detections.get("model")
        if not isinstance(model, dict) or not isinstance(model.get("name"), str) or not model.get("weights_sha256"):
            raise ValueError("Missing actual model provenance")
        boxes = _eligible_boxes(detections)
        state = self._streams.get(key)
        restarted = False
        if state:
            delta_media, delta_wall = media_time - state["media"], tick - state["tick"]
            if (configuration != state["configuration"] or delta_media <= 0 or delta_wall <= 0
                    or delta_media > MAX_GAP_SECONDS or delta_wall > MAX_GAP_SECONDS
                    or abs(delta_media - delta_wall) > MAX_CLOCK_STEP_DIFFERENCE):
                state = None
                restarted = True
        if state is None:
            state = {"media": media_time, "tick": tick, "configuration": configuration,
                     "hashes": deque(maxlen=MAX_HASHES), "tracks": []}
        self._streams[key] = state
        self._streams.move_to_end(key)
        while len(self._streams) > MAX_STREAMS:
            self._streams.popitem(last=False)
        if image_hash in state["hashes"]:
            state["tracks"] = []
            return monitor_status("warming", "Repeated image bytes do not count as continuing observation; waiting for distinct frames.")
        state["hashes"].append(image_hash)
        previous = state["tracks"]
        pairs = []
        for old_index, track in enumerate(previous):
            for new_index, box in enumerate(boxes):
                if track["class_name"] != box["class_name"]:
                    continue
                limits = RULES[box["rule"]]
                adjacent_iou = _iou(track["xyxy"], box["xyxy"])
                if adjacent_iou < limits["min_iou"]:
                    continue
                if box["rule"] == "possible_stationary_vehicle":
                    if (_iou(track["anchor"], box["xyxy"]) < limits["min_iou"]
                            or _distance(track["anchor"], box["xyxy"]) > limits["max_center_drift"]):
                        continue
                elif _distance(track["xyxy"], box["xyxy"]) > limits["max_center_step"]:
                    continue
                pairs.append((adjacent_iou, old_index, new_index))
        used_old, matches = set(), {}
        for _, old_index, new_index in sorted(pairs, reverse=True):
            if old_index not in used_old and new_index not in matches:
                used_old.add(old_index)
                matches[new_index] = previous[old_index]
        tracks = []
        for index, box in enumerate(boxes):
            prior = matches.get(index)
            if prior is None:
                track = {**box, "anchor": box["xyxy"], "start_media": media_time, "start_tick": tick,
                         "frames": 1, "minimum_confidence": box["confidence"], "max_center_drift": 0.0}
            else:
                track = {**prior, **box, "frames": prior["frames"] + 1,
                         "minimum_confidence": min(prior["minimum_confidence"], box["confidence"]),
                         "max_center_drift": max(prior["max_center_drift"], _distance(prior["anchor"], box["xyxy"]))}
            track["seconds"] = min(media_time - track["start_media"], tick - track["start_tick"])
            tracks.append(track)
        state.update(tracks=tracks, media=media_time, tick=tick)
        candidates = [track for track in tracks if track["seconds"] >= RULES[track["rule"]]["seconds"]
                      and track["frames"] >= RULES[track["rule"]]["frames"]]
        if candidates:
            winner = max(candidates, key=lambda t: (t["rule"] == "sustained_person_visible", t["seconds"]))
            candidate, source = self._candidate(camera, stream_id, media_time, winner, detections)
            incident = self.store.add_live_candidate(run_id, camera_id, candidate, source, raw)
            state["tracks"] = []
            return monitor_status("candidate", "Live evidence is ready for human review; no danger or emergency is established.",
                                  winner["seconds"], incident["id"])
        observed = max((track["seconds"] for track in tracks), default=0.0)
        if not tracks:
            return monitor_status("watching", "Watching distinct live frames; no sustained review cue. Traffic density alone does not alert.")
        message = "Observation restarted after a timing gap or stream discontinuity." if restarted else "Checking persistence across distinct frames; no candidate yet."
        return monitor_status("warming", message, observed)

    def _candidate(self, camera, stream_id, media_time, track, detections):
        rule, seconds, frames = track["rule"], round(track["seconds"], 3), track["frames"]
        stationary = rule == "possible_stationary_vehicle"
        title = "Possible stationary vehicle · review" if stationary else "Sustained person visible · review"
        summary = (f"A {track['class_name']} box stayed within the image-space stationary limits for {seconds:g} seconds across {frames} distinct sampled frames."
                   if stationary else f"A person box remained matched for {seconds:g} seconds across {frames} distinct sampled frames.")
        location = {"latitude": camera["latitude"], "longitude": camera["longitude"], "quality": "known_camera",
                    "label": f"{camera['name']} · camera position, not object location"}
        observed_at = self._clock().isoformat()
        source = {"id": camera["id"], "title": f"Live CCTV · {camera['name']}", "source_mode": "live",
                  "video_url": "", "poster_url": "", "duration_seconds": 0, "media_available": False,
                  "poster_available": True, "control_status": "live", "capture_time": None, "location": location,
                  "attribution": {"creator": "California Department of Transportation / Caltrans", "title": camera["name"],
                                  "source_url": PROVIDER_URL, "license": "Caltrans conditions of use", "license_url": TERMS_URL}}
        candidate = {
            "title": title, "category": rule, "source_mode": "live", "analysis_mode": "fresh",
            "evidence": [{"timestamp_seconds": media_time, "observation": summary}],
            "unknowns": ["A review cue is not a confirmed obstruction, emergency, or need for dispatch.",
                         "Lane membership, injury, intent, and danger are not inferred.",
                         "Camera coordinates locate the camera, not the detected object.",
                         "Provider capture time and live-stream delay are unknown; observed_at is server observation time.",
                         "Image-space stationarity can reflect a normal queue, parking, camera motion, or a false detection." if stationary
                         else "Person visibility may be ordinary pedestrian activity or a false detection; no identity is inferred."],
            "context_status": "camera_metadata_only", "location": location,
            "provenance": {"provider": "local_yolo_temporal_rule", "model": detections["model"]["name"],
                           "fixture": False, "cache_key": detections["image_sha256"],
                           "image_sha256": detections["image_sha256"], "detector": deepcopy(detections["model"]),
                           "configuration_sha256": detections["provenance"]["configuration_sha256"],
                           "rule": rule, "rule_version": RULE_VERSION, "rule_thresholds": RULES[rule],
                           "stream_id": stream_id, "distinct_frames": frames,
                           "observed_seconds": seconds, "minimum_confidence": track["minimum_confidence"],
                           "max_center_drift": round(track["max_center_drift"], 6)},
            "live_evidence": {"image_url": "", "observed_at": observed_at, "media_time_seconds": media_time,
                              "window_seconds": seconds, "rule": rule, "summary": summary,
                              "detections": deepcopy(detections)},
        }
        return candidate, source
