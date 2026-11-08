import type { LiveTrack } from "./liveTracking";

export type RoadPoint = readonly [number, number];
export type RoadQuad = readonly [RoadPoint, RoadPoint, RoadPoint, RoadPoint];
export interface RoadSpeedCalibration {
  cameraId: string;
  revision: string;
  imageQuad: RoadQuad;
  worldQuad: RoadQuad;
  basis: "measured" | "assumed";
  description: string;
  imageAspectRatio: number;
}
export type SpeedReason =
  | "estimated" | "collecting" | "uncalibrated" | "wrong_camera"
  | "aspect_changed" | "outside_zone" | "tentative" | "low_confidence"
  | "unsupported_class" | "discontinuity" | "repeated_frame"
  | "implausible_motion" | "unstable_motion" | "invalid_frame";
export interface RoadSpeedEstimate {
  mph: number | null;
  reason: SpeedReason;
  samples: number;
  durationSeconds: number;
}
export interface RoadSpeedFrame {
  cameraId: string;
  runId: string;
  streamId: string;
  configurationHash: string;
  imageHash: string;
  mediaTime: number;
  imageWidth: number;
  imageHeight: number;
  tracks: readonly LiveTrack[];
  resetReason?: string | null;
}
export type RoadSpeedEstimates = Record<string, RoadSpeedEstimate>;

const EPSILON = 1e-9;
const MPH_PER_MPS = 2.2369362920544;
const WINDOW_SECONDS = 2;
const MIN_SECONDS = 1;
const MIN_SAMPLES = 4;
const MAX_GAP_SECONDS = 0.75;
const MAX_TRACKS = 300;
const MAX_SAMPLES = 32;
const MAX_HASHES = 128;
// Reject physically implausible road speeds; never clamp an observation into a
// believable number. This is a fault guard, not a legal limit or accuracy claim.
const MAX_METERS_PER_SECOND = 90;
const VEHICLES = new Set(["car", "truck", "bus", "van", "motorcycle"]);
const HASH = /^[a-f0-9]{64}$/;
const TRACK_ID = /^bt-[a-f0-9]{12}-[1-9][0-9]*$/;
type Matrix = number[];
type Sample = { time: number; point: RoadPoint };
type TrackHistory = { className: string; samples: Sample[] };
type Prepared = { matrix: Matrix; quad: RoadQuad; cameraId: string; aspect: number };

function cross(a: RoadPoint, b: RoadPoint, c: RoadPoint): number {
  return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]);
}
function convex(quad: RoadQuad): boolean {
  const turns = quad.map((a, i) => cross(a, quad[(i + 1) % 4], quad[(i + 2) % 4]));
  return turns.every(v => v > EPSILON) || turns.every(v => v < -EPSILON);
}
function inside(quad: RoadQuad, point: RoadPoint): boolean {
  const turns = quad.map((a, i) => cross(a, quad[(i + 1) % 4], point));
  return turns.every(v => v >= -EPSILON) || turns.every(v => v <= EPSILON);
}
function multiply(a: Matrix, b: Matrix): Matrix {
  return Array.from({ length: 9 }, (_, index) => {
    const row = Math.floor(index / 3), col = index % 3;
    return a[row * 3] * b[col] + a[row * 3 + 1] * b[3 + col] + a[row * 3 + 2] * b[6 + col];
  });
}
function transform(matrix: Matrix, point: RoadPoint): RoadPoint | null {
  const [x, y] = point;
  const denominator = matrix[6] * x + matrix[7] * y + matrix[8];
  if (!Number.isFinite(denominator) || Math.abs(denominator) < EPSILON) return null;
  const output: RoadPoint = [
    (matrix[0] * x + matrix[1] * y + matrix[2]) / denominator,
    (matrix[3] * x + matrix[4] * y + matrix[5]) / denominator,
  ];
  return output.every(Number.isFinite) ? output : null;
}
function normalize(quad: RoadQuad) {
  const cx = quad.reduce((sum, p) => sum + p[0], 0) / 4;
  const cy = quad.reduce((sum, p) => sum + p[1], 0) / 4;
  const distance = quad.reduce((sum, p) => sum + Math.hypot(p[0] - cx, p[1] - cy), 0) / 4;
  if (!Number.isFinite(distance) || distance < EPSILON) return null;
  const scale = Math.SQRT2 / distance;
  return {
    points: quad.map(p => [(p[0] - cx) * scale, (p[1] - cy) * scale] as RoadPoint) as unknown as RoadQuad,
    forward: [scale, 0, -cx * scale, 0, scale, -cy * scale, 0, 0, 1],
    inverse: [1 / scale, 0, cx, 0, 1 / scale, cy, 0, 0, 1],
  };
}
function solve(rows: number[][]): number[] | null {
  for (let column = 0; column < 8; column++) {
    let pivot = column;
    for (let row = column + 1; row < 8; row++)
      if (Math.abs(rows[row][column]) > Math.abs(rows[pivot][column])) pivot = row;
    if (Math.abs(rows[pivot][column]) < EPSILON) return null;
    [rows[column], rows[pivot]] = [rows[pivot], rows[column]];
    const divisor = rows[column][column];
    for (let j = column; j <= 8; j++) rows[column][j] /= divisor;
    for (let row = 0; row < 8; row++) {
      if (row === column) continue;
      const factor = rows[row][column];
      for (let j = column; j <= 8; j++) rows[row][j] -= factor * rows[column][j];
    }
  }
  const result = rows.map(row => row[8]);
  return result.every(Number.isFinite) ? result : null;
}
function prepare(calibration: RoadSpeedCalibration | null): Prepared | null {
  if (!calibration || !calibration.cameraId || !calibration.revision ||
      !["measured", "assumed"].includes(calibration.basis) ||
      !Number.isFinite(calibration.imageAspectRatio) || calibration.imageAspectRatio <= 0 ||
      !Array.isArray(calibration.imageQuad) || calibration.imageQuad.length !== 4 ||
      !Array.isArray(calibration.worldQuad) || calibration.worldQuad.length !== 4 ||
      !calibration.imageQuad.every(p => Array.isArray(p) && p.length === 2 && p.every(v => Number.isFinite(v) && v >= 0 && v <= 1)) ||
      !calibration.worldQuad.every(p => Array.isArray(p) && p.length === 2 && p.every(Number.isFinite))) return null;
  const image = normalize(calibration.imageQuad), world = normalize(calibration.worldQuad);
  if (!image || !world || !convex(image.points) || !convex(world.points)) return null;
  const rows: number[][] = [];
  image.points.forEach(([x, y], i) => {
    const [u, v] = world.points[i];
    rows.push([x, y, 1, 0, 0, 0, -u * x, -u * y, u]);
    rows.push([0, 0, 0, x, y, 1, -v * x, -v * y, v]);
  });
  const solved = solve(rows);
  if (!solved) return null;
  const matrix = multiply(world.inverse, multiply([...solved, 1], image.forward));
  const quad = calibration.imageQuad.map(p => [...p] as RoadPoint) as unknown as RoadQuad;
  const denominators = quad.map(([x, y]) => matrix[6] * x + matrix[7] * y + matrix[8]);
  if (!(denominators.every(v => v > EPSILON) || denominators.every(v => v < -EPSILON))) return null;
  if (!quad.every((p, i) => {
    const projected = transform(matrix, p);
    return projected && Math.hypot(projected[0] - calibration.worldQuad[i][0], projected[1] - calibration.worldQuad[i][1]) < 1e-5;
  })) return null;
  return { matrix, quad, cameraId: calibration.cameraId, aspect: calibration.imageAspectRatio };
}

