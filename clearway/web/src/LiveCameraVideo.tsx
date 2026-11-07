import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import type Hls from "hls.js";
import { request } from "./api";
import { publicStreamUrl, readImageDetections } from "./liveCameras";
import type { ImageDetections, LiveCamera } from "./liveCameras";
import {
  jpegHash,
  LiveDetectionCounts,
  LiveImageBoxes,
} from "./LiveImageDetections";

interface AnalyzedVideoFrame {
  cameraId: string;
  image: string;
  mediaTime: number;
  sampledAt: string;
  detections: ImageDetections;
}

export async function captureLocalFrame(video: HTMLVideoElement) {
  if (video.readyState < 2 || video.videoWidth < 1 || video.videoHeight < 1)
    throw new Error("No decoded video frame.");
  const scale = Math.min(1, 640 / video.videoWidth, 480 / video.videoHeight);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
  canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Frame sampling unavailable.");
  const mediaTime = video.currentTime;
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  const image = canvas.toDataURL("image/jpeg", 0.8);
  const hash = await jpegHash(image);
  const bytes = Uint8Array.from(atob(image.split(",")[1]), (character) =>
    character.charCodeAt(0),
  );
  if (bytes.length > 1_000_000)
    throw new Error("Frame exceeds the local limit.");
  return {
    image,
    hash,
    blob: new Blob([bytes], { type: "image/jpeg" }),
    mediaTime,
    sampledAt: new Date().toISOString(),
  };
}

function useLiveFrameDetection(
  videoRef: RefObject<HTMLVideoElement | null>,
  cameraId: string,
  enabled: boolean,
) {
  const [frame, setFrame] = useState<AnalyzedVideoFrame | null>(null);
  const [message, setMessage] = useState("");
  const [count, setCount] = useState(0);
  useEffect(() => {
    setFrame(null);
    setCount(0);
    setMessage("");
  }, [cameraId]);
  useEffect(() => {
    const video = videoRef.current;
    if (!enabled || !video) return;
    let disposed = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let timeout: ReturnType<typeof setTimeout> | undefined;
    let controller: AbortController | undefined;
    let previousMediaTime = -1;
    const sample = async () => {
      if (disposed || document.visibilityState === "hidden") return;
      let delay = 1000;
      try {
        if (
          video.paused ||
          video.readyState < 2 ||
          video.currentTime === previousMediaTime
        )
          return;
        let captured: Awaited<ReturnType<typeof captureLocalFrame>>;
        try {
          captured = await captureLocalFrame(video);
        } catch {
          setMessage(
            "This stream cannot be sampled in this browser. Choose Snapshot for local YOLO on its provider image.",
          );
          disposed = true;
          return;
        }
        if (disposed) return;
        previousMediaTime = captured.mediaTime;
        controller = new AbortController();
        const active = controller;
        timeout = setTimeout(() => active.abort(), 15_000);
        const raw = await request<unknown>(
          `/api/live-cameras/${encodeURIComponent(cameraId)}/detect-frame`,
          {
            method: "POST",
            headers: { "Content-Type": "image/jpeg" },
            body: captured.blob,
            signal: active.signal,
          },
        );
        if (disposed || active.signal.aborted) return;
        const result = readImageDetections(raw, captured.hash);
        if (!result) {
          delay = 5000;
          setMessage(
            "Local YOLO is unavailable for this frame. No substitute boxes are shown.",
          );
          return;
        }
        setFrame({
          cameraId,
          image: captured.image,
          mediaTime: captured.mediaTime,
          sampledAt: captured.sampledAt,
          detections: result,
        });
        setCount((current) => current + 1);
        setMessage("");
      } catch {
        if (!disposed) {
          setMessage(
            "Local frame analysis interrupted. The last analyzed frame stays labeled below.",
          );
          delay = 5000;
        }
      } finally {
        if (timeout) clearTimeout(timeout);
        if (!disposed) timer = setTimeout(sample, delay);
      }
    };
    timer = setTimeout(sample, 1000);
    return () => {
      disposed = true;
      if (timer) clearTimeout(timer);
      if (timeout) clearTimeout(timeout);
      controller?.abort();
    };
  }, [videoRef, cameraId, enabled]);
  return { frame: frame?.cameraId === cameraId ? frame : null, message, count };
}

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
  const { frame, message, count } = useLiveFrameDetection(
    video,
    camera.id,
    sampling,
  );
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
        <span>Local YOLO · at most 1 frame/s</span>
        <button
          onClick={() => setYoloEnabled((value) => !value)}
          aria-pressed={yoloEnabled}
        >
          {yoloEnabled ? "Pause YOLO" : "Enable YOLO"}
        </button>
      </div>
      {frame ? (
        <div className="live-analyzed-frame">
          <div className="live-analysis-heading">
            <span>Exact analyzed frame</span>
            <span>{count} analyzed</span>
          </div>
          <div className="live-snapshot-frame">
            <img
              src={frame.image}
              alt={`Exact ${camera.name} video frame analyzed by local YOLO`}
            />
            <LiveImageBoxes detections={frame.detections} />
          </div>
          <LiveDetectionCounts detections={frame.detections} />
          <p className="live-camera-disclosure">
            Video time {frame.mediaTime.toFixed(2)}s · sampled in this browser
            at {new Date(frame.sampledAt).toLocaleTimeString()}. Boxes belong to
            this frame, not the moving video. Object detections do not establish
            danger.
          </p>
        </div>
      ) : (
        <p className="live-camera-disclosure">
          {yoloEnabled
            ? "The exact sampled frame and its boxes will appear here when local analysis completes."
            : "Local YOLO sampling paused."}
        </p>
      )}
      {message && (
        <p className="live-snapshot-notice" role="status">
          {message}
        </p>
      )}
    </div>
  );
}
