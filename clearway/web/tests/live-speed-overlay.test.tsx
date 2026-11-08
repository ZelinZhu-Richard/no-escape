import { act, useRef } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useLiveVideoOverlay } from "../src/useLiveVideoOverlay";
import { request } from "../src/api";
import { extractSceneSignature, matchSceneSignatures } from "../src/speedSceneGuard";
import { TVA43_CAMERA_ID } from "../src/trafficSpeedCalibration";

vi.mock("../src/api", () => ({ request: vi.fn() }));
vi.mock("../src/speedSceneGuard", () => ({
  extractSceneSignature: vi.fn(),
  matchSceneSignatures: vi.fn(),
}));

const runId = "00000000-0000-4000-8000-000000000100";
let container: HTMLDivElement;
let root: Root;
let video: HTMLVideoElement;
let hash: string;
let configurationHash: string;
let paused: boolean;
let sequence: number;
let selectedCamera: string;

function Probe({ cameraId = TVA43_CAMERA_ID, enabled = true }) {
  const ref = useRef<HTMLVideoElement>(null);
  const view = useLiveVideoOverlay(ref, cameraId, enabled, runId);
  return <><video ref={ref} /><pre>{JSON.stringify(view)}</pre></>;
}
const view = () => JSON.parse(container.querySelector("pre")!.textContent!);
const estimate = () => Object.values(view().speeds ?? {})[0] as
  { mph: number | null; reason: string; samples: number } | undefined;
const advance = async (milliseconds: number) => act(async () => {
  await vi.advanceTimersByTimeAsync(milliseconds);
});
const step = async (mediaTime: number) => {
  video.currentTime = mediaTime;
  await advance(180);
};
const responseFor = (options?: RequestInit) => {
  const headers = options!.headers as Record<string, string>;
  const mediaTime = Number(headers["X-Clearway-Media-Time"]);
  const prefix = headers["X-Clearway-Stream-ID"].replaceAll("-", "").slice(-12);
  // Synthetic, smoothly moving contact point inside the actual TVA43 preset.
  // This test checks wiring; it does not validate the real camera's scale.
  const y = 0.70 + (mediaTime - 1) * 0.015;
  const box = { class_name: "car", confidence: 0.91, xyxy: [0.58, y - 0.04, 0.62, y] };
  return {
    status: "available",
    analysis_mode: "fresh",
    image_sha256: hash,
    image_width: 640,
    image_height: 427,
    boxes: [box],
    vehicle_count: 1,
    person_count: 0,
    model: { name: "YOLO11s", version: "test" },
    provenance: {
      kind: "local_yolo_image",
      fixture: false,
      image_sha256: hash,
      configuration_sha256: configurationHash,
      analyzed_at: "2026-11-08T00:00:00Z",
    },
    inference_ms: 30,
    tracking: {
      status: "available",
      algorithm: "ByteTrack",
      schema_version: "clearway-live-tracking-v1",
      image_sha256: hash,
      configuration_sha256: configurationHash,
      camera_id: selectedCamera,
      run_id: headers["X-Clearway-Run-ID"],
      stream_id: headers["X-Clearway-Stream-ID"],
      media_time_seconds: mediaTime,
      reset_reason: null,
      tracks: [{ ...box, track_id: `bt-${prefix}-1`, observation: "high", confirmed: true }],
    },
  };
};
const start = async (cameraId = TVA43_CAMERA_ID) => {
  selectedCamera = cameraId;
  await act(async () => root.render(<Probe cameraId={cameraId} />));
  video = container.querySelector("video")!;
  Object.defineProperties(video, {
    videoWidth: { value: 720 },
    videoHeight: { value: 480 },
    readyState: { value: 4 },
    paused: { get: () => paused },
  });
  await step(1);
};
const accumulate = async () => {
  for (let i = 1; i <= 6; i++) await step(1 + i * 0.2);
  expect(view().detections?.boxes).toHaveLength(1);
  expect(estimate()?.reason).toBe("estimated");
  expect(estimate()?.mph).toBeGreaterThan(0);
};

