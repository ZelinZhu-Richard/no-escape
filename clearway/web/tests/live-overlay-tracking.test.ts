import { describe, expect, it } from "vitest";
import type { DetectionBox } from "../src/types";
import {
  MAX_CENTER_SPEED,
  MAX_PROJECTION_MS,
  projectLiveFrame,
  trackLiveFrame,
} from "../src/liveOverlayTracking";
import type {
  LiveDetectionFrame,
  LiveTrackedFrame,
} from "../src/liveOverlayTracking";

const box = (x: number, kind = "car", confidence = 0.8): DetectionBox => ({
  class_name: kind,
  confidence,
  xyxy: [x, 0.4, x + 0.1, 0.5],
});
const frame = (
  mediaTime: number,
  boxes = [box(0.2)],
  overrides: Partial<LiveDetectionFrame> = {},
): LiveDetectionFrame => ({
  sourceId: "caltrans-d4-53",
  mediaTime,
  capturedAtMs: mediaTime * 1000,
  receivedAtMs: mediaTime * 1000 + 40,
  boxes,
  ...overrides,
});
const tracked = (input: LiveDetectionFrame): LiveTrackedFrame => {
  const result = trackLiveFrame(null, input);
  expect(result).not.toBeNull();
  return result!;
};
function moving(): LiveTrackedFrame {
  return trackLiveFrame(
    tracked(frame(1)),
    frame(1.1, [box(0.225, "car", 0.9)]),
  )!;
}

