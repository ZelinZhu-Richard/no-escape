import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LiveCameraPanel } from "../src/LiveCameraPanel";
import {
  filterLiveCameras,
  readLiveCameraCatalog,
  readLiveSnapshot,
  readImageDetections,
  publicStreamUrl,
} from "../src/liveCameras";
import type {
  LiveCamera,
  LiveCameraCatalog,
  LiveSnapshot,
  ImageDetections,
} from "../src/liveCameras";
import { request } from "../src/api";

vi.mock("../src/api", () => ({ request: vi.fn() }));
const hlsMock = vi.hoisted(() => ({ instances: [] as any[] }));
vi.mock("hls.js", () => ({
  default: class {
    static isSupported = () => true;
    static Events = {
      ERROR: "error",
      LEVEL_LOADED: "level",
      MANIFEST_PARSED: "manifest",
    };
    handlers = new Map<string, (...args: any[]) => void>();
    destroy = vi.fn();
    loadSource = vi.fn();
    attachMedia = vi.fn();
    on = (event: string, callback: (...args: any[]) => void) => {
      this.handlers.set(event, callback);
    };
    constructor() {
      hlsMock.instances.push(this);
    }
  },
}));
const verifiedHash = "ab".repeat(32);
const detection = (hash = verifiedHash): ImageDetections => ({
  status: "available",
  analysis_mode: "fresh",
  image_sha256: hash,
  image_width: 352,
  image_height: 240,
  boxes: [{ class_name: "car", confidence: 0.91, xyxy: [0.1, 0.2, 0.4, 0.8] }],
  vehicle_count: 1,
  person_count: 0,
  model: { name: "YOLOX-Tiny", version: "test" },
  provenance: {
    kind: "local_yolo_image",
    fixture: false,
    image_sha256: hash,
    analyzed_at: "2026-11-07T17:30:00Z",
  },
  inference_ms: 25,
});
const camera = (id: string, region = "san-francisco"): LiveCamera => ({
  id,
  name: id === "camera-a" ? "Bay Bridge Approach" : "Oakland Freeway",
  latitude: 37.78,
  longitude: -122.4,
  region_id: region,
  region_name: region === "san-francisco" ? "San Francisco" : "Oakland",
  roadway: "I-80",
  direction: "East",
  provider: "Caltrans",
  provider_url: "https://cwwp2.dot.ca.gov/",
  mode: "refreshed_snapshot",
  in_service_reported: true,
  capture_time: null,
  source_refresh_seconds: 300,
});
const cameras = [camera("camera-a"), camera("camera-b", "oakland")];
const catalog: LiveCameraCatalog = {
  status: "available",
  provider: "Caltrans",
  mode: "live_snapshot_catalog",
  fetched_at: "2026-11-07T17:00:00Z",
  stale: false,
  refresh_interval_seconds: 30,
  regions: [
    { id: "san-francisco", name: "San Francisco" },
    { id: "oakland", name: "Oakland" },
  ],
  cameras,
};
const snapshot = (cameraId = "camera-a"): LiveSnapshot => ({
  status: "available",
  camera_id: cameraId,
  mode: "refreshed_snapshot",
  image_data_url: "data:image/jpeg;base64,/9j/AA==",
  fetched_at: "2026-11-07T17:30:00Z",
  source_last_modified: "2026-11-07T17:25:00Z",
  capture_time: null,
  stale: false,
  refresh_after_seconds: 300,
  message: "",
});
let container: HTMLDivElement;
let root: Root;
let visibility: ReturnType<typeof vi.spyOn>;
beforeEach(() => {
  (
    globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-11-07T17:30:00Z"));
  visibility = vi
    .spyOn(document, "visibilityState", "get")
    .mockReturnValue("visible");
  vi.mocked(request).mockReset();
  hlsMock.instances.length = 0;
  vi.stubGlobal("crypto", {
    subtle: { digest: vi.fn(async () => new Uint8Array(32).fill(0xab).buffer) },
  });
  vi.spyOn(HTMLMediaElement.prototype, "canPlayType").mockReturnValue("");
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  vi.spyOn(HTMLMediaElement.prototype, "load").mockImplementation(() => {});
  vi.mocked(request).mockImplementation(async (path) =>
    snapshot(path.includes("camera-b") ? "camera-b" : "camera-a"),
  );
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});
const render = async (
  selectedId: string | null = "camera-a",
  active = true,
) => {
  await act(async () =>
    root.render(
      <LiveCameraPanel
        catalog={catalog}
        selectedId={selectedId}
        onSelect={vi.fn()}
        active={active}
      />,
    ),
  );
};
const advance = async (milliseconds: number) => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(milliseconds);
  });
};

