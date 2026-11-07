import { act, createElement, useRef } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  containRect,
  DetectionOverlay,
  frameAtTime,
} from "../src/DetectionOverlay";
import { buildVoiceBrief, VoiceBrief } from "../src/VoiceBrief";
import { request } from "../src/api";
import type { DetectionResult, Incident } from "../src/types";

vi.mock("../src/api", () => ({ request: vi.fn() }));

const detections = (source = "road-obstruction"): DetectionResult => ({
  status: "available",
  source_id: source,
  model: {
    name: "YOLOX-Tiny",
    version: "test",
    weights_sha256: "test-hash",
    license: "Apache-2.0",
  },
  provenance: {
    kind: "local_yolo_cached",
    fixture: false,
    generated_at: "",
    source_sha256: "test-video",
    preprocessing_version: "test",
  },
  sample_fps: 4,
  duration_seconds: 2,
  video_width: 1920,
  video_height: 1080,
  frames: [
    {
      time_seconds: 0,
      boxes: [
        { class_name: "car", confidence: 0.9, xyxy: [0.1, 0.2, 0.5, 0.8] },
      ],
      vehicle_count: 1,
      person_count: 0,
    },
    {
      time_seconds: 0.25,
      boxes: [
        { class_name: "person", confidence: 0.8, xyxy: [0.2, 0.1, 0.4, 0.9] },
      ],
      vehicle_count: 0,
      person_count: 1,
    },
    { time_seconds: 1.25, boxes: [], vehicle_count: 0, person_count: 0 },
  ],
  gate: {
    evaluated_windows: 1,
    passed_windows: 1,
    suppressed_windows: 0,
    baseline: "one model call per 2-second window",
    estimated_calls_avoided: 0,
    actual_model_calls: 0,
    mode: "shadow",
    policy: "test",
    note: "Hypothetical avoided calls",
  },
});
const incident: Incident = {
  id: "one",
  run_id: "run-one",
  source_id: "road-obstruction",
  title: "Possible obstruction",
  category: "road_obstruction",
  source_mode: "recorded_replay",
  analysis_mode: "fixture",
  review_status: "candidate",
  created_at: "",
  confirmed_at: null,
  evidence: [
    { timestamp_seconds: 1, observation: "Reference: truck in roadway." },
  ],
  unknowns: ["Injury status", "Capture time"],
  context_status: "not_applicable",
  location: {
    latitude: 0,
    longitude: 0,
    quality: "simulated",
    label: "Demo placement",
  },
  provenance: {
    provider: null,
    model: null,
    prompt_version: "test",
    fixture: true,
    cache_key: null,
  },
  responder_path: "/respond/run-one/one",
};
let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  (
    globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  vi.mocked(request).mockReset();
  vi.stubGlobal(
    "requestAnimationFrame",
    vi.fn(() => 1),
  );
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
});
function Harness({ sourceId = "road-obstruction" }: { sourceId?: string }) {
  const video = useRef<HTMLVideoElement>(null);
  return (
    <div>
      <video ref={video} />
      <DetectionOverlay sourceId={sourceId} videoRef={video} />
    </div>
  );
}

