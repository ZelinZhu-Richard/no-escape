import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { ApiError, post, request } from "../src/api";
import { buildVoiceBrief } from "../src/VoiceBrief";
import type { Incident, Source, State } from "../src/types";
import type { ImageDetections } from "../src/liveCameras";

vi.mock("../src/api", async (original) => ({
  ...(await original<object>()),
  request: vi.fn(),
  post: vi.fn(),
}));
vi.mock("../src/MapView", () => ({
  MapView: ({
    incidents,
    onSelectIncident,
  }: {
    incidents: Incident[];
    onSelectIncident: (id: string) => void;
  }) =>
    createElement(
      "div",
      { "data-testid": "map" },
      incidents
        .filter((i) => i.source_mode === "live")
        .map((i) =>
          createElement(
            "button",
            {
              key: i.id,
              "data-map-incident": i.id,
              onClick: () => onSelectIncident(i.id),
            },
            i.title,
          ),
        ),
    ),
}));
vi.mock("../src/LiveCameraPanel", () => ({
  LiveCameraPanel: ({
    runId,
    selectedId,
    onSelect,
  }: {
    runId: string;
    selectedId: string;
    onSelect: (id: string) => void;
  }) =>
    createElement(
      "button",
      { "data-testid": "camera", onClick: () => onSelect("camera-streaming") },
      `${runId}:${selectedId ?? "none"}`,
    ),
}));
const hash = "ab".repeat(32);
const detections: ImageDetections = {
  status: "available",
  analysis_mode: "fresh",
  image_sha256: hash,
  image_width: 640,
  image_height: 360,
  boxes: [{ class_name: "car", confidence: 0.9, xyxy: [0.2, 0.3, 0.5, 0.6] }],
  vehicle_count: 1,
  person_count: 0,
  model: { name: "YOLO11s VisDrone", version: "1" },
  provenance: {
    kind: "local_yolo_image",
    fixture: false,
    image_sha256: hash,
    analyzed_at: "2026-11-07T20:00:00Z",
  },
  inference_ms: 55,
};
const replaySource: Source = {
  id: "road-obstruction",
  title: "Road replay",
  source_mode: "recorded_replay",
  video_url: "/fixture.webm",
  poster_url: "",
  duration_seconds: 11,
  media_available: false,
  control_status: "development",
  attribution: {
    creator: "Test",
    title: "Test footage",
    source_url: "#source",
    license: "CC BY",
    license_url: "#license",
  },
  location: {
    latitude: 35.994,
    longitude: -78.8986,
    quality: "simulated",
    label: "Demo placement",
  },
};
const live = (id: string): Incident => ({
  id,
  run_id: "run-one",
  source_id: `camera-${id}`,
  title: `Possible stationary vehicle ${id}`,
  category: "stationary_vehicle",
  source_mode: "live",
  analysis_mode: "fresh",
  review_status: "candidate",
  created_at: "2026-11-07T20:00:00Z",
  confirmed_at: null,
  evidence: [
    { timestamp_seconds: 112, observation: `Genuine window observation ${id}` },
  ],
  unknowns: ["Cause and severity unknown"],
  context_status: "camera_metadata_only",
  location: {
    latitude: 37.77,
    longitude: -122.3,
    quality: "known_camera",
    label: `Camera ${id}`,
  },
  provenance: {
    provider: "local_yolo_temporal_rule",
    model: "YOLO11s",
    fixture: false,
    cache_key: hash,
  },
  responder_path: `/respond/run-one/${id}`,
  live_source: {
    ...replaySource,
    id: `camera-${id}`,
    title: `Public camera ${id}`,
    source_mode: "live",
    video_url: "",
    poster_url: `/api/evidence/${id}`,
    location: {
      latitude: 37.77,
      longitude: -122.3,
      quality: "known_camera",
      label: `Camera ${id}`,
    },
  },
  live_evidence: {
    image_url: `/api/evidence/${id}`,
    observed_at: "2026-11-07T20:00:00Z",
    media_time_seconds: 112,
    window_seconds: 12,
    rule: "stationary_vehicle",
    summary: `Stationarity over 12 seconds ${id}`,
    detections,
  },
});
const replay: Incident = {
  ...live("replay"),
  source_id: replaySource.id,
  source_mode: "recorded_replay",
  analysis_mode: "fixture",
  live_source: undefined,
  live_evidence: undefined,
  title: "Recorded replay candidate",
  location: replaySource.location,
};
const stateFor = (incidents: Incident[] = [], id = "run-one"): State => ({
  run: { id, created_at: "", status: "idle" },
  incidents,
  analysis: { mode: "fixture", status: "idle", message: "Ready" },
  telemetry: {
    network_inference_calls: 0,
    cache_hits: 0,
    fixture_runs: 0,
    estimated_spend_usd: 0,
  },
});
let current: State, container: HTMLDivElement, root: Root;
let fetchImage: ReturnType<typeof vi.fn>;
const click = async (selector: string) => {
  const button = container.querySelector<HTMLButtonElement>(selector)!;
  expect(button).not.toBeNull();
  await act(async () => button.click());
};
const mount = async () => {
  await act(async () => root.render(createElement(App)));
};
const tick = async () => {
  await act(async () => vi.advanceTimersByTimeAsync(2000));
};
beforeEach(() => {
  vi.useFakeTimers();
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  window.history.replaceState({}, "", "/");
  current = stateFor();
  vi.mocked(request).mockReset();
  vi.mocked(post).mockReset();
  vi.stubGlobal("crypto", {
    subtle: {
      digest: vi.fn(
        async () => Uint8Array.from({ length: 32 }, () => 171).buffer,
      ),
    },
  });
  vi.stubGlobal(
    "matchMedia",
    vi.fn(() => ({ matches: true })),
  );
  HTMLElement.prototype.scrollIntoView = vi.fn();
  vi.stubGlobal(
    "fetch",
    (fetchImage = vi.fn(async () => ({
      ok: true,
      arrayBuffer: async () => new Uint8Array([1, 2, 3]).buffer,
    }))),
  );
  vi.stubGlobal(
    "URL",
    class extends URL {
      static createObjectURL = vi.fn(() => "blob:verified-frame");
      static revokeObjectURL = vi.fn();
    },
  );
  vi.mocked(request).mockImplementation(async (path) => {
    if (path === "/api/state") return current;
    if (path === "/api/sources")
      return {
        sources: [
          replaySource,
          { ...replaySource, id: "street-traffic", title: "Control clip" },
        ],
      };
    if (path === "/api/config")
      return {
        public_base_url: null,
        default_analysis_mode: "fixture",
        model_configured: false,
        budgets: { gemini: 5, claude: 10, openai: 0 },
      };
    if (path === "/api/live-cameras")
      return {
        status: "unavailable",
        provider: "Caltrans",
        mode: "live_snapshot_catalog",
        fetched_at: null,
        stale: true,
        refresh_interval_seconds: 30,
        regions: [],
        cameras: [],
      };
    if (path.startsWith("/api/respond/"))
      return {
        incident: current.incidents[0],
        source: current.incidents[0].live_source,
        run_id: "run-one",
        status: "candidate",
      };
    throw Error(`Unexpected path ${path}`);
  });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  window.history.replaceState({}, "", "/");
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("live incident review integration", () => {
  it("opens the exact queue/map candidate, confirms it, and preserves replay and streaming selections", async () => {
    const first = live("first"),
      second = live("second");
    current = stateFor([replay, first, second]);
    await mount();
    await click('[data-testid="camera"]');
    const cards = container.querySelectorAll<HTMLButtonElement>(
      '[data-testid="incident-card"]',
    );
    expect(cards).toHaveLength(3);
    await act(async () => cards[2].click());
    let evidence = container.querySelector('[data-testid="evidence-panel"]')!;
    expect(evidence.textContent).toContain("Public camera second");
    expect(evidence.textContent).not.toContain("Recorded replay");
    expect(evidence.querySelector("video")).toBeNull();
    expect(evidence.querySelector("button.timestamp")).toBeNull();
    expect(
      evidence.querySelector('[data-testid="live-yolo-boxes"]'),
    ).not.toBeNull();
    expect(evidence.querySelector("img")?.getAttribute("src")).toBe(
      "blob:verified-frame",
    );
    expect(container.querySelector('[data-testid="camera"]')?.textContent).toBe(
      "run-one:camera-streaming",
    );
    expect(
      container
        .querySelector<HTMLAnchorElement>('[data-testid="responder-preview"]')
        ?.getAttribute("href"),
    ).toBe("/respond/run-one/second");
    await click('[data-map-incident="first"]');
    evidence = container.querySelector('[data-testid="evidence-panel"]')!;
    expect(evidence.textContent).toContain("Public camera first");
    vi.mocked(post).mockResolvedValue({ ...first, review_status: "confirmed" });
    await click('[data-testid="confirm-incident"]');
    expect(post).toHaveBeenCalledWith(
      "/api/runs/run-one/incidents/first/confirm",
    );
    expect(evidence.textContent).toContain("Confirmed by operator");
    expect(container.querySelector('[data-testid="camera"]')?.textContent).toBe(
      "run-one:camera-streaming",
    );
    vi.mocked(post).mockResolvedValue(stateFor([replay]));
    await click('[data-testid="start-replay"]');
    expect(post).toHaveBeenLastCalledWith("/api/runs/run-one/replay", {
      source_id: "road-obstruction",
      analysis_mode: "fixture",
    });
  });
  it("selects the first arrival once, keeps operator focus on later polls, and clears evidence on reset", async () => {
    await mount();
    await click('[data-testid="camera"]');
    current = stateFor([live("first")]);
    await tick();
    expect(
      container.querySelector('[data-testid="evidence-panel"]')?.textContent,
    ).toContain("Public camera first");
    current = stateFor([live("second"), live("first")]);
    await tick();
    expect(
      container.querySelector('[data-testid="evidence-panel"]')?.textContent,
    ).toContain("Public camera first");
    current = stateFor([], "run-two");
    vi.mocked(post).mockResolvedValue(current);
    await click('[data-testid="reset-demo"]');
    expect(
      container.querySelectorAll('[data-testid="incident-card"]'),
    ).toHaveLength(0);
    expect(
      container.querySelector('[aria-label="Live camera incident evidence"]'),
    ).toBeNull();
    expect(container.querySelector('[data-testid="camera"]')?.textContent).toBe(
      "run-two:camera-streaming",
    );
  });
  it("browses another replay and changes analysis mode without deleting live evidence or stealing focus back", async () => {
    current = stateFor([live("first")]);
    await mount();
    await click('button[aria-label="Select Ordinary street traffic"]');
    expect(post).not.toHaveBeenCalled();
    expect(
      container.querySelector('[aria-label="Live camera incident evidence"]'),
    ).toBeNull();
    expect(
      container.querySelectorAll('[data-testid="incident-card"]'),
    ).toHaveLength(1);
    const mode = container.querySelector<HTMLSelectElement>(
      '[aria-label="Analysis mode"]',
    )!;
    await act(async () => {
      mode.value = "cached";
      mode.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(post).not.toHaveBeenCalled();
    current = stateFor([live("first"), live("second")]);
    await tick();
    expect(
      container.querySelector('[aria-label="Live camera incident evidence"]'),
    ).toBeNull();
    expect(
      container.querySelectorAll('[data-testid="incident-card"]'),
    ).toHaveLength(2);
    vi.mocked(post).mockResolvedValue(current);
    await click('[data-testid="start-replay"]');
    expect(post).toHaveBeenLastCalledWith("/api/runs/run-one/replay", {
      source_id: "street-traffic",
      analysis_mode: "cached",
    });
  });
  it("renders a truthful live responder, tracks review state, and expires its saved image", async () => {
    current = stateFor([live("first")]);
    window.history.replaceState({}, "", "/respond/run-one/first");
    await mount();
    expect(container.textContent).toContain("PUBLIC CCTV · FROZEN EVIDENCE");
    expect(container.textContent).not.toContain("Recorded replay");
    expect(container.textContent).not.toContain("historical replay");
    expect(container.querySelector("video")).toBeNull();
    expect(
      container.querySelector('[data-testid="live-yolo-boxes"]'),
    ).not.toBeNull();
    current = stateFor([{ ...live("first"), review_status: "confirmed" }]);
    await tick();
    expect(container.textContent).toContain("Operator confirmed");
    const voice = buildVoiceBrief(current.incidents[0]);
    expect(voice).toContain("Frozen evidence from a live feed");
    expect(voice).not.toContain("Recorded footage");
    vi.mocked(request).mockRejectedValue(new ApiError(410, "Expired"));
    await tick();
    expect(container.textContent).toContain("This handoff has expired");
    expect(container.querySelector("img")).toBeNull();
  });
  it("does not show boxes when the saved frame hash differs or a prior camera fetch returns late", async () => {
    let resolve!: (value: any) => void;
    fetchImage.mockImplementationOnce(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    );
    current = stateFor([live("first"), live("second")]);
    await mount();
    expect(
      container.querySelector('[data-testid="live-yolo-boxes"]'),
    ).toBeNull();
    vi.mocked(crypto.subtle.digest).mockResolvedValueOnce(
      new Uint8Array(32).buffer,
    );
    const cards = container.querySelectorAll<HTMLButtonElement>(
      '[data-testid="incident-card"]',
    );
    await act(async () => cards[1].click());
    expect(
      container.querySelector('[data-testid="evidence-panel"]')?.textContent,
    ).toContain("trigger image is unavailable");
    await act(async () =>
      resolve({
        ok: true,
        arrayBuffer: async () => new Uint8Array([1]).buffer,
      }),
    );
    expect(
      container.querySelector('[data-testid="live-yolo-boxes"]'),
    ).toBeNull();
    expect(container.querySelector("img")).toBeNull();
  });
});
