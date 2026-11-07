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
}

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
        streaming_url: httpsLink(camera.streaming_url),
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