describe("short-horizon live YOLO overlay", () => {
  it("retains mixed traffic classes from a configured live detector", () => {
    const kinds = ["car", "van", "tricycle", "awning-tricycle", "person"];
    const result = tracked(
      frame(
        1,
        kinds.map((kind, index) => box(index * 0.15, kind)),
      ),
    );
    expect(
      projectLiveFrame(result, 1.05, 1050).boxes.map((item) => item.class_name),
    ).toEqual(kinds);
  });
  it("shows new real boxes without inventing movement from one observation", () => {
    const result = projectLiveFrame(tracked(frame(1)), 1.08, 1080);
    expect(result.boxes).toEqual([box(0.2)]);
    expect(result.extrapolated).toBe(false);
    expect(result.reason).toBe("fresh");
  });

  it("moves a matched vehicle at frame cadence using adjacent detection media times", () => {
    const state = moving();
    const early = projectLiveFrame(state, 1.14, 1140);
    const later = projectLiveFrame(state, 1.18, 1180);
    expect(early.boxes[0].xyxy[0]).toBeCloseTo(0.235);
    expect(later.boxes[0].xyxy[0]).toBeCloseTo(0.245);
    expect(later.boxes[0].confidence).toBe(0.9);
    expect(later.extrapolated).toBe(true);
    expect(later.reason).toBe("projected");
    expect(later.mediaAgeMs).toBeCloseTo(80);
    expect(later.wallAgeMs).toBeCloseTo(80);
  });

  it("caps projection at 200 ms and hides after 350 ms of media age", () => {
    const state = moving();
    const capped = projectLiveFrame(state, 1.4, 1400);
    expect(capped.boxes[0].xyxy[0]).toBeCloseTo(
      0.225 + (0.25 * MAX_PROJECTION_MS) / 1000,
    );
    expect(projectLiveFrame(state, 1.451, 1451)).toMatchObject({
      reason: "stale",
      boxes: [],
      extrapolated: false,
    });
  });

  it("counts network/inference lag in wall age rather than resetting age at receipt", () => {
    const state = tracked(
      frame(1, [box(0.2)], { capturedAtMs: 500, receivedAtMs: 950 }),
    );
    expect(projectLiveFrame(state, 1.1, 1001)).toMatchObject({
      reason: "stale",
      boxes: [],
    });
    expect(
      trackLiveFrame(
        null,
        frame(1, [box(0.2)], { capturedAtMs: 500, receivedAtMs: 1001 }),
      ),
    ).toBeNull();
  });

  it("hides frozen/buffering frames on wall age even if media time does not advance", () => {
    expect(projectLiveFrame(tracked(frame(1)), 1, 1501)).toMatchObject({
      reason: "stale",
      boxes: [],
    });
  });

  it("hides future-frame boxes, seeks backwards and results not yet received", () => {
    const state = moving();
    expect(projectLiveFrame(state, 0.8, 1180)).toMatchObject({
      reason: "discontinuity",
      boxes: [],
    });
    expect(projectLiveFrame(state, 1.12, 1120)).toMatchObject({
      reason: "discontinuity",
      boxes: [],
    });
    expect(trackLiveFrame(state, frame(0.5))).toBeNull();
    expect(trackLiveFrame(state, frame(1.1))).toBeNull();
  });

  it("resets motion after camera changes and gaps between actual detections", () => {
    const prior = moving();
    const changed = trackLiveFrame(
      prior,
      frame(1.2, [box(0.25)], { sourceId: "caltrans-d4-88" }),
    )!;
    expect(changed.velocities).toEqual([[0, 0]]);
    const gap = trackLiveFrame(prior, frame(1.5, [box(0.25)]))!;
    expect(gap.velocities).toEqual([[0, 0]]);
    expect(projectLiveFrame(null, 1.6, 1600)).toMatchObject({
      reason: "unavailable",
      boxes: [],
    });
  });

  it("clears all tracks on zero detections and does not bridge a missed detection", () => {
    const empty = trackLiveFrame(moving(), frame(1.2, []))!;
    expect(projectLiveFrame(empty, 1.25, 1250)).toMatchObject({
      reason: "empty",
      boxes: [],
    });
    const reappeared = trackLiveFrame(empty, frame(1.3, [box(0.26)]))!;
    expect(reappeared.velocities).toEqual([[0, 0]]);
  });

  it("does not retain a previous box missing from the current detection frame", () => {
    const prior = tracked(frame(1, [box(0.2), box(0.6)]));
    const next = trackLiveFrame(prior, frame(1.1, [box(0.22)]))!;
    expect(projectLiveFrame(next, 1.15, 1150).boxes).toHaveLength(1);
  });

  it("matches one-to-one and never transfers car velocity to a person", () => {
    const prior = tracked(frame(1, [box(0.2)]));
    const next = trackLiveFrame(
      prior,
      frame(1.1, [box(0.21), box(0.23), box(0.22, "person")]),
    )!;
    expect(
      next.velocities.filter(([vx, vy]) => vx !== 0 || vy !== 0),
    ).toHaveLength(1);
    expect(next.velocities[0][0]).toBeCloseTo(0.1);
    expect(next.velocities[1]).toEqual([0, 0]);
    expect(next.velocities[2]).toEqual([0, 0]);
  });

  it("rejects distant, resized and speed-outlier matches instead of drifting boxes", () => {
    const prior = tracked(frame(1));
    const distant = trackLiveFrame(prior, frame(1.1, [box(0.7)]))!;
    expect(distant.velocities).toEqual([[0, 0]]);
    const huge: DetectionBox = {
      class_name: "car",
      confidence: 0.8,
      xyxy: [0.1, 0.3, 0.6, 0.8],
    };
    expect(trackLiveFrame(prior, frame(1.1, [huge]))!.velocities).toEqual([
      [0, 0],
    ]);
    const tooFast = trackLiveFrame(prior, frame(1.01, [box(0.23)]))!;
    expect(tooFast.velocities).toEqual([[0, 0]]);
    expect(Math.hypot(...moving().velocities[0])).toBeLessThanOrEqual(
      MAX_CENTER_SPEED,
    );
  });

  it("clips projected boxes at the image edge and keeps coordinates normalized", () => {
    const prior = tracked(frame(1, [box(0.87)]));
    const next = trackLiveFrame(prior, frame(1.1, [box(0.895)]))!;
    const result = projectLiveFrame(next, 1.3, 1300);
    expect(result.boxes[0].xyxy[2]).toBe(1);
    expect(result.boxes[0].xyxy.every((n) => n >= 0 && n <= 1)).toBe(true);
  });

  it("does not mutate detections or tracked state when projecting multiple frames", () => {
    const original = frame(1);
    const state = tracked(original);
    original.boxes[0].xyxy[0] = 0.7;
    expect(state.boxes[0].xyxy[0]).toBe(0.2);
    const first = projectLiveFrame(state, 1.1, 1100);
    first.boxes[0].xyxy[0] = 0.9;
    expect(projectLiveFrame(state, 1.2, 1200).boxes[0].xyxy[0]).toBe(0.2);
  });

  it("rejects invalid geometry, clock values and unsupported identity classes", () => {
    expect(trackLiveFrame(null, frame(Number.NaN))).toBeNull();
    expect(
      trackLiveFrame(null, frame(1, [box(0.2, "person identity")])),
    ).toBeNull();
    expect(
      trackLiveFrame(
        null,
        frame(1, [{ ...box(0.2), xyxy: [0.2, 0.5, 0.1, 0.6] }]),
      ),
    ).toBeNull();
    expect(
      trackLiveFrame(null, frame(1, [box(0.2)], { receivedAtMs: 999 })),
    ).toBeNull();
    expect(projectLiveFrame(moving(), Number.NaN, 1200).boxes).toEqual([]);
  });
});

