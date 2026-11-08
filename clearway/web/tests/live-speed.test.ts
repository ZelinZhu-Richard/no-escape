import { describe, expect, it } from "vitest";
import { projectRoadPoint, RoadSpeedEstimator } from "../src/liveSpeed";
import type { RoadPoint, RoadSpeedCalibration, RoadSpeedFrame } from "../src/liveSpeed";
import type { LiveTrack } from "../src/liveTracking";

const id = "bt-0123456789ab-1";
const hash = (value: number) => value.toString(16).padStart(64, "0");
const calibration: RoadSpeedCalibration = {
  cameraId: "caltrans-d4-285",
  revision: "test-road-v1",
  basis: "measured",
  description: "Synthetic plane with known dimensions; not a real camera calibration.",
  imageAspectRatio: 1.5,
  imageQuad: [[0, 0], [1, 0], [1, 1], [0, 1]],
  worldQuad: [[0, 0], [100, 0], [100, 100], [0, 100]],
};
const track = (point: RoadPoint, extra: Partial<LiveTrack> = {}): LiveTrack => ({
  track_id: id,
  class_name: "car",
  xyxy: [point[0] - 0.01, point[1] - 0.03, point[0] + 0.01, point[1]],
  confidence: 0.9,
  observation: "high",
  confirmed: true,
  ...extra,
});
const frame = (time: number, index: number, tracks = [track([0.5, 0.1 + time * 0.1])]): RoadSpeedFrame => ({
  cameraId: calibration.cameraId,
  runId: "run-1",
  streamId: "stream-1",
  configurationHash: hash(900),
  imageHash: hash(index + 1),
  mediaTime: time,
  imageWidth: 720,
  imageHeight: 480,
  tracks,
});
function run(estimator = new RoadSpeedEstimator(calibration)) {
  let result = estimator.update(frame(0, 0));
  for (let i = 1; i <= 5; i++) result = estimator.update(frame(i * 0.2, i));
  return { estimator, result };
}

describe("road-plane calibration", () => {
  it("maps a perspective trapezoid onto metric coordinates rather than using one pixel scale", () => {
    const perspective: RoadSpeedCalibration = {
      ...calibration,
      imageQuad: [[0.4, 0.1], [0.6, 0.1], [0.9, 0.9], [0.1, 0.9]],
      worldQuad: [[0, 0], [12, 0], [12, 80], [0, 80]],
    };
    for (let i = 0; i < 4; i++) {
      const mapped = projectRoadPoint(perspective, perspective.imageQuad[i])!;
      expect(mapped[0]).toBeCloseTo(perspective.worldQuad[i][0], 7);
      expect(mapped[1]).toBeCloseTo(perspective.worldQuad[i][1], 7);
    }
    // Known inverse projective mapping: y=(.125*t+.1)/(1-.75*t), t=Y/80.
    const point = projectRoadPoint(perspective, [0.5, 0.5])!;
    expect(point[0]).toBeCloseTo(6, 7);
    expect(point[1]).toBeCloseTo(64, 7);
    expect(projectRoadPoint(perspective, [0.1, 0.1])).toBeNull();
    const estimator = new RoadSpeedEstimator(perspective);
    let speed = null;
    for (let i = 0; i <= 5; i++) {
      const time = i * 0.2, t = (20 + 10 * time) / 80;
      speed = estimator.update(frame(time, i, [track([0.5, (0.125 * t + 0.1) / (1 - 0.75 * t)])]))[id].mph;
    }
    expect(speed).toBeCloseTo(22.36936, 5);
  });

  it("is numerically stable with a translated metric origin", () => {
    const shifted = {
      ...calibration,
      worldQuad: calibration.worldQuad.map(([x, y]) => [x + 500000, y + 4000000]) as unknown as RoadSpeedCalibration["worldQuad"],
    };
    const result = projectRoadPoint(shifted, [0.25, 0.5])!;
    expect(result[0]).toBeCloseTo(500025, 5);
    expect(result[1]).toBeCloseTo(4000050, 5);
  });

  it.each([
    null,
    { ...calibration, imageAspectRatio: 0 },
    { ...calibration, imageQuad: [[0, 0], [0, 0], [1, 1], [0, 1]] },
    { ...calibration, imageQuad: [[0, 0], [1, 1], [1, 0], [0, 1]] },
    { ...calibration, imageQuad: [[0, 0], [1, 0], [0.3, 0.3], [0, 1]] },
    { ...calibration, worldQuad: [[0, 0], [1, 0], [2, 0], [3, 0]] },
    { ...calibration, worldQuad: [[0, 0], [Infinity, 0], [1, 1], [0, 1]] },
  ])("rejects absent or degenerate calibration safely", (invalid) => {
    const value = invalid as RoadSpeedCalibration | null;
    expect(projectRoadPoint(value, [0.5, 0.5])).toBeNull();
    expect(run(new RoadSpeedEstimator(value)).result[id]).toMatchObject({ mph: null, reason: "uncalibrated" });
  });
});

