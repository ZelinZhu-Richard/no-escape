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
  MapView: ({
    incidents = [],
    onSelectIncident,
  }: {
    incidents?: Incident[];
    onSelectIncident?: (id: string) => void;
  }) =>
    createElement(
      "div",
      null,
      "Map placeholder",
      ...incidents.map((incident) =>
        createElement(
          "button",
          {
            key: incident.id,
            "data-map-incident": incident.id,
            onClick: () => onSelectIncident?.(incident.id),
          },
          incident.title,
        ),
      ),
    ),
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
let availableSources: Source[];
let nextState: (() => Promise<State>) | undefined;
let stateReads: number;

beforeEach(() => {
  vi.useFakeTimers();
  (
    globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }
  ).IS_REACT_ACT_ENVIRONMENT = true;
  currentState = stateFor();
  availableSources = [source];
  nextState = undefined;
  stateReads = 0;
  vi.mocked(request).mockReset();
  vi.mocked(post).mockReset();
  vi.mocked(request).mockImplementation(async (path: string) => {
    if (path === "/api/config") return config;
    if (path === "/api/sources") return { sources: availableSources };
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
    currentState.source_analyses = { [source.id]: currentState.analysis };
    await mount();
    vi.mocked(post).mockResolvedValue(currentState);
    await click("start-replay");
    expect(container.textContent).toContain("Analysis unavailable");
    expect(container.textContent).not.toContain("Cached model result");
    expect(container.textContent).not.toContain("This fixture produced");
  });

  it("refreshes the responder origin and removes a stale QR when config is unavailable", async () => {
    currentState = stateFor("oldrun01", [candidate]);
    await mount();
    expect(container.textContent).toContain("phone access not configured");
    const usual = vi.mocked(request).getMockImplementation()!;
    vi.mocked(request).mockImplementation((path, options) =>
      path === "/api/config"
        ? Promise.resolve({
            ...config,
            public_base_url: "https://responder.example.invalid",
          })
        : usual(path, options),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(
      container.querySelector<HTMLAnchorElement>(
        '[data-testid="responder-preview"]',
      )?.href,
    ).toBe("https://responder.example.invalid/respond/oldrun01/candidate1");
    vi.mocked(request).mockImplementation((path, options) =>
      path === "/api/config"
        ? Promise.reject(new Error("Connection lost"))
        : usual(path, options),
    );
    await act(async () => {
      await vi.advanceTimersByTimeAsync(10_000);
    });
    expect(container.textContent).toContain("phone access not configured");
    expect(
      container
        .querySelector<HTMLAnchorElement>('[data-testid="responder-preview"]')
        ?.getAttribute("href"),
    ).toBe("/respond/oldrun01/candidate1");
  });

  it("clears a connection-interrupted notice once polling recovers", async () => {
    await mount();
    nextState = () => Promise.reject(new Error("Temporary outage"));
    await tick();
    expect(container.textContent).toContain("Connection interrupted.");
    nextState = undefined;
    await tick();
    expect(container.textContent).not.toContain("Connection interrupted.");
  });
});