describe("ByteTrack ID motion association", () => {
  const identified = (id: number, x: number) => ({
    ...box(x),
    track_id: `bt-0123456789ab-${id}`,
    observation: "high" as const,
    confirmed: true,
  });
  it("uses stable IDs when nearest geometries would swap two vehicles", () => {
    const before = tracked(frame(1, [identified(1, 0.2), identified(2, 0.23)]));
    const after = trackLiveFrame(
      before,
      frame(1.1, [identified(1, 0.23), identified(2, 0.2)]),
    )!;
    expect(after.velocities[0][0]).toBeCloseTo(0.3);
    expect(after.velocities[1][0]).toBeCloseTo(-0.3);
    const projected = projectLiveFrame(after, 1.15, 1150);
    expect(projected.boxes[0].track_id).toBe("bt-0123456789ab-1");
    expect(projected.boxes[0].xyxy[0]).toBeCloseTo(0.245);
    expect(projected.boxes[1].xyxy[0]).toBeCloseTo(0.185);
  });
  it("does not transfer velocity across IDs, new track sessions, or raw fallback", () => {
    const before = tracked(frame(1, [identified(1, 0.2)]));
    const different = trackLiveFrame(
      before,
      frame(1.1, [identified(2, 0.22)]),
    )!;
    expect(different.velocities).toEqual([[0, 0]]);
    const session = trackLiveFrame(
      before,
      frame(1.1, [{ ...identified(1, 0.22), track_id: "bt-abcdef123456-1" }]),
    )!;
    expect(session.velocities).toEqual([[0, 0]]);
    expect(trackLiveFrame(before, frame(1.1, [box(0.22)]))!.velocities).toEqual(
      [[0, 0]],
    );
    expect(
      trackLiveFrame(
        tracked(frame(1, [box(0.2)])),
        frame(1.1, [identified(1, 0.22)]),
      )!.velocities,
    ).toEqual([[0, 0]]);
  });
  it("retains a current low recovery's metadata, expires it, and never resurrects a missing track", () => {
    const before = tracked(frame(1, [identified(1, 0.2)]));
    const recovered = trackLiveFrame(
      before,
      frame(1.1, [
        {
          ...identified(1, 0.22),
          confidence: 0.2,
          observation: "low_recovery" as const,
        },
      ]),
    )!;
    expect(projectLiveFrame(recovered, 1.15, 1150).boxes[0]).toMatchObject({
      track_id: "bt-0123456789ab-1",
      observation: "low_recovery",
      confirmed: true,
      confidence: 0.2,
    });
    expect(projectLiveFrame(recovered, 1.451, 1451).boxes).toEqual([]);
    const missing = trackLiveFrame(recovered, frame(1.2, []))!;
    expect(projectLiveFrame(missing, 1.25, 1250).boxes).toEqual([]);
  });
});
