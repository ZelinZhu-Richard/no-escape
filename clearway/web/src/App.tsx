import {
  lazy,
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import type { FormEvent, RefObject } from "react";
import { QRCodeSVG } from "qrcode.react";
import { request, post, ApiError, errorMessage } from "./api";
import type {
  AnalysisMode,
  Config,
  Incident,
  Label,
  ResponderData,
  Source,
  State,
} from "./types";
import { Icon } from "./Icon";
import { DetectionOverlay } from "./DetectionOverlay";
import { VoiceBrief } from "./VoiceBrief";
import { LiveIncidentEvidence } from "./LiveIncidentEvidence";
import { LiveCameraPanel } from "./LiveCameraPanel";
import { readLiveCameraCatalog } from "./liveCameras";
import type { LiveCamera, LiveCameraCatalog } from "./liveCameras";
const MapView = lazy(() =>
  import("./MapView").then((module) => ({ default: module.MapView })),
);

const shortId = (id: string) => id.slice(0, 8).toUpperCase();
const timeLabel = (seconds: number) =>
  `${Math.floor(seconds / 60)
    .toString()
    .padStart(2, "0")}:${Math.floor(seconds % 60)
    .toString()
    .padStart(2, "0")}`;
const sourceName = (id: string) =>
  id === "road-obstruction"
    ? "Road obstruction"
    : id === "street-traffic"
      ? "Ordinary street traffic"
      : id === "traffic-jam"
        ? "Dense traffic"
        : id === "person-roadway"
          ? "Person in roadway"
          : id.replaceAll("-", " ");
const sourceHint = (id: string) =>
  id === "road-obstruction"
    ? "Utility work zone · positive replay"
    : id === "street-traffic"
      ? "Control candidate · awaiting labels"
      : id === "traffic-jam"
        ? "Congestion candidate · unverified"
        : "Licensed scene · human review required";

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="brand">
      <span className="brand-symbol">
        <svg
          viewBox="0 0 32 32"
          width="26"
          height="26"
          fill="none"
          aria-hidden="true"
        >
          <circle
            cx="16"
            cy="16"
            r="11"
            stroke="currentColor"
            strokeWidth="1.6"
          />
          <circle
            cx="16"
            cy="16"
            r="5.2"
            stroke="currentColor"
            strokeWidth="1.6"
            opacity=".55"
          />
          <path
            d="M16 1.5v7M16 23.5v7M1.5 16h7M23.5 16h7"
            stroke="currentColor"
            strokeWidth="1.6"
          />
          <circle
            className="brand-core"
            cx="16"
            cy="16"
            r="2.2"
            fill="currentColor"
          />
        </svg>
      </span>
      <span className="brand-word">
        clearway<span className="brand-period">/</span>
      </span>
      {!compact && <span className="brand-separator" />}
    </div>
  );
}
function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <span className="topbar-clock mono" aria-label="Local time">
      {now.toLocaleTimeString([], {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      })}
      <small>
        {now
          .toLocaleDateString([], { month: "short", day: "2-digit" })
          .toUpperCase()}
      </small>
    </span>
  );
}
function Badge({
  children,
  kind = "",
}: {
  children: React.ReactNode;
  kind?: string;
}) {
  return <span className={`badge ${kind}`}>{children}</span>;
}
function ModeBadge({ mode }: { mode: AnalysisMode }) {
  return (
    <Badge
      kind={
        mode === "fixture"
          ? "fixture"
          : mode === "unavailable"
            ? "muted"
            : "green"
      }
    >
      {mode === "fixture"
        ? "Fixture analysis"
        : mode === "cached"
          ? "Cached model result"
          : mode === "fresh"
            ? "Fresh inference"
            : "Analysis unavailable"}
    </Badge>
  );
}
function Provenance({ incident }: { incident: Incident }) {
  return (
    <div className="provenance-row">
      <Badge>
        {incident.source_mode === "live"
          ? "Public camera · live source"
          : "Recorded replay"}
      </Badge>
      {incident.source_mode === "live" ? (
        <Badge kind="green">Local YOLO · temporal rule</Badge>
      ) : (
        <ModeBadge mode={incident.analysis_mode} />
      )}
      <Badge kind={incident.review_status === "confirmed" ? "green" : "amber"}>
        {incident.review_status === "candidate"
          ? "Needs review"
          : incident.review_status}
      </Badge>
    </div>
  );
}
function Credit({ source }: { source: Source }) {
  return (
    <p className="media-credit">
      <a href={source.attribution.source_url} target="_blank" rel="noreferrer">
        {source.attribution.creator} / {source.attribution.title}
      </a>
      <span> · </span>
      <a href={source.attribution.license_url} target="_blank" rel="noreferrer">
        {source.attribution.license}
      </a>
    </p>
  );
}
function Video({
  source,
  videoRef,
  replayKey,
  showDetections = false,
  playRequest,
}: {
  source: Source;
  videoRef?: RefObject<HTMLVideoElement | null>;
  replayKey?: string;
  showDetections?: boolean;
  playRequest?: number;
}) {
  const [failed, setFailed] = useState(false);
  const [aspectRatio, setAspectRatio] = useState(16 / 9);
  const localRef = useRef<HTMLVideoElement>(null);
  const effectiveRef = videoRef ?? localRef;
  useEffect(() => {
    setFailed(false);
    setAspectRatio(16 / 9);
  }, [source.video_url]);
  useEffect(() => {
    const video = effectiveRef.current;
    if (playRequest === undefined || !video || failed) return;
    // This runs after the requested source's actual element has mounted.
    // A ref read in the Start replay click still points at the previous evidence.
    try {
      video.currentTime = 0;
      void video.play().catch(() => {});
    } catch {
      // The native controls remain usable if autoplay is unavailable.
    }
    return () => video.pause();
  }, [effectiveRef, failed, playRequest, replayKey, source.video_url]);
  if (!source.media_available || failed)
    return (
      <div className="media-missing">
        <Icon name="camera" size={28} />
        <strong>Replay footage unavailable</strong>
        <span>
          The licensed clip has not been restored on this machine. Fixture
          observations are still labeled separately.
        </span>
      </div>
    );
  return (
    <>
      <video
        ref={effectiveRef}
        key={replayKey ?? source.video_url}
        controls
        muted
        playsInline
        preload="metadata"
        poster={
          source.poster_available === false ? undefined : source.poster_url
        }
        src={source.video_url}
        style={showDetections ? { aspectRatio } : undefined}
        onLoadedMetadata={(event) => {
          const video = event.currentTarget;
          if (video.videoWidth > 0 && video.videoHeight > 0)
            setAspectRatio(video.videoWidth / video.videoHeight);
        }}
        onError={() => setFailed(true)}
        aria-label={`${sourceName(source.id)} recorded footage`}
      />
      {showDetections && (
        <DetectionOverlay
          sourceId={source.id}
          videoRef={effectiveRef}
          replayKey={replayKey}
        />
      )}
    </>
  );
}

