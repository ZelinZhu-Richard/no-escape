import { useEffect, useRef, useState } from "react";
import type Hls from "hls.js";
import { publicStreamUrl } from "./liveCameras";
import type { LiveCamera } from "./liveCameras";
import { LiveImageBoxes } from "./LiveImageDetections";
import { useLiveVideoOverlay } from "./useLiveVideoOverlay";
export { captureLocalFrame } from "./useLiveVideoOverlay";

export function LiveCameraVideo({
  camera,
  active,
  onFallback,
}: {
  camera: LiveCamera;
  active: boolean;
  onFallback: () => void;
}) {
  const video = useRef<HTMLVideoElement>(null);
  const fallback = useRef(onFallback);
  fallback.current = onFallback;
  const [visible, setVisible] = useState(document.visibilityState !== "hidden");
  const [playback, setPlayback] = useState("connecting");
  const [yoloEnabled, setYoloEnabled] = useState(true);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    const changed = () => setVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", changed);
    return () => document.removeEventListener("visibilitychange", changed);
  }, []);

  useEffect(() => {
    const element = video.current;
    if (!element || !active || !visible) {
      setPlayback("paused");
      return;
    }
    const url = publicStreamUrl(camera.streaming_url);
    if (!url) {
      fallback.current();
      return;
    }
    let disposed = false;
    let player: Hls | undefined;
    let livePlaylist = false;
    let engine: "initializing" | "hls.js" | "native" = "initializing";
    let nativeAttempted = false;
    let switching = false;
    let hasPlayed = false;
    let startupDeadline = Date.now() + 20_000;
    let bufferingStarted: number | null = null;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    const nativeSupported = Boolean(
      element.canPlayType("application/vnd.apple.mpegurl"),
    );
    const diagnostic = (event: string, reason: string) => {
      const item = {
        at: new Date().toISOString(),
        camera_id: camera.id,
        engine,
        event,
        reason,
        ready_state: element.readyState,
        network_state: element.networkState,
        media_error_code: element.error?.code ?? null,
      };
      const host = window as Window & {
        __clearwayVideoDiagnostics?: (typeof item)[];
      };
      host.__clearwayVideoDiagnostics = [
        ...(host.__clearwayVideoDiagnostics ?? []).slice(-9),
        item,
      ];
      // Only authored reasons and numeric browser states; never log provider URLs,
      // response bodies, signed query strings, or media error messages.
      console.info("Clearway video diagnostics", item);
    };
    const stopMedia = () => {
      player?.destroy();
      player = undefined;
      element.pause();
      element.removeAttribute("src");
      element.load();
    };
    const failed = (reason: string) => {
      if (disposed) return;
      diagnostic("failure", reason);
      // A single alternate-engine attempt is bounded; never loop retries.
      if (
        reason !== "provider_playlist_not_live" &&
        nativeSupported &&
        !nativeAttempted
      ) {
        startNative();
        return;
      }
      disposed = true;
      if (timeout) clearTimeout(timeout);
      stopMedia();
      fallback.current();
    };
    const wait = () => {
      if (disposed || switching) return;
      setPlayback("buffering");
      if (timeout) clearTimeout(timeout);
      bufferingStarted ??= Date.now();
      const deadline = hasPlayed ? bufferingStarted + 20_000 : startupDeadline;
      timeout = setTimeout(
        () => failed("buffering_timeout"),
        Math.max(1, deadline - Date.now()),
      );
    };
    const playing = () => {
      if (disposed) return;
      if (timeout) clearTimeout(timeout);
      hasPlayed = true;
      bufferingStarted = null;
      setPlayback(
        livePlaylist || element.duration === Infinity ? "live" : "playing",
      );
      setNotice("");
      diagnostic("playing", "decoded_media_playing");
    };
    const paused = () => {
      if (!disposed && !switching) setPlayback("paused");
    };
    const startPlayback = () => {
      if (disposed) return;
      const requestedEngine = engine;
      void element.play().catch(() => {
        if (disposed || engine !== requestedEngine) return;
        if (timeout) clearTimeout(timeout);
        setPlayback("paused");
        setNotice("Press play to start the provider video.");
      });
    };
    function startNative() {
      if (!element || disposed || nativeAttempted) return;
      nativeAttempted = true;
      switching = true;
      if (timeout) clearTimeout(timeout);
      stopMedia();
      engine = "native";
      element.dataset.playbackEngine = engine;
      livePlaylist = false;
      hasPlayed = false;
      bufferingStarted = null;
      startupDeadline = Date.now() + 15_000;
      setPlayback("connecting");
      setNotice("Trying the browser's video engine…");
      element.src = url!;
      element.load();
      switching = false;
      diagnostic("start", "native_hls_attempt");
      timeout = setTimeout(() => failed("native_start_timeout"), 15_000);
      startPlayback();
    }
    const mediaError = () => {
      if (!switching && element.error) failed("media_element_error");
    };
    setPlayback("connecting");
    setNotice("");
    element.crossOrigin = "anonymous";
    element.muted = true;
    element.addEventListener("playing", playing);
    element.addEventListener("pause", paused);
    element.addEventListener("waiting", wait);
    element.addEventListener("error", mediaError);
    timeout = setTimeout(() => failed("player_start_timeout"), 20_000);
    // Embedded browsers can advertise native HLS yet stall after a detach and
    // reconnect. Prefer the explicitly managed MSE lifecycle when supported.
    void import("hls.js")
      .then(({ default: HlsPlayer }) => {
        if (disposed) return;
        if (!HlsPlayer.isSupported()) {
          if (nativeSupported) startNative();
          else failed("no_supported_hls_engine");
          return;
        }
        engine = "hls.js";
        element.dataset.playbackEngine = engine;
        diagnostic("start", "mse_hls_attempt");
        const policy = {
          default: {
            maxTimeToFirstByteMs: 7000,
            maxLoadTimeMs: 10_000,
            timeoutRetry: null,
            errorRetry: null,
          },
        };
        player = new HlsPlayer({
          enableWorker: false,
          lowLatencyMode: false,
          backBufferLength: 5,
          maxBufferLength: 10,
          maxMaxBufferLength: 20,
          manifestLoadPolicy: policy,
          playlistLoadPolicy: policy,
          fragLoadPolicy: policy,
        });
        player.on(HlsPlayer.Events.ERROR, (_event, data) => {
          if (data.fatal && engine === "hls.js") {
            const detail = /^[A-Za-z0-9_]{1,60}$/.test(data.details)
              ? data.details
              : "unknown";
            failed(`hls_fatal_${detail}`);
          }
        });
        player.on(HlsPlayer.Events.LEVEL_LOADED, (_event, data) => {
          if (engine !== "hls.js") return;
          livePlaylist = data.details.live;
          if (!livePlaylist) failed("provider_playlist_not_live");
        });
        player.on(HlsPlayer.Events.MANIFEST_PARSED, startPlayback);
        player.loadSource(url);
        player.attachMedia(element);
      })
      .catch(() => failed("player_initialization_failed"));
    return () => {
      disposed = true;
      if (timeout) clearTimeout(timeout);
      element.removeEventListener("playing", playing);
      element.removeEventListener("pause", paused);
      element.removeEventListener("waiting", wait);
      element.removeEventListener("error", mediaError);
      stopMedia();
    };
  }, [camera.id, camera.streaming_url, active, visible]);

  const sampling =
    active && visible && yoloEnabled && ["live", "playing"].includes(playback);
  const overlay = useLiveVideoOverlay(video, camera.id, sampling);
  const status =
    !active || !visible
      ? "Video paused"
      : playback === "live"
        ? "Live video"
        : playback === "playing"
          ? "Provider video playing"
          : playback === "paused"
            ? "Video paused"
            : "Connecting video…";
  return (
    <div className="live-video-view" data-testid="live-video-view">
      <div className="live-snapshot-frame live-stream-frame">
        <video
          ref={video}
          controls
          muted
          playsInline
          autoPlay
          crossOrigin="anonymous"
          aria-label={`${camera.name} provider video`}
        />
        {sampling && overlay.detections && (
          <div
            className="live-video-overlay"
            data-testid="live-direct-overlay"
            data-media-time={overlay.mediaTime}
            data-media-age-ms={overlay.mediaAgeMs}
            data-wall-age-ms={overlay.wallAgeMs}
            data-source-id={camera.id}
          >
            <LiveImageBoxes detections={overlay.detections} />
          </div>
        )}
        <span className="live-image-status">{status.toUpperCase()}</span>
      </div>
      <p className="live-camera-disclosure">
        Provider HLS stream · capture time and delivery delay unknown. This
        video stops loading when the tab is hidden.
      </p>
      {notice && (
        <p className="live-snapshot-notice" role="status">
          {notice}
        </p>
      )}
      <div className="live-camera-refresh">
        <span data-testid="live-yolo-status">
          Local YOLO · {overlay.updatesPerSecond.toFixed(1)} updates/s
          {!sampling
            ? " · paused"
            : overlay.phase === "delayed"
              ? " · delayed"
              : overlay.phase === "waiting"
                ? " · starting"
                : overlay.phase === "unavailable"
                  ? " · unavailable"
                  : ""}
        </span>
        <button
          onClick={() => setYoloEnabled((value) => !value)}
          aria-pressed={yoloEnabled}
        >
          {yoloEnabled ? "Pause YOLO" : "Enable YOLO"}
        </button>
      </div>
      {overlay.message && (
        <p className="live-snapshot-notice" role="status">
          {overlay.message}
        </p>
      )}
    </div>
  );
}