describe("public camera data boundaries", () => {
  it("preserves bounded camera-text exclusions and rejects invalid regions", () => {
    const regions = [{ id: "provider-title", xyxy: [0, 0, 0.46, 0.08] }];
    expect(readImageDetections({ ...detection(), excluded_regions: regions }, verifiedHash)?.excluded_regions).toEqual(regions);
    for (const xyxy of [[0, 0, 2, 1], [0.5, 0, 0.1, 1], [0, 0, NaN, 1]]) {
      expect(readImageDetections({ ...detection(), excluded_regions: [{ id: "provider-title", xyxy }] }, verifiedHash)).toBeNull();
    }
  });
  it("only allows official HLS sources and source-bound genuine local detections", () => {
    expect(
      publicStreamUrl(
        "https://wzmedia.dot.ca.gov/D4/E80_at_SAS_Tower.stream/playlist.m3u8",
      ),
    ).not.toBeNull();
    expect(
      publicStreamUrl("https://other.example/D4/test/playlist.m3u8"),
    ).toBeNull();
    expect(
      publicStreamUrl(
        "https://wzmedia.dot.ca.gov/D4/test/playlist.m3u8?token=unexpected",
      ),
    ).toBeNull();
    expect(readImageDetections(detection(), verifiedHash)?.vehicle_count).toBe(
      1,
    );
    expect(readImageDetections(detection(), "ff".repeat(32))).toBeNull();
    expect(
      readImageDetections(
        {
          ...detection(),
          provenance: { ...detection().provenance, fixture: true },
        },
        verifiedHash,
      ),
    ).toBeNull();
    expect(
      readImageDetections(
        {
          ...detection(),
          boxes: [{ class_name: "car", confidence: 0.9, xyxy: [-1, 0, 1, 1] }],
        },
        verifiedHash,
      ),
    ).toBeNull();
  });
  it("rejects false live-video modes, bad coordinates, duplicate IDs, and unsafe links", () => {
    const value = readLiveCameraCatalog({
      ...catalog,
      cameras: [
        cameras[0],
        cameras[0],
        { ...cameras[1], mode: "live_video" },
        { ...cameras[1], latitude: 99 },
        { ...cameras[1], provider_url: "javascript:alert(1)" },
      ],
    });
    expect(value?.cameras).toHaveLength(2);
    expect(value?.cameras[1].provider_url).toBeNull();
    expect(
      readLiveCameraCatalog({ ...catalog, mode: "recorded_replay" }),
    ).toBeNull();
  });
  it("keeps capture time unknown and refuses another camera's or non-JPEG data", () => {
    const result = readLiveSnapshot(snapshot(), "camera-a");
    expect(result?.capture_time).toBeNull();
    expect(result?.source_last_modified).toBe("2026-11-07T17:25:00Z");
    expect(readLiveSnapshot(snapshot(), "camera-b")).toBeNull();
    expect(
      readLiveSnapshot(
        { ...snapshot(), image_data_url: "data:image/svg+xml;base64,AAAA" },
        "camera-a",
      ),
    ).toBeNull();
  });
  it("filters only camera metadata and clamps provider retry intervals", () => {
    expect(
      filterLiveCameras(cameras, "oakland", "i-80 east").map((item) => item.id),
    ).toEqual(["camera-b"]);
    expect(
      filterLiveCameras(cameras, "", "bay bridge").map((item) => item.id),
    ).toEqual(["camera-a"]);
    expect(
      readLiveSnapshot(
        {
          ...snapshot(),
          status: "throttled",
          image_data_url: null,
          refresh_after_seconds: 5,
        },
        "camera-a",
      )?.refresh_after_seconds,
    ).toBe(30);
  });
});

