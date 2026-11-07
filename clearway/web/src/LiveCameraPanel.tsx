import { useEffect, useMemo, useRef, useState } from "react";
import { request } from "./api";
import { Icon } from "./Icon";
import {
  cadenceLabel,
  filterLiveCameras,
  BAY_AREA_REGIONS,
  MAX_LIVE_CAMERAS,
  isBayAreaCamera,
  readLiveSnapshot,
} from "./liveCameras";
import type {
  LiveCamera,
  LiveCameraCatalog,
  LiveSnapshot,
} from "./liveCameras";
import "./LiveCameraPanel.css";
import { LiveCameraVideo } from "./LiveCameraVideo";
import {
  LiveDetectionCounts,
  LiveImageBoxes,
  useVerifiedSnapshotDetections,
} from "./LiveImageDetections";

export interface LiveCameraPanelProps {
  catalog: LiveCameraCatalog | null;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onVisibleCamerasChange?: (cameras: LiveCamera[]) => void;
  loading?: boolean;
  catalogError?: string;
  active?: boolean;
  runId?: string;
}

function useSelectedSnapshot(camera: LiveCamera | undefined, enabled: boolean) {
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const attempts = useRef(new Map<string, { at: number; interval: number }>());
  // Keep a few selected images for A → B → A navigation without refetching.
  // Never prefetch an unselected camera or retain a complete camera archive.
  const retained = useRef(new Map<string, LiveSnapshot>());
  const cameraId = camera?.id;
  const sourceInterval =
    Math.max(30, camera?.source_refresh_seconds ?? 300) * 1000;

  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    const previous = cameraId ? (retained.current.get(cameraId) ?? null) : null;
    setSnapshot(previous);
    setLoading(false);
    setNotice("");
    if (!cameraId || !enabled) return;
    const selectedId = cameraId;
    const hidden = () => document.visibilityState === "hidden";
    let refreshInterval = sourceInterval;
    let inFlight = false;
    const retain = (value: LiveSnapshot | null) => {
      retained.current.delete(selectedId);
      if (value) retained.current.set(selectedId, value);
      while (retained.current.size > 4)
        retained.current.delete(retained.current.keys().next().value!);
    };
    const rememberInterval = (value: number) => {
      refreshInterval = Math.max(30_000, value);
      const last = attempts.current.get(selectedId);
      if (last)
        attempts.current.set(selectedId, {
          ...last,
          interval: refreshInterval,
        });
    };
    const schedule = (delay: number) => {
      if (timer) clearTimeout(timer);
      if (!disposed && !hidden()) timer = setTimeout(refresh, delay);
    };
    const fail = (message: string) => {
      setNotice(message);
      setSnapshot((current) => {
        const stale = current ? { ...current, stale: true } : null;
        retain(stale);
        return stale;
      });
    };
    async function refresh() {
      if (disposed || hidden()) return;
      const lastAttempt = attempts.current.get(selectedId);
      const elapsed =
        lastAttempt === undefined ? Infinity : Date.now() - lastAttempt.at;
      const wait = retained.current.has(selectedId)
        ? (lastAttempt?.interval ?? refreshInterval)
        : 30_000;
      if (elapsed < wait) {
        schedule(wait - elapsed);
        return;
      }
      controller = new AbortController();
      const activeRequest = controller;
      attempts.current.set(selectedId, {
        at: Date.now(),
        interval: sourceInterval,
      });
      inFlight = true;
      setLoading(true);
      setNotice("");
      timeout = setTimeout(() => activeRequest.abort(), 20_000);
      try {
        const raw = await request<unknown>(
          `/api/live-cameras/${encodeURIComponent(selectedId)}/snapshot`,
          { signal: activeRequest.signal },
        );
        if (disposed || activeRequest.signal.aborted) return;
        const result = readLiveSnapshot(raw, selectedId);
        if (!result) {
          rememberInterval(30_000);
          fail(
            "The provider response could not be displayed. No substitute footage is shown.",
          );
          return;
        }
        rememberInterval(
          result.status === "available"
            ? Math.max(sourceInterval, result.refresh_after_seconds * 1000)
            : result.refresh_after_seconds * 1000,
        );
        if (result.image_data_url) {
          retain(result);
          setSnapshot(result);
          if (result.stale)
            setNotice("The provider returned an older cached image.");
        } else
          fail(
            result.status === "throttled"
              ? "Provider refresh limit reached. Waiting before retrying."
              : "This camera image is currently unavailable. Retrying at the source cadence.",
          );
      } catch {
        if (!disposed && !hidden()) {
          rememberInterval(30_000);
          fail(
            "Camera refresh failed. Any image below is the last successful retrieval.",
          );
        }
      } finally {
        inFlight = false;
        if (timeout) clearTimeout(timeout);
        if (!disposed) {
          setLoading(false);
          schedule(
            Math.max(
              30_000,
              refreshInterval -
                (Date.now() - (attempts.current.get(selectedId)?.at ?? 0)),
            ),
          );
        }
      }
    }
    const visibility = () => {
      if (hidden()) {
        if (timer) clearTimeout(timer);
        if (inFlight) rememberInterval(30_000);
        controller?.abort();
        setLoading(false);
      } else void refresh();
    };
    document.addEventListener("visibilitychange", visibility);
    void refresh();
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
      if (timeout) clearTimeout(timeout);
      if (inFlight) rememberInterval(30_000);
      controller?.abort();
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [cameraId, enabled, sourceInterval]);
  return {
    snapshot: snapshot?.camera_id === cameraId ? snapshot : null,
    loading,
    notice,
  };
}

