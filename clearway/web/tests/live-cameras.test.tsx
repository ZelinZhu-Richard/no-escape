import { act, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LiveCameraPanel } from "../src/LiveCameraPanel";
import {
  filterLiveCameras,
  readLiveCameraCatalog,
  readLiveSnapshot,
} from "../src/liveCameras";
import type {
  LiveCamera,
  LiveCameraCatalog,
  LiveSnapshot,
} from "../src/liveCameras";
import { request } from "../src/api";

vi.mock("../src/api", () => ({ request: vi.fn() }));
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