/** Projects only within a valid calibrated road polygon; no extrapolation. */
export function projectRoadPoint(calibration: RoadSpeedCalibration | null, point: RoadPoint): RoadPoint | null {
  const prepared = prepare(calibration);
  return prepared && point.every(Number.isFinite) && inside(prepared.quad, point)
    ? transform(prepared.matrix, point) : null;
}

const unknown = (reason: SpeedReason, samples = 0, durationSeconds = 0): RoadSpeedEstimate =>
  ({ mph: null, reason, samples, durationSeconds });
function fit(samples: Sample[]): RoadSpeedEstimate {
  const duration = samples.at(-1)!.time - samples[0].time;
  if (samples.length < MIN_SAMPLES || duration + EPSILON < MIN_SECONDS)
    return unknown("collecting", samples.length, duration);
  // Center times for stable regression even after long HLS playback.
  const origin = samples[0].time;
  const meanT = samples.reduce((s, p) => s + p.time - origin, 0) / samples.length;
  const meanX = samples.reduce((s, p) => s + p.point[0], 0) / samples.length;
  const meanY = samples.reduce((s, p) => s + p.point[1], 0) / samples.length;
  let variance = 0, covarianceX = 0, covarianceY = 0;
  for (const sample of samples) {
    const dt = sample.time - origin - meanT;
    variance += dt * dt;
    covarianceX += dt * (sample.point[0] - meanX);
    covarianceY += dt * (sample.point[1] - meanY);
  }
  if (variance < EPSILON) return unknown("collecting", samples.length, duration);
  const vx = covarianceX / variance, vy = covarianceY / variance;
  const speed = Math.hypot(vx, vy);
  if (!Number.isFinite(speed) || speed > MAX_METERS_PER_SECOND)
    return unknown("implausible_motion");
  const rms = Math.sqrt(samples.reduce((sum, sample) => {
    const dt = sample.time - origin - meanT;
    return sum + (sample.point[0] - meanX - vx * dt) ** 2 + (sample.point[1] - meanY - vy * dt) ** 2;
  }, 0) / samples.length);
  if (rms > 1.5) return unknown("unstable_motion");
  return { mph: speed * MPH_PER_MPS, reason: "estimated", samples: samples.length, durationSeconds: duration };
}

/** In-memory estimates from observed road contact-point approximations only.
 * The caller must reset on pause/stall/seek; frames must be hash-verified before
 * update. Confidence is detector confidence, never speed confidence.
 */