describe("requested replay playback and source provenance", () => {
  const secondSource: Source = {
    ...source,
    id: "street-traffic",
    video_url: "/other.webm",
    media_available: true,
  };
  const secondIncident: Incident = {
    ...candidate,
    id: "other-candidate",
    source_id: secondSource.id,
    title: "Other replay incident",
  };
  const readyMedia = () => {
    availableSources = [{ ...source, media_available: true }, secondSource];
    const played: HTMLMediaElement[] = [];
    vi.spyOn(HTMLMediaElement.prototype, "play").mockImplementation(
      function () {
        played.push(this);
        return Promise.resolve();
      },
    );
    const paused = vi
      .spyOn(HTMLMediaElement.prototype, "pause")
      .mockImplementation(() => {});
    HTMLElement.prototype.scrollIntoView = vi.fn();
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn(() => ({ matches: true })),
    });
    return { played, paused };
  };
  const card = (title: string) =>
    Array.from(
      container.querySelectorAll<HTMLButtonElement>(
        '[data-testid="incident-card"]',
      ),
    ).find((button) => button.textContent?.includes(title))!;

  it("mounts and plays the requested source before analysis when another replay incident is displayed", async () => {
    const { played } = readyMedia();
    currentState = stateFor("oldrun01", [candidate, secondIncident]);
    await mount();
    await act(async () => card(secondIncident.title).click());
    const oldVideo = container.querySelector<HTMLVideoElement>("video")!;
    expect(oldVideo.getAttribute("src")).toBe("/other.webm");
    const result = deferred<State>();
    vi.mocked(post).mockReturnValue(result.promise);
    await click("start-replay");
    const requestedVideo = container.querySelector<HTMLVideoElement>("video")!;
    expect(requestedVideo.getAttribute("src")).toBe("/fixture.webm");
    expect(played).toEqual([requestedVideo]);
    expect(played).not.toContain(oldVideo);
    expect(post).toHaveBeenCalledWith("/api/runs/oldrun01/replay", {
      source_id: "road-obstruction",
      analysis_mode: "fixture",
    });
    await act(async () => result.resolve(currentState));
    expect(container.querySelector("video")).toBe(requestedVideo);
    expect(played).toEqual([requestedVideo]);
  });

  it("starts the requested replay after replacing live frozen evidence without losing the live candidate", async () => {
    const { played } = readyMedia();
    const live: Incident = {
      ...candidate,
      id: "live-candidate",
      source_id: "camera-live",
      source_mode: "live",
      analysis_mode: "fresh",
      live_source: {
        ...source,
        id: "camera-live",
        source_mode: "live",
        title: "Live camera",
        video_url: "",
        media_available: false,
      },
    };
    currentState = stateFor("oldrun01", [live]);
    await mount();
    expect(container.querySelector("video")).toBeNull();
    const result = deferred<State>();
    vi.mocked(post).mockReturnValue(result.promise);
    await click("start-replay");
    const video = container.querySelector<HTMLVideoElement>("video")!;
    expect(video.getAttribute("src")).toBe("/fixture.webm");
    expect(played).toEqual([video]);
    await act(async () =>
      result.resolve(stateFor("oldrun01", [live, candidate])),
    );
    expect(container.querySelector("video")).toBe(video);
    expect(played).toEqual([video]);
    expect(
      container.querySelectorAll('[data-testid="incident-card"]'),
    ).toHaveLength(2);
  });

  it("cancels a queued autoplay when selection changes before the commit and ignores a late replay response", async () => {
    const { played } = readyMedia();
    currentState = stateFor("oldrun01", [candidate, secondIncident]);
    await mount();
    await act(async () => card(secondIncident.title).click());
    const result = deferred<State>();
    vi.mocked(post).mockReturnValue(result.promise);
    await act(async () => {
      container
        .querySelector<HTMLButtonElement>('[data-testid="start-replay"]')!
        .click();
      card(secondIncident.title).click();
    });
    expect(played).toHaveLength(0);
    await act(async () => result.resolve(currentState));
    expect(container.querySelector("video")?.getAttribute("src")).toBe(
      "/other.webm",
    );
    expect(played).toHaveLength(0);
  });

  it("stops requested playback on reset and does not restart it when the old replay response arrives", async () => {
    const { played, paused } = readyMedia();
    await mount();
    const result = deferred<State>();
    vi.mocked(post).mockImplementation(async (path) =>
      path.endsWith("/replay") ? result.promise : stateFor("newrun02"),
    );
    await click("start-replay");
    const oldVideo = played[0];
    expect(played).toHaveLength(1);
    await click("reset-demo");
    expect(paused.mock.instances).toContain(oldVideo);
    const resetVideo = container.querySelector("video");
    expect(resetVideo).not.toBe(oldVideo);
    await act(async () => result.resolve(stateFor("oldrun01", [candidate])));
    expect(container.querySelector("video")).toBe(resetVideo);
    expect(played).toEqual([oldVideo]);
    expect(container.textContent).toContain("RUN NEWRUN02");
  });

  it("preserves a later evidence selection while replay analysis is pending", async () => {
    const { played, paused } = readyMedia();
    currentState = stateFor("oldrun01", [candidate, secondIncident]);
    await mount();
    const result = deferred<State>();
    vi.mocked(post).mockReturnValue(result.promise);
    await click("start-replay");
    const requestedVideo = played[0];
    await act(async () => card(secondIncident.title).click());
    expect(paused.mock.instances).toContain(requestedVideo);
    expect(container.querySelector("video")?.getAttribute("src")).toBe(
      "/other.webm",
    );
    await act(async () => result.resolve(currentState));
    expect(container.querySelector("video")?.getAttribute("src")).toBe(
      "/other.webm",
    );
    expect(played).toEqual([requestedVideo]);
  });

  it("does not attribute a prior fresh no-candidate analysis to an untouched source", async () => {
    readyMedia();
    currentState.analysis = {
      mode: "fresh",
      status: "complete",
      message: "A prior source returned no candidate",
    };
    await mount();
    const evidence = () =>
      container.querySelector('[data-testid="evidence-panel"]')!;
    expect(evidence().textContent).toContain("Not analyzed in this view");
    const freshResult = stateFor();
    freshResult.analysis = {
      mode: "fresh",
      status: "complete",
      message: "Fresh result for road obstruction",
    };
    freshResult.source_analyses = { [source.id]: freshResult.analysis };
    currentState = freshResult;
    vi.mocked(post).mockResolvedValue(freshResult);
    await click("start-replay");
    expect(evidence().textContent).toContain("Fresh inference");
    await act(async () =>
      container
        .querySelector<HTMLButtonElement>(
          '[aria-label="Select Ordinary street traffic"]',
        )!
        .click(),
    );
    expect(evidence().textContent).toContain("Not analyzed in this view");
    expect(evidence().textContent).not.toContain("Fresh inference");
    expect(container.textContent).not.toContain(
      "Fresh result for road obstruction",
    );
    await tick();
    expect(evidence().textContent).not.toContain("Fresh inference");
    await act(async () =>
      container
        .querySelector<HTMLButtonElement>(
          '[aria-label="Select Road obstruction"]',
        )!
        .click(),
    );
    expect(evidence().textContent).toContain("Fresh inference");
  });
});

