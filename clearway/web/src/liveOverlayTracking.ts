import type { DetectionBox } from "./types";

// Pure media-time helpers: no timers, DOM access, persistent identity, or model
// output creation. Callers clear their frame on pause/seek/buffering/source reset.
export const MAX_MEDIA_AGE_MS = 350;
export const MAX_WALL_AGE_MS = 500;
export const MAX_PROJECTION_MS = 200;
export const MAX_MATCH_GAP_MS = 300;
export const MAX_CENTER_SPEED = 0.5; // normalized image widths/heights per second
const EPSILON_MS = 0.001;
const MAX_BOXES = 300;
const CLASSES = new Set([
  "person",
  "bicycle",
  "car",
  "motorcycle",
  "bus",
  "truck",
  "van",
  "tricycle",
  "awning-tricycle",
]);

export interface LiveDetectionFrame {
  sourceId: string;
  mediaTime: number;
  capturedAtMs: number;
  receivedAtMs: number;
  boxes: DetectionBox[];
}

export interface LiveTrackedFrame extends LiveDetectionFrame {
  // Internal, short-lived pairings only. No object/person IDs are assigned.
  velocities: [number, number][];
}

export interface LiveOverlayProjection {
  boxes: DetectionBox[];
  mediaAgeMs: number | null;
  wallAgeMs: number | null;
  extrapolated: boolean;
  reason:
    | "fresh"
    | "projected"
    | "empty"
    | "stale"
    | "discontinuity"
    | "unavailable";
}

const finiteNonnegative = (value: number) =>
  Number.isFinite(value) && value >= 0;
const copyBox = (box: DetectionBox): DetectionBox => ({
  class_name: box.class_name,
  confidence: box.confidence,
  xyxy: [...box.xyxy],
});
const center = (box: DetectionBox): [number, number] => [
  (box.xyxy[0] + box.xyxy[2]) / 2,
  (box.xyxy[1] + box.xyxy[3]) / 2,
];
const size = (box: DetectionBox): [number, number] => [
  box.xyxy[2] - box.xyxy[0],
  box.xyxy[3] - box.xyxy[1],
];

function validFrame(frame: LiveDetectionFrame): boolean {
  return (
    typeof frame.sourceId === "string" &&
    frame.sourceId.length > 0 &&
    frame.sourceId.length <= 160 &&
    finiteNonnegative(frame.mediaTime) &&
    finiteNonnegative(frame.capturedAtMs) &&
    finiteNonnegative(frame.receivedAtMs) &&
    frame.receivedAtMs >= frame.capturedAtMs &&
    frame.receivedAtMs - frame.capturedAtMs <= MAX_WALL_AGE_MS &&
    Array.isArray(frame.boxes) &&
    frame.boxes.length <= MAX_BOXES &&
    frame.boxes.every(
      (box) =>
        CLASSES.has(box.class_name) &&
        Number.isFinite(box.confidence) &&
        box.confidence >= 0 &&
        box.confidence <= 1 &&
        Array.isArray(box.xyxy) &&
        box.xyxy.length === 4 &&
        box.xyxy.every((n) => Number.isFinite(n) && n >= 0 && n <= 1) &&
        box.xyxy[0] < box.xyxy[2] &&
        box.xyxy[1] < box.xyxy[3],
    )
  );
}

function iou(a: DetectionBox, b: DetectionBox): number {
  const intersection =
    Math.max(0, Math.min(a.xyxy[2], b.xyxy[2]) - Math.max(a.xyxy[0], b.xyxy[0])) *
    Math.max(0, Math.min(a.xyxy[3], b.xyxy[3]) - Math.max(a.xyxy[1], b.xyxy[1]));
  const [aw, ah] = size(a);
  const [bw, bh] = size(b);
  return intersection / (aw * ah + bw * bh - intersection);
}

/** Pair actual adjacent detections; unmatched/new boxes have zero velocity.
 *
 * An empty latest result clears every old pairing. Backwards/duplicate samples
 * are discarded, and a gap or source change starts again without old motion.
 * Input arrays are never mutated. Caller also rejects wrong request epochs.
 */
