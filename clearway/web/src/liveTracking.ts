import { isImageHash } from "./liveCameras";
import type { LiveImageBox } from "./liveCameras";

export interface LiveTrack extends LiveImageBox {
  track_id: string;
  observation: "high" | "low_recovery";
  confirmed: boolean;
}
export interface LiveTracking {
  status: "available";
  algorithm: "ByteTrack";
  schema_version: "clearway-live-tracking-v1";
  image_sha256: string;
  configuration_sha256: string;
  camera_id: string;
  run_id: string;
  stream_id: string;
  media_time_seconds: number;
  tracks: LiveTrack[];
  reset_reason: string | null;
}
export interface TrackingContext {
  imageHash: string;
  configurationHash?: string;
  cameraId: string;
  runId: string;
  streamId: string;
  mediaTime: number;
}
const record = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
const classes = new Set([
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
export const isTrackId = (value: unknown): value is string =>
  typeof value === "string" &&
  value.length <= 48 &&
  /^bt-[a-f0-9]{12}-[1-9][0-9]*$/.test(value);

/** An unavailable or mismatched tracker never replaces genuine raw detections. */
export function readLiveTracking(
  value: unknown,
  context: TrackingContext,
): LiveTracking | null {
  const raw = record(value);
  if (
    !raw ||
    raw.status !== "available" ||
    raw.algorithm !== "ByteTrack" ||
    raw.schema_version !== "clearway-live-tracking-v1" ||
    !isImageHash(context.imageHash) ||
    raw.image_sha256 !== context.imageHash ||
    !isImageHash(context.configurationHash) ||
    raw.configuration_sha256 !== context.configurationHash ||
    !context.runId ||
    !context.streamId ||
    !context.cameraId ||
    raw.camera_id !== context.cameraId ||
    raw.run_id !== context.runId ||
    raw.stream_id !== context.streamId ||
    !Number.isFinite(context.mediaTime) ||
    context.mediaTime < 0 ||
    raw.media_time_seconds !== context.mediaTime ||
    !Array.isArray(raw.tracks) ||
    raw.tracks.length > 300 ||
    !(
      raw.reset_reason === null ||
      (typeof raw.reset_reason === "string" &&
        /^[a-z_]{1,80}$/.test(raw.reset_reason))
    )
  )
    return null;
  const ids = new Set<string>();
  const tracks: LiveTrack[] = [];
  for (const value of raw.tracks) {
    const track = record(value);
    if (
      !track ||
      !isTrackId(track.track_id) ||
      ids.has(track.track_id) ||
      typeof track.class_name !== "string" ||
      !classes.has(track.class_name) ||
      typeof track.confidence !== "number" ||
      !Number.isFinite(track.confidence) ||
      track.confidence < 0 ||
      track.confidence > 1 ||
      !["high", "low_recovery"].includes(String(track.observation)) ||
      typeof track.confirmed !== "boolean" ||
      (track.observation === "low_recovery" && !track.confirmed) ||
      !Array.isArray(track.xyxy) ||
      track.xyxy.length !== 4 ||
      !track.xyxy.every(
        (n) => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 1,
      ) ||
      track.xyxy[0] >= track.xyxy[2] ||
      track.xyxy[1] >= track.xyxy[3]
    )
      return null;
    ids.add(track.track_id);
    tracks.push({
      track_id: track.track_id,
      class_name: track.class_name,
      confidence: track.confidence,
      xyxy: [...track.xyxy] as LiveTrack["xyxy"],
      observation: track.observation as LiveTrack["observation"],
      confirmed: track.confirmed,
    });
  }
  return {
    status: "available",
    algorithm: "ByteTrack",
    schema_version: "clearway-live-tracking-v1",
    image_sha256: context.imageHash,
    configuration_sha256: context.configurationHash,
    camera_id: context.cameraId,
    run_id: context.runId,
    stream_id: context.streamId,
    media_time_seconds: context.mediaTime,
    tracks,
    reset_reason: raw.reset_reason as string | null,
  };
}
