import { useEffect, useState } from "react";
import type { ImageDetections, LiveSnapshot } from "./liveCameras";

export async function jpegHash(dataUrl: string): Promise<string> {
  if (!/^data:image\/jpeg;base64,/.test(dataUrl) || dataUrl.length > 1_500_000)
    throw new Error("Unsupported image.");
  const binary = atob(dataUrl.slice(dataUrl.indexOf(",") + 1));
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}

export function useVerifiedSnapshotDetections(snapshot: LiveSnapshot | null) {
  const [verified, setVerified] = useState<{
    image: string;
    detections: ImageDetections;
  } | null>(null);
  useEffect(() => {
    let active = true;
    setVerified(null);
    if (
      !snapshot?.image_data_url ||
      !snapshot.image_sha256 ||
      !snapshot.detections
    )
      return;
    const current = snapshot;
    void jpegHash(current.image_data_url!)
      .then((hash) => {
        if (
          active &&
          hash === current.image_sha256 &&
          hash === current.detections!.image_sha256
        )
          setVerified({
            image: current.image_data_url!,
            detections: current.detections!,
          });
      })
      .catch(() => {
        /* Hash validation failure never creates replacement boxes. */
      });
    return () => {
      active = false;
    };
  }, [snapshot]);
  return verified?.image === snapshot?.image_data_url
    ? (verified?.detections ?? null)
    : null;
}

export function LiveImageBoxes({
  detections,
  labels = true,
  speeds,
}: {
  detections: ImageDetections;
  labels?: boolean;
  speeds?: Record<string, { mph: number | null; reason: string }>;
}) {
  const width = detections.image_width,
    height = detections.image_height;
  // Scale with the image so the same label remains legible in either player
  // size, without the old labels covering an entire neighboring vehicle.
  const font = Math.min(width / 60, height / 12);
  const hasSpeed = (id?: string) => {
    const mph = id ? speeds?.[id]?.mph : undefined;
    return typeof mph === "number" && Number.isFinite(mph) && mph >= 0;
  };
  // Paint numeric estimates last so neighboring unknown labels cannot cover
  // the mph text in dense traffic. Preserve fallback keys when reordering.
  const orderedBoxes = detections.boxes.map((box, index) => ({
    box, index, priority: box.class_name !== "person" && hasSpeed(box.track_id),
  }));
  if (speeds) orderedBoxes.sort((a, b) => Number(a.priority) - Number(b.priority));
  return (
    <svg
      className="live-image-boxes"
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
      data-testid="live-yolo-boxes"
    >
      {detections.excluded_regions?.map((region) => {
        const [x1, y1, x2, y2] = region.xyxy;
        return (
          <rect
            key={region.id}
            className="live-excluded-region"
            x={x1 * width}
            y={y1 * height}
            width={(x2 - x1) * width}
            height={(y2 - y1) * height}
          />
        );
      })}
      {orderedBoxes.map(({ box, index }) => {
        const [x1, y1, x2, y2] = box.xyxy;
        const identity = `${box.class_name}${box.track_id ? ` #${box.track_id.split("-").at(-1)}` : ""}`;
        const confidence = Math.round(box.confidence * 100);
        const speed = box.track_id ? speeds?.[box.track_id] : undefined;
        const showSpeed = speeds !== undefined && box.class_name !== "person";
        const validSpeed = typeof speed?.mph === "number" &&
          Number.isFinite(speed.mph) && speed.mph >= 0;
        // Keep dense-road overlays small. Full identity and the distinction
        // between detector confidence and speed stay in the title/captions.
        const lines = [showSpeed && !validSpeed ? `${confidence}% · —` : `${confidence}%`];
        if (showSpeed && validSpeed)
          lines.push(`est ${Math.round(speed!.mph!)} mph`);
        const title = `${identity}; detector confidence ${confidence}%${showSpeed
          ? validSpeed
            ? `; estimated speed ${Math.round(speed!.mph!)} mph`
            : `; speed unavailable${speed?.reason ? `: ${speed.reason}` : ""}`
          : ""}`;
        const labelWidth = Math.min(
          width,
          Math.max(...lines.map((line) => line.length)) * font * 0.62 + font * 0.8,
        );
        const labelHeight = font * (lines.length * 1.2 + 0.4);
        const gap = font * 0.4;
        const right = x2 * width + gap;
        const side = right + labelWidth <= width
          ? right
          : x1 * width - labelWidth - gap;
        const x = Math.max(0, Math.min(width - labelWidth, side));
        const y = Math.max(0, Math.min(height - labelHeight, y1 * height));
        return (
          <g
            key={box.track_id ?? index}
            data-track-id={box.track_id}
            data-observation={box.observation}
            className={
              box.class_name === "person"
                ? "detection-person"
                : "detection-vehicle"
            }
          >
            <title>{title}</title>
            <rect
              x={x1 * width}
              y={y1 * height}
              width={(x2 - x1) * width}
              height={(y2 - y1) * height}
              className="detection-box"
            />
            {labels && (
              <>
                <rect
                  x={x}
                  y={y}
                  width={labelWidth}
                  height={labelHeight}
                  className="detection-label-bg"
                />
                {lines.map((line, lineIndex) => (
                  <text
                    key={lineIndex}
                    x={x + font * 0.4}
                    y={y + font * (1.1 + lineIndex * 1.2)}
                    fill="currentColor"
                    fontSize={font}
                    fontFamily="monospace"
                  >
                    {line}
                  </text>
                ))}
              </>
            )}
          </g>
        );
      })}
    </svg>
  );
}

export function LiveDetectionCounts({
  detections,
}: {
  detections: ImageDetections;
}) {
  return (
    <div className="live-yolo-counts">
      <span>
        <b>{detections.vehicle_count}</b> vehicles
      </span>
      <span>
        <b>{detections.person_count}</b> people
      </span>
      <span>
        {detections.model.name} ·{" "}
        {detections.analysis_mode === "cached" ? "cached" : "local inference"}
        {detections.inference_ms === null
          ? ""
          : ` · ${Math.round(detections.inference_ms)} ms`}
      </span>
      {detections.model.selection === "camera_override" && (
        <span>Camera-specific model</span>
      )}
      {!!detections.excluded_regions?.length && (
        <span>Camera text regions excluded</span>
      )}
    </div>
  );
}