export function trackLiveFrame(
  previous: LiveTrackedFrame | null,
  current: LiveDetectionFrame,
): LiveTrackedFrame | null {
  if (!validFrame(current)) return null;
  const fresh: LiveTrackedFrame = {
    sourceId: current.sourceId,
    mediaTime: current.mediaTime,
    capturedAtMs: current.capturedAtMs,
    receivedAtMs: current.receivedAtMs,
    boxes: current.boxes.map(copyBox),
    velocities: current.boxes.map(() => [0, 0]),
  };
  if (!previous || previous.sourceId !== current.sourceId) return fresh;
  const dt = current.mediaTime - previous.mediaTime;
  const wallGap = current.capturedAtMs - previous.capturedAtMs;
  if (dt <= 0 || wallGap <= 0) return null;
  if (
    dt * 1000 > MAX_MATCH_GAP_MS + EPSILON_MS ||
    wallGap > MAX_WALL_AGE_MS ||
    !previous.boxes.length ||
    !current.boxes.length
  )
    return fresh;

  const candidates: { prior: number; next: number; cost: number }[] = [];
  current.boxes.forEach((next, nextIndex) => {
    const [nx, ny] = center(next);
    const [nw, nh] = size(next);
    previous.boxes.forEach((prior, priorIndex) => {
      if (prior.class_name !== next.class_name) return;
      const [px, py] = center(prior);
      const [pw, ph] = size(prior);
      if (
        Math.max(nw / pw, pw / nw) > 1.8 ||
        Math.max(nh / ph, ph / nh) > 1.8
      )
        return;
      const distance = Math.hypot(nx - px, ny - py);
      const overlap = iou(prior, next);
      const maximumDistance = Math.min(
        0.12,
        Math.max(0.025, Math.hypot(nw, nh) * 0.75),
      );
      if (
        distance > maximumDistance ||
        (overlap < 0.1 && distance > 0.04)
      )
        return;
      candidates.push({
        prior: priorIndex,
        next: nextIndex,
        cost: 1 - overlap + distance,
      });
    });
  });
  candidates.sort((a, b) => a.cost - b.cost || a.next - b.next || a.prior - b.prior);
  const usedPrior = new Set<number>();
  const usedNext = new Set<number>();
  for (const match of candidates) {
    if (usedPrior.has(match.prior) || usedNext.has(match.next)) continue;
    const [px, py] = center(previous.boxes[match.prior]);
    const [nx, ny] = center(current.boxes[match.next]);
    const vx = (nx - px) / dt;
    const vy = (ny - py) / dt;
    const speed = Math.hypot(vx, vy);
    if (speed > MAX_CENTER_SPEED) continue; // Treat implausible motion as a new box.
    usedPrior.add(match.prior);
    usedNext.add(match.next);
    fresh.velocities[match.next] = [vx, vy];
  }
  return fresh;
}

/** Project only the latest real boxes, for at most 200 ms of media time.
 *
 * Age starts at capture, including request latency. Stale/future results never
 * render. Callers should clear their ref on stale/discontinuity, and always on
 * seek/pause/buffering/source changes; this helper has no external state.
 */
export function projectLiveFrame(
  frame: LiveTrackedFrame | null,
  mediaTime: number,
  nowMs: number,
): LiveOverlayProjection {
  const hidden = (
    reason: LiveOverlayProjection["reason"],
    mediaAgeMs: number | null = null,
    wallAgeMs: number | null = null,
  ): LiveOverlayProjection => ({
    boxes: [],
    mediaAgeMs,
    wallAgeMs,
    extrapolated: false,
    reason,
  });
  if (!frame) return hidden("unavailable");
  if (!finiteNonnegative(mediaTime) || !finiteNonnegative(nowMs))
    return hidden("discontinuity");
  const mediaAgeMs = (mediaTime - frame.mediaTime) * 1000;
  const wallAgeMs = nowMs - frame.capturedAtMs;
  if (
    mediaAgeMs < -EPSILON_MS ||
    wallAgeMs < 0 ||
    nowMs < frame.receivedAtMs
  )
    return hidden("discontinuity", mediaAgeMs, wallAgeMs);
  if (
    mediaAgeMs > MAX_MEDIA_AGE_MS + EPSILON_MS ||
    wallAgeMs > MAX_WALL_AGE_MS
  )
    return hidden("stale", mediaAgeMs, wallAgeMs);
  if (!frame.boxes.length) return hidden("empty", mediaAgeMs, wallAgeMs);
  const elapsed = Math.min(MAX_PROJECTION_MS, Math.max(0, mediaAgeMs)) / 1000;
  let extrapolated = false;
  const boxes: DetectionBox[] = [];
  frame.boxes.forEach((box, index) => {
    const [vx, vy] = frame.velocities[index] ?? [0, 0];
    const dx = vx * elapsed;
    const dy = vy * elapsed;
    const clamp = (n: number) => Math.max(0, Math.min(1, n));
    const xyxy: DetectionBox["xyxy"] = [
      clamp(box.xyxy[0] + dx),
      clamp(box.xyxy[1] + dy),
      clamp(box.xyxy[2] + dx),
      clamp(box.xyxy[3] + dy),
    ];
    if (xyxy[0] >= xyxy[2] || xyxy[1] >= xyxy[3]) return;
    extrapolated ||= Math.abs(dx) + Math.abs(dy) > 1e-9;
    boxes.push({ class_name: box.class_name, confidence: box.confidence, xyxy });
  });
  return {
    boxes,
    mediaAgeMs: Math.max(0, mediaAgeMs),
    wallAgeMs,
    extrapolated,
    reason: boxes.length ? (extrapolated ? "projected" : "fresh") : "empty",
  };
}