describe("visible detection replay", () => {
  it("uses the current past sample without drawing future or stale gap boxes", () => {
    const data = detections();
    expect(frameAtTime(data, -1)).toBeNull();
    expect(frameAtTime(data, 0.2)?.boxes[0].class_name).toBe("car");
    expect(frameAtTime(data, 0.3)?.boxes[0].class_name).toBe("person");
    expect(frameAtTime(data, 0.9)).toBeNull();
    expect(frameAtTime(data, 1.3)?.boxes).toEqual([]);
    expect(frameAtTime(data, 3)).toBeNull();
  });
  it("places boxes inside letterboxed and pillarboxed content", () => {
    expect(containRect(400, 300, 1920, 1080)).toEqual({
      left: 0,
      top: 37.5,
      width: 400,
      height: 225,
    });
    expect(containRect(400, 225, 800, 800)).toEqual({
      left: 87.5,
      top: 0,
      width: 225,
      height: 225,
    });
    expect(containRect(0, 225, 1920, 1080).width).toBe(0);
  });
  it("synchronizes boxes on seek and clears them in an unsampled gap", async () => {
    vi.mocked(request).mockResolvedValue(detections());
    await act(async () => root.render(<Harness />));
    const video = container.querySelector("video")!;
    vi.spyOn(video, "getBoundingClientRect").mockReturnValue({
      left: 0,
      top: 0,
      width: 400,
      height: 225,
    } as DOMRect);
    await act(async () => video.dispatchEvent(new Event("loadedmetadata")));
    expect(container.querySelector(".detection-label")?.textContent).toBe(
      "car 90%",
    );
    expect(container.textContent).toContain("YOLO · saved detections");
    expect(container.textContent).toContain("replay estimate");
    await act(async () => {
      video.currentTime = 0.3;
      video.dispatchEvent(new Event("seeked"));
    });
    expect(container.querySelector(".detection-label")?.textContent).toBe(
      "person 80%",
    );
    await act(async () => {
      video.currentTime = 0.9;
      video.dispatchEvent(new Event("seeked"));
    });
    expect(container.querySelector(".detection-box")).toBeNull();
    expect(container.textContent).toContain("No sample at this time");
  });
  it("ignores a late result for the previously selected source", async () => {
    let resolveOld!: (data: DetectionResult) => void;
    const old = new Promise<DetectionResult>((resolve) => {
      resolveOld = resolve;
    });
    vi.mocked(request).mockImplementation((path) =>
      path.includes("road-obstruction")
        ? old
        : Promise.resolve(detections("street-traffic")),
    );
    await act(async () => root.render(<Harness />));
    await act(async () => root.render(<Harness sourceId="street-traffic" />));
    const stale = detections();
    stale.gate.estimated_calls_avoided = 99;
    await act(async () => resolveOld(stale));
    expect(
      container.querySelector('[data-testid="gate-savings"]')?.textContent,
    ).toBe("0 / 1");
  });
  it("does not present fixtures or unavailable detections as YOLO output", async () => {
    const fake = detections();
    (fake.provenance as { fixture: boolean }).fixture = true;
    vi.mocked(request).mockResolvedValue(fake);
    await act(async () => root.render(<Harness />));
    expect(container.textContent).toContain(
      "Verified YOLO detections unavailable",
    );
    expect(container.querySelector('[data-testid="gate-savings"]')).toBeNull();
  });
});

describe("grounded voice brief", () => {
  it("includes fixture disclosure, review status, evidence, location limits, and unknowns", () => {
    const brief = buildVoiceBrief(incident);
    expect(brief).toContain(
      "Fixture observations, not model-generated analysis",
    );
    expect(brief).toContain("Awaiting operator confirmation");
    expect(brief).toContain("At 1 seconds: Reference: truck in roadway.");
    expect(brief).toContain("Map placement is simulated");
    expect(brief).toContain("Injury status; Capture time");
  });
  it("never autoplays and cancels speech when the run changes", async () => {
    const speak = vi.fn();
    const cancel = vi.fn();
    vi.stubGlobal("speechSynthesis", { speak, cancel, getVoices: () => [] });
    vi.stubGlobal(
      "SpeechSynthesisUtterance",
      class {
        text: string;
        constructor(text: string) {
          this.text = text;
        }
      },
    );
    await act(async () => root.render(createElement(VoiceBrief, { incident })));
    expect(speak).not.toHaveBeenCalled();
    await act(async () =>
      container.querySelector<HTMLButtonElement>("button")!.click(),
    );
    expect(speak).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain("Stop voice brief");
    await act(async () =>
      root.render(
        createElement(VoiceBrief, {
          incident: { ...incident, run_id: "run-two" },
        }),
      ),
    );
    expect(cancel).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain("Listen to brief");
  });
});
