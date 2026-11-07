import { useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { request } from "./api";
import type {
  DetectionBox,
  DetectionFrame,
  DetectionResult,
  DetectionUnavailable,
} from "./types";

export function frameAtTime(
  data: DetectionResult,
  time: number,
): DetectionFrame | null {
  if (!Number.isFinite(time) || time < 0 || data.sample_fps <= 0) return null;
  // Hold the last sampled frame for one sampling interval. Never borrow a future
  // box or bridge a missing sample: this is replayed detection, not tracking.
  let low = 0;
  let high = data.frames.length - 1;
  let found = -1;
  while (low <= high) {
    const middle = (low + high) >> 1;
    if (data.frames[middle].time_seconds <= time + 0.001) {
      found = middle;
      low = middle + 1;
    } else high = middle - 1;
  }
  if (found < 0) return null;
  const frame = data.frames[found];
  return time - frame.time_seconds <= 1 / data.sample_fps + 0.035
    ? frame
    : null;
}

export function containRect(
  width: number,
  height: number,
  videoWidth: number,
  videoHeight: number,
) {
  if (width <= 0 || height <= 0 || videoWidth <= 0 || videoHeight <= 0)
    return { left: 0, top: 0, width: 0, height: 0 };
  const scale = Math.min(width / videoWidth, height / videoHeight);
  const contentWidth = videoWidth * scale;
  const contentHeight = videoHeight * scale;
  return {
    left: (width - contentWidth) / 2,
    top: (height - contentHeight) / 2,
    width: contentWidth,
    height: contentHeight,
  };
}

const validBox = (box: DetectionBox) =>
  typeof box.class_name === "string" &&
  Number.isFinite(box.confidence) &&
  box.confidence >= 0 &&
  box.confidence <= 1 &&
  Array.isArray(box.xyxy) &&
  box.xyxy.length === 4 &&
  box.xyxy.every((n) => Number.isFinite(n) && n >= 0 && n <= 1) &&
  box.xyxy[2] > box.xyxy[0] &&
  box.xyxy[3] > box.xyxy[1];

export function DetectionOverlay({
  sourceId,
  videoRef,
  replayKey,
}: {
  sourceId: string;
  videoRef: RefObject<HTMLVideoElement | null>;
  replayKey?: string;
}) {
  const [data, setData] = useState<DetectionResult | null>(null);
  const [message, setMessage] = useState("Loading saved detections…");
  const [time, setTime] = useState(0);
  const [visible, setVisible] = useState(true);
  const [showLabels, setShowLabels] = useState(sourceId !== "traffic-jam");
  const [rect, setRect] = useState({ left: 0, top: 0, width: 0, height: 0 });
  const sampleTime = useRef(-1);

  useEffect(() => {
    setShowLabels(sourceId !== "traffic-jam");
  }, [sourceId]);

  useEffect(() => {
    const controller = new AbortController();
    setData(null);
    setMessage("Loading saved detections…");
    request<DetectionResult | DetectionUnavailable>(
      `/api/sources/${encodeURIComponent(sourceId)}/detections`,
      { signal: controller.signal },
    )
      .then((result) => {
        if (controller.signal.aborted) return;
        if (result.status !== "available" || result.source_id !== sourceId) {
          setMessage(
            result.status === "unavailable" && result.message
              ? result.message
              : "YOLO detections unavailable for this source.",
          );
          return;
        }
        if (
          result.provenance?.fixture !== false ||
          result.provenance?.kind !== "local_yolo_cached" ||
          !Array.isArray(result.frames) ||
          !Number.isFinite(result.sample_fps) ||
          result.sample_fps <= 0
        ) {
          setMessage("Verified YOLO detections unavailable for this source.");
          return;
        }
        setData(result);
        setMessage("");
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setMessage(
            "YOLO detections unavailable. The source video still plays.",
          );
      });
    return () => controller.abort();
  }, [sourceId]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    let frameHandle = 0;
    let animationHandle = 0;
    let disposed = false;
    const updateTime = (mediaTime = video.currentTime) => {
      // Render only at the detector sample rate; transport/control events still
      // update immediately on seek, pause, reset, and source replacement.
      const bucket = Math.floor(mediaTime * (data?.sample_fps ?? 4));
      if (sampleTime.current !== bucket || video.paused) {
        sampleTime.current = bucket;
        setTime(mediaTime);
      }
    };
    const measure = () => {
      const element = video.getBoundingClientRect();
      const parent = video.offsetParent?.getBoundingClientRect();
      const fit = containRect(
        element.width,
        element.height,
        video.videoWidth || data?.video_width || 16,
        video.videoHeight || data?.video_height || 9,
      );
      setRect({
        ...fit,
        left: fit.left + element.left - (parent?.left ?? element.left),
        top: fit.top + element.top - (parent?.top ?? element.top),
      });
    };
    const refresh = () => {
      updateTime();
      measure();
    };
    const nextVideoFrame = (
      _now: number,
      metadata: VideoFrameCallbackMetadata,
    ) => {
      if (disposed) return;
      updateTime(metadata.mediaTime);
      frameHandle = video.requestVideoFrameCallback(nextVideoFrame);
    };
    const nextAnimation = () => {
      if (disposed) return;
      if (!video.paused) updateTime();
      animationHandle = requestAnimationFrame(nextAnimation);
    };
    if ("requestVideoFrameCallback" in video)
      frameHandle = video.requestVideoFrameCallback(nextVideoFrame);
    else animationHandle = requestAnimationFrame(nextAnimation);
    const observer =
      typeof ResizeObserver !== "undefined"
        ? new ResizeObserver(measure)
        : null;
    observer?.observe(video);
    [
      "loadedmetadata",
      "timeupdate",
      "seeking",
      "seeked",
      "pause",
      "play",
      "emptied",
    ].forEach((event) => video.addEventListener(event, refresh));
    window.addEventListener("resize", measure);
    sampleTime.current = -1;
    refresh();
    return () => {
      disposed = true;
      if (frameHandle) video.cancelVideoFrameCallback(frameHandle);
      if (animationHandle) cancelAnimationFrame(animationHandle);
      observer?.disconnect();
      [
        "loadedmetadata",
        "timeupdate",
        "seeking",
        "seeked",
        "pause",
        "play",
        "emptied",
      ].forEach((event) => video.removeEventListener(event, refresh));
      window.removeEventListener("resize", measure);
    };
  }, [videoRef, replayKey, data]);

  const frame = data ? frameAtTime(data, time) : null;
  const boxes = frame?.boxes.filter(validBox) ?? [];
  const gate = data?.gate;
  return (
    <>
      {data && visible && rect.width > 0 && (
        <svg
          className="detection-overlay"
          style={rect}
          viewBox={`0 0 ${rect.width} ${rect.height}`}
          aria-hidden="true"
          data-testid="detection-overlay"
        >
          {boxes.map((box, index) => {
            const x = box.xyxy[0] * rect.width;
            const y = box.xyxy[1] * rect.height;
            const width = (box.xyxy[2] - box.xyxy[0]) * rect.width;
            const height = (box.xyxy[3] - box.xyxy[1]) * rect.height;
            const label = `${box.class_name} ${Math.round(box.confidence * 100)}%`;
            const labelWidth = Math.min(rect.width, label.length * 5.6 + 10);
            const labelX = Math.max(0, Math.min(x, rect.width - labelWidth));
            const labelY = y >= 19 ? y - 19 : y + Math.min(height, 3);
            return (
              <g
                key={`${index}-${box.class_name}`}
                className={
                  box.class_name === "person"
                    ? "detection-person"
                    : "detection-vehicle"
                }
              >
                <rect
                  x={x}
                  y={y}
                  width={width}
                  height={height}
                  className="detection-box"
                />
                {showLabels && <><rect
                  x={labelX}
                  y={labelY}
                  width={labelWidth}
                  height="17"
                  className="detection-label-bg"
                  rx="2"
                />
                <text
                  x={labelX + 5}
                  y={labelY + 12}
                  className="detection-label"
                >
                  {label}
                </text></>}
              </g>
            );
          })}
        </svg>
      )}
      <div className="detection-panel" data-testid="detection-panel">
        <div className="detection-heading">
          <span>
            <i className={`tiny-dot ${data ? "" : "unavailable"}`} />
            YOLO · {data ? "saved detections" : "unavailable"}
          </span>
          <div className="detection-controls"><button
            className="detection-toggle"
            onClick={() => setVisible((value) => !value)}
            disabled={!data}
            aria-pressed={visible && Boolean(data)}
          >
            {visible ? "Hide boxes" : "Show boxes"}
          </button>
          <button
            className="detection-toggle"
            onClick={() => setShowLabels((value) => !value)}
            disabled={!data || !visible}
            aria-pressed={showLabels}
          >
            {showLabels ? "Hide labels" : "Show labels"}
          </button></div>
        </div>
        {data ? (
          <>
            <div className="detection-live-counts">
              <span>
                <strong>{frame?.vehicle_count ?? "—"}</strong> vehicles
              </span>
              <span>
                <strong>{frame?.person_count ?? "—"}</strong> people
              </span>
              <span className="mono">
                {frame
                  ? `${frame.time_seconds.toFixed(2)}s sample`
                  : "No sample at this time"}
              </span>
            </div>
            <div className="gate-metric">
              <span>
                Model calls saved by YOLO <small>replay estimate</small>
              </span>
              <strong data-testid="gate-savings">
                {gate?.estimated_calls_avoided ?? "—"}
                <span> / {gate?.evaluated_windows ?? "—"}</span>
              </strong>
            </div>
            <p className="detection-note">
              Whole clip · {gate?.baseline ?? "baseline unavailable"}. Shadow
              gate; no paid calls skipped. {data.model.name} · {data.sample_fps}{" "}
              samples/s. Boxes indicate object detections, not danger.
            </p>
          </>
        ) : (
          <p className="detection-note">{message}</p>
        )}
      </div>
    </>
  );
}