const formatTime = (value: string | null) =>
  value
    ? new Date(value).toLocaleString([], {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : "Unknown";
const CAMERA_PAGE_SIZE = 50;

export function LiveCameraPanel({
  catalog,
  selectedId,
  onSelect,
  onVisibleCamerasChange,
  loading = false,
  catalogError = "",
  active = true,
  runId,
}: LiveCameraPanelProps) {
  const [query, setQuery] = useState("");
  const [region, setRegion] = useState("");
  const [feedType, setFeedType] = useState<"video" | "all">("video");
  const [listLimit, setListLimit] = useState(CAMERA_PAGE_SIZE);
  const [paused, setPaused] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);
  const [mediaChoice, setMediaChoice] = useState<{
    cameraId: string;
    mode: "video" | "snapshot";
  } | null>(null);
  const [failedStream, setFailedStream] = useState<string | null>(null);
  const cameras = useMemo(
    () =>
      (catalog?.cameras ?? [])
        .filter(isBayAreaCamera)
        .slice(0, MAX_LIVE_CAMERAS),
    [catalog],
  );
  const regions = useMemo(() => {
    const present = new Set(cameras.map((camera) => camera.region_id));
    return Object.entries(BAY_AREA_REGIONS)
      .filter(([id]) => present.has(id))
      .map(([id, name]) => ({ id, name }));
  }, [cameras]);
  const demoCamera = cameras.find(
    (camera) => camera.id === "caltrans-d4-37" && camera.streaming_url,
  );
  const previewRef = useRef<HTMLDivElement>(null);
  const visible = useMemo(
    () => filterLiveCameras(cameras, region, query)
      .filter((camera) => feedType === "all" || Boolean(camera.streaming_url)),
    [cameras, region, query, feedType],
  );
  const selected = cameras.find((camera) => camera.id === selectedId);
  const listed = visible.slice(0, listLimit);
  const videoCount = cameras.filter((camera) => camera.streaming_url).length;
  useEffect(() => {
    setListLimit(CAMERA_PAGE_SIZE);
  }, [query, region, cameras, feedType]);
  const showVideo = Boolean(
    selected?.streaming_url &&
    failedStream !== selectedId &&
    !(mediaChoice?.cameraId === selectedId && mediaChoice.mode === "snapshot"),
  );
  const {
    snapshot,
    loading: refreshing,
    notice,
  } = useSelectedSnapshot(selected, active && !paused && !showVideo);
  const snapshotDetections = useVerifiedSnapshotDetections(snapshot);
  useEffect(() => {
    onVisibleCamerasChange?.(visible);
  }, [visible, onVisibleCamerasChange]);
  useEffect(() => {
    setImageFailed(false);
  }, [selectedId, snapshot?.fetched_at, snapshot?.image_data_url]);
  const hasImage = Boolean(snapshot?.image_data_url) && !imageFailed;
  const stale = Boolean(snapshot?.stale || notice || paused);

  return (
    <section
      className="live-camera-panel"
      aria-label="Public traffic CCTV"
      data-testid="live-camera-panel"
    >
      <div className="live-camera-heading">
        <div>
          <span className="eyebrow">PUBLIC CAMERA NETWORK</span>
          <h2>Bay Area traffic CCTV</h2>
        </div>
        <span className="live-camera-count">
          {cameras.length} cameras · Bay Area
        </span>
      </div>
      <p className="live-camera-result-count">
        {videoCount} advertised video links · {cameras.length} snapshot
        endpoints
      </p>
      <p className="live-camera-intro">
        Live-video cameras are shown first. Select one to play its provider stream;
        snapshots are used if video fails or you choose them. Local YOLO
        watches the selected playing video for sustained signals and sends
        candidates to the review queue. Confirmation stays with you.
      </p>
      {demoCamera && (
        <button
          className="live-camera-shortcut"
          onClick={() => {
            onSelect(demoCamera.id);
            setPaused(false);
            setFailedStream(null);
            setMediaChoice({ cameraId: demoCamera.id, mode: "video" });
            requestAnimationFrame(() =>
              previewRef.current?.scrollIntoView({
                block: "center",
                behavior: "auto",
              }),
            );
          }}
        >
          Open 6th Street live <span>I-80 · San Francisco</span>
        </button>
      )}
      {loading ? (
        <p className="live-camera-empty" role="status">
          Loading the public camera catalog…
        </p>
      ) : !cameras.length ? (
        <p className="live-camera-empty" role="status">
          {catalogError ||
            "Public cameras are unavailable. The recorded replay remains ready to use."}
        </p>
      ) : (
        <div className="live-camera-layout">
          <div className="live-camera-browser">
            <div className="live-camera-filters">
              <label className="live-camera-feed-filter">
                <span>Camera feeds</span>
                <select
                  value={feedType}
                  onChange={(event) => setFeedType(event.target.value as "video" | "all")}
                  aria-label="Camera feeds"
                >
                  <option value="video">Live video ({videoCount})</option>
                  <option value="all">All cameras ({cameras.length})</option>
                </select>
              </label>
              <label>
                <span className="sr-only">Search public cameras</span>
                <input
                  type="search"
                  placeholder="Search road or camera"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  aria-label="Search public cameras"
                />
              </label>
              <label>
                <span className="sr-only">Camera region</span>
                <select
                  value={region}
                  onChange={(event) => setRegion(event.target.value)}
                  aria-label="Camera region"
                >
                  <option value="">All Bay Area counties</option>
                  {regions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="live-camera-result-count">
              {visible.length} matching cameras{" "}
              {catalog?.stale && <span>· dated catalog</span>}
            </div>
            <ul className="live-camera-list" aria-label="Public camera choices">
              {listed.map((camera) => (
                <li key={camera.id}>
                  <button
                    onClick={() => {
                      setFailedStream(null);
                      setMediaChoice(null);
                      setPaused(false);
                      onSelect(camera.id);
                    }}
                    aria-pressed={selectedId === camera.id}
                    className={selectedId === camera.id ? "is-selected" : ""}
                  >
                    <Icon name="camera" size={15} />
                    <span>
                      <strong>{camera.name}</strong>
                      <small>
                        {[camera.roadway, camera.direction, camera.region_name]
                          .filter(Boolean)
                          .join(" · ")}
                      </small>
                      <small className="live-camera-capability">
                        {camera.streaming_url ? "Live video · snapshot fallback" : "Snapshot only"}
                      </small>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
            {visible.length > CAMERA_PAGE_SIZE && (
              <div className="live-camera-refresh">
                <span role="status">
                  Showing {listed.length} of {visible.length}
                </span>
                {listed.length < visible.length && (
                  <button
                    onClick={() =>
                      setListLimit((limit) => limit + CAMERA_PAGE_SIZE)
                    }
                  >
                    Show{" "}
                    {Math.min(CAMERA_PAGE_SIZE, visible.length - listed.length)}{" "}
                    more
                  </button>
                )}
              </div>
            )}
            {!visible.length && (
              <p className="live-camera-empty">
                {feedType === "video"
                  ? "No video cameras match these filters. Choose All cameras to include snapshots."
                  : "No cameras match these filters."}
              </p>
            )}
          </div>
          <div className="live-camera-preview" aria-live="off" ref={previewRef}>
            {selected ? (
              <>
                <div className="live-preview-heading">
                  <div>
                    <span className="live-snapshot-badge">
                      {showVideo ? "PROVIDER VIDEO" : "REFRESHED SNAPSHOT"}
                    </span>
                    <h3>{selected.name}</h3>
                  </div>
                  <button
                    className="live-close"
                    aria-label="Close selected public camera"
                    onClick={() => onSelect(null)}
                  >
                    <Icon name="cross" size={16} />
                  </button>
                </div>
                {selected.streaming_url && (
                  <div
                    className="live-media-mode"
                    aria-label="Camera media mode"
                  >
                    <button
                      aria-pressed={showVideo}
                      onClick={() => {
                        setMediaChoice({
                          cameraId: selected.id,
                          mode: "video",
                        });
                        setFailedStream(null);
                        setPaused(false);
                      }}
                    >
                      {failedStream === selected.id
                        ? "Retry live video"
                        : "Live video"}
                    </button>
                    <button
                      aria-pressed={!showVideo}
                      onClick={() =>
                        setMediaChoice({
                          cameraId: selected.id,
                          mode: "snapshot",
                        })
                      }
                    >
                      Snapshot + YOLO
                    </button>
                  </div>
                )}
                {showVideo ? (
                  <LiveCameraVideo
                    key={selected.id}
                    camera={selected}
                    active={active && !paused}
                    runId={runId}
                    onFallback={() => setFailedStream(selected.id)}
                  />
                ) : (
                  <>
                    {failedStream === selected.id && (
                      <p className="live-snapshot-notice" role="status">
                        Video is unavailable in this browser or from this
                        camera. Showing its provider snapshot instead.
                      </p>
                    )}
                    <div className="live-snapshot-frame">
                      {hasImage ? (
                        <img
                          src={snapshot!.image_data_url!}
                          alt={`${selected.name} public traffic camera snapshot; capture time ${snapshot?.capture_time ? formatTime(snapshot.capture_time) : "unknown"}`}
                          onError={() => setImageFailed(true)}
                        />
                      ) : (
                        <div className="live-snapshot-placeholder">
                          <Icon name="camera" size={25} />
                          <span>
                            {imageFailed
                              ? "The provider image could not be decoded."
                              : refreshing
                                ? "Retrieving the selected camera…"
                                : paused
                                  ? "Updates paused. Resume to retrieve this camera."
                                  : notice || "Waiting for a provider image."}
                          </span>
                        </div>
                      )}
                      {hasImage && snapshotDetections && (
                        <LiveImageBoxes detections={snapshotDetections} />
                      )}
                      {hasImage && (
                        <span
                          className={`live-image-status ${stale ? "is-stale" : ""}`}
                        >
                          {stale ? "LAST RETRIEVED IMAGE" : "PROVIDER SNAPSHOT"}
                        </span>
                      )}
                    </div>
                    {hasImage &&
                      (snapshotDetections ? (
                        <LiveDetectionCounts detections={snapshotDetections} />
                      ) : (
                        <p className="live-camera-disclosure">
                          Local YOLO unavailable or awaiting exact-image
                          verification. No substitute boxes are shown.
                        </p>
                      ))}
                    {hasImage && snapshotDetections && (
                      <p className="live-camera-disclosure">
                        YOLO boxes match this exact snapshot. Object detections
                        do not establish danger.
                      </p>
                    )}
                  </>
                )}
                <div className="live-camera-refresh">
                  <span role="status">
                    {showVideo
                      ? paused
                        ? "Video paused"
                        : "Selected provider feed"
                      : refreshing
                        ? "Refreshing…"
                        : paused
                          ? "Updates paused"
                          : `Source cadence ${cadenceLabel(selected.source_refresh_seconds)}`}
                  </span>
                  <button
                    onClick={() => setPaused((value) => !value)}
                    aria-pressed={paused}
                  >
                    {paused ? "Resume updates" : "Pause updates"}
                  </button>
                </div>
                {!showVideo && notice && (
                  <p className="live-snapshot-notice" role="status">
                    {notice}
                  </p>
                )}
                {!showVideo && (
                  <>
                    <dl className="live-snapshot-facts">
                      <div>
                        <dt>Retrieved</dt>
                        <dd title={snapshot?.fetched_at ?? undefined}>
                          {formatTime(snapshot?.fetched_at ?? null)}
                        </dd>
                      </div>
                      <div>
                        <dt>Capture time</dt>
                        <dd>{formatTime(snapshot?.capture_time ?? null)}</dd>
                      </div>
                      {snapshot?.source_last_modified && (
                        <div>
                          <dt>Provider last modified</dt>
                          <dd title={snapshot.source_last_modified}>
                            {formatTime(snapshot.source_last_modified)}
                          </dd>
                        </div>
                      )}
                    </dl>
                    <p className="live-camera-disclosure">
                      {selected.provider} public camera ·{" "}
                      {cadenceLabel(selected.source_refresh_seconds)} published
                      refresh. A refreshed image is not continuous live video.
                      The provider may show an outage card. Updates pause when
                      this tab is hidden. Automatic review candidates require
                      playing video; snapshots provide detections only.
                    </p>
                  </>
                )}
                {selected.provider_url && (
                  <a
                    className="live-provider-link"
                    href={selected.provider_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    View official source <Icon name="arrow" size={12} />
                  </a>
                )}
              </>
            ) : (
              <div className="live-camera-empty-preview">
                <Icon name="camera" size={28} />
                <strong>Select a camera or map pin.</strong>
                <span>
                  Video or a provider snapshot appears here. Local YOLO boxes
                  stay tied to their analyzed image. Camera markers are not
                  incident alerts.
                </span>
              </div>
            )}
          </div>
        </div>
      )}
      {catalog?.fetched_at && (
        <p className="live-catalog-credit">
          {catalog.provider} catalog retrieved {formatTime(catalog.fetched_at)}.
          The image retrieval time is shown separately.
        </p>
      )}
    </section>
  );
}