describe("observed per-vehicle road speed", () => {
  it("waits for a full observation window then estimates actual metric displacement", () => {
    const estimator = new RoadSpeedEstimator(calibration);
    for (let i = 0; i < 5; i++) {
      expect(estimator.update(frame(i * 0.2, i))[id]).toMatchObject({ mph: null, reason: "collecting" });
    }
    const result = estimator.update(frame(1, 5))[id];
    expect(result.mph).toBeCloseTo(22.36936, 5);
    expect(result).toMatchObject({ reason: "estimated", samples: 6, durationSeconds: 1 });
  });

  it("uses media elapsed time, supports stationary vehicles and separates track identities", () => {
    const second = "bt-0123456789ab-2";
    const estimator = new RoadSpeedEstimator(calibration);
    let result;
    for (let i = 0; i <= 5; i++) {
      const t = i * 0.2;
      result = estimator.update({ ...frame(t, i, [track([0.5, 0.1 + t * 0.2]), track([0.7, 0.4], { track_id: second })]), mediaTime: 10000 + t });
    }
    expect(result![id].mph).toBeCloseTo(44.738726, 5);
    expect(result![second].mph).toBeCloseTo(0, 8);
  });

  it("keeps assumed calibration usable but does not convert its basis into confidence", () => {
    const result = run(new RoadSpeedEstimator({ ...calibration, basis: "assumed" })).result[id];
    expect(result.mph).toBeCloseTo(22.36936, 5);
    expect(result).not.toHaveProperty("confidence");
  });

  it.each([
    [{ confirmed: false }, "tentative"],
    [{ observation: "low_recovery", confidence: 0.2 }, "low_confidence"],
    [{ class_name: "person" }, "unsupported_class"],
  ])("never reports speeds for unsupported observations %j", (extra, reason) => {
    const { estimator } = run();
    expect(estimator.update(frame(1.2, 6, [track([0.5, 0.22], extra as Partial<LiveTrack>)]))[id]).toMatchObject({ mph: null, reason });
    expect(estimator.update(frame(1.4, 7))[id]).toMatchObject({ mph: null, reason: "collecting", samples: 1 });
  });

  it("uses the bottom contact-point approximation and hides outside-zone estimates", () => {
    const zone = { ...calibration, imageQuad: [[0.2, 0.1], [0.8, 0.1], [0.8, 0.8], [0.2, 0.8]] as const };
    const estimator = new RoadSpeedEstimator(zone);
    const result = estimator.update(frame(0, 0, [track([0.5, 0.81], { xyxy: [0.4, 0.6, 0.6, 0.81] })]));
    expect(result[id]).toMatchObject({ mph: null, reason: "outside_zone" });
  });

  it.each([
    { cameraId: "another-camera" },
    { imageWidth: 1280, imageHeight: 720 },
  ])("refuses another camera/view geometry %j", (changed) => {
    const { estimator } = run();
    expect(estimator.update({ ...frame(1.2, 6), ...changed })[id].mph).toBeNull();
    expect(estimator.update(frame(1.4, 7))[id].mph).toBeNull();
  });

  it.each([
    { streamId: "stream-two" },
    { runId: "run-two" },
    { configurationHash: hash(901) },
    { imageWidth: 360, imageHeight: 240 },
    { resetReason: "tracker_reset" },
  ])("starts a new history when identity or geometry changes %j", (changed) => {
    const { estimator } = run();
    expect(estimator.update({ ...frame(1.2, 6), ...changed })[id]).toMatchObject({ mph: null, reason: "collecting", samples: 1 });
  });

  it.each([0.8, 1, 2])("drops speeds after a backward, duplicate-time or gapped frame at %s", (time) => {
    const { estimator } = run();
    expect(estimator.update(frame(time, 6))[id]).toMatchObject({ mph: null, reason: "discontinuity" });
  });

  it("does not accept repeated image bytes as another speed sample", () => {
    const { estimator } = run();
    expect(estimator.update({ ...frame(1.2, 6), imageHash: hash(5) })[id]).toMatchObject({ mph: null, reason: "repeated_frame" });
    expect(estimator.update(frame(1.4, 7))[id]).toMatchObject({ mph: null, reason: "collecting", samples: 1 });
  });

  it("does not carry speeds through missing observations or explicit playback reset", () => {
    const { estimator } = run();
    expect(estimator.update(frame(1.2, 6, []))).toEqual({});
    expect(estimator.update(frame(1.4, 7))[id]).toMatchObject({ mph: null, samples: 1 });
    estimator.reset();
    expect(estimator.update(frame(1.6, 8))[id]).toMatchObject({ mph: null, samples: 1 });
  });

  it("rejects a gross association jump without clamping it to a believable speed", () => {
    const { estimator } = run();
    expect(estimator.update(frame(1.2, 6, [track([0.5, 0.9])]))[id]).toMatchObject({ mph: null, reason: "implausible_motion" });
    expect(estimator.update(frame(1.4, 7))[id]).toMatchObject({ mph: null, samples: 1 });
  });

  it("rejects erratic tracks that do not support a stable velocity fit", () => {
    const estimator = new RoadSpeedEstimator(calibration);
    let result;
    for (let i = 0; i <= 5; i++)
      result = estimator.update(frame(i * 0.2, i, [track([0.5, 0.3 + (i % 2 ? 0.1 : 0)])]));
    expect(result![id]).toMatchObject({ mph: null, reason: "unstable_motion" });
  });

  it("bounds rolling history and output to current observations", () => {
    const estimator = new RoadSpeedEstimator(calibration);
    let result;
    for (let i = 0; i < 200; i++)
      result = estimator.update(frame(i * 0.05, i, [track([0.5, 0.4])]));
    expect(result![id].samples).toBeLessThanOrEqual(32);
    expect(result![id].durationSeconds).toBeLessThanOrEqual(2);
    expect(result![id].mph).toBeCloseTo(0, 8);
    const tooMany = Array.from({ length: 301 }, (_, i) => track([0.5, 0.4], { track_id: `bt-0123456789ab-${i + 1}` }));
    expect(estimator.update(frame(10, 200, tooMany))).toEqual({});
    expect(estimator.update(frame(10.2, 201))[id].mph).toBeNull();
  });

  it("rejects malformed frames and duplicate IDs instead of retaining a prior speed", () => {
    for (const changed of [
      { imageHash: "bad" }, { configurationHash: "bad" },
      { mediaTime: Number.NaN }, { imageHeight: 0 },
      { tracks: [track([0.5, 0.3]), track([0.5, 0.3])] },
      { tracks: [track([0.5, 0.3], { xyxy: [0.5, 0.2, 0.4, 0.3] })] },
    ]) {
      const { estimator } = run();
      expect(estimator.update({ ...frame(1.2, 6), ...changed })[id]).toMatchObject({ mph: null, reason: "invalid_frame" });
    }
  });
});