describe("selected public camera preview", () => {
  it("draws snapshot boxes only after its actual bytes verify against the source hash", async () => {
    vi.mocked(request).mockResolvedValue({
      ...snapshot(),
      image_sha256: verifiedHash,
      detections: detection(),
    });
    await render();
    expect(
      container.querySelector('[data-testid="live-yolo-boxes"]'),
    ).not.toBeNull();
    expect(container.textContent).toContain("1 vehicles");
    expect(container.textContent).toContain(
      "YOLO boxes match this exact snapshot",
    );
    const bad = "ff".repeat(32);
    vi.mocked(request).mockResolvedValue({
      ...snapshot("camera-b"),
      image_sha256: bad,
      detections: detection(bad),
    });
    await render("camera-b");
    expect(
      container.querySelector('[data-testid="live-yolo-boxes"]'),
    ).toBeNull();
  });

  it("draws fresh YOLO boxes on the playing video and stops the stream when hidden", async () => {
    const streamCamera = {
      ...cameras[0],
      streaming_url:
        "https://wzmedia.dot.ca.gov/D4/E80_at_SAS_Tower.stream/playlist.m3u8",
    };
    vi.mocked(request).mockResolvedValue(detection());
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      drawImage: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockReturnValue(
      snapshot().image_data_url!,
    );
    await act(async () =>
      root.render(
        <LiveCameraPanel
          catalog={{ ...catalog, cameras: [streamCamera] }}
          selectedId="camera-a"
          onSelect={vi.fn()}
        />,
      ),
    );
    expect(request).not.toHaveBeenCalled();
    const player = hlsMock.instances[0];
    expect(player.loadSource).toHaveBeenCalledWith(streamCamera.streaming_url);
    const video = container.querySelector("video")!;
    Object.defineProperties(video, {
      videoWidth: { value: 352 },
      videoHeight: { value: 240 },
      readyState: { value: 4 },
      paused: { get: () => false },
    });
    video.currentTime = 1.5;
    await act(async () => {
      player.handlers.get("level")("level", { details: { live: true } });
      video.dispatchEvent(new Event("playing"));
    });
    await advance(50);
    expect(request).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(request).mock.calls[0];
    expect(path).toBe("/api/live-cameras/camera-a/detect-frame");
    expect(options?.method).toBe("POST");
    expect(options?.headers).toEqual({ "Content-Type": "image/jpeg" });
    expect(
      container.querySelector(".live-stream-frame .live-image-boxes"),
    ).not.toBeNull();
    expect(
      container.querySelector(".live-analyzed-frame .live-image-boxes"),
    ).toBeNull();
    expect(
      container
        .querySelector('[data-testid="live-direct-overlay"]')
        ?.getAttribute("data-media-time"),
    ).toBe("1.5");
    expect(
      container
        .querySelector(".live-stream-frame svg")
        ?.getAttribute("viewBox"),
    ).toBe("0 0 352 240");
    expect(container.querySelector(".live-video-view img")).toBeNull();
    expect(container.querySelector(".live-stream-frame svg text")).toBeNull();
    expect(container.querySelector('[data-testid="live-detection-summary"]')?.textContent).toContain("1 vehicles");
    const showLabels = [...container.querySelectorAll("button")].find(button => button.textContent === "Show labels")!;
    await act(async () => showLabels.click());
    expect(container.querySelector(".live-stream-frame svg text")?.textContent).toContain("car");
    expect(hlsMock.instances).toHaveLength(1);
    await act(async () => {
      visibility.mockReturnValue("hidden");
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(player.destroy).toHaveBeenCalledTimes(1);
    await advance(5000);
    expect(request).toHaveBeenCalledTimes(1);
  });

  it("clears zero detections, expires stalled boxes, and resets on seek without reusing old responses", async () => {
    const streamCamera = {
      ...cameras[0],
      streaming_url:
        "https://wzmedia.dot.ca.gov/D4/E80_at_SAS_Tower.stream/playlist.m3u8",
    };
    vi.mocked(request).mockResolvedValue(detection());
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      drawImage: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockReturnValue(
      snapshot().image_data_url!,
    );
    await act(async () =>
      root.render(
        <LiveCameraPanel
          catalog={{ ...catalog, cameras: [streamCamera] }}
          selectedId="camera-a"
          onSelect={vi.fn()}
        />,
      ),
    );
    const video = container.querySelector("video")!;
    Object.defineProperties(video, {
      videoWidth: { value: 352 },
      videoHeight: { value: 240 },
      readyState: { value: 4 },
      paused: { get: () => false },
    });
    video.currentTime = 1;
    await act(async () => {
      hlsMock.instances[0].handlers.get("level")("level", {
        details: { live: true },
      });
      video.dispatchEvent(new Event("playing"));
    });
    await advance(50);
    expect(
      container.querySelector(".live-stream-frame .detection-box"),
    ).not.toBeNull();
    vi.mocked(request).mockResolvedValue({
      ...detection(),
      boxes: [],
      vehicle_count: 0,
    });
    video.currentTime = 1.2;
    await advance(180);
    expect(
      container.querySelector(".live-stream-frame .detection-box"),
    ).toBeNull();
    vi.mocked(request).mockResolvedValue(detection());
    video.currentTime = 1.4;
    await advance(180);
    expect(
      container.querySelector(".live-stream-frame .detection-box"),
    ).not.toBeNull();
    await advance(501);
    expect(
      container.querySelector('[data-testid="live-direct-overlay"]'),
    ).toBeNull();
    expect(container.textContent).toContain("delayed");
    let resolve!: (value: ImageDetections) => void;
    vi.mocked(request).mockReturnValue(
      new Promise<ImageDetections>((done) => {
        resolve = done;
      }),
    );
    video.currentTime = 1.6;
    await advance(20);
    const pendingSignal = vi.mocked(request).mock.calls.at(-1)?.[1]?.signal;
    await act(async () => {
      video.currentTime = 0.1;
      video.dispatchEvent(new Event("seeking"));
    });
    expect(pendingSignal?.aborted).toBe(true);
    await act(async () => resolve(detection()));
    expect(
      container.querySelector('[data-testid="live-direct-overlay"]'),
    ).toBeNull();
  });

  it("uses rVFC presentation time and rejects delayed results without queuing frames", async () => {
    const streamCamera = {
      ...cameras[0],
      streaming_url:
        "https://wzmedia.dot.ca.gov/D4/E80_at_SAS_Tower.stream/playlist.m3u8",
    };
    vi.mocked(request).mockResolvedValue(detection());
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
      drawImage: vi.fn(),
    } as unknown as CanvasRenderingContext2D);
    vi.spyOn(HTMLCanvasElement.prototype, "toDataURL").mockReturnValue(
      snapshot().image_data_url!,
    );
    await act(async () =>
      root.render(
        <LiveCameraPanel
          catalog={{ ...catalog, cameras: [streamCamera] }}
          selectedId="camera-a"
          onSelect={vi.fn()}
        />,
      ),
    );
    const video = container.querySelector("video")!;
    let presented!: VideoFrameRequestCallback;
    let callbackId = 0;
    Object.defineProperties(video, {
      videoWidth: { value: 352 },
      videoHeight: { value: 240 },
      readyState: { value: 4 },
      paused: { get: () => false },
      requestVideoFrameCallback: {
        value: vi.fn((callback: VideoFrameRequestCallback) => {
          presented = callback;
          return ++callbackId;
        }),
      },
      cancelVideoFrameCallback: { value: vi.fn() },
    });
    // currentTime is deliberately different: boxes must follow the frame that
    // was presented, not the media element's more advanced playback clock.
    video.currentTime = 99;
    await act(async () => {
      hlsMock.instances[0].handlers.get("level")("level", {
        details: { live: true },
      });
      video.dispatchEvent(new Event("playing"));
    });
    const present = async (mediaTime: number) => {
      await act(async () =>
        presented(performance.now(), {
          mediaTime,
        } as VideoFrameCallbackMetadata),
      );
    };
    await present(1.5);
    await advance(20);
    expect(
      container
        .querySelector('[data-testid="live-direct-overlay"]')
        ?.getAttribute("data-media-time"),
    ).toBe("1.5");
    expect(request).toHaveBeenCalledTimes(1);

    let resolveMediaLate!: (value: ImageDetections) => void;
    vi.mocked(request).mockReturnValue(
      new Promise<ImageDetections>((done) => {
        resolveMediaLate = done;
      }),
    );
    await advance(140);
    await present(1.7);
    expect(request).toHaveBeenCalledTimes(2);
    await advance(200);
    await present(1.9);
    await advance(100);
    await present(2.1);
    expect(request).toHaveBeenCalledTimes(2); // one request in flight, no backlog
    await act(async () => resolveMediaLate(detection()));
    expect(
      container.querySelector('[data-testid="live-direct-overlay"]'),
    ).toBeNull();

    let resolveWallLate!: (value: ImageDetections) => void;
    vi.mocked(request).mockReturnValue(
      new Promise<ImageDetections>((done) => {
        resolveWallLate = done;
      }),
    );
    await advance(140);
    await present(2.2);
    expect(request).toHaveBeenCalledTimes(3);
    await advance(501);
    await act(async () => resolveWallLate(detection()));
    expect(
      container.querySelector('[data-testid="live-direct-overlay"]'),
    ).toBeNull();
    expect(container.textContent).toContain("delayed");
  });

  it("falls back to the selected provider snapshot when HLS fails", async () => {
    const streamCamera = {
      ...cameras[0],
      streaming_url:
        "https://wzmedia.dot.ca.gov/D4/E80_at_SAS_Tower.stream/playlist.m3u8",
    };
    await act(async () =>
      root.render(
        <LiveCameraPanel
          catalog={{ ...catalog, cameras: [streamCamera] }}
          selectedId="camera-a"
          onSelect={vi.fn()}
        />,
      ),
    );
    await act(async () =>
      hlsMock.instances[0].handlers.get("error")("error", { fatal: true }),
    );
    expect(container.textContent).toContain(
      "Showing its provider snapshot instead",
    );
    expect(container.querySelector("video")).toBeNull();
    expect(container.querySelector("img")).not.toBeNull();
    expect(request).toHaveBeenCalledTimes(1);
    expect(vi.mocked(request).mock.calls[0][0]).toBe(
      "/api/live-cameras/camera-a/snapshot",
    );
  });
  it("makes no snapshot requests until a camera is deliberately selected", async () => {
    await render(null);
    expect(request).not.toHaveBeenCalled();
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("2 cameras");
    await render();
    expect(request).toHaveBeenCalledTimes(1);
    expect(vi.mocked(request).mock.calls[0][0]).toBe(
      "/api/live-cameras/camera-a/snapshot",
    );
    expect(container.textContent).toContain("REFRESHED SNAPSHOT");
    expect(container.textContent).toContain("Source cadence 5 min");
    expect(container.textContent).toContain("Provider last modified");
    expect(container.textContent).toContain("Capture timeUnknown");
  });
  it("refreshes at the source cadence and stops updates when hidden", async () => {
    await render();
    await advance(299_999);
    expect(request).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(request).toHaveBeenCalledTimes(2);
    await act(async () => {
      visibility.mockReturnValue("hidden");
      document.dispatchEvent(new Event("visibilitychange"));
    });
    await advance(600_000);
    expect(request).toHaveBeenCalledTimes(2);
    await act(async () => {
      visibility.mockReturnValue("visible");
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(request).toHaveBeenCalledTimes(3);
  });
  it("restores A after A to B to A without waiting five minutes or refetching", async () => {
    await render("camera-a");
    await render("camera-b");
    await render("camera-a");
    expect(request).toHaveBeenCalledTimes(2);
    expect(container.querySelector("img")?.alt).toContain(
      "Bay Bridge Approach",
    );
    expect(container.querySelector("img")?.getAttribute("src")).toBe(
      snapshot().image_data_url,
    );
  });
  it("clears the prior camera image and ignores its late response on selection change", async () => {
    let resolveA!: (value: LiveSnapshot) => void;
    const pending = new Promise<LiveSnapshot>((resolve) => {
      resolveA = resolve;
    });
    vi.mocked(request).mockImplementation((path) =>
      path.includes("camera-a")
        ? pending
        : Promise.resolve(snapshot("camera-b")),
    );
    await render("camera-a");
    const signal = vi.mocked(request).mock.calls[0][1]?.signal;
    await render("camera-b");
    expect(signal?.aborted).toBe(true);
    await act(async () =>
      resolveA({
        ...snapshot(),
        image_data_url: "data:image/jpeg;base64,/9j/BBBB",
      }),
    );
    expect(container.querySelector("img")?.alt).toContain("Oakland Freeway");
    expect(container.querySelector("img")?.getAttribute("src")).toBe(
      snapshot("camera-b").image_data_url,
    );
  });
  it("marks a retained image stale after refresh failure and respects short server retries", async () => {
    await render();
    vi.mocked(request).mockResolvedValue({
      ...snapshot(),
      status: "throttled",
      image_data_url: null,
      refresh_after_seconds: 5,
    });
    await advance(300_000);
    expect(container.textContent).toContain("LAST RETRIEVED IMAGE");
    expect(container.textContent).toContain("Provider refresh limit reached");
    await advance(29_999);
    expect(request).toHaveBeenCalledTimes(2);
    await advance(1);
    expect(request).toHaveBeenCalledTimes(3);
  });
  it("allows pausing updates while keeping the selected image clearly labeled", async () => {
    await render();
    const pause = [...container.querySelectorAll("button")].find(
      (button) => button.textContent === "Pause updates",
    )!;
    await act(async () => pause.click());
    await advance(600_000);
    expect(request).toHaveBeenCalledTimes(1);
    expect(container.textContent).toContain("LAST RETRIEVED IMAGE");
    expect(container.textContent).toContain("Updates paused");
  });
  it("emits a filtered map list without fetching preview images", async () => {
    const changed = vi.fn();
    function Controlled() {
      const [selected, setSelected] = useState<string | null>(null);
      return (
        <LiveCameraPanel
          catalog={catalog}
          selectedId={selected}
          onSelect={setSelected}
          onVisibleCamerasChange={changed}
        />
      );
    }
    await act(async () => root.render(<Controlled />));
    const select = container.querySelector<HTMLSelectElement>("select")!;
    await act(async () => {
      select.value = "oakland";
      select.dispatchEvent(new Event("change", { bubbles: true }));
    });
    expect(
      changed.mock.calls.at(-1)?.[0].map((item: LiveCamera) => item.id),
    ).toEqual(["camera-b"]);
    expect(request).not.toHaveBeenCalled();
  });
});