export class RoadSpeedEstimator {
  private readonly prepared: Prepared | null;
  private context = "";
  private lastTime: number | null = null;
  private histories = new Map<string, TrackHistory>();
  private hashes = new Set<string>();
  constructor(calibration: RoadSpeedCalibration | null) {
    this.prepared = prepare(calibration);
  }
  reset(): void {
    this.context = "";
    this.lastTime = null;
    this.histories.clear();
    this.hashes.clear();
  }
  update(frame: RoadSpeedFrame): RoadSpeedEstimates {
    const estimates: RoadSpeedEstimates = Object.create(null);
    const allUnknown = (reason: SpeedReason) => {
      this.histories.clear();
      for (const track of frame.tracks.slice(0, MAX_TRACKS))
        if (TRACK_ID.test(track.track_id)) estimates[track.track_id] = unknown(reason);
      return estimates;
    };
    if (!Array.isArray(frame.tracks) || frame.tracks.length > MAX_TRACKS) {
      this.reset();
      return estimates;
    }
    const ids = new Set(frame.tracks.map(t => t.track_id));
    if (ids.size !== frame.tracks.length ||
        ![frame.cameraId, frame.runId, frame.streamId].every(v => typeof v === "string" && v.length > 0 && v.length <= 256) ||
        !HASH.test(frame.imageHash) || !HASH.test(frame.configurationHash) ||
        !Number.isFinite(frame.mediaTime) || frame.mediaTime < 0 ||
        ![frame.imageWidth, frame.imageHeight].every(v => Number.isInteger(v) && v > 0 && v <= 4096) ||
        frame.tracks.some(t => !TRACK_ID.test(t.track_id) || !Array.isArray(t.xyxy) || t.xyxy.length !== 4 ||
          !t.xyxy.every((v: number) => Number.isFinite(v) && v >= 0 && v <= 1) || t.xyxy[0] >= t.xyxy[2] || t.xyxy[1] >= t.xyxy[3] ||
          !Number.isFinite(t.confidence) || t.confidence < 0 || t.confidence > 1)) {
      this.reset();
      return allUnknown("invalid_frame");
    }
    if (!this.prepared) return allUnknown("uncalibrated");
    if (frame.cameraId !== this.prepared.cameraId) return allUnknown("wrong_camera");
    if (Math.abs(frame.imageWidth / frame.imageHeight / this.prepared.aspect - 1) > 0.02)
      return allUnknown("aspect_changed");
    const context = JSON.stringify([frame.cameraId, frame.runId, frame.streamId, frame.configurationHash, frame.imageWidth, frame.imageHeight]);
    if (context !== this.context || frame.resetReason) this.reset();
    this.context = context;
    const previousTime = this.lastTime;
    this.lastTime = frame.mediaTime;
    if (previousTime !== null && (frame.mediaTime <= previousTime || frame.mediaTime - previousTime > MAX_GAP_SECONDS)) {
      this.hashes.add(frame.imageHash);
      while (this.hashes.size > MAX_HASHES) this.hashes.delete(this.hashes.values().next().value!);
      return allUnknown("discontinuity");
    }
    if (this.hashes.has(frame.imageHash)) return allUnknown("repeated_frame");
    this.hashes.add(frame.imageHash);
    while (this.hashes.size > MAX_HASHES) this.hashes.delete(this.hashes.values().next().value!);
    for (const id of this.histories.keys()) if (!ids.has(id)) this.histories.delete(id);
    for (const track of frame.tracks) {
      const reject = (reason: SpeedReason) => {
        this.histories.delete(track.track_id);
        estimates[track.track_id] = unknown(reason);
      };
      if (!VEHICLES.has(track.class_name)) { reject("unsupported_class"); continue; }
      if (!track.confirmed) { reject("tentative"); continue; }
      if (track.observation !== "high") { reject("low_confidence"); continue; }
      const contact: RoadPoint = [(track.xyxy[0] + track.xyxy[2]) / 2, track.xyxy[3]];
      const point = inside(this.prepared.quad, contact) ? transform(this.prepared.matrix, contact) : null;
      if (!point) { reject("outside_zone"); continue; }
      let history = this.histories.get(track.track_id);
      if (!history || history.className !== track.class_name) history = { className: track.class_name, samples: [] };
      const previous = history.samples.at(-1);
      if (previous && Math.hypot(point[0] - previous.point[0], point[1] - previous.point[1]) /
          (frame.mediaTime - previous.time) > MAX_METERS_PER_SECOND) {
        reject("implausible_motion"); continue;
      }
      history.samples.push({ time: frame.mediaTime, point });
      history.samples = history.samples.filter(p => frame.mediaTime - p.time <= WINDOW_SECONDS + EPSILON).slice(-MAX_SAMPLES);
      const estimate = fit(history.samples);
      estimates[track.track_id] = estimate;
      if (estimate.reason === "unstable_motion" || estimate.reason === "implausible_motion") this.histories.delete(track.track_id);
      else this.histories.set(track.track_id, history);
    }
    return estimates;
  }
}
