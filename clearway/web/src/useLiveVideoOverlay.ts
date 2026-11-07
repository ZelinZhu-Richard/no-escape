import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { request } from "./api";
import { jpegHash } from "./LiveImageDetections";
import { readImageDetections, readLiveAlertMonitor } from "./liveCameras";
import type { ImageDetections, LiveAlertMonitor } from "./liveCameras";
import { projectLiveFrame, trackLiveFrame } from "./liveOverlayTracking";
import type { LiveTrackedFrame } from "./liveOverlayTracking";
import { readLiveTracking } from "./liveTracking";
import type { LiveTracking } from "./liveTracking";

const SAMPLE_INTERVAL_MS = 140;

export async function captureLocalFrame(
  video: HTMLVideoElement,
  presentedMediaTime = video.currentTime,
) {
  if (video.readyState < 2 || video.videoWidth < 1 || video.videoHeight < 1)
    throw new Error("No decoded video frame.");
  const scale = Math.min(1, 640 / video.videoWidth, 480 / video.videoHeight);
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(video.videoWidth * scale));
  canvas.height = Math.max(1, Math.round(video.videoHeight * scale));
  const context = canvas.getContext("2d");
  if (!context) throw new Error("Frame sampling unavailable.");
  const capturedAtMs = performance.now();
  // drawImage happens synchronously inside the presented-frame callback. The
  // detector result must match these exact JPEG bytes before it can be used.
  context.drawImage(video, 0, 0, canvas.width, canvas.height);
  const image = canvas.toDataURL("image/jpeg", 0.8);
  const hash = await jpegHash(image);
  const bytes = Uint8Array.from(atob(image.split(",")[1]), (character) =>
    character.charCodeAt(0),
  );
  if (bytes.length > 1_000_000)
    throw new Error("Frame exceeds the local limit.");
  return {
    hash,
    blob: new Blob([bytes], { type: "image/jpeg" }),
    mediaTime: presentedMediaTime,
    capturedAtMs,
  };
}

interface OverlayView {
  cameraId: string;
  detections: ImageDetections | null;
  updatesPerSecond: number;
  phase: "waiting" | "running" | "empty" | "delayed" | "unavailable";
  message: string;
  mediaTime: number | null;
  mediaAgeMs: number | null;
  wallAgeMs: number | null;
  alertMonitor: LiveAlertMonitor | null;
  alertVersion: number;
  tracking: LiveTracking | null;
}
const initialView = (cameraId: string): OverlayView => ({
  cameraId,
  detections: null,
  updatesPerSecond: 0,
  phase: "waiting",
  message: "",
  mediaTime: null,
  mediaAgeMs: null,
  wallAgeMs: null,
  alertMonitor: null,
  alertVersion: -1,
  tracking: null,
});