describe("server-owned per-source analysis", () => {
  const otherSource: Source = {
    ...source,
    id: "street-traffic",
    video_url: "/other.webm",
  };
  const unavailable: State["analysis"] = {
    mode: "unavailable",
    status: "unavailable",
    message: "Road obstruction has no genuine cache entry",
  };
  const cached: State["analysis"] = {
    mode: "cached",
    status: "complete",
    message: "Street traffic cache completed with no candidate",
  };
  const evidence = () =>
    container.querySelector('[data-testid="evidence-panel"]')!;
  const select = async (label: string) => {
    await act(async () =>
      container
        .querySelector<HTMLButtonElement>(`[aria-label="Select ${label}"]`)!
        .click(),
    );
  };

  it("keeps an idempotent A cache miss distinct from B's completed cache result", async () => {
    availableSources = [source, otherSource];
    currentState = {
      ...stateFor(),
      analysis: cached,
      source_analyses: {
        [source.id]: unavailable,
        [otherSource.id]: cached,
      },
    };
    await mount();
    expect(evidence().textContent).toContain("Analysis unavailable");
    expect(evidence().textContent).not.toContain("Cached model result");
    await select("Ordinary street traffic");
    expect(evidence().textContent).toContain("Cached model result");
    await select("Road obstruction");
    vi.mocked(post).mockResolvedValue(currentState);
    await click("start-replay");
    expect(evidence().textContent).toContain("Analysis unavailable");
    expect(evidence().textContent).not.toContain("Cached model result");
    expect(container.textContent).toContain(unavailable.message);
    expect(container.textContent).not.toContain(cached.message);
    await tick();
    expect(evidence().textContent).toContain("Analysis unavailable");
  });

  it("updates a running source from polling without presenting another source's result as completion", async () => {
    currentState = {
      ...stateFor(),
      analysis: cached,
      source_analyses: {
        [source.id]: {
          mode: "fresh",
          status: "running",
          message: "Road obstruction analysis is running",
        },
        [otherSource.id]: cached,
      },
    };
    await mount();
    expect(evidence().textContent).toContain("Analysis in progress");
    expect(evidence().textContent).not.toContain("Fresh inference");
    expect(evidence().textContent).not.toContain("Cached model result");
    const fresh: State["analysis"] = {
      mode: "fresh",
      status: "complete",
      message: "Road obstruction completed without a candidate",
    };
    currentState = {
      ...currentState,
      source_analyses: { ...currentState.source_analyses, [source.id]: fresh },
    };
    await tick();
    expect(evidence().textContent).toContain("Fresh inference");
    expect(evidence().textContent).not.toContain("Analysis in progress");
    expect(container.textContent).toContain(fresh.message);
    expect(post).not.toHaveBeenCalled();
  });

  it("restores the selected source's result after reload and drops it with a new run", async () => {
    currentState = {
      ...stateFor(),
      analysis: unavailable,
      source_analyses: { [source.id]: cached },
    };
    await mount();
    expect(evidence().textContent).toContain("Cached model result");
    expect(evidence().textContent).not.toContain("Not analyzed in this view");
    expect(post).not.toHaveBeenCalled();
    currentState = { ...stateFor("newrun02"), source_analyses: {} };
    vi.mocked(post).mockResolvedValue(currentState);
    await click("reset-demo");
    expect(evidence().textContent).toContain("Not analyzed in this view");
    expect(evidence().textContent).not.toContain("Cached model result");
  });
});