function Operator() {
  const [config, setConfig] = useState<Config | null>(null);
  const [sources, setSources] = useState<Source[]>([]);
  const [state, setState] = useState<State | null>(null);
  const [sourceId, setSourceId] = useState("road-obstruction");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mode, setMode] = useState<AnalysisMode>("fixture");
  const [error, setError] = useState("");
  const [pending, setPending] = useState("");
  const [tab, setTab] = useState<"desk" | "labels">("desk");
  const [playbackKey, setPlaybackKey] = useState(0);
  const [replayPlayback, setReplayPlayback] = useState<{
    id: number;
    sourceId: string;
    runId: string;
  } | null>(null);
  const replayPlaybackId = useRef(0);
  const cancelReplayPlayback = useCallback(() => {
    ++replayPlaybackId.current;
    setReplayPlayback(null);
  }, []);
  const [liveCatalog, setLiveCatalog] = useState<LiveCameraCatalog | null>(
    null,
  );
  const [liveLoading, setLiveLoading] = useState(true);
  const [liveError, setLiveError] = useState("");
  const [liveSelectedId, setLiveSelectedId] = useState<string | null>(null);
  // The public camera browser stays mounted but folded until it is needed.
  const [cctvOpen, setCctvOpen] = useState(false);
  const [visibleLiveCameras, setVisibleLiveCameras] = useState<LiveCamera[]>(
    [],
  );
  const epoch = useRef(0);
  const autoSelectCandidate = useRef(true);
  const configEpoch = useRef(0);
  // Synchronous guard: a render-time pending flag cannot protect polling races.
  const writeInFlight = useRef<
    "reset" | "replay" | "confirm" | "dismiss" | null
  >(null);
  const mounted = useRef(true);
  const videoRef = useRef<HTMLVideoElement>(null);
  const evidenceRef = useRef<HTMLElement>(null);
  const [evidenceReveal, setEvidenceReveal] = useState(0);
  useEffect(() => {
    if (!evidenceReveal) return;
    // Reveal after the selected evidence has committed. In the stacked layout
    // the map and queue sit below this panel, including on desktop.
    evidenceRef.current?.focus({ preventScroll: true });
    evidenceRef.current?.scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
      block: "start",
    });
  }, [evidenceReveal]);
  const livePreviewRef = useRef<HTMLDivElement>(null);
  const selectMapCamera = useCallback((id: string) => {
    setLiveSelectedId(id);
    requestAnimationFrame(() => {
      livePreviewRef.current?.focus({ preventScroll: true });
      livePreviewRef.current?.scrollIntoView({
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
          ? "instant"
          : "smooth",
        block: "start",
      });
    });
  }, []);
  const source = sources.find((s) => s.id === sourceId);
  const incident = state?.incidents.find((i) => i.id === selectedId);
  const runIncidents = state?.incidents ?? [];
  const evidenceSource =
    incident?.live_source ??
    sources.find((s) => s.id === incident?.source_id) ??
    source;
  const liveIncident = incident?.source_mode === "live";

  useEffect(() => {
    // New candidates can open an empty desk, but polling never replaces a review.
    setSelectedId((current) => {
      if (current && state?.incidents.some((item) => item.id === current))
        return current;
      if (!autoSelectCandidate.current) return null;
      return (
        state?.incidents.find((item) => item.review_status === "candidate")
          ?.id ?? null
      );
    });
  }, [state?.run.id, state?.incidents]);

  useEffect(() => {
    // Public-camera availability must never block the local replay workflow.
    const controller = new AbortController();
    request<unknown>("/api/live-cameras", { signal: controller.signal })
      .then((raw) => {
        if (controller.signal.aborted) return;
        const catalog = readLiveCameraCatalog(raw);
        if (!catalog) throw new Error("Invalid public camera catalog");
        setLiveCatalog(catalog);
        setVisibleLiveCameras(catalog.cameras);
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setLiveError(
            "The public camera catalog is unavailable. Recorded replays remain ready.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLiveLoading(false);
      });
    return () => controller.abort();
  }, []);

  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    const generation = epoch.current;
    const configGeneration = ++configEpoch.current;
    Promise.all([
      request<Config>("/api/config", { signal: controller.signal }),
      request<{ sources: Source[] }>("/api/sources", {
        signal: controller.signal,
      }),
      request<State>("/api/state", { signal: controller.signal }),
    ])
      .then(([c, s, st]) => {
        if (!mounted.current) return;
        if (configGeneration === configEpoch.current) setConfig(c);
        setSources(s.sources);
        if (generation === epoch.current && writeInFlight.current === null) {
          setState(st);
          setMode(c.default_analysis_mode);
        }
      })
      .catch((e) => {
        if (
          !controller.signal.aborted &&
          generation === epoch.current &&
          writeInFlight.current === null
        )
          setError(
            `Unable to connect to the local service. ${errorMessage(e)}`,
          );
      });
    return () => {
      mounted.current = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    const refreshConfig = async () => {
      const generation = ++configEpoch.current;
      try {
        const result = await request<Config>("/api/config", {
          signal: controller.signal,
        });
        if (!controller.signal.aborted && generation === configEpoch.current)
          setConfig(result);
      } catch {
        // A stale public origin must not remain scannable after tunnel loss.
        if (!controller.signal.aborted && generation === configEpoch.current)
          setConfig((current) =>
            current ? { ...current, public_base_url: null } : current,
          );
      }
      if (!controller.signal.aborted) timer = setTimeout(refreshConfig, 10_000);
    };
    timer = setTimeout(refreshConfig, 10_000);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, []);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    let alive = true;
    const poll = async () => {
      if (
        document.visibilityState === "hidden" ||
        writeInFlight.current !== null
      ) {
        timer = setTimeout(poll, 2000);
        return;
      }
      const generation = epoch.current;
      try {
        const result = await request<State>("/api/state", {
          signal: controller.signal,
        });
        if (
          alive &&
          generation === epoch.current &&
          writeInFlight.current === null
        ) {
          setState(result);
          setError((current) =>
            current.startsWith("Connection interrupted.") ? "" : current,
          );
        }
      } catch (e) {
        if (
          alive &&
          !controller.signal.aborted &&
          generation === epoch.current &&
          writeInFlight.current === null
        )
          setError(`Connection interrupted. ${errorMessage(e)}`);
      }
      if (alive) timer = setTimeout(poll, 2000);
    };
    timer = setTimeout(poll, 2000);
    return () => {
      alive = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, []);

  const reset = useCallback(
    async (nextSource?: string, nextMode?: AnalysisMode) => {
      if (writeInFlight.current === "reset") return;
      const generation = ++epoch.current;
      writeInFlight.current = "reset";
      setPending("reset");
      setError("");
      cancelReplayPlayback();
      videoRef.current?.pause();
      try {
        const result = await post<State>("/api/reset");
        if (mounted.current && generation === epoch.current) {
          setState(result);
          autoSelectCandidate.current = true;
          setSelectedId(null);
          setPlaybackKey((k) => k + 1);
          if (nextSource) setSourceId(nextSource);
          if (nextMode) setMode(nextMode);
        }
      } catch (e) {
        if (generation === epoch.current) setError(errorMessage(e));
      } finally {
        if (mounted.current && generation === epoch.current) {
          // Invalidate any snapshot started before this mutation committed.
          ++epoch.current;
          writeInFlight.current = null;
          setPending("");
        }
      }
    },
    [cancelReplayPlayback],
  );

  const replay = async () => {
    if (!state || !source || writeInFlight.current !== null) return;
    const generation = ++epoch.current;
    writeInFlight.current = "replay";
    const runId = state.run.id;
    const playbackId = ++replayPlaybackId.current;
    setPending("replay");
    setError("");
    // Keep the requested replay visible even when a live or other-source
    // incident was selected. Do not wait for inference before playing it.
    autoSelectCandidate.current = false;
    setSelectedId(
      state.incidents.find((i) => i.source_id === sourceId)?.id ?? null,
    );
    setPlaybackKey((key) => key + 1);
    setReplayPlayback({ id: playbackId, sourceId, runId });
    try {
      const result = await post<State>(`/api/runs/${runId}/replay`, {
        source_id: sourceId,
        analysis_mode: mode,
      });
      if (mounted.current && generation === epoch.current) {
        setState(result);
        if (replayPlaybackId.current === playbackId)
          setSelectedId(
            result.incidents.find((i) => i.source_id === sourceId)?.id ?? null,
          );
      }
    } catch (e) {
      if (generation === epoch.current) setError(errorMessage(e));
    } finally {
      if (mounted.current && generation === epoch.current) {
        // Invalidate any snapshot started before this mutation committed.
        ++epoch.current;
        writeInFlight.current = null;
        setPending("");
      }
    }
  };
  const review = async (action: "confirm" | "dismiss") => {
    if (!incident || writeInFlight.current !== null) return;
    const generation = ++epoch.current;
    writeInFlight.current = action;
    setPending(action);
    setError("");
    try {
      const result = await post<Incident>(
        `/api/runs/${incident.run_id}/incidents/${incident.id}/${action}`,
      );
      if (mounted.current && generation === epoch.current)
        setState((current) =>
          current?.run.id === result.run_id
            ? {
                ...current,
                incidents: current.incidents.map((i) =>
                  i.id === result.id ? result : i,
                ),
              }
            : current,
        );
    } catch (e) {
      if (generation === epoch.current) setError(errorMessage(e));
    } finally {
      if (mounted.current && generation === epoch.current) {
        // Invalidate any snapshot started before this mutation committed.
        ++epoch.current;
        writeInFlight.current = null;
        setPending("");
      }
    }
  };
  const openEvidence = (id?: string) => {
    cancelReplayPlayback();
    if (id ?? incident?.id) setSelectedId(id ?? incident!.id);
    setEvidenceReveal((version) => version + 1);
  };
  const seek = (time: number) => {
    if (liveIncident) return;
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      videoRef.current.focus();
    }
  };
  const confirmedCount =
    state?.incidents.filter((i) => i.review_status === "confirmed").length ?? 0;
  const selectedAnalysis = state?.source_analyses?.[sourceId];
  const displayedMode: AnalysisMode =
    selectedAnalysis?.status === "unavailable"
      ? "unavailable"
      : selectedAnalysis?.status === "complete"
        ? selectedAnalysis.mode
        : mode;

  const pendingCount = runIncidents.filter(
    (item) => item.review_status === "candidate",
  ).length;
  const alertState = pendingCount
    ? "alert"
    : confirmedCount
      ? "confirmed"
      : "idle";
  const feedCount = liveCatalog?.cameras?.length ?? 0;
  const cctvVisible = cctvOpen || Boolean(liveSelectedId);

  return (
    <div className={`operator-app state-${alertState} tab-${tab}`}>
      <div className="alert-frame" aria-hidden="true" />
      <header className="topbar">
        <div className="masthead">
          <a
            className="brand-link"
            href="/"
            aria-label="Clearway incident desk"
          >
            <Brand />
          </a>
          <p className="edition mono">
            <span>Durham, North Carolina</span>
            <span>Road operations desk</span>
          </p>
          <div className="topbar-status">
            <span className="status-dot" />
            Local demo
            <span className="topbar-shortid mono">
              {state ? `RUN ${shortId(state.run.id)}` : "CONNECTING"}
            </span>
            <Clock />
          </div>
        </div>
        <div className="nav-row">
          <nav aria-label="Main navigation">
            <button
              className={tab === "desk" ? "nav-button active" : "nav-button"}
              onClick={() => setTab("desk")}
            >
              Incident desk
            </button>
            <button
              className={tab === "labels" ? "nav-button active" : "nav-button"}
              onClick={() => {
                cancelReplayPlayback();
                setTab("labels");
              }}
            >
              Label windows
            </button>
          </nav>
          <div className="topbar-telemetry mono">
            <span className={`telemetry-cell ${pendingCount ? "is-hot" : ""}`}>
              <small>Pending</small>
              <b>{pendingCount.toString().padStart(2, "0")}</b>
            </span>
            <span className="telemetry-cell">
              <small>Cleared</small>
              <b>{confirmedCount.toString().padStart(2, "0")}</b>
            </span>
          </div>
          <div className="run-controls">
            <label className="analysis-select">
              <span className="sr-only">Analysis mode</span>
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as AnalysisMode)}
                disabled={Boolean(pending)}
                aria-label="Analysis mode"
              >
                <option value="fixture">Fixture walkthrough</option>
                <option value="cached">Frozen model cache</option>
                <option
                  value="fresh"
                  disabled={!config?.model_configured}
                  title={config?.model_readiness?.message}
                >
                  Fresh inference
                  {!config?.model_configured ? " · unavailable" : ""}
                </option>
              </select>
            </label>
            <button
              className="secondary-button reset-button"
              onClick={() => void reset()}
              disabled={pending === "reset" || !state}
              data-testid="reset-demo"
            >
              <Icon name="reset" />
              <span>{pending === "reset" ? "Resetting…" : "Reset demo"}</span>
            </button>
            <button
              className="primary-button"
              onClick={() => void replay()}
              disabled={Boolean(pending) || !state || !source}
              data-testid="start-replay"
            >
              <Icon name="play" size={17} />
              <span>
                {pending === "replay" ? "Preparing…" : "Start replay"}
              </span>
            </button>
          </div>
        </div>
      </header>
      {error && (
        <div className="error-banner" role="alert">
          <Icon name="alert" />
          <span>{error}</span>
          <button onClick={() => setError("")} aria-label="Dismiss error">
            <Icon name="cross" />
          </button>
        </div>
      )}
      {tab === "labels" ? (
        <Labeling sources={sources} onBack={() => setTab("desk")} />
      ) : (
        <>
          <section className="desk-toolbar">
            <div className="desk-headline">
              <span className="headline-signal" aria-hidden="true">
                <i />
              </span>
              <div>
                <div className="eyebrow">
                  ROAD OPERATIONS / REVIEW WORKSPACE
                </div>
                <h1>
                  {alertState === "alert"
                    ? `${pendingCount} ${pendingCount === 1 ? "signal" : "signals"} awaiting your call`
                    : alertState === "confirmed"
                      ? "Incident confirmed. Handoff ready."
                      : "No candidates yet."}
                </h1>
                <p>
                  See the evidence. Make the call. Keep the handoff connected.
                </p>
              </div>
            </div>
            {alertState === "alert" && (
              <div className="ticker" aria-hidden="true">
                <div className="ticker-track">
                  {[0, 1].map((copy) => (
                    <span key={copy}>
                      Incident candidate ◆ Awaiting operator review ◆ Evidence
                      attached ◆ No automatic dispatch ◆{" "}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>
          <div className="workspace-grid">
            <aside
              className="evidence-panel"
              ref={evidenceRef}
              tabIndex={-1}
              aria-label="Evidence panel"
              data-testid="evidence-panel"
            >
              <div className="evidence-heading">
                <div>
                  <span className="eyebrow">EVIDENCE REVIEW</span>
                  <h2>
                    {incident ? "The scene behind the signal." : "Look closer."}
                  </h2>
                </div>
                <Icon name="expand" size={17} />
              </div>
              {evidenceSource ? (
                <>
                  {liveIncident && incident ? (
                    <LiveIncidentEvidence
                      key={incident.id}
                      incident={incident}
                    />
                  ) : (
                    <div className="video-wrap">
                      <Video
                        source={evidenceSource}
                        videoRef={videoRef}
                        replayKey={`${evidenceSource.id}-${state?.run.id}-${playbackKey}`}
                        playRequest={
                          replayPlayback?.sourceId === evidenceSource.id &&
                          replayPlayback.runId === state?.run.id
                            ? replayPlayback.id
                            : undefined
                        }
                        showDetections
                      />
                      <div className="video-toplabel">
                        <span className="video-dot" />
                        LICENSED RECORDED REPLAY
                      </div>
                    </div>
                  )}
                  <Credit source={evidenceSource} />
                  {incident ? (
                    <div className="evidence-body">
                      <Provenance incident={incident} />
                      <h3>{incident.title}</h3>
                      <p className="evidence-summary">
                        {liveIncident
                          ? "Review this frozen trigger frame and the rule observations before confirming. A visual signal alone does not establish an emergency."
                          : incident.analysis_mode === "fixture"
                            ? "These are reference observations for the workflow demonstration. No model inferred this result."
                            : "Review the saved observations against the source video before confirming."}
                      </p>
                      <VoiceBrief
                        incident={incident}
                        disabled={Boolean(pending)}
                      />
                      <div className="section-label">OBSERVED IN THE SCENE</div>
                      <ol className="observations">
                        {incident.evidence.map((e, index) => (
                          <li key={`${e.timestamp_seconds}-${index}`}>
                            {liveIncident ? (
                              <span
                                className="timestamp mono"
                                title="Live stream media clock"
                              >
                                {timeLabel(e.timestamp_seconds)}
                              </span>
                            ) : (
                              <button
                                onClick={() => seek(e.timestamp_seconds)}
                                title={`Seek to ${e.timestamp_seconds} seconds`}
                                className="timestamp mono"
                              >
                                {timeLabel(e.timestamp_seconds)}
                              </button>
                            )}
                            <span>{e.observation}</span>
                          </li>
                        ))}
                      </ol>
                      <details className="unknowns">
                        <summary>
                          <Icon name="alert" size={15} />
                          <strong>Still unknown</strong>
                          <span className="unknowns-count mono">
                            {incident.unknowns.length || 1}
                          </span>
                        </summary>
                        <p>
                          {incident.unknowns.length
                            ? incident.unknowns.join(" · ")
                            : "Original location and capture time are unverified."}
                        </p>
                      </details>
                      <div className="context-note">
                        <Icon name="pin" size={15} />
                        <p>
                          <strong>
                            {incident.location.quality === "simulated"
                              ? "Simulated map placement"
                              : "Source camera context"}
                          </strong>
                          <span>
                            {incident.location.quality === "simulated"
                              ? "The marker demonstrates the workflow. It is not a measured incident location."
                              : "Camera metadata does not establish the location of an object in the scene."}
                          </span>
                        </p>
                      </div>
                      <div className="review-actions">
                        {incident.review_status === "candidate" ? (
                          <>
                            <button
                              className="confirm-button"
                              onClick={() => void review("confirm")}
                              disabled={Boolean(pending)}
                              data-testid="confirm-incident"
                            >
                              <Icon name="check" size={19} />
                              {pending === "confirm"
                                ? "Confirming…"
                                : "Confirm incident"}
                            </button>
                            <button
                              className="dismiss-button"
                              onClick={() => void review("dismiss")}
                              disabled={Boolean(pending)}
                            >
                              Dismiss
                            </button>
                          </>
                        ) : (
                          <div
                            className={`review-result ${incident.review_status === "confirmed" ? "confirmed" : ""}`}
                            role="status"
                          >
                            <Icon
                              name={
                                incident.review_status === "confirmed"
                                  ? "shield"
                                  : "cross"
                              }
                              size={21}
                            />
                            <div>
                              <strong>
                                {incident.review_status === "confirmed"
                                  ? "Confirmed by operator"
                                  : "Candidate dismissed"}
                              </strong>
                              <span>
                                {incident.review_status === "confirmed"
                                  ? "The responder brief reflects this review."
                                  : "Reset the demo to begin a new review."}
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                      <Handoff incident={incident} config={config} />
                    </div>
                  ) : (
                    <div className="evidence-body empty-evidence">
                      <span className="eyebrow">
                        {sourceName(evidenceSource.id)}
                      </span>
                      <h3>
                        A short replay.
                        <br />A complete review.
                      </h3>
                      <p>
                        Start the scene, inspect timestamped evidence, then
                        confirm what should be handed off.
                      </p>
                      <div className="walkthrough-steps">
                        <span>
                          <b>01</b>Replay the source
                        </span>
                        <span>
                          <b>02</b>Review the evidence
                        </span>
                        <span>
                          <b>03</b>Confirm & hand off
                        </span>
                      </div>
                      <div className="fixture-note">
                        {selectedAnalysis?.status === "running" ? (
                          <Badge kind="muted">Analysis in progress</Badge>
                        ) : selectedAnalysis ? (
                          <ModeBadge mode={displayedMode} />
                        ) : (
                          <Badge kind="muted">Not analyzed in this view</Badge>
                        )}
                        <p>
                          {selectedAnalysis?.status === "running"
                            ? "Analysis is running for this source. Results will appear here when ready."
                            : displayedMode === "unavailable"
                              ? "No source-specific analysis result is available for this preview."
                              : mode === "fixture"
                                ? "The next replay uses a labeled fixture to exercise the workflow without paid model calls."
                                : mode === "cached"
                                  ? "Frozen cache only. A missing genuine model result will be shown as unavailable."
                                  : "Fresh analysis can call the configured model within the server budget. Review its observations before confirming."}
                        </p>
                      </div>
                    </div>
                  )}
                </>
              ) : (
                <div className="loading-state">
                  <div className="loading-bar" />
                  <p>Connecting to the local incident service…</p>
                </div>
              )}
            </aside>
            <div className="lower-band">
              <div className="stage" aria-label="City map stage">
                <Suspense
                  fallback={
                    <section className="map-shell">
                      <div className="loading-state">
                        Preparing the spatial view…
                      </div>
                    </section>
                  }
                >
                  <MapView
                    source={evidenceSource}
                    incident={incident}
                    incidents={runIncidents}
                    onSelect={() => openEvidence()}
                    onSelectIncident={openEvidence}
                    liveCameras={visibleLiveCameras}
                    liveSelectedId={liveSelectedId}
                    onSelectLiveCamera={selectMapCamera}
                  />
                </Suspense>
              </div>
              <div className="dock" aria-label="Control deck">
                <aside className="source-rail" aria-label="Replay sources">
                  <div className="rail-heading">
                    <h2>Replay sources</h2>
                    <span className="count-label">
                      {sources.length.toString().padStart(2, "0")}
                    </span>
                  </div>
                  <p className="rail-intro">
                    Recorded scenes, ready to review.
                  </p>
                  <div className="source-list">
                    {sources.map((s, index) => (
                      <button
                        key={s.id}
                        className={`source-card ${sourceId === s.id ? "selected" : ""}`}
                        onClick={() => {
                          // Source browsing must not expire another camera's evidence.
                          autoSelectCandidate.current = false;
                          cancelReplayPlayback();
                          videoRef.current?.pause();
                          setSourceId(s.id);
                          setSelectedId(
                            state?.incidents.find(
                              (item) => item.source_id === s.id,
                            )?.id ?? null,
                          );
                          setPlaybackKey((key) => key + 1);
                        }}
                        disabled={Boolean(pending)}
                        aria-pressed={sourceId === s.id}
                        aria-label={`Select ${sourceName(s.id)}`}
                      >
                        <div className="source-thumb">
                          {s.media_available &&
                            s.poster_available !== false && (
                              <img
                                src={s.poster_url}
                                alt=""
                                onError={(e) => {
                                  e.currentTarget.style.display = "none";
                                }}
                              />
                            )}
                          <span className="thumb-icon">
                            <Icon name="camera" size={22} />
                          </span>
                          <span className="source-number mono">
                            CAM {String(index + 1).padStart(2, "0")}
                          </span>
                          <span className="duration mono">
                            {timeLabel(s.duration_seconds)}
                          </span>
                        </div>
                        <div className="source-card-text">
                          <strong>{sourceName(s.id)}</strong>
                          <small>{sourceHint(s.id)}</small>
                          <span className="source-availability">
                            <i
                              className={
                                s.media_available
                                  ? "tiny-dot"
                                  : "tiny-dot unavailable"
                              }
                            />
                            {s.media_available
                              ? "Recorded replay"
                              : "Media unavailable"}
                            {sourceId === s.id && (
                              <Icon name="check" size={13} />
                            )}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                  <div className="rail-footnote">
                    <Icon name="shield" size={16} />
                    <p>
                      Recorded demo scenes.
                      <br />
                      Every source keeps its original credit.
                    </p>
                  </div>
                </aside>
                <section className="incident-tray">
                  <div className="tray-heading">
                    <div>
                      <span className="eyebrow">REVIEW QUEUE</span>
                      <h2>
                        {runIncidents.length
                          ? "Incidents with evidence."
                          : "Ready when you are."}
                      </h2>
                    </div>
                    <span className="count-label">
                      {runIncidents.length.toString().padStart(2, "0")}
                    </span>
                  </div>
                  {runIncidents.length ? (
                    runIncidents.map((i) => (
                      <button
                        key={i.id}
                        className={`incident-card ${selectedId === i.id || incident?.id === i.id ? "selected" : ""}`}
                        data-testid="incident-card"
                        onClick={() => openEvidence(i.id)}
                      >
                        <span
                          className={`incident-icon ${i.review_status === "confirmed" ? "confirmed" : ""}`}
                        >
                          <Icon
                            name={
                              i.review_status === "confirmed"
                                ? "check"
                                : "alert"
                            }
                            size={20}
                          />
                        </span>
                        <span className="incident-card-content">
                          <strong>{i.title}</strong>
                          <span>
                            <span className="mono">#{shortId(i.id)}</span>
                            <span>·</span>
                            {i.review_status === "candidate"
                              ? "Needs human review"
                              : i.review_status}
                            <span>·</span>
                            {i.source_mode === "live"
                              ? "Live CCTV"
                              : i.analysis_mode === "fixture"
                                ? "Fixture"
                                : i.analysis_mode}
                          </span>
                        </span>
                        <Icon name="arrow" size={17} />
                      </button>
                    ))
                  ) : (
                    <div className="queue-empty">
                      <span className="empty-icon">
                        <Icon name="layers" size={21} />
                      </span>
                      <p>
                        {selectedAnalysis?.status === "running"
                          ? "Analysis is running for this source."
                          : selectedAnalysis?.status === "unavailable"
                            ? "Analysis is unavailable for this scene."
                            : selectedAnalysis?.status === "complete"
                              ? selectedAnalysis.mode === "fixture"
                                ? "This fixture produced no incident candidate."
                                : selectedAnalysis.mode === "cached"
                                  ? "The saved model result contains no incident candidate."
                                  : "Fresh analysis produced no incident candidate."
                              : "Start a replay to bring its evidence into the review queue."}
                        <small>
                          {selectedAnalysis?.status === "complete"
                            ? selectedAnalysis.mode === "fixture"
                              ? "Fixture behavior is not a measured detection result."
                              : "No candidate does not establish that the scene is safe. Review the source footage."
                            : "The demo keeps source, analysis, and review status separate."}
                        </small>
                      </p>
                    </div>
                  )}
                  {selectedAnalysis?.message && (
                    <p className="analysis-message" role="status">
                      {selectedAnalysis.message}
                    </p>
                  )}
                </section>
                <button
                  className={`cctv-toggle ${cctvVisible ? "is-open" : ""}`}
                  aria-expanded={cctvVisible}
                  onClick={() => {
                    if (cctvVisible) {
                      setCctvOpen(false);
                      setLiveSelectedId(null);
                    } else setCctvOpen(true);
                  }}
                >
                  <span className="cctv-toggle-icon">
                    <Icon name="camera" size={16} />
                  </span>
                  <span className="cctv-toggle-text">
                    <strong>Public CCTV network</strong>
                    <small className="mono">
                      {feedCount} Caltrans cameras · live video + local YOLO
                    </small>
                  </span>
                  <span className="cctv-toggle-action mono">
                    {cctvVisible ? "Hide" : "Browse"}
                    <Icon name="chevron" size={14} />
                  </span>
                </button>
              </div>
            </div>
            <div
              ref={livePreviewRef}
              tabIndex={-1}
              aria-label="Selected public camera preview"
              className={`cctv-drawer ${cctvVisible ? "is-open" : ""}`}
            >
              <LiveCameraPanel
                runId={state?.run.id}
                catalog={liveCatalog}
                selectedId={liveSelectedId}
                onSelect={setLiveSelectedId}
                onVisibleCamerasChange={setVisibleLiveCameras}
                loading={liveLoading}
                catalogError={liveError}
              />
            </div>
          </div>
          <footer className="desk-footer">
            <div>
              <span className="status-dot" />
              <span>Operator confirmation required</span>
              <span className="footer-divider">/</span>
              <span>{confirmedCount} confirmed this run</span>
            </div>
            <div className="footer-metrics">
              <span>
                <b>
                  {state
                    ? (state.telemetry.network_inference_calls ?? "Unknown")
                    : "—"}
                </b>{" "}
                cloud inference calls
              </span>
              <span>
                <b>{state ? (state.telemetry.cache_hits ?? "Unknown") : "—"}</b>{" "}
                cache hits
              </span>
              <span className="mono">
                {state?.telemetry.estimated_spend_usd == null
                  ? "Spend unknown"
                  : `$${state.telemetry.estimated_spend_usd.toFixed(state.telemetry.estimated_spend_usd > 0 && state.telemetry.estimated_spend_usd < 0.01 ? 4 : 2)} ${state.telemetry.unknown_cost_requests ? "API cost bound" : "est. API cost"}`}
              </span>
            </div>
          </footer>
        </>
      )}
    </div>
  );
}

function Handoff({
  incident,
  config,
}: {
  incident: Incident;
  config: Config | null;
}) {
  const publicUrl = config?.public_base_url
    ? `${config.public_base_url.replace(/\/$/, "")}${incident.responder_path}`
    : null;
  return (
    <section className="handoff">
      <div className="handoff-heading">
        <Icon name="phone" size={18} />
        <div>
          <strong>Keep the handoff connected.</strong>
          <span>
            {publicUrl
              ? "Scan this incident on your phone."
              : "Local preview · phone access not configured"}
          </span>
        </div>
      </div>
      {publicUrl ? (
        <div className="qr-row">
          <QRCodeSVG
            value={publicUrl}
            size={100}
            marginSize={3}
            bgColor="#ffffff"
            fgColor="#0e0e0e"
            title="Open this incident's responder brief"
          />
          <p>
            Selected incident only.
            <br />
            This link expires when the demo resets.
            <a
              href={publicUrl}
              target="_blank"
              rel="noreferrer"
              data-testid="responder-preview"
            >
              Open responder page <Icon name="arrow" size={14} />
            </a>
          </p>
        </div>
      ) : (
        <a
          className="preview-link"
          href={incident.responder_path}
          target="_blank"
          rel="noreferrer"
          data-testid="responder-preview"
        >
          Open local responder preview
          <Icon name="arrow" size={17} />
        </a>
      )}
    </section>
  );
}

function Responder({
  runId,
  incidentId,
}: {
  runId: string;
  incidentId: string;
}) {
  const [data, setData] = useState<ResponderData | null>(null);
  const [error, setError] = useState("");
  const [expired, setExpired] = useState(false);
  const [notFound, setNotFound] = useState(false);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    let failures = 0;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    const poll = async () => {
      if (document.visibilityState === "hidden") {
        timer = setTimeout(poll, 2000);
        return;
      }
      try {
        const result = await request<ResponderData>(
          `/api/respond/${encodeURIComponent(runId)}/${encodeURIComponent(incidentId)}`,
          { signal: controller.signal },
        );
        if (!alive) return;
        setData(result);
        setError("");
        setCheckedAt(
          new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
          }),
        );
        failures = 0;
      } catch (e) {
        if (!alive || controller.signal.aborted) return;
        if (e instanceof ApiError && e.status === 410) {
          setExpired(true);
          setData(null);
          return;
        }
        if (e instanceof ApiError && e.status === 404) {
          setNotFound(true);
          setData(null);
          return;
        }
        setError(
          "Connection interrupted. The last received status may be stale. Retrying…",
        );
        failures++;
      }
      if (alive)
        timer = setTimeout(poll, Math.min(2000 * (failures + 1), 15000));
    };
    void poll();
    return () => {
      alive = false;
      controller.abort();
      clearTimeout(timer);
    };
  }, [runId, incidentId]);
  const incident = data?.incident;
  return (
    <div className="responder-shell">
      <header className="responder-header">
        <Brand compact />
        <span className="eyebrow">RESPONDER BRIEF</span>
      </header>
      <main className="responder-main">
        {expired || notFound ? (
          <section className="expired-state" role="status">
            <span className="expired-symbol">
              <Icon name="clock" size={30} />
            </span>
            <span className="eyebrow">
              {expired ? "DEMO RUN ENDED" : "BRIEF UNAVAILABLE"}
            </span>
            <h1>
              {expired
                ? "This handoff has expired."
                : "This incident could not be found."}
            </h1>
            <p>
              {expired
                ? "The operator reset the demo. Scan the new incident’s QR code to see the current brief."
                : "Check the full link with the operator. This page never redirects to a different incident."}
            </p>
            <span className="mono">RUN {shortId(runId)}</span>
          </section>
        ) : data && incident ? (
          <>
            <div className="responder-kicker">
              <span className="mono">INCIDENT #{shortId(incident.id)}</span>
              <Badge
                kind={
                  incident.review_status === "confirmed" ? "green" : "amber"
                }
              >
                {incident.review_status === "confirmed"
                  ? "Operator confirmed"
                  : incident.review_status === "candidate"
                    ? "Awaiting confirmation"
                    : incident.review_status}
              </Badge>
            </div>
            <h1>{incident.title}</h1>
            <p className="responder-lede">
              {incident.review_status === "confirmed"
                ? "A reviewed scene, with its evidence and remaining unknowns in one place."
                : "This candidate has not been confirmed by the operator. Review status updates automatically."}
            </p>
            <Provenance incident={incident} />
            <VoiceBrief incident={incident} disabled={Boolean(error)} />
            {error && (
              <div className="responder-warning" role="alert">
                {error}
              </div>
            )}
            <section className="responder-video">
              {incident.source_mode === "live" ? (
                <LiveIncidentEvidence key={incident.id} incident={incident} />
              ) : (
                <Video source={data.source} />
              )}
              <Credit source={data.source} />
            </section>
            <section className="responder-section">
              <div className="section-label">EVIDENCE SUMMARY</div>
              {incident.analysis_mode === "fixture" && (
                <p className="fixture-disclosure">
                  Fixture observations for a demonstration; not model-generated
                  analysis.
                </p>
              )}
              <ul className="responder-observations">
                {incident.evidence.map((item, index) => (
                  <li key={index}>
                    <span className="mono">
                      {timeLabel(item.timestamp_seconds)}
                    </span>
                    <p>{item.observation}</p>
                  </li>
                ))}
              </ul>
            </section>
            <section className="responder-section location-section">
              <Icon name="pin" size={22} />
              <div>
                <h2>
                  {incident.location.quality === "simulated"
                    ? "Simulated placement"
                    : "Camera location"}
                </h2>
                <p>{incident.location.label}</p>
                <small>
                  {incident.location.quality === "simulated"
                    ? "Actual filming location is unknown. Do not use this marker for navigation or dispatch."
                    : "The camera position is not a measured object position."}
                </small>
              </div>
            </section>
            <section className="responder-section">
              <div className="section-label">REMAINING UNKNOWNS</div>
              <ul className="unknown-list">
                {incident.unknowns.map((u, i) => (
                  <li key={i}>{u}</li>
                ))}
              </ul>
              <p className="context-unavailable">
                {incident.source_mode === "live"
                  ? "External corroboration: not independently verified. Review the frozen camera evidence and remaining unknowns."
                  : "External corroboration: not applicable to this historical replay."}
              </p>
            </section>
            <div className="responder-status">
              <Icon name="shield" size={19} />
              <p>
                Read-only demo brief
                <span>
                  Checked {checkedAt ?? "now"} · updates every 2 seconds
                </span>
              </p>
            </div>
          </>
        ) : (
          <div className="loading-state">
            <div className="loading-bar" />
            <h1>Opening the incident brief…</h1>
            <p>{error || "Connecting to the selected run."}</p>
          </div>
        )}
      </main>
      <footer className="responder-footer">
        {incident?.source_mode === "live"
          ? "Public-camera review · No automatic dispatch"
          : "Recorded demonstration · No emergency dispatch"}
        <br />
        <span className="mono">RUN {shortId(runId)}</span>
      </footer>
    </div>
  );
}

function Labeling({
  sources,
  onBack,
}: {
  sources: Source[];
  onBack: () => void;
}) {
  const [sourceId, setSourceId] = useState("road-obstruction");
  const [labels, setLabels] = useState<Label[]>([]);
  const [reviewer, setReviewer] = useState("");
  const [label, setLabel] = useState("");
  const [start, setStart] = useState("0");
  const [end, setEnd] = useState("5");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const source = sources.find((s) => s.id === sourceId);
  useEffect(() => {
    const controller = new AbortController();
    request<{ labels: Label[] }>("/api/labels", { signal: controller.signal })
      .then((data) => setLabels(data.labels))
      .catch((e) => {
        if (!controller.signal.aborted) setError(errorMessage(e));
      });
    return () => controller.abort();
  }, []);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!label || !reviewer.trim()) {
      setError("Choose a condition and enter your reviewer name.");
      return;
    }
    if (
      !Number.isFinite(Number(start)) ||
      !Number.isFinite(Number(end)) ||
      Number(start) < 0 ||
      Number(end) <= Number(start) ||
      Number(end) > (source?.duration_seconds ?? 0)
    ) {
      setError(
        "Choose a valid time window within the clip. End must be after start.",
      );
      return;
    }
    setBusy(true);
    try {
      const saved = await post<Label>("/api/labels", {
        source_id: sourceId,
        start_seconds: Number(start),
        end_seconds: Number(end),
        label,
        reviewer: reviewer.trim(),
        note,
      });
      setLabels((current) => [...current, saved]);
      setMessage("Human label saved.");
      setLabel("");
      setNote("");
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="labeling-page">
      <div className="labeling-heading">
        <div>
          <span className="eyebrow">HUMAN REVIEW / DEVELOPMENT DATA</span>
          <h1>Start with what you can see.</h1>
          <p>
            Label a time window after reviewing the footage. Unknown is a useful
            answer.
          </p>
        </div>
        <button className="secondary-button" onClick={onBack}>
          <Icon name="arrow" style={{ transform: "rotate(180deg)" }} />
          Back to desk
        </button>
      </div>
      <div className="labeling-grid">
        <section className="labeling-video">
          <label className="field-label">
            Replay source
            <select
              value={sourceId}
              onChange={(e) => {
                setSourceId(e.target.value);
                setLabel("");
                setMessage("");
              }}
            >
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {sourceName(s.id)}
                </option>
              ))}
            </select>
          </label>
          {source && (
            <>
              <Video source={source} />
              <Credit source={source} />
            </>
          )}
          <div className="labeling-note">
            <Icon name="doc" />
            <p>
              These clips are development material. Repeated windows from one
              clip are not independent incidents. Labels are never filled in by
              a model.
            </p>
          </div>
        </section>
        <form className="label-form" onSubmit={submit}>
          <span className="eyebrow">NEW HUMAN LABEL</span>
          <h2>Describe this window.</h2>
          <div className="two-fields">
            <label className="field-label">
              Start (seconds)
              <input
                type="number"
                min="0"
                step="0.1"
                value={start}
                onChange={(e) => setStart(e.target.value)}
                required
              />
            </label>
            <label className="field-label">
              End (seconds)
              <input
                type="number"
                min="0"
                max={source?.duration_seconds}
                step="0.1"
                value={end}
                onChange={(e) => setEnd(e.target.value)}
                required
              />
            </label>
          </div>
          <label className="field-label">
            Observable condition
            <select
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              required
            >
              <option value="">Choose after reviewing…</option>
              <option value="road_obstruction">
                Road obstruction / work zone
              </option>
              <option value="person_in_roadway">
                Person in roadway · context needs review
              </option>
              <option value="normal">Normal traffic</option>
              <option value="queue">Queue / dense traffic</option>
              <option value="uncertain">
                Insufficient visibility / uncertain
              </option>
            </select>
          </label>
          <label className="field-label">
            Reviewer name
            <input
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              maxLength={100}
              autoComplete="name"
              placeholder="Your name"
              required
            />
          </label>
          <label className="field-label">
            Notes (optional)
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              maxLength={2000}
              rows={3}
              placeholder="Visible evidence or uncertainty"
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          {message && (
            <p className="form-success" role="status">
              {message}
            </p>
          )}
          <button type="submit" className="primary-button" disabled={busy}>
            <Icon name="check" />
            {busy ? "Saving…" : "Save human label"}
          </button>
        </form>
      </div>
      <section className="labels-summary">
        <div>
          <span className="eyebrow">EVALUATION READINESS</span>
          <h2>
            {labels.length
              ? `${labels.length} human-labeled window${labels.length === 1 ? "" : "s"}`
              : "Awaiting labels"}
          </h2>
          <p>
            {labels.length
              ? `${new Set(labels.map((l) => l.source_id)).size} distinct source clip(s). Freeze configuration before evaluation; no accuracy is inferred from this count.`
              : "No human labels submitted. Accuracy, gate recall, and false-alert metrics are not available."}
          </p>
        </div>
        {labels.length > 0 && (
          <div className="label-history">
            {labels
              .slice(-5)
              .reverse()
              .map((l) => (
                <div key={l.id}>
                  <strong>{sourceName(l.source_id)}</strong>
                  <span className="mono">
                    {timeLabel(l.start_seconds)}–{timeLabel(l.end_seconds)}
                  </span>
                  <span>{l.label.replaceAll("_", " ")}</span>
                  <span>{l.reviewer}</span>
                </div>
              ))}
          </div>
        )}
      </section>
    </main>
  );
}

export function App() {
  const match = window.location.pathname.match(
    /^\/respond\/([^/]+)\/([^/]+)\/?$/,
  );
  return (
    <>
      {match ? (
        <Responder runId={match[1]} incidentId={match[2]} />
      ) : (
        <Operator />
      )}
      <div className="source-notice">
        <a
          href="https://github.com/ZelinZhu-Richard/no-escape/tree/feat/clearway-overnight-demo"
          target="_blank"
          rel="noreferrer"
        >
          Source code
        </a>
        <span> · </span>
        <a
          href="/assets/licenses/AGPL-3.0.txt"
          target="_blank"
          rel="noreferrer"
        >
          AGPL-3.0
        </a>
        <span> · No warranty</span>
      </div>
    </>
  );
}
