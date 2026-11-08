"""Bounded ByteTrack association for current public-camera observations only.

Adapted from the MIT ByteTrack core by Yifu Zhang, pinned at
d1bf0191adff59bc8fcfeaa0b33d3d1642552a99:
https://github.com/ifzhang/ByteTrack/tree/d1bf0191adff59bc8fcfeaa0b33d3d1642552a99/yolox/tracker
See licenses/BYTETRACK-MIT.txt for the full upstream notice and adaptation notes.

The official XYAH Kalman model, score-fused high association, low-score second
association, tentative confirmation and lost-track high-score recovery are
retained. NumPy minimum-cost assignment replaces LAP; classes never associate.
Time-scaled prediction and short media/wall TTLs replace video-frame buffers.
Prediction is INTERNAL ONLY: every returned coordinate/score is an actual
observation in this frame. Unmatched high observations remain visible while
tentative; unmatched low observations and prediction-only tracks never appear.
Raw detector boxes and incident-monitor inputs are never changed.

TVA43 alone adds a sparse-frame recovery after normal high-score association:
current high observations may uniquely match a recently observed active or
tentative vehicle using bounded center/size/overlap gates and two-way ambiguity
margins. Lost tracks and low observations cannot enter this recovery. The
camera-specific policy and count are explicit in response provenance.

process(context, detections): context has run_id, camera_id, stream_id,
media_time_seconds. detections is an exact-image local result with a bounded
tracking_candidates pool (all post-NMS observations >= .1), raw high boxes,
confidence_threshold, dimensions, and image/configuration provenance hashes.
No model download, persistence, image bytes, or persistent identity is used.
Importing this module does not require the optional NumPy runtime.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
import math
import re
import threading
import time
from uuid import UUID, uuid4

SCHEMA_VERSION = "clearway-live-tracking-v1"
UPSTREAM_COMMIT = "d1bf0191adff59bc8fcfeaa0b33d3d1642552a99"
MAX_SESSIONS = 20
MAX_CANDIDATES = 300
MAX_TRACKS = 300
MAX_HASHES = 128
MAX_FRAME_GAP_SECONDS = 1.0
MAX_CLOCK_STEP_DIFFERENCE = 0.5
LOST_TTL_SECONDS = 0.75
SESSION_TTL_SECONDS = 3.0
LOW_THRESHOLD = 0.1
GEOMETRY_CAMERA_ID = "caltrans-d4-285"
GEOMETRY_POLICY = "bytetrack-tva43-gated-geometry-v1"
GEOMETRY_MAX_GAP = .25
GEOMETRY_MAX_DISTANCE = .65
GEOMETRY_MIN_MARGIN = .15
GEOMETRY_CLASSES = frozenset({"car", "truck", "bus", "van", "motorcycle"})
CLASSES = frozenset({"person", "bicycle", "car", "motorcycle", "bus", "truck", "van", "tricycle", "awning-tricycle"})
_HASH = re.compile(r"[a-f0-9]{64}")
_CAMERA = re.compile(r"[A-Za-z0-9_-]{1,120}")


def _number(value, low=0.0, high=1.0):
    return type(value) in (int, float) and math.isfinite(value) and low <= value <= high


def _box(raw):
    if not isinstance(raw, dict) or raw.get("class_name") not in CLASSES:
        raise ValueError("Invalid observation class")
    coords, confidence = raw.get("xyxy"), raw.get("confidence")
    if (not _number(confidence, LOW_THRESHOLD) or not isinstance(coords, list) or len(coords) != 4
            or not all(_number(n) for n in coords) or coords[0] >= coords[2] or coords[1] >= coords[3]):
        raise ValueError("Invalid observation")
    return {"class_name": raw["class_name"], "confidence": float(confidence), "xyxy": [float(n) for n in coords]}


def _box_key(box):
    return box["class_name"], box["confidence"], tuple(box["xyxy"])


def _context_key(context):
    if not isinstance(context, dict):
        raise ValueError("Invalid tracking context")
    run, stream = str(UUID(context["run_id"])), str(UUID(context["stream_id"]))
    camera = context["camera_id"]
    if not isinstance(camera, str) or not _CAMERA.fullmatch(camera):
        raise ValueError("Invalid tracking context")
    return run, camera, stream


def _validated(context, result):
    key = _context_key(context)
    camera, media = key[1], context["media_time_seconds"]
    if not isinstance(result, dict) or not _number(media, high=1_000_000_000):
        raise ValueError("Invalid tracking input")
    provenance = result.get("provenance", {})
    image_hash = result.get("image_sha256")
    config_hash = provenance.get("configuration_sha256")
    if (result.get("status") != "available" or result.get("analysis_mode") not in ("fresh", "cached")
            or result.get("camera_id") != camera or provenance.get("kind") != "local_yolo_image"
            or provenance.get("fixture") is not False or provenance.get("image_sha256") != image_hash
            or not isinstance(image_hash, str) or not _HASH.fullmatch(image_hash)
            or not isinstance(config_hash, str) or not _HASH.fullmatch(config_hash)):
        raise ValueError("Exact current detection provenance is required")
    width, height = result.get("image_width"), result.get("image_height")
    if (type(width) is not int or type(height) is not int or not 1 <= width <= 4096
            or not 1 <= height <= 4096 or width * height > 8_388_608):
        raise ValueError("Invalid image dimensions")
    threshold = result.get("confidence_threshold")
    if not _number(threshold, LOW_THRESHOLD):
        raise ValueError("Invalid detector threshold")
    candidates, high = result.get("tracking_candidates"), result.get("boxes")
    if (not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES
            or not isinstance(high, list) or len(high) > MAX_CANDIDATES):
        raise ValueError("A bounded candidate pool is required")
    boxes, seen = [], set()
    for raw in [*high, *candidates]:
        box = _box(raw)
        observation_key = _box_key(box)
        if observation_key not in seen:
            boxes.append(box)
            seen.add(observation_key)
    if any(_box(raw)["confidence"] < threshold for raw in high) or len(boxes) > MAX_CANDIDATES:
        raise ValueError("Inconsistent high detections or candidate pool")
    return key, float(media), image_hash, config_hash, (width, height), float(threshold), boxes


def _linear_assignment(cost, threshold, np):
    """Exact minimum-cost assignment with threshold-priced unmatched rows.

    Dummy columns make leaving a track unmatched an explicit optimization
    choice (equivalent to LAP's cost-limit objective). Filtering a full forced
    assignment afterwards is NOT equivalent. This is the shortest augmenting
    path Hungarian algorithm, with vectorized column reductions, not greedy IoU.
    """
    n, m = cost.shape
    if not n or not m:
        return [], list(range(n)), list(range(m))
    padded = np.concatenate((np.where(cost <= threshold, cost, threshold + 2),
                             np.full((n, n), threshold + 1e-10)), axis=1)
    columns = padded.shape[1]
    u, v = np.zeros(n + 1), np.zeros(columns + 1)
    p, way = np.zeros(columns + 1, dtype=int), np.zeros(columns + 1, dtype=int)
    for row in range(1, n + 1):
        p[0], column = row, 0
        minimum, used = np.full(columns + 1, np.inf), np.zeros(columns + 1, dtype=bool)
        while True:
            used[column] = True
            current = padded[p[column] - 1] - u[p[column]] - v[1:]
            improve = (~used[1:]) & (current < minimum[1:])
            minimum[1:][improve] = current[improve]
            way[1:][improve] = column
            available = np.flatnonzero(~used[1:]) + 1
            next_column = available[np.argmin(minimum[available])]
            delta = minimum[next_column]
            u[p[used]] += delta
            v[used] -= delta
            minimum[~used] -= delta
            column = int(next_column)
            if p[column] == 0:
                break
        while column:
            previous = way[column]
            p[column] = p[previous]
            column = int(previous)
    matches = [(int(p[j] - 1), j - 1) for j in range(1, m + 1)
               if p[j] and cost[p[j] - 1, j - 1] <= threshold]
    matched_rows, matched_columns = {a for a, _ in matches}, {b for _, b in matches}
    return matches, [i for i in range(n) if i not in matched_rows], [i for i in range(m) if i not in matched_columns]


class _Kalman:
    """ByteTrack/DeepSORT XYAH constant-velocity filter, NumPy adaptation."""
    def __init__(self, np):
        self.np = np

    def initiate(self, measurement):
        np = self.np
        h = max(measurement[3], 1e-3)
        std = [2*h/20, 2*h/20, 1e-2, 2*h/20, 10*h/160, 10*h/160, 1e-5, 10*h/160]
        return np.r_[measurement, np.zeros(4)], np.diag(np.square(std))

    def predict(self, mean, covariance, seconds, lost):
        np = self.np
        dt = max(1e-3, seconds * 8)  # nominal eight sampled frames/s, variable clock
        motion = np.eye(8)
        motion[:4, 4:] = np.eye(4) * dt
        mean = mean.copy()
        if lost:
            mean[7] = 0  # official lost-track height-velocity handling
        h = max(mean[3], 1e-3)
        std = np.array([h/20, h/20, 1e-2, h/20, h/160, h/160, 1e-5, h/160]) * math.sqrt(dt)
        mean = motion @ mean
        mean[2:4] = np.maximum(mean[2:4], 1e-6)
        return mean, motion @ covariance @ motion.T + np.diag(std * std)

    def update(self, mean, covariance, measurement):
        np = self.np
        h = max(mean[3], 1e-3)
        innovation_cov = covariance[:4, :4] + np.diag(np.square([h/20, h/20, .1, h/20]))
        gain = np.linalg.solve(innovation_cov, covariance[:4, :]).T
        new_mean = mean + gain @ (measurement - mean[:4])
        new_covariance = covariance - gain @ innovation_cov @ gain.T
        return new_mean, (new_covariance + new_covariance.T) / 2


@dataclass
class _Track:
    identifier: str
    kind: str
    mean: object
    covariance: object
    media: float
    wall: float
    state: str
    confirmed: bool


class _ByteTrack:
    def __init__(self, shape, threshold, *, geometric_recovery=False):
        import numpy as np  # Optional dependency: never required to import/start API.
        self.np, self.kalman = np, _Kalman(np)
        self.shape, self.threshold = shape, threshold
        self.prefix, self.next_id = uuid4().hex[:12], 0
        self.tracks: list[_Track] = []
        self.frames = 0
        self.geometric_recovery = geometric_recovery

    def _measurement(self, box):
        x1, y1, x2, y2 = box["xyxy"]
        width, height = self.shape
        w, h = (x2-x1)*width, (y2-y1)*height
        return self.np.array([(x1+x2)*width/2, (y1+y2)*height/2, w/h, h])

    def _cost(self, tracks, boxes, fuse):
        np = self.np
        if not tracks or not boxes:
            return np.zeros((len(tracks), len(boxes)))
        predicted = []
        for track in tracks:
            x, y, aspect, h = track.mean[:4]
            w = aspect * h
            predicted.append([x-w/2, y-h/2, x+w/2, y+h/2])
        left = np.array(predicted)
        right = np.array([box["xyxy"] for box in boxes]) * np.array([*self.shape, *self.shape])
        overlap = np.maximum(0, np.minimum(left[:, None, 2:], right[None, :, 2:])
                             - np.maximum(left[:, None, :2], right[None, :, :2]))
        intersection = overlap[:, :, 0] * overlap[:, :, 1]
        a = np.prod(np.maximum(0, left[:, 2:]-left[:, :2]), axis=1)
        b = np.prod(right[:, 2:]-right[:, :2], axis=1)
        similarity = intersection / np.maximum(a[:, None] + b[None, :] - intersection, 1e-12)
        if fuse:
            similarity *= np.array([box["confidence"] for box in boxes])[None, :]
        cost = 1-similarity
        for i, track in enumerate(tracks):
            for j, box in enumerate(boxes):
                if track.kind != box["class_name"]:
                    cost[i, j] = 2
        return cost

    def _geometric_matches(self, tracks, boxes, media, wall):
        """One-pass mutual nearest matches, with ambiguity in BOTH directions.

        This does not optimize its way around an ambiguous choice. Competing
        candidates remain in the matrix while margins are checked; only one
        high observation can be assigned to each eligible recently seen track.
        """
        np = self.np
        if not tracks or not boxes:
            return []
        costs = np.full((len(tracks), len(boxes)), np.inf)
        for i, track in enumerate(tracks):
            if (track.state not in {"tracked", "tentative"} or track.kind not in GEOMETRY_CLASSES
                    or not 0 < media-track.media <= GEOMETRY_MAX_GAP
                    or not 0 < wall-track.wall <= GEOMETRY_MAX_GAP):
                continue
            x, y, aspect, height = track.mean[:4]
            width = aspect*height
            if not all(math.isfinite(float(v)) and v > 0 for v in (width, height)):
                continue
            left = (x-width/2, y-height/2, x+width/2, y+height/2)
            for j, box in enumerate(boxes):
                if box["class_name"] != track.kind or box["confidence"] < self.threshold:
                    continue
                bx, by, baspect, bh = self._measurement(box)
                bw = baspect*bh
                if not (2/3 <= bw/width <= 1.5 and 2/3 <= bh/height <= 1.5):
                    continue
                diagonal = min(math.hypot(width, height), math.hypot(bw, bh))
                distance = math.hypot(bx-x, by-y)/diagonal
                if not math.isfinite(distance) or distance > GEOMETRY_MAX_DISTANCE:
                    continue
                right = (bx-bw/2, by-bh/2, bx+bw/2, by+bh/2)
                intersection = (max(0, min(left[2], right[2])-max(left[0], right[0]))
                                * max(0, min(left[3], right[3])-max(left[1], right[1])))
                overlap = intersection/max(width*height+bw*bh-intersection, 1e-12)
                if overlap >= .05:
                    costs[i, j] = distance
        matches = []
        for i in range(len(tracks)):
            j = int(np.argmin(costs[i]))
            best = costs[i, j]
            if not math.isfinite(float(best)) or int(np.argmin(costs[:, j])) != i:
                continue
            row_alternatives = np.delete(costs[i], j)
            column_alternatives = np.delete(costs[:, j], i)
            if ((len(row_alternatives) and float(np.min(row_alternatives))-best < GEOMETRY_MIN_MARGIN)
                    or (len(column_alternatives) and float(np.min(column_alternatives))-best < GEOMETRY_MIN_MARGIN)):
                continue
            matches.append((i, j))
        return matches

    def update(self, boxes, media, wall, delta):
        self.frames += 1
        self.tracks = [track for track in self.tracks
                       if media-track.media <= LOST_TTL_SECONDS and wall-track.wall <= LOST_TTL_SECONDS]
        pool = [track for track in self.tracks if track.state != "tentative"]
        tentative = [track for track in self.tracks if track.state == "tentative"]
        for track in pool:
            track.mean, track.covariance = self.kalman.predict(track.mean, track.covariance, delta, track.state == "lost")
        high = [box for box in boxes if box["confidence"] >= self.threshold]
        low = [box for box in boxes if box["confidence"] < self.threshold]
        observations = []

        def observed(track, box, kind, association="bytetrack"):
            track.mean, track.covariance = self.kalman.update(track.mean, track.covariance, self._measurement(box))
            track.media, track.wall, track.state, track.confirmed = media, wall, "tracked", True
            observations.append({**box, "xyxy": list(box["xyxy"]), "track_id": track.identifier,
                                 "observation": kind, "confirmed": True,
                                 **({"association": association} if self.geometric_recovery else {})})

        # Stage 1: confirmed active + recently lost tracks against high scores.
        matches, unmatched, remaining = _linear_assignment(self._cost(pool, high, True), .8, self.np)
        for track_index, box_index in matches:
            observed(pool[track_index], high[box_index], "high")
        # Stage 2: only unmatched ACTIVE tracks can recover low observations.
        active = [pool[index] for index in unmatched if pool[index].state == "tracked"]
        removed = None
        if self.geometric_recovery:
            # Give normal tentative IoU association first choice as well. This
            # operates on high scores only and cannot consume low-stage inputs.
            remaining_high = [high[index] for index in remaining]
            matches, removed, leftover = _linear_assignment(self._cost(tentative, remaining_high, True), .7, self.np)
            for track_index, box_index in matches:
                observed(tentative[track_index], remaining_high[box_index], "high")
            remaining = [remaining[index] for index in leftover]
            recovery_pool = [*active, *(tentative[index] for index in removed)]
            recovery_boxes = [high[index] for index in remaining]
            recovered = self._geometric_matches(recovery_pool, recovery_boxes, media, wall)
            recovered_ids, recovered_boxes = set(), set()
            for track_index, box_index in recovered:
                track = recovery_pool[track_index]
                observed(track, recovery_boxes[box_index], "high", "gated_geometry")
                recovered_ids.add(track.identifier)
                recovered_boxes.add(box_index)
            active = [track for track in active if track.identifier not in recovered_ids]
            removed = [index for index in removed if tentative[index].identifier not in recovered_ids]
            remaining = [index for offset, index in enumerate(remaining) if offset not in recovered_boxes]
        matches, unmatched_active, _ = _linear_assignment(self._cost(active, low, False), .5, self.np)
        for track_index, box_index in matches:
            observed(active[track_index], low[box_index], "low_recovery")
        for index in unmatched_active:
            active[index].state = "lost"
        # Official tentative-track confirmation against remaining high scores.
        remaining_high = [high[index] for index in remaining]
        if removed is None:
            matches, removed, unmatched_high = _linear_assignment(self._cost(tentative, remaining_high, True), .7, self.np)
            for track_index, box_index in matches:
                observed(tentative[track_index], remaining_high[box_index], "high")
        else:
            unmatched_high = range(len(remaining_high))
        removed_ids = {tentative[index].identifier for index in removed}
        self.tracks = [track for track in self.tracks if track.identifier not in removed_ids]
        for index in unmatched_high:
            box = remaining_high[index]
            self.next_id += 1
            identifier = f"bt-{self.prefix}-{self.next_id}"
            mean, covariance = self.kalman.initiate(self._measurement(box))
            confirmed = self.frames == 1
            self.tracks.append(_Track(identifier, box["class_name"], mean, covariance, media, wall,
                                      "tracked" if confirmed else "tentative", confirmed))
            observations.append({**box, "xyxy": list(box["xyxy"]), "track_id": identifier,
                                 "observation": "high", "confirmed": confirmed})
        # Never discard a current high observation to retain a prediction.
        current_ids = {item["track_id"] for item in observations}
        self.tracks.sort(key=lambda track: (track.identifier in current_ids, track.wall), reverse=True)
        self.tracks = self.tracks[:MAX_TRACKS]
        return observations


class LiveTrackingService:
    """One locked bounded set of ephemeral stream trackers; no side effects."""
    def __init__(self, *, monotonic=None):
        self._clock = monotonic or time.monotonic
        self._lock = threading.Lock()
        self._sessions: OrderedDict[tuple[str, str, str], dict] = OrderedDict()

    def reset(self):
        with self._lock:
            self._sessions.clear()

    def process(self, context: dict, detections: dict) -> dict:
        unavailable = {"schema_version": SCHEMA_VERSION, "status": "unavailable", "algorithm": "ByteTrack",
                       "tracks": [], "message": "Tracking unavailable; raw detector observations remain separate."}
        with self._lock:
            key = None
            try:
                key = _context_key(context)
                key, media, image_hash, configuration, shape, threshold, boxes = _validated(context, detections)
                now = self._clock()
                if not _number(now, high=1e15):
                    raise ValueError("Invalid server clock")
                for previous in list(self._sessions):
                    entry = self._sessions[previous]
                    if now-entry["wall"] > SESSION_TTL_SECONDS or (previous[:2] == key[:2] and previous != key):
                        del self._sessions[previous]
                state = self._sessions.get(key)
                reason = None
                if state:
                    dm, dw = media-state["media"], now-state["wall"]
                    if configuration != state["configuration"]:
                        reason = "configuration_changed"
                    elif shape != state["shape"]:
                        reason = "image_shape_changed"
                    elif threshold != state["threshold"]:
                        reason = "threshold_changed"
                    elif image_hash in state["hashes"]:
                        reason = "duplicate_frame"
                    elif dm <= 0 or dw <= 0:
                        reason = "clock_discontinuity"
                    elif dm > MAX_FRAME_GAP_SECONDS or dw > MAX_FRAME_GAP_SECONDS or abs(dm-dw) > MAX_CLOCK_STEP_DIFFERENCE:
                        reason = "timing_gap"
                    if reason and reason != "duplicate_frame":
                        del self._sessions[key]
                        state = None
                result = {"schema_version": SCHEMA_VERSION, "status": "available", "algorithm": "ByteTrack",
                          "implementation": "clearway-bytetrack-observed-v1", "upstream_commit": UPSTREAM_COMMIT,
                          "association_policy": GEOMETRY_POLICY if key[1] == GEOMETRY_CAMERA_ID else "bytetrack-iou-v1",
                          "run_id": key[0], "camera_id": key[1], "stream_id": key[2],
                          "media_time_seconds": media, "image_sha256": image_hash,
                          "configuration_sha256": configuration, "reset_reason": reason,
                          "tracks": [], "prediction_only_tracks_returned": 0, "geometry_recoveries": 0}
                if reason == "duplicate_frame":
                    # Keep the bounded hashes as a tombstone: a frozen stream
                    # cannot alternate between reset and a newly tracked frame.
                    state["engine"] = _ByteTrack(shape, threshold, geometric_recovery=key[1] == GEOMETRY_CAMERA_ID)
                    state.update(media=media, wall=now)
                    self._sessions.move_to_end(key)
                    return result
                if state is None:
                    state = {"engine": _ByteTrack(shape, threshold, geometric_recovery=key[1] == GEOMETRY_CAMERA_ID), "configuration": configuration,
                             "shape": shape, "threshold": threshold, "media": media, "wall": now,
                             "hashes": deque(maxlen=MAX_HASHES)}
                    delta = 0.125
                else:
                    delta = media-state["media"]
                result["tracks"] = state["engine"].update(boxes, media, now, delta)
                result["geometry_recoveries"] = sum(t.get("association") == "gated_geometry" for t in result["tracks"])
                state["hashes"].append(image_hash)
                state.update(media=media, wall=now)
                self._sessions[key] = state
                self._sessions.move_to_end(key)
                while len(self._sessions) > MAX_SESSIONS:
                    self._sessions.popitem(last=False)
                return result
            except Exception:
                if key is not None:
                    self._sessions.pop(key, None)
                return unavailable
