import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MapView } from "../src/MapView";
import { request } from "../src/api";
import { readCameraContext } from "../src/mapContext";
import type { Incident, Source } from "../src/types";
import type { LiveCamera } from "../src/liveCameras";

const mocks = vi.hoisted(() => ({ viewers: [] as any[], handlers: [] as any[], createTiles: vi.fn() }));
vi.mock("../src/api", () => ({ request: vi.fn() }));
vi.mock("cesium", async (original) => {
  const real = await original<object>();
  return { ...real,
    Viewer: class {
      records = new Map<string, any>();
      entities = { getById: (id: string) => this.records.get(id), removeById: vi.fn((id: string) => this.records.delete(id)), add: vi.fn((entity: any) => {
        this.records.set(entity.id, entity); return entity;
      }) };
      scene = { backgroundColor: null, globe: { baseColor: null, enableLighting: false, show: true },
        screenSpaceCameraController: {}, canvas: document.createElement("canvas"),
        renderError: { addEventListener: vi.fn() },
        postRender: { addEventListener: vi.fn(() => vi.fn()) }, requestRender: vi.fn(),
        primitives: { add: vi.fn(), remove: vi.fn() }, pick: vi.fn(), };
      imageryLayers = { addImageryProvider: vi.fn(() => ({})) };
      camera = { flyTo: vi.fn(), zoomIn: vi.fn(), zoomOut: vi.fn(), positionCartographic: { height: 1450 } };
      isDestroyed = vi.fn(() => false); destroy = vi.fn();
      constructor() { mocks.viewers.push(this); }
    },
    ScreenSpaceEventHandler: class {
      input: any;
      setInputAction = vi.fn((fn: any) => { this.input = fn; }); destroy = vi.fn();
      constructor() { mocks.handlers.push(this); }
    },
    OpenStreetMapImageryProvider: class { errorEvent = { addEventListener: vi.fn() }; },
    createGooglePhotorealistic3DTileset: mocks.createTiles,
  };
});
const source = { id: "road-obstruction", title: "Obstruction replay", source_mode: "recorded_replay",
  duration_seconds: 11.1, media_available: true,
  location: { latitude: 35.994, longitude: -78.8986, quality: "simulated", label: "Durham demo" },
} as Source;
const incident = { id: "candidate", review_status: "candidate", evidence: [{ timestamp_seconds: 1, observation: "Roadway obstruction" }] } as Incident;
const point = { id: "ncdot-test", name: "Official camera", description: "NC 147", latitude: 35.99,
  longitude: -78.9, quality: "official_inventory", status: "metadata_only" };
const context = { status: "available", mode: "inventory_snapshot", fetched_at: "2026-11-07T16:00:00Z",
  stale: false, attribution: "NCDOT", source_url: "https://www.ncdot.gov/", points: [point] };
const liveCamera: LiveCamera = {
  id: "caltrans-d4-7", name: "Test public camera", latitude: 37.8, longitude: -122.3,
  region_id: "alameda", region_name: "Alameda", roadway: "I-80", direction: "East",
  provider: "Caltrans", provider_url: "https://quickmap.dot.ca.gov/", mode: "refreshed_snapshot",
  in_service_reported: true, capture_time: null,
};
let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  (globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
  vi.stubEnv("VITE_MAP_OFFLINE", "false");
  vi.stubEnv("VITE_CESIUM_ION_TOKEN", "");
  vi.stubEnv("VITE_PHOTOREALISTIC_TILES", "false");
  vi.stubGlobal("PerformanceObserver", class { observe() {} disconnect() {} });
  vi.stubGlobal("matchMedia", vi.fn(() => ({ matches: true })));
  mocks.viewers.length = 0;
  mocks.handlers.length = 0;
  mocks.createTiles.mockReset();
  vi.mocked(request).mockResolvedValue(context);
  container = document.createElement("div"); document.body.append(container);
  root = createRoot(container);
});

describe("public snapshot map layer", () => {
  const renderLive = async (cameras: LiveCamera[], selected: string | null = null, onSelect = vi.fn(), replaySelect = vi.fn()) => {
    await act(async () => root.render(createElement(MapView, {
      source, incident, onSelect: replaySelect,
      liveCameras: cameras, liveSelectedId: selected, onSelectLiveCamera: onSelect,
    })));
  };

  it("updates public pins without replacing the viewer, inventory or replay incident", async () => {
    await renderLive([liveCamera]);
    const viewer = mocks.viewers[0];
    const cameraEntity = viewer.records.get(`public-camera:${liveCamera.id}`);
    expect(cameraEntity).toBeTruthy();
    await renderLive([{ ...liveCamera }], liveCamera.id);
    expect(mocks.viewers).toHaveLength(1);
    expect(viewer.records.get(`public-camera:${liveCamera.id}`)).toBe(cameraEntity);
    expect(viewer.records.has("selected-source")).toBe(true);
    expect(viewer.records.has("context-camera:ncdot-test")).toBe(true);
    expect(container.textContent).toContain("Public traffic cameras");
    expect(container.textContent).toContain("Separate replay evidence");
    await renderLive([]);
    expect(viewer.records.has(`public-camera:${liveCamera.id}`)).toBe(false);
    expect(viewer.records.has("selected-source")).toBe(true);
  });

  it("routes a public pin click to the preview, not to replay evidence", async () => {
    const onLive = vi.fn(); const onReplay = vi.fn();
    await renderLive([liveCamera], null, onLive, onReplay);
    mocks.viewers[0].scene.pick.mockReturnValue({ id: { id: `public-camera:${liveCamera.id}` } });
    await act(async () => mocks.handlers[0].input({ position: {} }));
    expect(onLive).toHaveBeenCalledWith(liveCamera.id);
    expect(onReplay).not.toHaveBeenCalled();
  });

  it("bounds the layer and filters invalid coordinates without claiming online availability", async () => {
    const cameras = Array.from({ length: 101 }, (_, i) => ({ ...liveCamera, id: `camera-${i}` }));
    await renderLive([{ ...liveCamera, id: "bad", latitude: 100 }, ...cameras]);
    const viewer = mocks.viewers[0];
    expect([...viewer.records.keys()].filter((id) => id.startsWith("public-camera:"))).toHaveLength(100);
    expect(viewer.records.has("public-camera:bad")).toBe(false);
    expect(container.textContent).toContain("Pin presence does not prove the camera is online");
    const toggle = container.querySelector<HTMLInputElement>('[data-testid="map-public-toggle"]')!;
    await act(async () => toggle.click());
    expect(viewer.records.get("public-camera:camera-0").show).toBe(false);
    expect(viewer.records.get("context-camera:ncdot-test").show).toBe(true);
  });
});
afterEach(async () => {
  await act(async () => root.unmount()); container.remove();
  vi.unstubAllEnvs(); vi.unstubAllGlobals();
});
const render = async (value?: Incident) => {
  await act(async () => root.render(createElement(MapView, { source, incident: value, onSelect: vi.fn() })));
};