beforeEach(() => {
  (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
    .IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-11-08T00:00:00Z"));
  vi.spyOn(document, "visibilityState", "get").mockReturnValue("visible");
  sequence = 0;
  hash = "ab".repeat(32);
  configurationHash = "cd".repeat(32);
  paused = false;
  selectedCamera = TVA43_CAMERA_ID;
  let streamSequence = 0;
  vi.stubGlobal("crypto", {
    subtle: {
      digest: vi.fn(async () => {
        const bytes = new Uint8Array(32).fill(++sequence);
        hash = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
        return bytes.buffer;
      }),
    },
    randomUUID: vi.fn(() => `00000000-0000-4000-8000-${String(++streamSequence).padStart(12, "0")}`),
  });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    drawImage: vi.fn(),
    getImageData: vi.fn(() => ({ data: new Uint8ClampedArray(4) })),
  } as unknown as CanvasRenderingContext2D);
  vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockImplementation(
    () => `data:image/jpeg;base64,${btoa(`frame-${sequence}`)}`,
  );
  vi.mocked(extractSceneSignature).mockReset().mockReturnValue({
    version: "clearway-static-patches-v1", aspectRatio: 1.5, patches: [],
  });
  vi.mocked(matchSceneSignatures).mockReset().mockReturnValue({ matches: true, score: 1 });
  vi.mocked(request).mockReset().mockImplementation(async (_path, options) => responseFor(options));
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("live calibrated-speed overlay wiring", () => {
  it("requires a matching view and enough confirmed observations before publishing speed", async () => {
    await start();
    expect(estimate()?.reason).toBe("collecting");
    expect(estimate()?.mph).toBeNull();
    await accumulate();
    expect(view().speedViewMatches).toBe(true);
    expect(estimate()?.samples).toBeGreaterThanOrEqual(4);
    expect(extractSceneSignature).toHaveBeenCalled();
    expect(matchSceneSignatures).toHaveBeenCalled();
  });

  it("clears speed on a mismatching background while keeping current detections", async () => {
    await start();
    await accumulate();
    vi.mocked(matchSceneSignatures).mockReturnValue({ matches: false, score: 0.2 });
    await step(2.4);
    expect(view().speedViewMatches).toBe(false);
    expect(view().speeds).toBeNull();
    expect(view().detections?.boxes).toHaveLength(1);
    vi.mocked(matchSceneSignatures).mockReturnValue({ matches: true, score: 1 });
    await step(2.6);
    expect(estimate()?.mph).toBeNull();
    expect(estimate()?.reason).toBe("collecting");
    expect(estimate()?.samples).toBe(1);
  });

  it("clears speed on pause and requires a new observation window after resume", async () => {
    await start();
    await accumulate();
    await act(async () => {
      paused = true;
      video.dispatchEvent(new Event("pause"));
    });
    expect(view().speeds).toBeNull();
    expect(view().detections).toBeNull();
    paused = false;
    await step(2.4);
    expect(estimate()?.mph).toBeNull();
    expect(estimate()?.samples).toBe(1);
  });

  it("hides stale speed and resets its history when video frames stop advancing", async () => {
    await start();
    await accumulate();
    await advance(501);
    expect(view().speeds).toBeNull();
    expect(view().detections).toBeNull();
    await step(2.4);
    expect(estimate()?.mph).toBeNull();
    expect(estimate()?.samples).toBe(1);
  });

  it("does not carry speeds across detector configuration changes", async () => {
    await start();
    await accumulate();
    configurationHash = "ef".repeat(32);
    await step(2.4);
    expect(view().detections?.boxes).toHaveLength(1);
    expect(estimate()?.mph).toBeNull();
    expect(estimate()?.samples).toBe(1);
  });

  it("never applies the TVA43 calibration to another camera", async () => {
    await start("caltrans-d4-49");
    for (let i = 1; i <= 6; i++) await step(1 + i * 0.2);
    expect(view().detections?.boxes).toHaveLength(1);
    expect(view().tracking?.algorithm).toBe("ByteTrack");
    expect(view().speeds).toBeNull();
    expect(view().speedViewMatches).toBeNull();
    expect(extractSceneSignature).not.toHaveBeenCalled();
    expect(matchSceneSignatures).not.toHaveBeenCalled();
  });
});
