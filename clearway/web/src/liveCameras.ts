export interface LiveCamera {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  region_id: string;
  region_name: string;
  roadway: string;
  direction: string;
  provider: string;
  provider_url: string | null;
  mode: "refreshed_snapshot";
  in_service_reported: boolean;
  capture_time: string | null;
  source_refresh_seconds: number;
  streaming_url?: string | null;
}

export interface LiveCameraCatalog {
  status: "available" | "unavailable";
  provider: string;
  mode: "live_snapshot_catalog";
  fetched_at: string | null;
  stale: boolean;
  refresh_interval_seconds: number;
  regions: { id: string; name: string }[];
  cameras: LiveCamera[];
}

export interface LiveSnapshot {
  status: "available" | "unavailable" | "throttled";
  camera_id: string;
  mode: "refreshed_snapshot";
  image_data_url: string | null;
  fetched_at: string | null;
  source_last_modified: string | null;
  capture_time: string | null;
  stale: boolean;
  refresh_after_seconds: number;
  message: string;
  image_sha256?: string | null;
  detections?: ImageDetections | null;
}

export interface ImageDetections {
  status: "available";
  analysis_mode: "fresh" | "cached";
  image_sha256: string;
  image_width: number;
  image_height: number;
  boxes: {
    class_name: string;
    confidence: number;
    xyxy: [number, number, number, number];
  }[];
  vehicle_count: number;
  person_count: number;
  model: { name: string; version: string };
  provenance: {
    kind: "local_yolo_image";
    fixture: false;
    image_sha256: string;
    analyzed_at: string;
  };
  inference_ms: number | null;
  excluded_regions?: { id: string; xyxy: [number, number, number, number] }[];
}
export const isImageHash = (value: unknown): value is string =>
  typeof value === "string" && /^[a-f0-9]{64}$/.test(value);

const record = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
const safeText = (value: unknown, fallback = "") =>
  typeof value === "string" ? value.slice(0, 500) : fallback;
const safeDate = (value: unknown) =>
  typeof value === "string" && Number.isFinite(Date.parse(value))
    ? value
    : null;
const validId = (value: unknown): value is string =>
  typeof value === "string" && /^[a-zA-Z0-9_-]{1,120}$/.test(value);
const interval = (value: unknown, fallback = 300) =>
  typeof value === "number" && Number.isFinite(value)
    ? Math.min(3600, Math.max(30, value))
    : fallback;
function httpsLink(value: unknown): string | null {
  if (typeof value !== "string") return null;
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}

export function publicStreamUrl(value: unknown): string | null {
  const link = httpsLink(value);
  if (!link) return null;
  const url = new URL(link);
  return url.hostname === "wzmedia.dot.ca.gov" &&
    !url.port &&
    !url.search &&
    !url.hash &&
    /^\/D4\/[A-Za-z0-9_.-]+\/playlist\.m3u8$/.test(url.pathname)
    ? link
    : null;
}

export function readImageDetections(
  value: unknown,
  imageHash: string | null,
): ImageDetections | null {
  const raw = record(value);
  const provenance = record(raw?.provenance);
  const model = record(raw?.model);
  if (
    !raw ||
    !isImageHash(imageHash) ||
    raw.status !== "available" ||
    !["fresh", "cached"].includes(String(raw.analysis_mode)) ||
    raw.image_sha256 !== imageHash ||
    provenance?.kind !== "local_yolo_image" ||
    provenance.fixture !== false ||
    provenance.image_sha256 !== imageHash ||
    !safeDate(provenance.analyzed_at) ||
    typeof raw.image_width !== "number" ||
    !Number.isInteger(raw.image_width) ||
    raw.image_width < 1 ||
    raw.image_width > 4096 ||
    typeof raw.image_height !== "number" ||
    !Number.isInteger(raw.image_height) ||
    raw.image_height < 1 ||
    raw.image_height > 4096 ||
    !Array.isArray(raw.boxes) ||
    raw.boxes.length > 500 ||
    !model ||
    typeof model.name !== "string"
  )
    return null;
  const boxes: ImageDetections["boxes"] = [];
  for (const item of raw.boxes) {
    const box = record(item);
    if (
      !box ||
      typeof box.class_name !== "string" ||
      typeof box.confidence !== "number" ||
      !Number.isFinite(box.confidence) ||
      box.confidence < 0 ||
      box.confidence > 1 ||
      !Array.isArray(box.xyxy) ||
      box.xyxy.length !== 4 ||
      !box.xyxy.every(
        (n) => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 1,
      ) ||
      box.xyxy[2] <= box.xyxy[0] ||
      box.xyxy[3] <= box.xyxy[1]
    )
      return null;
    boxes.push({
      class_name: box.class_name,
      confidence: box.confidence,
      xyxy: box.xyxy as [number, number, number, number],
    });
  }
  const count = (n: unknown) =>
    typeof n === "number" && Number.isInteger(n) && n >= 0 && n <= 500
      ? n
      : null;
  const vehicles = count(raw.vehicle_count),
    people = count(raw.person_count);
  if (vehicles === null || people === null) return null;
  const excludedRegions: NonNullable<ImageDetections["excluded_regions"]> = [];
  if (raw.excluded_regions !== undefined) {
    if (!Array.isArray(raw.excluded_regions) || raw.excluded_regions.length > 8)
      return null;
    for (const item of raw.excluded_regions) {
      const region = record(item);
      if (!region || !validId(region.id) || !Array.isArray(region.xyxy) ||
        region.xyxy.length !== 4 || !region.xyxy.every(
          n => typeof n === "number" && Number.isFinite(n) && n >= 0 && n <= 1,
        ) || region.xyxy[2] <= region.xyxy[0] || region.xyxy[3] <= region.xyxy[1])
        return null;
      excludedRegions.push({id: region.id, xyxy: region.xyxy as [number, number, number, number]});
    }
  }
  return {
    status: "available",
    analysis_mode: raw.analysis_mode as "fresh" | "cached",
    image_sha256: imageHash,
    image_width: raw.image_width,
    image_height: raw.image_height,
    boxes,
    excluded_regions: excludedRegions,
    vehicle_count: vehicles,
    person_count: people,
    model: { name: model.name, version: safeText(model.version) },
    provenance: {
      kind: "local_yolo_image",
      fixture: false,
      image_sha256: imageHash,
      analyzed_at: provenance.analyzed_at as string,
    },
    inference_ms:
      typeof raw.inference_ms === "number" &&
      Number.isFinite(raw.inference_ms) &&
      raw.inference_ms >= 0
        ? raw.inference_ms
        : null,
  };
}