describe("map replay lifecycle", () => {
  it("keeps one viewer and marker while replacing review text as ordinary HTML", async () => {
    await render();
    expect(container.querySelector('[data-testid="map-world-label"]')?.textContent).toBe("DEMO CAMERA");
    await render(incident);
    expect(container.querySelector('[data-testid="map-world-label"]')?.textContent).toBe("REVIEW CANDIDATE");
    await render({ ...incident, review_status: "confirmed" });
    expect(container.querySelector('[data-testid="map-world-label"]')?.textContent).toBe("CONFIRMED DEMO");
    await render();
    expect(container.querySelector('[data-testid="map-world-label"]')?.textContent).toBe("DEMO CAMERA");
    expect(mocks.viewers).toHaveLength(1);
    const markers = mocks.viewers[0].entities.add.mock.calls.filter(([e]: any[]) => e.id === "selected-source");
    expect(markers).toHaveLength(1);
    expect(mocks.viewers[0].records.get("selected-source").label).toBeUndefined();
    expect(mocks.createTiles).not.toHaveBeenCalled();
  });

  it("keeps context cameras separate and hides them without changing the replay marker", async () => {
    await render(incident);
    expect(container.textContent).toContain("Inventory only");
    expect(container.textContent).toContain("Simulated placement");
    const viewer = mocks.viewers[0];
    expect(viewer.records.get("context-camera:ncdot-test").show).toBe(true);
    const toggle = container.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    await act(async () => toggle.click());
    expect(viewer.records.get("context-camera:ncdot-test").show).toBe(false);
    expect(viewer.records.has("selected-source")).toBe(true);
    expect(container.textContent).toContain("Google 3D is not configured");
  });

  it("does not call a loaded root metadata response a rendered 3D city", async () => {
    vi.stubEnv("VITE_CESIUM_ION_TOKEN", "test-public-token");
    vi.stubEnv("VITE_PHOTOREALISTIC_TILES", "true");
    let onTile!: () => void;
    const tileset = { destroy: vi.fn(), tileLoad: { addEventListener: vi.fn((fn) => { onTile = fn; return vi.fn(); }) },
      tileFailed: { addEventListener: vi.fn() } };
    mocks.createTiles.mockResolvedValue(tileset);
    await render();
    expect(container.textContent).toContain("Loading Google 3D");
    expect(container.textContent).not.toContain("Photorealistic 3D");
    await act(async () => onTile());
    expect(container.textContent).toContain("Photorealistic 3D");
    await render(incident);
    expect(mocks.createTiles).toHaveBeenCalledTimes(1);
  });

  it("falls back after an unavailable 3D service without displaying raw provider errors", async () => {
    vi.stubEnv("VITE_CESIUM_ION_TOKEN", "test-public-token");
    vi.stubEnv("VITE_PHOTOREALISTIC_TILES", "true");
    mocks.createTiles.mockRejectedValue(new Error("secret provider URL"));
    await render();
    expect(container.textContent).toContain("3D unavailable");
    expect(container.textContent).not.toContain("secret provider URL");
    expect(mocks.viewers[0].imageryLayers.addImageryProvider).toHaveBeenCalledTimes(1);
  });
});

describe("camera inventory boundaries", () => {
  it("does not display invalid coordinates, duplicate IDs, or live claims as inventory points", () => {
    const result = readCameraContext({ ...context, points: [point, point,
      { ...point, id: "bad", latitude: 100 }, { ...point, id: "live", status: "live" }] });
    expect(result?.points).toEqual([point]);
    expect(readCameraContext({ ...context, mode: "live" })).toBeNull();
    expect(readCameraContext({ ...context, status: "unavailable" })?.points).toEqual([]);
  });

  it("rejects unsafe source links and marks missing freshness metadata as unknown", () => {
    const result = readCameraContext({ ...context, source_url: "javascript:alert(1)", fetched_at: "not a date", stale: null });
    expect(result?.source_url).toBeNull();
    expect(result?.fetched_at).toBeNull();
    expect(result?.stale).toBe(true);
  });
});
