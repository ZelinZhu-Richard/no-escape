import type { RoadSpeedCalibration } from "./liveSpeed";

export const TVA43_CAMERA_ID = "caltrans-d4-285";
// Hand-aligned to the 720×480 provider view inspected on 2026-11-08 UTC.
// This is an APPROXIMATE demo scale, not a surveyed camera calibration.
// The near right-hand carriageway is treated as a plane: three assumed 12ft
// lanes and about three assumed 40ft dash+gap cycles. Do not extrapolate beyond
// this polygon or transfer the preset to another camera angle.
export const TVA43_CALIBRATION: RoadSpeedCalibration = {
  cameraId: TVA43_CAMERA_ID,
  revision: "tva43-assumed-road-plane-20261108-v1",
  imageQuad: [[413 / 720, 300 / 480], [503 / 720, 300 / 480],
    [470 / 720, 465 / 480], [248 / 720, 465 / 480]],
  worldQuad: [[0, 0], [10.9728, 0], [10.9728, 36.576], [0, 36.576]],
  basis: "assumed",
  description: "Assumed 36 ft road width and 120 ft length; manually aligned, not surveyed.",
  imageAspectRatio: 1.5,
};

export const TVA43_MARKING_SOURCE = "https://dot.ca.gov/-/media/dot-media/programs/safety-programs/documents/ca-mutcd/2026/camutcd-2026-3a.pdf";