/** Treat an inventory record as a public snapshot source, never as an incident. */
export function readLiveCameraCatalog(
  value: unknown,
): LiveCameraCatalog | null {
  const raw = record(value);
  if (
    !raw ||
    raw.mode !== "live_snapshot_catalog" ||
    !["available", "unavailable"].includes(String(raw.status)) ||
    !Array.isArray(raw.cameras) ||
    raw.cameras.length > 100 ||
    !Array.isArray(raw.regions)
  )
    return null;
  const cameras: LiveCamera[] = [];
  const ids = new Set<string>();
  if (raw.status === "available")
    for (const item of raw.cameras) {
      const camera = record(item);
      if (
        !camera ||
        !validId(camera.id) ||
        ids.has(camera.id) ||
        camera.mode !== "refreshed_snapshot" ||
        typeof camera.name !== "string" ||
        !camera.name.trim() ||
        typeof camera.latitude !== "number" ||
        !Number.isFinite(camera.latitude) ||
        Math.abs(camera.latitude) > 90 ||
        typeof camera.longitude !== "number" ||
        !Number.isFinite(camera.longitude) ||
        Math.abs(camera.longitude) > 180 ||
        !validId(camera.region_id)
      )
        continue;
      cameras.push({
        id: camera.id,
        name: safeText(camera.name),
        latitude: camera.latitude,
        longitude: camera.longitude,
        region_id: camera.region_id,
        region_name: safeText(camera.region_name, camera.region_id),
        roadway: safeText(camera.roadway),
        direction: safeText(camera.direction),
        provider: safeText(camera.provider, "Public provider"),
        provider_url: httpsLink(camera.provider_url),
        mode: "refreshed_snapshot",
        in_service_reported: camera.in_service_reported === true,
        capture_time: safeDate(camera.capture_time),
        source_refresh_seconds: interval(camera.source_refresh_seconds),
        streaming_url: publicStreamUrl(camera.streaming_url),
      });
      ids.add(camera.id);
    }
  const regions = new Map<string, string>();
  for (const camera of cameras)
    regions.set(camera.region_id, camera.region_name);
  return {
    status: raw.status as LiveCameraCatalog["status"],
    provider: safeText(raw.provider, "Public provider"),
    mode: "live_snapshot_catalog",
    fetched_at: safeDate(raw.fetched_at),
    stale: raw.stale !== false,
    refresh_interval_seconds: interval(raw.refresh_interval_seconds, 30),
    regions: [...regions].map(([id, name]) => ({ id, name })),
    cameras,
  };
}

/** Only the selected camera's bounded JPEG can become a preview. */
export function readLiveSnapshot(
  value: unknown,
  cameraId: string,
): LiveSnapshot | null {
  const raw = record(value);
  if (
    !raw ||
    raw.camera_id !== cameraId ||
    raw.mode !== "refreshed_snapshot" ||
    !["available", "unavailable", "throttled"].includes(String(raw.status))
  )
    return null;
  let image: string | null = null;
  if (
    typeof raw.image_data_url === "string" &&
    raw.image_data_url.length <= 1_500_000 &&
    /^data:image\/jpeg;base64,[A-Za-z0-9+/]+={0,2}$/.test(raw.image_data_url)
  )
    image = raw.image_data_url;
  if (raw.status === "available" && (!image || !safeDate(raw.fetched_at)))
    return null;
  return {
    status: raw.status as LiveSnapshot["status"],
    camera_id: cameraId,
    mode: "refreshed_snapshot",
    image_data_url: image,
    fetched_at: safeDate(raw.fetched_at),
    source_last_modified: safeDate(raw.source_last_modified),
    capture_time: safeDate(raw.capture_time),
    stale: raw.stale !== false,
    refresh_after_seconds: interval(raw.refresh_after_seconds),
    message: safeText(raw.message),
    image_sha256: isImageHash(raw.image_sha256) ? raw.image_sha256 : null,
    detections: readImageDetections(
      raw.detections,
      isImageHash(raw.image_sha256) ? raw.image_sha256 : null,
    ),
  };
}

export function filterLiveCameras(
  cameras: LiveCamera[],
  region: string,
  query: string,
): LiveCamera[] {
  const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  return cameras.filter(
    (camera) =>
      (!region || camera.region_id === region) &&
      words.every((word) =>
        `${camera.name} ${camera.roadway} ${camera.direction} ${camera.region_name}`
          .toLocaleLowerCase()
          .includes(word),
      ),
  );
}

export function cadenceLabel(seconds: number): string {
  return seconds >= 60
    ? `${Math.round(seconds / 60)} min`
    : `${Math.round(seconds)} sec`;
}
