import { act, createElement } from "react";
import { createRoot, type Root } from "react-dom/client";
import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { post, request } from "../src/api";
import type { Config, Incident, Source, State } from "../src/types";

vi.mock("../src/api", async (importOriginal) => ({
  ...(await importOriginal<object>()),
  request: vi.fn(),
  post: vi.fn(),
}));
vi.mock("../src/MapView", () => ({
  MapView: () => createElement("div", null, "Map placeholder"),
}));

const source: Source = {
  id: "road-obstruction",
  title: "Test footage",
  source_mode: "recorded_replay",
  video_url: "/fixture.webm",
  poster_url: "",
  duration_seconds: 11,
  media_available: false,
  control_status: "development",
  attribution: {
    creator: "Test",
    title: "Fixture",
    source_url: "#source",
    license: "CC BY",
    license_url: "#license",
  },
  location: {
    latitude: 0,
    longitude: 0,
    quality: "simulated",
    label: "Demo placement",
  },
};
const config: Config = {
  public_base_url: null,
  default_analysis_mode: "fixture",
  map_mode: "basic",
  budgets: { gemini: 0, claude: 10, openai: 0 },
  model_configured: false,
};
const stateFor = (run = "oldrun01", incidents: Incident[] = []): State => ({
  run: { id: run, created_at: "", status: "idle" },
  incidents,
  analysis: { mode: "fixture", status: "idle", message: "Ready" },
  telemetry: {
    network_inference_calls: 0,
    cache_hits: 0,
    fixture_runs: 0,
    estimated_spend_usd: 0,
  },
});
const candidate: Incident = {
  id: "candidate1",
  run_id: "oldrun01",
  source_id: source.id,
  title: "Possible road obstruction",
  category: "road_obstruction",
  source_mode: "recorded_replay",
  analysis_mode: "fixture",
  review_status: "candidate",
  created_at: "",
  confirmed_at: null,
  evidence: [{ timestamp_seconds: 1, observation: "Reference evidence" }],
  unknowns: ["Location unknown"],
  context_status: "not_applicable",
  location: source.location,
  provenance: {
    provider: null,
    model: null,
    prompt_version: "fixture",
    fixture: true,
    cache_key: null,
  },
  responder_path: "/respond/oldrun01/candidate1",
};
const deferred = <T,>() => {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
};
let container: HTMLDivElement;
let root: Root;
let currentState: State;
let nextState: (() => Promise<State>) | undefined;
let stateReads: number;

beforeEach(() => {
  vi.useFakeTimers();
  (
    globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  currentState = stateFor();
  nextState = undefined;
  stateReads = 0;
  vi.mocked(request).mockReset();
  vi.mocked(post).mockReset();
  vi.mocked(request).mockImplementation(async (path: string) => {
    if (path === "/api/config") return config;
    if (path === "/api/sources") return { sources: [source] };
    if (path === "/api/state") {
      stateReads++;
      return nextState ? nextState() : currentState;
    }
    throw new Error(`Unexpected request: ${path}`);
  });
  container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.useRealTimers();
});
const mount = async () => {
  await act(async () => root.render(createElement(App)));
};
const click = async (id: string) => {
  const button = container.querySelector<HTMLButtonElement>(
    `[data-testid="${id}"]`,
  );
  expect(button, `Missing button ${id}`).not.toBeNull();
  expect(button!.disabled).toBe(false);
  await act(async () => button!.click());
};
const tick = async () => {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(2000);
  });
};

describe("operator mutation and polling consistency", () => {
  it("ignores a pre-reset poll and skips new polling until reset commits", async () => {
    await mount();
    const oldPoll = deferred<State>();
    nextState = () => oldPoll.promise;
    await tick();
    const reset = deferred<State>();
    vi.mocked(post).mockReturnValue(reset.promise);
    await click("reset-demo");
    const before = stateReads;
    await tick();
    expect(stateReads).toBe(before);
    await act(async () => {
      reset.resolve(stateFor("newrun02"));
    });
    await act(async () => {
      oldPoll.resolve(stateFor("oldrun01", [candidate]));
    });
    expect(container.textContent).toContain("RUN NEWRUN02");
    expect(container.querySelector('[data-testid="incident-card"]')).toBeNull();
  });

  it("preserves confirmation when an older poll returns after the write", async () => {
    currentState = stateFor("oldrun01", [candidate]);
    await mount();
    const oldPoll = deferred<State>();
    nextState = () => oldPoll.promise;
    await tick();
    const confirmation = deferred<Incident>();
    vi.mocked(post).mockReturnValue(confirmation.promise);
    await click("confirm-incident");
    const before = stateReads;
    await tick();
    expect(stateReads).toBe(before);
    await act(async () => {
      confirmation.resolve({ ...candidate, review_status: "confirmed" });
    });
    await act(async () => {
      oldPoll.resolve(currentState);
    });
    expect(container.textContent).toContain("Confirmed by operator");
    expect(
      container.querySelector('[data-testid="confirm-incident"]'),
    ).toBeNull();
  });

  it("allows reset during a pending replay and ignores its late incident", async () => {
    await mount();
    const replay = deferred<State>();
    vi.mocked(post).mockImplementation(async (path) =>
      path.endsWith("/replay") ? replay.promise : stateFor("newrun02"),
    );
    await click("start-replay");
    await click("reset-demo");
    expect(container.textContent).toContain("RUN NEWRUN02");
    await act(async () => {
      replay.resolve(stateFor("oldrun01", [candidate]));
    });
    expect(container.textContent).toContain("RUN NEWRUN02");
    expect(container.querySelector('[data-testid="incident-card"]')).toBeNull();
    expect(
      container.querySelector<HTMLButtonElement>(
        '[data-testid="start-replay"]',
      )!.disabled,
    ).toBe(false);
  });

  it("does not let delayed initialization replace a newer reset", async () => {
    const initialConfig = deferred<Config>();
    const usual = vi.mocked(request).getMockImplementation()!;
    vi.mocked(request).mockImplementation((path, options) =>
      path === "/api/config" ? initialConfig.promise : usual(path, options),
    );
    await mount();
    await tick();
    vi.mocked(post).mockResolvedValue(stateFor("newrun02"));
    await click("reset-demo");
    await act(async () => {
      initialConfig.resolve(config);
    });
    expect(container.textContent).toContain("RUN NEWRUN02");
  });

  it("labels a missing cache as unavailable without claiming a cached result", async () => {
    currentState.analysis = {
      mode: "unavailable",
      status: "unavailable",
      message: "No cache entry",
    };
    await mount();
    expect(container.textContent).toContain("Analysis unavailable");
    expect(container.textContent).not.toContain("Cached model result");
    expect(container.textContent).not.toContain("This fixture produced");
  });
});