export function useLiveVideoOverlay(
  videoRef: RefObject<HTMLVideoElement | null>,
  cameraId: string,
  enabled: boolean,
  runId?: string,
  alertsEnabled = true,
) {
  const [view, setView] = useState<OverlayView>(() => initialView(cameraId));
  const alertSettings = useRef({
    enabled: alertsEnabled,
    version: 0,
    pendingPause: !alertsEnabled,
  });
  if (alertSettings.current.enabled !== alertsEnabled) {
    alertSettings.current = {
      enabled: alertsEnabled,
      version: alertSettings.current.version + 1,
      pendingPause: alertSettings.current.pendingPause || !alertsEnabled,
    };
  }
  useEffect(() => {
    const video = videoRef.current;
    setView(initialView(cameraId));
    if (!video || !enabled) return;
    let disposed = false;
    let epoch = 0;
    let inFlight = false;
    let samplingUnavailable = false;
    let controller: AbortController | undefined;
    let requestTimeout: ReturnType<typeof setTimeout> | undefined;
    let frameHandle = 0;
    let animationHandle = 0;
    let tracked: LiveTrackedFrame | null = null;
    let details: ImageDetections | null = null;
    let trackingDetails: LiveTracking | null = null;
    let mediaTime = video.currentTime;
    let lastPresentedTime: number | null = null;
    let lastSampledMediaTime: number | null = null;
    let lastAttemptAt = -Infinity;
    let retryAt = 0;
    let updates: number[] = [];
    let lastStatsAt = -Infinity;
    let lastViewKey = "";
    let message = "";
    let alertMonitor: LiveAlertMonitor | null = null;
    let alertMonitorVersion = alertSettings.current.version;
    let streamId = runId ? crypto.randomUUID() : "";
    const nativeFrames = typeof video.requestVideoFrameCallback === "function";

    const reset = () => {
      ++epoch;
      tracked = null;
      details = null;
      trackingDetails = null;
      alertMonitor = null;
      streamId = runId ? crypto.randomUUID() : "";
      lastPresentedTime = null;
      lastSampledMediaTime = null;
      controller?.abort();
      if (requestTimeout) clearTimeout(requestTimeout);
      inFlight = false;
      updates = [];
      message = "";
      lastViewKey = "";
      setView(initialView(cameraId));
    };
    const publish = (now: number) => {
      if (disposed) return;
      if (
        video.paused ||
        video.seeking ||
        video.readyState < 2 ||
        document.visibilityState === "hidden"
      ) {
        if (lastViewKey !== "paused") {
          lastViewKey = "paused";
          setView(initialView(cameraId));
        }
        return;
      }
      const projection = projectLiveFrame(tracked, mediaTime, now);
      if (
        projection.reason === "stale" ||
        projection.reason === "discontinuity"
      ) {
        tracked = null;
        details = null;
        message = "Local YOLO delayed · old boxes are hidden.";
      }
      updates = updates.filter((time) => now - time <= 2000);
      const phase: OverlayView["phase"] = samplingUnavailable
        ? "unavailable"
        : !tracked && message
          ? "delayed"
          : projection.reason === "stale" ||
              projection.reason === "discontinuity"
            ? "delayed"
            : projection.reason === "empty"
              ? "empty"
              : projection.reason === "fresh" ||
                  projection.reason === "projected"
                ? "running"
                : "waiting";
      const fresh =
        details && ["fresh", "projected", "empty"].includes(projection.reason);
      const key = `${phase}:${Math.round(mediaTime * 60)}:${details?.image_sha256 ?? ""}:${updates.length}:${message}`;
      // Draw with the displayed media clock. A wall-clock watchdog still clears
      // boxes if video-frame callbacks stall without a browser waiting event.
      if (key === lastViewKey && now - lastStatsAt < 250) return;
      lastViewKey = key;
      lastStatsAt = now;
      setView({
        cameraId,
        detections: fresh ? { ...details!, boxes: projection.boxes } : null,
        updatesPerSecond: updates.length / 2,
        phase,
        message,
        mediaTime,
        mediaAgeMs: projection.mediaAgeMs,
        wallAgeMs: projection.wallAgeMs,
        alertMonitor:
          alertSettings.current.enabled &&
          alertMonitorVersion === alertSettings.current.version
            ? alertMonitor
            : null,
        alertVersion: alertMonitorVersion,
        tracking: fresh ? trackingDetails : null,
      });
    };

    const sample = async (presentedTime: number, now: number) => {
      if (
        disposed ||
        inFlight ||
        samplingUnavailable ||
        now < retryAt ||
        now - lastAttemptAt < SAMPLE_INTERVAL_MS ||
        presentedTime === lastSampledMediaTime ||
        video.paused ||
        video.seeking ||
        video.readyState < 2 ||
        document.visibilityState === "hidden"
      )
        return;
      inFlight = true;
      lastAttemptAt = now;
      lastSampledMediaTime = presentedTime;
      const generation = epoch;
      try {
        let captured: Awaited<ReturnType<typeof captureLocalFrame>>;
        try {
          captured = await captureLocalFrame(video, presentedTime);
        } catch {
          if (!disposed && generation === epoch) {
            samplingUnavailable = true;
            tracked = null;
            details = null;
            message =
              "This browser cannot sample the video. Snapshot YOLO is still available.";
          }
          return;
        }
        if (disposed || generation !== epoch) return;
        controller = new AbortController();
        const active = controller;
        requestTimeout = setTimeout(() => active.abort(), 750);
        const requestedAlertVersion = alertSettings.current.version;
        const monitorActive =
          alertSettings.current.enabled && !alertSettings.current.pendingPause;
        // Even a rapid pause/resume sends one pause, resetting alert continuity
        // without resetting the independent ByteTrack stream session.
        const raw = await request<unknown>(
          `/api/live-cameras/${encodeURIComponent(cameraId)}/detect-frame`,
          {
            method: "POST",
            headers: {
              "Content-Type": "image/jpeg",
              ...(runId
                ? {
                    "X-Clearway-Run-ID": runId,
                    "X-Clearway-Stream-ID": streamId,
                    "X-Clearway-Media-Time": String(captured.mediaTime),
                    ...(!monitorActive
                      ? { "X-Clearway-Alert-Monitor": "paused" }
                      : {}),
                  }
                : {}),
            },
            body: captured.blob,
            signal: active.signal,
          },
        );
        if (disposed || generation !== epoch || active.signal.aborted) return;
        if (
          runId &&
          !monitorActive &&
          requestedAlertVersion === alertSettings.current.version
        )
          alertSettings.current.pendingPause = false;
        const receivedAtMs = performance.now();
        const result = readImageDetections(raw, captured.hash);
        if (!result) {
          alertMonitor = null;
          tracked = null;
          details = null;
          const response =
            raw && typeof raw === "object"
              ? (raw as Record<string, unknown>)
              : {};
          const retrySeconds =
            typeof response.retry_after_seconds === "number" &&
            Number.isFinite(response.retry_after_seconds)
              ? Math.max(0.5, Math.min(30, response.retry_after_seconds))
              : 0.5;
          retryAt = receivedAtMs + retrySeconds * 1000;
          message = "Local YOLO delayed · old boxes are hidden.";
          return;
        }
        const mediaAge = mediaTime - captured.mediaTime;
        if (
          mediaAge < -0.02 ||
          mediaAge > 0.35 ||
          receivedAtMs - captured.capturedAtMs > 500
        ) {
          tracked = null;
          details = null;
          alertMonitor = null;
          message = "Local YOLO delayed · old boxes are hidden.";
          return;
        }
        trackingDetails = runId
          ? readLiveTracking((raw as Record<string, unknown>).tracking, {
              imageHash: captured.hash,
              configurationHash: result.provenance.configuration_sha256,
              cameraId,
              runId,
              streamId,
              mediaTime: captured.mediaTime,
            })
          : null;
        tracked = trackLiveFrame(tracked, {
          sourceId: `${cameraId}:${result.provenance.configuration_sha256 ?? "raw"}`,
          mediaTime: captured.mediaTime,
          capturedAtMs: captured.capturedAtMs,
          receivedAtMs,
          boxes: trackingDetails?.tracks ?? result.boxes,
        });
        details = tracked ? result : null;
        alertMonitorVersion = requestedAlertVersion;
        alertMonitor =
          runId && monitorActive
            ? readLiveAlertMonitor(
                (raw as Record<string, unknown>).alert_monitor,
              )
            : null;
        updates.push(receivedAtMs);
        message = "";
      } catch {
        if (!disposed && generation === epoch) {
          tracked = null;
          details = null;
          alertMonitor = null;
          retryAt = performance.now() + 500;
          message = "Local YOLO delayed · old boxes are hidden.";
        }
      } finally {
        if (!disposed && generation === epoch) {
          if (requestTimeout) clearTimeout(requestTimeout);
          inFlight = false;
          publish(performance.now());
        }
      }
    };
    const presented = (time: number, now: number) => {
      if (
        lastPresentedTime !== null &&
        (time < lastPresentedTime - 0.02 || time - lastPresentedTime > 0.5)
      )
        reset();
      mediaTime = time;
      lastPresentedTime = time;
      void sample(time, now);
    };
    const nextFrame = (_now: number, metadata: VideoFrameCallbackMetadata) => {
      if (disposed) return;
      presented(metadata.mediaTime, performance.now());
      frameHandle = video.requestVideoFrameCallback(nextFrame);
    };
    const animate = () => {
      if (disposed) return;
      const now = performance.now();
      if (!nativeFrames) presented(video.currentTime, now);
      publish(now);
      animationHandle = requestAnimationFrame(animate);
    };
    const events = [
      "seeking",
      "pause",
      "waiting",
      "stalled",
      "emptied",
      "resize",
    ];
    events.forEach((event) => video.addEventListener(event, reset));
    if (nativeFrames) frameHandle = video.requestVideoFrameCallback(nextFrame);
    animationHandle = requestAnimationFrame(animate);
    return () => {
      disposed = true;
      ++epoch;
      controller?.abort();
      if (requestTimeout) clearTimeout(requestTimeout);
      if (frameHandle) video.cancelVideoFrameCallback(frameHandle);
      cancelAnimationFrame(animationHandle);
      events.forEach((event) => video.removeEventListener(event, reset));
    };
  }, [videoRef, cameraId, enabled, runId]);
  return enabled && view.cameraId === cameraId
    ? {
        ...view,
        alertMonitor:
          alertsEnabled && view.alertVersion === alertSettings.current.version
            ? view.alertMonitor
            : null,
      }
    : initialView(cameraId);
}
