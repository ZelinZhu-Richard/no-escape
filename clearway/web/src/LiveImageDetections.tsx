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
}: {
  detections: ImageDetections;
  labels?: boolean;
}) {
  const width = detections.image_width,
    height = detections.image_height;
  const font = width / 30;
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
        return <rect key={region.id} className="live-excluded-region"
          x={x1 * width} y={y1 * height} width={(x2 - x1) * width}
          height={(y2 - y1) * height} />;
      })}
      {detections.boxes.map((box, index) => {
        const [x1, y1, x2, y2] = box.xyxy;
        const label = `${box.class_name} ${Math.round(box.confidence * 100)}%`;
        const labelWidth = Math.min(
          width,
          label.length * font * 0.56 + font * 0.6,
        );
        const x = Math.max(0, Math.min(width - labelWidth, x1 * width));
        const y =
          y1 * height >= font * 1.5 ? y1 * height - font * 1.5 : y1 * height;
        return (
          <g
            key={index}
            className={
              box.class_name === "person"
                ? "detection-person"
                : "detection-vehicle"
            }
          >
            <rect
              x={x1 * width}
              y={y1 * height}
              width={(x2 - x1) * width}
              height={(y2 - y1) * height}
              className="detection-box"
            />
            {labels && <><rect
              x={x}
              y={y}
              width={labelWidth}
              height={font * 1.4}
              className="detection-label-bg"
            />
            <text
              x={x + font * 0.3}
              y={y + font}
              fill="currentColor"
              fontSize={font}
              fontFamily="monospace"
            >
              {label}
            </text></>}
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
      {!!detections.excluded_regions?.length && <span>Camera text regions excluded</span>}
    </div>
  );
}
