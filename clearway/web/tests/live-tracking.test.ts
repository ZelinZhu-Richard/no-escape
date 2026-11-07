import { describe, expect, it } from "vitest";
import { readLiveTracking } from "../src/liveTracking";
import type { LiveTracking, TrackingContext } from "../src/liveTracking";
const context: TrackingContext = {
  imageHash: "ab".repeat(32),
  configurationHash: "cd".repeat(32),
  cameraId: "caltrans-d4-7",
  runId: "run-one",
  streamId: "stream-one",
  mediaTime: 12.5,
};
const result = (): LiveTracking => ({
  status: "available",
  algorithm: "ByteTrack",
  schema_version: "clearway-live-tracking-v1",
  image_sha256: context.imageHash,
  configuration_sha256: context.configurationHash!,
  camera_id: context.cameraId,
  run_id: context.runId,
  stream_id: context.streamId,
  media_time_seconds: context.mediaTime,
  reset_reason: null,
  tracks: [
    {
      track_id: "bt-0123456789ab-1",
      class_name: "car",
      confidence: 0.8,
      xyxy: [0.1, 0.2, 0.4, 0.5],
      observation: "high",
      confirmed: false,
    },
    {
      track_id: "bt-0123456789ab-2",
      class_name: "car",
      confidence: 0.2,
      xyxy: [0.5, 0.2, 0.8, 0.5],
      observation: "low_recovery",
      confirmed: true,
    },
  ],
});

describe("ByteTrack response identity", () => {
  it("accepts current high observations and confirmed low recoveries while preserving separate metadata", () => {
    const original = result();
    const parsed = readLiveTracking(original, context);
    expect(parsed).toEqual(original);
    original.tracks[0].xyxy[0] = 0.3;
    expect(parsed!.tracks[0].xyxy[0]).toBe(0.1);
  });
  it.each([
    "image_sha256",
    "configuration_sha256",
    "camera_id",
    "run_id",
    "stream_id",
    "media_time_seconds",
    "algorithm",
    "schema_version",
  ])("rejects mismatched %s instead of overlaying another context", (key) => {
    expect(
      readLiveTracking(
        {
          ...result(),
          [key]: key === "media_time_seconds" ? 12.6 : "different",
        },
        context,
      ),
    ).toBeNull();
  });
  it("rejects unverified config, unavailable tracking and prediction-only/duplicate track records", () => {
    expect(
      readLiveTracking(result(), { ...context, configurationHash: undefined }),
    ).toBeNull();
    expect(
      readLiveTracking({ ...result(), status: "unavailable" }, context),
    ).toBeNull();
    expect(
      readLiveTracking(
        {
          ...result(),
          tracks: [{ ...result().tracks[0], observation: "predicted" }],
        },
        context,
      ),
    ).toBeNull();
    expect(
      readLiveTracking(
        { ...result(), tracks: [result().tracks[0], result().tracks[0]] },
        context,
      ),
    ).toBeNull();
    expect(
      readLiveTracking(
        { ...result(), tracks: [{ ...result().tracks[1], confirmed: false }] },
        context,
      ),
    ).toBeNull();
  });
  it("rejects invalid boxes, confidence and IDs but accepts a reset with no current tracks", () => {
    for (const invalid of [
      { xyxy: [-0.1, 0, 0.3, 0.5] },
      { xyxy: [0.3, 0.2, 0.2, 0.5] },
      { confidence: NaN },
      { track_id: "<script>" },
      { confirmed: "yes" },
    ]) {
      expect(
        readLiveTracking(
          { ...result(), tracks: [{ ...result().tracks[0], ...invalid }] },
          context,
        ),
      ).toBeNull();
    }
    expect(
      readLiveTracking(
        { ...result(), tracks: [], reset_reason: "duplicate_frame" },
        context,
      )?.tracks,
    ).toEqual([]);
  });
});