describe("stacked Dispatch layout", () => {
  it.each([
    [false, "smooth"],
    [true, "instant"],
  ] as const)(
    "reveals committed desktop map evidence with reduced motion %s",
    async (reducedMotion, behavior) => {
      const previousWidth = window.innerWidth;
      const previousMatchMedia = window.matchMedia;
      Object.defineProperty(window, "innerWidth", {
        configurable: true,
        value: 1440,
      });
      Object.defineProperty(window, "matchMedia", {
        configurable: true,
        value: vi.fn(() => ({ matches: reducedMotion })),
      });
      const other: Incident = {
        ...candidate,
        id: "second-map-incident",
        title: "Second camera evidence",
      };
      currentState = stateFor("oldrun01", [candidate, other]);
      try {
        await mount();
        const panel = container.querySelector<HTMLElement>(
          '[data-testid="evidence-panel"]',
        )!;
        const scroll = vi.fn(function (this: HTMLElement) {
          expect(this.querySelector("h3")?.textContent).toBe(other.title);
          expect(document.activeElement).toBe(this);
        });
        panel.scrollIntoView = scroll;
        const mapButton = container.querySelector<HTMLButtonElement>(
          '[data-map-incident="second-map-incident"]',
        )!;
        expect(
          panel.compareDocumentPosition(mapButton) &
            Node.DOCUMENT_POSITION_FOLLOWING,
        ).toBeTruthy();
        mapButton.focus();
        await act(async () => mapButton.click());
        expect(scroll).toHaveBeenCalledOnce();
        expect(scroll).toHaveBeenCalledWith({ behavior, block: "start" });
        await tick();
        expect(scroll).toHaveBeenCalledOnce();
      } finally {
        Object.defineProperty(window, "innerWidth", {
          configurable: true,
          value: previousWidth,
        });
        Object.defineProperty(window, "matchMedia", {
          configurable: true,
          value: previousMatchMedia,
        });
      }
    },
  );

  it("does not imply active monitoring or clear roads when there are no candidates", async () => {
    await mount();
    expect(container.querySelector("h1")?.textContent).toBe(
      "No candidates yet.",
    );
    expect(container.querySelector("h1")?.textContent).not.toMatch(
      /quiet|watching|safe|clear/i,
    );
  });
});
